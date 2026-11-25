import argparse
import json
import shutil
from pathlib import Path

from course_eval.export_revision import HOME_PATH, PRIVATE, PRIVATE_PEM, SECRET


CONTROL_FILES = {"preflight.json", "result.json", "report.json", "grader.json", "test_output.txt",
                 "test-stdout.txt", "reward.txt", "run_instance.log", "trial.log", "checkout.json"}


def copy_controls(source, destination):
    count = 0
    for path in sorted(source.rglob("*")):
        relative = path.relative_to(source)
        if not path.is_file() or path.is_symlink() or path.name not in CONTROL_FILES:
            continue
        if {"starter", "grader-input", "tests", "solution", "environment"}.intersection(relative.parts):
            continue
        content = HOME_PATH.sub("[本机路径]", PRIVATE_PEM.sub("[REDACTED BENCHMARK PRIVATE KEY]", path.read_text()))
        if SECRET.search(content) or PRIVATE.search(content):
            raise ValueError(f"Sensitive control content: {relative}")
        if path.suffix == ".json":
            json.loads(content)
        output = destination / relative
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(content)
        count += 1
    return count


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--preflights", type=Path, required=True)
    parser.add_argument("--swe-controls", type=Path, required=True)
    parser.add_argument("--terminal-controls", type=Path, required=True)
    parser.add_argument("--published-repo", type=Path, required=True)
    args = parser.parse_args()
    evidence = args.published_repo / "作业二/evidence"
    manifest = json.loads(args.manifest.read_text())
    count = 0
    for task in manifest["selected"]:
        name = task["id"].replace("/", "__")
        source = args.preflights / name
        control = json.loads((source / "preflight.json").read_text())
        if control["original_starter"]["passed"] is not False or control["upstream_reference"]["passed"] is not True:
            raise ValueError("Unqualified original grader control: " + name)
        count += copy_controls(source, evidence / "confirmation-preflights-v1" / name)
        if task["benchmark"] in {"swe", "terminal"}:
            source = (args.swe_controls if task["benchmark"] == "swe" else args.terminal_controls) / task["id"]
            count += copy_controls(source, evidence / "confirmation-public-controls-v1" / name)
    code = args.published_repo / "shared/course_eval"
    for source in Path(__file__).parent.iterdir():
        if source.is_file() and source.suffix in {".py", ".yaml"}:
            shutil.copy2(source, code / source.name)
    print(json.dumps({"control_files": count, "selected_tasks": len(manifest["selected"])}))


if __name__ == "__main__":
    main()
