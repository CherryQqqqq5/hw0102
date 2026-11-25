import argparse
from collections import Counter
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BASE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("retained_nvidia_export_helpers", BASE / "export_nvidia_v28.py")
helpers = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helpers)
legacy, consumer = helpers.legacy, helpers.consumer
read, digest, contained = legacy.read, legacy.digest, legacy.contained


def rows_from(snapshot):
    rows = snapshot["retained_pilots"] + snapshot["retained_unscored_v27_videos"] + snapshot["retained_unscored_v28_videos"]
    extra = snapshot.get("retained_unscored_v29_relu", [])
    current = snapshot["plan_sha256"] in {helpers.V30_SHA, helpers.V31_SHA, helpers.V32_SHA}
    v31 = snapshot["plan_sha256"] in {helpers.V31_SHA, helpers.V32_SHA}
    v32 = snapshot["plan_sha256"] == helpers.V32_SHA
    if len(extra) != (3 if current else 0):
        raise ValueError("The current protocol must retain all three real preceding ReLU interruptions")
    rows += extra
    native30 = snapshot.get("retained_unscored_v30_dsh_relu", [])
    probes = snapshot.get("retained_openrouter_route_probes", [])
    if len(native30) != int(v31) or len(probes) != int(v31) + int(v32):
        raise ValueError("The exact old DSH interruption and OR30/31 route probes must stay separate")
    rows += native30
    rows += [snapshot["retained_unscored_v25_interruptions"]["nvidia"], snapshot["retained_unscored_v25_interruptions"]["openrouter"]]
    rows += probes
    expected_count = 16 if v32 else 15 if v31 else 13 if current else 10
    if len(rows) != expected_count or len({row["run_dir"] for row in rows}) != expected_count:
        raise ValueError("Every exact retained physical position must remain distinct")
    if sorted(row["historical_unknown_ordinal"] for row in rows if row.get("historical_unknown_ordinal")) != [26, 27, 28] + ([29] if current else []) + ([30] if v31 else []) + ([31] if v32 else []):
        raise ValueError("The three actual unknown gaps must remain explicit")
    for row in rows:
        ordinal = row.get("historical_unknown_ordinal")
        if ordinal:
            fields = ("actual_amount", "actual_usage", "actual_model_identity", "actual_generation_id") if ordinal in (26, 30, 31) else (
                "unknown_actual_amount", "unknown_actual_usage", "unknown_actual_model_identity")
            if any(name not in row or row[name] is not None for name in fields):
                raise ValueError("The historical snapshot must retain each actual unknown field explicitly as null")
            if ordinal in (30, 31):
                if (row["kind"] != "route_probe" or row["is_task_position"] is not False
                        or row["scoreable"] is not None or row["passed"] is not None
                        or row["original_result"] is not None or row["physical_request_count"] != 1
                        or row["complete_own_receipts"] != 0 or row["own_zero_receipt_available"] is not False
                        or row["unverified_requests"] != [1] or row["reported_monetary_cost_usd"] is not None):
                    raise ValueError("A route unknown remains one nonbenchmark request with no individual fee or usage receipt")
            elif row["scoreable"] is not False or row["passed"] is not None:
                raise ValueError("A missing financial response cannot become an original semantic grade")
            if ordinal in (27, 28, 29):
                expected = {27: [16], 28: [20], 29: [11]}[ordinal]
                if row["accepted_unknown_requests"] != expected or row["billing"]["unverified_requests"] != expected:
                    raise ValueError("The accepted unknown no longer identifies its actual physical request")
    return rows


def sdk_observation(directory):
    sessions = list(directory.rglob("session.v4.jsonl"))
    transports = list(directory.rglob("dsh-transport.jsonl"))
    if len(sessions) > 1 or len(transports) > 1:
        raise ValueError("A historical DSH run has multiple native event streams")
    summaries = []
    for path in transports:
        with path.open() as stream:
            summaries += [row["result"] for row in map(json.loads, stream) if row["event"] == "sdk_result"]
    if len(summaries) > 1:
        raise ValueError("A historical DSH run has multiple final SDK summaries")
    return {"observed_tool_metrics": consumer.reader.dsh_tool_metrics(directory) if sessions else None,
        "final_sdk_summary_available": bool(summaries)}


