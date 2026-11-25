import argparse
import hashlib
import json
import os
import runpy
import subprocess
import sys
import time
import uuid
from pathlib import Path

import course_eval.resource_pool as pool_module


parser = argparse.ArgumentParser(add_help=False)
parser.add_argument("--task", required=True)
parser.add_argument("--benchmark", required=True)
parser.add_argument("--image", required=True)
parser.add_argument("--expected-image-id", required=True)
parser.add_argument("--record", type=Path, required=True)
parser.add_argument("--qualify-only", action="store_true")
args, _ = parser.parse_known_args()
root = Path.cwd()
folder = root / "work/parallel-free-evaluation-20261124"
original_lease = pool_module.ResourceLease
docker = os.environ["COURSE_DOCKER_BIN"]


def call(*command, timeout=600):
    return subprocess.run([docker, *command], capture_output=True, text=True, timeout=timeout, check=True)


def prepare_actual_image():
    if args.benchmark != "swe":
        return
    inspected = subprocess.run([docker, "image", "inspect", "--format", "{{.Id}}", args.image],
        capture_output=True, text=True, timeout=30)
    if inspected.returncode:
        if "No such image" in inspected.stderr:
            return
        inspected.check_returncode()
    if inspected.stdout.strip() != args.expected_image_id:
        raise ValueError("The preparation image differs from the actual original pin")
    name = "course-image-ready-" + uuid.uuid4().hex
    path = args.record.with_suffix(".warmup.json")
    record = {"task": args.task, "image": args.image, "pin": args.expected_image_id, "container": name,
        "stage": "preparing_original_image_before_model_clock", "new_model_calls": 0, "new_original_scores": 0,
        "model_runtime_and90_second_constructor_unchanged": True, "maximum_preparation_seconds": 600,
        "purpose": "Finish rootless image snapshot preparation with an isolated disposable sleep0 container before the unchanged model task starts"}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=2) + "\n")
    started = time.monotonic()
    try:
        result = call("run", "--name", name, "--pull=never", "--platform", "linux/amd64", "--network", "none",
            "--cpus", "2", "--memory", "3072m", "--pids-limit", "512", "--security-opt", "no-new-privileges",
            "--tmpfs", "/opt/miniconda3/pkgs:ro,noexec,nosuid,size=1m",
            "--tmpfs", "/root/.cache/pip:ro,noexec,nosuid,size=1m", "--entrypoint", "/bin/sleep", "-w", "/testbed",
            args.expected_image_id, "0")
        record.update(stage="original_pin_preparation_passed", returncode=result.returncode,
            stdout=result.stdout, stderr=result.stderr, preparation_seconds=time.monotonic()-started)
    except (OSError, subprocess.SubprocessError) as error:
        record.update(stage="preparation_failed_before_model", error_type=type(error).__name__, error=str(error),
            preparation_seconds=time.monotonic()-started)
        raise
    finally:
        cleaned = subprocess.run([docker, "rm", "-f", name], capture_output=True, text=True, timeout=90)
        record["cleanup_returncode"] = cleaned.returncode
        record["cleanup_stdout"] = cleaned.stdout
        record["cleanup_stderr"] = cleaned.stderr
        path.write_text(json.dumps(record, indent=2) + "\n")
        if cleaned.returncode and "No such container" not in cleaned.stderr:
            cleaned.check_returncode()
    print(json.dumps({"task": args.task, "preparation": record["stage"],
        "preparation_seconds": record["preparation_seconds"], "new_model_calls": 0}), flush=True)


class PreparedLease(original_lease):
    def __enter__(self):
        super().__enter__()
        try:
            if self.label == args.task:
                prepare_actual_image()
        except BaseException:
            super().__exit__(*sys.exc_info())
            raise
        return self


if args.qualify_only:
    from course_eval.docker_target import DockerTarget

    if args.benchmark != "swe":
        raise ValueError("This real image qualification covers the actual SWE startup failure")
    with original_lease(folder / "resources", exclusive=True, label="qualify-image-readiness-" + args.task):
        prepare_actual_image()
        started = time.monotonic()
        with DockerTarget(args.image, "/testbed", platform="linux/amd64", memory_mb=3072, cpus=2,
                read_only_empty_dirs=("/opt/miniconda3/pkgs", "/root/.cache/pip")) as target:
            constructor_seconds = time.monotonic()-started
            if target.image != args.expected_image_id:
                raise ValueError("The actual frozen constructor used a different original image")
            source = Path(sys.modules[DockerTarget.__module__].__file__)
            record = {"status": "actual_preparation_and_unchanged_frozen_constructor_passed", "task": args.task,
                "pin": target.image, "frozen_constructor_seconds": constructor_seconds,
                "docker_target_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                "actual_system": target.system_info, "new_model_calls": 0, "new_original_scores": 0}
        args.record.write_text(json.dumps(record, indent=2) + "\n")
        print(json.dumps(record), flush=True)
else:
    pool_module.ResourceLease = PreparedLease
    runpy.run_path(str(folder / "resource_trial.py"), run_name="__main__")
