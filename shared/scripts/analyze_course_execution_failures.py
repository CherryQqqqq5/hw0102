import argparse
import json
from pathlib import Path
from statistics import median

from jsonschema import Draft202012Validator
from pydantic import ValidationError

from course_eval.controller import ControlAction


parser = argparse.ArgumentParser()
parser.add_argument("--evidence-root", type=Path, default=Path("work/hw0102-publish/作业二/evidence"))
parser.add_argument("--output", type=Path, default=Path("work/course-execution-failure-analysis-20261118.json"))
args = parser.parse_args()
ROOT = args.evidence_root
BATCH = "confirmation-hy4flash-free-v16"
rows = json.loads((ROOT / (BATCH + "-summary") / "trials.json").read_text())
assert len(rows) == 270 and sum(row["passed"] for row in rows) == 207
details = []
aggregates = []
contract_mismatches = []
empty_feedback = []
case_records = []
for row in rows:
    directory = ROOT / BATCH / row["run_id"]
    sources = list(directory.rglob("model.jsonl"))
    assert len(sources) == 1
    events = [json.loads(line) for line in sources[0].read_text().splitlines()]
    responses = [event for event in events if event["event"] == "response"]
    requests = {event["request_id"]: event for event in events if event["event"] == "request"}
    for request in requests.values():
        last = request["history"][-1]
        if last.get("role") == "user" and last.get("content") in (
            "Public verification of the changed candidate: []",
            "Final verification phase: repair these public failures within the remaining budget. []"):
            empty_feedback.append({"run_id": row["run_id"], "request_id": request["request_id"], "content": last["content"]})
    for response in responses:
        request = requests[response["request_id"]]
        for event in response["payload"]:
            action = event.get("structured_output") if event.get("type") == "result" else None
            if (isinstance(action, dict) and action.get("operation") == "submit"
                    and any(action.get(key) is not None for key in ("command", "check_id", "candidate_id"))):
                try:
                    ControlAction.model_validate(action)
                except ValidationError as error:
                    local_error = str(error)
                else:
                    raise ValueError("The recorded submit action is not rejected by the current local contract")
                followup = requests.get(response["request_id"] + 1)
                if followup:
                    assert followup["history"][:len(request["history"])] == request["history"]
                added = followup["history"][len(request["history"]):] if followup else []
                wrong_fields = [key for key in ("command", "check_id", "candidate_id") if action.get(key) is not None]
                native_usage = [item["providerData"]["rawUsage"] for item in response["payload"]
                                if "rawUsage" in item.get("providerData", {})]
                contract_mismatches.append({"run_id": row["run_id"], "request_id": response["request_id"],
                    "sent_schema_accepts": Draft202012Validator(request["schema"]).is_valid(action),
                    "local_validator_error": local_error, "action": action,
                    "next_request_exists": followup is not None,
                    "last_native_output_tokens": native_usage[-1]["completion_tokens"],
                    "next_request_added_messages": added,
                    "followup_local_rejection_feedback": any(
                        message.get("role") == "user" and "Invalid structured output" in str(message.get("content", ""))
                        and any(f"{key} is not valid for submit" in str(message.get("content", "")) for key in wrong_fields)
                        for message in added)})
    usages = [event["providerData"]["rawUsage"] for response in responses for event in response["payload"]
              if "rawUsage" in event.get("providerData", {})]
    usage_by_response = [[event["providerData"]["rawUsage"] for event in response["payload"]
                          if "rawUsage" in event.get("providerData", {})] for response in responses]
    exhausted_tail = len(responses) >= 3 and all(
        len(group) == 1 and group[0]["completion_tokens"] == 4096
        and group[0].get("completion_tokens_details", {}).get("reasoning_tokens") == 4096
        and not any(event.get("type") == "function_call" for event in response["payload"])
        for response, group in zip(responses[-3:], usage_by_response[-3:], strict=True))
    exhausted_last_segments = len(responses) >= 3 and all(
        group and group[-1]["completion_tokens"] == 4096
        and group[-1].get("completion_tokens_details", {}).get("reasoning_tokens") == 4096
        and not any(event.get("type") == "function_call" for event in response["payload"])
        for response, group in zip(responses[-3:], usage_by_response[-3:], strict=True))
    aggregates.append(row | {"native_usage_records": len(usages),
        "native_output_tokens": sum(item["completion_tokens"] for item in usages),
        "native_reasoning_tokens": sum(item.get("completion_tokens_details", {}).get("reasoning_tokens", 0) for item in usages),
        "recovered_actions": sum(event["event"] == "truncation_recovered" for event in events)})
    if row["task"] == "polyglot-rust-c" and row["arm"] == "B0" and row["repeat"] in (1, 2):
        case_records.append({"run_id": row["run_id"], "passed": row["passed"], "protocol_commit": row["protocol_commit"],
            "requests": [{"request_id": response["request_id"],
                "native_output_tokens": [item["completion_tokens"] for item in group],
                "native_reasoning_tokens": [item.get("completion_tokens_details", {}).get("reasoning_tokens") for item in group],
                "history_roles": [message["role"] for message in requests[response["request_id"]]["history"]],
                "history_has_reasoning_content": any("reasoning_content" in message for message in requests[response["request_id"]]["history"])}
                for response, group in zip(responses, usage_by_response, strict=True)],
            "recovered_action_request_ids": [event["request_id"] for event in events if event["event"] == "truncation_recovered"]})
    if row["exit_status"] == "RepeatedFormatError":
        details.append({"run_id": row["run_id"], "arm": row["arm"], "repeat": row["repeat"], "passed": row["passed"],
            "last_three_single_native_reasoning_only_4096_without_action": exhausted_tail,
            "last_three_final_native_segments_reasoning_only_4096_without_action": exhausted_last_segments,
            "last_three_request_ids": [event["request_id"] for event in responses[-3:]],
            "last_three_native_output_tokens": [[item["completion_tokens"] for item in group] for group in usage_by_response[-3:]],
            "last_three_native_reasoning_tokens": [[item.get("completion_tokens_details", {}).get("reasoning_tokens") for item in group]
                                                    for group in usage_by_response[-3:]],
            "source": sources[0].relative_to(ROOT).as_posix()})
