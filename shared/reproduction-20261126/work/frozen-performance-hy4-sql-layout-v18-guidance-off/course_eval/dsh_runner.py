import json
import os
import selectors
import shlex
import subprocess
import time
from pathlib import Path

from course_eval.sandbox_command import CONTAINER_COMMAND


def runtime_mounts(platform):
    if os.environ.get("COURSE_AGENT_FRAMEWORK", "mini-swe") != "dsh":
        return ()
    variable = {"linux/amd64": "COURSE_DSH_RUNTIME", "linux/arm64": "COURSE_DSH_RUNTIME_ARM64"}[platform]
    source = Path(os.environ[variable]).resolve(strict=True)
    if not (source / "python/bin/python3").is_file() or not (source / "lib/deepseek_harness").is_dir():
        raise ValueError("The official standalone DSH runtime is incomplete")
    return ((str(source), "/opt/course-harness"),)


def run_course_dsh(task, target, directory, limits):
    from minisweagent.exceptions import FormatError, TimeExceeded

    from course_eval.dsh_free import DshFreeProvider

    if not hasattr(target, "container") or not hasattr(target, "docker"):
        raise ValueError("DSH requires the verified direct Docker task transport")
    (directory / "instruction.txt").write_text(task)
    provider = DshFreeProvider(directory, limits, os.environ["COURSE_FREE_STOP_PATH"])
    started = time.monotonic()
    try:
        result = run_sandbox(target, directory / "dsh", task, provider,
                             timeout=limits.wall_seconds, max_output_tokens=limits.max_output_tokens)
        return {"exit_status": "Submitted" if result["finish_reason"] == "completed" else result["finish_reason"],
                "submission": result["final_response"], "framework": "deepseek-harness-sdk-0.2.2rc2",
                "sdk_result": result}
    except (FormatError, TimeExceeded) as exc:
        return {"exit_status": type(exc).__name__, "submission": "", "termination_messages": exc.messages,
                "framework": "deepseek-harness-sdk-0.2.2rc2"}
    except TimeoutError as exc:
        return {"exit_status": "TimeExceeded", "submission": "", "termination_detail": str(exc),
                "framework": "deepseek-harness-sdk-0.2.2rc2"}
    finally:
        provider.preserve_billing_stop()
        (directory / "execution-budget.json").write_text(json.dumps({
            "limit_seconds": limits.wall_seconds, "elapsed_seconds": time.monotonic() - started,
            "actual_cli_generations": provider.request_id, "framework": "dsh", "strict": True}, indent=2) + "\n")


def run_sandbox(target, directory, instruction, reply, *, timeout=3600, max_output_tokens=64000):
    directory.mkdir(parents=True, exist_ok=True)
    source = Path(__file__).with_name("dsh_sandbox.py")
    target.upload_file(source, "/course-dsh-sandbox.py")
    pythonpath = target.exec("printf '%s' \"${PYTHONPATH-}\"", timeout=5)
    if pythonpath["returncode"]:
        raise RuntimeError("Cannot read the original isolated task's Python module path")
    settings = directory / "dsh-input.json"
    settings.write_text(json.dumps({"instruction": instruction, "wall_seconds": timeout,
                                   "max_output_tokens": max_output_tokens,
                                   "task_pythonpath": pythonpath["stdout"]}, ensure_ascii=False))
    target.upload_file(settings.resolve(), "/course-dsh-input.json")
    command = [target.binary, "exec", "-i", "-w", target.cwd,
               "-e", "PYTHONPATH=/opt/course-harness/lib", "-e", "TMPDIR=/course-dsh-home/tmp",
               target.container, "timeout", "--foreground", "--signal=USR1", "--kill-after=3s", f"{timeout}s",
               "bash", "-c", CONTAINER_COMMAND.replace('bash -c "$1" &', 'bash -c "$1" <&0 &'),
               "course-dsh", "exec " + shlex.join(("/opt/course-harness/python/bin/python3",
                                                    "/course-dsh-sandbox.py", "--input", "/course-dsh-input.json"))]
    started = time.monotonic()
    result = None
    supervisor = None
    requests = 0
    pending = b""
    with (directory / "dsh-stderr.log").open("x") as error, \
            (directory / "dsh-transport.jsonl").open("x") as log, \
            subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=error) as process, \
            selectors.DefaultSelector() as selector:
        selector.register(process.stdout, selectors.EVENT_READ)
        try:
            while True:
                remaining = timeout - (time.monotonic() - started)
                if remaining <= 0:
                    raise TimeoutError("The complete DSH sandbox exceeded its shared execution deadline")
                if not selector.select(min(1, remaining)):
                    if process.poll() is not None:
                        break
                    continue
                chunk = os.read(process.stdout.fileno(), 65536)
                if not chunk:
                    if pending.strip():
                        raise ValueError("DSH transport ended with an incomplete JSON event")
                    break
                pending += chunk
                if len(pending) > 64 * 1024 * 1024:
                    raise ValueError("DSH transport event exceeds the bounded request envelope")
                while b"\n" in pending:
                    line, pending = pending.split(b"\n", 1)
                    event = json.loads(line)
                    log.write(json.dumps(event, ensure_ascii=False) + "\n")
                    log.flush()
                    if event["event"] == "sandbox_started":
                        supervisor = event["supervisor_pid"]
                        if type(supervisor) is not int or supervisor <= 1:
                            raise ValueError("Missing exact sandbox supervisor identity")
                    elif event["event"] == "model_request":
                        requests += 1
                        response = reply(event["payload"], requests)
                        process.stdin.write((json.dumps(response, ensure_ascii=False) + "\n").encode())
                        process.stdin.flush()
                    elif event["event"] == "sdk_result":
                        result = event["result"]
                    elif event["event"] == "sdk_error":
                        raise RuntimeError(event)
                    else:
                        raise ValueError("Unknown DSH transport event: " + str(event.get("event")))
            process.wait(timeout=15)
            if process.returncode == 124:
                raise TimeoutError("The DSH sandbox command reached its shared execution deadline")
            if process.returncode or result is None:
                raise RuntimeError(f"DSH runtime exited {process.returncode} without a complete result; inspect {directory / 'dsh-stderr.log'}")
        except BaseException:
            if supervisor is not None:
                target.exec("kill -USR1 " + str(supervisor), timeout=10)
            if process.poll() is None:
                process.kill()
            process.wait(timeout=15)
            raise
        finally:
            evidence = directory / "dsh-home"
            evidence.mkdir(exist_ok=True)
            for name in ("sessions", "attachments", "free-provider.patch.json"):
                copied = target.docker("cp", target.container + ":/course-dsh-home/" + name,
                                       str(evidence / name), check=False)
                if copied.returncode and "Could not find the file" not in copied.stderr:
                    copied.check_returncode()
    return result | {"sdk_model_http_requests": requests, "wall_seconds": time.monotonic() - started}
