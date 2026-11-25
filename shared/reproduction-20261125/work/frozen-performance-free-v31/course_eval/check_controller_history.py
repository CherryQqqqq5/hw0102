import argparse
import json
from pathlib import Path

from course_eval.agent import RunLimits
from course_eval.benchmarks import SWE_HIDDEN_CACHES, aider_source, check_swe_checkout, prepare_aider, score_aider
from course_eval.controller import Budget, BoundedTarget, ControlledEnvironment, run_controlled
from course_eval.docker_target import DockerTarget
from course_eval.verification import PublicCheck


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    tasks = {row["id"]: row for row in json.loads(Path("work/frozen.json").read_text())["selected"]}
    cases = [("pydata__xarray-6599", "xarray/core/computation.py", "xarray/tests/test_computation.py", " -k polyval", "stale"),
             ("pytest-dev__pytest-7205", "src/_pytest/setuponly.py", "testing/test_setuponly.py", "", "protected_dependency_changed")]
    records = []
    for identifier, source, tests, selector, expected in cases:
        task = tasks[identifier]
        folder = args.out / identifier
        folder.mkdir()
        historical = Path("work/vmshare/revision-pilot-v1") / ("D-swe-" + identifier + "-R-r1/candidate.patch")
        check = PublicCheck("historical-suite", "public regression", "/opt/miniconda3/envs/testbed/bin/python -m pytest -q " + tests + selector,
                            (source, tests))
        with DockerTarget(task["image"], "/testbed", platform="linux/amd64", memory_mb=3072, cpus=2,
                          read_only_empty_dirs=SWE_HIDDEN_CACHES) as target:
            check_swe_checkout(task, target, folder)
            budget = Budget(180)
            env = ControlledEnvironment(BoundedTarget(target, budget), folder, RunLimits(wall_seconds=180), (check,),
                                        {"kind": "repository", "python": "/opt/miniconda3/envs/testbed/bin/python"}, budget, True)
            before = env.verify(check.check_id, "historical_initial")
            assert before["state"] == "passed", before
            target.upload_file(historical.resolve(), "/historical-candidate.patch")
            assert target.exec("git apply /historical-candidate.patch", timeout=10)["returncode"] == 0
            after = env.status()[1][check.check_id]
            assert after["state"] == expected, after
            records.append({"task": identifier, "historical_patch": str(historical), "before": before["state"], "after": after})
    folder = args.out / "initialization-failure"
    folder.mkdir()
    task = {"id": "python/proverb", "stratum": "python"}
    starter = folder / "starter"
    instruction, files = prepare_aider(task, aider_source(task, Path("work/datasets")), starter)
    check = PublicCheck("suite", "Original tests are available.", "python -m pytest", tuple(files))
    with DockerTarget("nju-course-aider:python", "/exercise", platform="linux/arm64", memory_mb=1024, cpus=1) as target:
        target.upload_tree(starter)
        result = run_controlled(instruction, target, folder, RunLimits(strict_wall=True), "C1", (check,),
                                {"kind": "files", "artifacts": files, "python": "/unavailable-course-python"})
        assert result["exit_status"] == "CandidateOperationError", result
        candidate = folder / "candidate"
        for name in files:
            assert target.download_file(name, candidate / name)
    grade = score_aider(task, starter, candidate, folder, "nju-course-aider:python")
    assert grade["scoreable"] and grade["passed"] is False, grade
    result = {"engineering_check": "pass", "model_requests": 0, "formal_benchmark_trial": False,
              "historical_cases": records, "initialization_error": result, "actual_grading_after_error": grade}
    (args.out / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
