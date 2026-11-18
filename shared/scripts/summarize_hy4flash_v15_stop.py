import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from statistics import median

from audit_confirmation_sources import audit_free_billing, audit_free_recovery_preparation, audit_stopped_billing, compare_files, same_usage
from course_eval.confirmation_summary import mechanism, merge_usage
from course_eval.export_revision import HOME_PATH, PRIVATE, SECRET
from course_eval.summarize import read_runs, run_metrics
from course_eval.verify_scores import verify


root = Path("work/vmshare/confirmation-hy4flash-free-v15")
previous = root.with_name(root.name + "-previous")
plan = json.loads(Path("work/confirmation-plan-hy4flash-free-v15.json").read_text())
before = json.loads(Path("work/hy4flash-v15-resume-validation.json").read_text())
protocol = "081a796c7bceca10e390fa983c18173289c4fe7a"
slots = {slot["run_id"]: slot for slot in plan["slots"]}
rows = read_runs(root)
scored = [row for row in rows if row["scoreable"]]
unscored, = [row for row in rows if not row["scoreable"]]
assert len(rows) == 261 and len(scored) == 260
assert unscored["run_id"] == "C-swe-pydata__xarray-4687-B0-r3"
reused = [row for row in scored if slots[row["run_id"]].get("source_batch")]
new = [row for row in scored if row not in reused]
assert len(reused) == 188 and len(new) == 72
compared = 0
for row in rows:
    trial = json.loads((root / row["run_id"] / "trial.json").read_text())
    slot = slots[row["run_id"]]
    assert trial["protocol_commit"] == slot.get("source_protocol_commit", protocol)
    assert all(trial[key] == plan[key] for key in ("model", "backend", "limits"))
    if row in reused:
        compared += compare_files(root.parent / slot["source_batch"] / row["run_id"], root / row["run_id"])
for item in plan["preserved_previous_attempts"]:
    compared += compare_files(root.parent / item["source_batch"] / item["source_run_id"], previous / item["preserved_run_id"])
assert compared == before["evidence_files_compared"] == 2677
for name, expected in plan["runtime_sha256"].items():
    assert hashlib.sha256((Path("work/frozen-runtime-v15/course_eval") / name).read_bytes()).hexdigest() == expected
    assert hashlib.sha256((Path("course_eval") / name).read_bytes()).hexdigest() == expected
client = Path("work/codebuddy/node_modules/@tencent-ai/codebuddy-code/dist/codebuddy-headless.js")
assert hashlib.sha256(client.read_bytes()).hexdigest() == plan["codebuddy_headless_sha256"]
completed = [{"run_id": row["run_id"], **audit_free_billing(root / row["run_id"])} for row in scored]
current_billing = audit_stopped_billing(root)
previous_billing = audit_stopped_billing(previous, require_runtime_acceptance=False)
assert current_billing["missing_responses"] == current_billing["total_unknown_cli_requests"] == 1
assert current_billing["returned_unverified_responses"] == 0
assert previous_billing["missing_responses"] == 9
assert previous_billing["returned_unknown_responses"] == 1
assert previous_billing["returned_known_zero_local_metadata_rejections"] == 1
assert previous_billing["total_unknown_cli_requests"] == 10
preparation = audit_free_recovery_preparation(Path("work/codebuddy-quota-probe"), Path("work/vmshare/hy4flash-interface-v1"))
assert preparation["missing_responses"] == 2
usage = merge_usage([run_metrics(root), run_metrics(previous)])
new_usage = merge_usage([run_metrics(root / row["run_id"]) for row in new + [unscored]])
same_usage(usage, merge_usage([before["all_free_formal_usage_before_resume"], new_usage]))
failed_dir = root / unscored["run_id"]
events = [json.loads(line) for line in (failed_dir / "model.jsonl").read_text().splitlines()]
error, = [event for event in events if event["event"] == "request_error"]
assert error["request_id"] == 24 and error["stdout"] == error["stderr"] == ""
request = next(event for event in events if event["event"] == "request" and event["request_id"] == 24)
child = next(event for event in events if event["event"] == "cli_process_started" and event["request_id"] == 24)
diag = error["provider_diagnostics"]
assert diag["model_requests_sent"] == 1 and diag["completed_streams"] == diag["first_raw_chunks"] == 0
assert diag["truncation_retries"] == diag["structured_output_retries"] == diag["retry_notices"] == 0
sent = {event["request_id"]: event for event in events if event["event"] == "request"}
returned = {event["request_id"]: event for event in events if event["event"] == "response"}
assert len(sent) == 24 and len(returned) == 23
latencies = [event["time"] - sent[key]["time"] for key, event in returned.items()]
stamp = datetime.fromtimestamp(child["time"], timezone.utc)
log = Path.home() / ".codebuddy/logs" / stamp.strftime("%Y-%m-%d") / diag["log_name"]
stage_events = []
for index, line in enumerate(log.read_text().splitlines(), 1):
    if f"[pid={diag['cli_pid']}]" not in line or not line.startswith("["):
        continue
    for kind, marker in (("request_sent", "Sending request:"), ("event_loop_alive", "[WorkflowMemProbe] tick")):
        if marker in line:
            stage_events.append({"source_line": index, "event": kind,
                                 "timestamp": line.split("]", 1)[0].removeprefix("[")})
