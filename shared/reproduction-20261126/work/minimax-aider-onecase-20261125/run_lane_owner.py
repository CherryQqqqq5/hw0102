import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


def read(path):
    return json.loads(path.read_text())


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def image_reference(task):
    return "nju-course-aider:" + task["stratum"] if task["benchmark"] == "aider" else task["image"]


def ensure_image(task, expected_pin, environment, prepare_missing=None):
    reference = image_reference(task)
    command = [environment["COURSE_DOCKER_BIN"], "image", "inspect", "--format", "{{.Id}}", reference]
    actual = subprocess.run(command, capture_output=True, text=True, env=environment)
    if actual.returncode:
        if "No such image" not in actual.stderr:
            actual.check_returncode()
        if task["benchmark"] == "aider":
            raise RuntimeError("The pinned shared Aider image is absent; use its existing reproducible builder before continuing")
        if prepare_missing is None:
            raise RuntimeError("The original image is absent; this read-only preflight never prepares images")
        prepare_missing(task, environment)
        actual = subprocess.run(command, capture_output=True, text=True, env=environment, check=True)
    if actual.stdout.strip() != expected_pin:
        raise ValueError("The cached task image differs from the original frozen pin")
    return reference


def verified_primary_state(root, priority):
    for path_key, hash_key in (("config", "config_sha256"), ("review", "review_sha256"), ("producer", "producer_sha256")):
        path = root / priority[path_key]
        if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()) or sha(path) != priority[hash_key]:
            raise ValueError("The primary continuation provenance changed")
    config, review = read(root / priority["config"]), read(root / priority["review"])
    if (review["status"] != "APPROVE" or review["blocking_findings"]
            or review["config_sha256"] != priority["config_sha256"]
            or config["source_sha256"][priority["producer"]] != priority["producer_sha256"]):
        raise ValueError("The actual primary continuation lacks its exact source admission")
    path = root / priority["state"]
    if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
        raise ValueError("The primary continuation state leaves the project")
    raw = path.read_bytes()
    state = json.loads(raw)
    if state.get("config_sha256") != priority["config_sha256"]:
        raise ValueError("The state is not from the approved primary continuation")
    return {"ready": state.get(priority["ready_field"]) == priority["ready_value"],
        "status": state.get("status"), "state_sha256": hashlib.sha256(raw).hexdigest(),
        "config_sha256": priority["config_sha256"]}


