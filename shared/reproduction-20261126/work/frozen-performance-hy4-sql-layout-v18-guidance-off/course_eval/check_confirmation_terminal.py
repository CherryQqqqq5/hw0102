import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path

from course_eval.agent import RunLimits
from course_eval.controller import Budget, BoundedTarget, ControlledEnvironment
from course_eval.docker_target import DockerTarget
from course_eval.inventory import REVISIONS
from course_eval.terminal_runtime import prepare_public_runtime


def main():
    from course_eval.confirmation_terminal_materials import terminal_check, terminal_scope

    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--sources", type=Path, default=Path("work/datasets"))
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--task", action="append")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    for task in json.loads(args.manifest.read_text())["selected"]:
        if task["benchmark"] != "terminal" or (args.task and task["id"] not in args.task):
            continue
        folder = args.out / task["id"]
        if folder.exists():
            continue
        available = subprocess.run([os.environ["COURSE_DOCKER_BIN"], "image", "inspect", task["image"]],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
        if available.returncode:
            print("WAIT_IMAGE " + task["id"], flush=True)
            continue
        original = args.sources / f"terminal-bench-2-1-{REVISIONS['terminal']}" / "tasks" / task["id"]
        instruction = (original / "instruction.md").read_text()
        check = terminal_check(task, instruction)
        folder.mkdir()
        with DockerTarget(task["image"], None, platform="linux/amd64", memory_mb=2048, cpus=1) as target:
            listing = target.exec("find . -type f -print", timeout=30)
            if listing["returncode"]:
                raise RuntimeError(listing)
            scope = terminal_scope(task, listing["stdout"].splitlines())
            runtime = prepare_public_runtime(target, scope)
            budget = Budget(900)
            environment = ControlledEnvironment(BoundedTarget(target, budget), folder, RunLimits(wall_seconds=900),
                                                 (check,), scope, budget, True)
            before = environment.verify(check.check_id, "original_starter")
            target.docker("cp", str((original / "solution").resolve()), target.container + ":/solution")
            reference = target.exec("bash /solution/solve.sh", timeout=600)
            (folder / "reference-execution.json").write_text(json.dumps(reference, indent=2) + "\n")
            after = environment.verify(check.check_id, "upstream_reference")
            (folder / "reference-artifacts.json").write_text(json.dumps(environment.store.capture(), indent=2) + "\n")
            result = {"task": task["id"], "original": before, "reference": after, "scope": scope,
                      "reference_exit_code": reference["returncode"], "public_runtime": runtime, "model_requests": 0,
                      "check_command_sha256": hashlib.sha256(check.command.encode()).hexdigest(),
                      "formal_benchmark_trial": False, "source": "public task conditions; upstream reference used only as control"}
            if task["id"] == "modernize-scientific-stack" and after["state"] == "passed":
                alternative = folder / "public-pyproject.toml"
                alternative.write_text('[project]\nname="public-climate-check"\nversion="0.0.1"\ndependencies=["numpy>=2", "pandas>=2", "scipy>=1"]\n')
                target.upload_file(alternative.resolve(), "/app/pyproject.toml")
                moved = target.exec("mv /app/requirements.txt /course-reference-requirements.txt", timeout=10)
                if moved["returncode"]:
                    raise RuntimeError(moved)
                optional = environment.verify(check.check_id, "public_pyproject_alternative")
                assert optional["state"] == "passed", optional
                result["permitted_pyproject_alternative"] = optional
            (folder / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
            print(task["id"], before["state"], after["state"], reference["returncode"], flush=True)


if __name__ == "__main__":
    main()