diagnostic = {
    "source_run_id": unscored["run_id"], "request_id": 24, "cli_pid": diag["cli_pid"],
    "configured_model": plan["model"], "actual_provider_model": None, "actual_provider_credit": None,
    "failure_category": "first_response_wait_exceeded_remaining_execution_window",
    "request_time_unix": request["time"], "error_time_unix": error["time"],
    "effective_request_timeout_seconds": error["timeout_seconds"],
    "request_window_floor_seconds": 60, "execution_limit_seconds": 600,
    "previous_complete_cli_responses": len(returned), "last_complete_request_id": max(returned),
    "previous_cli_latency_median_seconds": median(latencies), "previous_cli_latency_max_seconds": max(latencies),
    "stdout_bytes": 0, "stderr_bytes": 0, "provider_diagnostics": diag, "stage_events": stage_events,
    "confirmed_observation": "The 24th CLI request was admitted with 73.08 seconds remaining; one native request was sent, the event loop stayed alive, no first chunk or actual usage arrived, and the outer 600-second deadline killed the client",
    "causal_limit": "Client records locate asynchronous waiting before the first response; they do not identify upstream queuing versus network latency or prove the missing fee is zero",
    "official_usage_contract": "https://www.codebuddy.cn/docs/cli/stream-json-turn-usage",
    "receipt_query_boundary": "CLI help exposes no supported per-request invoice query. Official stage usage reports unknown when cancellation precedes any completed model call; aggregate quota is not a replacement receipt",
    "new_model_requests_in_diagnosis_or_after_stop": 0,
}
diagnostic_path = Path("work/codebuddy-first-response-v15/diagnostic.json")
diagnostic_path.parent.mkdir(exist_ok=True)
diagnostic_path.write_text(json.dumps(diagnostic, ensure_ascii=False, indent=2) + "\n")
for row in scored:
    row.update(mechanism(root / row["run_id"]))
arm_scores = {}
for arm in ("B0", "C0", "C1"):
    selected = [row for row in scored if row["arm"] == arm]
    arm_scores[arm] = {
        "scored": len(selected), "passed": sum(row["passed"] for row in selected),
        "failed": sum(not row["passed"] for row in selected),
        "valid_final_verification": sum(row["valid_final_verification"] is True for row in selected),
        "public_valid_original_failed": sum(row["valid_final_verification"] is True and not row["passed"] for row in selected),
        "public_invalid_original_passed": sum(row["valid_final_verification"] is False and row["passed"] for row in selected),
        "repair_chain_and_original_passed": sum(row["changed_candidate_repair_chains"] > 0 and row["passed"] for row in selected),
        "restored_final_candidate": sum(row["restored_final_candidate"] for row in selected),
        "failed_original_by_exit_status": dict(Counter(row["exit_status"] for row in selected if not row["passed"])),
        "original_passed_without_submission": sum(row["passed"] and row["exit_status"] != "Submitted" for row in selected),
    }
unstarted = [slot["run_id"] for slot in plan["slots"] if slot["run_id"] not in {row["run_id"] for row in rows}]
result = {
    "status": "stopped_new_unknown_fee_before_first_response", "recorded_utc": datetime.now(timezone.utc).isoformat(),
    "batch": root.name, "protocol_commit": protocol, "planned_primary_positions": 270,
    "started_positions": len(rows), "valid_original_scores": len(scored),
    "passed": sum(row["passed"] for row in scored), "failed": sum(not row["passed"] for row in scored),
    "new_scored_positions": len(new), "remaining_scores": 270 - len(scored),
    "unscored_positions": [unscored["run_id"]], "unstarted_positions": unstarted,
    "arm_scores": arm_scores, "old_unknown_cli_requests": 12, "new_unknown_cli_requests": 1,
    "total_unknown_cli_requests": 13, "formal_missing_receipts": 10,
    "formal_returned_unverified_requests": 2, "formal_returned_unknown_requests": 1,
    "formal_known_zero_local_metadata_rejections": 1, "historical_preparation_missing_receipts": 2,
    "failure": diagnostic, "current_billing": current_billing, "previous_billing": previous_billing,
    "completed_position_billing": completed, "all_free_formal_attempt_usage": usage,
    "new_continuation_usage": new_usage, "all_free_preparation": preparation,
    "source_partitions_match": True, "preserved_evidence_files_compared": compared,
    "original_score_verification": verify(root, allow_unscored=True),
    "previous_original_score_verification": verify(previous, allow_unscored=True),
    "frozen_runtime_matches_plan": True, "frozen_runtime": "frozen-runtime/v15/course_eval",
    "fee_validator_unchanged": True,
    "local_metadata_repair_live_validation": json.loads(Path("work/codebuddy-local-result-v14/live-validation-v15.json").read_text()),
    "primary_result_ready": False, "complete_report_generated": False, "new_model_requests_after_stop": 0,
    "billing_boundary": "Ten formal missing receipts, one returned true unknown and two preparation missing receipts remain unknown. One separate local metadata rejection has complete own zero-credit native receipts and remains unscored; it does not settle any unknown request",
    "score_scope": "260 saved independent original grades; incomplete arm denominators do not form the frozen 270-position primary comparison",
}
assert result["passed"] == 202 and result["failed"] == 58 and len(unstarted) == 9
assert current_billing["total_unknown_cli_requests"] + previous_billing["total_unknown_cli_requests"] + preparation["missing_responses"] == 13
content = HOME_PATH.sub("[本机路径]", json.dumps(result, ensure_ascii=False, indent=2)) + "\n"
assert not SECRET.search(content) and not PRIVATE.search(content)
Path("work/hy4flash-v15-stopped-summary.json").write_text(content)
Path("work/hy4flash-v15-scored-trials.json").write_text(json.dumps(scored, ensure_ascii=False, indent=2) + "\n")
print(json.dumps({key: result[key] for key in ("status", "valid_original_scores", "passed", "failed", "remaining_scores",
    "total_unknown_cli_requests", "preserved_evidence_files_compared", "arm_scores", "current_billing", "previous_billing")}, ensure_ascii=False))
