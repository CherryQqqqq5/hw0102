import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

root = Path.cwd()
os.environ.setdefault("MSWEA_GLOBAL_CONFIG_DIR", str(root / "work/miniswe-config"))
os.environ.setdefault("MSWEA_SILENT_STARTUP", "1")

from course_eval.docker_target import DockerTarget
from scripts.run_performance_queue import audit_billing, completed_result, run_directory


def read_json(path):
    return json.loads(path.read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save_json(path, value):
    temporary = path.with_name(path.name + ".writing")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)


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


def release_scored_image(task, reference, environment, queue):
    if task["benchmark"] == "aider":
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
            "reason": "Remove only the rebuildable image cache after both arms are scored; retain all source and evidence"}) + "\n")


def prepare_missing_image(task, environment):
    if task["benchmark"] == "aider":
        raise RuntimeError("A shared Aider image requires its existing reproducible build before continuing")
    base = "django11999" if task["id"] == "django__django-11999" else task["id"].replace("/", "-")
    attempt = 0
    while True:
        stem = base + ("-preparation-r" + str(attempt) if attempt else "")
        record = root / ("work/registry-tools/copy-" + stem + ".json")
        imported = root / ("work/registry-tools/import-" + stem + ".json")
        if not imported.exists():
            break
        if read_json(imported)["status"] != "imported" or not read_json(imported)["pinned_identity_verified"]:
            raise RuntimeError("A previous image import failed; inspect it without overwriting")
        attempt += 1
    if not record.exists():
        subprocess.run([sys.executable, "-m", "scripts.run_pinned_image_copy", "--task", task["id"], "--attempt", str(attempt)],
                       env=environment, check=True)
    if read_json(record)["status"] != "ready_for_import":
        raise RuntimeError("A failed image preparation needs inspection; do not overwrite it")
    subprocess.run([sys.executable, "-m", "scripts.import_pinned_image_copy", "--task", task["id"], "--attempt", str(attempt)],
                   env=environment, check=True)


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
    baseline_runtime = Path(baseline_protocol["runtime_root"])
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
        root / "scripts/run_performance_trial.py": plan["driver_sha256"],
        Path(environment["COURSE_CODEBUDDY_IMAGE_METADATA"]): plan["image_metadata_sha256"],
        Path(environment["COURSE_ELF_PUBLIC_WHEEL"]): plan["elf_wheel_sha256"],
        runtime / "course_eval/codebuddy_free.py": plan["billing_validator_sha256"],
        root / "work/codebuddy/node_modules/@tencent-ai/codebuddy-code/dist/codebuddy-headless.js": plan["client_sha256"]}
    expected.update({runtime / name: checksum for name, checksum in
                     (plan["runtime_sha256"] | plan["runtime_resources_sha256"]).items()})
    expected.update({root / name: checksum for name, checksum in plan["image_preparation_sha256"].items()})
    if plan.get("qualification_protocol"):
        expected[Path(plan["qualification_protocol"])] = plan["qualification_protocol_sha256"]
    expected.update({baseline_runtime / name: checksum for name, checksum in baseline_protocol["runtime_sha256"].items()})
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
            baseline_by_task[task_id] = completed_result(original, source, baseline_runtime, framework="dsh")
        configuration = plan["configuration_by_task"][task_id]
        treatment = queue / (task_id.replace("/", "-") + "-" + configuration + "-r1")
        if (treatment / "result.json").exists():
            task, = read_json(resolved / (task_id.replace("/", "-") + ".json"))["selected"]
            policy_by_task[task_id] = policy_result(task, treatment, configuration, runtime)
    baseline_rows, policy_rows = list(baseline_by_task.values()), list(policy_by_task.values())
    if any(digest(path) != checksum for path, checksum in expected.items()):
        raise RuntimeError("A frozen code, input, client or billing dependency changed")
    if args.validate_only:
        print(json.dumps({"status": "validated", "tasks": len(originals), "baseline_completed": len(baseline_rows),
            "policy_completed": len(policy_rows), "new_model_calls": 0}), flush=True)
        return
    for original in originals:
        if read_json(root / "work/performance-stop-20261122.json")["active"]:
            raise RuntimeError("New models are stopped for an unresolved actual fee")
        if any(digest(path) != checksum for path, checksum in expected.items()):
            raise RuntimeError("A frozen code, input, client or billing dependency changed")
        task_id = original["id"]
        stem = task_id.replace("/", "-")
        configuration = plan["configuration_by_task"][task_id]
        source = run_directory(original, baseline, baseline_protocol, mechanical)
        treatment = queue / (stem + "-" + configuration + "-r1")
        manifest_path = resolved / (stem + ".json")
        baseline_done = (source / "result.json").exists()
        policy_done = (treatment / "result.json").exists()
        if baseline_done and policy_done:
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
        for arm, directory, selected_runtime, framework, selected_manifest, selected_configuration in (
            ("public_dsh", source, baseline_runtime, "dsh", baseline / "tasks.json", "B0"),
            ("fixed_policy", treatment, runtime, "mini-swe", manifest_path, configuration)):
            if (directory / "result.json").exists():
                if arm == "public_dsh":
                    baseline_by_task[task_id] = completed_result(original, directory, baseline_runtime, framework="dsh")
                    baseline_rows = list(baseline_by_task.values())
                else:
                    task, = read_json(manifest_path)["selected"]
                    policy_by_task[task_id] = policy_result(task, directory, configuration, runtime)
                    policy_rows = list(policy_by_task.values())
                continue
            if directory.exists():
                raise RuntimeError("An unfinished real attempt already exists; inspect without overwriting")
            save_json(state_path, {"status": "running", "current_task": task_id, "current_arm": arm,
                "baseline_completed": len(baseline_rows), "policy_completed": len(policy_rows),
                "baseline_results": baseline_rows, "policy_results": policy_rows, "deferred_tasks": deferred})
            command = [sys.executable, str(root / "scripts/run_performance_trial.py"), "--task", task_id,
                "--manifest", str(selected_manifest), "--configuration", selected_configuration,
                "--persistent-session", "--runtime-root", str(selected_runtime), "--run-dir", str(directory)]
            if arm == "fixed_policy":
                command.extend(("--checks", str(policy / "checks.json")))
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
        release_scored_image(original, reference, environment, queue)
    save_json(state_path, {"status": "waiting_for_environment" if deferred else "complete", "current_task": None,
        "required_tasks": 75, "baseline_completed": len(baseline_rows), "policy_completed": len(policy_rows),
        "baseline_passed": sum(row["passed"] for row in baseline_rows), "policy_passed": sum(row["passed"] for row in policy_rows),
        "baseline_results": baseline_rows, "policy_results": policy_rows, "deferred_tasks": deferred})


if __name__ == "__main__":
    main()
