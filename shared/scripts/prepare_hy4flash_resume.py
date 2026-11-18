import argparse
import json
import shutil
from pathlib import Path

from audit_confirmation_sources import audit_free_billing, compare_files, evidence_files, same_usage
from course_eval.confirmation import prepare
from course_eval.confirmation_summary import merge_usage
from course_eval.summarize import read_runs, run_metrics
from course_eval.verify_scores import verify


def copy_evidence(source, destination):
    destination.mkdir(parents=True, exist_ok=False)
    for relative in evidence_files(source):
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source / relative, target)
    return compare_files(source, destination)


root = Path("work/vmshare")
parser = argparse.ArgumentParser()
parser.add_argument("--source-version", type=int, required=True)
parser.add_argument("--version", type=int, required=True)
validation = parser.add_mutually_exclusive_group(required=True)
validation.add_argument("--probe", type=Path)
validation.add_argument("--local-validation", type=Path)
args = parser.parse_args()
assert args.version == args.source_version + 1
source = root / f"confirmation-hy4flash-free-v{args.source_version}"
destination = root / f"confirmation-hy4flash-free-v{args.version}"
previous = destination.with_name(destination.name + "-previous")
plan_path = Path(f"work/confirmation-plan-hy4flash-free-v{args.version}.json")
assert not destination.exists() and not previous.exists() and not plan_path.exists()
source_plan = json.loads(Path(f"work/confirmation-plan-hy4flash-free-v{args.source_version}.json").read_text())
source_summary = json.loads(Path(f"work/hy4flash-v{args.source_version}-stopped-summary.json").read_text())
if args.probe:
    probe = json.loads((args.probe / "summary.json").read_text())
    assert probe["actual_cli_requests"] == 1 and probe["historical_unknown_cli_requests"] == source_summary["total_unknown_cli_requests"]
    assert probe["complete_json_and_terminal_event"] and probe["billing"]["credit"] == 0
    audit_free_billing(args.probe)
else:
    probe = json.loads(args.local_validation.read_text())
    assert probe["status"] == "passed" and probe["model_calls"] == 0
    assert probe["actual_native_events_unchanged"] and probe["final_4096_segment_rejected"]
    assert probe["old_true_unknown_still_rejected"] and probe["live_fixed_client_verified"] is False
    assert source_summary["new_unknown_cli_requests"] == 0
    assert source_summary["failure"]["native_requests_with_unmatched_usage"] == 0
rows = read_runs(source)
reused = [row for row in rows if row["scoreable"]]
unscored = [row for row in rows if not row["scoreable"]]
assert len(rows) == source_summary["started_positions"] and len(reused) == source_summary["valid_original_scores"] and len(unscored) == 1
assert sum(not row["passed"] for row in reused) == source_summary["failed"]
source_scores = verify(source, allow_unscored=True)
for row in reused:
    directory = source / row["run_id"]
    trial = json.loads((directory / "trial.json").read_text())
    source_slot = next(slot for slot in source_plan["slots"] if slot["run_id"] == row["run_id"])
    assert trial["protocol_commit"] == source_slot.get("source_protocol_commit", source_summary["protocol_commit"])
    assert all(trial[key] == source_plan[key] for key in ("model", "backend", "limits"))
    audit_free_billing(directory)

previous_count = len(source_plan["preserved_previous_attempts"]) + len(unscored)
prepare(Path("work/confirmation-frozen-v1.json"), Path("work/confirmation-public-checks-v1.json"),
        root / "confirmation-preflights-v1", plan_path, attempt_cap=300 - previous_count)
plan = json.loads(plan_path.read_text())
assert all(plan[key] == source_plan[key] for key in (
    "seed", "model", "backend", "codebuddy_version", "limits", "manifest_sha256", "checks_sha256",
    "python_version", "package_versions"))
assert [name for name in plan["runtime_sha256"]
        if plan["runtime_sha256"][name] != source_plan["runtime_sha256"][name]] == (["agent.py"] if args.probe else [])
assert plan["runtime_sha256"]["agent.py"] == probe["agent_sha256"]
assert plan["codebuddy_headless_sha256"] == probe["client_sha256"]
destination.mkdir()
previous.mkdir()
slots = {slot["run_id"]: slot for slot in plan["slots"]}
copied = 0
for row in reused:
    copied += copy_evidence(source / row["run_id"], destination / row["run_id"])
    trial = json.loads((source / row["run_id"] / "trial.json").read_text())
    slots[row["run_id"]].update(source_batch=source.name, source_protocol_commit=trial["protocol_commit"])
