import argparse
import hashlib
import json
from pathlib import Path

from audit_confirmation_sources import audit_free_billing
from course_eval.summarize import read_runs
from course_eval.verify_scores import verify


parser = argparse.ArgumentParser()
parser.add_argument("--runs", type=Path, required=True)
parser.add_argument("--previous-runs", type=Path, required=True)
parser.add_argument("--mechanical-runs", type=Path)
parser.add_argument("--summary", type=Path, required=True)
parser.add_argument("--plan", type=Path, required=True)
args = parser.parse_args()
summary = json.loads(args.summary.read_text())
if "mechanical_billing" in summary and args.mechanical_runs is None:
    parser.error("This summary requires --mechanical-runs to preserve archived unknown costs")
plan = json.loads(args.plan.read_text())
for name, expected in plan["runtime_sha256"].items():
    assert hashlib.sha256((Path("course_eval") / name).read_bytes()).hexdigest() == expected, name
assert audit_free_billing(args.runs, require_runtime_acceptance=False) == summary["current_billing"]
assert audit_free_billing(args.previous_runs, require_runtime_acceptance=False) == summary["previous_billing"]
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
assert summary["primary_result_ready"] is False and summary["failure"]["actual_model_credit"] is None
print(json.dumps({"status": "verified_preserved_partial_run", "scored": len(scored),
                  "passed": sum(row["passed"] for row in scored),
                  "responses": summary["current_billing"]["responses"],
                  "verified_actual_model_records": summary["current_billing"]["actual_model_usage_records"],
                  "new_missing_receipts": summary["current_billing"]["missing_responses"],
                  "historical_missing_receipts": summary["previous_billing"]["missing_responses"],
                  "recovery_archive_missing_receipts": summary["mechanical_billing"]["missing_responses"] if args.mechanical_runs is not None else 0,
                  "new_model_requests": 0}, ensure_ascii=False))
