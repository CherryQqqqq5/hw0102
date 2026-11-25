import argparse
from collections import Counter
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import math
from pathlib import Path
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[2]
FOLDER = Path(__file__).resolve().parent
RUNTIME = ROOT / "work/frozen-performance-free-v27"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(RUNTIME))

from course_eval.nvidia_free import audit_nvidia_events
from course_eval.summarize import grader_seconds, run_metrics
from scripts.summarize_performance_comparison import control_artifact_metrics, dsh_tool_metrics


for module_name in ("nvidia_free", "summarize"):
    if Path(sys.modules["course_eval." + module_name].__file__).resolve() != RUNTIME / "course_eval" / (module_name + ".py"):
        raise RuntimeError("The offline consumer loaded another runtime's module: " + module_name)


class SourceChanged(ValueError):
    pass


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read(path):
    return json.loads(path.read_bytes())


def relative(path):
    return str(path.resolve().relative_to(ROOT))


class Snapshot:
    def __init__(self, directory):
        self.directory = directory.resolve()
        self.hashes = {}
        self.observations = {}

    def add(self, path):
        path = path.resolve(strict=True)
        if not path.is_relative_to(self.directory) and path != self.directory.with_suffix(".protocol.json"):
            raise ValueError("A run evidence path leaves its declared directory: " + str(path))
        self.hashes[relative(path)] = digest(path)
        return path

    def json(self, path):
        path = self.add(path)
        value = read(path)
        if digest(path) != self.hashes[relative(path)]:
            raise SourceChanged("JSON source changed while being read: " + relative(path))
        return value

    def verify(self):
        for name, expected in self.hashes.items():
            if digest(ROOT / name) != expected:
                raise SourceChanged("A completed-run source changed during consumption: " + name)


def validate_protocol(plan, plan_sha, lane, task, trial, protocol):
    expected = {"model": lane["model"], "backend": lane["backend"],
        "framework": lane["framework"], "configuration": lane["configuration"], "limits": plan["limits"]}
    if trial["task"] != task or trial["phase"] != "formal":
        raise ValueError("The actual trial task or phase differs from the frozen position")
    if any(trial.get(key) != value or protocol.get(key) != value for key, value in expected.items()):
        raise ValueError("The actual task protocol differs in model/backend/framework/configuration/limits")
    if (protocol["task"] != task["id"] or protocol["plan_sha256"] != plan_sha
            or (ROOT / protocol["runtime_root"]).resolve() != (ROOT / plan["runtime_root"]).resolve()
            or protocol["historical_unknown_calls_preserved"] != plan["historical_unknown_calls"]):
        raise ValueError("The actual protocol lacks this exact plan/runtime/history binding")


def projected_events(trace, target, snapshot):
    events = []
    snapshot.add(trace)
    # 一次只保留单行原始消息，审计投影去掉推理正文和图片，保留完整用量及金额字段。
    with trace.open() as source, target.open("w") as destination:
        for number, line in enumerate(source, 1):
            if not line.strip():
                continue
            if not line.endswith("\n"):
                raise ValueError(f"Closed model trace has an unfinished line: {number}")
            event = json.loads(line)
            if event["event"] == "request":
                if "first_user_prompt" not in snapshot.observations:
                    content = next((message.get("content") for message in event["payload"].get("messages", [])
                        if message.get("role") == "user"), None)
                    snapshot.observations["first_user_prompt"] = {
                        "legacy_reasoning_text_template_present": isinstance(content, str) and "Reasoning text" in content,
                        "new_registered_verify_instruction_present": isinstance(content, str) and
                            "Before submit, call verify with each registered check_id" in content,
                        "scope": "Literal first-request text observations, not proof of adoption or a causal explanation of all subsequent actions."}
                event["payload"] = {key: value for key, value in event["payload"].items()
                    if key not in {"messages", "tools"}}
            elif event["event"] == "response":
                proposed = snapshot.observations.setdefault("native_proposed_function_calls_by_name", {})
                for choice in event["payload"].get("choices", []):
                    for call in (choice.get("message") or {}).get("tool_calls") or []:
                        name = (call.get("function") or {}).get("name", "<missing_function_name>")
                        proposed[name] = proposed.get(name, 0) + 1
                event["payload"] = {key: value for key, value in event["payload"].items() if key != "choices"}
            events.append(event)
            destination.write(json.dumps(event) + "\n")
    return events


