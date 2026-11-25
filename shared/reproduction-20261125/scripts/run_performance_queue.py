import argparse
import hashlib
import json
import os
import subprocess
import sys
from collections import Counter
from pathlib import Path


def read_json(path):
    return json.loads(path.read_text())


def save_json(path, value):
    temporary = path.with_name(path.name + ".writing")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit_billing(directory, *, allow_context_resets=False):
    events = [json.loads(line) for path in directory.rglob("model.jsonl")
              for line in path.read_text().splitlines()]
    requests = {row["request_id"] for row in events if row["event"] == "request"}
    verified = {row["request_id"] for row in events if row["event"] == "billing_verified"}
    if not requests or requests != verified:
        raise RuntimeError(f"Actual requests do not all have individual receipts: {directory}")
    if any(row["event"] in {"request_error", "billing_error"} for row in events):
        raise RuntimeError(f"Unresolved provider or billing error: {directory}")
    receipts = {row["request_id"]: row for row in events if row["event"] == "billing_verified"}
    if any(row["credit"] != 0 or row["request_model"] != "hy4flash-free"
           or row.get("fresh_usage_records", 0) < 1 for row in receipts.values()):
        raise RuntimeError(f"A fresh zero-credit Hy4 receipt is missing: {directory}")
    sessions = {row["native_session_id"] for row in events if row["event"] == "request"}
    if None in sessions or (not allow_context_resets and len(sessions) != 1):
        raise RuntimeError(f"The task did not use a single persistent native session: {directory}")
    if allow_context_resets:
        first = next(row["native_session_id"] for row in events if row["event"] == "request")
        recorded = {row["native_session_id"] for row in events if row["event"] == "native_context_reset"}
        if sessions - ({first} | recorded):
            raise RuntimeError("A native DSH session changed without a recorded context reset")
    return {"actual_requests": len(requests), "verified_zero_credit_requests": len(verified),
            "fresh_native_usage_records": sum(row["fresh_usage_records"] for row in receipts.values()),
            "native_session_count": len(sessions)}


def completed_result(task, directory, runtime, *, framework="mini-swe"):
    result = read_json(directory / "result.json")
    trial = read_json(directory / "trial.json")
    protocol = read_json(directory.with_suffix(".protocol.json"))
    if (result["task"] != task["id"] or trial["task"] != task
            or trial.get("framework", "mini-swe") != framework
            or protocol["model"] != "hy4flash-free" or protocol["configuration"] != "B0"
            or not protocol["persistent_native_session"]
            or protocol["limits"] != {"model_calls": 500, "wall_seconds": 3600.0,
                "command_seconds": 120, "max_output_tokens": 64000, "timeout_retries": 0,
                "strict_wall": True}
            or (Path.cwd() / protocol["runtime_root"]).resolve() != runtime):
        raise ValueError(f"The saved task or configuration differs: {directory}")
    if not result["scoreable"] or type(result["passed"]) is not bool:
        raise RuntimeError(f"Missing original score; inspect before continuing: {directory}")
    billing = audit_billing(directory, allow_context_resets=framework == "dsh")
    if framework == "dsh" and billing["actual_requests"] != billing["fresh_native_usage_records"]:
        raise RuntimeError("The native DSH single-generation protocol was violated")
    return {"task": task["id"], "benchmark": task["benchmark"], "run_dir": str(directory),
            "passed": result["passed"], "wall_seconds": result["wall_seconds"],
            **billing}


def run_directory(task, queue, protocol, mechanical):
    if task["id"] in mechanical:
        return Path(mechanical[task["id"]]["replacement_run"])
    initial = protocol["initial_validation_runs"].get(task["id"])
    return Path(initial) if initial else queue / (task["id"].replace("/", "-") + "-B0-r1")


