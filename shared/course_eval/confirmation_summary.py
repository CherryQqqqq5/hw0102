import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from statistics import mean, median

from course_eval.summarize import compare, read_runs, run_metrics


def mechanism(directory):
    events = [json.loads(line) for path in directory.rglob("controller.jsonl") for line in path.read_text().splitlines()]
    checks = [event for event in events if event["event"] == "verification"]
    failed = {}
    repairs = []
    for event in checks:
        key = event["check_id"]
        if event["state"] == "failed":
            failed[key] = event
        elif event["state"] == "passed" and key in failed:
            earlier = failed.pop(key)
            if earlier["artifact_digest"] != event["artifact_digest"]:
                repairs.append({"check_id": key, "failed_step": earlier["step"], "passed_step": event["step"],
                                "failed_digest": earlier["artifact_digest"], "passed_digest": event["artifact_digest"]})
    finals = list(directory.rglob("final-verification.json"))
    final = json.loads(finals[0].read_text()) if finals else {}
    budgets = list(directory.rglob("execution-budget.json"))
    budget = json.loads(budgets[0].read_text()) if budgets else {}
    return {"public_checks": len(checks), "automatic_checks": sum(event["reason"] != "requested" for event in checks),
            "public_check_seconds": sum(event["seconds"] for event in checks),
            "candidate_operation_seconds": sum(event["seconds"] for event in events if event["event"] == "candidate_operation"),
            "failed_public_checks": sum(event["state"] == "failed" for event in checks),
            "unknown_public_checks": sum(event["state"] == "unknown" for event in checks),
            "changed_candidate_repair_chains": len(repairs), "repair_chain_details": repairs,
            "valid_final_verification": final.get("valid_verification"),
            "restored_final_candidate": bool(final.get("restored_candidate")),
            "execution_seconds": budget.get("elapsed_seconds"),
            "controller_errors": sum(event["event"] in {"controller_error", "finalization_error"} for event in events)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=Path, required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    plan = json.loads(args.plan.read_text())
    rows = read_runs(args.runs)
    if {row["run_id"] for row in rows} != {slot["run_id"] for slot in plan["slots"]} or any(not row["scoreable"] for row in rows):
        raise ValueError("Primary comparison requires every frozen position to be scored")
    for row in rows:
        row.update(mechanism(args.runs / row["run_id"]))
    groupings = []
    for benchmark in ("all", "swe", "terminal", "aider"):
        for arm in ("B0", "C0", "C1"):
            matches = [row for row in rows if row["arm"] == arm and (benchmark == "all" or row["benchmark"] == benchmark)]
            task_scores = defaultdict(list)
            for row in matches:
                task_scores[row["task"]].append(int(row["passed"]))
            if any(len(values) != 3 for values in task_scores.values()):
                raise ValueError("Incomplete three-repeat task")
            recorded_execution = [row["execution_seconds"] for row in matches if row["execution_seconds"] is not None]
            groupings.append({"benchmark": benchmark, "arm": arm, "trials": len(matches),
                "success": sum(row["passed"] for row in matches), "success_rate": mean(row["passed"] for row in matches),
                "task_mean_success": mean(mean(values) for values in task_scores.values()),
                "all_three_successful_tasks": sum(all(values) for values in task_scores.values()),
                "execution_seconds_recorded": len(recorded_execution),
                "total_execution_seconds": sum(recorded_execution),
                "median_execution_seconds": median(recorded_execution) if recorded_execution else None,
                "median_wall_seconds": median(row["wall_seconds"] for row in matches),
                "valid_final_verification_trials": sum(row["valid_final_verification"] is True for row in matches),
                "repair_chain_and_original_pass_trials": sum(row["changed_candidate_repair_chains"] > 0 and row["passed"] for row in matches),
                **{key: sum(row[key] or 0 for row in matches) for key in ("model_calls", "model_responses", "input_tokens",
                   "output_tokens", "cached_input_tokens", "model_request_retries", "model_request_timeouts", "wall_seconds",
                   "grader_seconds", "public_checks", "public_check_seconds", "candidate_operation_seconds", "automatic_checks", "failed_public_checks", "unknown_public_checks", "changed_candidate_repair_chains",
                   "restored_final_candidate", "controller_errors")}})
    comparisons = [compare(rows, "C", reference, treatment, 3, expected_tasks=30)
                   for reference, treatment in (("B0", "C1"), ("C0", "C1"), ("B0", "C0"))]
    slices = [compare([row for row in rows if row["benchmark"] == benchmark], "C", reference, treatment, 3, expected_tasks=10)
              | {"benchmark": benchmark} for benchmark in ("swe", "terminal", "aider")
              for reference, treatment in (("B0", "C1"), ("C0", "C1"), ("B0", "C0"))]
    archived = args.runs.with_name(args.runs.name + "-attempts")
    formal_usage, mechanical_usage = run_metrics(args.runs), run_metrics(archived)
    total_usage = {key: formal_usage[key] + mechanical_usage[key] for key in formal_usage if key != "provider_reported_cost_usd"}
    reported = [value for value in (formal_usage["provider_reported_cost_usd"], mechanical_usage["provider_reported_cost_usd"]) if value is not None]
    total_usage["provider_reported_cost_usd"] = sum(reported) if reported else None
    result = {"primary_comparison": "C1 versus B0", "mechanism_comparison": "C1 versus C0",
              "interval": "10000 paired task bootstrap samples, stratified by benchmark, seed 20261104",
              "coverage": groupings, "comparisons": comparisons, "benchmark_comparisons": slices,
              "all_attempt_usage": total_usage, "formal_attempt_usage": formal_usage, "mechanical_attempt_usage": mechanical_usage,
              "mechanical_attempt_count": len(list(archived.glob("*/trial.json"))),
              "mechanism_boundary": "A failed-check, changed-candidate, passing-check sequence is an observed sequence; causal effect comes from matched arm comparisons."}
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "summary.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    (args.out / "trials.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n")
    fields = [key for key in rows[0] if key != "repair_chain_details"]
    with (args.out / "trials.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps({"scored": len(rows), "comparisons": [{k: v for k, v in item.items() if k != "pairs"} for item in comparisons]}))


if __name__ == "__main__":
    main()