def inspect_route_probe(directory):
    protocol = read(directory / "protocol.json")
    events = [json.loads(line) for line in (directory / "model.jsonl").read_text().splitlines()]
    request, = [row for row in events if row["event"] == "request"]
    error, = [row for row in events if row["event"] == "request_error"]
    model = "inclusionai/ling-3.2-flash:free"
    valid_protocol = (protocol["allowed_models"] == [model] and protocol["tool_execution"] is False
        and protocol["original_grading"] is False and protocol["actual_model_request_limit"] == 1
        and protocol["output_tokens_limit"] == 512 and protocol["wall_seconds_limit"] == 300
        and protocol["automatic_retries"] == 0 and request["endpoint"] == "https://openrouter.ai/api/v1/responses"
        and request["payload"]["max_output_tokens"] == 512 and request["payload"]["store"] is False
        and request["payload"]["stream"] is False and request["payload"]["plugins"] == []
        and request["payload"]["provider"] == {"allow_fallbacks": False, "max_price": {"prompt": 0, "completion": 0}}
        if "allowed_models" in protocol else protocol["model"] == model and protocol["tool_execution"] is False
        and protocol["paid_fallback"] is False and protocol["actual_model_request_limit"] == 1
        and protocol["limits"]["model_calls"] == 1 and protocol["limits"]["max_output_tokens"] == 512
        and protocol["limits"]["wall_seconds"] == 300 and protocol["limits"]["timeout_retries"] == 0
        and request["payload"]["max_tokens"] == 512)
    if (not valid_protocol
            or request["request_id"] != 1 or request["attempt"] != 1
            or request["payload"]["model"] != model
            or error["request_id"] != 1 or error["http_status"] != 400 or error["response_ids"]
            or error["billing_status"] != "unknown"
            or json.loads(error["body"]) != {"error": {"message": "Request path cannot be relayed", "code": 400}}
            or any(row["event"] in {"response", "billing_verified"} for row in events)):
        raise ValueError("The Ling route probe differs from its one actual no-receipt HTTP400")
    return {"kind": "route_probe", "is_task_position": False, "original_result": None,
        "configured_model": model, "actual_model_identity": None, "actual_generation_id": None,
        "actual_usage": None, "actual_amount": None, "grader_seconds": None, "actual_error": error,
        "billing": {"actual_requests": 1, "verified_nonbilled_service_calls": 0,
            "actual_monetary_receipt_calls": 0, "unverified_requests": [1], "reported_monetary_cost": None},
        "generation_ids": [], "incomplete_request_ids": [1],
        "known_response_usage": {"model_calls": 1, "model_responses": 0, "input_tokens": None,
            "output_tokens": None, "cached_input_tokens": None, "reported_total_tokens": None},
        "complete_total_usage": None, "reported_monetary_cost_usd": None}


