import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from course_eval.resource_pool import ResourceLease, task_requires_exclusive


parser = argparse.ArgumentParser()
parser.add_argument("--task", required=True)
parser.add_argument("--benchmark", required=True)
parser.add_argument("--image", required=True)
parser.add_argument("--expected-image-id", required=True)
parser.add_argument("--record", type=Path, required=True)
parser.add_argument("command", nargs=argparse.REMAINDER)
args = parser.parse_args()
command = args.command[1:] if args.command[:1] == ["--"] else args.command
if not command:
    raise ValueError("The resource admission must wrap an actual existing trial driver")
exclusive = task_requires_exclusive({"id": args.task, "benchmark": args.benchmark})
state = {"task": args.task, "benchmark": args.benchmark, "exclusive": exclusive,
    "requested_at": time.time(), "resource_wait_is_outside_original_task_budget": True}
args.record.parent.mkdir(parents=True, exist_ok=True)
args.record.write_text(json.dumps(state, indent=2) + "\n")
root = Path.cwd()
pool = root / "work/parallel-free-evaluation-20261124/resources"
for attempt in range(3):
    with ResourceLease(pool, exclusive=exclusive, label=args.task):
        inspected = subprocess.run([os.environ["COURSE_DOCKER_BIN"], "image", "inspect", "--format", "{{.Id}}", args.image],
            capture_output=True, text=True, check=False)
        if inspected.returncode == 0:
            if inspected.stdout.strip() != args.expected_image_id:
                raise RuntimeError("The leased task environment differs from its frozen original image")
            state.update(admitted_at=time.time(), actual_image_id=inspected.stdout.strip(), image_resolution_round=attempt)
            args.record.write_text(json.dumps(state, indent=2) + "\n")
            try:
                actual = subprocess.run(command, check=False)
                state.update(returncode=actual.returncode)
            finally:
                state.update(released_at=time.time())
                args.record.write_text(json.dumps(state, indent=2) + "\n")
            break
        if "No such image" not in inspected.stderr:
            inspected.check_returncode()
    with ResourceLease(pool, exclusive=True, label="restore-prepared-image-" + args.task):
        sys.path.insert(0, str(root))
        from scripts.run_performance_matrix import prepare_missing_image
        prepare_missing_image({"id": args.task, "benchmark": args.benchmark}, os.environ | {"PYTHONPATH": str(root)})
else:
    raise RuntimeError("The prepared image was repeatedly removed before task admission; no model request was started")
raise SystemExit(actual.returncode)