def load_completed_results(tasks, queue, runtime, protocol, mechanical):
    results = []
    for task in tasks:
        directory = run_directory(task, queue, protocol, mechanical)
        path = directory / "result.json"
        if path.exists() and read_json(path)["scoreable"]:
            results.append(completed_result(task, directory, runtime, framework=protocol.get("framework", "mini-swe")))
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--queue-dir", type=Path, required=True)
    parser.add_argument("--runtime-root", type=Path, required=True)
    parser.add_argument("--framework", choices=("mini-swe", "dsh"), default="mini-swe")
    parser.add_argument("--initial-validation-runs", type=Path)
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--recover-task", help="One replacement after an environment-start timeout with zero model calls")
    parser.add_argument("--cached-only", action="store_true", help="Defer uncached environments while retaining all 75 required tasks")
    parser.add_argument("--prefetch-only", action="store_true", help="Prepare missing images serially without model calls")
    args = parser.parse_args()
    root = Path.cwd()
    runtime = args.runtime_root.resolve(strict=True)
    queue = args.queue_dir.resolve()
    queue.mkdir(parents=True, exist_ok=True)
    sources = [root / "work/hw0102-publish/shared/frozen-tasks.json",
               root / "work/confirmation-frozen-v1.json"]
    documents = [read_json(path) for path in sources]
    if any(doc["stage"] != "frozen" or doc["revisions"] != documents[0]["revisions"]
           for doc in documents):
        raise ValueError("The original frozen inputs have incompatible benchmark revisions")
    selected = [row for doc in documents for row in doc["selected"]]
    if len({(row["benchmark"], row["id"]) for row in selected}) != 75:
        raise ValueError("The original inputs do not form the required 75 distinct tasks")
    if Counter(row["benchmark"] for row in selected) != {"aider": 25, "swe": 25, "terminal": 25}:
        raise ValueError("Each benchmark must contribute exactly 25 tasks")
    priorities = ["extract-elf", "video-processing", "llm-inference-batching-scheduler", "query-optimize"]
    ordered = [next(row for row in selected if row["id"] == task) for task in priorities]
    buckets = {name: sorted([row for row in selected if row["benchmark"] == name
                            and row["id"] not in priorities], key=lambda row: row["id"])
               for name in ("aider", "terminal", "swe")}
    for index in range(max(map(len, buckets.values()))):
        ordered.extend(rows[index] for rows in buckets.values() if index < len(rows))
    manifest = {"stage": "frozen", "revisions": documents[0]["revisions"],
                "selected": ordered, "inventory": ordered,
                "source_manifests": [{"path": str(path.relative_to(root)), "sha256": digest(path)}
                                     for path in sources],
                "scope": "D30 + C30 + H15; all previously exposed; original scorers unchanged"}
    manifest_path = queue / "tasks.json"
    pins_path = queue / "environment-pins.json"
    environment_pins = read_json(pins_path)["pins"] if pins_path.exists() else {}
    if environment_pins:
        if set(environment_pins) != {row["id"] for row in ordered}:
            raise ValueError("Environment identities must cover exactly the complete 75-task union")
        lock_path = queue / "environment-pins-lock.json"
        lock = {"environment_pins_sha256": digest(pins_path), "source_task_inputs_changed": False}
        if lock_path.exists() and read_json(lock_path) != lock:
            raise RuntimeError("The environment identity supplement changed")
        if not lock_path.exists():
            save_json(lock_path, lock)
    implementation = {str(path.relative_to(runtime)): digest(path)
                      for path in sorted((runtime / "course_eval").rglob("*.py"))}
    protocol = {"phase": "RUN", "configuration": "B0", "backend": "codebuddy",
                "model": "hy4flash-free", "persistent_native_session": True,
                "runtime_root": str(runtime), "runtime_sha256": implementation,
                "driver_sha256": digest(root / "scripts/run_performance_trial.py"),
                "task_count": 75, "repeats": 1,
                "limits": {"model_calls": 500, "wall_seconds": 3600, "command_seconds": 120,
                           "max_output_tokens": 64000, "timeout_retries": 0, "strict_wall": True},
                "selection": "Four original failure tasks first, then fixed interleaved lexical order",
                "stopping": "Any new unknown/nonzero fee or unscored mechanical error stops the queue",
                "valid_failures": "Retain and continue; no resampling for a better score",
                "initial_validation_runs": {
                    "javascript/sum-of-multiples": str(root / "work/vmshare/performance-hy4-session-v5/javascript-sum-of-multiples-B0-r1"),
                    "extract-elf": str(root / "work/vmshare/performance-hy4-session-v5/extract-elf-B0-r1")},
                "interpretation": "Development coverage, not unseen generalization; repetitions and matched public framework comparison remain separate"}
    if args.framework == "dsh":
        protocol.update(framework="dsh", sdk_version="0.2.2rc2",
            images_enabled=True,
            client_sha256=digest(root / "work/codebuddy/node_modules/@tencent-ai/codebuddy-code/dist/codebuddy-headless.js"),
            image_metadata_sha256=digest(Path(os.environ["COURSE_CODEBUDDY_IMAGE_METADATA"])),
            runtime_mounts={name: str(Path(os.environ[name]).resolve(strict=True))
                           for name in ("COURSE_DSH_RUNTIME", "COURSE_DSH_RUNTIME_ARM64")},
            initial_validation_runs={})
        if os.environ.get("COURSE_AGENT_FRAMEWORK") != "dsh" or os.environ.get("COURSE_CODEBUDDY_IMAGES") != "1":
            raise ValueError("The process environment must match the frozen native DSH protocol")
    elif os.environ.get("COURSE_AGENT_FRAMEWORK", "mini-swe") != "mini-swe":
        raise ValueError("The framework environment differs from the requested queue")
    if args.initial_validation_runs:
        protocol["initial_validation_runs"] = read_json(args.initial_validation_runs)
        if set(protocol["initial_validation_runs"]) - {row["id"] for row in ordered}:
            raise ValueError("A validation source is outside the original 75-task union")
    for path, value in ((manifest_path, manifest), (queue / "protocol.json", protocol)):
        if path.exists():
            if read_json(path) != value:
                raise RuntimeError(f"A frozen queue input changed: {path}")
        else:
            save_json(path, value)
    if args.prepare_only:
        print(json.dumps({"prepared_tasks": 75, "manifest": str(manifest_path)}), flush=True)
        return
    environment = os.environ | {"DOCKER_HOST": "unix://" + str(root / "work/v/c/sock/docker.sock"),
        "DOCKER_CONFIG": str(root / "work/docker-config"), "LIMA_HOME": str(root / ".v"),
        "TMPDIR": str(root / "work/process-tmp")}
    docker = str(root / "work/vendor/docker/docker")
    if args.prefetch_only:
        prepared = []
        skipped_completed = []
        for task in ordered:
            if task["benchmark"] not in {"swe", "terminal"}:
                continue
            if read_json(root / "work/performance-stop-20261122.json")["active"]:
                raise RuntimeError("Preparation stopped at the new billing boundary")
            state = read_json(queue / "state.json") if (queue / "state.json").exists() else {}
            if task["id"] in {row["task"] for row in state.get("results", [])}:
                skipped_completed.append(task["id"])
                continue
            inspected = subprocess.run([docker, "image", "inspect", task["image"]], env=environment,
                                       capture_output=True, text=True)
            if inspected.returncode:
                disk = subprocess.check_output([str(root / "work/vendor/bin/limactl"), "shell", "c",
                                                "df", "-Pk", "/"], env=environment, text=True)
                free_bytes = int(disk.splitlines()[-1].split()[3]) * 1024
                if free_bytes < 12 * 1024**3:
                    save_json(queue / "image-preparation.json", {"status": "space_reserve", "new_model_calls": 0,
                        "next_task": task["id"], "free_bytes": free_bytes, "prepared": prepared})
                    print("Image preparation stopped before a new pull to preserve VM workspace", flush=True)
                    return
                save_json(queue / "image-preparation.json", {"status": "pulling", "new_model_calls": 0,
                    "current_task": task["id"], "prepared": prepared})
                with (queue / (task["id"] + ".image-pull.log")).open("a") as log:
                    try:
                        subprocess.run([docker, "pull", "--platform", "linux/amd64", task["image"]],
                            env=environment, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=10800)
                    except (subprocess.TimeoutExpired, subprocess.CalledProcessError) as exc:
                        save_json(queue / "image-preparation.json", {"status": "download_failed",
                            "current_task": task["id"], "new_model_calls": 0, "prepared": prepared,
                            "exception": type(exc).__name__, "detail": str(exc), "timeout_seconds": 10800})
                        raise
            image = subprocess.check_output([docker, "image", "inspect", "--format", "{{.Id}}", task["image"]],
                                            env=environment, text=True).strip()
            if ((task.get("image_id") and image != task["image_id"])
                    or (environment_pins and image != environment_pins[task["id"]])):
                raise RuntimeError(f"The original frozen image changed for {task['id']}")
            prepared.append({"task": task["id"], "image": task["image"], "image_id": image})
            save_json(queue / "image-preparation.json", {"status": "preparing", "new_model_calls": 0,
                "prepared": prepared})
        save_json(queue / "image-preparation.json", {"status": "complete", "new_model_calls": 0,
            "prepared": prepared, "skipped_completed_tasks": skipped_completed})
        return
    mechanical_path = queue / "mechanical-recoveries.json"
    mechanical = read_json(mechanical_path) if mechanical_path.exists() else {}
    if args.recover_task and args.recover_task not in mechanical:
        task = next(row for row in ordered if row["id"] == args.recover_task)
        original = queue / (task["id"].replace("/", "-") + "-B0-r1")
        outcome = read_json(original / "result.json")
        if outcome["scoreable"] or not outcome.get("harbor_result"):
            raise RuntimeError("Only an unscored environment-start timeout can use this recovery entry")
        details = read_json(original / outcome["harbor_result"])
        if (details.get("exception_info") or {}).get("exception_type") != "EnvironmentStartTimeoutError":
            raise RuntimeError("The original failure is outside the zero-model environment recovery scope")
        traces = [json.loads(line) for path in original.rglob("model.jsonl") for line in path.read_text().splitlines()]
        if any(row["event"] == "request" for row in traces):
            raise RuntimeError("A model request already exists; this zero-model recovery entry does not apply")
        image = subprocess.check_output([docker, "image", "inspect", "--format", "{{.Id}}", task["image"]],
                                        env=environment, text=True).strip()
        replacement = queue / "recovered" / original.name
        mechanical[task["id"]] = {"original_run": str(original), "replacement_run": str(replacement),
            "reason": "EnvironmentStartTimeoutError before any model request; pre-pulled identical task image",
            "original_model_requests": 0, "recovery_limit": 1, "prepared_image_id": image,
            "unchanged_protocol_sha256": digest(queue / "protocol.json")}
        save_json(mechanical_path, mechanical)
    results = load_completed_results(ordered, queue, runtime, protocol, mechanical)
    completed_tasks = {row["task"] for row in results}
    deferred = []
    if args.cached_only:
        save_json(queue / "environment-order-adjustment.json", {
            "reason": ("Prepare cold images outside the agent deadline and dispatch ready environments first"
                       if args.framework == "dsh" else
                       "The cold environment timed out before any model request; dispatch ready environments first"),
            "selection_uses_scores": False, "all_75_tasks_still_required": True,
            "changed": "Environment readiness changes task execution order only",
            "unchanged": "Original inputs, frozen runtime, model, limits, permissions, graders and billing gate"})
    state_path = queue / "state.json"
    for task in ordered:
        stop = read_json(root / "work/performance-stop-20261122.json")
        if stop["active"]:
            raise RuntimeError("All new model calls are stopped for an unresolved fee")
        if task["id"] in completed_tasks:
            continue
        directory = run_directory(task, queue, protocol, mechanical)
        if args.cached_only and (directory / "result.json").exists():
            existing = read_json(directory / "result.json")
            if not existing["scoreable"]:
                detail = read_json(directory / existing["harbor_result"]) if existing.get("harbor_result") else {}
                events = [json.loads(line) for path in directory.rglob("model.jsonl")
                          for line in path.read_text().splitlines()]
                if ((detail.get("exception_info") or {}).get("exception_type") != "EnvironmentStartTimeoutError"
                        or any(row["event"] == "request" for row in events)):
                    raise RuntimeError("An unscored attempt needs inspection before deferring or replacing it")
                deferred.append(task["id"])
                continue
        save_json(state_path, {"status": "running", "current_task": task["id"], "completed": len(results),
                              "passed": sum(row["passed"] for row in results), "results": results})
        if not (directory / "result.json").exists():
            if directory.exists():
                raise RuntimeError(f"An unfinished attempt already exists; inspect without overwriting: {directory}")
            if task["benchmark"] in {"swe", "terminal"} or environment_pins:
                reference = "nju-course-aider:" + task["stratum"] if task["benchmark"] == "aider" else task["image"]
                inspected = subprocess.run([docker, "image", "inspect", reference], env=environment,
                                           capture_output=True, text=True)
                if inspected.returncode:
                    if args.cached_only:
                        deferred.append(task["id"])
                        continue
                    with (queue / (task["id"] + ".image-pull.log")).open("a") as log:
                        subprocess.run([docker, "pull", "--platform", "linux/amd64", reference],
                                       env=environment, stdout=log, stderr=subprocess.STDOUT, check=True,
                                       timeout=3600)
                image = subprocess.check_output([docker, "image", "inspect", "--format", "{{.Id}}", reference],
                                                env=environment, text=True).strip()
                if ((task.get("image_id") and image != task["image_id"])
                        or (environment_pins and image != environment_pins[task["id"]])):
                    raise RuntimeError(f"The original frozen image changed for {task['id']}")
            command = [sys.executable, "scripts/run_performance_trial.py", "--task", task["id"],
                       "--manifest", str(manifest_path), "--configuration", "B0", "--persistent-session",
                       "--runtime-root", str(runtime), "--run-dir", str(directory)]
            subprocess.run(command, check=True)
        result = completed_result(task, directory, runtime, framework=args.framework)
        results.append(result)
        completed_tasks.add(task["id"])
        save_json(state_path, {"status": "running", "current_task": None, "completed": len(results),
                              "passed": sum(row["passed"] for row in results), "results": results})
        print(json.dumps({"completed": len(results), "total": 75, **result}, ensure_ascii=False), flush=True)
    save_json(state_path, {"status": "waiting_for_environment" if deferred else "complete", "completed": len(results),
                          "passed": sum(row["passed"] for row in results), "results": results,
                          "deferred_tasks": deferred, "required_total": 75})


if __name__ == "__main__":
    main()
