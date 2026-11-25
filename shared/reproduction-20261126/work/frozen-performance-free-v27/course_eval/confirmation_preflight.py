import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from course_eval.inventory import REVISIONS
from course_eval.terminal_setup import dependency_key, offline_spec


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--sources", type=Path, default=Path("work/datasets"))
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--benchmark", choices=("swe", "terminal", "aider"))
    parser.add_argument("--task", action="append")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    tasks = json.loads(args.manifest.read_text())["selected"]
    docker = os.environ["COURSE_DOCKER_BIN"]
    for task in tasks:
        if ((args.benchmark and task["benchmark"] != args.benchmark)
                or (args.task and task["id"] not in args.task)):
            continue
        name = task["id"].replace("/", "__")
        directory = args.out / name
        if (directory / "preflight.json").exists():
            print("EXISTS " + name, flush=True)
            continue
        if directory.exists():
            print("INCOMPLETE " + name, flush=True)
            continue
        if task["benchmark"] == "terminal":
            script = args.sources / f"terminal-bench-2-1-{REVISIONS['terminal']}" / "tasks" / task["id"] / "tests/test.sh"
            try:
                interpreter, requirements, _ = offline_spec(script.read_text())
            except ValueError as exc:
                print("UNSUPPORTED " + name + " " + str(exc), flush=True)
                continue
            archive = Path(os.environ["COURSE_TERMINAL_DEPS"]) / (dependency_key(interpreter, requirements) + ".tar.gz")
            if not archive.exists():
                print("MISSING_DEPENDENCIES " + name + " " + archive.name, flush=True)
                continue
        image = task.get("image") or "nju-course-aider:" + task["stratum"]
        inspected = subprocess.run([docker, "image", "inspect", image], stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL, timeout=30)
        if inspected.returncode:
            if shutil.disk_usage(args.out).free < 8 * 1024**3:
                raise RuntimeError("Less than 8 GiB host space before a new image pull")
            with (args.out / (name + ".pull.log")).open("a") as log:
                subprocess.run([docker, "pull", "--platform", "linux/amd64", image], stdout=log,
                               stderr=log, timeout=2400, check=True)
        print("START " + name, flush=True)
        started = time.monotonic()
        with (args.out / (name + ".log")).open("a") as log:
            result = subprocess.run([sys.executable, "-m", "course_eval.preflight", "--manifest", str(args.manifest),
                                     "--sources", str(args.sources), "--id", task["id"], "--out", str(directory)],
                                    stdout=log, stderr=log, check=False)
        print(f"END {name} exit={result.returncode} seconds={time.monotonic()-started:.1f}", flush=True)


if __name__ == "__main__":
    main()
