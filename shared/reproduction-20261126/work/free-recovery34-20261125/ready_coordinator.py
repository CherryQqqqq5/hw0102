import argparse
import fcntl
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

root = Path.cwd()
os.environ.setdefault("MSWEA_GLOBAL_CONFIG_DIR", str(root / "work/miniswe-config"))
os.environ.setdefault("MSWEA_SILENT_STARTUP", "1")

from course_eval.docker_target import DockerTarget
from course_eval.resource_pool import ResourceLease, image_cleanup_needed, task_requires_exclusive
from scripts.run_performance_queue import audit_billing, completed_result, run_directory


def read_json(path):
    return json.loads(path.read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save_json(path, value):
    temporary = path.with_name(path.name + ".writing")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)


def policy_directory(task_id, configuration, queue, plan):
    recovery = plan.get("mechanical_policy_recoveries", {}).get(task_id)
    if recovery is None:
        return queue / (task_id.replace("/", "-") + "-" + configuration + "-r" + str(plan["repeat"]))
    previous = Path(recovery["original_run"])
    result = read_json(previous / "result.json")
    if (digest(previous / "result.json") != recovery["original_result_sha256"]
            or result["scoreable"] is not False or result["passed"] is not None
            or result.get("error") != recovery["original_error"]):
        raise RuntimeError("Only the registered unscored transport interruption may receive a fresh environment")
    return Path(recovery["replacement_run"])


def recorded_runtime(directory, default, plan):
    saved = plan["registered_existing_runs"].get(str(directory.resolve()))
    if saved is None:
        inflight = plan["registered_inflight_runtime_roots"].get(str(directory.resolve()))
        if inflight is not None:
            if digest(directory.with_suffix(".protocol.json")) != inflight["protocol_sha256"]:
                raise RuntimeError("The original in-flight task protocol changed before handover")
            return Path(inflight["runtime_root"])
        return default
    if digest(directory / "result.json") != saved["result_sha256"]:
        raise RuntimeError("A registered historical original score changed")
    return Path(saved["runtime_root"])


def policy_result(task, directory, configuration, runtime):
    result = read_json(directory / "result.json")
    trial = read_json(directory / "trial.json")
    protocol = read_json(directory.with_suffix(".protocol.json"))
    if (result["task"] != task["id"] or trial["task"] != task or trial["configuration"] != configuration
            or trial.get("framework", "mini-swe") != "mini-swe"
            or protocol["configuration"] != configuration or protocol["model"] != "hy4flash-free"
            or (root / protocol["runtime_root"]).resolve() != runtime
            or not protocol["persistent_native_session"]
            or protocol["limits"] != {"model_calls": 500, "wall_seconds": 3600.0,
                "command_seconds": 120, "max_output_tokens": 64000, "timeout_retries": 0, "strict_wall": True}):
        raise ValueError("The actual policy trial differs from the frozen input")
    if not result["scoreable"] or type(result["passed"]) is not bool:
        raise RuntimeError("The original policy score is missing; preserve and inspect before continuing")
    billing = audit_billing(directory)
    if billing["actual_requests"] != billing["fresh_native_usage_records"]:
        raise RuntimeError("The policy client violated the single-generation rule")
    return {"task": task["id"], "benchmark": task["benchmark"], "configuration": configuration,
            "run_dir": str(directory), "passed": result["passed"], "wall_seconds": result["wall_seconds"], **billing}


def all_consumers_scored(task, plan):
    baseline = Path(plan["baseline_queue"])
    original_protocol = read_json(baseline / "protocol.json")
    mechanical = read_json(baseline / "mechanical-recoveries.json") if (baseline / "mechanical-recoveries.json").exists() else {}
    directories = [run_directory(task, baseline, original_protocol, mechanical)]
    for consumer in plan["cache_consumers"]:
        directories.append(policy_directory(task["id"], plan["configuration_by_task"][task["id"]],
            root / consumer["queue"], consumer))
    return all((path / "result.json").exists() and read_json(path / "result.json")["scoreable"] is True
               for path in directories)


