import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from audit_confirmation_sources import audit_free_billing, compare_files, same_usage
from course_eval.agent import CodeBuddyModel
from course_eval.confirmation_summary import merge_usage
from course_eval.export_revision import HOME_PATH, PRIVATE, SECRET
from course_eval.summarize import read_runs, run_metrics
from course_eval.verify_scores import verify


root = Path("work/vmshare/confirmation-hy4flash-free-v10")
previous = root.with_name(root.name + "-previous")
plan = json.loads(Path("work/confirmation-plan-hy4flash-free-v10.json").read_text())
before = json.loads(Path("work/hy4flash-v10-resume-validation.json").read_text())
old = json.loads(Path("work/hy4flash-v8-stopped-summary.json").read_text())
probe_root = Path("work/codebuddy-single-turn-probe-v10")
probe = json.loads((probe_root / "summary.json").read_text())
protocol = "8e158f5d9e1e574a5e3c53277a77a4c458ffe8e5"
slots = {slot["run_id"]: slot for slot in plan["slots"]}
rows = read_runs(root)
scored = [row for row in rows if row["scoreable"]]
failed, = [row for row in rows if not row["scoreable"]]
assert len(rows) == 91 and len(scored) == 90
assert failed["run_id"] == "C-terminal-feal-linear-cryptanalysis-C0-r2"
assert all(row["run_id"].endswith("-r1") for row in scored)
log, = (root / failed["run_id"]).rglob("model.jsonl")
events = [json.loads(line) for line in log.read_text().splitlines()]
error, = [event for event in events if event["event"] == "request_error"]
request, = [event for event in events if event["event"] == "request" and event["request_id"] == 2]
child, = [event for event in events if event["event"] == "cli_process_started" and event["request_id"] == 2]
assert error["request_id"] == 2 and error["failure_category"] == "local_cli_turn_limit_without_receipt"
assert error["stdout"] == "" and error["stderr"] == "Max turns (1) exceeded\n"
assert error["billing_status"] == "unknown"
stamp = datetime.fromtimestamp(child["time"]).astimezone()
run = log.parent.resolve()
sdk_log = Path.home() / ".codebuddy/logs" / stamp.strftime("%Y-%m-%d") / (
    run.name + "__" + hashlib.md5(str(run).encode()).hexdigest() + ".log")
pid = child["provider_diagnostics"]["cli_pid"]
diagnostic = CodeBuddyModel.inspect_cli_log(sdk_log, pid)
assert diagnostic["model_requests_sent"] == diagnostic["first_raw_chunks"] == 1
assert diagnostic["truncation_retries"] == diagnostic["structured_output_retries"] == 0
causal_lines = [{"line": index, "text": line.split(f"[pid={pid}]", 1)[1].strip()}
    for index, line in enumerate(sdk_log.read_text().splitlines(), 1)
    if f"[pid={pid}]" in line and any(marker in line for marker in (
        "[LLMView]  Waiting for result.completed", "[LLMView]  Error during result.completed",
        "[LLMView]  Rejecting deferred with error", "[LLMView]  Subscription unsubscribed"))]
assert any("Rejecting deferred" in line["text"] for line in causal_lines)
headless = Path("work/codebuddy/node_modules/@tencent-ai/codebuddy-code/dist/codebuddy-headless.js")
assert hashlib.sha256(headless.read_bytes()).hexdigest() == plan["codebuddy_headless_sha256"]
source = headless.read_text()
assert "await this.waitForResultCompletion(eA,ep)" in source
assert "eg=eA}if(eh)" in source
assert 'ec.reject(eg)' in source
compared = 0
for row in rows:
    trial = json.loads((root / row["run_id"] / "trial.json").read_text())
    slot = slots[row["run_id"]]
    assert trial["protocol_commit"] == slot.get("source_protocol_commit", protocol)
    assert all(trial[key] == plan[key] for key in ("model", "backend", "limits"))
    if row["scoreable"]:
        compared += compare_files(root.parent / slot["source_batch"] / row["run_id"], root / row["run_id"])
for item in plan["preserved_previous_attempts"]:
    compared += compare_files(root.parent / item["source_batch"] / item["source_run_id"],
                              previous / item["preserved_run_id"])
