import argparse
import base64
from collections import Counter
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import sys


FOLDER = Path(__file__).resolve().parent
ROOT = FOLDER.parents[1]
spec = importlib.util.spec_from_file_location("v27_offline_consumer", FOLDER / "analyze.py")
consumer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(consumer)

sanitizer_spec = importlib.util.spec_from_file_location("v27_evidence_sanitizer", ROOT / "course_eval/export_revision.py")
sanitizer = importlib.util.module_from_spec(sanitizer_spec)
sanitizer_spec.loader.exec_module(sanitizer)
from scripts.export_performance_evidence import export_captured_artifacts, inspect_nvidia_run, scrub


read = consumer.read
digest = consumer.digest
EXPECTED_PLAN = "13166798b21d7069d9194363cd4d1a3b2ec8d9c9c5f129ca44ebb4fa620e970f"
EXCLUDED = {"starter", "grader-input", "_python", "_deps", "solution", "tests"}


def contained(root, name):
    relative = Path(name)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("An export member is not a contained relative path")
    path = root / relative
    if any(parent.is_symlink() for parent in (path, *path.parents)):
        raise ValueError("An export path or ancestor is a symlink")
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError("An export member escapes its declared directory")
    return path


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def private_scan(path):
    raw = path.read_bytes()
    text = raw.decode("utf-8", errors="replace")
    if any(pattern.search(text) for pattern in (sanitizer.SECRET, sanitizer.PRIVATE,
            sanitizer.HOME_PATH, sanitizer.PRIVATE_PEM)):
        raise ValueError("Sensitive content requires explicit review: " + path.name)
    if path.suffix == ".json":
        value = json.loads(text)
        if "candidates" in path.parts:
            for name, record in value["files"].items():
                decoded = base64.b64decode(record.get("data", ""), validate=True).decode("utf-8", errors="replace")
                if any(pattern.search(decoded) for pattern in (sanitizer.SECRET, sanitizer.PRIVATE,
                        sanitizer.HOME_PATH, sanitizer.PRIVATE_PEM)):
                    raise ValueError("Sensitive candidate requires explicit review: " + name)
    elif path.suffix == ".jsonl":
        for line in text.splitlines():
            json.loads(line)


def clean_text(path):
    text = path.read_text(encoding="utf-8")
    if path.name == "model.jsonl":
        text = sanitizer.sanitize_model(text)
    elif path.name == "agent.json":
        info = json.loads(text)["info"]
        text = json.dumps({"info": {key: info[key] for key in ("exit_status", "submission", "model_stats")
            if key in info}}, ensure_ascii=False, indent=2) + "\n"
    return scrub(text, ROOT)


def plan_positions(plan, tasks):
    if len(plan["all_files_sha256"]) != 218 or len(tasks) != 75:
        raise ValueError("The frozen218 inputs or original75 task union changed")
    if Counter(task["benchmark"] for task in tasks.values()) != {"aider": 25, "swe": 25, "terminal": 25}:
        raise ValueError("The original task strata changed")
    expected = {"main": ("mini-swe", "C0", 1), "dsh": ("dsh", "B0", 1), "repeat": ("mini-swe", "C0", 2)}
    if set(plan["lanes"]) != set(expected):
        raise ValueError("The three frozen lanes changed")
    positions = []
    for name, lane in plan["lanes"].items():
        if ((lane["framework"], lane["configuration"], lane["repetition"]) != expected[name]
                or lane["backend"] != "nvidia-free" or lane["model"] != "stepfun-ai/step-5-preview"
                or len(lane["tasks"]) != 75 or set(lane["tasks"]) != set(tasks)):
            raise ValueError("The frozen model/framework/configuration/repetition or complete75 lane changed")
        for task in lane["tasks"]:
            suffix = task.replace("/", "-") + "-" + lane["configuration"] + "-r" + str(lane["repetition"])
            positions.append((name, task, str(Path(plan["queue"]) / name / suffix)))
    if len({name for _, _, name in positions}) != 225:
        raise ValueError("The physical225 positions are not unique")
    return positions