def metric_projection(directory, destination, trace, snapshot):
    events = projected_events(trace, destination / "model.jsonl", snapshot)
    for index, path in enumerate(sorted(directory.rglob("tools.jsonl"))):
        snapshot.add(path)
        folder = destination / ("tools-" + str(index))
        folder.mkdir()
        with path.open() as source, (folder / "tools.jsonl").open("w") as output:
            for line in source:
                if line.strip():
                    event = json.loads(line)
                    recorded = snapshot.observations.setdefault("recorded_tool_events_by_name", {})
                    name = event.get("event", "<missing_event_name>")
                    recorded[name] = recorded.get(name, 0) + 1
                    output.write("{}\n")
    for index, path in enumerate(sorted(directory.rglob("verification.jsonl"))):
        snapshot.add(path)
        folder = destination / ("verification-" + str(index))
        folder.mkdir()
        with path.open() as source, (folder / "verification.jsonl").open("w") as output:
            for line in source:
                if line.strip():
                    event = json.loads(line)
                    output.write(json.dumps({key: event[key] for key in ("event", "missing", "state") if key in event}) + "\n")
    return events, run_metrics(destination)


def original_grade(task, directory, result, snapshot):
    if result.get("harbor_result"):
        path = directory / result["harbor_result"]
        actual = snapshot.json(path)
        verifier = actual.get("verifier_result")
        reward = (verifier.get("rewards") or {}).get("reward") if verifier else None
        scoreable = reward in (0, 1) and not actual.get("exception_info")
        if result["scoreable"] is not bool(scoreable) or result["passed"] is not (reward == 1 if scoreable else None):
            raise ValueError("The outer original score differs from the actual Harbor verifier")
    elif task["benchmark"] == "aider" and (directory / "grader.json").exists():
        actual = snapshot.json(directory / "grader.json")
        code = actual["returncode"]
        scoreable = code not in (124, 125, 126, 127, 137)
        if result["scoreable"] is not scoreable or result["passed"] is not (code == 0 if scoreable else None):
            raise ValueError("The original Aider score differs from the actual grader exit")
    elif task["benchmark"] == "swe" and result["scoreable"]:
        reports = list((directory / "swe-official").rglob("report.json"))
        if len(reports) != 1:
            raise ValueError("A scored SWE position needs one actual original grade report")
        report = snapshot.json(reports[0])[task["id"]]
        if report.get("infra_failure", False) or report["resolved"] is not result["passed"]:
            raise ValueError("The outer SWE score differs from the original report")
    elif result["scoreable"]:
        if not (task["benchmark"] == "aider" and result["passed"] is False and result.get("missing_required_sources")):
            raise ValueError("A scored position lacks its actual original grader evidence")
    for pattern in ("candidate.patch", "artifact.json", "final-verification.json", "controller.jsonl",
            "checkout.json", "artifact-capture.json", "test_output.txt", "run_instance.log", "patch.diff", "reward.txt", "test-stdout.txt"):
        for path in directory.rglob(pattern):
            snapshot.add(path)
    for folder in (directory / "candidate", directory / "swe-official"):
        if folder.exists():
            for path in folder.rglob("*"):
                if path.is_file():
                    snapshot.add(path)
    for folder in directory.glob("*/artifacts"):
        for path in folder.rglob("*"):
            if path.is_file():
                snapshot.add(path)
    return grader_seconds(directory, result)


