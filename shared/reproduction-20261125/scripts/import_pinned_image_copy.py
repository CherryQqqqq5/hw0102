import argparse
import hashlib
import json
import os
import shutil
import signal
import subprocess
import time
from pathlib import Path

from scripts.prepare_registry_export_tool import registry_tool_environment


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cancel-prefetch-pid", type=int)
    parser.add_argument("--task", default="django__django-11999")
    parser.add_argument("--attempt", type=int, default=0)
    args = parser.parse_args()
    if args.attempt < 0:
        raise ValueError("The preparation attempt must be nonnegative")
    root = Path.cwd()
    stem = "django11999" if args.task == "django__django-11999" else args.task.replace("/", "-")
    if args.attempt:
        stem += "-preparation-r" + str(args.attempt)
    prepared_path = root / ("work/registry-tools/copy-" + stem + ".json")
    prepared = json.loads(prepared_path.read_text())
    if prepared["status"] != "ready_for_import" or prepared["task"] != args.task:
        raise ValueError("The original image has not completed independent content verification")
    output = root / ("work/registry-tools/import-" + stem + ".json")
    if output.exists():
        raise FileExistsError(output)
    tasks = json.loads((root / "work/vmshare/performance75-dsh-hy4-v10/tasks.json").read_text())["selected"]
    task, = [row for row in tasks if row["id"] == prepared["task"]]
    docker = root / "work/vendor/docker/docker"
    registry = root / "work/vendor/bin/regctl"
    if hashlib.sha256(registry.read_bytes()).hexdigest() != prepared["tool_sha256"]:
        raise ValueError("The verified registry tool changed")
    environment = os.environ | {"DOCKER_HOST": "unix://" + str(root / "work/v/c/sock/docker.sock"),
                                "DOCKER_CONFIG": str(root / "work/docker-config")}
    record = {"status": "importing", "prepared_record_sha256": hashlib.sha256(prepared_path.read_bytes()).hexdigest(),
        "expected_image_id": prepared["expected_image_id"], "tag": task["image"], "new_model_calls": 0,
        "docker_daemon_or_proxy_reconfigured": False}
    export = load = None
    started = time.monotonic()
    try:
        if args.cancel_prefetch_pid:
            command = subprocess.run(["ps", "-p", str(args.cancel_prefetch_pid), "-o", "command="],
                                     text=True, capture_output=True, check=False)
            if command.returncode == 0:
                expected = str(docker) + " pull --platform linux/amd64 " + task["image"]
                if command.stdout.strip() != expected:
                    raise ValueError("The requested cancellation PID is not the known image preparation child")
                os.kill(args.cancel_prefetch_pid, signal.SIGTERM)
                record.update(cancelled_prefetch_pid=args.cancel_prefetch_pid,
                    cancellation_reason="Replace the slow incomplete download with an independently verified exact image")
            else:
                record["prefetch_child_already_exited"] = True
        output.write_text(json.dumps(record, indent=2) + "\n")
        with (root / ("work/registry-tools/export-" + stem + ".log")).open("x") as export_log, \
                (root / ("work/registry-tools/load-" + stem + ".log")).open("x") as load_log:
            export = subprocess.Popen([str(registry), "image", "export", prepared["destination"], "--name", task["image"]],
                cwd=root, env=registry_tool_environment(root), stdout=subprocess.PIPE, stderr=export_log)
            load = subprocess.Popen([str(docker), "image", "load"], env=environment,
                stdin=export.stdout, stdout=load_log, stderr=subprocess.STDOUT)
            export.stdout.close()
            load.wait(timeout=900)
            export.wait(timeout=30)
        if load.returncode or export.returncode:
            raise RuntimeError(f"The real image pipeline failed: export={export.returncode}, load={load.returncode}")
        inspected = subprocess.check_output([str(docker), "image", "inspect", "--format", "{{.Id}}", task["image"]],
                                           env=environment, text=True, timeout=30).strip()
        record["actual_image_id"] = inspected
        if inspected != prepared["expected_image_id"]:
            raise ValueError("The imported image identity differs from the frozen original; do not run models on it")
        cache = root / "work/registry-tools" / stem
        shutil.rmtree(cache)
        record.update(status="imported", pinned_identity_verified=True,
                      temporary_oci_cache_removed=True, original_evaluation_inputs_changed=False)
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        record.update(status="failed", error_type=type(exc).__name__, detail=str(exc))
        raise
    finally:
        for process in (load, export):
            if process is not None and process.poll() is None:
                process.kill()
                process.wait(timeout=10)
        record["wall_seconds"] = time.monotonic() - started
        output.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n")
        print(json.dumps(record, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
