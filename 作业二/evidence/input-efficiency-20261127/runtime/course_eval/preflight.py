import argparse
import json
import os
import shutil
from pathlib import Path

from course_eval.benchmarks import (aider_source, grade_swe, prepare_aider, prepare_terminal_task,
                                    score_aider, terminal_trial, write_json)


def aider_preflight(task: dict, sources: Path, destination: Path) -> dict:
    original = aider_source(task, sources)
    initial = destination / "starter"
    _, solution = prepare_aider(task, original, initial)
    config = json.loads((original / ".meta/config.json").read_text())["files"]
    image = f"nju-course-aider:{task['stratum']}"
    starter_dir = destination / "negative"
    starter_dir.mkdir()
    grade0 = score_aider(task, initial, starter_dir / "empty", starter_dir, image)
    result = {"original_starter": grade0}
    examples = config.get("example", [])
    if len(solution) == len(examples) == 1:
        mapping = dict(zip(solution, examples, strict=True))
    else:
        extensions = {Path(name).suffix: name for name in examples}
        matched = {name: extensions[Path(name).suffix] for name in solution if Path(name).suffix in extensions}
        complete = len(matched) == len(examples) == len(extensions) and set(matched.values()) == set(examples)
        mapping = matched if complete else {}
    if not mapping:
        raise ValueError(f"Cannot map the declared upstream examples to solution files: {solution}, {examples}")
    ref_dir = destination / "positive"
    ref_dir.mkdir()
    for name, example in mapping.items():
        candidate = ref_dir / "reference" / name
        candidate.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(original / example, candidate)
    result["upstream_reference"] = score_aider(task, initial, ref_dir / "reference", ref_dir, image)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--sources", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--id", required=True)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    task = next(row for row in manifest["inventory"] if row["id"] == args.id)
    args.out.mkdir(parents=True, exist_ok=False)
    if task["benchmark"] == "aider":
        result = aider_preflight(task, args.sources, args.out)
    elif task["benchmark"] == "swe":
        rows = json.loads((args.sources / "swe-grader.json").read_text())
        row = next(row for row in rows if row["instance_id"] == task["id"])
        result = {"original_starter": grade_swe(row, "", args.out / "negative"),
                  "upstream_reference": grade_swe(row, row["patch"], args.out / "positive")}
    else:
        result = {}
        for key, agent in (("original_starter", "nop"), ("upstream_reference", "oracle")):
            folder = args.out.resolve() / agent
            folder.mkdir()
            path = prepare_terminal_task(task, args.sources.resolve(), folder, oracle=agent == "oracle")
            result[key] = terminal_trial(path, folder, agent, os.environ)
    write_json(args.out / "preflight.json", {"task": task["id"], **result})
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
