import argparse
import base64
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

os.environ.setdefault("MSWEA_GLOBAL_CONFIG_DIR", str(Path.cwd() / "work/miniswe-config"))
os.environ.setdefault("MSWEA_SILENT_STARTUP", "1")

from course_eval.codebuddy_free import verify_free_response
from course_eval.export_revision import HOME_PATH, LOG_NAMES, PRIVATE, PRIVATE_PEM, SECRET
from course_eval.summarize import run_metrics
from scripts.run_performance_queue import audit_billing
from scripts.summarize_performance_comparison import control_artifact_metrics, dsh_tool_metrics


def read_json(path):
    return json.loads(path.read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def scrub(text, root):
    text = PRIVATE_PEM.sub("[REDACTED BENCHMARK PRIVATE KEY]", text)
    text = re.sub(r"-----BEGIN [A-Z ]*PRIVATE KEY-----", "[REDACTED PRIVATE KEY HEADER]", text)
    text = HOME_PATH.sub("[本机路径]", text.replace(str(root), "[project]"))
    if SECRET.search(text) or PRIVATE.search(text):
        raise ValueError("Sensitive marker remains in the exported evidence")
    return text


def export_captured_artifacts(source, destination, root, expected_artifacts):
    capture = source / "artifact-capture.json"
    if not capture.exists():
        return {"native_capture_registered": False, "outputs": []}
    record = read_json(capture)
    config_path = source / "artifact-capture-config.json"
    config = read_json(config_path)
    if digest(config_path) != record["config_sha256"]:
        raise ValueError("The actual native artifact collection config changed")
    if record["sources"] != config["artifacts"] or record["sources"] != expected_artifacts:
        raise ValueError("Native artifact sources differ from the frozen task output scope")
    manifest_path, = source.glob("*/artifacts/manifest.json")
    entries = read_json(manifest_path)
    outputs = []
    for name in expected_artifacts:
        entry, = [entry for entry in entries if entry["source"] == name]
        output = {"source": name, "status": entry["status"]}
        if entry["status"] == "ok":
            original = manifest_path.parent.parent / entry["destination"]
            original = original.resolve(strict=True)
            if (not original.is_relative_to(manifest_path.parent.resolve())
                    or entry["type"] != "file" or original.is_symlink() or not original.is_file()):
                raise ValueError("An artifact is outside the native trial artifact directory")
            relative = original.relative_to(source)
            exported = destination / relative
            exported.parent.mkdir(parents=True, exist_ok=True)
            raw = original.read_bytes()
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                decoded = raw.decode("latin1")
                if SECRET.search(decoded) or PRIVATE.search(decoded) or HOME_PATH.search(decoded):
                    raise ValueError("A binary artifact contains a sensitive marker")
                exported.write_bytes(raw)
            else:
                exported.write_text(scrub(text, root))
            output.update(path=str(relative), source_sha256=digest(original), export_sha256=digest(exported),
                          byte_identical=digest(original) == digest(exported), bytes=original.stat().st_size)
        outputs.append(output)
    for original in (capture, config_path, manifest_path):
        exported = destination / original.relative_to(source)
        exported.parent.mkdir(parents=True, exist_ok=True)
        exported.write_text(scrub(original.read_text(), root))
    return {"native_capture_registered": True, "outputs": outputs}


def inspect_nvidia_run(directory, framework, contract):
    from course_eval.nvidia_free import audit_nvidia_events, verify_nvidia_contract

    trace, = directory.rglob("model.jsonl")
    events = [json.loads(line) for line in trace.read_text().splitlines()]
    trial = read_json(directory / "trial.json")
    if trial["framework"] != framework:
        raise ValueError("The actual NVIDIA framework differs from its exported arm")
    model = trial["model"]
    verify_nvidia_contract(read_json(contract), model)
    billing = audit_nvidia_events(events, contract, model, 64000)
    if billing["unverified_requests"]:
        raise ValueError("A completed NVIDIA export lacks an individual free-service proof")
    pending, response, requests = None, None, {}
    for event in events:
        kind = event["event"]
        if kind == "request":
            if pending is not None:
                raise ValueError("A new NVIDIA request preceded its previous individual proof")
            pending = event["request_id"]
            requests[pending] = event
            response = None
        elif kind == "response":
            if pending != event["request_id"] or response is not None:
                raise ValueError("The NVIDIA response lacks its unique pending request")
            response = event
            cap = requests[pending]["payload"]["max_tokens"]
            if type(cap) is not int or not 0 < cap <= 64000 or response["payload"]["usage"]["completion_tokens"] > cap:
                raise ValueError("The NVIDIA export differs from an individual requested output cap")
        elif kind == "billing_verified":
            if pending != event["request_id"] or response is None:
                raise ValueError("The NVIDIA proof precedes its actual individual response")
            pending = None
    if pending is not None:
        raise ValueError("An in-flight NVIDIA call cannot enter a completed export")
    score = read_json(directory / "result.json")
    if not score["scoreable"] or type(score["passed"]) is not bool:
        raise ValueError("Only independent original-scored tasks enter this snapshot")
    metrics = run_metrics(directory)
    metrics.update(control_artifact_metrics(directory, framework, trial["configuration"]))
    if framework == "dsh":
        metrics.update(dsh_tool_metrics(directory))
    return {"task": score["task"], "passed": score["passed"],
            "wall_seconds": score["wall_seconds"], **billing, **metrics}


def inspect_run(directory, framework, nvidia_contract=None):
    if nvidia_contract is not None:
        return inspect_nvidia_run(directory, framework, nvidia_contract)
    billing = audit_billing(directory, allow_context_resets=framework == "dsh")
    logs = list(directory.rglob("model.jsonl"))
    if len(logs) != 1:
        raise ValueError("One real task must have exactly one model event log")
    seen, pending, response_seen, fresh_ids, last_time = {}, None, False, set(), None
    request_ids = set()
    for line in logs[0].read_text().splitlines():
        event = json.loads(line)
        if event["event"] == "request":
            if (pending is not None or event["request_id"] in request_ids
                    or (last_time is not None and event["time"] < last_time)):
                raise ValueError("A new request preceded the previous individual receipt")
            request_ids.add(event["request_id"])
            pending = (event["request_id"], event["native_session_id"])
            response_seen = False
            last_time = event["time"]
        elif event["event"] == "response":
            if pending is None or event["request_id"] != pending[0] or response_seen:
                raise ValueError("A model response lacks its unique pending request")
            verify_free_response(event["payload"])
            fresh_ids = set()
            for item in event["payload"]:
                provider = item.get("providerData", {})
                if "rawUsage" not in provider:
                    continue
                key = (pending[1], provider["messageId"])
                if key in seen:
                    if seen[key] != provider["rawUsage"]:
                        raise ValueError("A cumulative model usage record changed")
                else:
                    seen[key] = provider["rawUsage"]
                    fresh_ids.add(provider["messageId"])
            if len(fresh_ids) != 1:
                raise ValueError("A physical generation lacks exactly one fresh model receipt")
            response_seen = True
            if event["time"] < last_time:
                raise ValueError("The response predates its request")
            last_time = event["time"]
        elif event["event"] == "billing_verified":
            if (pending is None or event["request_id"] != pending[0] or not response_seen
                    or set(event["fresh_model_message_ids"]) != fresh_ids
                    or len(event["fresh_model_message_ids"]) != 1 or event["fresh_usage_records"] != 1
                    or event["time"] < last_time):
                raise ValueError("The individual receipt identity or ordering differs")
            pending = None
            last_time = event["time"]
    if pending is not None:
        raise ValueError("An unfinished actual request cannot enter a completed snapshot")
    metrics = run_metrics(directory)
    if framework == "dsh":
        metrics.update(dsh_tool_metrics(directory))
    score = read_json(directory / "result.json")
    if not score["scoreable"] or type(score["passed"]) is not bool:
        raise ValueError("Only independent original-scored tasks enter this snapshot")
    return {"task": score["task"], "passed": score["passed"],
            "wall_seconds": score["wall_seconds"], **billing, **metrics}


def verify_snapshot(output):
    index = read_json(output / "index.json")
    if index["stage"] != "verified_completed_snapshot":
        raise ValueError("An unfinished export is not a verified evidence snapshot")
    union = {row["id"] for row in read_json(output / "tasks.json")["selected"]}
    expected = set(index.get("planned_task_ids", union))
    actual = [record["task"] for record in index["runs"]]
    if (len(union) != 75 or not expected or expected - union
            or len(expected) != index["required_tasks"]
            or len(set(actual)) != len(actual) or set(actual) - expected):
        raise ValueError("The exported task coverage differs from the original 75-task scope")
    for member in index["files"]:
        path = (output / member["path"]).resolve()
        if not path.is_relative_to(output) or digest(path) != member["export_sha256"]:
            raise ValueError("An exported evidence member changed")
    contract = output / index["nvidia_contract"] if index.get("nvidia_contract") else None
    for record in index["runs"]:
        if inspect_run(output / record["path"], record["framework"], contract) != record["metrics"]:
            raise ValueError("Exported original scores, actual fees or metrics differ from the source")
    passed = sum(r["metrics"]["passed"] for r in index["runs"])
    return {"verified_runs": len(index["runs"]), "passed": passed,
            "all_75_passed": len(expected) == len(actual) == passed == 75,
            "all_planned_passed": len(expected) == len(actual) == passed,
            "known_protected_changes": [record["task"] for record in index["runs"]
                if record["metrics"].get("final_protected_unchanged") is False],
            "verified_files": len(index["files"]), "new_model_calls": 0}


def export_snapshot(args):
    root, output = Path.cwd(), args.out.resolve()
    plan = read_json(args.plan)
    state_bytes = (args.state or args.queue / "state.json").read_bytes()
    state = json.loads(state_bytes)
    matrix = plan.get("comparison_kind") == "complete75_matrix"
    contract = None
    if matrix:
        from scripts.summarize_nvidia_matrix import cohort_operations

        coordinator = cohort_operations(root, plan)
        coordinator.verify_frozen(root, plan)
        completed_result = coordinator.completed_result
        scheduled_trials = coordinator.scheduled_trials
        trial_directory = coordinator.trial_directory
        arm = next((arm for arm in plan["arms"] if arm["id"] == args.arm), None)
        if arm is None or args.queue.resolve() != (root / plan["queue"]).resolve():
            raise ValueError("The export arm or queue differs from the actual frozen matrix")
        if state["plan_sha256"] != digest(args.plan):
            raise ValueError("The source snapshot belongs to a different matrix plan")
        rows = [row for row in state["results"] if row["arm"] == args.arm]
        planned_tasks = arm.get("tasks", plan["task_order"])
        framework = arm["framework"]
        contract = root / plan["contract"]
        sources = {"plan.json": args.plan, "tasks.json": root / plan["manifest"],
                   "checks.json": root / plan["checks"], "nvidia-free-contract.json": contract}
    else:
        if args.arm not in {"fixed_policy", "public_dsh"}:
            raise ValueError("This legacy paired plan does not contain the requested matrix arm")
        key = "policy_results" if args.arm == "fixed_policy" else "baseline_results"
        rows = state[key]
        planned_tasks = [row["id"] for row in read_json(args.plan.parent / "tasks.json")["selected"]]
        framework = "mini-swe" if args.arm == "fixed_policy" else "dsh"
        sources = {"plan.json": args.plan, **{name: args.plan.parent / name
                   for name in ("tasks.json", "checks.json")}}
    if len({row["task"] for row in rows}) != len(rows):
        raise ValueError("The completed source snapshot repeats a task")
    output.mkdir(parents=True, exist_ok=False)
    index = {"stage": "exporting", "format_version": 2, "arm": args.arm,
             "required_tasks": len(planned_tasks), "planned_task_ids": planned_tasks,
             "exporter_sha256": digest(Path(__file__)),
             "sanitizer_sha256": digest(root / "course_eval/export_revision.py"),
             "complete_performance_evaluation": False, "new_model_calls": 0,
             "source_plan_sha256": digest(args.plan), "source_state_sha256": hashlib.sha256(state_bytes).hexdigest(),
             "runs": [], "files": [], "interpretation": "Completed original scores only, retaining failures; partial snapshots are not 75/75. A raw original pass does not establish protected-file or task-source-boundary compliance."}
    if contract is not None:
        index["nvidia_contract"] = "nvidia-free-contract.json"
    for name, source in sources.items():
        destination = output / name
        content = scrub(source.read_text(), root)
        if source == contract:
            if content != source.read_text():
                raise ValueError("Redacting the NVIDIA contract would break its actual proof checksum")
            destination.write_bytes(source.read_bytes())
        else:
            destination.write_text(content)
        json.loads(destination.read_text())
        index["files"].append({"path": name, "source_sha256": digest(source), "export_sha256": digest(destination)})
    snapshot = output / "source-snapshot.json"
    snapshot.write_text(scrub(state_bytes.decode(), root))
    index["files"].append({"path": snapshot.name, "source_sha256": index["source_state_sha256"],
                           "export_sha256": digest(snapshot)})
    for row in rows:
        source = Path(row["run_dir"]).resolve()
        if matrix:
            task = next(task for task in read_json(root / plan["manifest"])["selected"] if task["id"] == row["task"])
            configuration, execution_plan, _ = next(item for item in scheduled_trials(plan, row["task"])
                                                    if item[2] == args.arm)
            expected = trial_directory(root / plan["queue"], row["task"], configuration, execution_plan)
            actual = completed_result(root, execution_plan, task, configuration, expected) | {"arm": args.arm}
            if source != expected.resolve() or actual != row:
                raise ValueError("The exported NVIDIA position differs from its actual frozen protocol or original score")
        before = inspect_run(source, framework, contract)
        if before["task"] != row["task"] or before["passed"] != row["passed"]:
            raise ValueError("The source index differs from its original score")
        relative = Path("runs") / source.name
        destination = output / relative
        subprocess.run([sys.executable, "-m", "course_eval.export_revision", "--runs", str(source),
                        "--out", str(destination)], check=True, capture_output=True, text=True)
        if framework == "dsh":
            sdk_log, = source.rglob("session.v4.jsonl")
            exported = destination / sdk_log.relative_to(source)
            exported.parent.mkdir(parents=True, exist_ok=True)
            exported.write_text(scrub(sdk_log.read_text(), root))
        if not matrix:
            task = next(task for task in read_json(sources["tasks.json"])["selected"]
                        if task["id"] == row["task"])
        expected_artifacts = (task.get("candidate_scope") or {}).get("artifacts", [])
        capture = export_captured_artifacts(source, destination, root, expected_artifacts)
        for exported in destination.rglob("*"):
            if exported.is_file():
                original = source / exported.relative_to(destination)
                index["files"].append({"path": str(exported.relative_to(output)),
                    "source_sha256": digest(original), "export_sha256": digest(exported)})
        protocol = source.with_suffix(".protocol.json")
        protocol_out = destination.with_suffix(".protocol.json")
        protocol_out.write_text(scrub(protocol.read_text(), root))
        json.loads(protocol_out.read_text())
        index["files"].append({"path": str(protocol_out.relative_to(output)),
            "source_sha256": digest(protocol), "export_sha256": digest(protocol_out)})
        exported_contract = output / index["nvidia_contract"] if contract is not None else None
        if inspect_run(destination, framework, exported_contract) != before:
            raise ValueError("The export changed actual original scores, fees or metrics")
        index["runs"].append({"task": row["task"], "framework": framework,
            "source_relative": str(source.relative_to(root)), "path": str(relative), "metrics": before,
            "artifact_capture": capture})
        write_json(output / "index.json", index)
    index["stage"] = "verified_completed_snapshot"
    index["complete_arm_evaluation"] = len(rows) == len(planned_tasks)
    index["complete_performance_evaluation"] = len(rows) == len(planned_tasks) == 75
    write_json(output / "index.json", index)
    print(json.dumps(verify_snapshot(output), ensure_ascii=False))


def native_copy(source, root, output, inventory):
    source = source.resolve(strict=True)
    relative = source.relative_to(root)
    raw = source.read_bytes()
    try:
        content = raw.decode("utf-8")
    except UnicodeDecodeError:
        content = raw.decode("latin1")
    private_content = PRIVATE.search(content) and source.suffix not in {".py", ".mjs", ".cjs", ".sh"}
    if SECRET.search(content) or private_content or PRIVATE_PEM.search(content):
        raise ValueError("Sensitive material requires an explicit filtered export: " + str(relative))
    if "candidates" in relative.parts:
        for name, record in json.loads(content)["files"].items():
            decoded = base64.b64decode(record.get("data", ""), validate=True).decode("utf-8", errors="replace")
            if SECRET.search(decoded) or PRIVATE.search(decoded) or PRIVATE_PEM.search(decoded):
                raise ValueError("Sensitive candidate requires an explicit filtered export: " + name)
    destination = output / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(raw)
    inventory["files_sha256"][str(relative)] = digest(destination)


def verify_native(output):
    inventory = read_json(output / "index.json")
    if inventory["format"] != "native_dsh_exact_evidence_v1":
        raise ValueError("This is not an exact native DSH evidence artifact")
    for name, expected in inventory["files_sha256"].items():
        path = (output / name).resolve(strict=True)
        if not path.is_relative_to(output) or digest(path) != expected:
            raise ValueError("An original native evidence member changed: " + name)
    plan_path = (output / inventory["source_plan"]).resolve(strict=True)
    if (not plan_path.is_relative_to(output) or digest(plan_path) != inventory["source_plan_sha256"]
            or inventory["source_plan"] not in inventory["files_sha256"]):
        raise ValueError("The native export lacks its exact declared comparison plan")
    plan = read_json(plan_path)
    snapshot = output / "source-state.json"
    if digest(snapshot) != inventory["source_state_sha256"]:
        raise ValueError("The original completed-position snapshot changed")
    state = read_json(snapshot)
    positions = {(task, arm["id"]) for task in plan["task_order"] for arm in plan["arms"]
        if "tasks" not in arm or task in arm["tasks"]}
    actual_positions = [(row["task"], row["arm"]) for row in inventory["runs"]]
    saved_positions = [(row["task"], row["arm"]) for row in state["results"]]
    if (inventory["planned_executions"] != plan["planned_executions"]
            or len(positions) != plan["planned_executions"]
            or state["plan_sha256"] != inventory["source_plan_sha256"]
            or actual_positions != saved_positions or len(set(actual_positions)) != len(actual_positions)
            or set(actual_positions) - positions):
        raise ValueError("The native export omitted, repeated or changed a declared scored position")
    from scripts.audit_nvidia_relocated import audit_bundle

    for row in inventory["runs"]:
        score_path = (output / row["score_path"]).resolve(strict=True)
        if (not score_path.is_relative_to(output) or row["score_path"] not in inventory["files_sha256"]
                or digest(score_path) != row["original_score_sha256"]
                or read_json(score_path)["passed"] is not row["passed"]
                or read_json(score_path)["scoreable"] is not True):
            raise ValueError("The original score changed during native export")
        billing = audit_bundle(output, Path(inventory["source_root"]), inventory["runtime_root"],
            "index.json", row["trace"], inventory["contract"], inventory["policy"], inventory["model"])
        for key, value in row["financial"].items():
            if billing[key] != value:
                raise ValueError("Portable original financial evidence differs: " + key)
    return {"verified_original_scores": len(inventory["runs"]),
        "original_passes": sum(row["passed"] for row in inventory["runs"]),
        "planned_executions": inventory["planned_executions"],
        "complete_cohort": len(inventory["runs"]) == inventory["planned_executions"],
        "all_members_byte_identical": True, "new_model_calls": 0, "new_original_grader_calls": 0}


def export_native(args):
    root, output = Path.cwd().resolve(), args.out.resolve()
    plan = read_json(args.plan)
    from scripts.summarize_nvidia_matrix import cohort_operations

    operations = cohort_operations(root, plan)
    operations.verify_frozen(root, plan)
    state_bytes = (root / plan["queue"] / "state.json").read_bytes()
    state = json.loads(state_bytes)
    if state["plan_sha256"] != digest(args.plan):
        raise ValueError("The original-scored state belongs to another frozen plan")
    if plan["comparison_kind"] != "complete75_matrix_with_final":
        raise ValueError("Native export requires the declared full final-method comparison")
    runtime = root / plan["runtime_root"]
    from course_eval import nvidia_free

    if not Path(nvidia_free.__file__).resolve().is_relative_to(runtime):
        raise ValueError("Run the exporter with the exact frozen runtime first in PYTHONPATH")
    tasks = {row["id"]: row for row in read_json(root / plan["manifest"])["selected"]}
    output.mkdir(parents=True, exist_ok=False)
    inventory = {"format": "native_dsh_exact_evidence_v1", "source_root": str(root),
        "source_plan": str(args.plan.resolve().relative_to(root)), "source_plan_sha256": digest(args.plan),
        "source_state_sha256": hashlib.sha256(state_bytes).hexdigest(),
        "runtime_root": plan["runtime_root"], "contract": plan["contract"],
        "policy": plan["nvidia_http_recovery_policy"], "model": plan["model"],
        "planned_executions": plan["planned_executions"], "files_sha256": {}, "runs": [],
        "external_runtime_members": {},
        "interpretation": "Exact original evidence, including real failures and unknowns. Original project paths are retained as provenance for cryptographic prefix checks. Prepared benchmark tests, hidden references, credentials and VM disks are excluded. Partial exports do not establish full75 success."}
    common = [args.plan.resolve(), root / plan["manifest"], root / plan["checks"],
        root / plan["contract"], root / plan["nvidia_http_recovery_policy"],
        root / plan["source_plan"], root / plan["coordinator"], root / plan["admission_plan"],
        root / "scripts/export_performance_evidence.py", root / "scripts/audit_nvidia_relocated.py"]
    common.extend(path for path in runtime.rglob("*") if path.is_file()
        and "__pycache__" not in path.parts and path.suffix != ".pyc")
    text_suffixes = {".py", ".json", ".jsonl", ".md", ".txt", ".toml", ".sh", ".mjs", ".cjs", ".yaml", ".yml"}
    for name, expected in plan["execution_files_sha256"].items():
        if Path(name).suffix in text_suffixes:
            common.append(root / name)
        else:
            inventory["external_runtime_members"][name] = expected
    for source in dict.fromkeys(common):
        native_copy(source, root, output, inventory)
    snapshot = output / "source-state.json"
    snapshot.write_bytes(state_bytes)
    inventory["files_sha256"][snapshot.name] = digest(snapshot)
    generations = set()
    retained = LOG_NAMES | {"dsh-input.json", "dsh-process-control.jsonl", "dsh-stderr.log",
        "nvidia-accepted-http-errors.jsonl"}
    from course_eval.nvidia_evidence import audit_recoverable_events

    for saved in state["results"]:
        configuration, execution, _ = next(value for value in operations.scheduled_trials(plan, saved["task"])
            if value[2] == saved["arm"])
        source = operations.trial_directory(root / plan["queue"], saved["task"], configuration, execution)
        actual = operations.completed_result(root, execution, tasks[saved["task"]], configuration, source)
        if any(saved[key] != value for key, value in actual.items()):
            raise ValueError("A saved native position differs from its exact execution and score")
        trace, = source.rglob("model.jsonl")
        events = [json.loads(line) for line in trace.read_text().splitlines()]
        ids = {row["generation_id"] for row in events if row["event"] == "billing_verified"}
        if ids != set(saved["generation_ids"]) or ids.intersection(generations):
            raise ValueError("Independent positions reuse or alter a real generation identity")
        generations.update(ids)
        members = [source.with_suffix(".protocol.json")]
        members.extend(path for path in source.rglob("*") if path.is_file() and not path.is_symlink()
            and not {"tests", "starter", "grader-input", "_python", "_deps", "solution"}.intersection(path.relative_to(source).parts)
            and (path.name in retained or "candidates" in path.relative_to(source).parts))
        ledger = trace.parent / "nvidia-accepted-http-errors.jsonl"
        if ledger.exists():
            for line in ledger.read_text().splitlines():
                history = Path(json.loads(line)["history_file"])
                record = read_json(history)
                members.extend([history, Path(record["authorization_file"]),
                    Path(record["recovery_policy_file"]), Path(record["official_policy_snapshot"])])
        artifacts = (tasks[saved["task"]].get("candidate_scope") or {}).get("artifacts", [])
        if artifacts:
            capture_manifest, = source.glob("*/artifacts/manifest.json")
            members.extend([capture_manifest, source / "artifact-capture.json", source / "artifact-capture-config.json"])
            for item in read_json(capture_manifest):
                if item["source"] in artifacts and item["status"] == "ok":
                    artifact = (capture_manifest.parent.parent / item["destination"]).resolve(strict=True)
                    if not artifact.is_relative_to(capture_manifest.parent.resolve()) or item["type"] != "file":
                        raise ValueError("An actual submitted artifact escapes its capture directory")
                    members.append(artifact)
        for member in dict.fromkeys(members):
            native_copy(member, root, output, inventory)
        financial = audit_recoverable_events(events, trace, root / plan["contract"], plan["model"], 64000,
            root / plan["nvidia_http_recovery_policy"])
        inventory["runs"].append({"task": saved["task"], "arm": saved["arm"], "passed": actual["passed"],
            "score_path": str((source / "result.json").relative_to(root)),
            "original_score_sha256": actual["original_score_sha256"],
            "trace": str(trace.relative_to(root)), "financial": financial})
    write_json(output / "index.json", inventory)
    environment = os.environ | {"PYTHONPATH": os.pathsep.join((str(output / plan["runtime_root"]), str(output)))}
    completed = subprocess.run([sys.executable, str(output / "scripts/export_performance_evidence.py"),
        "verify-native", "--artifact", str(output)], cwd=output, env=environment,
        capture_output=True, text=True, check=True)
    print(json.dumps(json.loads(completed.stdout), ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    export = commands.add_parser("export")
    export.add_argument("--plan", type=Path, required=True)
    export.add_argument("--queue", type=Path, required=True)
    export.add_argument("--arm", choices=("fixed_policy", "public_dsh", "main", "dsh", "repeat", "control"), required=True)
    export.add_argument("--out", type=Path, required=True)
    export.add_argument("--state", type=Path)
    verify = commands.add_parser("verify")
    verify.add_argument("--artifact", type=Path, required=True)
    native = commands.add_parser("export-native")
    native.add_argument("--plan", type=Path, required=True)
    native.add_argument("--out", type=Path, required=True)
    native_verify = commands.add_parser("verify-native")
    native_verify.add_argument("--artifact", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "export":
        export_snapshot(args)
    elif args.command == "export-native":
        export_native(args)
    elif args.command == "verify-native":
        print(json.dumps(verify_native(args.artifact.resolve()), ensure_ascii=False))
    else:
        print(json.dumps(verify_snapshot(args.artifact.resolve()), ensure_ascii=False))


if __name__ == "__main__":
    main()