aggregates_for_round = []
for repeat in (1, 2, 3):
    for arm in ("B0", "C0", "C1"):
        selected = [row for row in aggregates if row["repeat"] == repeat and row["arm"] == arm]
        assert len(selected) == 30
        entry = {"repeat": repeat, "arm": arm, "trials": 30, "passed": sum(row["passed"] for row in selected),
            "format_exits": sum(row["exit_status"] == "RepeatedFormatError" for row in selected)}
        for key in ("model_calls", "model_responses", "input_tokens", "output_tokens", "native_usage_records",
                    "native_output_tokens", "native_reasoning_tokens", "recovered_actions"):
            entry[key] = sum(row[key] for row in selected)
        aggregates_for_round.append(entry)
result = {"source_batch": BATCH, "original_scores": 270, "original_passed": 207,
    "original_failed": 63, "format_exit_runs": len(details), "format_exit_and_original_failed": sum(not row["passed"] for row in details),
    "reasoning_only_4096_tail_and_original_failed": sum(not row["passed"] and row["last_three_single_native_reasoning_only_4096_without_action"] for row in details),
    "last_native_reasoning_only_4096_tail_and_original_failed": sum(not row["passed"] and row["last_three_final_native_segments_reasoning_only_4096_without_action"] for row in details),
    "rounds": aggregates_for_round, "format_failure_details": details,
    "real_submit_schema_mismatches": contract_mismatches, "real_empty_feedback_requests": empty_feedback,
    "polyglot_cross_version_cases": case_records,
    "new_model_requests": 0, "new_original_grader_executions": 0}
