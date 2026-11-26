import argparse
import json
from pathlib import Path

from course_eval.agent import RunLimits
from course_eval.benchmarks import SWE_HIDDEN_CACHES, check_swe_checkout
from course_eval.controller import Budget, BoundedTarget, ControlledEnvironment, ControlAction
from course_eval.docker_target import DockerTarget
from course_eval.verification import PublicCheck


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    manifest = json.loads(Path("work/frozen.json").read_text())
    task = next(row for row in manifest["selected"] if row["id"] == "scikit-learn__scikit-learn-14496")
    historical = Path("work/vmshare/revision-matched-R-v1/D-swe-scikit-learn__scikit-learn-14496-R-r1/candidate.patch")
    check = PublicCheck("optics", "public regression", "/opt/miniconda3/envs/testbed/bin/python -m pytest -q sklearn/cluster/tests/test_optics.py",
                        ("sklearn/cluster/optics_.py", "sklearn/cluster/tests/test_optics.py"))
    scope = {"kind": "repository", "python": "/opt/miniconda3/envs/testbed/bin/python"}
    with DockerTarget(task["image"], "/testbed", platform="linux/amd64", memory_mb=3072, cpus=2,
                      read_only_empty_dirs=SWE_HIDDEN_CACHES) as target:
        check_swe_checkout(task, target, args.out)
        budget = Budget(180)
        env = ControlledEnvironment(BoundedTarget(target, budget), args.out, RunLimits(wall_seconds=180),
                                    (check,), scope, budget, True)
        target.docker("cp", str(historical.resolve()), target.container + ":/historical-candidate.patch")
        assert target.exec("git apply /historical-candidate.patch", timeout=10)["returncode"] == 0
        verified = env.verify("optics", "requested")
        assert verified["state"] == "passed", verified
        first = env.store.candidates[-1]
        env.execute(ControlAction(operation="bash", command="printf '\\nnew unrelated change\\n' >> README.rst; printf 'new file\\n' > candidate-notes.txt; printf 'assert True\\n' > test_public_reproducer.py; printf 'new production source\\n' > new_source.py; git add -N new_source.py; git add test_public_reproducer.py").model_dump())
        restored = env.restore_candidate(first["candidate_id"])
        assert restored["artifact_digest"] == first["artifact_digest"]
        assert target.exec("test ! -e candidate-notes.txt && test ! -e test_public_reproducer.py && test ! -e new_source.py && git diff --quiet HEAD -- README.rst", timeout=10)["returncode"] == 0
        assert env.status()[1]["optics"]["state"] == "passed"
        env.execute(ControlAction(operation="bash", command="printf '[pytest]\\naddopts = --collect-only\\n' > pytest.ini").model_dump())
        assert env.status()[1]["optics"]["state"] == "protected_dependency_changed"
    result = {"engineering_check": "pass", "model_requests": 0, "formal_benchmark_trial": False,
              "historical_candidate": str(historical), "restores_previously_unseen_tracked_file": True,
              "removes_previously_unseen_new_file": True, "new_test_configuration_invalidates": True,
              "restores_after_new_staged_test_and_intent_to_add_source": True,
              "historical_public_suite_exit": verified["returncode"]}
    (args.out / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
