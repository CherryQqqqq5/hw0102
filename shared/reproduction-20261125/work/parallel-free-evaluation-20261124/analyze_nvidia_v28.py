import argparse
import ast
from collections import Counter
from datetime import datetime, timezone
import fcntl
import hashlib
import importlib.util
import json
from pathlib import Path
import statistics
import sys


ROOT = Path(__file__).resolve().parents[2]
BASE = Path(__file__).resolve().parent
EXPERIMENT = ROOT / "work/nvidia75-transport-v28-20261125"
PLAN_SHA = "86ffe1672729bdf1a68aacc0884a471cd9777162b3a048881a41335823884a92"
V29_SHA = "d2d8e1f1daf9ec0dc25f824a6a4e7168696eb3b92f37f433048690a461a6483e"
V30_SHA = "c0fe4961f310f979bec7da1101e75f0b86db240cb5b40364ccd76f4e2b528f18"
V31_SHA = "0995b63b9b2d06cef8a4348872a7757941c13c8fc1419a2da5b5c133e0dd4da3"
V32_SHA = "f5971565bd5b18374b065f0b2aeb7659727310beef85a0e375b9fd18c9f7dae2"
PARENT_SHA = "13166798b21d7069d9194363cd4d1a3b2ec8d9c9c5f129ca44ebb4fa620e970f"
READER = ROOT / "work/nvidia75-v27-20261125/analyze.py"
READER_SHA = "af0c09ed8056c86f120d3e05fd76caad957e7175f0652c8c15966a38f2188dba"


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read(path):
    return json.loads(path.read_bytes())


def relative(path):
    return str(path.resolve().relative_to(ROOT))


if digest(READER) != READER_SHA:
    raise ValueError("The previously verified offline reader changed")
spec = importlib.util.spec_from_file_location("nvidia_v27_offline_reader", READER)
reader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reader)


def verify_hashes(hashes):
    for name, expected in hashes.items():
        if digest(ROOT / name) != expected:
            raise ValueError("An evidence source changed: " + name)


def merge_hashes(target, additional):
    for name, expected in additional.items():
        if name in target and target[name] != expected:
            raise ValueError("Evidence sources bind conflicting hashes for: " + name)
        target[name] = expected


def observed_sdk_tools(directory, row):
    sessions = list(directory.rglob("session.v4.jsonl"))
    transports = list(directory.rglob("dsh-transport.jsonl"))
    if len(sessions) > 1 or len(transports) > 1:
        raise ValueError("A closed single-agent DSH position has multiple session or transport records")
    paths = sessions + transports
    hashes = {relative(path): digest(path) for path in paths}
    merge_hashes(row["source_sha256"], hashes)
    metrics = reader.dsh_tool_metrics(directory) if sessions else None
    summaries = []
    for path in transports:
        with path.open() as stream:
            for line in stream:
                event = json.loads(line)
                if event["event"] == "sdk_result":
                    summaries.append(event["result"])
    if len(summaries) > 1:
        raise ValueError("A closed single-agent DSH position has multiple final SDK summaries")
    verify_hashes(hashes)
    if metrics is not None:
        row["sdk_tools"] = metrics
    return {"session_trace_available": bool(sessions),
        "session_trace": relative(sessions[0]) if sessions else None,
        "observed_tool_metrics": metrics,
        "final_sdk_summary_available": bool(summaries),
        "final_sdk_finish_reason": summaries[0].get("finish_reason") if summaries else None,
        "final_sdk_summary_source": relative(transports[0]) if summaries else None,
        "scope": "Counts actual native session tool/call and tool/result identities even when original scoring is absent. Missing session evidence stays null; a missing final SDK summary does not erase observed tools or prove task completion."}


def consume(directory, plan, plan_sha, lane, task, out, lane_name, stratum):
    row = reader.inspect_position(directory, plan, plan_sha, lane, task, out)
    row.update(lane=lane_name, transport_stratum=stratum, actual_source_plan_sha256=plan_sha,
        actual_source_runtime=plan["runtime_root"])
    for key in ("scoreable", "passed", "qualified_passed", "wall_seconds", "usage", "billing",
            "control", "generation_ids", "grader_seconds", "physical_request_count"):
        row.setdefault(key, None)
    row.setdefault("source_sha256", {})
    row.setdefault("validation_errors", [])
    row["sdk_observation"] = (observed_sdk_tools(directory, row)
        if row.get("model_content_consumed") and lane["framework"] == "dsh" else None)
    if row.get("model_content_consumed"):
        row["physical_request_count"] = row["usage"]["model_calls"]
        row["all_response_usage_available"] = (row["usage"]["model_calls"] == row["usage"]["model_responses"]
            and not row["usage"]["usage_missing_input_responses"] and not row["usage"]["usage_missing_output_responses"])
        row["observed_response_usage"] = {key: row["usage"][key] for key in
            ("input_tokens", "output_tokens", "cached_input_tokens", "reported_total_tokens")}
    else:
        row["all_response_usage_available"] = None
        row["observed_response_usage"] = None
    return row