preserved = []
old_previous = source.with_name(source.name + "-previous")
for item in source_plan["preserved_previous_attempts"]:
    copied += copy_evidence(old_previous / item["preserved_run_id"], previous / item["preserved_run_id"])
    preserved.append(item)
for row in unscored:
    name = f"v{args.source_version}__" + row["run_id"]
    copied += copy_evidence(source / row["run_id"], previous / name)
    preserved.append({"source_batch": source.name, "source_run_id": row["run_id"], "preserved_run_id": name})
assert len(preserved) == previous_count
assert len(read_runs(destination)) == len(reused) and len(read_runs(previous)) == previous_count
before = merge_usage([run_metrics(source), run_metrics(old_previous)])
after = merge_usage([run_metrics(destination), run_metrics(previous)])
same_usage(before, after)
assert after["usage_unreturned_requests"] == source_summary["formal_missing_receipts"]
plan.update(reused_positions=len(reused), new_positions=270 - len(reused), preserved_previous_attempts=preserved,
            cumulative_attempt_cap=300,
            network_policy={"inherit_proxy_environment": True, "proxy_config_file_disabled": True,
                            "sdk_proxy_source": "env", "new_request_unknown_or_nonzero_credit": "stop"},
            historical_unknown_cost="Preserved as unknown; never replaced by new request receipts",
            historical_unknown_cli_requests={"formal": source_summary["formal_missing_receipts"] + source_summary.get("formal_returned_unknown_requests", source_summary.get("formal_returned_unverified_requests", 0)),
                "formal_missing_responses": source_summary["formal_missing_receipts"],
                "formal_returned_unverified": source_summary.get("formal_returned_unverified_requests", 0),
                "formal_known_zero_local_metadata_rejections": source_summary.get("formal_known_zero_local_metadata_rejections", 0),
                "preparation": source_summary["historical_preparation_missing_receipts"],
                "total": source_summary["total_unknown_cli_requests"],
                "preparation_traces": ["work/codebuddy-single-turn-probe-v9/truncated-64/model.jsonl",
                    "work/codebuddy-single-turn-probe-v11/model.jsonl"]},
            transport_sensitivity_excluded_task="django__django-11999",
            diagnostic_policy={"cli_pid_recorded": True, "timeout_reads_own_workspace_sdk_log": True,
                               "sdk_log_never_proves_billing": True, "model_arguments_and_timeouts_unchanged": True},
            mechanical_recovery={"scope": ("Disable the SDK independent empty-stream and timeout recovery for external recovery opt-in; use UTC SDK diagnostic date; scientific inputs unchanged" if args.probe else "Correct local tool-result model metadata using the exact parent callId/messageId/conversationRequestId; preserve callId in evidence export; actual provider events, receipts, agent/controller/billing logic and scientific inputs unchanged"),
                "environment": {"COURSE_CODEBUDDY_EXTERNAL_RECOVERY": "1"},
                "outer_recovery": "Only after actual zero-credit receipt; charged to existing 24 decisions and 600 seconds",
                "preparation_evidence": str(args.probe / "summary.json") if args.probe else str(args.local_validation),
                "preparation_cli_requests": 1 if args.probe else 0, "preparation_scores": 0},
            resumed_unscored_run_id=unscored[0]["run_id"], resumed_position_total_attempt_number=2)
plan_path.write_text(json.dumps(plan, indent=2) + "\n")
verification = {"stage": "frozen_resume_ready", "new_model_requests": 0,
                "source_scores": source_scores, "reused_positions": len(reused),
                "preserved_valid_failures": source_summary["failed"], "new_positions": 270 - len(reused), "previous_attempts": previous_count,
                "evidence_files_compared": copied, "usage_source_partitions_match": True,
                "all_free_formal_usage_before_resume": after,
                "actual_model_identity_and_credit_rules_unchanged": True,
                "local_timeout_diagnostics": ("UTC-day and PID-scoped phases; agent.py diagnostic path and the explicitly recorded SDK stream recovery changed; billing validator and other fourteen frozen execution files unchanged" if args.probe else "Actual two-request/two-stream/two-receipt coverage and local parent identity matched; local SDK metadata-only repair; all fifteen runtime files unchanged; the separate evidence exporter additionally retains callId"),
                "reused_original_scores": verify(destination),
                "previous_original_scores": verify(previous, allow_unscored=True)}
Path(f"work/hy4flash-v{args.version}-resume-validation.json").write_text(json.dumps(verification, ensure_ascii=False, indent=2) + "\n")
print(json.dumps({key: verification[key] for key in (
    "stage", "new_model_requests", "reused_positions", "preserved_valid_failures", "new_positions",
    "previous_attempts", "evidence_files_compared", "usage_source_partitions_match")}, ensure_ascii=False))
