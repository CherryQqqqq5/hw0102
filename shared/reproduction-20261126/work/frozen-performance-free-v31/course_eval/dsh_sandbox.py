import argparse
import json
import os
import selectors
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


RPC_LOCK = threading.Lock()


def emit(event, **fields):
    print(json.dumps({"event": event, **fields}, ensure_ascii=False), flush=True)


class LocalModelGateway(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def do_GET(self):
        if self.path != "/v1/models":
            self.send_error(404)
            return
        self.send_json(200, {"object": "list", "data": [{"id": getattr(self.server, "model_id", "hy4flash-free"), "object": "model"}]})

    def send_json(self, status, body):
        data = json.dumps(body, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def heartbeat(self):
        self.wfile.write(b": local bridge awaiting a verified response\n\n")
        self.wfile.flush()

    @staticmethod
    def receive_response(streaming, heartbeat=None):
        pending = bytearray()
        with selectors.DefaultSelector() as selector:
            selector.register(sys.stdin.fileno(), selectors.EVENT_READ)
            while True:
                if not selector.select(15):
                    if streaming and heartbeat is not None:
                        heartbeat()
                    continue
                chunk = os.read(sys.stdin.fileno(), 65536)
                if not chunk:
                    if pending:
                        raise ValueError("The host closed an incomplete bridge response")
                    return None
                pending.extend(chunk)
                if len(pending) > 64 * 1024 * 1024:
                    raise ValueError("The verified bridge response exceeds its bounded envelope")
                if b"\n" in pending:
                    line, remainder = pending.split(b"\n", 1)
                    if remainder.strip():
                        raise ValueError("The host sent unsolicited extra bridge responses")
                    return json.loads(line)

    def do_POST(self):
        if self.path != "/v1/chat/completions":
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", "0"))
        if not 0 < length <= 32 * 1024 * 1024:
            self.send_error(413)
            return
        request = json.loads(self.rfile.read(length))
        if request.get("model") != getattr(self.server, "model_id", "hy4flash-free"):
            self.send_json(400, {"error": {"message": "The requested model differs from the fixed free profile"}})
            return
        with RPC_LOCK:
            emit("model_request", payload=request)
            streaming = bool(request.get("stream"))
            if streaming:
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Connection", "close")
                self.end_headers()
                self.heartbeat()
            response = self.receive_response(streaming, self.heartbeat)
            if response is None:
                error = {"error": {"message": "The host billing-gated bridge closed before a verified response"}}
                if streaming:
                    self.wfile.write(("data: " + json.dumps(error) + "\n\ndata: [DONE]\n\n").encode())
                    self.wfile.flush()
                else:
                    self.send_json(503, error)
                return
        status, body = response["status"], response["body"]
        if not streaming:
            self.send_json(status, body)
            return
        if status != 200:
            error = {"error": body.get("error", body), "upstream_status": status}
            self.wfile.write(("data: " + json.dumps(error) + "\n\ndata: [DONE]\n\n").encode())
            self.wfile.flush()
            return
        choice, = body["choices"]
        message = choice["message"]
        delta = {"role": "assistant"}
        if message.get("content"):
            delta["content"] = message["content"]
        if message.get("reasoning_content"):
            delta["reasoning_content"] = message["reasoning_content"]
        if message.get("tool_calls"):
            delta["tool_calls"] = [call | {"index": index}
                                   for index, call in enumerate(message["tool_calls"])]
        common = {key: body[key] for key in ("id", "model", "created")}
        common["object"] = "chat.completion.chunk"
        chunks = [common | {"choices": [{"index": 0, "delta": delta, "finish_reason": None}]},
                  common | {"choices": [{"index": 0, "delta": {}, "finish_reason": choice["finish_reason"]}],
                            "usage": body["usage"]}]
        for chunk in chunks:
            self.wfile.write(("data: " + json.dumps(chunk, ensure_ascii=False) + "\n\n").encode())
        self.wfile.write(b"data: [DONE]\n\n")
        self.wfile.flush()


def profile_patch(endpoint, model="hy4flash-free", reasoning_effort="high", stream_idle_timeout_ms=930000,
                  compaction_fixture=False):
    context_window = 262144 if model == "mistralai/mistral-large-4-1t-a52b" else 960000
    compaction = {"maxTokens": 64000}
    if compaction_fixture:
        compaction.update(thresholdRatio=0.01, retainTokens=128)
    return [
        {"id": "llm-deepseek", "disabled": True},
        {"id": "session-log-deepseek", "config": {"enabled": False}},
        {"id": "plugin-package-inventory-deepseek", "disabled": True},
        {"id": "session-title", "disabled": True},
        {"id": "compaction-basic", "config": compaction},
        {"id": "persistent-bash", "config": {"timeoutMs": 120000, "maxOutputChars": 10000,
            "description": "Run commands in the isolated task's persistent bash shell. The task has no external network access."}},
        {"id": "terminal-bash", "config": {"timeoutMs": 120000}},
        {"insert": [{"id": "llm-course-free", "name": "@deepseek-ai/dsh-llm-pi-ai", "config": {
            "providers": {"course-free": {"apiKeyEnv": "COURSE_DSH_LOCAL_PLACEHOLDER_KEY",
                "api": "openai-completions", "baseURL": endpoint,
                "timeoutMs": 3600000, "streamIdleTimeoutMs": stream_idle_timeout_ms,
                "retryPolicy": {"mode": "normal", "maxRetries": 0},
                "compat": {"supportsDeveloperRole": False, "maxTokensField": "max_tokens"},
                "models": [{"id": model, "input": ["text", "image"],
                    "contextWindow": context_window, "maxTokens": 64000,
                    "reasoningEfforts": {reasoning_effort: reasoning_effort}}]}}}}]},
    ]


def main():
    from deepseek_harness import DeepSeekHarness

    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    args = parser.parse_args()
    settings = json.loads(args.input.read_text())
    home = Path("/course-dsh-home")
    (home / "tmp").mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(("127.0.0.1", 0), LocalModelGateway)
    server.daemon_threads = True
    server.model_id = settings.get("model", "hy4flash-free")
    reasoning_effort = settings.get("reasoning_effort", "high")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    patch = home / "free-provider.patch.json"
    patch.write_text(json.dumps(profile_patch(f"http://127.0.0.1:{server.server_port}/v1",
                                               server.model_id, reasoning_effort,
                                               settings.get("stream_idle_timeout_ms", 930000),
                                               settings.get("compaction_fixture", False))))
    emit("sandbox_started", pid=os.getpid(), supervisor_pid=os.getppid(), cwd=os.getcwd(),
         sdk_version="0.2.2rc2", network="loopback model bridge only")
    try:
        with DeepSeekHarness(provider="course-free", model=server.model_id, reasoning_effort=reasoning_effort,
                max_tokens=settings["max_output_tokens"], cwd=os.getcwd(), dsh_home=str(home),
                profile="sdk-minimal", patches=(str(patch),),
                env={"COURSE_DSH_LOCAL_PLACEHOLDER_KEY": "local-pipe-bridge-no-provider-key",
                     "TMPDIR": str(home / "tmp"), "PYTHONPATH": settings["task_pythonpath"]}, initialize_timeout_seconds=90,
                request_timeout_seconds=settings["wall_seconds"], shutdown_timeout_seconds=10) as harness:
            review_rounds = settings.get("post_review_max_rounds", 0)
            if type(review_rounds) is not int or review_rounds not in (0, 2):
                raise ValueError("The submission-review policy requires its fixed zero-or-two repair bound")
            stage_results = []
            instruction = settings["instruction"]
            for stage in range(review_rounds + 1):
                result = harness.run(instruction, session_id="course-task")
                stage_results.append({"finish_reason": result.finish_reason, "events": len(result.events),
                                      "notifications": len(result.notifications)})
                if not review_rounds or result.finish_reason not in {"completed", "max-tokens"}:
                    break
                with RPC_LOCK:
                    emit("public_review_requested", stage=stage)
                    packet = LocalModelGateway.receive_response(False)
                if (not isinstance(packet, dict) or set(packet) != {"continue", "verification_passed", "feedback"}
                        or type(packet["continue"]) is not bool or type(packet["verification_passed"]) is not bool
                        or not isinstance(packet["feedback"], str) or len(packet["feedback"].encode()) > 8 * 1024 * 1024
                        or (packet["continue"] and (packet["verification_passed"] or stage >= review_rounds))):
                    raise ValueError("The host returned an invalid native-session review packet")
                if not packet["continue"]:
                    break
                instruction = packet["feedback"]
            emit("sdk_result", result={"session_id": result.session_id, "final_response": result.final_response,
                "finish_reason": result.finish_reason, "events": len(result.events),
                "termination_reason": next((event.get("data", {}).get("reason") for event in reversed(result.events)
                    if event.get("type") == "turn/end"), None),
                "notifications": len(result.notifications), "sdk_turns": len(stage_results),
                "sdk_stage_results": stage_results})
    except BaseException as exc:
        emit("sdk_error", error_type=type(exc).__name__, detail=str(exc))
        raise
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
