import json
import os
import shlex
import subprocess
import uuid

from pydantic import BaseModel, ConfigDict


class RPCResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    ok: bool
    call_id: str
    metadata: dict
    payload: dict | None = None
    http_status: int | None = None
    request_id: str | None = None
    error_type: str | None = None
    timeout: bool = False
    response_body: str | None = None
    retry_after: str | None = None
    seconds: float


class BoyueTimeout(TimeoutError):
    def __init__(self, diagnostics):
        self.diagnostics = diagnostics
        super().__init__("Boyue request deadline exceeded")


class BoyueTransportError(RuntimeError):
    def __init__(self, diagnostics):
        self.diagnostics = diagnostics
        super().__init__("Boyue transport failed: " + diagnostics["error_type"])


class BoyueTransport:
    def __init__(self):
        # 此命令来自可信的课程环境配置，模型输出不能改变远端入口或地址。
        self.command = shlex.split(os.environ["COURSE_BOYUE_RPC_COMMAND"])
        if not self.command or self.command[0] != "ssh":
            raise ValueError("The course Boyue transport requires the configured SSH entry point")

    def metadata(self):
        process = subprocess.run([*self.command, "--metadata"], text=True, capture_output=True,
                                 timeout=20, check=True)
        return json.loads(process.stdout)

    def send(self, payload, timeout_seconds):
        call_id = uuid.uuid4().hex
        request = {"call_id": call_id, "timeout_seconds": max(0.1, float(timeout_seconds) - 4),
                   "payload": payload}
        try:
            process = subprocess.run(self.command, input=json.dumps(request, ensure_ascii=False),
                                     text=True, capture_output=True, timeout=timeout_seconds, check=False)
        except subprocess.TimeoutExpired:
            raise BoyueTimeout({"error_type": "SSHRequestTimeout", "call_id": call_id,
                                "timeout_seconds": timeout_seconds}) from None
        if process.returncode:
            raise BoyueTransportError({"error_type": "SSHProcessError", "call_id": call_id,
                                       "returncode": process.returncode})
        try:
            response = RPCResponse.model_validate_json(process.stdout)
        except ValueError:
            raise BoyueTransportError({"error_type": "RPCResponseSchemaError", "call_id": call_id}) from None
        if response.call_id != call_id:
            raise BoyueTransportError({"error_type": "RPCCallIdentityMismatch", "call_id": call_id})
        if not response.ok:
            diagnostics = response.model_dump(exclude_none=True)
            if response.timeout:
                raise BoyueTimeout(diagnostics)
            raise BoyueTransportError(diagnostics)
        if response.payload is None:
            raise BoyueTransportError({"error_type": "RPCMissingPayload", "call_id": call_id})
        return response
