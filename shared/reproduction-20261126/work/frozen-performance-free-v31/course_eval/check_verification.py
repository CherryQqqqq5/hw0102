import argparse
import json
import shutil
from pathlib import Path

from minisweagent.exceptions import Submitted

from course_eval.agent import RunLimits, SUBMIT, TracedEnvironment
from course_eval.benchmarks import AIDER_TESTS, aider_source, prepare_aider, write_json
from course_eval.docker_target import DockerTarget
from course_eval.verification import PublicCheck, VerificationState


def submit(environment: TracedEnvironment) -> bool:
    try:
        observation = environment.execute({"command": "echo " + SUBMIT})
    except Submitted:
        return True
    if observation["returncode"] != 2:
        raise AssertionError(observation)
    return False


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sources", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    task = {"id": "python/proverb", "stratum": "python"}
    original = aider_source(task, args.sources.resolve())
    config = json.loads((original / ".meta/config.json").read_text())["files"]
    artifact, = config["solution"]
    reference, = config["example"]
    initial = args.out / "workspace"
    instruction, _ = prepare_aider(task, original, initial)
    shutil.copyfile(original / reference, initial / artifact)
    command = AIDER_TESTS["python"]
    check = PublicCheck("public-suite", "Original tests are available.", command,
                        tuple(config["solution"] + config["test"]))
    check.validate(instruction)
    with DockerTarget("nju-course-aider:python", "/exercise", platform="linux/arm64", memory_mb=1024, cpus=1) as target:
        target.upload_tree(initial)
        limits = RunLimits()
        directories = [args.out / name for name in ("F", "A")]
        for directory in directories:
            directory.mkdir()
        full = TracedEnvironment(target, directories[0], limits, VerificationState((check,), invalidate=True))
        ablation = TracedEnvironment(target, directories[1], limits, VerificationState((check,), invalidate=False))
        assert not submit(full) and not submit(ablation)
        assert full.execute({"command": command})["returncode"] == 0
        assert ablation.execute({"command": command})["returncode"] == 0
        assert full.execute({"command": "printf 'diagnostic log\n' > run-notes.txt"})["returncode"] == 0
        assert submit(full) and submit(ablation)
        target.docker("cp", str(original / artifact), f"{target.container}:{target.cwd}/{artifact}")
        assert not submit(full) and submit(ablation)
        assert full.execute({"command": command})["returncode"] == 1
        assert not submit(full)
        target.docker("cp", str(original / reference), f"{target.container}:{target.cwd}/{artifact}")
        assert full.execute({"command": command})["returncode"] == 0
        assert submit(full)
    write_json(args.out / "result.json", {"engineering_check": "pass", "source": task["id"],
                                          "model_requests": 0, "formal_benchmark_trial": False})


if __name__ == "__main__":
    main()