def summary(rows):
    value = reader.summarize(rows)
    closed = [row for row in rows if row.get("model_content_consumed")]
    sdk_closed = [row for row in closed if row["framework"] == "dsh"]
    observed = [row["sdk_observation"] for row in sdk_closed
        if row.get("sdk_observation") and row["sdk_observation"]["session_trace_available"]]
    known_calls = sum(item["observed_tool_metrics"]["tool_calls"] for item in observed) if observed else None
    known_results = sum(item["observed_tool_metrics"]["sdk_tool_results"] for item in observed) if observed else None
    all_sessions_available = bool(sdk_closed) and len(observed) == len(sdk_closed)
    value.update(sdk_tool_calls=known_calls if all_sessions_available else None,
        sdk_tool_results=known_results if all_sessions_available else None,
        sdk_observed_tool_calls=known_calls, sdk_observed_tool_results=known_results,
        sdk_session_observed_positions=len(observed),
        sdk_session_missing_positions=len(sdk_closed) - len(observed),
        sdk_final_summary_available_positions=sum(bool(row.get("sdk_observation")
            and row["sdk_observation"]["final_sdk_summary_available"]) for row in sdk_closed),
        sdk_final_summary_missing_positions=sum(not row.get("sdk_observation")
            or not row["sdk_observation"]["final_sdk_summary_available"] for row in sdk_closed),
        sdk_session_trace_available_for_all_closed_positions=all_sessions_available if sdk_closed else None)
    value["raw_pass_rate_of_original_scored"] = value["raw_passed"] / value["original_scored"] if value["original_scored"] else None
    value["qualified_pass_rate_of_validated_scored"] = value["qualified_passed"] / value["validated_original_scored"] if value["validated_original_scored"] else None
    value["known_response_usage"] = {key: value[key] for key in
        ("input_tokens", "output_tokens", "cached_input_tokens", "reported_total_tokens")}
    metrics = [row["usage"] for row in closed]
    known_total_available = bool(metrics) and all(metric["reported_total_tokens"] is not None
        or metric["model_responses"] == 0 for metric in metrics)
    known_total = sum(metric["reported_total_tokens"] or 0 for metric in metrics) if known_total_available else None
    value["reported_total_tokens"] = known_total
    value["known_response_usage"]["reported_total_tokens"] = known_total
    value["closed_cost_records_consumed"] = value["closed_cost_coverage_complete"]
    value["closed_cost_coverage_complete"] = value["closed_cost_records_consumed"] and value["unverified_closed_calls"] == 0
    value["all_monetary_receipts_available"] = (value["actual_monetary_receipt_calls"] == value["actual_closed_requests"]
        if value["actual_closed_requests"] else None)
    complete_usage = bool(closed) and all(row["all_response_usage_available"] is True for row in closed)
    value["all_closed_response_usage_available"] = complete_usage if closed else None
    if not complete_usage:
        for key in ("input_tokens", "output_tokens", "cached_input_tokens", "reported_total_tokens"):
            value[key] = None
    value["known_closed_usage_only_excludes_open_requests"] = True
    value["verified_nonbilled_fraction_of_closed_requests"] = (
        value["verified_nonbilled_service_calls"] / value["actual_closed_requests"] if value["actual_closed_requests"] else None)
    return value


def claims(row):
    if not row.get("model_content_consumed"):
        return []
    directory = ROOT / row["run_dir"]
    traces = list(directory.rglob("model.jsonl"))
    if not traces:
        if row["physical_request_count"] != 0:
            raise ValueError("A consumed physical request lacks its trace")
        return []
    trace, = traces
    if digest(trace) != row["source_sha256"][relative(trace)]:
        raise ValueError("A closed trace changed after the actual reader consumed it")
    result = []
    with trace.open() as stream:
        for line in stream:
            event = json.loads(line)
            if event["event"] == "billing_verified":
                result.append((event["generation_id"], {"trace": str(trace.resolve()),
                    "request_id": event["request_id"], "model": event["provider_model"]}))
    if [identity for identity, _ in result] != row["generation_ids"]:
        raise ValueError("The actual per-request generation claims differ from the reader")
    return result


def identity_audit(matrix, historical, seed, registry, plan):
    seen, errors, inherited_self_bindings = {}, [], Counter()
    seeds = set(seed["generation_ids"])
    historical_ids = registry["generations"]
    for row in matrix + historical:
        is_matrix = row in matrix
        for identity, claim in claims(row):
            reason = None
            prior = historical_ids.get(identity)
            if identity in seen:
                reason = "A native generation identity appears at two consumed physical positions"
            elif is_matrix and identity in seeds:
                reason = "A matrix generation reuses the immutable historical seed"
            elif is_matrix and prior is not None:
                stratum = row["transport_stratum"]
                inherited = (plan["inherited_completed_positions"].get(row["lane"])
                    if stratum == "v27_inherited_elf" else
                    plan.get("additional_inherited_v30_relu_positions", {}).get(row["lane"])
                    if stratum == "v30_inherited_scored_relu" else
                    plan.get("additional_inherited_v31_dsh_relu_position")
                    if stratum == "v31_inherited_scored_dsh_relu" and row["lane"] == "dsh" else None)
                expected_plan = (PARENT_SHA if stratum == "v27_inherited_elf" else
                    V31_SHA if stratum == "v31_inherited_scored_dsh_relu" else V30_SHA)
                if (inherited is None or row["task"] != inherited["task"]
                        or row["actual_source_plan_sha256"] != expected_plan
                        or row["run_dir"] != inherited["run_dir"] or prior != claim):
                    reason = "A new matrix generation reuses another prior registered physical call"
                else:
                    inherited_self_bindings[stratum] += 1
            elif not is_matrix and prior is not None and prior != claim:
                reason = "A historical cost view disagrees with its exact registered physical claim"
            elif not is_matrix and prior is None and identity not in seeds:
                reason = "A declared historical cost view is absent from both frozen histories"
            if reason:
                errors.append({"generation_id": identity, "run_dir": row["run_dir"], "reason": reason,
                    "previous_run": seen.get(identity, {}).get("run_dir")})
                row["record_validated"] = False
                row["validation_errors"].append(reason)
                if identity in seen:
                    previous_row = seen[identity]
                    previous_row["record_validated"] = False
                    previous_row["validation_errors"].append(reason)
            seen[identity] = row
    return {"errors": errors, "distinct_consumed_generation_ids": len(seen),
        "allowed_exact_inherited_elf_self_bindings": inherited_self_bindings["v27_inherited_elf"],
        "allowed_exact_inherited_v30_relu_self_bindings": inherited_self_bindings["v30_inherited_scored_relu"],
        "allowed_exact_inherited_v31_dsh_relu_self_bindings": inherited_self_bindings["v31_inherited_scored_dsh_relu"],
        "allowed_exact_inherited_self_bindings_total": sum(inherited_self_bindings.values()),
        "consumed_prior_snapshot_ids": len(set(seen).intersection(historical_ids)),
        "unconsumed_prior_snapshot_ids": sorted(set(historical_ids) - set(seen)),
        "seed_generation_count": len(seeds), "prior_snapshot_generation_count": len(historical_ids)}