class LocalSnapshot:
    def __init__(self, directory):
        self.directory = directory

    def add(self, path):
        relative = path.relative_to(self.directory)
        return contained(self.directory, relative)

    def json(self, path):
        return read(self.add(path))


def inspect_portable(directory, protocol_path, plan, lane, task, contract):
    trial, protocol = read(directory / "trial.json"), read(protocol_path)
    consumer.validate_protocol(plan, EXPECTED_PLAN, lane, task, trial, protocol)
    metrics = inspect_nvidia_run(directory, lane["framework"], contract)
    result = read(directory / "result.json")
    if result["task"] != task["id"] or metrics["actual_requests"] <= 0:
        raise ValueError("The original score lacks its actual task and new model calls")
    if metrics["actual_requests"] > plan["limits"]["model_calls"] or metrics["model_request_retries"]:
        raise ValueError("A source position exceeded the frozen model budget or retried HTTP")
    grade_seconds = consumer.original_grade(task, directory, result, LocalSnapshot(directory))
    trace, = directory.rglob("model.jsonl")
    generations = []
    proposed = Counter()
    with trace.open() as stream:
        for line in stream:
            event = json.loads(line)
            if event["event"] == "billing_verified":
                generations.append(event["generation_id"])
            elif event["event"] == "response":
                for choice in event["payload"].get("choices", []):
                    for call in (choice.get("message") or {}).get("tool_calls") or []:
                        proposed[(call.get("function") or {}).get("name", "<missing_function_name>")] += 1
    if len(generations) != len(set(generations)) or len(generations) != metrics["actual_requests"]:
        raise ValueError("Actual native generation IDs are missing or repeated")
    # 终局文件在脱敏后有自己的摘要；语义状态必须与原件完全相同。
    metrics.pop("final_verification_sha256", None)
    return {"metrics": metrics, "grader_seconds": grade_seconds, "generation_ids": generations,
        "native_proposed_function_calls_by_name": dict(proposed)}


def inventory_member(output, source, destination):
    private_scan(destination)
    return {"path": str(destination.relative_to(output)), "source_relative": str(source.relative_to(ROOT)),
        "source_sha256": digest(source), "export_sha256": digest(destination),
        "source_bytes": source.stat().st_size, "export_bytes": destination.stat().st_size,
        "byte_identical": digest(source) == digest(destination)}


def copy_text(output, source, name, exact=False):
    destination = contained(output, name)
    destination.parent.mkdir(parents=True, exist_ok=True)
    content = clean_text(source)
    if exact:
        if content.encode("utf-8") != source.read_bytes():
            raise ValueError("The raw NVIDIA contract cannot be redacted without invalidating its proofs")
        destination.write_bytes(source.read_bytes())
    else:
        destination.write_text(content, encoding="utf-8")
    return inventory_member(output, source, destination)


def copy_run(output, source, destination, task):
    omitted = Counter()
    source_shas = {}
    for original in sorted(source.rglob("*")):
        relative = original.relative_to(source)
        if not original.is_file():
            continue
        if EXCLUDED.intersection(relative.parts):
            omitted["existing_private_or_runtime_directory_exclusion"] += 1
            continue
        allowed = original.name in sanitizer.LOG_NAMES or {"candidate", "candidates"}.intersection(relative.parts)
        actual_grade_patch = original.name == "patch.diff" and "swe-official" in relative.parts
        if not allowed and not actual_grade_patch:
            omitted["outside_existing_log_candidate_and_native_capture_allowlist"] += 1
            continue
        if any(part.is_symlink() for part in (original, *original.parents)):
            raise ValueError("A selected source evidence member is a symlink")
        source_shas[str(original.relative_to(ROOT))] = digest(original)
        exported = contained(output, str(destination.relative_to(output) / relative))
        exported.parent.mkdir(parents=True, exist_ok=True)
        exported.write_text(clean_text(original), encoding="utf-8")
        private_scan(exported)
    capture = export_captured_artifacts(source, destination, ROOT, (task.get("candidate_scope") or {}).get("artifacts", []))
    files = []
    for exported in sorted(destination.rglob("*")):
        if exported.is_file():
            original = source / exported.relative_to(destination)
            source_shas.setdefault(str(original.relative_to(ROOT)), digest(original))
            files.append(inventory_member(output, original, exported))
    protocol = source.with_suffix(".protocol.json")
    files.append(copy_text(output, protocol, str(destination.relative_to(output).with_suffix(".protocol.json"))))
    source_shas[str(protocol.relative_to(ROOT))] = digest(protocol)
    return files, capture, dict(omitted), source_shas


