import argparse
import json
import shutil
from collections import Counter
from pathlib import Path

from minisweagent.exceptions import Submitted

from course_eval.agent import RunLimits, SUBMIT, TracedEnvironment
from course_eval.benchmarks import aider_source, prepare_aider, write_json
from course_eval.docker_target import DockerTarget
from course_eval.verification import PublicCheck, VerificationState


parser = argparse.ArgumentParser()
parser.add_argument("--runs", type=Path, required=True)
parser.add_argument("--sources", type=Path, required=True)
parser.add_argument("--out", type=Path, required=True)
args = parser.parse_args()
root = args.out.resolve()
root.mkdir(parents=True, exist_ok=False)
counts = Counter(RunLimits.model_validate(json.loads(path.read_text())["limits"]).timeout_retries
                 for path in args.runs.glob("*/trial.json"))
assert counts == {0: 109, 2: 131}, counts
task = {"id": "python/proverb", "stratum": "python"}
original = aider_source(task, args.sources.resolve())
files = json.loads((original / ".meta/config.json").read_text())["files"]
artifact, = files["solution"]
reference, = files["example"]
initial = root / "starter"
prepare_aider(task, original, initial)
shutil.copyfile(original / reference, initial / artifact)
check = PublicCheck("suite", "Original tests are available.", "python -m pytest", tuple(files["solution"] + files["test"]))
for name in ("R", "RP"):
    (root / name).mkdir()
with DockerTarget("nju-course-aider:python", "/exercise", platform="linux/arm64", memory_mb=1024, cpus=1) as target:
    target.upload_tree(initial)
    env = TracedEnvironment(target, root / "R", RunLimits(), VerificationState((check,), invalidate=True),
                            automatic_checks=True, budget_feedback=True)
    control = TracedEnvironment(target, root / "RP", RunLimits(), VerificationState((check,), invalidate=True),
                                budget_feedback=True)
    assert env.execute({"command": "cd /exercise && python -m pytest && echo PUBLIC_CHECK_OK"})["returncode"] == 0
    assert control.execute({"command": "echo " + SUBMIT})["returncode"] == 2
    try:
        env.execute({"command": "echo " + SUBMIT})
    except Submitted:
        pass
    else:
        raise AssertionError("Automatic check should permit the tested solution")
    target.docker("cp", str(original / artifact), f"{target.container}:/exercise/{artifact}")
    output = env.execute({"command": "echo " + SUBMIT})
    assert output["returncode"] == 2 and "failed" in output["output"]
    target.docker("cp", str(original / reference), f"{target.container}:/exercise/{artifact}")
    try:
        env.execute({"command": "echo " + SUBMIT})
    except Submitted:
        pass
    else:
        raise AssertionError("Repaired solution should pass its fresh automatic check")
events = [json.loads(line) for line in (root / "R/verification.jsonl").read_text().splitlines()]
automatic = [event for event in events if event["event"] == "automatic_public_check"]
assert [event["returncode"] for event in automatic] == [0, 1, 0]
write_json(root / "result.json", {"engineering_check": "pass", "historical_retry_allowance": dict(counts),
                                  "actual_check_exit_codes": [0, 1, 0], "model_requests": 0,
                                  "formal_benchmark_trial": False})
print((root / "result.json").read_text())