def release_scored_image(task, reference, environment, queue, plan):
    if task["benchmark"] == "aider":
        return
    if not all_consumers_scored(task, plan):
        return
    disk = subprocess.check_output([str(root / "work/vendor/bin/limactl"), "shell", "c", "df", "-Pk", "/"],
        env=environment | {"LIMA_HOME": str(root / ".v")}, text=True)
    free_bytes = int(disk.splitlines()[-1].split()[3]) * 1024
    if free_bytes >= 12 * 1024**3:
        return
    docker = environment["COURSE_DOCKER_BIN"]
    active = subprocess.check_output([docker, "ps", "-aq", "--filter", "ancestor=" + reference],
                                     env=environment, text=True)
    if active.strip():
        raise RuntimeError("A scored image remains attached to a container; preserve it for inspection")
    removed = subprocess.run([docker, "image", "rm", reference], env=environment, capture_output=True, text=True)
    removed.check_returncode()
    with (queue / "cache-cleanup.jsonl").open("a") as handle:
        handle.write(json.dumps({"task": task["id"], "image": reference, "both_original_scores_retained": True,
            "selection_uses_scores": False, "free_bytes_before": free_bytes,
            "removal_stdout": removed.stdout, "removal_stderr": removed.stderr,
            "reason": "Remove only the rebuildable image after main, original DSH and independent repeat are scored, irrespective of success; retain every source and evidence record"}) + "\n")


def prepare_missing_image(task, environment):
    if task["benchmark"] == "aider":
        raise RuntimeError("A shared Aider image requires its existing reproducible build before continuing")
    base = "django11999" if task["id"] == "django__django-11999" else task["id"].replace("/", "-")
    pool = root / "work/parallel-free-evaluation-20261124/resources"
    pool.mkdir(parents=True, exist_ok=True)
    with (pool / ("image-" + base + ".lock")).open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        inspected = subprocess.run([environment["COURSE_DOCKER_BIN"], "image", "inspect", "--format", "{{.Id}}", task["image"]],
            capture_output=True, text=True, env=environment)
        pins = read_json(root / "work/vmshare/performance75-dsh-hy4-v10/environment-pins.json")["pins"]
        if inspected.returncode == 0:
            if inspected.stdout.strip() != pins[task["id"]]:
                raise ValueError("A prepared image differs from its original content identity")
            return
        if "No such image" not in inspected.stderr:
            inspected.check_returncode()
        for recovery in range(2):
            attempt, pending = 0, None
            while True:
                stem = base + ("-preparation-r" + str(attempt) if attempt else "")
                record = root / ("work/registry-tools/copy-" + stem + ".json")
                imported = root / ("work/registry-tools/import-" + stem + ".json")
                if not record.exists():
                    break
                copied = read_json(record)
                if copied["task"] != task["id"] or copied["expected_image_id"] != pins[task["id"]]:
                    raise ValueError("An existing public copy differs from the original task pin")
                if imported.exists():
                    if read_json(imported)["status"] != "imported" or not read_json(imported)["pinned_identity_verified"]:
                        raise RuntimeError("An earlier image import failed; inspect it without overwriting")
                elif copied["status"] in ("downloading", "ready_for_import"):
                    pending = attempt, record
                    break
                elif copied["status"] != "failed":
                    raise RuntimeError("An image copy has an unknown status")
                attempt += 1
            if pending is None:
                subprocess.run([sys.executable, environment["COURSE_PINNED_IMAGE_COPY_DRIVER"], "--task", task["id"],
                    "--attempt", str(attempt)], env=environment, check=True)
            else:
                attempt, record = pending
                deadline = time.monotonic() + 10860
                while read_json(record)["status"] == "downloading":
                    if time.monotonic() > deadline:
                        raise TimeoutError("The public copy did not finish inside its original bounded preparation window")
                    time.sleep(5)
            copied = read_json(record)
            if copied["status"] == "failed" and recovery == 0:
                continue
            if copied["status"] != "ready_for_import":
                raise RuntimeError("The bounded original image copy failed; all earlier records are preserved")
            with ResourceLease(pool, exclusive=True, label="import-original-" + task["id"]):
                subprocess.run([sys.executable, "-m", "scripts.import_pinned_image_copy", "--task", task["id"], "--attempt", str(attempt)],
                    env=environment, check=True)
            return


