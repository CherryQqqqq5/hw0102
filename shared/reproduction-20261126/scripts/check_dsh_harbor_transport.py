import argparse
import asyncio
import hashlib
import inspect
import json
import os
import time
from pathlib import Path

os.environ.setdefault("MSWEA_GLOBAL_CONFIG_DIR", str(Path.cwd() / "work/miniswe-config"))
os.environ.setdefault("MSWEA_SILENT_STARTUP", "1")

from harbor.environments.docker.docker import DockerEnvironment
from harbor.models.task.config import EnvironmentConfig
from harbor.models.trial.paths import TrialPaths

from course_eval.dsh_runner import run_sandbox
from course_eval.harbor_agent import make_harbor_target


async def check(args):
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    definition = out / "environment"
    definition.mkdir()
    paths = TrialPaths(trial_dir=out / "harbor")
    paths.mkdir()
    runtime = (Path.cwd() / "work/vmshare/dsh-linux-runtime").resolve(strict=True)
    overlay = out / "runtime-compose.json"
    overlay.write_text(json.dumps({"services": {"main": {"network_mode": "none", "volumes": [
        {"type": "bind", "source": str(runtime), "target": "/opt/course-harness", "read_only": True}]}}}))
    environment = DockerEnvironment(environment_dir=definition, environment_name="course-dsh-transport-fixture",
        session_id="course-dsh-transport-fixture-v9", trial_paths=paths,
        task_env_config=EnvironmentConfig(docker_image=args.image, cpus=1, memory_mb=1536),
        extra_docker_compose=(overlay,))
    requests = []

    def fixture(body, index):
        requests.append(body)
        if index not in (1, 2):
            raise AssertionError("The fixed Harbor protocol fixture exceeded two requests")
        message = {"role": "assistant", "content": "Offline Harbor transport verified." if index == 2 else ""}
        if index == 1:
            message["tool_calls"] = [{"id": "harbor-fixture-bash", "type": "function", "function": {
                "name": "bash", "arguments": json.dumps({"command": "printf actual-harbor-transport > /course-harbor-proof.txt"})}}]
        return {"status": 200, "body": {"id": f"offline-harbor-{index}", "object": "chat.completion",
            "created": int(time.time()), "model": args.model, "choices": [{"index": 0, "message": message,
            "finish_reason": "tool_calls" if index == 1 else "stop"}],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}}}

    fixture.model_id = args.model
    fixture.reasoning_effort = args.reasoning_effort
    await environment.start(force_build=False)
    try:
        target = await make_harbor_target(environment, native_dsh=True)
        inspected = await asyncio.to_thread(target.docker, "inspect", target.container)
        (out / "environment-inspect.json").write_text(inspected.stdout)
        result = await asyncio.to_thread(run_sandbox, target, out / "dsh", "Execute the offline Harbor fixture.",
                                         fixture, timeout=120)
        proof = await asyncio.to_thread(target.exec, "cat /course-harbor-proof.txt", timeout=5)
        assert proof["returncode"] == 0 and proof["stdout"] == "actual-harbor-transport", proof
        assert len(requests) == 2
        inspected, = json.loads((await asyncio.to_thread(target.docker, "inspect", target.container)).stdout)
        mount, = [entry for entry in inspected["Mounts"] if entry["Destination"] == "/opt/course-harness"]
        assert mount["RW"] is False
        report = {"status": "passed", "scope": "Actual Harbor Docker environment, native SDK and scripted provider",
                  "selected_model": args.model, "reasoning_effort": args.reasoning_effort,
                  "source_sha256": {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in (
                      Path(__file__).resolve(), Path(inspect.getsourcefile(run_sandbox)),
                      Path(inspect.getsourcefile(make_harbor_target)))},
                  "new_model_calls": 0, "original_grader_calls": 0, "synthetic_usage_is_not_billing_evidence": True,
                  "offline_main_container_verified": True, "runtime_mount_read_only": True, "sdk_result": result}
        (out / "result.json").write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report))
    finally:
        await environment.stop(delete=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--model", default="hy4flash-free")
    parser.add_argument("--reasoning-effort", choices=("low", "high"), default="high")
    asyncio.run(check(parser.parse_args()))


if __name__ == "__main__":
    main()