for name, expected in plan["runtime_sha256"].items():
    assert hashlib.sha256((Path("course_eval") / name).read_bytes()).hexdigest() == expected, name
completed = [{"run_id": row["run_id"], **audit_free_billing(root / row["run_id"])} for row in scored]
assert {item["run_id"]: item for item in completed} == {
    item["run_id"]: item for item in old["completed_position_billing"]}
new_usage = run_metrics(root / failed["run_id"])
usage = merge_usage([run_metrics(root), run_metrics(previous)])
same_usage(usage, merge_usage([before["all_free_formal_usage_before_resume"], new_usage]))
current_billing = audit_free_billing(root, require_runtime_acceptance=False)
previous_billing = audit_free_billing(previous, require_runtime_acceptance=False)
probe_billing = audit_free_billing(probe_root)
new_billing = audit_free_billing(root / failed["run_id"], require_runtime_acceptance=False)
assert current_billing["missing_responses"] == 1 and previous_billing["missing_responses"] == 7
assert new_billing["requests"] == 2 and new_billing["responses"] == 1
assert probe_billing["requests"] == probe_billing["responses"] == 2
assert usage["usage_unreturned_requests"] == 8
result = {
    "status": "stopped_new_missing_receipt_at_client_result_completion",
    "recorded_utc": datetime.now(timezone.utc).isoformat(), "batch": root.name, "protocol_commit": protocol,
    "planned_primary_positions": 270, "started_positions": len(rows), "valid_original_scores": 90,
    "passed": 82, "failed": 8, "new_scored_positions": 0, "remaining_scores": 180,
    "unscored_positions": [failed["run_id"]], "unstarted_positions": 179,
    "arm_scores": old["arm_scores"], "old_unknown_cli_requests": 8,
    "new_unknown_cli_requests": 1, "total_unknown_cli_requests": 9,
    "failure": {"run_id": failed["run_id"], "request_id": 2,
        "failure_category": error["failure_category"], "stderr": error["stderr"], "stdout_characters": 0,
        "request_time_unix": request["time"], "error_time_unix": error["time"],
        "wall_clock_request_seconds": error["time"] - request["time"],
        "actual_model_credit": None, "original_score": None, "automatic_retries": 0,
        "provider_diagnostics": diagnostic, "causal_log_lines": causal_lines,
        "confirmed_client_boundary": "LLMView awaits result.completed; MaxTurnsExceededError rejects the deferred before jsonView.render(toSerializableArray(history))",
        "not_established": "No returned receipt or completed-stream diagnostic; exact final token count and model content are unknown"},
    "current_billing": current_billing, "previous_billing": previous_billing,
    "completed_position_billing": completed, "all_free_formal_attempt_usage": usage,
    "new_continuation_usage": new_usage, "new_continuation_billing": new_billing,
    "preparation_billing": probe_billing, "preparation_validation": probe,
    "new_cli_requests_this_continuation": 4, "new_returned_zero_credit_responses": 3,
    "source_partitions_match": True, "preserved_evidence_files_compared": compared,
    "original_score_verification": verify(root, allow_unscored=True),
    "previous_original_score_verification": verify(previous, allow_unscored=True),
    "runtime_matches_frozen_plan": True, "fee_validator_unchanged": True,
    "primary_result_ready": False, "complete_report_generated": False,
    "new_model_requests_after_stop": 0,
    "billing_boundary": "Only actual returned provider records prove zero credit; eight formal and one earlier preparation missing receipts remain unknown",
    "validation_boundary": "Tool-argument truncation and live shorter recovery passed; MaxTurns failure before JSON serialization did not pass the original-task validation",
}
content = HOME_PATH.sub("[本机路径]", json.dumps(result, ensure_ascii=False, indent=2)) + "\n"
assert not SECRET.search(content) and not PRIVATE.search(content)
Path("work/hy4flash-v10-stopped-summary.json").write_text(content)
print(json.dumps({key: result[key] for key in ("status", "valid_original_scores", "remaining_scores",
    "new_cli_requests_this_continuation", "new_returned_zero_credit_responses", "total_unknown_cli_requests",
    "preserved_evidence_files_compared", "current_billing", "previous_billing")}, ensure_ascii=False))
