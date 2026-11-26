import csv
import hashlib
import json
import statistics

from run_study import FOLDER, hashes, inspect, read, save


def summary(rows):
    passed = sum(row["passed"] for row in rows)
    tokens = sum(row["total_tokens"] for row in rows)
    times = [row["agent_seconds"] for row in rows]
    return {"completed": len(rows), "passed": passed, "tokens": tokens,
        "qualified_passed": sum(row["passed"] and (not row["final_control_applicable"]
            or row["final_valid_verification"] is True) for row in rows),
        "actual_requests": sum(row["actual_requests"] for row in rows),
        "tokens_per_passed_task": tokens / passed if passed else None,
        "median_agent_seconds": statistics.median(times), "max_agent_seconds": max(times)}


def eligible(group, baseline):
    return (group["qualified_passed"] == 6 and baseline["tokens_per_passed_task"] is not None
        and group["tokens_per_passed_task"] <= 0.9 * baseline["tokens_per_passed_task"]
        and group["median_agent_seconds"] <= 1.1 * baseline["median_agent_seconds"]
        and group["max_agent_seconds"] <= 1.1 * baseline["max_agent_seconds"])


def save_rows(rows):
    with (FOLDER / "joint-trials.csv").open("w") as handle:
        fields = ["stage", "task", "benchmark", "arm", "passed", "final_valid_verification", "actual_requests",
            "input_tokens", "output_tokens", "total_tokens", "agent_seconds", "wall_seconds", "run_dir"]
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def analyze():
    candidate = read(FOLDER / "candidate-tasks.json")
    if read(FOLDER / "study-plan.json")["source_hashes"] != hashes():
        raise RuntimeError("The actual study runtime changed after freezing")
    tasks = {row["id"]: row for row in candidate["selected"]}
    rows, sessions = [], set()
    for name in candidate["diagnostic_ids"]:
        for arm in ("base", "environment", "digest"):
            row = inspect(tasks[name], arm, FOLDER / "trials" / name / arm)
            row["stage"] = "diagnostic"
            if sessions.intersection(row["native_sessions"]):
                raise RuntimeError("Independent diagnostic positions reused a native session")
            sessions.update(row["native_sessions"])
            rows.append(row)
    digest_ok = all(row["passed"] and row["final_valid_verification"] is True
        for row in rows if row["arm"] == "digest")
    arms = ["dsh", "environment"] + (["digest"] if digest_ok else [])
    confirmation = []
    for name in candidate["confirmation_ids"]:
        for arm in arms:
            row = inspect(tasks[name], arm, FOLDER / "trials" / name / arm)
            row["stage"] = "confirmation"
            if sessions.intersection(row["native_sessions"]):
                raise RuntimeError("Independent confirmation positions reused a native session")
            sessions.update(row["native_sessions"])
            confirmation.append(row)
    rows.extend(confirmation)
    lookup = {(row["task"], row["arm"]): row for row in confirmation}
    by_configuration = {arm: summary([row for row in confirmation if row["arm"] == arm]) for arm in arms}
    maps = {arm: {name: arm for name in candidate["confirmation_ids"]} for arm in arms}
    for name, routing in candidate["routing_candidates"].items():
        mapping = {task: routing[tasks[task]["benchmark"]] for task in candidate["confirmation_ids"]}
        if all(arm in arms for arm in mapping.values()):
            maps[name] = mapping
            by_configuration[name] = summary([lookup[task, arm] for task, arm in mapping.items()])
    baseline = by_configuration["environment"]
    choices = [name for name, group in by_configuration.items()
        if name != "environment" and eligible(group, baseline)]
    chosen = min(choices, key=lambda name: by_configuration[name]["tokens"]) if choices else None
    result = {"stage": "complete", "diagnostic_digest_admitted": digest_ok, "rows": rows,
        "by_configuration": by_configuration, "chosen_configuration": chosen,
        "selection_rule": candidate["selection_rule"], "actual_model_task_trials": len(rows)}
    save(FOLDER / "study-results.json", result)
    save_rows(rows)
    if chosen is None:
        save(FOLDER / "repeat-results.json", {"stage": "not_started", "reason": "No registered configuration met the success, token and time criteria"})
        return
    plan = {"chosen_configuration": chosen, "configuration_by_task": maps[chosen],
        "baseline": baseline, "study_results_sha256": hashlib.sha256((FOLDER / "study-results.json").read_bytes()).hexdigest(),
        "adoption_rule": candidate["repeat_adoption_rule"], "maximum_independent_repeats": 6}
    path = FOLDER / "repeat-plan.json"
    if path.exists() and read(path) != plan:
        raise RuntimeError("A different repeat configuration was already frozen")
    save(path, plan)
    repeats = []
    for task, arm in maps[chosen].items():
        directory = FOLDER / "repeat" / task / arm
        if not (directory / "result.json").exists():
            return
        row = inspect(tasks[task], arm, directory)
        row["stage"] = "repeat"
        if sessions.intersection(row["native_sessions"]):
            raise RuntimeError("A repeat reused a prior native model session")
        sessions.update(row["native_sessions"])
        repeats.append(row)
    repeated = summary(repeats)
    save(FOLDER / "repeat-results.json", {"stage": "complete", "rows": repeats,
        "summary": repeated, "baseline": baseline, "adopt": eligible(repeated, baseline),
        "actual_model_task_trials": len(rows) + len(repeats)})
    save_rows(rows + repeats)


if __name__ == "__main__":
    analyze()
