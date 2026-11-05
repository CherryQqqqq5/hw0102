import argparse
import csv
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from random import Random
from statistics import mean

from course_eval.matrix import slots


def run_metrics(path: Path, *, complete: bool = True) -> dict:
    metrics = Counter()
    reported_cost = []
    for log in path.rglob("model.jsonl"):
        for line in log.read_text().splitlines(keepends=True):
            if not complete and not line.endswith("\n"):
                continue
            event = json.loads(line)
            if event["event"] == "request":
                metrics["model_calls"] += 1
                metrics["model_request_retries"] += event.get("attempt", 1) > 1
            if event["event"] == "request_error" and event.get("error_type") in {"TimeoutExpired", "APITimeoutError"}:
                metrics["model_request_timeouts"] += 1
            if event["event"] != "response":
                continue
            metrics["model_responses"] += 1
            payload = event["payload"]
            if isinstance(payload, list):
                result = next((item for item in payload if item["type"] == "result"), None)
                if result is None:
                    continue
                usage = result.get("usage") or {}
                metrics["input_tokens"] += usage.get("input_tokens", 0)
                metrics["output_tokens"] += usage.get("output_tokens", 0)
                metrics["cached_input_tokens"] += usage.get("cache_read_input_tokens", 0)
                metrics["provider_turns"] += result.get("num_turns", 0)
                if result.get("total_cost_usd") is not None:
                    reported_cost.append(result["total_cost_usd"])
            else:
                usage = payload.get("usage") or {}
                metrics["input_tokens"] += usage.get("prompt_tokens", 0)
                metrics["output_tokens"] += usage.get("completion_tokens", 0)
                metrics["cached_input_tokens"] += (usage.get("prompt_tokens_details") or {}).get("cached_tokens", 0)
    for log in path.rglob("tools.jsonl"):
        with log.open() as handle:
            metrics["tool_calls"] += sum(1 for line in handle if line.strip())
    for log in path.rglob("verification.jsonl"):
        for line in log.read_text().splitlines(keepends=True):
            if not complete and not line.endswith("\n"):
                continue
            event = json.loads(line)
            if event["event"] == "deliverable_checkpoint":
                metrics["deliverable_checkpoints"] += 1
                metrics["deliverable_reminders"] += bool(event["missing"])
            if event["event"] == "submission_check":
                states = [value["state"] for value in event["state"].values()]
                metrics["submission_check_opportunities"] += len(states)
                metrics["stale_at_submission"] += states.count("stale")
    keys = ("model_calls", "model_responses", "model_request_retries", "model_request_timeouts",
            "provider_turns", "tool_calls", "input_tokens", "output_tokens", "cached_input_tokens",
            "submission_check_opportunities", "stale_at_submission", "deliverable_checkpoints", "deliverable_reminders")
    return {key: metrics[key] for key in keys} | {
        "provider_reported_cost_usd": sum(reported_cost) if reported_cost else None,
    }


def grader_seconds(directory: Path, result: dict) -> float | None:
    if result.get("harbor_result"):
        details = json.loads((directory / result["harbor_result"]).read_text())
        verifier = details.get("verifier") or {}
        if verifier.get("started_at") and verifier.get("finished_at"):
            return (datetime.fromisoformat(verifier["finished_at"]) - datetime.fromisoformat(verifier["started_at"])
                    ).total_seconds()
    return result.get("grader_seconds")


def read_runs(root: Path) -> list[dict]:
    rows = []
    for path in sorted(root.glob("*/trial.json")):
        trial = json.loads(path.read_text())
        if trial["phase"] != "formal":
            continue
        run_dir = path.parent
        task = trial["task"]
        result_path = run_dir / "result.json"
        result = json.loads(result_path.read_text()) if result_path.is_file() else {}
        trajectory = next(run_dir.rglob("agent.json"), None) if result else None
        info = json.loads(trajectory.read_text())["info"] if trajectory else {}
        status = info.get("exit_status", result.get("exit_status", ""))
        submission = info.get("submission", result.get("submission", ""))
        rows.append({
            "run_id": run_dir.name, "benchmark": task["benchmark"], "split": task["split"], "task": task["id"],
            "arm": trial["configuration"], "repeat": int(run_dir.name.rsplit("-r", 1)[-1]),
            "request_retry_allowance": trial["limits"].get("timeout_retries", 0),
            "scoreable": result.get("scoreable", False),
            "passed": result.get("passed"), "exit_status": status,
            "declared_complete": status == "Submitted" and not submission.startswith("PARTIAL:"),
            "wall_seconds": result.get("wall_seconds"), "grader_seconds": grader_seconds(run_dir, result),
            **run_metrics(run_dir, complete=bool(result)),
        })
    return rows


