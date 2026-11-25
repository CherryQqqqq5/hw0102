import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from statistics import median

from course_eval.summarize import compare, read_runs


def enriched_rows(root):
    rows = read_runs(root)
    for row in rows:
        automatic = []
        for path in (root / row["run_id"]).rglob("verification.jsonl"):
            for line in path.read_text().splitlines(keepends=True):
                if not row["scoreable"] and not line.endswith("\n"):
                    continue
                event = json.loads(line)
                if event["event"] == "automatic_public_check":
                    automatic.append(event)
        row["automatic_checks"] = len(automatic)
        row["automatic_failures"] = sum(event["returncode"] != 0 for event in automatic)
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--reference", default="B0")
    parser.add_argument("--treatment", default="A")
    parser.add_argument("--replace-runs", type=Path)
    args = parser.parse_args()
    plan = json.loads((args.runs / "run-plan.json").read_text())
    rows = enriched_rows(args.runs)
    replacement_ids = []
    if args.replace_runs:
        replacement_plan = json.loads((args.replace_runs / "run-plan.json").read_text())
        if any(plan[key] != replacement_plan[key] for key in ("model", "backend", "limits")):
            raise ValueError("Replacement model or budget differs from the original plan")
        replacements = enriched_rows(args.replace_runs)
        affected = {row["task"] for row in replacements}
        expected_ids = {row["run_id"] for row in rows if row["task"] in affected}
        actual_ids = {row["run_id"] for row in replacements}
        if not actual_ids or actual_ids != expected_ids or not all(row["scoreable"] for row in replacements):
            raise ValueError("A replacement must include every scored arm and repeat of each affected task")
        replacement_ids = sorted(actual_ids)
        indexed = {row["run_id"]: row | {"source_batch": args.runs.name} for row in rows}
        indexed.update({row["run_id"]: row | {"source_batch": args.replace_runs.name} for row in replacements})
        rows = [indexed[key] for key in sorted(indexed)]
    split, = {row["split"] for row in rows}
    repetitions = max(slot["repeat"] for slot in plan["slots"])
    expected_tasks = len({slot["task"] for slot in plan["slots"]})
    planned = Counter(slot["arm"] for slot in plan["slots"])
    coverage = []
    for arm, expected in sorted(planned.items()):
        matching = [row for row in rows if row["arm"] == arm]
        scored = [row for row in matching if row["scoreable"]]
        coverage.append({"arm": arm, "planned": expected, "started": len(matching), "scored": len(scored),
                         "passed": sum(row["passed"] for row in scored),
                         "wall_median_seconds": median(row["wall_seconds"] for row in scored) if scored else None,
                         **{key: sum(row[key] for row in matching) for key in (
                             "model_calls", "model_responses", "model_request_retries", "model_request_timeouts",
                             "input_tokens", "output_tokens", "tool_calls")}})
    for item in coverage:
        matching = [row for row in rows if row["arm"] == item["arm"]]
        item["automatic_checks"] = sum(row["automatic_checks"] for row in matching)
        item["automatic_failures"] = sum(row["automatic_failures"] for row in matching)
    result = {"plan": plan, "coverage": coverage,
              "comparison": compare(rows, split, args.reference, args.treatment, repetitions,
                                    expected_tasks=expected_tasks),
              "by_repeat": [compare([row for row in rows if row["repeat"] == repeat], split,
                                    args.reference, args.treatment, 1, expected_tasks=expected_tasks) | {"repeat": repeat}
                            for repeat in range(1, repetitions + 1)]}
    if args.replace_runs:
        result["replacement_run_ids"] = replacement_ids
        result["source_batches"] = [args.runs.name, args.replace_runs.name]
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "summary.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    with (args.out / "trials.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps(coverage, indent=2))


if __name__ == "__main__":
    main()
