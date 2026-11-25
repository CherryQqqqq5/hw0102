import argparse
import json
import shutil
from pathlib import Path

from minisweagent.exceptions import Submitted

from course_eval.agent import RunLimits
from course_eval.benchmarks import aider_source, prepare_aider
from course_eval.controller import Budget, BoundedTarget, ControlAction, ControlledEnvironment
from course_eval.docker_target import DockerTarget
from course_eval.verification import PublicCheck


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sources", type=Path, default=Path("work/datasets"))
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    original = aider_source({"id": "python/proverb"}, args.sources)
    config = json.loads((original / ".meta/config.json").read_text())["files"]
    artifact, = config["solution"]
    reference, = config["example"]
    starter = args.out / "starter"
    instruction, files = prepare_aider({"id": "python/proverb", "stratum": "python"}, original, starter)
    shutil.copyfile(original / reference, starter / artifact)
    check = PublicCheck("suite", "Original tests are available.", "python -m pytest -q",
                        tuple(config["solution"] + config["test"]), coverage=("original visible test suite",))
    check.validate(instruction)
    scope = {"kind": "files", "artifacts": files, "protected": config["test"]}
    results = []
    for enabled in (False, True):
        folder = args.out / ("C1" if enabled else "C0")
        folder.mkdir()
        with DockerTarget("nju-course-aider:python", "/exercise", platform="linux/arm64", memory_mb=1024, cpus=1) as target:
            target.upload_tree(starter)
            budget = Budget(120)
            env = ControlledEnvironment(BoundedTarget(target, budget), folder, RunLimits(wall_seconds=120),
                                        (check,), scope, budget, enabled)
            pending = env.execute(ControlAction(operation="save").model_dump())
            assert '"eligible": false' in pending["output"]
            report = json.loads(env.execute(ControlAction(operation="verify", check_id="suite").model_dump())["output"].split("\nBudget:")[0])
            assert report["state"] == "passed"
            saved = env.execute(ControlAction(operation="save").model_dump())
            assert "candidate-002" in saved["output"]
            target.docker("cp", str(original / artifact), f"{target.container}:/exercise/{artifact}")
            assert env.status()[1]["suite"]["state"] == "stale"
            report = env.verify("suite", "requested")
            assert report["state"] == "failed"
            if enabled:
                final = env.finish("engineering_deadline")
                assert final["restored_candidate"] == "candidate-002" and final["valid_verification"]
                assert target.exec("python -m pytest -q", timeout=30)["returncode"] == 0
            else:
                final = env.finish("engineering_deadline")
                assert not final["valid_verification"] and final["restored_candidate"] is None
            results.append({"configuration": "C1" if enabled else "C0", **final})
    folder = args.out / "protected"
    folder.mkdir()
    with DockerTarget("nju-course-aider:python", "/exercise", platform="linux/arm64", memory_mb=1024, cpus=1) as target:
        target.upload_tree(starter)
        budget = Budget(120)
        env = ControlledEnvironment(BoundedTarget(target, budget), folder, RunLimits(), (check,), scope, budget, True)
        assert env.verify("suite", "requested")["state"] == "passed"
        test_file = config["test"][0]
        target.exec(f"printf '\\n# changed test dependency\\n' >> {test_file}", timeout=5)
        assert env.status()[1]["suite"]["state"] == "protected_dependency_changed"
        assert env.verify("suite", "requested")["state"] == "protected_dependency_changed"
    folder = args.out / "new-config"
    folder.mkdir()
    with DockerTarget("nju-course-aider:python", "/exercise", platform="linux/arm64", memory_mb=1024, cpus=1) as target:
        target.upload_tree(starter)
        budget = Budget(120)
        env = ControlledEnvironment(BoundedTarget(target, budget), folder, RunLimits(), (check,), scope, budget, True)
        assert env.verify("suite", "requested")["state"] == "passed"
        target.exec("printf '[pytest]\\naddopts = --collect-only\\n' > pytest.ini", timeout=5)
        assert env.status()[1]["suite"]["state"] == "protected_dependency_changed"
    folder = args.out / "deadline"
    folder.mkdir()
    slow = PublicCheck("suite", "Original tests are available.",
                       "if python -m pytest -q; then true; else sleep 60; exit 1; fi", check.dependencies)
    with DockerTarget("nju-course-aider:python", "/exercise", platform="linux/arm64", memory_mb=1024, cpus=1) as target:
        target.upload_tree(starter)
        budget = Budget(40)
        env = ControlledEnvironment(BoundedTarget(target, budget), folder, RunLimits(wall_seconds=40),
                                    (slow,), scope, budget, True)
        assert env.verify("suite", "requested")["state"] == "passed"
        target.docker("cp", str(original / artifact), f"{target.container}:/exercise/{artifact}")
        final = env.finish("engineering_short_deadline")
        assert final["restored_candidate"] == "candidate-001" and final["valid_verification"]
        assert final["elapsed_seconds"] < 40
        events = [json.loads(line) for line in (folder / "controller.jsonl").read_text().splitlines()]
        assert any(event.get("returncode") == 124 for event in events)
        results.append({"configuration": "C1-short-deadline", **final})
    for entry in ("final_phase", "requested"):
        folder = args.out / ("deadline-" + entry)
        folder.mkdir()
        with DockerTarget("nju-course-aider:python", "/exercise", platform="linux/arm64", memory_mb=1024, cpus=1) as target:
            target.upload_tree(starter)
            budget = Budget(62)
            env = ControlledEnvironment(BoundedTarget(target, budget), folder, RunLimits(wall_seconds=62),
                                        (slow,), scope, budget, True)
            assert env.verify("suite", "requested")["state"] == "passed"
            target.docker("cp", str(original / artifact), f"{target.container}:/exercise/{artifact}")
            if entry == "final_phase":
                env.before_decision(20)
                assert env.final_phase
            else:
                env.execute(ControlAction(operation="verify", check_id="suite").model_dump())
            final = env.finish("engineering_after_" + entry)
            assert final["restored_candidate"] == "candidate-001" and final["valid_verification"]
            assert final["elapsed_seconds"] < 62
            results.append({"configuration": "C1-deadline-" + entry, **final})
    result = {"engineering_check": "pass", "model_requests": 0, "formal_benchmark_trial": False,
              "real_fixture": "python/proverb starter and upstream reference", "comparisons": results,
              "protected_dependency_change_detected": True, "new_configuration_detected": True,
              "pending_candidate_upgraded": True, "timeout_then_recovery": True}
    (args.out / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
