import argparse
import hashlib
import json
from pathlib import Path

from audit_confirmation_sources import audit_free_billing, audit_free_recovery_preparation, audit_stopped_billing
from course_eval.confirmation_summary import mechanism, merge_usage
from course_eval.summarize import compare, read_runs, run_metrics
from course_eval.verify_scores import verify


parser = argparse.ArgumentParser()
parser.add_argument("--runs", type=Path, required=True)
parser.add_argument("--previous-runs", type=Path, required=True)
parser.add_argument("--mechanical-runs", type=Path)
parser.add_argument("--summary", type=Path, required=True)
parser.add_argument("--plan", type=Path, required=True)
parser.add_argument("--runtime", type=Path, default=Path("course_eval"))
parser.add_argument("--trials", type=Path)
parser.add_argument("--source-audit", type=Path)
parser.add_argument("--preparation-root", type=Path)
args = parser.parse_args()
summary = json.loads(args.summary.read_text())
if "mechanical_billing" in summary and args.mechanical_runs is None:
    parser.error("This summary requires --mechanical-runs to preserve archived unknown costs")
plan = json.loads(args.plan.read_text())
for name, expected in plan["runtime_sha256"].items():
    assert hashlib.sha256((args.runtime / name).read_bytes()).hexdigest() == expected, name
def check_billing(directory, expected, require_runtime_acceptance):
    if "total_unknown_cli_requests" in expected or expected.get("returned_unverified_responses"):
        actual = audit_stopped_billing(directory, require_runtime_acceptance=require_runtime_acceptance)
    else:
        actual = audit_free_billing(directory, require_runtime_acceptance=False)
    assert {key: actual[key] for key in expected} == expected
    return actual


if args.source_audit is not None:
    if args.trials is None or args.preparation_root is None:
        parser.error("Complete verification requires --trials and --preparation-root")
    audit = json.loads(args.source_audit.read_text())
    scored = read_runs(args.runs)
    slots = {slot["run_id"]: slot for slot in plan["slots"]}
    assert len(scored) == len(slots) == audit["primary_positions"] == 270
    assert all(row["scoreable"] for row in scored)
    assert {row["run_id"] for row in scored} == slots.keys()
    current = audit_free_billing(args.runs)
    assert current == audit["free_billing"] and current["missing_responses"] == 0
    previous = audit_stopped_billing(args.previous_runs, require_runtime_acceptance=False)
    assert [previous] == audit["previous_free_billing"]
    assert summary["previous_attempt_count"] == len(plan["preserved_previous_attempts"]) == 15
    assert summary["previous_scored_count"] == summary["mechanical_attempt_count"] == 0
    assert merge_usage([run_metrics(args.runs), run_metrics(args.previous_runs)]) == summary["all_attempt_usage"]
    original = verify(args.runs)
    historical = verify(args.previous_runs, allow_unscored=True)
    assert original["score_records_verified"] == 270 and len(historical["unscored_records_preserved"]) == 15
    for row in scored:
        trial = json.loads((args.runs / row["run_id"] / "trial.json").read_text())
        slot = slots[row["run_id"]]
        expected = slot.get("source_protocol_commit", audit["protocol_commit"])
        assert trial["protocol_commit"] == expected
        assert all(trial[key] == plan[key] for key in ("model", "backend", "limits"))
        row.update(mechanism(args.runs / row["run_id"]))
        row["source_batch"] = slot.get("source_batch", args.runs.name)
        row["protocol_commit"] = expected
    assert scored == json.loads(args.trials.read_text())
    comparisons = [compare(scored, "C", reference, treatment, 3, expected_tasks=30)
                   for reference, treatment in (("B0", "C1"), ("C0", "C1"), ("B0", "C0"))]
    assert comparisons == summary["comparisons"]
    for item in summary["coverage"]:
        selected = [row for row in scored if row["arm"] == item["arm"]
                    and (item["benchmark"] == "all" or row["benchmark"] == item["benchmark"])]
        assert item["trials"] == len(selected) and item["success"] == sum(row["passed"] for row in selected)
    preparation = audit_free_recovery_preparation(args.preparation_root / "codebuddy-quota-probe",
                                                args.preparation_root / "hy4flash-interface-v1")
    expected = audit["free_preparation"]
    for key in ("usage", "actual_model_usage_records", "missing_responses", "initial_preparation"):
        assert preparation[key] == expected[key]
    for actual, recorded in zip(preparation["recovery_preparation"], expected["recovery_preparation"], strict=True):
        assert {key: value for key, value in actual.items() if key != "source"} == {key: value for key, value in recorded.items() if key != "source"}
    unknown = previous["total_unknown_cli_requests"] + preparation["missing_responses"]
    assert unknown == plan["historical_unknown_cli_requests"]["total"] == 13
    assert previous["returned_known_zero_local_metadata_rejections"] == 1
    print(json.dumps({"status": "verified_complete_free_run", "scored": len(scored),
        "passed": sum(row["passed"] for row in scored), "failed": sum(not row["passed"] for row in scored),
        "responses": current["responses"], "verified_actual_model_records": current["actual_model_usage_records"],
        "new_missing_receipts": 0, "historical_unknown_cli_requests": unknown,
        "historical_known_zero_local_metadata_rejections": 1, "historical_unscored_attempts": 15,
        "preparation_requests_verified": preparation["usage"]["model_calls"],
        "paired_statistics_and_trial_analysis_recomputed": True, "new_model_or_grader_calls": 0}, ensure_ascii=False))
    raise SystemExit(0)


