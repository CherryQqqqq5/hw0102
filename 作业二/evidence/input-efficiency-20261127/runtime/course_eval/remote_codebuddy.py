import argparse
import hashlib
import json
import os
import socket
import socketserver
import subprocess
import tempfile
import time
import uuid
from dataclasses import dataclass
from pathlib import Path


MAX_BYTES = 64 * 1024**2
FIXED = {"--model": "hy4flash-free", "--tools": "StructuredOutput", "--allowedTools": "StructuredOutput",
    "--permission-mode": "dontAsk", "--max-turns": "1", "--output-format": "json",
    "--setting-sources": "", "--settings": '{"disableAllHooks":true}', "--mcp-config": '{"mcpServers":{}}'}


@dataclass
class Invocation:
    args: list[str]
    prompt: str
    timeout: float
    max_output_tokens: int
    session: str
    request_id: int

    def __post_init__(self):
        if (not isinstance(self.args, list) or not all(isinstance(arg, str) for arg in self.args)
                or not isinstance(self.prompt, str) or not isinstance(self.timeout, (int, float))
                or not 0 < self.timeout <= 1800 or type(self.max_output_tokens) is not int
                or not 0 < self.max_output_tokens <= 64000
                or type(self.request_id) is not int or self.request_id < 1):
            raise ValueError("Invalid free-client invocation")
        uuid.UUID(self.session)
        flags = dict(FIXED)
        flags.update({"--json-schema": None, "--system-prompt": None})
        session_flags = []
        remaining = list(self.args)
        for flag in ("--print", "--strict-mcp-config"):
            if remaining.count(flag) != 1:
                raise ValueError("Missing required isolated-client flag")
            remaining.remove(flag)
        while remaining:
            flag = remaining.pop(0)
            if flag == "Choose the next command from the conversation on stdin." and not remaining:
                break
            if not remaining:
                raise ValueError("Incomplete client option")
            value = remaining.pop(0)
            if flag in {"--session-id", "--resume"}:
                session_flags.append(flag)
                if value != self.session:
                    raise ValueError("Client session identity differs")
            elif flag in flags:
                expected = flags.pop(flag)
                if expected is not None and value != expected:
                    raise ValueError("Only the fixed free structured-output client is admitted")
            elif flag != "--input-format" or value != "stream-json":
                raise ValueError("Unexpected free-client option")
        if flags or len(session_flags) != 1:
            raise ValueError("Incomplete fixed free-client invocation")


def invoke(model, command, prompt, environment, timeout):
    request = Invocation(command[1:], prompt, timeout, model.limits.max_output_tokens,
        model.native_session_id, model.request_id)
    socket_path = environment["COURSE_CODEBUDDY_RELAY_SOCKET"]
    with socket.socket(socket.AF_UNIX) as connection:
        connection.settimeout(timeout + 15)
        connection.connect(socket_path)
        connection.sendall(json.dumps(request.__dict__).encode() + b"\n")
        stream = connection.makefile("rwb")
        body = stream.readline(MAX_BYTES + 1)
        if not body.endswith(b"\n") or len(body) > MAX_BYTES:
            raise RuntimeError("The actual client relay response is incomplete")
        record = json.loads(body)
        folder = model.run_dir / "relay"
        folder.mkdir(exist_ok=True)
        path = folder / f"request-{model.request_id:05d}.json"
        with path.open("xb") as handle:
            handle.write(body)
            handle.flush()
            os.fsync(handle.fileno())
        stream.write(json.dumps({"stored_sha256": hashlib.sha256(body).hexdigest()}).encode() + b"\n")
        stream.flush()
    if record["client_sha256"] != environment["COURSE_CODEBUDDY_RELAY_CLIENT_SHA256"]:
        raise RuntimeError("The actual authenticated client differs from its frozen source")
    if (record["native_session_id"], record["request_id"]) != (request.session, request.request_id):
        raise RuntimeError("The actual relay response belongs to a different model request")
    if record["timeout"]:
        error = subprocess.TimeoutExpired(command, timeout, output=record["stdout"], stderr=record["stderr"])
        error.provider_diagnostics = record["diagnostics"]
        raise error
    return subprocess.CompletedProcess(command, record["returncode"], record["stdout"], record["stderr"])


