import argparse
import json
from pathlib import Path

from course_eval.agent import RunLimits
from course_eval.controller import run_controlled
from course_eval.docker_target import DockerTarget
from course_eval.summarize import run_metrics
from course_eval.verification import PublicCheck


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    records = []
    instruction = ("Write answer.txt containing exactly the lowercase word ready without a newline. "
                   "Check the file contents and finish the task. Preserve all existing files.")
    check = PublicCheck("answer", "Write answer.txt containing exactly the lowercase word ready without a newline.",
                        "test -f answer.txt && test \"$(cat answer.txt)\" = ready && test \"$(wc -c < answer.txt)\" -eq 5",
                        ("answer.txt",), deliverables=("answer.txt",))
    for arm in ("B0", "C0", "C1"):
        directory = args.out / arm
        directory.mkdir()
        limits = RunLimits(model_calls=4, wall_seconds=120, command_seconds=15,
                           max_output_tokens=32768, strict_wall=True)
        with DockerTarget("nju-course-aider:python", "/exercise", platform="linux/arm64",
                          memory_mb=1024, cpus=1) as target:
            outcome = run_controlled(instruction, target, directory, limits, arm, (check,),
                                     {"kind": "files", "artifacts": ["answer.txt"]})
            actual = target.exec("cat answer.txt", timeout=5)
            budget = json.loads((directory / "execution-budget.json").read_text())
            assert actual["returncode"] == 0 and actual["stdout"] == "ready", (arm, outcome, actual)
            assert budget["elapsed_seconds"] < limits.wall_seconds, budget
            assert outcome["exit_status"] in {"Submitted", "ControllerFinalized"}, outcome
            records.append({"arm": arm, "actual_synthetic_artifact_correct": True,
                            "execution_budget": budget, "outcome": outcome})
    usage = run_metrics(args.out)
    assert usage["model_calls"] <= 12 and usage["model_request_retries"] == 0, usage
    result = {"engineering_check": "pass", "formal_benchmark_trial": False,
              "data": "synthetic five-byte file task", "cases": records, "usage": usage}
    (args.out / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
