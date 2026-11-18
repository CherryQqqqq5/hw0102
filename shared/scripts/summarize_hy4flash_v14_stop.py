import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from audit_confirmation_sources import audit_free_billing, audit_stopped_billing, compare_files, same_usage
from course_eval.confirmation_summary import merge_usage
from course_eval.export_revision import HOME_PATH, PRIVATE, SECRET
from course_eval.summarize import read_runs, run_metrics
from course_eval.verify_scores import verify


root = Path("work/vmshare/confirmation-hy4flash-free-v14")
previous = root.with_name(root.name + "-previous")
plan = json.loads(Path("work/confirmation-plan-hy4flash-free-v14.json").read_text())
before = json.loads(Path("work/hy4flash-v14-resume-validation.json").read_text())
protocol = "7c7679a44cc36dc3f6d35525bc57960cbd72aa51"
slots = {slot["run_id"]: slot for slot in plan["slots"]}
rows = read_runs(root)
scored = [row for row in rows if row["scoreable"]]
unscored, = [row for row in rows if not row["scoreable"]]
assert len(rows) == 189 and len(scored) == 188
assert unscored["run_id"] == "C-swe-django__django-11999-B0-r3"
reused = [row for row in scored if slots[row["run_id"]].get("source_batch")]
new = [row for row in scored if row not in reused]
assert len(reused) == 138 and len(new) == 50
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
assert compared == before["evidence_files_compared"] == 2002
for name, expected in plan["runtime_sha256"].items():
    assert hashlib.sha256((Path("work/frozen-runtime-v14/course_eval") / name).read_bytes()).hexdigest() == expected
    assert hashlib.sha256((Path("course_eval") / name).read_bytes()).hexdigest() == expected
completed = [{"run_id": row["run_id"], **audit_free_billing(root / row["run_id"])} for row in scored]
current_billing = audit_stopped_billing(root)
previous_billing = audit_stopped_billing(previous, require_runtime_acceptance=False)
assert current_billing["returned_unverified_responses"] == current_billing["returned_known_zero_local_metadata_rejections"] == 1
assert current_billing["missing_responses"] == current_billing["returned_unknown_responses"] == 0
assert previous_billing["missing_responses"] == 9 and previous_billing["returned_unknown_responses"] == 1
usage = merge_usage([run_metrics(root), run_metrics(previous)])
new_usage = merge_usage([run_metrics(root / row["run_id"]) for row in new + [unscored]])
same_usage(usage, merge_usage([before["all_free_formal_usage_before_resume"], new_usage]))
diagnostic = json.loads(Path("work/codebuddy-local-result-v14/diagnostic.json").read_text())
assert diagnostic["native_requests_with_unmatched_usage"] == 0
arm_scores = {arm: {"scored": sum(row["arm"] == arm for row in scored),
    "passed": sum(row["arm"] == arm and row["passed"] for row in scored)} for arm in ("B0", "C0", "C1")}
result = {
    "status": "stopped_local_tool_result_identity_rejection_actual_native_fees_verified_zero",
    "recorded_utc": datetime.now(timezone.utc).isoformat(), "batch": root.name, "protocol_commit": protocol,
    "planned_primary_positions": 270, "started_positions": len(rows), "valid_original_scores": len(scored),
    "passed": sum(row["passed"] for row in scored), "failed": sum(not row["passed"] for row in scored),
    "new_scored_positions": len(new), "remaining_scores": 270 - len(scored),
    "unscored_positions": [unscored["run_id"]], "unstarted_positions": 270 - len(rows),
    "arm_scores": arm_scores, "old_unknown_cli_requests": 12, "new_unknown_cli_requests": 0,
    "total_unknown_cli_requests": 12, "formal_missing_receipts": 9,
    "formal_returned_unverified_requests": 2, "formal_returned_unknown_requests": 1,
    "formal_known_zero_local_metadata_rejections": 1, "historical_preparation_missing_receipts": 2,
    "failure": diagnostic, "current_billing": current_billing, "previous_billing": previous_billing,
    "completed_position_billing": completed, "all_free_formal_attempt_usage": usage,
    "new_continuation_usage": new_usage,
    "preparation_validation": json.loads(Path("work/codebuddy-empty-stream-probe-v14/summary.json").read_text()),
    "source_partitions_match": True, "preserved_evidence_files_compared": compared,
    "original_score_verification": verify(root, allow_unscored=True),
    "previous_original_score_verification": verify(previous, allow_unscored=True),
    "frozen_runtime_matches_plan": True, "frozen_runtime": "frozen-runtime/v14/course_eval",
    "fee_validator_unchanged": True, "local_metadata_repair_live_validated": False,
    "local_metadata_repair_validation": json.loads(Path("work/codebuddy-local-result-v14/validation.json").read_text()),
    "primary_result_ready": False, "complete_report_generated": False, "new_model_requests_after_stop": 0,
    "billing_boundary": "The new local-result metadata rejection remains unscored and raw response rejected. Both actual native requests have their own verified zero-credit identity/usage. Old twelve true unknown requests remain unknown; no model call was made for diagnosis or repair.",
}
assert result["passed"] == 148 and result["failed"] == 40
content = HOME_PATH.sub("[本机路径]", json.dumps(result, ensure_ascii=False, indent=2)) + "\n"
assert not SECRET.search(content) and not PRIVATE.search(content)
Path("work/hy4flash-v14-stopped-summary.json").write_text(content)
print(json.dumps({key: result[key] for key in ("status", "valid_original_scores", "passed", "failed", "remaining_scores",
    "total_unknown_cli_requests", "formal_known_zero_local_metadata_rejections", "preserved_evidence_files_compared", "arm_scores")}, ensure_ascii=False))