def inspect_closed(directory, plan, plan_sha, lane, task, out):
    snapshot = Snapshot(directory)
    row = {"source_sha256": snapshot.hashes, "record_validated": False, "validation_errors": []}
    result = snapshot.json(directory / "result.json")
    row.update(scoreable=result.get("scoreable"), passed=result.get("passed"), original_result=result)
    if type(result.get("scoreable")) is not bool or result.get("task") != task["id"]:
        raise ValueError("The original result task or scoreable state is invalid")
    if (result["scoreable"] and type(result.get("passed")) is not bool) or (not result["scoreable"] and result.get("passed") is not None):
        raise ValueError("A missing original score cannot become a semantic pass/failure")
    row["execution_state"] = "scored_true" if result["scoreable"] and result["passed"] else "scored_false" if result["scoreable"] else "unscored_interruption"
    wall = result.get("wall_seconds")
    if type(wall) not in (int, float) or not math.isfinite(wall) or wall < 0:
        raise ValueError("The original wall duration is invalid")
    row["wall_seconds"] = wall
    trial = snapshot.json(directory / "trial.json")
    protocol = snapshot.json(directory.with_suffix(".protocol.json"))
    validate_protocol(plan, plan_sha, lane, task, trial, protocol)
    traces = list(directory.rglob("model.jsonl"))
    if len(traces) > 1 or (result["scoreable"] and len(traces) != 1):
        raise ValueError("An original scored single-agent position needs exactly one actual trace")
    events = []
    if traces:
        with tempfile.TemporaryDirectory(prefix=".metrics-", dir=out) as temporary:
            events, row["usage"] = metric_projection(directory, Path(temporary), traces[0], snapshot)
    else:
        with tempfile.TemporaryDirectory(prefix=".metrics-", dir=out) as temporary:
            row["usage"] = run_metrics(Path(temporary))
    row["raw_billing_verified_events"] = sum(event["event"] == "billing_verified" for event in events)
    row["generation_ids"] = [event["generation_id"] for event in events if event["event"] == "billing_verified"]
    total_tokens = [(event["payload"].get("usage") or {}).get("total_tokens") for event in events if event["event"] == "response"]
    row["usage"]["reported_total_tokens"] = sum(total_tokens) if total_tokens and all(type(value) is int for value in total_tokens) else None
    try:
        billing = audit_nvidia_events(events, ROOT / lane["contract"], lane["model"], plan["limits"]["max_output_tokens"])
        row["billing"] = billing
        responses = {event["request_id"]: event["payload"] for event in events if event["event"] == "response"}
        for event in events:
            if event["event"] != "request":
                continue
            cap = event["payload"]["max_tokens"]
            if type(cap) is not int or not 0 < cap <= plan["limits"]["max_output_tokens"]:
                raise ValueError("An actual request changed its individual output allowance")
            if event["request_id"] in responses and responses[event["request_id"]]["usage"]["completion_tokens"] > cap:
                raise ValueError("Actual completion exceeds its individual requested cap")
        if billing["unverified_requests"]:
            row["validation_errors"].append("Closed physical requests lack their own verified proof; these are not automatically accepted historical unknowns")
        if row["usage"]["model_calls"] != billing["actual_requests"]:
            raise ValueError("Physical request counts differ between existing independent readers")
        if billing["actual_requests"] > plan["limits"]["model_calls"] or row["usage"]["model_request_retries"]:
            raise ValueError("Actual requests exceed the original budget or introduce a forbidden HTTP retry")
        if result["scoreable"] and not billing["actual_requests"]:
            raise ValueError("A prospective scored position lacks an actual fresh model request")
    except (KeyError, TypeError, ValueError) as exc:
        row["validation_errors"].append(type(exc).__name__ + ": " + str(exc))
    row["grader_seconds"] = original_grade(task, directory, result, snapshot)
    control = control_artifact_metrics(directory, lane["framework"], lane["configuration"])
    row["control"] = control
    final_paths = list(directory.rglob("final-verification.json"))
    if len(final_paths) == 1:
        final = snapshot.json(final_paths[0])
        row["final_check_states"] = {key: value["state"] for key, value in final["evidence"].items()}
        row["final_agent_elapsed_seconds"] = final.get("elapsed_seconds")
    row["source_observations"] = snapshot.observations
    row["recorded_tool_events"] = row["usage"]["tool_calls"]
    row["executed_bash_commands"] = snapshot.observations.get("recorded_tool_events_by_name", {}).get("bash", 0) if lane["framework"] == "mini-swe" else None
    row["native_proposed_function_calls_by_name"] = snapshot.observations.get("native_proposed_function_calls_by_name", {})
    row["native_proposed_function_calls"] = sum(row["native_proposed_function_calls_by_name"].values())
    row["request_deadline_skips"] = [event for event in events if event["event"] == "request_skipped_for_deadline"]
    row["captured_declared_artifacts"] = []
    for path in directory.glob("*/artifacts/manifest.json"):
        manifest = snapshot.json(path)
        row["captured_declared_artifacts"] += [{key: item.get(key) for key in ("source", "status", "destination")}
            for item in manifest if item.get("type") == "file"]
    missing_artifact_lines = set()
    for path in directory.rglob("test-stdout.txt"):
        snapshot.add(path)
        with path.open() as stream:
            for line in stream:
                if line.startswith("E ") and ("does not exist" in line or "No such file or directory" in line):
                    missing_artifact_lines.add(line.strip())
    row["original_grader_missing_artifact_lines"] = sorted(missing_artifact_lines)
    if lane["framework"] == "dsh" and result["scoreable"]:
        sessions = list(directory.rglob("session.v4.jsonl"))
        if len(sessions) != 1:
            raise ValueError("The scored native DSH position needs one actual session trace")
        snapshot.add(sessions[0])
        row["sdk_tools"] = dsh_tool_metrics(directory)
    if result["scoreable"] and control["final_control_applicable"] and control["final_control_state"] == "missing_record":
        row["validation_errors"].append("The scored controlled position lacks its actual final control record")
    row["qualified_passed"] = result["passed"] is True and (not control["final_control_applicable"] or
        control["final_protected_unchanged"] is True and control["final_valid_verification"] is True)
    snapshot.verify()
    row["record_validated"] = not row["validation_errors"]
    return row