def paired(rows, left_name, right_name, wanted):
    all_positions = {name: {row["task"]: row for row in rows if row["lane"] == name}
        for name in (left_name, right_name)}
    indexed = {name: {row["task"]: row for row in rows if row["lane"] == name
        and row["scoreable"] is True and row["record_validated"] is True}
        for name in (left_name, right_name)}
    left, right = indexed[left_name], indexed[right_name]
    completed = [task for task in wanted if task in left and task in right]
    cross = [task for task in completed if left[task]["transport_stratum"] != right[task]["transport_stratum"]]
    common = [task for task in completed if task not in cross]
    same_stratum_planned = sum(task in all_positions[left_name] and task in all_positions[right_name]
        and all_positions[left_name][task]["transport_stratum"] == all_positions[right_name][task]["transport_stratum"]
        for task in wanted)
    def descriptive(row):
        return {"run_dir": row["run_dir"], "transport_stratum": row["transport_stratum"],
            "actual_source_plan_sha256": row["actual_source_plan_sha256"], "passed": row["passed"],
            "actual_requests": row["billing"]["actual_requests"], "wall_seconds": row["wall_seconds"]}
    cells = Counter((left[task]["passed"], right[task]["passed"]) for task in common)
    delta = cells[True, False] - cells[False, True]
    right_passed = cells[True, True] + cells[False, True]
    def describe(positions):
        value = summary(positions)
        applicable = [row for row in positions if row["control"]["final_control_applicable"]]
        value["final_protected_unchanged_count"] = sum(row["control"]["final_protected_unchanged"] is True for row in applicable) if applicable else None
        value["final_valid_verification_count"] = sum(row["control"]["final_valid_verification"] is True for row in applicable) if applicable else None
        value["control_applicable_positions"] = len(applicable)
        return value
    deltas = {"actual_requests": [left[task]["billing"]["actual_requests"] - right[task]["billing"]["actual_requests"] for task in common],
        "wall_seconds": [left[task]["wall_seconds"] - right[task]["wall_seconds"] for task in common],
        "input_tokens": [left[task]["usage"]["input_tokens"] - right[task]["usage"]["input_tokens"] for task in common],
        "output_tokens": [left[task]["usage"]["output_tokens"] - right[task]["usage"]["output_tokens"] for task in common]}
    return {"left_lane": left_name, "right_lane": right_name, "matched": len(common), "planned": len(wanted),
        "strict_same_stratum_planned": same_stratum_planned,
        "completed_same_task_pairs": len(completed), "cross_stratum_completed_pairs": len(cross),
        "cross_stratum_descriptive_comparisons": [{"task": task, "left": descriptive(left[task]),
            "right": descriptive(right[task]), "scope": "Descriptive same-task observation across protocol strata; excluded from strict paired statistics and causal comparisons."} for task in cross],
        "matched_task_ids": common, "left": describe([left[task] for task in common]),
        "right": describe([right[task] for task in common]),
        "both_pass": cells[True, True], "left_only_pass": cells[True, False],
        "right_only_pass": cells[False, True], "both_fail": cells[False, False],
        "absolute_pass_difference": delta, "percentage_point_difference": 100 * delta / len(common) if common else None,
        "relative_success_rate_change_percent": 100 * delta / right_passed if right_passed else None,
        "mean_paired_left_minus_right": {key: statistics.mean(values) if values else None for key, values in deltas.items()},
        "median_paired_left_minus_right": {key: statistics.median(values) if values else None for key, values in deltas.items()},
        "scope": "Strict pairs require the exact same task and task-local transport stratum,with completed validated original scores on both sides. Cross-stratum same-task observations stay descriptive and retain their scores/costs outside the strict four cells. No pass-based selection,partial imputation or control=0forDSH; no causal-benefit claim."}