class Handler(socketserver.StreamRequestHandler):
    def handle(self):
        body = self.rfile.readline(MAX_BYTES + 1)
        if len(body) > MAX_BYTES or not body.endswith(b"\n"):
            raise ValueError("The free-client request is incomplete")
        decoded = json.loads(body)
        if decoded == {"event": "info"}:
            self.wfile.write(json.dumps({"client_sha256": self.server.client_sha256,
                "client_version": self.server.client_version, "new_model_calls": 0}).encode() + b"\n")
            self.wfile.flush()
            return
        request = Invocation(**decoded)
        directory = self.server.state / "sessions" / request.session
        directory.mkdir(parents=True, exist_ok=True)
        environment = os.environ.copy()
        for key in ("CODEBUDDY_FALLBACK_MODEL", "WORKBUDDY_PROXY_SOURCE", "CODEBUDDY_FORCE_LITE_WB_BUNDLE"):
            environment.pop(key, None)
        environment.update(NODE_OPTIONS="--use-bundled-ca", CODEBUDDY_MAX_RETRIES="0",
            HTTP_PROXY="http://127.0.0.1:7890", HTTPS_PROXY="http://127.0.0.1:7890",
            NO_PROXY="localhost,127.0.0.1,::1",
            CODEBUDDY_MODEL_401_MAX_RETRIES="0", CODEBUDDY_RETRY_WATCHDOG="0",
            CODEBUDDY_CODE_MAX_OUTPUT_TOKENS=str(request.max_output_tokens),
            CODEBUDDY_MODEL="hy4flash-free", CODEBUDDY_SMALL_FAST_MODEL="hy4flash-free",
            CODEBUDDY_BIG_SLOW_MODEL="hy4flash-free", CODEBUDDY_DISABLE_PROXY_CONFIG_FILE="1",
            COURSE_CODEBUDDY_EXTERNAL_RECOVERY="1", CODEBUDDY_CODE_DISABLE_SESSION_SUMMARY="1",
            CODEBUDDY_PROJECT_CONFIG_DIR=str(directory / "native-session"))
        started = time.monotonic()
        timed_out = False
        with tempfile.TemporaryFile(mode="w+", encoding="utf-8", dir=directory) as output, \
                subprocess.Popen([str(self.server.cli), *request.args], stdin=subprocess.PIPE,
                    stdout=output, stderr=subprocess.PIPE, cwd=directory, env=environment, text=True) as process:
            try:
                _, stderr = process.communicate(request.prompt, timeout=max(1, request.timeout - 5))
            except subprocess.TimeoutExpired:
                timed_out = True
                process.kill()
                _, stderr = process.communicate()
            output.seek(0)
            result = {"stdout": output.read(), "stderr": stderr, "returncode": process.returncode,
                "timeout": timed_out, "elapsed_seconds": time.monotonic() - started,
                "native_session_id": request.session, "request_id": request.request_id,
                "diagnostics": {"source": "actual authenticated client relay", "pid": process.pid,
                    "billing_status": "Not inferred; receiver checks the actual provider receipt"},
                "client_sha256": self.server.client_sha256}
        response = json.dumps(result, ensure_ascii=False).encode() + b"\n"
        pending = self.server.state / "pending"
        pending.mkdir(exist_ok=True)
        path = pending / (str(uuid.uuid4()) + ".json")
        path.write_bytes(response)
        if len(response) > MAX_BYTES:
            raise RuntimeError("The actual client response exceeds the registered envelope; retained in pending")
        self.wfile.write(response)
        self.wfile.flush()
        self.connection.settimeout(15)
        acknowledgment = json.loads(self.rfile.readline(1024))
        if acknowledgment != {"stored_sha256": hashlib.sha256(response).hexdigest()}:
            raise RuntimeError("The actual response has not been durably saved on ModelArts")
        path.unlink()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--socket", type=Path, required=True)
    parser.add_argument("--cli", type=Path, required=True)
    parser.add_argument("--state", type=Path, required=True)
    args = parser.parse_args()
    args.state.mkdir(parents=True, exist_ok=True, mode=0o700)
    if args.socket.exists():
        raise FileExistsError(args.socket)
    with socketserver.UnixStreamServer(str(args.socket), Handler) as server:
        os.chmod(args.socket, 0o600)
        server.cli, server.state = args.cli.resolve(strict=True), args.state.resolve()
        bundle = server.cli.parent.parent / "dist/codebuddy-headless.js"
        server.client_sha256 = hashlib.sha256(bundle.read_bytes()).hexdigest()
        server.client_version = subprocess.check_output([str(server.cli), "--version"], text=True, timeout=30).strip()
        print(json.dumps({"status": "listening", "socket": str(args.socket),
            "client_sha256": server.client_sha256, "client_version": server.client_version,
            "new_model_calls": 0}), flush=True)
        server.serve_forever(poll_interval=0.5)


if __name__ == "__main__":
    main()