def cached_references(environment):
    return set(subprocess.check_output([environment["COURSE_DOCKER_BIN"], "image", "ls", "--format", "{{.Repository}}:{{.Tag}}"],
        env=environment, text=True).splitlines())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--queue-dir", type=Path, required=True)
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    policy = args.plan.resolve().parent
    plan = read_json(args.plan)
    queue = args.queue_dir.resolve()
    queue.mkdir(parents=True, exist_ok=True)
    runtime = Path(plan["runtime_root"])
    baseline = Path(plan["baseline_queue"])
    baseline_protocol = read_json(baseline / "protocol.json")
    baseline_runtime = Path(plan["baseline_runtime_root"])
    originals = read_json(baseline / "tasks.json")["selected"]
    original_by_id = {row["id"]: row for row in originals}
    order = plan.get("task_order", [row["id"] for row in originals])
    if len(order) != 75 or len(set(order)) != 75 or set(order) != set(original_by_id):
        raise ValueError("The fixed task order omits or repeats an original task")
    originals = [original_by_id[task_id] for task_id in order]
    templates = {row["id"]: row for row in read_json(policy / "tasks.json")["selected"]}
    mechanical = read_json(baseline / "mechanical-recoveries.json") if (baseline / "mechanical-recoveries.json").exists() else {}
    pins = read_json(baseline / "environment-pins.json")["pins"]
    environment = os.environ | {"DOCKER_HOST": "unix://" + str(root / "work/v/c/sock/docker.sock"),
        "DOCKER_CONFIG": str(root / "work/docker-config"), "COURSE_DOCKER_BIN": str(root / "work/vendor/docker/docker"),
        "COURSE_CODEBUDDY_IMAGES": "1", "COURSE_CODEBUDDY_IMAGE_METADATA": str(root / "work/free-channel-capabilities-20261122/cloud-model-metadata.json"),
        "COURSE_DSH_RUNTIME": str(root / "work/vmshare/dsh-linux-runtime"),
        "COURSE_DSH_RUNTIME_ARM64": str(root / "work/vmshare/dsh-linux-arm64"),
        "COURSE_FREE_STOP_PATH": str(root / "work/performance-stop-20261122.json"),
        "COURSE_ELF_PUBLIC_WHEEL": str(root / "work/vmshare/elf-public-check-deps/pyelftools-0.33-py3-none-any.whl")}
    os.environ.update(environment)
    expected = {policy / "tasks.json": plan["tasks_sha256"], policy / "checks.json": plan["checks_sha256"],
        policy / "scopes.json": plan["scopes_sha256"], Path(__file__).resolve(): plan["coordinator_sha256"],
        baseline / "protocol.json": plan["baseline_protocol_sha256"],
        baseline / "tasks.json": plan["baseline_tasks_sha256"],
        baseline / "environment-pins.json": plan["environment_pins_sha256"],
        root / "scripts/run_performance_queue.py": plan["shared_auditor_sha256"],
        root / plan["driver_path"]: plan["driver_sha256"],
        Path(environment["COURSE_CODEBUDDY_IMAGE_METADATA"]): plan["image_metadata_sha256"],
        Path(environment["COURSE_ELF_PUBLIC_WHEEL"]): plan["elf_wheel_sha256"],
        runtime / "course_eval/codebuddy_free.py": plan["billing_validator_sha256"],
        root / "work/codebuddy/node_modules/@tencent-ai/codebuddy-code/dist/codebuddy-headless.js": plan["client_sha256"]}
    expected.update({runtime / name: checksum for name, checksum in
                     (plan["runtime_sha256"] | plan["runtime_resources_sha256"]).items()})
    expected.update({root / name: checksum for name, checksum in plan["image_preparation_sha256"].items()})
    expected.update({root / name: checksum for name, checksum in plan["request_guard_sha256"].items()})
    environment["COURSE_CODEBUDDY_GUARDED_BIN"] = str(root / plan["guarded_cli_path"])
    environment["COURSE_PINNED_IMAGE_COPY_DRIVER"] = str(root / plan["image_copy_driver"])
    if plan.get("qualification_protocol"):
        expected[Path(plan["qualification_protocol"])] = plan["qualification_protocol_sha256"]
    expected.update({Path(baseline_protocol["runtime_root"]) / name: checksum for name, checksum in baseline_protocol["runtime_sha256"].items()})
    expected.update({baseline_runtime / name: checksum for name, checksum in plan["baseline_runtime_sha256"].items()})
    for bound in plan["historical_runtime_bindings"]:
        expected.update({Path(bound["runtime_root"]) / name: checksum for name, checksum in bound["sha256"].items()})
    if baseline_protocol["client_sha256"] != plan["client_sha256"] or baseline_protocol["image_metadata_sha256"] != plan["image_metadata_sha256"]:
        raise RuntimeError("The baseline model client differs from the fixed comparison")
    baseline_by_task, policy_by_task, deferred = {}, {}, []
    state_path = queue / "state.json"
    resolved = queue / "resolved-inputs"
    resolved.mkdir(exist_ok=True)
    for original in originals:
        task_id = original["id"]
        source = run_directory(original, baseline, baseline_protocol, mechanical)
        if (source / "result.json").exists():
            baseline_by_task[task_id] = completed_result(original, source, recorded_runtime(source, baseline_runtime, plan), framework="dsh")
        configuration = plan["configuration_by_task"][task_id]
        treatment = policy_directory(task_id, configuration, queue, plan)
        if (treatment / "result.json").exists():
            task, = read_json(resolved / (task_id.replace("/", "-") + ".json"))["selected"]
            policy_by_task[task_id] = policy_result(task, treatment, configuration, recorded_runtime(treatment, runtime, plan))
    baseline_rows, policy_rows = list(baseline_by_task.values()), list(policy_by_task.values())
    if any(digest(path) != checksum for path, checksum in expected.items()):
        raise RuntimeError("A frozen code, input, client or billing dependency changed")
    if args.validate_only:
        print(json.dumps({"status": "validated", "tasks": len(originals), "baseline_completed": len(baseline_rows),
            "policy_completed": len(policy_rows), "new_model_calls": 0}), flush=True)
        return
    pending = list(originals)
    original_order = {task["id"]: index for index, task in enumerate(originals)}
    while pending:
        cached = cached_references(environment)
        original = min(pending, key=lambda task: (
            ("nju-course-aider:" + task["stratum"] if task["benchmark"] == "aider" else task["image"]) not in cached,
            original_order[task["id"]]))
        pending.remove(original)
        if read_json(root / "work/performance-stop-20261122.json")["active"]:
            raise RuntimeError("New models are stopped for an unresolved actual fee")
        if any(digest(path) != checksum for path, checksum in expected.items()):
            raise RuntimeError("A frozen code, input, client or billing dependency changed")
        task_id = original["id"]
        stem = task_id.replace("/", "-")
        configuration = plan["configuration_by_task"][task_id]
        source = run_directory(original, baseline, baseline_protocol, mechanical)
        treatment = policy_directory(task_id, configuration, queue, plan)
        manifest_path = resolved / (stem + ".json")
        baseline_done = (source / "result.json").exists()
        policy_done = (treatment / "result.json").exists()
        if policy_done and (baseline_done or plan.get("baseline_dispatch_disabled", False)):
            continue
        reference = "nju-course-aider:" + original["stratum"] if original["benchmark"] == "aider" else original["image"]
        inspected = subprocess.run([environment["COURSE_DOCKER_BIN"], "image", "inspect", "--format", "{{.Id}}", reference],
                                   capture_output=True, text=True, env=environment)
        if inspected.returncode:
            if "No such image" not in inspected.stderr:
                inspected.check_returncode()
            save_json(state_path, {"status": "preparing_original_image", "current_task": task_id,
                "baseline_completed": len(baseline_rows), "policy_completed": len(policy_rows),
                "baseline_results": baseline_rows, "policy_results": policy_rows, "new_model_calls_during_preparation": 0})
            prepare_missing_image(original, environment)
            inspected = subprocess.run([environment["COURSE_DOCKER_BIN"], "image", "inspect", "--format", "{{.Id}}", reference],
                                       capture_output=True, text=True, env=environment, check=True)
        if inspected.stdout.strip() != pins[task_id]:
            raise RuntimeError("An actual environment differs from the original frozen image")
        if not manifest_path.exists():
            task = json.loads(json.dumps(templates[task_id]))
            scope = task.get("candidate_scope")
            if configuration == "C0" and original["benchmark"] == "terminal" and scope["python"] == "python3":
                with ResourceLease(root / plan["resource_pool"], exclusive=task_requires_exclusive(original), label="interpreter-probe-" + task_id):
                    actual_image = subprocess.run([environment["COURSE_DOCKER_BIN"], "image", "inspect", "--format", "{{.Id}}", reference],
                        capture_output=True, text=True, env=environment)
                    if actual_image.returncode:
                        if "No such image" not in actual_image.stderr:
                            actual_image.check_returncode()
                        raise RuntimeError("A pending original image disappeared before its leased probe; no model request started")
                    if actual_image.stdout.strip() != pins[task_id]:
                        raise RuntimeError("The interpreter probe image differs from its frozen original pin")
                    with DockerTarget(reference, "/app", platform="linux/amd64", memory_mb=512, cpus=1,
                                      read_only_empty_dirs=("/tests",)) as target:
                        probe = target.exec("python3 --version", timeout=10)
                        if probe["returncode"]:
                            absent = target.exec("test ! -e /usr/local/bin/python3 && test ! -L /usr/local/bin/python3", timeout=10)
                            if probe["returncode"] != 127 or absent["returncode"]:
                                raise RuntimeError("The candidate interpreter requires explicit mechanical repair before any model")
                            scope["python"] = "/opt/course-runtime/bin/python3"
                        save_json(resolved / (stem + ".environment.json"), {"original_image": pins[task_id],
                            "native_python_probe": probe, "resolved_python": scope["python"], "new_model_calls": 0})
            save_json(manifest_path, {"stage": "frozen", "revisions": read_json(policy / "tasks.json")["revisions"], "selected": [task]})
        arms = (
            ("public_dsh", source, baseline_runtime, "dsh", baseline / "tasks.json", "B0"),
            ("fixed_policy", treatment, runtime, "mini-swe", manifest_path, configuration))
        if plan.get("baseline_dispatch_disabled", False):
            arms = arms[1:]
        for arm, directory, selected_runtime, framework, selected_manifest, selected_configuration in arms:
            if (directory / "result.json").exists():
                if arm == "public_dsh":
                    baseline_by_task[task_id] = completed_result(original, directory, recorded_runtime(directory, baseline_runtime, plan), framework="dsh")
                    baseline_rows = list(baseline_by_task.values())
                else:
                    task, = read_json(manifest_path)["selected"]
                    policy_by_task[task_id] = policy_result(task, directory, configuration, recorded_runtime(directory, runtime, plan))
                    policy_rows = list(policy_by_task.values())
                continue
            if directory.exists():
                raise RuntimeError("An unfinished real attempt already exists; inspect without overwriting")
            save_json(state_path, {"status": "running", "current_task": task_id, "current_arm": arm,
                "baseline_completed": len(baseline_rows), "policy_completed": len(policy_rows),
                "baseline_results": baseline_rows, "policy_results": policy_rows, "deferred_tasks": deferred})
            command = [sys.executable, str(root / plan["driver_path"]), "--task", task_id,
                "--manifest", str(selected_manifest), "--configuration", selected_configuration,
                "--persistent-session", "--framework", framework,
                "--runtime-root", str(selected_runtime), "--run-dir", str(directory)]
            if arm == "fixed_policy":
                command.extend(("--checks", str(policy / "checks.json")))
            command = [sys.executable, str(root / plan["resource_driver"]), "--task", task_id,
                "--benchmark", original["benchmark"], "--image", reference, "--expected-image-id", pins[task_id],
                "--record", str(directory.with_suffix(".resources.json")), "--", *command]
            subprocess.run(command, env=environment | {"COURSE_AGENT_FRAMEWORK": framework}, check=True)
            if arm == "public_dsh":
                baseline_by_task[task_id] = completed_result(original, directory, baseline_runtime, framework="dsh")
                baseline_rows = list(baseline_by_task.values())
                save_json(baseline / "state.json", {"status": "running", "current_task": None,
                    "completed": len(baseline_rows), "passed": sum(row["passed"] for row in baseline_rows),
                    "results": baseline_rows, "dispatcher": "paired " + plan["policy_name"]})
            else:
                task, = read_json(manifest_path)["selected"]
                policy_by_task[task_id] = policy_result(task, directory, configuration, runtime)
                policy_rows = list(policy_by_task.values())
            print(json.dumps({"task": task_id, "arm": arm, "baseline_completed": len(baseline_rows),
                "policy_completed": len(policy_rows)}, ensure_ascii=False), flush=True)
        save_json(state_path, {"status": "running", "current_task": None,
            "baseline_completed": len(baseline_rows), "policy_completed": len(policy_rows),
            "baseline_results": baseline_rows, "policy_results": policy_rows, "deferred_tasks": deferred})
        if image_cleanup_needed(root, environment):
            for finished in originals:
                if finished["benchmark"] == "aider" or not all_consumers_scored(finished, plan):
                    continue
                with ResourceLease(root / plan["resource_pool"], exclusive=True, label="cleanup-" + finished["id"]):
                    reference = finished["image"]
                    inspected = subprocess.run([environment["COURSE_DOCKER_BIN"], "image", "inspect", reference],
                        env=environment, capture_output=True, text=True)
                    if inspected.returncode:
                        if "No such image" not in inspected.stderr:
                            inspected.check_returncode()
                        continue
                    active = subprocess.check_output([environment["COURSE_DOCKER_BIN"], "ps", "-aq", "--filter", "ancestor=" + reference],
                        env=environment, text=True)
                    if not active.strip():
                        release_scored_image(finished, reference, environment, queue, plan)
                if not image_cleanup_needed(root, environment):
                    break
    save_json(state_path, {"status": "waiting_for_environment" if deferred else "complete", "current_task": None,
        "required_tasks": 75, "baseline_completed": len(baseline_rows), "policy_completed": len(policy_rows),
        "baseline_passed": sum(row["passed"] for row in baseline_rows), "policy_passed": sum(row["passed"] for row in policy_rows),
        "baseline_results": baseline_rows, "policy_results": policy_rows, "deferred_tasks": deferred})


if __name__ == "__main__":
    main()