current = check_billing(args.runs, summary["current_billing"], True)
previous = check_billing(args.previous_runs, summary["previous_billing"], False)
if args.mechanical_runs is not None:
    assert audit_free_billing(args.mechanical_runs, require_runtime_acceptance=False) == summary["mechanical_billing"]
expected_billing = {record["run_id"]: record for record in summary["completed_position_billing"]}
scored = [row for row in read_runs(args.runs) if row["scoreable"]]
assert {row["run_id"] for row in scored} == expected_billing.keys()
for row in scored:
    assert audit_free_billing(args.runs / row["run_id"]) == {
        key: value for key, value in expected_billing[row["run_id"]].items() if key != "run_id"}
groups = [(args.runs, "original_score_verification"),
          (args.previous_runs, "previous_original_score_verification")]
if args.mechanical_runs is not None:
    groups.append((args.mechanical_runs, "mechanical_original_score_verification"))
for directory, field in groups:
    actual = verify(directory, allow_unscored=True)
    for key in ("score_records_verified", "by_benchmark", "unscored_records_preserved"):
        assert actual[key] == summary[field][key], (directory, key)
assert summary["primary_result_ready"] is False
failure = summary["failure"]
credit_field = "actual_provider_credit" if "actual_provider_credit" in failure else "actual_model_credit"
assert failure[credit_field] is None
if "formal_known_zero_local_metadata_rejections" in summary:
    assert current["total_unknown_cli_requests"] + previous["total_unknown_cli_requests"] + summary["historical_preparation_missing_receipts"] == summary["total_unknown_cli_requests"]
    assert previous["returned_known_zero_local_metadata_rejections"] == summary["formal_known_zero_local_metadata_rejections"]
    assert merge_usage([run_metrics(args.runs), run_metrics(args.previous_runs)]) == summary["all_free_formal_attempt_usage"]
    if args.trials is None:
        parser.error("This summary requires --trials to verify the saved partial analysis")
if args.trials is not None:
    expected = json.loads(args.trials.read_text())
    actual = []
    for row in scored:
        row.update(mechanism(args.runs / row["run_id"]))
        actual.append(row)
    assert actual == expected
print(json.dumps({"status": "verified_preserved_partial_run", "scored": len(scored),
                  "passed": sum(row["passed"] for row in scored),
                  "responses": summary["current_billing"]["responses"],
                  "verified_actual_model_records": summary["current_billing"]["actual_model_usage_records"],
                  "new_missing_receipts": summary["current_billing"]["missing_responses"],
                  "returned_unverified_responses": summary["current_billing"].get("returned_unverified_responses", 0),
                  "historical_missing_receipts": summary["previous_billing"]["missing_responses"],
                  "historical_returned_unknown_responses": previous.get("returned_unknown_responses", 0),
                  "historical_known_zero_local_metadata_rejections": previous.get("returned_known_zero_local_metadata_rejections", 0),
                  "recovery_archive_missing_receipts": summary["mechanical_billing"]["missing_responses"] if args.mechanical_runs is not None else 0,
                  "new_model_requests": 0}, ensure_ascii=False))