def verify(output, require_complete=False):
    contained(output, ".")
    index = read(contained(output, "index.json"))
    if index["format"] != "nvidia75_v27_sanitized_evidence_v1" or index["stage"] not in {
            "partial_internal_evidence", "complete_original225_evidence"}:
        raise ValueError("This is not a finished v27 evidence export")
    members = index["files"]
    names = [member["path"] for member in members]
    if len(names) != len(set(names)):
        raise ValueError("The evidence inventory repeats an exported member")
    for member in members:
        path = contained(output, member["path"])
        if digest(path) != member["export_sha256"] or path.stat().st_size != member["export_bytes"]:
            raise ValueError("An exported evidence member changed: " + member["path"])
        private_scan(path)
    actual_files = {str(path.relative_to(output)) for path in output.rglob("*") if path.is_file()}
    if actual_files != set(names) | {"index.json"}:
        raise ValueError("Uninventoried or missing files exist in the evidence directory")
    private_scan(output / "index.json")
    plan, tasks_manifest = read(output / "plan.json"), read(output / "tasks.json")
    tasks = {task["id"]: task for task in tasks_manifest["selected"]}
    positions = plan_positions(plan, tasks)
    validation = read(output / "source-validation.json")
    if (index["source_plan_sha256"] != EXPECTED_PLAN or validation["plan_sha256"] != EXPECTED_PLAN
            or validation["matched_all_files_sha256"] != plan["all_files_sha256"]
            or validation["matched_count"] != 218):
        raise ValueError("The export lacks the actual218-source validation attestation")
    metadata = {member["path"]: member for member in members}
    analyzed_summary = read(output / "analysis-summary.json")
    analyzed_rows = [json.loads(line) for line in (output / "analysis-trials.jsonl").read_text().splitlines()]
    if (analyzed_summary["plan_sha256"] != EXPECTED_PLAN or analyzed_summary["bound_source_count"] != 218
            or validation["analysis_summary_sha256"] != metadata["analysis-summary.json"]["source_sha256"]
            or validation["analysis_rows_sha256"] != metadata["analysis-trials.jsonl"]["source_sha256"]
            or analyzed_summary["trials_sha256"] != validation["analysis_rows_sha256"]
            or analyzed_summary["generation_identity_overlaps"]
            or [(row["lane"], row["task"], row["run_dir"]) for row in analyzed_rows] != positions):
        raise ValueError("The exported analysis snapshot differs from its exact225 source rows")
    analyzed_closed = [row for row in analyzed_rows if row.get("scoreable") is True]
    if any(row.get("record_validated") is not True or row.get("validation_errors") for row in analyzed_closed):
        raise ValueError("An original-scored snapshot row lacks its successful evidence audit")
    if [(record["lane"], record["task"], record["source_relative"]) for record in index["runs"]] != [
            (row["lane"], row["task"], row["run_dir"]) for row in analyzed_closed[:len(index["runs"])]]:
        raise ValueError("The exported prefix dropped or changed a completed position, possibly a failure")
    analyzed_by_position = {(row["lane"], row["task"]): row for row in analyzed_closed}
    for target, source_key in (("tasks.json", "manifest"), ("checks.json", "checks"),
            ("capture-policy.json", "artifact_capture_policy")):
        if metadata[target]["source_sha256"] != plan["all_files_sha256"][plan[source_key]]:
            raise ValueError("A task/check/capture source differs from the frozen plan")
    contract_path = output / "nvidia-free-contract.json"
    contract_member = metadata[contract_path.name]
    if not contract_member["byte_identical"] or digest(contract_path) != contract_member["source_sha256"]:
        raise ValueError("NVIDIA proof-contract bytes changed")
    expected = {(lane, task): source for lane, task, source in positions}
    used_positions, used_sources, used_generations = set(), set(), set()
    groups = {name: {"original_scored": 0, "raw_passed": 0, "qualified_passed": 0} for name in plan["lanes"]}
    requests = receipts = monetary = 0
    input_tokens = output_tokens = 0
    artifact_count = 0
    for record in index["runs"]:
        key = (record["lane"], record["task"])
        if key in used_positions or record["source_relative"] in used_sources or expected.get(key) != record["source_relative"]:
            raise ValueError("A physical run is repeated or is outside the frozen225 positions")
        used_positions.add(key)
        used_sources.add(record["source_relative"])
        lane, task = plan["lanes"][record["lane"]], tasks[record["task"]]
        if contract_member["source_sha256"] != plan["all_files_sha256"][lane["contract"]]:
            raise ValueError("The raw contract differs from this lane's frozen proof contract")
        directory = contained(output, record["path"])
        portable = inspect_portable(directory, directory.with_suffix(".protocol.json"), plan, lane, task, contract_path)
        if portable != record["portable_evidence"]:
            raise ValueError("Exported score, free proof, usage, control or tools differ from the source")
        analyzed = analyzed_by_position[key]
        if portable["generation_ids"] != analyzed["generation_ids"] or portable["metrics"]["passed"] is not analyzed["passed"]:
            raise ValueError("The actual exported IDs or raw score differ from the analyzed original source")
        for field in ("actual_requests", "verified_nonbilled_service_calls", "actual_monetary_receipt_calls", "reported_monetary_cost"):
            if portable["metrics"][field] != analyzed["billing"][field]:
                raise ValueError("The actual exported proof differs from the analyzed per-call financial evidence")
        for generation in portable["generation_ids"]:
            if generation in used_generations:
                raise ValueError("A native generation ID is reused across physical runs")
            used_generations.add(generation)
        metrics = portable["metrics"]
        group = groups[record["lane"]]
        group["original_scored"] += 1
        group["raw_passed"] += metrics["passed"] is True
        group["qualified_passed"] += metrics["passed"] is True and (not metrics["final_control_applicable"] or
            metrics["final_protected_unchanged"] is True and metrics["final_valid_verification"] is True)
        requests += metrics["actual_requests"]
        receipts += metrics["verified_nonbilled_service_calls"]
        monetary += metrics["actual_monetary_receipt_calls"]
        input_tokens += metrics["input_tokens"]
        output_tokens += metrics["output_tokens"]
        for item in record["artifact_capture"]["outputs"]:
            if item["status"] == "ok":
                artifact_count += 1
                artifact = contained(directory, item["path"])
                if digest(artifact) != item["export_sha256"]:
                    raise ValueError("A native captured artifact changed")
    complete = len(used_positions) == 225 and all(row["original_scored"] == 75 for row in groups.values())
    if index["complete_original225"] is not complete or index["stage"] != (
            "complete_original225_evidence" if complete else "partial_internal_evidence"):
        raise ValueError("The export incorrectly labels its completion status")
    if require_complete and not complete:
        raise ValueError("--require-complete requires all three75-task original-scored lanes")
    return {"status": "verified", "stage": index["stage"], "groups": groups,
        "unique_physical_runs": len(used_positions), "distinct_generation_ids": len(used_generations),
        "actual_requests": requests, "verified_nonbilled_service_calls": receipts,
        "actual_monetary_receipt_calls": monetary,
        "reported_monetary_cost_usd": None if requests != monetary else 0,
        "input_tokens": input_tokens, "output_tokens": output_tokens,
        "native_artifacts": artifact_count, "inventory_files": len(members),
        "export_bytes": sum(member["export_bytes"] for member in members) + (output / "index.json").stat().st_size,
        "sensitive_marker_findings": 0, "verify_reads_original_run_paths": False,
        "scope": "Portable structural/proof verification of the exported closed runs, not a complete semantic trajectory review or a rerun of the original grader. Frozen218 sources were hashed at export time; their recorded hashes do not bundle SDK trees or establish a self-contained execution environment.",
        "new_model_calls": 0, "new_original_grader_calls": 0, "vm_commands": 0, "stop_modified": False}