assert result["format_exit_runs"] == 52 and result["format_exit_and_original_failed"] == 48
index = {(row["task"], row["arm"], row["repeat"]): row for row in rows}
result["protocol_matched_descriptive_pairs"] = []
for reference, treatment in (("B0", "C1"), ("C0", "C1"), ("B0", "C0")):
    pairs = [(row, index[row["task"], treatment, row["repeat"]]) for row in rows if row["arm"] == reference]
    matched = [(first, second) for first, second in pairs if first["protocol_commit"] == second["protocol_commit"]]
    result["protocol_matched_descriptive_pairs"].append({"reference": reference, "treatment": treatment,
        "task_repeat_pairs": len(matched), "reference_passed": sum(first["passed"] for first, second in matched),
        "treatment_passed": sum(second["passed"] for first, second in matched),
        "interpretation": "Post-hoc source-protocol match only; subset composition varies, not a new causal experiment"})
result["submit_conflict_evidence"] = {
    "responses": len(contract_mismatches), "runs": len({item["run_id"] for item in contract_mismatches}),
    "immediate_next_request_added_rejection": sum(item["followup_local_rejection_feedback"] for item in contract_mismatches),
    "no_next_request": sum(not item["next_request_exists"] for item in contract_mismatches),
    "last_native_output_at_cap": sum(item["last_native_output_tokens"] == 4096 for item in contract_mismatches)}
assert result["submit_conflict_evidence"] == {"responses": 71, "runs": 60,
    "immediate_next_request_added_rejection": 68, "no_next_request": 3, "last_native_output_at_cap": 0}
groups = {}
for row in rows:
    if row["arm"] != "B0":
        continue
    triple = [index[row["task"], arm, row["repeat"]] for arm in ("B0", "C0", "C1")]
    if len({item["protocol_commit"] for item in triple}) != 1:
        continue
    groups.setdefault((row["protocol_commit"], row["repeat"]), []).append(triple)
result["same_protocol_complete_triples"] = []
for (protocol, repeat), triples in sorted(groups.items(), key=lambda item: (item[0][1], item[0][0])):
    selection = {"protocol_commit": protocol, "repeat": repeat, "tasks": len(triples),
                 "benchmarks": {name: sum(triple[0]["benchmark"] == name for triple in triples)
                                for name in ("aider", "swe", "terminal")}, "arms": {},
                 "task_ids": sorted(triple[0]["task"] for triple in triples)}
    for number, arm in enumerate(("B0", "C0", "C1")):
        selected = [triple[number] for triple in triples]
        selection["arms"][arm] = {"trials": len(selected), "passed": sum(item["passed"] for item in selected),
            "model_calls": sum(item["model_calls"] for item in selected),
            "output_tokens": sum(item["output_tokens"] for item in selected),
            "median_execution_seconds": median(item["execution_seconds"] for item in selected),
            "format_exits": sum(item["exit_status"] == "RepeatedFormatError" for item in selected),
            "run_ids": [item["run_id"] for item in selected]}
    result["same_protocol_complete_triples"].append(selection)
assert len(result["same_protocol_complete_triples"]) == 9
largest = next(item for item in result["same_protocol_complete_triples"]
               if item["protocol_commit"].startswith("081a796c") and item["repeat"] == 3)
assert largest["tasks"] == 23 and [largest["arms"][arm]["passed"] for arm in ("B0", "C0", "C1")] == [18, 19, 17]
result["grouping_rule"] = "Post-hoc: retain every task-repeat with all three arms and identical protocol_commit, group by protocol and repeat; no score filter"
output = args.output
output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
print(json.dumps({key: value for key, value in result.items() if key not in
    ("format_failure_details", "real_submit_schema_mismatches", "real_empty_feedback_requests", "polyglot_cross_version_cases", "same_protocol_complete_triples")}
    | {"submit_schema_mismatch_responses": len(contract_mismatches), "empty_feedback_requests": len(empty_feedback)}, ensure_ascii=False))
