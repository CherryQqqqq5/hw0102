import argparse
import json
import shutil
from pathlib import Path

from course_eval.aider_runtime import prepare_aider_runtime
from course_eval.benchmarks import AIDER_TESTS, aider_cwd, aider_source, prepare_aider, score_aider
from course_eval.controller import Budget, BoundedTarget, CandidateStore
from course_eval.docker_target import DockerTarget


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--sources", type=Path, default=Path("work/datasets"))
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    cases = []
    for task in json.loads(args.manifest.read_text())["selected"]:
        if task["benchmark"] != "aider":
            continue
        directory = args.out / task["id"].replace("/", "__")
        directory.mkdir()
        original = aider_source(task, args.sources)
        starter = directory / "starter"
        _, files = prepare_aider(task, original, starter)
        image = "nju-course-aider:" + task["stratum"]
        with DockerTarget(image, aider_cwd(task), platform="linux/arm64", memory_mb=2048, cpus=1) as target:
            target.upload_tree(starter)
            runtime = prepare_aider_runtime(target, task["stratum"])
            budget = Budget(120)
            scope = {"kind": "files", "artifacts": files,
                     "protected": [str(path.relative_to(starter)) for path in starter.rglob("*")
                                   if path.is_file() and str(path.relative_to(starter)) not in files]}
            store = CandidateStore(BoundedTarget(target, budget), directory, scope, budget)
            assert store.trusted(store.capture())
            case = {"task": task["id"], "initialization": "passed", "runtime": runtime,
                    "image_id": target.image}
            if task["stratum"] == "javascript":
                before = target.exec(AIDER_TESTS["javascript"], timeout=60)
                assert before["returncode"] == 1, before
                meta = json.loads((original / ".meta/config.json").read_text())["files"]
                reference = directory / "upstream-reference"
                shutil.copytree(starter, reference)
                for destination, source in zip(meta["solution"], meta["example"], strict=True):
                    shutil.copyfile(original / source, reference / destination)
                    target.upload_file((reference / destination).resolve(), target.cwd + "/" + destination)
                after = target.exec(AIDER_TESTS["javascript"], timeout=60)
                assert after["returncode"] == 0, after
                assert store.trusted(store.capture())
                negative = score_aider(task, starter, starter, directory / "negative", image)
                positive = score_aider(task, starter, reference, directory / "positive", image)
                assert negative["scoreable"] and negative["passed"] is False, negative
                assert positive["scoreable"] and positive["passed"] is True, positive
                case.update(public_starter_returncode=before["returncode"], public_reference_returncode=after["returncode"],
                            original_starter=negative, original_reference=positive)
            cases.append(case)
            print(json.dumps({"task": task["id"], "initialization": "passed"}), flush=True)
    report = {"model_requests": 0, "formal_benchmark_trial": False, "cases": cases}
    (args.out / "result.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"validated": len(cases), "model_requests": 0}))


if __name__ == "__main__":
    main()