def historical_views(plan, parent, parent_sha, tasks, out, source_hashes):
    pilots = []
    v26_path = ROOT / "work/free-parallel-v26-20261125/plan.json"
    v26 = read(v26_path)
    source_hashes[relative(v26_path)] = digest(v26_path)
    merge_hashes(source_hashes, {v26["manifest"]: v26["all_files_sha256"][v26["manifest"]]})
    verify_hashes({v26["manifest"]: source_hashes[v26["manifest"]]})
    for task_id, saved in plan["retained_prior_pilots"].items():
        lane = v26["lanes"]["step5-elf" if task_id == "extract-elf" else "step5-video"] | {
            "framework": "mini-swe", "configuration": "C0", "repetition": 1}
        task = next(task for task in read(ROOT / v26["manifest"])["selected"] if task["id"] == task_id)
        row = consume(ROOT / saved["run_dir"], v26, digest(v26_path), lane, task, out,
            "retained_v26_pilot", "v26_pilot_not_a_matrix_score")
        row["not_a_v28_matrix_score"] = True
        pilots.append(row)
    acceptance_path = ROOT / "work/free-recovery27-20261125/accepted-unknown27.json"
    accepted = read(acceptance_path)
    merge_hashes(source_hashes, accepted["source_sha256"])
    verify_hashes(accepted["source_sha256"])
    interrupted = []
    for actual in accepted["interrupted_positions"]:
        name = actual["lane"]
        row = consume(ROOT / actual["run_dir"], parent, parent_sha, parent["lanes"][name],
            tasks["video-processing"], out, name, "v27_unscored_video_not_a_matrix_score")
        if row["original_result"] != actual["original_result"] or row["scoreable"] is not False or row["passed"] is not None:
            raise ValueError("An unscored video readmission changed its original classification")
        row["not_a_v28_matrix_score"] = True
        row["accepted_unknown_requests"] = []
        if name == "main":
            expected_error = "Closed physical requests lack their own verified proof; these are not automatically accepted historical unknowns"
            if (row["physical_request_count"] != 16 or row["billing"]["unverified_requests"] != [16]
                    or row["billing"]["verified_nonbilled_service_calls"] != 15
                    or row["validation_errors"] != [expected_error]
                    or accepted["physical_unknown_requests"] != 1 or accepted["request_id"] != 16
                    or accepted["actual_usage"] is not None or accepted["actual_amount"] is not None):
                raise ValueError("Unknown27 differs from its unique actual incomplete request")
            row["accepted_unknown_requests"] = [16]
            row["historical_unknown_ordinal"] = 27
            row["unknown_actual_model_identity"] = None
            row["unknown_actual_usage"] = None
            row["unknown_actual_amount"] = None
            row["partial_stream_observation"] = accepted["partial_stream_observation"]
            row["historical_ledger_validated"] = True
            row["known_complete_billing_before_unknown"] = accepted["preceding_main_complete_billing"]
        elif name == "repeat":
            if not row["record_validated"] or row["billing"] != actual["billing"]:
                raise ValueError("The thirteen complete companion proofs changed")
            row["historical_ledger_validated"] = True
        else:
            if not row["record_validated"] or row["physical_request_count"] != 0:
                raise ValueError("The blocked native DSH video unexpectedly sent a model request")
            row["historical_ledger_validated"] = True
        interrupted.append(row)
    v25_path = ROOT / "work/free-parallel-20261125/plan.json"
    v25 = read(v25_path)
    source_hashes[relative(v25_path)] = digest(v25_path)
    merge_hashes(source_hashes, {v25["manifest"]: v25["all_files_sha256"][v25["manifest"]]})
    verify_hashes({v25["manifest"]: source_hashes[v25["manifest"]]})
    v25_admission_path = ROOT / v25["admission"]
    v25_admission_sha = v25["all_files_sha256"][v25["admission"]]
    if digest(v25_admission_path) != v25_admission_sha:
        raise ValueError("The original v25 admission changed")
    source_hashes[relative(v25_admission_path)] = v25_admission_sha
    v25_reader_plan = v25 | {"historical_unknown_calls": read(v25_admission_path)["historical_unknown_calls"]}
    v25_nvidia = ROOT / "work/vmshare/performance-free-parallel-v25-20261125/nvidia-step5/video-processing-C0-r1"
    lane = next(lane for lane in v25["lanes"].values() if lane["backend"] == "nvidia-free") | {
        "framework": "mini-swe", "configuration": "C0", "repetition": 1}
    old_task = next(task for task in read(ROOT / v25["manifest"])["selected"] if task["id"] == "video-processing")
    nvidia = consume(v25_nvidia, v25_reader_plan, digest(v25_path), lane, old_task, out,
        "retained_v25_nvidia", "v25_unscored_nvidia_not_a_matrix_score")
    if not nvidia["record_validated"] or nvidia["scoreable"] is not False or nvidia["physical_request_count"] != 3:
        raise ValueError("The retained v25 NVIDIA interruption lost its three actual proofs")
    nvidia["not_a_v28_matrix_score"] = True
    nvidia["historical_ledger_validated"] = True
    nvidia["historical_schema_adapter"] = "The original v25 plan stores its historical count only in its hash-bound admission. The reader receives that actual admission value; original plan/protocol bytes and plan SHA remain unchanged."
    unknown26_path = ROOT / "work/free-parallel-v26-20261125/accepted-unknown26.json"
    unknown26 = read(unknown26_path)
    source_hashes[relative(unknown26_path)] = digest(unknown26_path)
    merge_hashes(source_hashes, unknown26["source_sha256"])
    verify_hashes(unknown26["source_sha256"])
    or_directory = ROOT / "work/vmshare/performance-free-parallel-v25-20261125/openrouter-ultra/extract-elf-C0-r1"
    snapshot = reader.Snapshot(or_directory)
    result = snapshot.json(or_directory / "result.json")
    actual = snapshot.json(or_directory / result["harbor_result"])
    trace, = or_directory.rglob("model.jsonl")
    snapshot.add(trace)
    counts = Counter()
    request_ids = []
    for line in trace.open():
        event = json.loads(line)
        counts[event["event"]] += 1
        if event["event"] == "request":
            request_ids.append(event["request_id"])
    if (result["scoreable"] is not False or result["passed"] is not None or request_ids != [1]
            or counts["response"] or counts["billing_verified"] or unknown26["physical_unknown_requests"] != 1
            or unknown26["canonical_trace"] != relative(trace)):
        raise ValueError("The actual OpenRouter unknown26 source changed")
    snapshot.verify()
    openrouter = {"run_dir": relative(or_directory), "scoreable": False, "passed": None,
        "original_result": result, "physical_request_count": 1, "complete_own_receipts": 0,
        "historical_unknown_ordinal": 26, "actual_model_identity": None, "actual_generation_id": None,
        "actual_usage": None, "actual_amount": None, "input_tokens": None, "output_tokens": None,
        "reported_monetary_cost_usd": None, "own_zero_receipt_available": False,
        "error": (actual.get("exception_info") or {}).get("exception_message"),
        "source_sha256": snapshot.hashes, "historical_ledger_validated": True,
        "not_a_v28_matrix_score": True, "scope": "A different provider's one actual unknown request; never a NVIDIA proof or semantic false. No individual fee or usage is inferred."}
    return pilots, interrupted, nvidia, openrouter