def export(args):
    plan_path = FOLDER / "plan.json"
    plan = read(plan_path)
    if digest(plan_path) != EXPECTED_PLAN:
        raise ValueError("This exporter only accepts the admitted final v27 plan")
    validation = {"plan_sha256": digest(plan_path), "matched_all_files_sha256": {}, "matched_count": 0}
    for name, expected in plan["all_files_sha256"].items():
        source = contained(ROOT, name)
        if digest(source) != expected:
            raise ValueError("Frozen source changed: " + name)
        validation["matched_all_files_sha256"][name] = expected
    validation["matched_count"] = len(validation["matched_all_files_sha256"])
    summary_path, rows_path = args.analysis / "summary.json", args.analysis / "trials.jsonl"
    summary_sha, rows_sha = digest(summary_path), digest(rows_path)
    summary = read(summary_path)
    if summary["plan_sha256"] != EXPECTED_PLAN or summary["trials_sha256"] != rows_sha:
        raise ValueError("The analyzed snapshot lacks the exact plan or rows checksum")
    for name, expected in summary["source_sha256"].items():
        if digest(contained(ROOT, name)) != expected:
            raise ValueError("An analyzed source changed: " + name)
    rows = [json.loads(line) for line in rows_path.read_text().splitlines()]
    tasks = {task["id"]: task for task in read(ROOT / plan["manifest"])["selected"]}
    expected = plan_positions(plan, tasks)
    if [(row["lane"], row["task"], row["run_dir"]) for row in rows] != expected:
        raise ValueError("The analysis no longer enumerates the fixed225 positions in plan order")
    closed = [row for row in rows if row.get("scoreable") is True]
    if any(row.get("record_validated") is not True or row.get("validation_errors") for row in closed):
        raise ValueError("An original-scored source failed the actual offline consumer")
    selected = closed[:args.limit] if args.limit is not None else closed
    if not selected:
        raise ValueError("There are no validated completed original-scored positions to export")
    if args.require_complete and len(selected) != 225:
        raise ValueError("--require-complete requires all three75-task original-scored lanes")
    output = args.out.absolute()
    contained(output, ".")
    for _, _, name in expected:
        source = (ROOT / name).resolve()
        if output.resolve().is_relative_to(source) or source.is_relative_to(output.resolve()):
            raise ValueError("The export overlaps an original run directory")
    output.mkdir(parents=True, exist_ok=False)
    files = []
    for target, source in (("plan.json", plan_path), ("tasks.json", ROOT / plan["manifest"]),
            ("checks.json", ROOT / plan["checks"]), ("capture-policy.json", ROOT / plan["artifact_capture_policy"]),
            ("analysis-summary.json", summary_path), ("analysis-trials.jsonl", rows_path)):
        files.append(copy_text(output, source, target))
    contracts = {lane["contract"] for lane in plan["lanes"].values()}
    if len(contracts) != 1:
        raise ValueError("This admitted v27 export requires its one exact shared NVIDIA contract")
    contract, = contracts
    files.append(copy_text(output, ROOT / contract, "nvidia-free-contract.json", exact=True))
    validation["observed_utc"] = datetime.now(timezone.utc).isoformat()
    validation["analysis_summary_sha256"] = summary_sha
    validation["analysis_rows_sha256"] = rows_sha
    validation["scope"] = "Actual current218 input SHA equality checked before and after export; sources are recorded, not all copied. No model, API, VM, grader or STOP action."
    validation_path = contained(output, "source-validation.json")
    write(validation_path, validation)
    private_scan(validation_path)
    files.append({"path": validation_path.name, "source_relative": None, "source_sha256": None,
        "export_sha256": digest(validation_path), "source_bytes": None,
        "export_bytes": validation_path.stat().st_size, "byte_identical": None})
    index = {"format": "nvidia75_v27_sanitized_evidence_v1", "stage": "exporting",
        "source_plan_sha256": EXPECTED_PLAN, "complete_original225": False, "files": files, "runs": [],
        "exporter_sha256": digest(Path(__file__)), "sanitizer_sha256": digest(Path(sanitizer.__file__)),
        "existing_exporter_sha256": digest(ROOT / "scripts/export_performance_evidence.py"),
        "analyzer_sha256": digest(FOLDER / "analyze.py"),
        "selection": "All validated original-scored rows in frozen lane/task order, retaining true and false; optional limit takes a prefix, never selected by pass.",
        "excluded_views": "v26 pilots and v25 interruptions are retained separately in analysis metadata and are not exported as v27 scores. Open/unscored runs are status-only in the analyzed snapshot; their model contents are not read.",
        "privacy": "Existing sanitizer/log/candidate exclusions and scrub are reused. Actual SWE grader patch.diff is included with the same scrub. Native declared artifacts use the existing capture whitelist; contract bytes must remain exact. Files requiring additional secret filtering abort, never silently become a successful proof.",
        "new_model_calls": 0, "new_original_grader_calls": 0, "vm_commands": 0, "stop_modified": False}
    for row in selected:
        source = contained(ROOT, row["run_dir"])
        for name, expected_sha in row["source_sha256"].items():
            if digest(contained(ROOT, name)) != expected_sha:
                raise ValueError("A completed source changed after analysis: " + name)
        lane, task = plan["lanes"][row["lane"]], tasks[row["task"]]
        before = inspect_portable(source, source.with_suffix(".protocol.json"), plan, lane, task, ROOT / contract)
        for key in ("actual_requests", "verified_nonbilled_service_calls", "actual_monetary_receipt_calls", "reported_monetary_cost"):
            if before["metrics"][key] != row["billing"][key]:
                raise ValueError("The actual source differs from the analyzed per-request proof")
        if before["generation_ids"] != row["generation_ids"] or before["metrics"]["passed"] is not row["passed"]:
            raise ValueError("The actual generation identities or original score differ from the snapshot")
        name = str(Path("runs") / row["lane"] / source.name)
        destination = contained(output, name)
        copied, capture, omissions, current_shas = copy_run(output, source, destination, task)
        files.extend(copied)
        after = inspect_portable(destination, destination.with_suffix(".protocol.json"), plan, lane, task,
            output / "nvidia-free-contract.json")
        if before != after:
            raise ValueError("Sanitization changed a score, proof, usage, control or tool metric")
        for member in copied:
            if digest(contained(ROOT, member["source_relative"])) != member["source_sha256"]:
                raise ValueError("A selected evidence source changed during export")
        index["runs"].append({"lane": row["lane"], "task": row["task"], "framework": lane["framework"],
            "source_relative": row["run_dir"], "path": name, "portable_evidence": before,
            "artifact_capture": capture, "omitted_file_reasons": omissions,
            "source_member_sha256": current_shas})
        print(json.dumps({"exported_lane": row["lane"], "task": row["task"], "passed": row["passed"], "files": len(copied)}), flush=True)
    for name, expected_sha in plan["all_files_sha256"].items():
        if digest(contained(ROOT, name)) != expected_sha:
            raise ValueError("A frozen input changed during export: " + name)
    if digest(summary_path) != summary_sha or digest(rows_path) != rows_sha:
        raise ValueError("The analyzed source snapshot changed during export")
    index["complete_original225"] = len(selected) == 225
    index["stage"] = "complete_original225_evidence" if index["complete_original225"] else "partial_internal_evidence"
    write(contained(output, "index.json"), index)
    return verify(output, args.require_complete)


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("export", "verify"):
        child = sub.add_parser(name)
        child.add_argument("--out", type=Path, required=True)
        child.add_argument("--require-complete", action="store_true")
        if name == "export":
            child.add_argument("--analysis", type=Path, default=FOLDER / "analysis")
            child.add_argument("--limit", type=int)
    args = parser.parse_args()
    if args.command == "export" and args.limit is not None and args.limit < 1:
        raise ValueError("An optional export prefix must have positive length")
    result = export(args) if args.command == "export" else verify(args.out.absolute(), args.require_complete)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
