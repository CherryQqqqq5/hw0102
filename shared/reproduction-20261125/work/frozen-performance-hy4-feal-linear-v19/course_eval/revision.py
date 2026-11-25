import argparse
import json
import os
import subprocess
import sys
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from pathlib import Path

from course_eval.agent import RunLimits
from course_eval.inventory import order


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--sources", type=Path, required=True)
    parser.add_argument("--checks", type=Path, required=True)
    parser.add_argument("--runs", type=Path, required=True)
    parser.add_argument("--arms", nargs="+", choices=("B0", "BP", "A", "F", "R", "RP"), required=True)
    parser.add_argument("--split", choices=("D", "H"), default="D")
    parser.add_argument("--task", action="append")
    parser.add_argument("--selection", type=Path)
    parser.add_argument("--repeats", type=int, choices=(1, 2, 3), default=1)
    parser.add_argument("--workers", type=int, choices=(1, 2, 3, 4), default=2)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    tasks = [item for item in manifest["selected"] if item["split"] == args.split]
    if args.task and args.selection:
        parser.error("Use either --task or --selection")
    requested = set(json.loads(args.selection.read_text())) if args.selection else set(args.task or [])
    if requested:
        if requested - {task["id"] for task in tasks}:
            raise ValueError("Requested task is outside the selected split")
        tasks = [task for task in tasks if task["id"] in requested]
    limits = RunLimits.model_validate_json(os.environ["COURSE_RUN_LIMITS"])
    slots = [(task, arm, repeat) for repeat in range(1, args.repeats + 1)
             for task in sorted(tasks, key=lambda task: order("revision/" + task["id"]))
             for arm in sorted(args.arms, key=lambda arm: order(f"revision/{repeat}/{task['id']}/{arm}"))]
    plan = {"model": os.environ["COURSE_MODEL_ID"], "backend": os.environ["COURSE_MODEL_BACKEND"],
            "limits": limits.model_dump(), "slots": [{"task": task["id"], "arm": arm, "repeat": repeat}
                                                       for task, arm, repeat in slots]}
    args.runs.mkdir(parents=True, exist_ok=True)
    plan_path = args.runs / "run-plan.json"
    if plan_path.exists() and json.loads(plan_path.read_text()) != plan:
        raise ValueError("The existing run plan differs")
    plan_path.write_text(json.dumps(plan, indent=2) + "\n")

    def run_one(slot):
        task, arm, repeat = slot
        run_id = f"{task['split']}-{task['benchmark']}-{task['id'].replace('/', '__')}-{arm}-r{repeat}"
        run_dir = args.runs / run_id
        if run_dir.exists():
            result = json.loads((run_dir / "result.json").read_text())
            trial = json.loads((run_dir / "trial.json").read_text())
            if (not result["scoreable"] or trial["model"] != plan["model"]
                    or trial["backend"] != plan["backend"] or trial["limits"] != plan["limits"]):
                raise ValueError(f"Cannot reuse mismatched or unscoreable trial: {run_id}")
            return
        print("START " + run_id, flush=True)
        subprocess.run([sys.executable, "-m", "course_eval.benchmarks", "--manifest", str(args.manifest),
                        "--sources", str(args.sources), "--checks", str(args.checks), "--id", task["id"],
                        "--configuration", arm, "--run-dir", str(run_dir)], check=True)
        result = json.loads((run_dir / "result.json").read_text())
        if not result["scoreable"]:
            raise RuntimeError(f"Unscoreable trial: {run_id}")
        print(f"DONE {run_id} passed={result['passed']}", flush=True)

    queue = iter(slots)
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        active = {executor.submit(run_one, slot) for _, slot in zip(range(args.workers), queue)}
        while active:
            completed, active = wait(active, return_when=FIRST_COMPLETED)
            for future in completed:
                future.result()
            for _, slot in zip(completed, queue):
                active.add(executor.submit(run_one, slot))


if __name__ == "__main__":
    main()
