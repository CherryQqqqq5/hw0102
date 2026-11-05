import argparse
import json
from pathlib import Path

from course_eval.controller import Budget, BoundedTarget, CandidateOperationError, CandidateStore
from course_eval.docker_target import DockerTarget


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--expect-failure", action="store_true")
    parser.add_argument("--manifest", type=Path, default=Path("work/confirmation-frozen-v1.json"))
    parser.add_argument("--fixture-directory", type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    tasks = json.loads(args.manifest.read_text())["selected"]
    tasks = [task for task in tasks if task["benchmark"] == "swe"
             and (not args.expect_failure or task["id"] == "django__django-11999")]
    results = []
    for task in tasks:
        directory = args.out / task["id"]
        directory.mkdir()
        with DockerTarget(task["image"], "/testbed", platform="linux/amd64", memory_mb=1024, cpus=1) as target:
            budget = Budget(120)
            scope = {"kind": "repository", "python": "/opt/miniconda3/envs/testbed/bin/python"}
            try:
                store = CandidateStore(BoundedTarget(target, budget), directory, scope, budget)
            except CandidateOperationError as error:
                if not args.expect_failure or "UnicodeDecodeError" not in str(error):
                    raise
                results.append({"task": task["id"], "expected_failure_reproduced": True,
                                "error": str(error), "image_id": target.image})
                continue
            if args.expect_failure:
                raise AssertionError("Expected original locale failure did not occur")
            initial = store.capture()
            assert initial["files"] == {}
            first = store.save(initial, {"engineering": {"state": "pending"}})
            filename = "course_路径.txt"
            target.upload_file((args.fixture_directory / "locale-fixture-original.txt").resolve(), "/testbed/" + filename)
            captured = store.capture()
            assert filename in captured["files"] and store.trusted(captured)
            saved = store.save(captured, {"engineering": {"state": "pending"}})
            target.upload_file((args.fixture_directory / "locale-fixture-changed.txt").resolve(), "/testbed/" + filename)
            assert store.capture()["artifact_digest"] != saved["artifact_digest"]
            store.restore(saved["candidate_id"])
            assert store.capture()["artifact_digest"] == saved["artifact_digest"]
            store.restore(first["candidate_id"])
            assert store.capture()["artifact_digest"] == initial["artifact_digest"]
            assert target.exec("test ! -e " + filename, timeout=5)["returncode"] == 0
            results.append({"task": task["id"], "initial_capture_passed": True,
                            "unicode_candidate_roundtrip": True, "restore_initial_removed_new_file": True,
                            "pending_evidence_preserved": not saved["eligible"], "image_id": target.image})
    report = {"model_requests": 0, "formal_benchmark_trial": False, "cases": results}
    (args.out / "result.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
