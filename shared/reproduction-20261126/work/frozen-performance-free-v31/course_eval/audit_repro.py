import argparse
import json
from collections import Counter
from pathlib import Path

from course_eval.agent import RunLimits
from course_eval.summarize import compare, read_runs


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    rows = read_runs(args.runs)
    limits = {path.parent.name: RunLimits.model_validate(json.loads(path.read_text())["limits"])
              for path in args.runs.glob("*/trial.json")}
    assert len(rows) == len(limits) == 240
    counts = Counter(value.timeout_retries for value in limits.values())
    assert counts == {0: 109, 2: 131}, counts
    assert all(limits[row["run_id"]].timeout_retries == row["request_retry_allowance"] for row in rows)
    groups = Counter((row["split"], row["arm"], row["request_retry_allowance"]) for row in rows)
    mismatches = []
    excluded = []
    for split, reference, treatment, repeats in (("D", "B0", "F", 1), ("H", "B0", "F", 3),
                                                 ("H", "BP", "F", 3), ("H", "A", "F", 3)):
        treatment_rows = {(row["task"], row["repeat"]): row for row in rows
                          if row["split"] == split and row["arm"] == treatment}
        for row in rows:
            if row["split"] != split or row["arm"] != reference:
                continue
            other = treatment_rows[(row["task"], row["repeat"])]
            if row["request_retry_allowance"] != other["request_retry_allowance"]:
                mismatches.append({"split": split, "reference": reference, "treatment": treatment,
                                   "task": row["task"], "repeat": row["repeat"],
                                   "allowances": [row["request_retry_allowance"], other["request_retry_allowance"]],
                                   "retries": [row["model_request_retries"], other["model_request_retries"]],
                                   "passed": [row["passed"], other["passed"]]})
        comparison = compare(rows, split, reference, treatment, repeats)
        excluded.append({"split": split, "reference": reference, "treatment": treatment,
                         "removed_tasks": [pair["task"] for pair in comparison["pairs"] if pair["provider_timeout"]],
                         "remaining_tasks": comparison["pairs_without_provider_timeout"],
                         "remaining_delta": comparison["delta_without_provider_timeout_percentage_points"]})
    result = {"historical_configurations": len(rows), "retry_allowance": dict(counts),
              "retry_groups": [{"split": split, "arm": arm, "allowance": retry, "count": count}
                               for (split, arm, retry), count in sorted(groups.items())],
              "mismatched_pairs": mismatches, "timeout_sensitivity": excluded,
              "exploratory_A_vs_B0": compare(rows, "H", "B0", "A", 3)}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({key: value for key, value in result.items() if key != "exploratory_A_vs_B0"}, indent=2))


if __name__ == "__main__":
    main()
