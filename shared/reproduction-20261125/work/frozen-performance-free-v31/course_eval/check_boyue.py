import argparse
import json
import secrets
import shlex
from pathlib import Path

from minisweagent.config import builtin_config_dir, get_config_from_spec

from course_eval.agent import CourseModel, RunLimits, TracedEnvironment
from course_eval.controller import Budget, BoundedTarget, ControlledEnvironment, CourseControlModel
from course_eval.docker_target import DockerTarget
from course_eval.summarize import run_metrics
from course_eval.verification import PublicCheck


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    config = get_config_from_spec(builtin_config_dir / "mini.yaml")
    records = []
    for arm in ("B0", "C0", "C1"):
        directory = args.out / arm
        directory.mkdir()
        nonce = secrets.token_hex(12)
        limits = RunLimits(model_calls=2, wall_seconds=320, max_output_tokens=32768, strict_wall=True)
        with DockerTarget("nju-course-aider:python", "/exercise", platform="linux/arm64",
                          memory_mb=1024, cpus=1) as target:
            assert target.exec("printf '%s' " + shlex.quote(nonce) + " > fixture.txt", timeout=5)["returncode"] == 0
            budget = Budget(limits.wall_seconds)
            bounded = BoundedTarget(target, budget)
            if arm == "B0":
                model = CourseModel(directory, limits, config["model"]["observation_template"])
                environment = TracedEnvironment(bounded, directory, limits)
            else:
                model = CourseControlModel(directory, limits, config["model"]["observation_template"])
                check = PublicCheck("fixture-present", "Read fixture.txt.", "test -s fixture.txt", ("fixture.txt",))
                environment = ControlledEnvironment(bounded, directory, limits, (check,),
                    {"kind": "files", "artifacts": ["answer.txt"], "protected": ["fixture.txt"]}, budget, arm == "C1")
            model.budget = budget
            messages = [{"role": "system", "content":
                         "Use exactly one registered tool action per response. Execute the user's shell command. "
                         "For the action function choose operation bash."},
                        {"role": "user", "content": "Read fixture.txt. Execute exactly: cat fixture.txt"}]
            first = model.query(messages)
            output = environment.execute(first["extra"]["actions"][0])
            assert nonce in output["output"], output
            messages += [first, *model.format_observation_messages(first, [output])]
            messages.append({"role": "user", "content":
                "Using the value in the tool observation, execute one bash action that writes that exact "
                "value, without a newline, to answer.txt. Do not read fixture.txt again. Do not submit."})
            second = model.query(messages)
            output = environment.execute(second["extra"]["actions"][0])
            assert output["returncode"] == 0, output
            actual = target.exec("cat answer.txt", timeout=5)
            assert actual["returncode"] == 0 and actual["stdout"] == nonce, actual
            events = [json.loads(line) for line in (directory / "model.jsonl").read_text().splitlines()]
            responses = [event for event in events if event["event"] == "response"]
            requests = [event for event in events if event["event"] == "request"]
            first_message = responses[0]["payload"]["choices"][0]["message"]
            continued = requests[1]["payload"]["messages"][2]
            assert "reasoning_content" in first_message and first_message["reasoning_content"], first_message.keys()
            assert continued == first_message, "Assistant reasoning or tool call changed on continuation"
            assert all(event["payload"]["usage"]["completion_tokens"] > 0 for event in responses)
            records.append({"arm": arm, "two_request_tool_roundtrip": True,
                            "reasoning_preserved": True, "exact_synthetic_value": True,
                            "execution_seconds": limits.wall_seconds - budget.remaining()})
    result = {"engineering_check": "pass", "formal_benchmark_trial": False,
              "data": "synthetic random nonce in a network-disabled container", "cases": records,
              "usage": run_metrics(args.out)}
    (args.out / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
