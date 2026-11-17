import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from audit_confirmation_sources import audit_free_billing, audit_stopped_billing, compare_files, same_usage
from course_eval.confirmation_summary import merge_usage
from course_eval.export_revision import HOME_PATH, PRIVATE, SECRET
from course_eval.summarize import read_runs, run_metrics
from course_eval.verify_scores import verify


root = Path("work/vmshare/confirmation-hy4flash-free-v13")
previous = root.with_name(root.name + "-previous")
plan = json.loads(Path("work/confirmation-plan-hy4flash-free-v13.json").read_text())
before = json.loads(Path("work/hy4flash-v13-resume-validation.json").read_text())
protocol = "abad82197a3b7833478261a0360f2eae873efdaa"
slots = {slot["run_id"]: slot for slot in plan["slots"]}
rows = read_runs(root)
scored = [row for row in rows if row["scoreable"]]
unscored, = [row for row in rows if not row["scoreable"]]
assert len(rows) == 139 and len(scored) == 138
assert unscored["run_id"] == "C-aider-javascript__house-C1-r2"
reused = [row for row in scored if slots[row["run_id"]].get("source_batch")]
new = [row for row in scored if row not in reused]
assert len(reused) == 95 and len(new) == 43
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
assert compared == 1434
for name, expected in plan["runtime_sha256"].items():
    assert hashlib.sha256((Path("work/frozen-runtime-v13/course_eval") / name).read_bytes()).hexdigest() == expected, name
assert hashlib.sha256(Path("course_eval/codebuddy_free.py").read_bytes()).hexdigest() == plan["runtime_sha256"]["codebuddy_free.py"]
completed = [{"run_id": row["run_id"], **audit_free_billing(root / row["run_id"])} for row in scored]
current_billing = audit_stopped_billing(root)
previous_billing = audit_free_billing(previous, require_runtime_acceptance=False)
assert current_billing["missing_responses"] == 0 and current_billing["returned_unverified_responses"] == 1
assert previous_billing["missing_responses"] == 9
usage = merge_usage([run_metrics(root), run_metrics(previous)])
new_usage = merge_usage([run_metrics(root / row["run_id"]) for row in new + [unscored]])
same_usage(usage, merge_usage([before["all_free_formal_usage_before_resume"], new_usage]))
events = [json.loads(line) for line in (root / unscored["run_id"] / "model.jsonl").read_text().splitlines()]
error, = [event for event in events if event["event"] == "billing_error"]
request, = [event for event in events if event["event"] == "request" and event["request_id"] == 7]
assert error["request_id"] == 7
diagnostic = json.loads(Path("work/codebuddy-empty-stream-v13/diagnostic.json").read_text())
probe_root = Path("work/codebuddy-stdout-probe-v13")
probe = audit_free_billing(probe_root)
assert probe["requests"] == probe["responses"] == 1
arm_scores = {arm: {"scored": sum(row["arm"] == arm for row in scored),
    "passed": sum(row["arm"] == arm and row["passed"] for row in scored)} for arm in ("B0", "C0", "C1")}
result = {
    "status": "stopped_new_unknown_native_fee_after_internal_empty_stream_retry",
    "recorded_utc": datetime.now(timezone.utc).isoformat(), "batch": root.name, "protocol_commit": protocol,
    "planned_primary_positions": 270, "started_positions": len(rows), "valid_original_scores": len(scored),
    "passed": sum(row["passed"] for row in scored), "failed": sum(not row["passed"] for row in scored),
    "new_scored_positions": len(new), "remaining_scores": 270 - len(scored),
    "unscored_positions": [unscored["run_id"]], "unstarted_positions": 270 - len(rows),
    "arm_scores": arm_scores, "old_unknown_cli_requests": 11, "new_unknown_cli_requests": 1,
    "total_unknown_cli_requests": 12, "formal_missing_receipts": 9,
    "formal_returned_unverified_requests": 1, "historical_preparation_missing_receipts": 2,
    "failure": {"run_id": unscored["run_id"], "request_id": 7,
        "failure_category": "first_native_empty_stream_without_own_billing_receipt",
        "provider_diagnostics": diagnostic["provider_diagnostics"],
        "request_time_unix": request["time"], "error_time_unix": error["time"],
        "wall_clock_request_seconds": error["time"] - request["time"],
        "actual_model_credit": None, "original_score": None,
        "actual_current_terminal_event_present": True,
        "later_known_model_credit": 0,
        "confirmed_observation": "First native attempt ended with reasoning-only finish_reason=error at 92 seconds; SDK internally retried; only later native attempt has actual zero-credit receipt",
        "causal_scope": "SDK stream recovery bypassed ordinary zero-retry configuration; upstream internal error cause and first native fee remain unknown"},
    "current_billing": current_billing, "previous_billing": previous_billing,
    "completed_position_billing": completed, "all_free_formal_attempt_usage": usage,
    "new_continuation_usage": new_usage, "preparation_billing": probe,
    "preparation_validation": json.loads((probe_root / "summary.json").read_text()),
    "new_cli_requests_this_continuation": new_usage["model_calls"] + 1,
    "new_returned_verified_zero_credit_responses": new_usage["model_responses"] - current_billing["returned_unverified_responses"] + probe["responses"],
    "source_partitions_match": True, "preserved_evidence_files_compared": compared,
    "original_score_verification": verify(root, allow_unscored=True),
    "previous_original_score_verification": verify(previous, allow_unscored=True),
    "frozen_runtime_matches_plan": True, "frozen_runtime": "frozen-runtime/v13/course_eval",
    "fee_validator_unchanged": True, "stdout_repair_live_validated": True,
    "empty_stream_repair_validation": json.loads(Path("work/codebuddy-empty-stream-v13/recovery-validation.json").read_text()),
    "empty_stream_repair_live_validated": False,
    "primary_result_ready": False, "complete_report_generated": False, "new_model_requests_after_stop": 0,
    "billing_boundary": "Nine old formal missing responses, one new returned-unverified native attempt, and two old preparation missing responses remain unknown; later zero credit cannot settle earlier unknown fee",
}
assert result["passed"] == 115 and result["failed"] == 23
content = HOME_PATH.sub("[本机路径]", json.dumps(result, ensure_ascii=False, indent=2)) + "\n"
assert not SECRET.search(content) and not PRIVATE.search(content)
Path("work/hy4flash-v13-stopped-summary.json").write_text(content)
print(json.dumps({key: result[key] for key in ("status", "valid_original_scores", "passed", "failed", "remaining_scores",
    "new_cli_requests_this_continuation", "total_unknown_cli_requests", "preserved_evidence_files_compared",
    "current_billing", "previous_billing", "arm_scores")}, ensure_ascii=False))