def inspect(directory, task, contract, backend, expected_requests, include_sdk=False):
    result = read(directory / "result.json")
    helpers.verify_original_reward(directory, result)
    grade_seconds = legacy.consumer.original_grade(task, directory, result, legacy.LocalSnapshot(directory))
    traces = list(directory.rglob("model.jsonl"))
    if len(traces) > 1 or not traces and (expected_requests != 0 or result["scoreable"] is not False):
        raise ValueError("Only an explicitly recorded zero-request unscored attempt may lack a model trace")
    events = [json.loads(line) for line in traces[0].read_text().splitlines()] if traces else []
    counts = Counter(event["event"] for event in events)
    if backend == "nvidia-free":
        billing = consumer.reader.audit_nvidia_events(events, contract, "stepfun-ai/step-5-preview", 64000)
        identities = [event["generation_id"] for event in events if event["event"] == "billing_verified"]
        incomplete = billing["unverified_requests"]
    else:
        if (counts["request"] != 1 or counts["response"] or counts["billing_verified"]
                or [event["http_status"] for event in events if event["event"] == "request_error"] != [400]):
            raise ValueError("The retained OpenRouter400 is not its original single unknown request")
        billing = {"actual_requests": 1, "verified_nonbilled_service_calls": 0,
            "actual_monetary_receipt_calls": 0, "unverified_requests": [1], "reported_monetary_cost": None}
        identities, incomplete = [], [1]
    if billing["actual_requests"] != expected_requests:
        raise ValueError("The retained actual request count changed")
    if len(identities) != len(set(identities)):
        raise ValueError("The retained position repeats a native model identity")
    usage = consumer.reader.run_metrics(directory)
    totals = [event["payload"].get("usage", {}).get("total_tokens") for event in events if event["event"] == "response"]
    usage["reported_total_tokens"] = sum(totals) if all(type(value) is int and value >= 0 for value in totals) else None
    value = {"original_result": result, "grader_seconds": grade_seconds, "billing": billing,
        "generation_ids": identities, "incomplete_request_ids": incomplete,
        "known_response_usage": {key: usage[key] for key in ("model_calls", "model_responses", "input_tokens", "output_tokens", "cached_input_tokens", "reported_total_tokens")},
        "complete_total_usage": None if incomplete else {key: usage[key] for key in ("input_tokens", "output_tokens", "reported_total_tokens")},
        "reported_monetary_cost_usd": billing["reported_monetary_cost"]}
    if include_sdk:
        value["sdk_observation"] = sdk_observation(directory)
    return json.loads(legacy.scrub(json.dumps(value, ensure_ascii=False), ROOT))


