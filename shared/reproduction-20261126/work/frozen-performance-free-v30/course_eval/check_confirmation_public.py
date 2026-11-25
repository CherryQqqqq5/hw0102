import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path

from course_eval.benchmarks import SWE_HIDDEN_CACHES, check_swe_checkout, swe_public_dependencies
from course_eval.confirmation_materials import swe_check
from course_eval.docker_target import DockerTarget


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--sources", type=Path, default=Path("work/datasets"))
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--task", action="append")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    rows = {row["instance_id"]: row for row in json.loads((args.sources / "swe-grader.json").read_text())}
    for task in json.loads(args.manifest.read_text())["selected"]:
        if task["benchmark"] != "swe" or (args.task and task["id"] not in args.task):
            continue
        folder = args.out / task["id"]
        if folder.exists():
            continue
        available = subprocess.run([os.environ["COURSE_DOCKER_BIN"], "image", "inspect", task["image"]],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
        if available.returncode:
            print("WAIT_IMAGE " + task["id"], flush=True)
            continue
        folder.mkdir()
        row = rows[task["id"]]
        check = swe_check(task, row["problem_statement"])
        reference = folder / "reference.patch"
        reference.write_text(row["patch"])
        with DockerTarget(task["image"], "/testbed", platform="linux/amd64", memory_mb=3072, cpus=2,
                          read_only_empty_dirs=SWE_HIDDEN_CACHES, **swe_public_dependencies(task)) as target:
            check_swe_checkout(task, target, folder)
            before = target.exec(check.command, timeout=60)
            target.docker("cp", str(reference.resolve()), target.container + ":/public-control-reference.patch")
            patch = target.exec("git apply /public-control-reference.patch", timeout=20)
            if patch["returncode"]:
                raise RuntimeError(patch)
            after = target.exec(check.command, timeout=60)
        result = {"task": task["id"], "original": before, "reference": after, "model_requests": 0,
                  "check_command_sha256": hashlib.sha256(check.command.encode()).hexdigest(),
                  "formal_benchmark_trial": False, "source": "public task reproducer; upstream patch control"}
        (folder / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        print(task["id"], before["returncode"], after["returncode"], flush=True)


if __name__ == "__main__":
    main()
