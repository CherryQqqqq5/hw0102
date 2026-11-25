import argparse
import hashlib
import json
import signal
import sys
import time
from pathlib import Path
from typing import Any

import openai
import httpx2
import pydantic
from openai import DefaultHttpxClient, OpenAI
from pydantic import BaseModel, ConfigDict, Field


BASE_URL = "https://apicz.boyuerichdata.com/v1"


class RPCRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    call_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    timeout_seconds: float = Field(gt=0, le=150)
    payload: dict[str, Any]


class RequestDeadline(TimeoutError):
    pass


def sdk_metadata():
    return {"openai": openai.__version__, "base_url": BASE_URL,
            "python": sys.version, "pydantic": pydantic.__version__, "httpx2": httpx2.__version__,
            "transport": "openai-sdk-chat-completions-via-ssh", "sdk_retries": 0,
            "follow_redirects": False,
            "runtime_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}


def call(request, credential_file, output):
    # 密钥仅在远端读取，不进入模型参数、命令行或证据文件。
    if (credential_file.is_symlink() or not credential_file.is_file()
            or credential_file.stat().st_mode & 0o077):
        raise ValueError("Credential must be a private regular file")
    key = credential_file.read_text().strip()
    if not key or any(character.isspace() for character in key):
        raise ValueError("Credential is empty or contains whitespace")
    payload = request.payload
    if (payload.get("model") != "deepseek-v4-pro-0813" or payload.get("stream") is not False
            or payload.get("reasoning_effort") != "max" or payload.get("max_tokens", 0) > 32768):
        raise ValueError("Request is outside the course provider contract")
    directory = output / request.call_id
    directory.mkdir(parents=True, exist_ok=False)
    (directory / "request.json").write_text(json.dumps(payload, ensure_ascii=False) + "\n")
    started = time.monotonic()

    def expired(*_):
        raise RequestDeadline("Request deadline exceeded")

    previous = signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, request.timeout_seconds)
    response = {"ok": False, "call_id": request.call_id, "metadata": sdk_metadata()}
    try:
        with OpenAI(base_url=BASE_URL, api_key=key, max_retries=0, timeout=request.timeout_seconds,
                    http_client=DefaultHttpxClient(follow_redirects=False)) as client:
            raw = client.chat.completions.with_raw_response.create(**payload)
            body = raw.text.replace(key, "[REDACTED_CREDENTIAL]")
            (directory / "response-body.json").write_text(body)
            parsed = json.loads(body)
            raw.parse()
            response.update(ok=True, payload=parsed, http_status=raw.status_code,
                            request_id=raw.headers.get("x-request-id"))
    except (RequestDeadline, openai.APITimeoutError) as exc:
        response.update(error_type=type(exc).__name__, timeout=True)
    except openai.APIStatusError as exc:
        response.update(error_type=type(exc).__name__, http_status=exc.status_code,
                        response_body=exc.response.text.replace(key, "[REDACTED_CREDENTIAL]"),
                        retry_after=exc.response.headers.get("retry-after"))
    except (openai.APIError, ValueError, TypeError) as exc:
        # 异常文本可能包含请求和认证信息，只记录异常类型。
        response.update(error_type=type(exc).__name__)
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)
    response["seconds"] = time.monotonic() - started
    (directory / "result.json").write_text(json.dumps(response, ensure_ascii=False) + "\n")
    return response


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--credential-file", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--metadata", action="store_true")
    args = parser.parse_args()
    if args.metadata:
        print(json.dumps(sdk_metadata()))
        return
    if args.credential_file is None or args.output is None:
        parser.error("Requests require --credential-file and --output")
    request = RPCRequest.model_validate_json(sys.stdin.read())
    print(json.dumps(call(request, args.credential_file, args.output), ensure_ascii=False))


if __name__ == "__main__":
    main()