def verify(output):
    index = read(contained(output, "index.json"))
    if index["format"] != "retained_free_attempts_portable_v1" or index["role"] != "historical_cost_and_original_outcome_only":
        raise ValueError("Historical attempts cannot be labeled a new performance matrix")
    members = {row["path"]: row for row in index["files"]}
    if len(members) != len(index["files"]):
        raise ValueError("The history export repeats a physical member")
    for name, member in members.items():
        helpers.verify_member_source(member)
        path = contained(output, name)
        if digest(path) != member["export_sha256"] or path.stat().st_size != member["export_bytes"]:
            raise ValueError("A historical evidence member changed: " + name)
        legacy.private_scan(path)
    actual = {str(path.relative_to(output)) for path in output.rglob("*") if path.is_file()}
    if actual != set(members) | {"index.json"}:
        raise ValueError("Historical evidence inventory is incomplete")
    legacy.private_scan(output / "index.json")
    snapshot = read(output / "analysis-summary.json")
    source_plan = index.get("source_plan_sha256", helpers.V29_SHA)
    if source_plan not in {helpers.V29_SHA, helpers.V30_SHA, helpers.V31_SHA, helpers.V32_SHA} or snapshot["plan_sha256"] != source_plan:
        raise ValueError("The historical evidence lost its actual admitted source plan")
    expected = rows_from(snapshot)
    if source_plan in {helpers.V31_SHA, helpers.V32_SHA}:
        member = "plan-v32.json" if source_plan == helpers.V32_SHA else "plan-v31.json"
        if members[member]["source_sha256"] != source_plan:
            raise ValueError("The historical snapshot lost its exact admitted source plan")
        plan = read(output / member)
        for probe in snapshot["retained_openrouter_route_probes"]:
            ordinal = probe["historical_unknown_ordinal"]
            evidence_member = f"accepted-unknown{ordinal}.json"
            accepted = read(output / evidence_member)
            if (members[evidence_member]["source_sha256"] != probe["accepted_evidence_sha256"]
                or members[evidence_member]["source_sha256"] != plan["all_files_sha256"][probe["accepted_evidence"]]
                or accepted["historical_unknown_ordinal"] != ordinal or accepted["physical_unknown_requests"] != 1
                or accepted["canonical_trace"] != str(Path(probe["run_dir"]) / "model.jsonl")
                or any(accepted[name] is not None for name in (
                    "complete_actual_model_identity", "actual_generation_id", "actual_usage", "actual_amount"))):
                raise ValueError("An individual route unknown acceptance lost its actual null evidence")
    if snapshot["identity_audit"]["errors"] or snapshot["historical_ledger_errors"]:
        raise ValueError("The historical source audit contains unresolved evidence errors")
    contract = output / "nvidia-free-contract.json"
    if not members[contract.name]["byte_identical"] or digest(contract) != members[contract.name]["source_sha256"]:
        raise ValueError("The actual NVIDIA proof contract was altered")
    seen, incomplete, scored = set(), [], []
    requests = proofs = route_count = 0
    for record, row in zip(index["runs"], expected, strict=True):
        helpers.verify_run_source_members(record["source_sha256"], members)
        if record["source_relative"] != row["run_dir"]:
            raise ValueError("A retained attempt was replaced or omitted")
        directory = contained(output, record["path"])
        is_probe = row.get("kind") == "route_probe"
        if is_probe:
            if record.get("kind") != "route_probe":
                raise ValueError("A route probe cannot be substituted for a course attempt")
            current = inspect_route_probe(directory)
            route_count += 1
        else:
            trial = read(directory / "trial.json")
            include_sdk = source_plan in {helpers.V31_SHA, helpers.V32_SHA} and trial["framework"] == "dsh"
            current = inspect(directory, trial["task"], contract, trial["backend"], row["physical_request_count"], include_sdk)
            if include_sdk and current["sdk_observation"] != {key: row["sdk_observation"][key]
                    for key in ("observed_tool_metrics", "final_sdk_summary_available")}:
                raise ValueError("The observed native tools or missing final SDK summary changed")
        if current != record["portable_evidence"] or current["original_result"] != row["original_result"]:
            raise ValueError("The original outcome, actual proof or usage changed after sanitization")
        if is_probe and current["actual_error"] != row["error"]:
            raise ValueError("The route-probe error no longer matches its retained actual source")
        ordinal = row.get("historical_unknown_ordinal")
        expected_ids = {26: [1], 27: [16], 28: [20], 29: [11], 30: [1], 31: [1]}.get(ordinal, [])
        if current["incomplete_request_ids"] != expected_ids:
            raise ValueError("A real missing receipt was erased or invented")
        if ordinal:
            if ((current["original_result"] is not None and current["original_result"]["passed"] is not None)
                    or current["complete_total_usage"] is not None or current["reported_monetary_cost_usd"] is not None):
                raise ValueError("Unknown financial evidence cannot become zero cost or a semantic grade")
            incomplete.append(ordinal)
        if set(current["generation_ids"]) & seen:
            raise ValueError("Two historical attempts reuse a native model generation")
        seen.update(current["generation_ids"])
        requests += current["billing"]["actual_requests"]
        proofs += current["billing"]["verified_nonbilled_service_calls"]
        if current["original_result"] is not None and current["original_result"]["scoreable"]:
            scored.append(current["original_result"]["passed"])
    wanted_unknowns = [26, 27, 28] + ([29] if source_plan in {helpers.V30_SHA, helpers.V31_SHA, helpers.V32_SHA} else []) + ([30] if source_plan in {helpers.V31_SHA, helpers.V32_SHA} else []) + ([31] if source_plan == helpers.V32_SHA else [])
    if len(index["runs"]) != len(expected) or sorted(incomplete) != wanted_unknowns or sorted(scored) != [False, True]:
        raise ValueError("The exact scored pilots and unscored interruptions were not retained")
    return {"status": "verified", "physical_attempts": len(expected), "actual_requests": requests,
        "complete_policy_proofs": proofs, "distinct_native_generation_ids": len(seen),
        "unknown_ordinals": sorted(incomplete), "original_scored_pilots": 2, "original_passed_pilots": 1,
        "unscored_attempts": len(expected) - 2, "reported_monetary_cost_usd": None, "complete_total_usage": None,
        "route_probes": route_count, "unscored_task_attempts": len(expected) - 2 - route_count,
        "inventory_files": len(members), "sensitive_marker_findings": 0,
        "verify_reads_original_run_paths": False, "not_a_new_performance_cohort": True,
        "new_model_calls": 0, "new_original_grader_calls": 0}