def compare(rows: list[dict], split: str, reference: str, treatment: str, repetitions: int,
            *, expected_tasks: int | None = None) -> dict:
    scores = defaultdict(list)
    interrupted = set()
    for row in rows:
        if row["split"] == split and row["scoreable"]:
            scores[(row["benchmark"], row["task"], row["arm"])].append(int(row["passed"]))
            if (row["exit_status"] == "ProviderTimeout" or row["model_request_timeouts"]) and row["arm"] in {reference, treatment}:
                interrupted.add((row["benchmark"], row["task"]))
    paired = []
    for benchmark, task in sorted({key[:2] for key in scores}):
        first, second = scores[(benchmark, task, reference)], scores[(benchmark, task, treatment)]
        if len(first) == len(second) == repetitions:
            paired.append({"benchmark": benchmark, "task": task, "reference": first, "treatment": second,
                           "change": mean(second) - mean(first), "provider_timeout": (benchmark, task) in interrupted})
    counts = Counter()
    strata = defaultdict(list)
    for item in paired:
        change = item["change"]
        if change > 0:
            counts["gain"] += 1
        elif change < 0:
            counts["loss"] += 1
        else:
            count = sum(item["reference"])
            counts["both_success" if count == repetitions else "both_failure" if count == 0 else "tie_partial"] += 1
        strata[item["benchmark"]].append(change)
    interval = None
    expected = expected_tasks if expected_tasks is not None else (30 if split == "D" else 15)
    if len(paired) == expected:
        # 按基准分层重采样题目，保留同题的配置配对和重复结构。
        rng = Random(20261104)
        samples = sorted(100 * mean(value for group in strata.values() for value in rng.choices(group, k=len(group)))
                         for _ in range(10_000))
        interval = [samples[250], samples[9749]]
    delta = 100 * mean(row["change"] for row in paired) if paired else None
    rate = mean(mean(row["reference"]) for row in paired) if paired else None
    stable = [row["change"] for row in paired if not row["provider_timeout"]]
    return {"split": split, "reference": reference, "treatment": treatment, "paired_tasks": len(paired),
            "changes": dict(counts), "delta_percentage_points": delta, "relative_change_percent": delta / rate if rate else None,
            "pairs_without_provider_timeout": len(stable),
            "delta_without_provider_timeout_percentage_points": 100 * mean(stable) if stable else None,
            "bootstrap_95_interval_percentage_points": interval, "pairs": paired}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--runs", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    tasks = json.loads(args.manifest.read_text())["selected"]
    planned = Counter((row["split"], row["benchmark"], arm) for phase in ("diagnose", "compare", "holdout")
                      for row, arm, _ in slots(tasks, phase))
    rows = read_runs(args.runs)
    coverage = []
    for (split, benchmark, arm), expected in sorted(planned.items()):
        matches = [row for row in rows if (row["split"], row["benchmark"], row["arm"]) == (split, benchmark, arm)]
        scored = [row for row in matches if row["scoreable"]]
        success = sum(row["passed"] is True for row in scored)
        completed = [row for row in scored if row["declared_complete"]]
        by_task = defaultdict(list)
        for row in scored:
            by_task[row["task"]].append(row["passed"])
        repetitions = 3 if split == "H" else 1
        complete_tasks = [results for results in by_task.values() if len(results) == repetitions]
        timing = [row["grader_seconds"] for row in matches if row["grader_seconds"] is not None]
        cost = [row["provider_reported_cost_usd"] for row in matches]
        total_cost = sum(cost) if cost and all(item is not None for item in cost) else None
        coverage.append({"split": split, "benchmark": benchmark, "arm": arm, "planned": expected,
                         "started": len(matches), "scoreable": len(scored), "success": success,
                         "success_rate_on_scoreable": success / len(scored) if scored else None,
                         "expected_tasks": expected // repetitions, "fully_scored_tasks": len(complete_tasks),
                         "task_mean_success": mean(mean(task) for task in complete_tasks) if complete_tasks else None,
                         "all_repeats_successful": sum(all(task) for task in complete_tasks),
                         "declared_complete": len(completed),
                         "incorrect_complete_claims": sum(row["passed"] is False for row in completed),
                         "budget_terminations": sum(row["exit_status"] in {"LimitsExceeded", "TimeExceeded"} for row in matches),
                         "provider_timeouts": sum(row["exit_status"] == "ProviderTimeout" for row in matches),
                         "recorded_wall_seconds": sum(row["wall_seconds"] or 0 for row in matches),
                         "recorded_grader_seconds": sum(timing) if timing else None,
                         "provider_reported_cost_usd": total_cost,
                         "provider_reported_cost_per_success_usd": total_cost / success if total_cost is not None and success else None,
                         **{key: sum(row[key] for row in matches) for key in ("model_calls", "model_responses", "model_request_retries",
                             "model_request_timeouts", "tool_calls", "input_tokens", "output_tokens", "cached_input_tokens",
                             "stale_at_submission", "submission_check_opportunities",
                             "deliverable_checkpoints", "deliverable_reminders")}})
    args.out.mkdir(parents=True, exist_ok=True)
    controls = ("B0", "BP", "A")
    result = {"coverage": coverage, "comparisons": [compare(rows, "D", "B0", "F", 1),
              *[compare(rows, "H", baseline, "F", 3) for baseline in controls]],
              "holdout_by_repeat": [compare([row for row in rows if row["repeat"] == repeat], "H", baseline, "F", 1)
                                    | {"repeat": repeat} for repeat in (1, 2, 3) for baseline in controls]}
    (args.out / "summary.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    if rows:
        with (args.out / "trials.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    print(json.dumps({"planned": sum(planned.values()), "started": len(rows),
                      "scoreable": sum(row["scoreable"] for row in rows)}))


if __name__ == "__main__":
    main()
