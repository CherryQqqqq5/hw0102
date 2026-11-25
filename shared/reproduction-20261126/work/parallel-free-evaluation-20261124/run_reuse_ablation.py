import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from scripts.export_performance_evidence import inspect_run
from scripts.summarize_performance_comparison import control_artifact_metrics
from ready_coordinator import prepare_missing_image


def read(path):
    return json.loads(path.read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, default=Path("work/parallel-free-evaluation-20261124/final-reuse-ablation/plan.json"))
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--wait-core", action="store_true")
    args = parser.parse_args()
    root, plan = Path.cwd(), read(args.plan)
    for name, checksum in plan["all_files_sha256"].items():
        if digest(root / name) != checksum:
            raise ValueError("The prespecified ablation source changed: " + name)
    tasks = read(root / plan["manifest"])["selected"]
    if [row["id"] for row in tasks] != plan["task_ids"] or len(tasks) != 3:
        raise ValueError("The three helper-family tasks were added, removed or reordered")
    for task in tasks:
        reference = plan["main_references"][task["id"]]
        if digest(root / reference["result"]) != reference["result_sha256"]:
            raise ValueError("An existing reference score changed")
        if read(root / reference["trial"])["task"] != task:
            raise ValueError("An ablation task differs from its actual full-guidance reference")
    if args.validate_only:
        print(json.dumps({"status": "validated", "tasks": 3, "changed_behavior_functions": 1,
            "helper_algorithms_checks_inputs_budgets_unchanged": True, "new_model_calls": 0}), flush=True)
        return
    queues = {name: root / value for name, value in plan["core_queues"].items()}
    while True:
        if read(root / "work/performance-stop-20261122.json")["active"]:
            raise RuntimeError("The actual financial stop prevents the next experiment stage")
        states = {name: read(queue / "state.json") for name, queue in queues.items()}
        ready = (states["main"]["status"] == "complete" and states["main"]["baseline_completed"] == 75
            and states["main"]["policy_completed"] == 75 and states["repeat"]["status"] == "complete"
            and states["repeat"]["policy_completed"] == 75)
        if ready:
            break
        if not args.wait_core:
            raise RuntimeError("Complete the original225 positions before starting this declared supplementary ablation")
        time.sleep(10)
    for name, checksum in plan["all_files_sha256"].items():
        if digest(root / name) != checksum:
            raise ValueError("A frozen ablation dependency changed while the core was running")
    queue = root / plan["queue"]
    queue.mkdir(exist_ok=True)
    environment = os.environ | {"PYTHONPATH": str(root), "DOCKER_HOST": "unix://" + str(root / "work/v/c/sock/docker.sock"),
        "DOCKER_CONFIG": str(root / "work/docker-config"), "LIMA_HOME": str(root / ".v"),
        "COURSE_DOCKER_BIN": str(root / "work/vendor/docker/docker"), "COURSE_CODEBUDDY_IMAGES": "1",
        "COURSE_CODEBUDDY_IMAGE_METADATA": str(root / "work/free-channel-capabilities-20261122/cloud-model-metadata.json"),
        "COURSE_ELF_PUBLIC_WHEEL": str(root / "work/vmshare/elf-public-check-deps/pyelftools-0.33-py3-none-any.whl"),
        "COURSE_CODEBUDDY_GUARDED_BIN": str(root / "work/hy4-free-readiness-20261124/codebuddy-guard.sh"),
        "COURSE_FREE_STOP_PATH": str(root / "work/performance-stop-20261122.json"),
        "COURSE_HARBOR_CAPTURE_POLICY": str(root / plan["artifact_capture_policy"]),
        "COURSE_PINNED_IMAGE_COPY_DRIVER": str(root / plan["image_copy_driver"])}
    rows = []
    for task in tasks:
        for name, checksum in plan["all_files_sha256"].items():
            if digest(root / name) != checksum:
                raise ValueError("An ablation dependency changed before the next position: " + name)
        if read(root / "work/performance-stop-20261122.json")["active"]:
            raise RuntimeError("An actual new financial stop prevents the next task")
        directory = queue / (task["id"] + "-C0-reuse-guidance-off-r1")
        if not (directory / "result.json").exists():
            if directory.exists():
                raise RuntimeError("An unfinished real ablation requires diagnosis instead of resampling")
            prepare_missing_image(task, environment)
            command = [sys.executable, str(root / plan["resource_driver"]), "--task", task["id"],
                "--benchmark", task["benchmark"], "--image", task["image"], "--expected-image-id", plan["pins"][task["id"]],
                "--record", str(directory.with_suffix(".resources.json")), "--", sys.executable, str(root / plan["driver"]),
                "--task", task["id"], "--manifest", str(root / plan["manifest"]), "--configuration", "C0",
                "--persistent-session", "--framework", "mini-swe", "--runtime-root", str(root / plan["runtime_root"]),
                "--run-dir", str(directory), "--checks", str(root / plan["checks"])]
            with directory.with_suffix(".dispatch.log").open("x") as log:
                subprocess.run(command, env=environment, stdout=log, stderr=subprocess.STDOUT, check=True)
        result = inspect_run(directory, "mini-swe")
        protocol = read(directory.with_suffix(".protocol.json"))
        if (protocol["limits"] != plan["limits"] or protocol["configuration"] != "C0"
                or protocol["model"] != "hy4flash-free" or not protocol["persistent_native_session"]
                or (root / protocol["runtime_root"]).resolve() != (root / plan["runtime_root"]).resolve()
                or read(directory / "trial.json")["task"] != task):
            raise ValueError("The actual ablation differs from its frozen input, model or budget")
        rows.append({"task": task["id"], "run_dir": str(directory.relative_to(root)),
            "original_score_sha256": digest(directory / "result.json"), **result,
            **control_artifact_metrics(directory, "mini-swe", "C0")})
        state = {"plan_sha256": digest(args.plan), "required": 3, "completed": len(rows),
            "passed": sum(row["passed"] for row in rows), "rows": rows,
            "stage": "complete" if len(rows) == 3 else "running", "all_actual_failures_retained": True}
        (queue / "state.json").write_text(json.dumps(state, indent=2) + "\n")
        print(json.dumps({"task": task["id"], "original_passed": result["passed"], "actual_requests": result["actual_requests"]}), flush=True)


if __name__ == "__main__":
    main()
