import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from audit_confirmation_sources import audit_free_billing, same_usage
from course_eval.agent import CodeBuddyModel
from course_eval.confirmation_summary import merge_usage
from course_eval.export_revision import HOME_PATH, PRIVATE, SECRET, sanitize_model
from course_eval.summarize import read_runs, run_metrics
from course_eval.verify_scores import verify


formal = Path("work/vmshare/confirmation-hy4flash-free-v10")
previous = formal.with_name(formal.name + "-previous")
before = json.loads(Path("work/hy4flash-v10-stopped-summary.json").read_text())
rows = read_runs(formal)
assert len(rows) == 91 and sum(row["scoreable"] for row in rows) == 90
current = audit_free_billing(formal, require_runtime_acceptance=False)
historical = audit_free_billing(previous, require_runtime_acceptance=False)
assert current == before["current_billing"] and historical == before["previous_billing"]
for item in before["completed_position_billing"]:
    assert audit_free_billing(formal / item["run_id"]) == {key: value for key, value in item.items() if key != "run_id"}
usage = merge_usage([run_metrics(formal), run_metrics(previous)])
same_usage(usage, before["all_free_formal_attempt_usage"])
probe = Path("work/codebuddy-single-turn-probe-v11")
events = [json.loads(line) for line in (probe / "model.jsonl").read_text().splitlines()]
requests = [event for event in events if event["event"] == "request"]
response, = [event for event in events if event["event"] == "response"]
error, = [event for event in events if event["event"] == "request_error"]
child, = [event for event in events if event["event"] == "cli_process_started" and event["request_id"] == 2]
assert [event["request_id"] for event in requests] == [1, 2]
assert all(event["model"] == "hy4flash-free" and event["configured_max_output_tokens"] == 4096 for event in requests)
assert response["request_id"] == 1 and error["request_id"] == 2
assert error["stdout"] == "" and error["stderr"] == "eb.isMaxTurnsExceededError is not a function\n"
assert error["billing_status"] == "unknown"
probe_billing = audit_free_billing(probe, require_runtime_acceptance=False)
assert probe_billing["responses"] == probe_billing["missing_responses"] == 1
stamp = datetime.fromtimestamp(child["time"]).astimezone()
run = probe.resolve()
log = Path.home() / ".codebuddy/logs" / stamp.strftime("%Y-%m-%d") / (
    run.name + "__" + hashlib.md5(str(run).encode()).hexdigest() + ".log")
pid = child["provider_diagnostics"]["cli_pid"]
diagnostic = CodeBuddyModel.inspect_cli_log(log, pid)
assert diagnostic["model_requests_sent"] == diagnostic["completed_streams"] == 1
assert diagnostic["truncation_retries"] == diagnostic["structured_output_retries"] == 0
lines = [{"line": index, "text": line.split(f"[pid={pid}]", 1)[1].strip()}
    for index, line in enumerate(log.read_text().splitlines(), 1)
    if f"[pid={pid}]" in line and any(text in line for text in (
        "Error during result.completed", "Rejecting deferred with error", "TypeError: eb.isMaxTurnsExceededError"))]
patch = json.loads(Path("work/codebuddy-external-recovery-patch.json").read_text())
headless = Path("work/codebuddy/node_modules/@tencent-ai/codebuddy-code/dist/codebuddy-headless.js")
assert hashlib.sha256(headless.read_bytes()).hexdigest() == patch["patched_sha256"]
failed_client = Path("work/codebuddy-terminal-response-v11/codebuddy-headless.failed-cf1edc0d.js")
assert hashlib.sha256(failed_client.read_bytes()).hexdigest() == patch["terminal_response_patch"]["failed_probe_client_sha256"]
assert hashlib.sha256(Path("course_eval/codebuddy_free.py").read_bytes()).hexdigest() == patch["billing_validator_sha256"]
replay = json.loads(Path("work/codebuddy-terminal-response-v11/render-replay.json").read_text())
assert replay["actual_export_maps_verified"] and replay["failed_cf1edc0d_namespace_rejected"]
for name in ("fixed", "missing_receipt", "paid_receipt"):
    replay[name]["payload"] = json.loads(sanitize_model(json.dumps({"event": "response",
        "payload": replay[name]["payload"]})))["payload"]
Path("work/codebuddy-terminal-response-v11/render-replay-sanitized.json").write_text(
    json.dumps(replay, ensure_ascii=False, indent=2) + "\n")
record = {
    "status": "stopped_new_unknown_billing_during_terminal_serialization_probe",
    "recorded_utc": datetime.now(timezone.utc).isoformat(), "formal_batch": formal.name,
    "formal_protocol_commit": before["protocol_commit"], "planned_primary_positions": 270,
    "valid_original_scores": 90, "passed": 82, "failed": 8, "remaining_scores": 180,
    "unscored_positions": before["unscored_positions"], "unstarted_positions": 179,
    "arm_scores": before["arm_scores"], "new_formal_positions": 0,
    "current_billing": current, "previous_billing": historical,
    "all_free_formal_attempt_usage": usage, "old_unknown_cli_requests": 9,
    "new_unknown_cli_requests": 1, "total_unknown_cli_requests": 10,
    "probe_billing": probe_billing,
    "first_probe": {"request_id": 1, "completion_tokens": 1783, "credit": 0,
        "outcome": "Same original FEAL input returned a full action; did not exercise truncation or terminal failure"},
    "failure": {"request_id": 2, "purpose": "Native Read of the task-local receipt-input.txt followed by the one-turn boundary",
        "stdout_characters": 0, "stderr": error["stderr"], "actual_model_credit": None,
        "request_time_unix": requests[1]["time"], "error_time_unix": error["time"],
        "wall_clock_request_seconds": error["time"] - requests[1]["time"],
        "diagnostic": diagnostic, "causal_log_lines": lines,
        "root_cause": "Wrong namespace: the LLMView eb binding is module 96829, which does not export the SDK predicate or physical-completion helper"},
    "initial_local_validation_gap": "The isolated replay injected compatibility functions into eb without checking the actual module export map; its earlier pass did not establish runtime linkage",
    "corrected_client": patch, "local_replay": {key: value for key, value in replay.items()
        if key not in {"fixed", "missing_receipt", "paid_receipt"}},
    "corrected_client_live_validation": False, "output_4096_revalidated_this_turn": False,
    "original_score_revalidated_this_turn": False,
    "original_score_verification": verify(formal, allow_unscored=True),
    "old_scores_and_costs_unchanged": True, "fee_validator_unchanged": True,
    "formal_v11_launched": False, "primary_result_ready": False,
    "new_model_requests_after_stop": 0,
    "fee_scope": "Eight formal missing receipts and two preparation missing receipts remain unknown; client logs do not prove credit",
}
content = HOME_PATH.sub("[本机路径]", json.dumps(record, ensure_ascii=False, indent=2)) + "\n"
assert not SECRET.search(content) and not PRIVATE.search(content)
Path("work/hy4flash-v11-stopped-summary.json").write_text(content)
print(json.dumps({key: record[key] for key in ("status", "valid_original_scores", "remaining_scores",
    "new_formal_positions", "total_unknown_cli_requests", "corrected_client_live_validation")}, ensure_ascii=False))
