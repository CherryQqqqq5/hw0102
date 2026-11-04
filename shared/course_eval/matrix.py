import argparse
import json
import os
import subprocess
import sys
from collections import Counter
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from pathlib import Path

from course_eval.inventory import order


def slots(tasks: list[dict], phase: str):
    if phase == "diagnose":
        yield from ((task, "B0", 1) for task in tasks if task["split"] == "D")
    elif phase == "compare":
        yield from ((task, "F", 1) for task in tasks if task["split"] == "D")
    else:
        for repeat in range(1, 4):
            for task in sorted((row for row in tasks if row["split"] == "H"),
                               key=lambda row: order(f"{repeat}/{row['id']}")):
                for arm in sorted(("B0", "BP", "A", "F"), key=lambda name: order(f"{repeat}/{task['id']}/{name}")):
                    yield task, arm, repeat


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--sources", required=True, type=Path)
    parser.add_argument("--runs", required=True, type=Path)
    parser.add_argument("--phase", required=True, choices=("diagnose", "compare", "holdout"))
    parser.add_argument("--checks", type=Path)
    parser.add_argument("--workers", type=int, choices=range(1, 5), default=1)
    parser.add_argument("--list", action="store_true")
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    tasks = manifest["selected"]
    for benchmark in ("swe", "terminal", "aider"):
        chosen = [row for row in tasks if row["benchmark"] == benchmark]
        if Counter(row["split"] for row in chosen) != {"D": 10, "H": 5}:
            raise ValueError(f"Invalid split sizes for {benchmark}")
        if len({row["group"] for row in chosen}) != 15:
            raise ValueError(f"Related tasks are duplicated in {benchmark}")
    if not args.list and manifest["stage"] != "frozen":
        parser.error("Only a preflight-verified frozen manifest can start formal trials")
    if not args.list and args.phase != "diagnose" and args.checks is None:
        parser.error("Comparison requires the check plans frozen after diagnosis")

    def run_one(task, arm, repeat):
        task_id = task["id"]
        run_id = f"{task['split']}-{task['benchmark']}-{task_id.replace('/', '__')}-{arm}-r{repeat}"
        if args.list:
            print(run_id)
            return
        run_dir = args.runs / run_id
        completed = run_dir / "result.json"
        if completed.exists():
            if json.loads(completed.read_text())["scoreable"]:
                trial = json.loads((run_dir / "trial.json").read_text())
                if trial.get("model") != os.environ["COURSE_MODEL_ID"] or trial.get("backend") != os.environ["COURSE_MODEL_BACKEND"]:
                    raise RuntimeError(f"The completed trial uses a different model configuration: {run_dir}")
                return
            raise RuntimeError(f"The existing run is not scoreable: {run_dir}")
        if run_dir.exists():
            raise RuntimeError(f"An earlier attempt is incomplete. Preserve it and diagnose: {run_dir}")
        command = [sys.executable, "-m", "course_eval.benchmarks", "--manifest", str(args.manifest),
                   "--sources", str(args.sources), "--id", task_id, "--configuration", arm,
                   "--run-dir", str(run_dir)]
        if args.checks:
            command.extend(["--checks", str(args.checks)])
        print(run_id, flush=True)
        subprocess.run(command, env=os.environ, check=True)
        if not json.loads(completed.read_text())["scoreable"]:
            raise RuntimeError(f"The run is not scoreable: {run_dir}")

    queue = iter(slots(tasks, args.phase))
    if args.list:
        for slot in queue:
            run_one(*slot)
        return
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        active = {executor.submit(run_one, *slot) for _, slot in zip(range(args.workers), queue)}
        while active:
            completed, active = wait(active, return_when=FIRST_COMPLETED)
            for future in completed:
                future.result()
            for _, slot in zip(completed, queue):
                active.add(executor.submit(run_one, *slot))


if __name__ == "__main__":
    main()
