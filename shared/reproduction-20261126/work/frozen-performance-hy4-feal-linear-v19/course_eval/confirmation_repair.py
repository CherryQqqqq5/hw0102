import argparse
import json
import os
import shutil
from pathlib import Path

from course_eval.aider_runtime import PYTHON_SHA256
from course_eval.confirmation import prepare
from course_eval.summarize import read_runs


def copy_record(source, destination):
    shutil.copytree(source, destination, copy_function=os.link, symlinks=True)


def main():
    parser = argparse.ArgumentParser()
    for name in ("manifest", "checks", "preflights", "legacy-runs", "source-runs", "source-plan", "interrupted-runs", "runs", "previous-out", "plan"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    if any(path.exists() for path in (args.runs, args.previous_out, args.plan)):
        raise FileExistsError("Preserve previous preparation; use new output paths")
    rows = read_runs(args.source_runs)
    if len(rows) != 86 or any(not row["scoreable"] for row in rows):
        raise ValueError("The observed v2 boundary must contain exactly 86 scored records")
    replacement = {"javascript/house", "javascript/sum-of-multiples"}
    replaced = [row for row in rows if row["task"] in replacement]
    if len(replaced) != 6 or {(row["task"], row["arm"]) for row in replaced} != {
            (task, arm) for task in replacement for arm in ("B0", "C0", "C1")}:
        raise ValueError("Affected tasks require complete three-arm replacement")
    for row in replaced:
        if row["arm"] == "B0":
            continue
        result = json.loads((args.source_runs / row["run_id"] / "result.json").read_text())
        if (row["model_calls"] != 0 or result.get("exit_status") != "CandidateOperationError"
                or "python3" not in result.get("controller_error", "")):
            raise ValueError("The replacement cause differs from missing Python")
    interrupted = read_runs(args.interrupted_runs)
    if len(interrupted) != 1 or interrupted[0]["scoreable"]:
        raise ValueError("Exactly one interrupted, unscored attempt must be preserved")
    previous_count = len(read_runs(args.legacy_runs)) + len(replaced) + len(interrupted)
    prepare(args.manifest, args.checks, args.preflights, args.plan, 300 - previous_count)
    plan = json.loads(args.plan.read_text())
    previous_plan = json.loads(args.source_plan.read_text())
    for key in ("model", "backend", "codebuddy_version", "python_version", "package_versions", "limits",
                "manifest_sha256", "checks_sha256", "slots"):
        if plan[key] != previous_plan[key]:
            raise ValueError("Source protocol differs beyond the runtime repair: " + key)
    args.runs.mkdir()
    args.previous_out.mkdir()
    reused = [row for row in rows if row["task"] not in replacement]
    for row in reused:
        source = args.source_runs / row["run_id"]
        copy_record(source, args.runs / row["run_id"])
        trial = json.loads((source / "trial.json").read_text())
        slot = next(slot for slot in plan["slots"] if slot["run_id"] == row["run_id"])
        slot.update(source_batch=args.source_runs.name, source_protocol_commit=trial["protocol_commit"])
    for row in replaced:
        copy_record(args.source_runs / row["run_id"], args.previous_out / row["run_id"])
    for row in interrupted:
        copy_record(args.interrupted_runs / row["run_id"], args.previous_out / row["run_id"])
    plan.update(reused_slots=len(reused), new_slots=270 - len(reused),
                replaced_tasks=sorted(replacement), previous_attempt_count=previous_count,
                cumulative_attempt_cap=300, aider_public_python_sha256=PYTHON_SHA256,
                repair="Add the same ARM Python runtime to every JavaScript arm; retain all unaffected valid scores")
    args.plan.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"reused": len(reused), "new": 270 - len(reused), "previous_attempts": previous_count,
                      "queue_attempt_cap": plan["max_total_attempts"]}))


if __name__ == "__main__":
    main()
