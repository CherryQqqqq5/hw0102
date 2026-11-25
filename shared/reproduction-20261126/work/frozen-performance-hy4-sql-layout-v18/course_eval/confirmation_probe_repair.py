import argparse
import json
import os
import shutil
from dataclasses import asdict
from pathlib import Path

from course_eval.confirmation import prepare
from course_eval.confirmation_terminal_materials import terminal_check
from course_eval.inventory import REVISIONS
from course_eval.summarize import read_runs


def main():
    parser = argparse.ArgumentParser()
    for name in ("manifest", "source-checks", "checks", "preflights", "source-plan", "source-runs",
                 "runs", "previous-out", "plan"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--sources", type=Path, default=Path("work/datasets"))
    args = parser.parse_args()
    for destination in (args.checks, args.runs, args.previous_out, args.plan):
        if destination.exists():
            raise FileExistsError(destination)
    rows = read_runs(args.source_runs)
    if len(rows) != 36 or sum(row["scoreable"] for row in rows) != 35:
        raise ValueError("The preserved v4 boundary must contain 36 attempts and 35 scored records")
    task_id = "modernize-scientific-stack"
    replaced = [row for row in rows if row["task"] == task_id]
    if len(replaced) != 3 or {row["arm"] for row in replaced} != {"B0", "C0", "C1"}:
        raise ValueError("The affected task requires complete three-arm replacement")
    if any(not row["run_id"].endswith("-r1") for row in replaced):
        raise ValueError("The replacement boundary is the first repeat only")
    reused = [row for row in rows if row["task"] != task_id]
    if len(reused) != 33 or any(not row["scoreable"] for row in reused):
        raise ValueError("Every unaffected record must be preserved regardless of its score")
    source_plan = json.loads(args.source_plan.read_text())
    manifest = json.loads(args.manifest.read_text())
    task = next(task for task in manifest["selected"] if task["id"] == task_id)
    original = args.sources / f"terminal-bench-2-1-{REVISIONS['terminal']}" / "tasks" / task_id
    checks = json.loads(args.source_checks.read_text())
    checks[task_id] = [asdict(terminal_check(task, (original / "instruction.md").read_text()))]
    args.checks.write_text(json.dumps(checks, indent=2) + "\n")
    prepare(args.manifest, args.checks, args.preflights, args.plan,
            source_plan["max_total_attempts"] - len(replaced))
    plan = json.loads(args.plan.read_text())
    for key in ("model", "backend", "provider_profile", "python_version", "package_versions", "limits",
                "manifest_sha256", "slots"):
        if plan[key] != source_plan[key]:
            raise ValueError("The mechanical repair changed frozen settings: " + key)
    changed_runtime = {name for name, checksum in plan["runtime_sha256"].items()
                       if checksum != source_plan["runtime_sha256"][name]}
    if changed_runtime != {"benchmarks.py"}:
        raise ValueError("Unexpected execution source change: " + repr(changed_runtime))
    args.runs.mkdir()
    args.previous_out.mkdir()
    for row in reused:
        source = args.source_runs / row["run_id"]
        shutil.copytree(source, args.runs / row["run_id"], copy_function=os.link, symlinks=True)
        trial = json.loads((source / "trial.json").read_text())
        slot = next(slot for slot in plan["slots"] if slot["run_id"] == row["run_id"])
        slot.update(source_batch=args.source_runs.name, source_protocol_commit=trial["protocol_commit"])
    for row in replaced:
        shutil.copytree(args.source_runs / row["run_id"], args.previous_out / row["run_id"],
                        copy_function=os.link, symlinks=True)
    plan.update(reused_slots=len(reused), new_slots=270 - len(reused),
                replaced_tasks=[task_id], previous_attempt_count=len(replaced),
                previous_scored_count=sum(row["scoreable"] for row in replaced),
                cumulative_attempt_cap=source_plan["max_total_attempts"],
                parent_protocol_commit="a59144b",
                repair="Isolate climate probe argv and preserve metadata across SystemExit; allow Harbor setup and cleanup outside the unchanged strict internal budget")
    args.plan.write_text(json.dumps(plan, indent=2) + "\n")
    print(json.dumps({"reused": len(reused), "new": 270 - len(reused), "previous_attempts": len(replaced),
                      "queue_attempt_cap": plan["max_total_attempts"]}))


if __name__ == "__main__":
    main()