def export(args):
    snapshot_path = args.summary.resolve()
    snapshot = read(snapshot_path)
    if snapshot["plan_sha256"] not in {helpers.V29_SHA, helpers.V30_SHA, helpers.V31_SHA, helpers.V32_SHA} or snapshot["stage"] == "invalid_evidence":
        raise ValueError("Use the exact current v29 validated retained-cost snapshot")
    consumer.verify_hashes(snapshot["source_sha256"])
    rows = rows_from(snapshot)
    output = args.out.absolute()
    contained(output, ".")
    if not output.resolve().is_relative_to(BASE) or output.resolve() == BASE:
        raise ValueError("Use a new separate offline output child")
    output.mkdir(parents=True, exist_ok=False)
    files = [legacy.copy_text(output, snapshot_path, "analysis-summary.json")]
    plan = read(ROOT / snapshot["plan_path"])
    if snapshot["plan_sha256"] in {helpers.V31_SHA, helpers.V32_SHA}:
        member = "plan-v32.json" if snapshot["plan_sha256"] == helpers.V32_SHA else "plan-v31.json"
        files.append(legacy.copy_text(output, ROOT / snapshot["plan_path"], member))
        for probe in snapshot["retained_openrouter_route_probes"]:
            files.append(legacy.copy_text(output, ROOT / probe["accepted_evidence"], f"accepted-unknown{probe['historical_unknown_ordinal']}.json"))
    contract = ROOT / plan["lanes"]["main"]["contract"]
    files.append(legacy.copy_text(output, contract, "nvidia-free-contract.json", exact=True))
    records = []
    snapshot_sha = digest(snapshot_path)
    for number, row in enumerate(rows, 1):
        consumer.verify_hashes(row["source_sha256"])
        source = ROOT / row["run_dir"]
        destination = contained(output, str(Path("runs") / (str(number).zfill(2) + "-" + source.name)))
        if row.get("kind") == "route_probe":
            before = inspect_route_probe(source)
            copied = [legacy.copy_text(output, source / name, str(destination.relative_to(output) / name))
                for name in ("model.jsonl", "protocol.json")]
            hashes = {str((source / name).relative_to(ROOT)): digest(source / name) for name in ("model.jsonl", "protocol.json")}
            capture, omitted = {"native_capture_registered": False, "outputs": []}, {}
            after = inspect_route_probe(destination)
        else:
            trial = read(source / "trial.json")
            include_sdk = snapshot["plan_sha256"] in {helpers.V31_SHA, helpers.V32_SHA} and trial["framework"] == "dsh"
            before = inspect(source, trial["task"], contract, trial["backend"], row["physical_request_count"], include_sdk)
            copied, capture, omitted, hashes = legacy.copy_run(output, source, destination, trial["task"])
            after = inspect(destination, read(destination / "trial.json")["task"], output / "nvidia-free-contract.json", trial["backend"], row["physical_request_count"], include_sdk)
        files.extend(copied)
        if before != after:
            raise ValueError("Sanitization changed the retained actual evidence")
        consumer.verify_hashes(hashes)
        records.append({"source_relative": row["run_dir"], "path": str(destination.relative_to(output)),
            "kind": row.get("kind", "course_attempt"),
            "portable_evidence": before, "source_sha256": hashes,
            "artifact_capture": capture, "omitted_file_reasons": omitted})
    consumer.verify_hashes(snapshot["source_sha256"])
    if digest(snapshot_path) != snapshot_sha:
        raise ValueError("The asynchronous source snapshot changed during history export")
    legacy.write(output / "index.json", {"format": "retained_free_attempts_portable_v1",
        "role": "historical_cost_and_original_outcome_only", "source_summary_sha256": snapshot_sha,
        "source_plan_sha256": snapshot["plan_sha256"],
        "exporter_sha256": digest(Path(__file__)), "scored_exporter_sha256": digest(Path(helpers.__file__)),
        "files": files, "runs": records, "new_model_calls": 0, "new_original_grader_calls": 0,
        "scope": "Two real scored v26 pilots,all declared unscored prior course attempts,and any explicitly separate route probe. Known complete proofs remain strict; unknown amounts/usage stay null. None adds a success to the current75-task comparison. Raw sources are unchanged; source/export hashes remain separate."})
    return verify(output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("export", "verify"))
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--summary", type=Path, default=BASE / "final-nvidia-v32-summary/summary.json")
    args = parser.parse_args()
    print(json.dumps(export(args) if args.action == "export" else verify(args.out.absolute()), ensure_ascii=False, indent=2))