@contextmanager
def provider_task_lease(root, declaration, blocked):
    path = root / declaration["lock"]
    expected = root / "work/parallel-free-evaluation-20261124/resources/nvidia-provider-task.lock"
    if declaration["capacity"] != 1 or path != expected or path.is_symlink():
        raise ValueError("Only the single canonical NVIDIA auxiliary task slot is permitted")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as lock:
        while True:
            if blocked():
                raise RuntimeError("A new financial stop blocks NVIDIA provider-slot admission")
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                time.sleep(1)
        if blocked():
            raise RuntimeError("A financial event arrived before the leased task dispatch")
        yield


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("lane")
    parser.add_argument("--single-task")
    parser.add_argument("--image-preflight", type=Path)
    args = parser.parse_args()
    root, folder = Path.cwd(), Path(__file__).parent.resolve()
    if args.image_preflight:
        plan = read(args.image_preflight)
        review = read(args.image_preflight.parent / "execution-review.json")
        if review["status"] != "APPROVE" or review["blocking_findings"] or review["plan_sha256"] != sha(args.image_preflight):
            raise ValueError("The cached-image diagnostic requires an existing admitted source plan")
        task = next(task for task in read(root / plan["manifest"])["selected"] if task["id"] == args.single_task)
        environment = os.environ | {"DOCKER_HOST": "unix://" + str(root / "work/v/c/sock/docker.sock"),
            "DOCKER_CONFIG": str(root / "work/docker-config"), "COURSE_DOCKER_BIN": str(root / "work/vendor/docker/docker")}
        reference = ensure_image(task, plan["pins"][task["id"]], environment)
        print(json.dumps({"status": "actual_cached_original_pin_verified", "task": task["id"],
            "image_reference": reference, "pin": plan["pins"][task["id"]], "new_model_calls": 0,
            "new_containers_started": 0, "image_preparation_calls": 0}))
        return
    plan_path = folder / "plan.json"
    plan, review = read(plan_path), read(folder / "execution-review.json")
    if review["status"] != "APPROVE" or review["plan_sha256"] != sha(plan_path) or review["blocking_findings"]:
        raise RuntimeError("The exact parallel plan requires independent source admission")
    lane = plan["lanes"][args.lane]
    runtime = root / plan["runtime_root"]
    sys.path.insert(0, str(root))
    sys.path.insert(0, str(runtime))
    from course_eval.financial_stop import free_query_blocked, preserve_free_stop
    from course_eval.agent import RunLimits
    from course_eval.summarize import run_metrics
    from course_eval.openrouter_free import verify_free_receipt
    from course_eval.nvidia_free import admit_nvidia_channel, audit_nvidia_events
    from scripts.summarize_performance_comparison import control_artifact_metrics
    from external_runtimes import verify_runtime

    admission = root / plan["admission"]
    stop = root / "work/performance-stop-20261122.json"
    environment = os.environ | {"PYTHONPATH": str(runtime) + os.pathsep + str(root), "COURSE_MODEL_BACKEND": lane["backend"],
        "COURSE_MODEL_ID": lane["model"], "COURSE_FREE_STOP_PATH": str(stop),
        "COURSE_PARALLEL_FREE_ADMISSION": str(admission), "COURSE_PARALLEL_FREE_ADMISSION_SHA256": sha(admission),
        "COURSE_FREE_MODEL_METADATA": str(folder / "openrouter-metadata/openrouter-metadata.json"),
        "COURSE_FREE_REQUEST_HISTORY": str(root / "work/vmshare"),
        "COURSE_FREE_GENERATION_SEED": str(root / plan["generation_seed"]),
        "COURSE_FREE_GENERATION_SEED_SHA256": sha(root / plan["generation_seed"]),
        "COURSE_FREE_GENERATION_REGISTRY": str(root / plan["generation_registry"]),
        "DOCKER_HOST": "unix://" + str(root / "work/v/c/sock/docker.sock"),
        "DOCKER_CONFIG": str(root / "work/docker-config"), "COURSE_DOCKER_BIN": str(root / "work/vendor/docker/docker"),
        "PATH": str(root / "work/vendor/docker") + os.pathsep + os.environ["PATH"],
        "TMPDIR": str(root / "work/process-tmp"), "LIMA_HOME": str(root / ".v"),
        "COURSE_PINNED_IMAGE_COPY_DRIVER": str(root / plan["image_copy_driver"]),
        "COURSE_AGENT_FRAMEWORK": lane["framework"], "COURSE_CODEBUDDY_PERSIST_SESSION": "0",
        "COURSE_DSH_RUNTIME": str(root / "work/vmshare/dsh-linux-runtime"),
        "COURSE_DSH_RUNTIME_ARM64": str(root / "work/vmshare/dsh-linux-arm64"),
        "COURSE_TERMINAL_DEPS": str(root / "work/terminal-runtime/deps"),
        "COURSE_TERMINAL_PYTHON": str(root / "work/terminal-runtime/python-3.13.12-linux-x86_64.tar.gz"),
        "COURSE_TERMINAL_PYTHON_312": str(root / "work/terminal-runtime/python-3.12.13-linux-x86_64.tar.gz"),
        "COURSE_AIDER_PUBLIC_PYTHON": str(root / "work/terminal-runtime/python-3.13.12-linux-aarch64.tar.gz"),
        "COURSE_PUBLIC_DEPS_ROOT": str(root / "work/vmshare/confirmation-public-deps"),
        "COURSE_HARBOR_BIN": str(root / "work/.venv/bin/harbor"),
        "COURSE_HARBOR_CAPTURE_POLICY": str(root / plan["artifact_capture_policy"]),
        "COURSE_ELF_PUBLIC_WHEEL": str(root / "work/vmshare/elf-public-check-deps/pyelftools-0.33-py3-none-any.whl"),
        "COURSE_RUN_LIMITS": RunLimits(**plan["limits"]).model_dump_json(),
        "MSWEA_GLOBAL_CONFIG_DIR": str(root / "work/miniswe-config"), "MSWEA_SILENT_STARTUP": "1"}
    if lane["backend"] == "nvidia-free":
        admit_nvidia_channel(root / lane["contract"], root / lane["qualification"], 64000)
        environment.update(COURSE_NVIDIA_FREE_CONTRACT=str(root / lane["contract"]),
            COURSE_NVIDIA_FREE_QUALIFICATION=str(root / lane["qualification"]))
    environment.pop("COURSE_NVIDIA_HTTP_RECOVERY_POLICY", None)
    environment.pop("COURSE_DSH_PROCESS_CONTROL", None)
    environment.pop("COURSE_DSH_POST_REVIEW", None)
    os.environ.update({key: environment[key] for key in (
        "COURSE_PARALLEL_FREE_ADMISSION", "COURSE_PARALLEL_FREE_ADMISSION_SHA256")})
    task_map = {task["id"]: task for task in read(root / plan["manifest"])["selected"]}
    queue = root / plan["queue"] / args.lane
    queue.mkdir(parents=True, exist_ok=True)
    state_path = queue / "state.json"
    prior_state = read(state_path) if state_path.exists() else None
    if prior_state and prior_state["plan_sha256"] != sha(plan_path):
        raise ValueError("The prior actual positions belong to another prospective plan")
    records = prior_state["rows"] if prior_state else []
    for task_id in lane["tasks"]:
        if args.single_task and task_id != args.single_task:
            continue
        for name, expected in plan["all_files_sha256"].items():
            if sha(root / name) != expected:
                raise ValueError("A prospective source changed: " + name)
        if free_query_blocked(stop, lane["model"]):
            raise RuntimeError("An actual unresolved financial stop blocks all new calls")
        priority = plan["primary_priority"]
        primary = verified_primary_state(root, priority)
        while datetime.now(timezone.utc) >= datetime.fromisoformat(priority["drain_new_tasks_at"]):
            primary = verified_primary_state(root, priority)
            if primary["ready"]:
                break
            if free_query_blocked(stop, lane["model"]):
                raise RuntimeError("A new financial event supersedes the auxiliary priority wait")
            state_path.write_text(json.dumps({"lane": args.lane, "plan_sha256": sha(plan_path),
                "status": "waiting_for_primary_core_priority", "completed": len(records),
                "required": len(lane["tasks"]), "rows": records, "primary_state_attestation": primary}, indent=2) + "\n")
            time.sleep(30)
        task = task_map[task_id]
        if lane["framework"] == "dsh":
            verify_runtime(root, read(root / plan["external_runtime_manifest"]))
        configuration = lane["configuration"]
        directory = queue / (task_id.replace("/", "-") + "-" + configuration + "-r" + str(lane["repetition"]))
        if directory.exists():
            recorded = [row for row in records if row["task"] == task_id]
            if (len(recorded) == 1 and (directory / "result.json").exists()
                    and read(directory / "result.json") == recorded[0]["original_result"]
                    and recorded[0]["original_result"]["scoreable"] is True
                    and type(recorded[0]["original_result"]["passed"]) is bool):
                if task_id == plan["first_control_qualification_task"] and lane["framework"] == "mini-swe" and recorded[0]["qualified_passed"] is not True:
                    raise RuntimeError("The first native-control task remains unqualified across restarts; no expansion is allowed")
                continue
            raise FileExistsError("Retain the actual prior attempt; never silently rerun or skip an unscored fixed position")
        sys.path.insert(0, str(root / "work/parallel-free-evaluation-20261124"))
        from ready_coordinator import prepare_missing_image
        reference = ensure_image(task, plan["pins"][task_id], environment, prepare_missing_image)
        protocol = {"task": task_id, "backend": lane["backend"], "model": lane["model"], "configuration": configuration,
            "framework": lane["framework"], "runtime_root": plan["runtime_root"], "limits": plan["limits"],
            "plan_sha256": sha(plan_path), "historical_unknown_calls_preserved": plan["historical_unknown_calls"],
            "quota_only_hy4_pause_preserved": False, "native_cli_persistence": False,
            "billing": "Every actual response must independently pass its provider's existing approved zero-cost proof; no fallback or request retry"}
        directory.with_suffix(".protocol.json").write_text(json.dumps(protocol, indent=2) + "\n")
        command = [sys.executable, str(root / plan["resource_driver"]), "--task", task_id, "--benchmark", task["benchmark"],
            "--image", reference, "--expected-image-id", plan["pins"][task_id],
            "--record", str(directory.with_suffix(".resources.json")), "--", sys.executable, str(folder / "benchmarks_entry.py"),
            "--manifest", str(root / plan["manifest"]), "--sources", str(root / "work/datasets"), "--id", task_id,
            "--configuration", configuration, "--run-dir", str(directory), "--checks", str(root / plan["checks"])]
        environment["COURSE_PRIOR_FREE_GENERATION_IDS"] = json.dumps(sorted(set(plan["historical_generation_ids"]) | {
            identity for row in records for identity in row["billing"].get("generation_ids", [])}))
        with provider_task_lease(root, plan["provider_task_lease"], lambda: free_query_blocked(stop, lane["model"])):
            if any(sha(root / name) != expected for name, expected in plan["all_files_sha256"].items()):
                raise ValueError("A frozen dependency changed while waiting for the provider task slot")
            primary = verified_primary_state(root, priority)
            if datetime.now(timezone.utc) >= datetime.fromisoformat(priority["drain_new_tasks_at"]) and not primary["ready"]:
                raise RuntimeError("The primary priority deadline arrived during provider-slot waiting; no new model task was dispatched")
            with directory.with_suffix(".log").open("x") as log:
                returncode = subprocess.run(command, cwd=root, env=environment, stdout=log, stderr=subprocess.STDOUT).returncode
        traces = list(directory.rglob("model.jsonl"))
        if len(traces) != 1:
            raise RuntimeError("The actual single-agent trial must have exactly one model trace")
        events = [json.loads(line) for line in traces[0].read_text().splitlines()]
        requests = {row["request_id"] for row in events if row["event"] == "request"}
        receipts = {row["request_id"] for row in events if row["event"] == "billing_verified"}
        if requests - receipts:
            preserve_free_stop(stop, run_dir=str(traces[0].parent), unverified_requests=sorted(requests - receipts),
                reason="A new parallel free-provider call lacks its own complete verified receipt")
            raise RuntimeError("A parallel request lacks a verified receipt; all new calls are stopped")
        if lane["backend"] == "nvidia-free":
            billing = audit_nvidia_events(events, root / lane["contract"], lane["model"], 64000)
            billing["generation_ids"] = [row["generation_id"] for row in events if row["event"] == "billing_verified"]
        else:
            responses = {row["request_id"]: row["payload"] for row in events if row["event"] == "response"}
            ids = set()
            for key in receipts:
                receipt = verify_free_receipt(responses[key], lane["model"], 64000)
                if receipt.id in ids:
                    raise ValueError("An OpenRouter actual generation was reused")
                ids.add(receipt.id)
            billing = {"actual_requests": len(requests), "own_zero_receipts": len(receipts), "generation_ids": sorted(ids)}
        result = read(directory / "result.json")
        control = control_artifact_metrics(directory, lane["framework"], configuration)
        qualified = result["passed"] is True and (not control["final_control_applicable"] or
            control["final_protected_unchanged"] is True and control["final_valid_verification"] is True)
        records.append({"task": task_id, "run_dir": str(directory.relative_to(root)), "original_result": result,
            "qualified_passed": qualified, "control": control, "billing": billing, "usage": run_metrics(directory)})
        state_path.write_text(json.dumps({"lane": args.lane, "plan_sha256": sha(plan_path), "completed": len(records), "required": len(lane["tasks"]),
            "rows": records, "not_mixed_into_hy4_core": True}, indent=2) + "\n")
        print(json.dumps({"lane": args.lane, "task": task_id, "result": result,
            "requests": len(requests), "verified_receipts": len(receipts)}), flush=True)
        if returncode or result["scoreable"] is not True:
            raise RuntimeError("The actual trial ended without original scoring; retain and diagnose before dispatch")
        if task_id == plan["first_control_qualification_task"] and lane["framework"] == "mini-swe" and not qualified:
            raise RuntimeError("The first real native-control task did not close its verification contract; retain the original score and diagnose before expansion")


if __name__ == "__main__":
    main()
