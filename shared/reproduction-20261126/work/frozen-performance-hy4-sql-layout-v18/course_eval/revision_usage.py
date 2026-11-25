import argparse
import json
from pathlib import Path

from course_eval.revision_summary import enriched_rows


FIELDS = (
    "model_calls", "model_responses", "model_request_retries", "model_request_timeouts",
    "input_tokens", "output_tokens", "tool_calls", "automatic_checks", "automatic_failures",
)


def usage(rows):
    return {"trials": len(rows), "scoreable": sum(row["scoreable"] for row in rows),
            "unscored": sum(not row["scoreable"] for row in rows),
            **{key: sum(row[key] for row in rows) for key in FIELDS}}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=Path, nargs="+", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if len({path.resolve() for path in args.runs}) != len(args.runs):
        raise ValueError("Duplicate source batch")
    combined = []
    batches = []
    for root in args.runs:
        rows = enriched_rows(root)
        if not rows or any(not (root / row["run_id"] / "result.json").exists() for row in rows):
            raise ValueError(f"Incomplete batch: {root}")
        batches.append({"source_batch": root.name, **usage(rows)})
        combined.extend(rows)
    result = {"scope": "All completed attempts in the listed batches, including unscored provider failures and superseded recovery records; no merged comparison directory",
              "batches": batches, "total": usage(combined)}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