def inspect_position(directory, plan, plan_sha, lane, task, out):
    base = {"task": task["id"], "benchmark": task["benchmark"], "run_dir": relative(directory),
        "framework": lane["framework"], "configuration": lane["configuration"], "repetition": lane["repetition"],
        "record_validated": False, "model_content_consumed": False}
    if not (directory / "result.json").exists():
        base["execution_state"] = "inflight_or_open" if directory.exists() else "dispatched_waiting_or_preparing" if directory.with_suffix(".protocol.json").exists() else "not_started"
        return base
    try:
        return base | inspect_closed(directory, plan, plan_sha, lane, task, out) | {"model_content_consumed": True}
    except (OSError, KeyError, TypeError, ValueError) as exc:
        failure = base | {"execution_state": "unstable_or_invalid_closed_record", "validation_errors": [type(exc).__name__ + ": " + str(exc)]}
        try:
            result_path = directory / "result.json"
            before = digest(result_path)
            result = read(result_path)
            if digest(result_path) == before:
                failure.update(original_result=result, scoreable=result.get("scoreable"), passed=result.get("passed"),
                    source_sha256={relative(result_path): before})
        except (OSError, TypeError, ValueError):
            failure["original_result_unreadable"] = True
        return failure


def summarize(rows):
    closed = [row for row in rows if row.get("model_content_consumed")]
    billing = [row["billing"] for row in closed if "billing" in row]
    metrics = [row["usage"] for row in closed if "usage" in row]
    requests = sum(row["model_calls"] for row in metrics)
    receipts = sum(row["verified_nonbilled_service_calls"] for row in billing)
    monetary = sum(row["actual_monetary_receipt_calls"] for row in billing)
    grader_times = [row["grader_seconds"] for row in closed if row.get("grader_seconds") is not None]
    unconsumed = sum(row["execution_state"] == "unstable_or_invalid_closed_record" for row in rows)
    proposed = Counter()
    for row in closed:
        proposed.update(row["native_proposed_function_calls_by_name"])
    return {"required": len(rows), "execution_states": dict(Counter(row["execution_state"] for row in rows)),
        "original_scored": sum(row.get("scoreable") is True for row in rows),
        "validated_original_scored": sum(row.get("scoreable") is True and row["record_validated"] for row in rows),
        "raw_passed": sum(row.get("passed") is True for row in rows),
        "raw_false": sum(row.get("passed") is False for row in rows),
        "qualified_passed": sum(row.get("qualified_passed") is True and row["record_validated"] for row in rows),
        "actual_closed_requests": requests, "verified_nonbilled_service_calls": receipts,
        "raw_billing_verified_events": sum(row.get("raw_billing_verified_events", 0) for row in rows),
        "actual_monetary_receipt_calls": monetary,
        "unverified_closed_calls": sum(len(row["unverified_requests"]) for row in billing),
        "reported_monetary_cost_usd": sum(row["reported_monetary_cost"] for row in billing)
            if requests and requests == receipts == monetary and all(row["reported_monetary_cost"] is not None for row in billing) else None,
        "input_tokens": sum(row["input_tokens"] for row in metrics), "output_tokens": sum(row["output_tokens"] for row in metrics),
        "cached_input_tokens": sum(row["cached_input_tokens"] for row in metrics),
        "reported_total_tokens": sum(row["reported_total_tokens"] for row in metrics)
            if metrics and all(row["reported_total_tokens"] is not None for row in metrics) else None,
        "recorded_tool_events": sum(row["recorded_tool_events"] for row in closed),
        "executed_bash_commands": sum(row["executed_bash_commands"] for row in closed if row["executed_bash_commands"] is not None)
            if any(row["framework"] == "mini-swe" for row in rows) else None,
        "native_proposed_function_calls": sum(row["native_proposed_function_calls"] for row in closed),
        "native_proposed_function_calls_by_name": dict(proposed),
        "sdk_tool_calls": sum(row.get("sdk_tools", {}).get("tool_calls", 0) for row in closed),
        "sdk_tool_results": sum(row.get("sdk_tools", {}).get("sdk_tool_results", 0) for row in closed),
        "final_control_states": dict(Counter(row["control"]["final_control_state"] for row in closed)),
        "wall_seconds": sum(row["wall_seconds"] for row in closed),
        "grader_seconds": sum(grader_times) if grader_times else None,
        "evidence_error_positions": sum(bool(row.get("validation_errors")) for row in rows),
        "unconsumed_closed_records": unconsumed,
        "closed_cost_coverage_complete": not unconsumed and len(billing) == len(closed),
        "open_model_request_counts": None}


