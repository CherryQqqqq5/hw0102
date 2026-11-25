import argparse
import json
import os
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
        self.send_json(200, {"object": "list", "data": [{"id": "hy4flash-free", "object": "model"}]})

    def send_json(self, status, body):
        data = json.dumps(body, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        if self.path != "/v1/chat/completions":
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", "0"))
        if not 0 < length <= 32 * 1024 * 1024:
            self.send_error(413)
            return
        request = json.loads(self.rfile.read(length))
        if request.get("model") != "hy4flash-free":
            self.send_json(400, {"error": {"message": "Only hy4flash-free is admitted"}})
            return
        with RPC_LOCK:
            emit("model_request", payload=request)
            line = sys.stdin.readline()
            if not line:
                self.send_json(503, {"error": {"message": "The host billing-gated bridge closed"}})
                return
            response = json.loads(line)
        status, body = response["status"], response["body"]
        if status != 200 or not request.get("stream"):
            self.send_json(status, body)
            return
        choice, = body["choices"]
        message = choice["message"]
        delta = {"role": "assistant"}
        if message.get("content"):
            delta["content"] = message["content"]
        if message.get("tool_calls"):
            delta["tool_calls"] = [call | {"index": index}
                                   for index, call in enumerate(message["tool_calls"])]
        common = {key: body[key] for key in ("id", "model", "created")}
        common["object"] = "chat.completion.chunk"
        chunks = [common | {"choices": [{"index": 0, "delta": delta, "finish_reason": None}]},
                  common | {"choices": [{"index": 0, "delta": {}, "finish_reason": choice["finish_reason"]}],
                            "usage": body["usage"]}]
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Connection", "close")
        self.end_headers()
        for chunk in chunks:
            self.wfile.write(("data: " + json.dumps(chunk, ensure_ascii=False) + "\n\n").encode())
        self.wfile.write(b"data: [DONE]\n\n")
        self.wfile.flush()


def profile_patch(endpoint):
    return [
        {"id": "llm-deepseek", "disabled": True},
        {"id": "session-log-deepseek", "config": {"enabled": False}},
        {"id": "plugin-package-inventory-deepseek", "disabled": True},
        {"id": "session-title", "disabled": True},
        {"id": "persistent-bash", "config": {"timeoutMs": 120000, "maxOutputChars": 10000,
            "description": "Run commands in the isolated task's persistent bash shell. The task has no external network access."}},
        {"id": "terminal-bash", "config": {"timeoutMs": 120000}},
        {"insert": [{"id": "llm-course-free", "name": "@deepseek-ai/dsh-llm-pi-ai", "config": {
            "providers": {"course-free": {"apiKeyEnv": "COURSE_DSH_LOCAL_PLACEHOLDER_KEY",
                "api": "openai-completions", "baseURL": endpoint,
                "retryPolicy": {"mode": "normal", "maxRetries": 0},
                "compat": {"supportsDeveloperRole": False, "maxTokensField": "max_tokens"},
                "models": [{"id": "hy4flash-free", "input": ["text", "image"],
                    "contextWindow": 960000, "maxTokens": 64000, "reasoningEfforts": {"high": "high"}}]}}}}]},
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
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    patch = home / "free-provider.patch.json"
    patch.write_text(json.dumps(profile_patch(f"http://127.0.0.1:{server.server_port}/v1")))
    emit("sandbox_started", pid=os.getpid(), supervisor_pid=os.getppid(), cwd=os.getcwd(),
         sdk_version="0.2.2rc2", network="loopback model bridge only")
    try:
        with DeepSeekHarness(provider="course-free", model="hy4flash-free", reasoning_effort="high",
                max_tokens=settings["max_output_tokens"], cwd=os.getcwd(), dsh_home=str(home),
                profile="sdk-minimal", patches=(str(patch),),
                env={"COURSE_DSH_LOCAL_PLACEHOLDER_KEY": "local-pipe-bridge-no-provider-key",
                     "TMPDIR": str(home / "tmp"), "PYTHONPATH": settings["task_pythonpath"]}, initialize_timeout_seconds=90,
                request_timeout_seconds=settings["wall_seconds"], shutdown_timeout_seconds=10) as harness:
            result = harness.run(settings["instruction"], session_id="course-task")
            emit("sdk_result", result={"session_id": result.session_id, "final_response": result.final_response,
                "finish_reason": result.finish_reason, "events": len(result.events),
                "notifications": len(result.notifications)})
    except BaseException as exc:
        emit("sdk_error", error_type=type(exc).__name__, detail=str(exc))
        raise
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