def openrouter_unknown30(plan, source_hashes, ordinal=30):
    if ordinal not in {30, 31}:
        raise ValueError("Only the two exact retained Ling route probes are supported")
    path = ROOT / f"work/free-recovery{ordinal}-20261125/accepted-unknown{ordinal}.json"
    accepted = read(path)
    if digest(path) != plan["all_files_sha256"][relative(path)]:
        raise ValueError("The exact accepted route evidence changed")
    merge_hashes(source_hashes, accepted["source_sha256"] | {relative(path): digest(path)})
    verify_hashes(accepted["source_sha256"])
    batch = "performance-openrouter-responses-route-probe-20261125" if ordinal == 31 else "performance-openrouter-ling-route-probe-20261125"
    directory = ROOT / "work/vmshare" / batch / "one-call-Ling/agent"
    snapshot = reader.Snapshot(directory)
    trace = snapshot.add(directory / "model.jsonl")
    protocol = snapshot.json(directory / "protocol.json")
    requests, errors, forbidden = [], [], []
    for line in trace.open():
        event = json.loads(line)
        if event["event"] == "request":
            requests.append(event)
        elif event["event"] == "request_error":
            errors.append(event)
        elif event["event"] in {"response", "billing_verified"}:
            forbidden.append(event)
    request, = requests
    error, = errors
    protocol_valid = (protocol["allowed_models"] == [request["payload"]["model"]]
        and protocol["actual_model_request_limit"] == 1 and protocol["wall_seconds_limit"] == 300
        and protocol["output_tokens_limit"] == 512 and protocol["automatic_retries"] == 0
        and protocol["tool_execution"] is False and protocol["original_grading"] is False
        and request["endpoint"] == "https://openrouter.ai/api/v1/responses"
        and request["payload"]["max_output_tokens"] == 512 and request["payload"]["store"] is False
        and request["payload"]["provider"] == {"allow_fallbacks": False, "max_price": {"prompt": 0, "completion": 0}}
        if ordinal == 31 else protocol["model"] == request["payload"]["model"]
        and protocol["actual_model_request_limit"] == 1 and protocol["tool_execution"] is False
        and protocol["paid_fallback"] is False and protocol["limits"]["model_calls"] == 1
        and protocol["limits"]["wall_seconds"] == 300 and protocol["limits"]["max_output_tokens"] == 512
        and protocol["limits"]["timeout_retries"] == 0)
    if (accepted["historical_unknown_ordinal"] != ordinal or accepted["physical_unknown_requests"] != 1
            or accepted["canonical_trace"] != relative(trace) or accepted["request_id"] != 1
            or any(accepted[key] is not None for key in (
                "complete_actual_model_identity", "actual_generation_id", "actual_usage", "actual_amount"))
            or accepted["own_zero_receipt_available"] is not False or forbidden
            or request["request_id"] != 1 or request["attempt"] != 1
            or request["payload"]["model"] != "inclusionai/ling-3.2-flash:free"
            or error != accepted["actual_error"] or error["http_status"] != 400
            or error["response_ids"] or error["billing_status"] != "unknown"
            or json.loads(error["body"]) != {"error": {"message": "Request path cannot be relayed", "code": 400}}
            or not protocol_valid):
        raise ValueError("The unique Ling HTTP400 cannot become a task score, own-zero receipt or known amount")
    snapshot.verify()
    return {"kind": "route_probe", "is_task_position": False, "run_dir": relative(directory),
        "configured_model": request["payload"]["model"], "scoreable": None, "passed": None,
        "original_result": None, "physical_request_count": 1, "complete_own_receipts": 0,
        "unverified_requests": [1], "historical_unknown_ordinal": ordinal,
        "actual_model_identity": None, "actual_generation_id": None, "actual_usage": None,
        "actual_amount": None, "reported_monetary_cost_usd": None, "own_zero_receipt_available": False,
        "error": error, "accepted_evidence": relative(path), "accepted_evidence_sha256": digest(path),
        "source_sha256": snapshot.hashes, "historical_ledger_validated": True,
        "scope": "One nonbenchmark OpenRouter route probe. HTTP400 and aggregate free-account usage do not establish an individual zero-cost receipt. Not a NVIDIA proof, task failure, scored position or performance denominator."}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=BASE / "final-nvidia-v28-summary")
    parser.add_argument("--experiment", choices=("v28", "v29", "v30", "v31", "v32"), default="v28")
    args = parser.parse_args()
    experiment, plan_sha, binding_count = {
        "v28": (EXPERIMENT, PLAN_SHA, 427),
        "v29": (ROOT / "work/nvidia75-resume-v29-20261125", V29_SHA, 541),
        "v30": (ROOT / "work/nvidia75-small-actions-v30-20261125", V30_SHA, 729),
        "v31": (ROOT / "work/nvidia75-idle-alignment-v31-20261125", V31_SHA, 969),
        "v32": (ROOT / "work/nvidia75-parallel-dispatch-v32-20261125", V32_SHA, 1100),
    }[args.experiment]
    current_stratum = ("v31_runtime_v32_parallel_remaining219" if args.experiment == "v32" else
        "v31_sdk_idle_alignment_remaining220" if args.experiment == "v31" else
        "v30_common_guidance_remaining74" if args.experiment == "v30" else "v28_remaining74")
    out = args.out.absolute()
    if (not out.resolve().is_relative_to(BASE) or out.resolve() == BASE or (out / "plan.json").exists()
            or any(path.is_symlink() for path in (out, *out.parents))):
        raise ValueError("Only a separate offline child output directory is permitted")
    out.mkdir(parents=True, exist_ok=True)
    with (out / ".consumer.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        plan_path, parent_path = experiment / "plan.json", ROOT / "work/nvidia75-v27-20261125/plan.json"
        plan, parent = read(plan_path), read(parent_path)
        if digest(plan_path) != plan_sha or digest(parent_path) != PARENT_SHA or len(plan["all_files_sha256"]) != binding_count:
            raise ValueError("The exact selected admitted plan or original v27 plan changed")
        source_hashes = dict(plan["all_files_sha256"])
        merge_hashes(source_hashes, {relative(plan_path): plan_sha, relative(parent_path): PARENT_SHA,
            relative(READER): READER_SHA, relative(Path(__file__)): digest(Path(__file__))})
        for function in (reader.audit_nvidia_events, reader.run_metrics, reader.control_artifact_metrics):
            path = Path(sys.modules[function.__module__].__file__)
            source_hashes[relative(path)] = digest(path)
        verify_hashes(source_hashes)
        old_source = (ROOT / parent["runtime_root"] / "course_eval/nvidia_free.py").read_text()
        expected = old_source.replace("timeout = min(900, available)", "timeout = available").replace(
            "timeout=(min(10, remaining), remaining)", "timeout=(min(10, remaining), min(900, remaining))")
        expected_tree = ast.parse(expected)
        actual_tree = ast.parse((ROOT / plan["runtime_root"] / "course_eval/nvidia_free.py").read_text())
        if args.experiment in {"v30", "v31", "v32"}:
            actual_tree.body = [node for node in actual_tree.body if not (isinstance(node, ast.FunctionDef) and node.name == "with_tool_delivery_guidance")
                and not (isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "TOOL_DELIVERY_GUIDANCE" for target in node.targets))]
            old_class = next(node for node in expected_tree.body if isinstance(node, ast.ClassDef) and node.name == "NvidiaFreeModel")
            new_class = next(node for node in actual_tree.body if isinstance(node, ast.ClassDef) and node.name == "NvidiaFreeModel")
            old_method = next(node for node in old_class.body if isinstance(node, ast.FunctionDef) and node.name == "request_payload")
            new_method = next(node for node in new_class.body if isinstance(node, ast.FunctionDef) and node.name == "request_payload")
            if ast.unparse(new_method) != "def request_payload(self, payload):\n    return self._single_request_payload(with_tool_delivery_guidance(payload))":
                raise ValueError("The common input adapter changed outside its admitted entry")
            new_class.body[new_class.body.index(new_method)] = old_method
        if ast.dump(expected_tree) != ast.dump(actual_tree):
            raise ValueError("Reusing the prior offline proof reader no longer matches the unchanged v28 proof semantics")
        tasks = {task["id"]: task for task in read(ROOT / plan["manifest"])["selected"]}
        v30_path = ROOT / "work/nvidia75-small-actions-v30-20261125/plan.json"
        v30 = read(v30_path) if args.experiment in {"v31", "v32"} else None
        if v30 is not None and digest(v30_path) != V30_SHA:
            raise ValueError("The two inherited ReLU positions lost their exact v30 source plan")
        v31_path = ROOT / "work/nvidia75-idle-alignment-v31-20261125/plan.json"
        v31 = read(v31_path) if args.experiment == "v32" else None
        if v31 is not None and digest(v31_path) != V31_SHA:
            raise ValueError("The inherited DSH ReLU lost its actual v31 source plan")
        expected_lanes = {"main": ("mini-swe", "C0", 1), "dsh": ("dsh", "B0", 1), "repeat": ("mini-swe", "C0", 2)}
        if (len(tasks) != 75 or set(plan["lanes"]) != set(expected_lanes)
                or Counter(task["benchmark"] for task in tasks.values()) != {"aider": 25, "swe": 25, "terminal": 25}):
            raise ValueError("The original75 task union or three lanes changed")
        rows, expected_dirs = [], set()
        for name, lane in plan["lanes"].items():
            original = parent["lanes"][name]
            remaining = [task for task in original["tasks"] if task != "extract-elf"]
            if args.experiment != "v28":
                remaining = remaining[1:] + remaining[:1]
            if args.experiment == "v32" or args.experiment == "v31" and name != "dsh":
                remaining = [task for task in remaining if task != "model-extraction-relu-logits"]
            if ((lane["framework"], lane["configuration"], lane["repetition"]) != expected_lanes[name]
                    or lane["backend"] != "nvidia-free" or lane["model"] != "stepfun-ai/step-5-preview"
                    or len(original["tasks"]) != 75 or set(original["tasks"]) != set(tasks)
                    or lane["tasks"] != remaining):
                raise ValueError("A declared fixed remaining arm or its original task order changed")
            for task_id in original["tasks"]:
                if task_id == "extract-elf":
                    saved = plan["inherited_completed_positions"][name]
                    directory = ROOT / saved["run_dir"]
                    row = consume(directory, parent, PARENT_SHA, original, tasks[task_id], out, name, "v27_inherited_elf")
                    if (not row["record_validated"] or row["original_result"] != saved["actual_result"]
                            or row["control"] != saved["control"] or row["billing"] != saved["billing"]):
                        raise ValueError("An inherited ELF position differs from its exact original plan/protocol/score/control/proof")
                elif args.experiment in {"v31", "v32"} and name != "dsh" and task_id == "model-extraction-relu-logits":
                    saved = plan["additional_inherited_v30_relu_positions"][name]
                    directory = ROOT / saved["run_dir"]
                    row = consume(directory, v30, V30_SHA, v30["lanes"][name], tasks[task_id], out,
                        name, "v30_inherited_scored_relu")
                    if (not row["record_validated"] or row["original_result"] != saved["original_result"]
                            or row["passed"] is not (name == "repeat") or row["scoreable"] is not True
                            or row["qualified_passed"] != saved["qualified_passed"] or row["control"] != saved["control"]
                            or row["billing"] != {key: value for key, value in saved["billing"].items() if key != "generation_ids"}
                            or row["generation_ids"] != saved["billing"]["generation_ids"]):
                        raise ValueError("An inherited true main failure or repeat success was altered or resampled")
                elif args.experiment == "v32" and name == "dsh" and task_id == "model-extraction-relu-logits":
                    saved = plan["additional_inherited_v31_dsh_relu_position"]
                    directory = ROOT / saved["run_dir"]
                    row = consume(directory, v31, V31_SHA, v31["lanes"][name], tasks[task_id], out,
                        name, "v31_inherited_scored_dsh_relu")
                    if (not row["record_validated"] or row["original_result"] != saved["original_result"]
                            or row["passed"] is not True or row["scoreable"] is not True
                            or row["qualified_passed"] != saved["qualified_passed"] or row["control"] != saved["control"]
                            or row["billing"] != {key: value for key, value in saved["billing"].items() if key != "generation_ids"}
                            or row["generation_ids"] != saved["billing"]["generation_ids"]):
                        raise ValueError("The inherited v31DSH grade/protocol/proofs changed")
                else:
                    directory = ROOT / plan["queue"] / name / (task_id.replace("/", "-") + "-" + lane["configuration"] + "-r" + str(lane["repetition"]))
                    expected_dirs.add(directory.resolve())
                    row = consume(directory, plan, plan_sha, lane, tasks[task_id], out, name, current_stratum)
                rows.append(row)
        if len(rows) != 225 or len({row["run_dir"] for row in rows}) != 225:
            raise ValueError("The actual225 physical matrix positions are not unique")
        unexpected = [relative(path) for name in plan["lanes"] for path in (ROOT / plan["queue"] / name).glob("*")
            if path.is_dir() and path.resolve() not in expected_dirs]
        pilots, interrupted, old_nvidia, old_openrouter = historical_views(plan, parent, PARENT_SHA, tasks, out, source_hashes)
        interrupted28 = []
        if args.experiment != "v28":
            accepted_path = ROOT / "work/free-recovery28-20261125/accepted-unknown28.json"
            accepted = read(accepted_path)
            merge_hashes(source_hashes, accepted["source_sha256"] | {relative(accepted_path): digest(accepted_path)})
            prior_plan = read(EXPERIMENT / "plan.json")
            for actual in accepted["interrupted_positions"]:
                name = actual["lane"]
                row = consume(ROOT / actual["run_dir"], prior_plan, PLAN_SHA, prior_plan["lanes"][name],
                    tasks["video-processing"], out, name, "v28_unscored_video_not_a_matrix_score")
                if row["original_result"] != actual["original_result"] or row["scoreable"] is not False or row["passed"] is not None:
                    raise ValueError("The actual retained v28 interruption changed its original classification")
                row["accepted_unknown_requests"] = []
                if name == "main":
                    expected_error = "Closed physical requests lack their own verified proof; these are not automatically accepted historical unknowns"
                    if (row["physical_request_count"] != 20 or row["billing"]["unverified_requests"] != [20]
                            or row["billing"]["verified_nonbilled_service_calls"] != 19
                            or row["validation_errors"] != [expected_error]
                            or accepted["physical_unknown_requests"] != 1 or accepted["request_id"] != 20
                            or accepted["actual_usage"] is not None or accepted["actual_amount"] is not None):
                        raise ValueError("Unknown28 differs from its unique actual incomplete request")
                    row.update(accepted_unknown_requests=[20], historical_unknown_ordinal=28,
                        unknown_actual_model_identity=None, unknown_actual_usage=None, unknown_actual_amount=None,
                        partial_stream_observation=accepted["partial_stream_observation"],
                        known_complete_billing_before_unknown=accepted["preceding_main_complete_billing"])
                elif not row["record_validated"] or row["billing"] != actual["billing"]:
                    raise ValueError("The complete companion v28 proofs differ from accepted evidence")
                row.update(not_a_v28_matrix_score=True, historical_ledger_validated=True)
                interrupted28.append(row)
        interrupted29 = []
        if args.experiment in {"v30", "v31", "v32"}:
            accepted_path = ROOT / "work/free-recovery29-20261125/accepted-unknown29.json"
            accepted = read(accepted_path)
            merge_hashes(source_hashes, accepted["source_sha256"] | {relative(accepted_path): digest(accepted_path)})
            prior_path = ROOT / accepted["actual_plan"]
            prior_plan = read(prior_path)
            if digest(prior_path) != V29_SHA or accepted["actual_plan_sha256"] != V29_SHA:
                raise ValueError("The ReLU interruption lost its real v29 protocol")
            for actual in accepted["interrupted_positions"]:
                name = actual["lane"]
                row = consume(ROOT / actual["run_dir"], prior_plan, V29_SHA, prior_plan["lanes"][name],
                    tasks["model-extraction-relu-logits"], out, name, "v29_unscored_relu_not_a_matrix_score")
                if row["original_result"] != actual["original_result"] or row["scoreable"] is not False or row["passed"] is not None:
                    raise ValueError("The actual retained ReLU interruption changed its original outcome")
                row["accepted_unknown_requests"] = []
                if name == "main":
                    expected_error = "Closed physical requests lack their own verified proof; these are not automatically accepted historical unknowns"
                    if (row["physical_request_count"] != 11 or row["billing"]["unverified_requests"] != [11]
                            or row["billing"]["verified_nonbilled_service_calls"] != 10
                            or row["validation_errors"] != [expected_error]
                            or accepted["historical_unknown_ordinal"] != 29 or accepted["physical_unknown_requests"] != 1
                            or accepted["request_id"] != 11 or accepted["actual_usage"] is not None or accepted["actual_amount"] is not None):
                        raise ValueError("Unknown29 differs from its one actual missing response")
                    row.update(accepted_unknown_requests=[11], historical_unknown_ordinal=29,
                        unknown_actual_model_identity=None, unknown_actual_usage=None, unknown_actual_amount=None,
                        partial_stream_observation=accepted["partial_stream_observation"],
                        known_complete_billing_before_unknown=accepted["preceding_main_complete_billing"])
                elif not row["record_validated"] or row["billing"] != actual["billing"]:
                    raise ValueError("The eight complete companion ReLU proofs or zero-call DSH changed")
                row.update(not_current_matrix_score=True, historical_ledger_validated=True)
                interrupted29.append(row)
        interrupted30, route_probes = [], []
        if args.experiment in {"v31", "v32"}:
            actual = plan["retained_unscored_v30_dsh_interruption"]
            row = consume(ROOT / actual["run_dir"], v30, V30_SHA, v30["lanes"]["dsh"],
                tasks["model-extraction-relu-logits"], out, "dsh", "v30_unscored_dsh_relu_not_a_matrix_score")
            if (not row["record_validated"] or row["original_result"] != actual["original_result"]
                    or row["scoreable"] is not False or row["passed"] is not None
                    or row["billing"] != actual["billing"] or row["physical_request_count"] != 7):
                raise ValueError("The old v30 native interruption or its seven complete proofs changed")
            row.update(not_current_matrix_score=True, historical_ledger_validated=True,
                interruption_kind="native_sdk_idle_before_complete_verified_host_reply")
            interrupted30.append(row)
            route_probes.append(openrouter_unknown30(plan, source_hashes))
            if args.experiment == "v32":
                route_probes.append(openrouter_unknown30(plan, source_hashes, ordinal=31))
        historical = pilots + interrupted + interrupted28 + interrupted29 + interrupted30 + [old_nvidia]
        registry = read(experiment / "prior-generation-registry-snapshot.json")
        seed = read(ROOT / plan["generation_seed"])
        if registry["seed_sha256"] != digest(ROOT / plan["generation_seed"]):
            raise ValueError("The frozen prior registry belongs to a different immutable history")
        identities = identity_audit(rows, historical, seed, registry, plan)
        groups = {name: summary([row for row in rows if row["lane"] == name]) for name in plan["lanes"]}
        by_benchmark = {name: {benchmark: summary([row for row in rows
            if row["lane"] == name and row["benchmark"] == benchmark])
            for benchmark in ("aider", "swe", "terminal")} for name in plan["lanes"]}
        wanted = parent["lanes"]["main"]["tasks"]
        pairs = {}
        for right in ("dsh", "repeat"):
            pairs["main_vs_" + right] = paired(rows, "main", right, wanted) | {
                "by_benchmark": {benchmark: paired(rows, "main", right,
                    [task for task in wanted if tasks[task]["benchmark"] == benchmark])
                    for benchmark in ("aider", "swe", "terminal")}}
        historical_errors = [row["run_dir"] for row in historical if not (
            row.get("record_validated") or row.get("historical_ledger_validated"))]
        invalid = bool(identities["errors"] or unexpected or historical_errors or any(row["validation_errors"] for row in rows))
        complete = not invalid and all(group["validated_original_scored"] == 75 for group in groups.values())
        cost_totals = summary(rows + historical)
        cost_totals.update(performance_comparison_applicable=False, raw_pass_rate_of_original_scored=None,
            qualified_pass_rate_of_validated_scored=None,
            scope="Full retained NVIDIA cost view across versions; original score counts are provenance only, not a pooled performance cohort.")
        for row in rows + historical + [old_openrouter] + route_probes:
            verify_hashes(row["source_sha256"])
        verify_hashes(source_hashes)
        trials = out / "trials.jsonl"
        temporary = trials.with_suffix(".writing")
        with temporary.open("w") as stream:
            for row in rows:
                stream.write(json.dumps(row, ensure_ascii=False) + "\n")
        temporary.replace(trials)
        result = {"schema": "nvidia75_v28_stratified_offline_summary_v1", "observed_utc": datetime.now(timezone.utc).isoformat(),
            "stage": "complete_original225" if complete else "invalid_evidence" if invalid else "partial",
            "all_original225_validated": complete, "plan_path": relative(plan_path), "plan_sha256": plan_sha, "bound_source_count": binding_count,
            "required_positions": 225, "groups": groups, "by_benchmark": by_benchmark,
            "paired_raw_original_scores": pairs, "matrix_totals": summary(rows),
            "transport_strata": {stratum: summary([row for row in rows if row["transport_stratum"] == stratum])
                for stratum in (("v27_inherited_elf", "v30_inherited_scored_relu", "v31_inherited_scored_dsh_relu", current_stratum)
                    if args.experiment == "v32" else ("v27_inherited_elf", "v30_inherited_scored_relu", current_stratum)
                    if args.experiment == "v31" else ("v27_inherited_elf", current_stratum))},
            "identity_audit": identities, "unexpected_position_directories": unexpected,
            "retained_pilots": pilots, "retained_pilot_totals": summary(pilots),
            "retained_unscored_v27_videos": interrupted, "retained_unscored_v27_video_totals": summary(interrupted),
            "retained_unscored_v28_videos": interrupted28, "retained_unscored_v28_video_totals": summary(interrupted28),
            "retained_unscored_v29_relu": interrupted29, "retained_unscored_v29_relu_totals": summary(interrupted29),
            "retained_unscored_v30_dsh_relu": interrupted30, "retained_unscored_v30_dsh_relu_totals": summary(interrupted30),
            "retained_openrouter_route_probes": route_probes,
            "retained_unscored_v25_interruptions": {"nvidia": old_nvidia, "openrouter": old_openrouter},
            "all_consumed_nvidia_cost_positions": cost_totals,
            "cross_service_retained_costs": {"nvidia_physical_requests": cost_totals["actual_closed_requests"],
                "nvidia_complete_policy_proofs": cost_totals["verified_nonbilled_service_calls"],
                "openrouter_physical_requests": old_openrouter["physical_request_count"]
                    + sum(row["physical_request_count"] for row in route_probes),
                "closed_physical_requests": cost_totals["actual_closed_requests"] + old_openrouter["physical_request_count"]
                    + sum(row["physical_request_count"] for row in route_probes),
                "reported_monetary_cost_usd": None,
                "scope": "Only closed attempts explicitly retained in these views, including separate OpenRouter unknowns. No inflight request or usage is consumed; historical unknown ordinals1through25 remain in their preserved acceptance chain, not reconstructed as new physical calls."},
            "historical_ledger_errors": historical_errors, "historical_unknown_calls_in_admitted_plan": plan["historical_unknown_calls"],
            "explicit_unknowns_in_these_retained_cost_views": [26, 27] + ([28] if interrupted28 else [])
                + ([29] if interrupted29 else []) + [row["historical_unknown_ordinal"] for row in route_probes],
            "source_sha256": source_hashes, "trials_path": relative(trials), "trials_sha256": digest(trials),
            "offline_reader": {"path": relative(READER), "sha256": READER_SHA,
                "runtime": "v27 offline proof/metric reader; v28 changes only the two unused network-timeout expressions. Both source versions are bound. Original v27 ELF is consumed with its original plan/protocol, never rewritten as v28."},
            "metric_definitions": {"usage.tool_calls": "Legacy actual tools.jsonl records, not all native functions.",
                "executed_bash_commands": "Recorded mini-swe bash execution only; SDK calls are separate.",
                "native_proposed_function_calls": "Proposals in real provider responses, not proof of execution.",
                "sdk_tool_calls/sdk_tool_results": "Actual observed native session identities across closed DSH positions, including unscored interruptions. Null when inapplicable or any closed DSH session trace is unavailable; observed subtotals and missing-position counts are separate.",
                "sdk_final_summary_available_positions": "Closed positions with an actual sdk_result transport event; distinct from the existence of tool events or an original grader result. An interrupted session can have observed tools and no final summary.",
                "input_tokens/output_tokens": "Null unless every consumed closed request has observed response usage. known_response_usage retains only observed-response totals; inflight requests are never consumed.",
                "zero_denominators": "Pass rates, proof fractions and unavailable complete usage remain null when their denominator/evidence is absent.",
                "inherited_ids": "Only exact trace/request/model self-bindings of the3inherited v27ELF,the2inherited v30scored ReLU and,under v32,the1actual v31DSHReLU may coincide with frozen prior registry entries. New matrix positions may reuse neither seed nor any prior registry ID. Historical cost views retain their own exact claims."},
            "scope": ("Three actual v27ELF,two actual v30miniReLU and one actual v31DSHReLU scores plus219scheduling-only v32positions under unchanged v31runtime. OR unknown30/31route probes and every old interruption remain separate cost views. "
                if args.experiment == "v32" else "Three actual v27ELF positions,two actual scored v30ReLU positions and220fixed v31remaining positions. The old v30DSH null/seven proofs and the OR unknown30route probe are historical cost views,not new matrix scores. "
                if args.experiment == "v31" else "Three original ELF scores under v27 plus222fixed remaining positions. ")
                + "Partial is not complete225. Old pilots,unscored interruptions,raw/qualified grades and unknown fees stay separate. Missing monetary fields remain null. Historical acceptance validates the ledger,never a missing response or fee. Structural/source validation is not word-for-word reasoning review or new original grading.",
            "new_model_calls": 0, "new_original_grader_calls": 0, "vm_commands": 0,
            "stop_modified": False, "original_runs_modified": False}
        reader.write_json(out / "summary.json", result)
        print(json.dumps({"stage": result["stage"], "groups": groups,
            "matrix_requests": result["matrix_totals"]["actual_closed_requests"],
            "identity_audit": identities, "retained_video_known_proofs": result["retained_unscored_v27_video_totals"]["verified_nonbilled_service_calls"],
            "retained_unknowns": result["explicit_unknowns_in_these_retained_cost_views"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
