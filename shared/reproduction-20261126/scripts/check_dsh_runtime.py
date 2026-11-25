import argparse
import binascii
import json
import os
import random
import string
import struct
import time
import zlib
from pathlib import Path

os.environ.setdefault("MSWEA_GLOBAL_CONFIG_DIR", str(Path.cwd() / "work/miniswe-config"))
os.environ.setdefault("MSWEA_SILENT_STARTUP", "1")

from course_eval.docker_target import DockerTarget
from course_eval.dsh_runner import run_sandbox
from course_eval.image_input import native_image_turn


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--platform", choices=("linux/amd64", "linux/arm64"), default="linux/amd64")
    parser.add_argument("--runtime", type=Path, default=Path("work/vmshare/dsh-linux-runtime"))
    parser.add_argument("--task-env-only", action="store_true")
    parser.add_argument("--model", default="hy4flash-free")
    parser.add_argument("--reasoning-effort", choices=("low", "high"), default="high")
    parser.add_argument("--tool-error-first", action="store_true")
    parser.add_argument("--first-response-delay-seconds", type=float, default=0)
    parser.add_argument("--stream-idle-timeout-ms", type=int, default=930000)
    parser.add_argument("--compaction-fixture", action="store_true")
    args = parser.parse_args()
    root = Path.cwd()
    os.environ.update(DOCKER_HOST="unix://" + str(root / "work/v/c/sock/docker.sock"),
                      DOCKER_CONFIG=str(root / "work/docker-config"),
                      COURSE_DOCKER_BIN=str(root / "work/vendor/docker/docker"))
    args.out.mkdir(parents=True, exist_ok=False)
    requests = []
    image_verified = False
    tool_error_verified = False
    ordinary_requests = 0
    summary_requests = []
    summary_adopted = False

    def png_chunk(kind, data):
        return struct.pack("!I", len(data)) + kind + data + struct.pack("!I", binascii.crc32(kind + data))

    image = args.out / "fixture.png"
    image.write_bytes(b"\x89PNG\r\n\x1a\n" + png_chunk(b"IHDR", struct.pack("!IIBBBBB", 8, 8, 8, 2, 0, 0, 0))
                      + png_chunk(b"IDAT", zlib.compress((b"\0" + bytes((0, 80, 160)) * 8) * 8))
                      + png_chunk(b"IEND", b""))

    def actual_tool_output(body, identity):
        message, = [item for item in body["messages"]
                    if item["role"] == "tool" and item.get("tool_call_id") == identity]
        if not isinstance(message["content"], str):
            raise ValueError("Expected the actual textual bash observation")
        return message["content"]

    def fixture(body, index):
        nonlocal image_verified, tool_error_verified, ordinary_requests, summary_adopted
        requests.append(body)
        tools = {row["function"]["name"] for row in body.get("tools", [])}
        if body["model"] != args.model or "bash" not in tools:
            raise ValueError("The actual SDK request selected an unexpected model or tool catalog")
        physical_index = index
        if len(requests) > 12:
            raise ValueError("The zero-model SDK fixture exceeded its twelve-request limit")
        last = body["messages"][-1].get("content", "")
        text = last if isinstance(last, str) else "\n".join(part.get("text", "") for part in last)
        if args.compaction_fixture and "compaction engine for this AI coding assistant" in text:
            if not 0 < body["max_tokens"] <= 64000:
                raise ValueError("The native summary request exceeded the real comparison output allowance")
            summary_requests.append(body)
            return {"status": 200, "body": {"id": f"fixture-summary-{physical_index}", "created": int(time.time()),
                "object": "chat.completion", "model": args.model,
                "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant",
                    "content": "## Current Work\nscripted-compaction-checkpoint: fixture shell variable COURSE_DSH_FIXTURE=retained; continue the scripted state and image check."}}],
                "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}}}
        ordinary_requests += 1
        index = ordinary_requests
        if args.compaction_fixture and "scripted-compaction-checkpoint" in json.dumps(body["messages"]):
            summary_adopted = True
        if index == 1 and args.first_response_delay_seconds:
            time.sleep(args.first_response_delay_seconds)
        if args.tool_error_first:
            if index == 1:
                return {"status": 200, "body": {"id": "fixture-invalid-tool", "created": int(time.time()),
                    "object": "chat.completion", "model": args.model,
                    "choices": [{"index": 0, "finish_reason": "tool_calls", "message": {"role": "assistant",
                        "content": "", "tool_calls": [{"id": "fixture-invalid-tool", "type": "function",
                            "function": {"name": "bash", "arguments": "{}"}}]}}],
                    "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}}}
            if index == 2:
                error = actual_tool_output(body, "fixture-invalid-tool")
                if "error" not in error.lower() and "invalid" not in error.lower():
                    raise ValueError("The invalid native tool arguments did not produce SDK error feedback")
                tool_error_verified = True
            index -= 1
        if index == 1:
            command = "export COURSE_DSH_FIXTURE=retained; printf 'fixture-first\\n'"
            if args.compaction_fixture:
                padding = "".join(random.Random(42).choices(string.ascii_letters + string.digits, k=8500))
                command += "; printf '%s\\n' '" + padding + "'"
        elif index == 2:
            if not (args.compaction_fixture and summary_adopted):
                observation = actual_tool_output(body, "fixture-1")
                if not observation.startswith("fixture-first\n") or "[Command finished with exit code 0]" not in observation:
                    raise ValueError("The actual first tool observation was not carried into the next request")
            path_check = ("test \"$PYTHONPATH\" = /course-public-task-path" if args.task_env_only else
                          "python -c 'import sys; assert \"/opt/course-harness/lib\" not in sys.path; "
                          "assert \"/course-public-task-path\" in sys.path'")
            command = (path_check + " && "
                       "test \"$COURSE_DSH_FIXTURE\" = retained && printf 'fixture-second\\n' > /course-dsh-proof.txt && cat /course-dsh-proof.txt")
        elif index == 3:
            observation = actual_tool_output(body, "fixture-2")
            if not observation.startswith("fixture-second\n") or "[Command finished with exit code 0]" not in observation:
                raise ValueError("The persistent-shell state or original Python environment check failed")
            command = None
        elif index == 4:
            prompt, count = native_image_turn(body["messages"])
            if count != 1 or not prompt:
                raise ValueError("The actual SDK image did not reach the native free-model input formatter")
            image_verified = True
            command = None
        else:
            raise RuntimeError("The four-request protocol fixture budget was exceeded")
        final = index == 4
        message = {"role": "assistant", "content": "Offline protocol fixture completed." if final else ""}
        if command is not None:
            message["tool_calls"] = [{"id": f"fixture-{index}", "type": "function",
                                      "function": {"name": "bash", "arguments": json.dumps({"command": command})}}]
        elif index == 3:
            message["tool_calls"] = [{"id": "fixture-image", "type": "function",
                "function": {"name": "read_image", "arguments": json.dumps({"file_path": "/course-dsh-fixture.png"})}}]
        return {"status": 200, "body": {"id": f"fixture-{physical_index}", "created": int(time.time()),
            "object": "chat.completion", "model": args.model, "choices": [{"index": 0, "message": message,
            "finish_reason": "stop" if final else "tool_calls"}],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}}}

    fixture.model_id, fixture.reasoning_effort = args.model, args.reasoning_effort
    fixture.stream_idle_timeout_ms = args.stream_idle_timeout_ms
    fixture.compaction_fixture = args.compaction_fixture
    with DockerTarget(args.image, "/app", platform=args.platform, memory_mb=1536, cpus=1,
            read_only_mounts=((str(args.runtime.resolve(strict=True)), "/opt/course-harness"),),
            environment={"PYTHONPATH": "/course-public-task-path"},
            read_only_empty_dirs=("/tests",)) as target:
        target.upload_file(image.resolve(), "/course-dsh-fixture.png")
        result = run_sandbox(target, args.out, "Execute the offline protocol fixture supplied by the test adapter.",
                             fixture, timeout=max(180, args.first_response_delay_seconds + 90))
        proof = target.exec("cat /course-dsh-proof.txt", timeout=10)
        if proof["returncode"] or proof["stdout"] != "fixture-second\n":
            raise AssertionError(proof)
    report = {"mode": "Scripted protocol fixture, not real model inference",
              "selected_model": args.model, "reasoning_effort": args.reasoning_effort,
              "first_response_delay_seconds": args.first_response_delay_seconds,
              "stream_idle_timeout_ms": args.stream_idle_timeout_ms,
              "ordinary_requests": ordinary_requests,
              "native_summary_requests": len(summary_requests), "native_summary_adopted": summary_adopted,
              "history_mode": "native_checkpoint_and_raw_tail" if summary_adopted else "raw_tool_observations",
              "invalid_tool_feedback_and_recovery_verified": tool_error_verified if args.tool_error_first else None,
              "new_model_calls": 0, "original_grader_calls": 0, "synthetic_usage_is_not_billing_evidence": True,
              "actual_sdk": result, "persistent_bash_state_verified": True,
              "observation_history_verified": True, "original_python_environment_clean": None if args.task_env_only else True,
              "task_python_import_checked": not args.task_env_only,
              "fixture_public_pythonpath_retained": True,
              "native_image_turn_verified": image_verified, "protocol_requests": len(requests), "passed": image_verified}
    (args.out / "result.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False))
    if (not report["passed"] or ordinary_requests != 4 + int(args.tool_error_first)
            or args.compaction_fixture and (not summary_requests or not summary_adopted)
            or args.tool_error_first and not tool_error_verified):
        raise AssertionError("The actual SDK state/image fixture did not complete its fixed path")


if __name__ == "__main__":
    main()