def write_json(path, value):
    temporary = path.with_suffix(".writing")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=FOLDER / "analysis")
    args = parser.parse_args()
    out = args.out.resolve()
    if not out.is_relative_to(FOLDER) or out == FOLDER:
        raise ValueError("Offline output must be a separate child directory of this experiment folder")
    out.mkdir(parents=True, exist_ok=True)
    with (out / ".consumer.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        helper_hashes = {relative(Path(module.__file__)): digest(Path(module.__file__)) for module in (
            sys.modules[audit_nvidia_events.__module__], sys.modules[run_metrics.__module__],
            sys.modules[control_artifact_metrics.__module__])}
        helper_hashes[relative(Path(__file__))] = digest(Path(__file__))
        plan_path = FOLDER / "plan.json"
        plan_sha, plan = digest(plan_path), read(plan_path)
        if (ROOT / plan["runtime_root"]).resolve() != RUNTIME:
            raise ValueError("This consumer is bound to the actual v27 evidence readers")
        source_hashes = dict(plan["all_files_sha256"])
        for name, expected in source_hashes.items():
            if digest(ROOT / name) != expected:
                raise ValueError("Frozen experiment source changed: " + name)
        tasks = {task["id"]: task for task in read(ROOT / plan["manifest"])["selected"]}
        expected = {"main": ("mini-swe", "C0", 1), "dsh": ("dsh", "B0", 1), "repeat": ("mini-swe", "C0", 2)}
        if len(tasks) != 75 or Counter(task["benchmark"] for task in tasks.values()) != {"aider": 25, "swe": 25, "terminal": 25} or set(plan["lanes"]) != set(expected):
            raise ValueError("The original75 union or three prespecified comparison arms changed")
        rows, expected_dirs = [], set()
        for name, lane in plan["lanes"].items():
            if ((lane["framework"], lane["configuration"], lane["repetition"]) != expected[name]
                    or lane["backend"] != "nvidia-free" or lane["model"] != "stepfun-ai/step-5-preview"
                    or len(lane["tasks"]) != 75 or set(lane["tasks"]) != tasks.keys()):
                raise ValueError("A fixed complete75 arm changed model/configuration/repetition or task coverage")
            for task_id in lane["tasks"]:
                directory = ROOT / plan["queue"] / name / (task_id.replace("/", "-") + "-" + lane["configuration"] + "-r" + str(lane["repetition"]))
                expected_dirs.add(directory.resolve())
                rows.append(inspect_position(directory, plan, plan_sha, lane, tasks[task_id], out) | {"lane": name})
        unexpected = [relative(path) for name in plan["lanes"] for path in (ROOT / plan["queue"] / name).glob("*")
            if path.is_dir() and path.resolve() not in expected_dirs]
        pilots = []
        parent_path = ROOT / "work/free-parallel-v26-20261125/plan.json"
        parent = read(parent_path)
        source_hashes[relative(parent_path)] = digest(parent_path)
        for task_id, saved in plan["retained_prior_pilots"].items():
            directory = ROOT / saved["run_dir"]
            if (directory / "result.json").exists():
                lane = parent["lanes"]["step5-elf" if task_id == "extract-elf" else "step5-video"] | {"framework": "mini-swe", "configuration": "C0", "repetition": 1}
                task = next(task for task in read(ROOT / parent["manifest"])["selected"] if task["id"] == task_id)
                pilots.append(inspect_position(directory, parent, digest(parent_path), lane, task, out) | {"lane": "retained_v26_pilot", "not_a_v27_score": True})
            else:
                pilots.append({"task": task_id, "run_dir": saved["run_dir"], "execution_state": "inflight_or_open",
                    "model_content_consumed": False, "not_a_v27_score": True, "scope": "Status-only pilot; its potentially unstable model contents are intentionally not consumed."})
        interruptions = []
        for subpath in ("nvidia-step5/video-processing-C0-r1", "openrouter-ultra/extract-elf-C0-r1"):
            directory = ROOT / "work/vmshare/performance-free-parallel-v25-20261125" / subpath
            snapshot = Snapshot(directory)
            result = snapshot.json(directory / "result.json")
            if result["scoreable"] is not False or result["passed"] is not None:
                raise ValueError("A retained v25 unscored interruption changed its original classification")
            details = snapshot.json(directory / result["harbor_result"])
            snapshot.verify()
            interruptions.append({"run_dir": relative(directory), "scoreable": False, "passed": None,
                "error": (details.get("exception_info") or {}).get("exception_message"),
                "source_sha256": snapshot.hashes, "model_content_consumed": False,
                "scope": "Retained unscored v25 interruption only; not a semantic false or v27 score. Its trace/cost is outside this consumer's current audited totals."})
        seed = read(ROOT / plan["generation_seed"])
        seen, overlaps = {}, []
        for row in rows + pilots:
            for identity in row.get("generation_ids", []):
                previous = seen.get(identity)
                if previous is not None or (row.get("lane") != "retained_v26_pilot" and identity in seed["generation_ids"]):
                    overlaps.append({"generation_id": identity, "run_dir": row["run_dir"],
                        "previous": previous["run_dir"] if previous else "immutable_historical_seed"})
                    row["record_validated"] = False
                    row.setdefault("validation_errors", []).append("A native generation identity was already consumed at another position")
                    if previous:
                        previous["record_validated"] = False
                        previous.setdefault("validation_errors", []).append("A native generation identity was also consumed at another position")
                seen[identity] = row
        groups = {name: summarize([row for row in rows if row["lane"] == name]) for name in plan["lanes"]}
        complete = all(group["validated_original_scored"] == 75 for group in groups.values()) and not overlaps and not unexpected
        invalid = bool(overlaps or unexpected or any(row.get("validation_errors") for row in rows))
        source_hashes.update(helper_hashes)
        source_hashes[relative(plan_path)] = plan_sha
        for name, expected_hash in source_hashes.items():
            if digest(ROOT / name) != expected_hash:
                raise SourceChanged("An analysis input changed before output: " + name)
        trials = out / "trials.jsonl"
        temporary = trials.with_suffix(".writing")
        with temporary.open("w") as stream:
            for row in rows:
                stream.write(json.dumps(row, ensure_ascii=False) + "\n")
        temporary.replace(trials)
        summary = {"schema": "nvidia75_offline_evidence_summary_v1", "observed_utc": datetime.now(timezone.utc).isoformat(),
            "stage": "complete_original225" if complete else "invalid_evidence" if invalid else "partial", "all_original225_validated": complete,
            "plan_sha256": plan_sha, "bound_source_count": len(plan["all_files_sha256"]), "required_positions": 225,
            "groups": groups, "matrix_totals": summarize(rows), "generation_identity_overlaps": overlaps,
            "distinct_consumed_generation_ids_including_completed_pilot": len(seen), "unexpected_position_directories": unexpected,
            "retained_pilots": pilots, "retained_pilot_totals": summarize(pilots), "retained_unscored_v25_interruptions": interruptions,
            "pilot_interpretation": "The old v26 controller did not select its defined native control template, as established by the bound source/first-request prompt qualification. Missing final artifacts and the minimum900-second new-request window are separate source observations. This consumer does not establish that the unused template caused every later behavior or outcome. Neither pilot enters the new225.",
            "trials_path": relative(trials), "trials_sha256": digest(trials), "source_sha256": source_hashes,
            "metric_definitions": {
                "usage.tool_calls": "Unmodified legacy run_metrics field: nonempty tools.jsonl records. It is not every native function call.",
                "recorded_tool_events": "The same actual tools.jsonl record count, explicitly named; mini-swe currently records bash actions here.",
                "executed_bash_commands": "Model bash actions actually recorded as event=bash in mini-swe tools.jsonl. Excludes internal verify/save/grader shell activity. Not applicable to the SDK tool-event layer.",
                "native_proposed_function_calls": "Tool/function calls proposed in actual provider response choices, grouped by function name. Proposal alone does not establish execution.",
                "sdk_tool_calls": "Native DSH session.v4.jsonl tool/call identities checked by existing dsh_tool_metrics; kept separate from tools.jsonl and provider proposals."},
            "scope": "Only completed stable run evidence is consumed. Inflight/open records have no inferred request, usage, fee or historical-unknown count. v26 pilots and Hy4 are excluded from the225 totals. Money absent under the approved nonbilled-service policy remains null. Raw scores, qualified pass and complete-matrix status are distinct. Metrics use the existing run_metrics on a temporary message-free event projection; original trace SHA is retained. This is structural/source validation, not a semantic or word-for-word trajectory review.",
            "new_model_calls": 0, "new_grader_calls": 0, "vm_commands": 0, "stop_modified": False}
        write_json(out / "summary.json", summary)
        print(json.dumps({"stage": summary["stage"], "groups": groups, "identity_overlaps": len(overlaps),
            "retained_pilot_states": {row["task"]: row["execution_state"] for row in pilots}}, ensure_ascii=False))


if __name__ == "__main__":
    main()
