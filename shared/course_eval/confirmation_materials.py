import argparse
import hashlib
import json
import os
import shlex
import subprocess
from dataclasses import asdict
from pathlib import Path

from course_eval.verification import PublicCheck
from course_eval.benchmarks import AIDER_TESTS, aider_source


SWE_FILES = {
    "django__django-11999": ("django/db/models/fields/__init__.py", "custom get_FIELD_display method is retained"),
    "django__django-12193": ("django/contrib/postgres/forms/array.py", "Boolean array checked states equal supplied values"),
    "django__django-14855": ("django/contrib/admin/helpers.py", "readonly foreign-key link uses custom AdminSite prefix"),
    "scikit-learn__scikit-learn-11310": ("sklearn/model_selection/_search.py", "refit_time_ is a nonnegative measured duration"),
    "scikit-learn__scikit-learn-13124": ("sklearn/model_selection/_split.py", "random seed changes sample partitions while preserving stratification"),
    "scikit-learn__scikit-learn-25232": ("sklearn/impute/_iterative.py", "explicit constant fill_value controls initial imputation"),
    "pydata__xarray-4687": ("xarray/core/computation.py", "where preserves attributes with the offered preservation option"),
    "pydata__xarray-7393": ("xarray/core/indexes.py", "stack keeps the public int32 coordinate dtype"),
    "pytest-dev__pytest-5631": ("src/_pytest/compat.py", "public numpy-array patch test collects and runs"),
    "pytest-dev__pytest-7490": ("src/_pytest/skipping.py", "dynamically added xfail marks the failing public example as xfailed"),
}


def swe_check(task, instruction):
    source = Path(__file__).with_name("confirmation_swe_checks.py").read_text()
    filename, coverage = SWE_FILES[task["id"]]
    quote = next(line.strip() for line in instruction.splitlines() if line.strip())
    command = shlex.join(("/opt/miniconda3/envs/testbed/bin/python", "-c", source, task["id"]))
    check = PublicCheck("public-issue", quote, command, (filename,), coverage=(coverage,), inconclusive_exit_codes=(124,))
    check.validate(instruction)
    return check


def aider_check(task, sources):
    original = aider_source(task, sources)
    files = json.loads((original / ".meta/config.json").read_text())["files"]
    solution = [name for name in files["solution"] if name not in {"CMakeLists.txt", "Cargo.toml"}]
    dependencies = tuple(dict.fromkeys(solution + files["test"] + files.get("invalidator", [])))
    coverage = "original visible tests; Java Disabled tests remain disabled in this public check"
    return PublicCheck("public-suite", "Original tests are available.", AIDER_TESTS[task["stratum"]], dependencies,
                       coverage=(coverage if task["stratum"] == "java" else "original visible test suite",),
                       inconclusive_exit_codes=(124,))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--sources", type=Path, default=Path("work/datasets"))
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--terminal-controls", type=Path)
    parser.add_argument("--swe-controls", type=Path)
    parser.add_argument("--manifest-out", type=Path)
    parser.add_argument("--published-preflights", type=Path)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    issues = {row["instance_id"]: row["problem_statement"]
              for row in json.loads((args.sources / "swe-grader.json").read_text())}
    checks = {}
    for task in manifest["selected"]:
        if task["benchmark"] == "swe":
            check = swe_check(task, issues[task["id"]])
            if args.swe_controls is None:
                raise ValueError("SWE public check qualification records are required")
            control = json.loads((args.swe_controls / task["id"] / "result.json").read_text())
            if control["original"]["returncode"] == 0 or control["reference"]["returncode"] != 0:
                raise ValueError("SWE public check controls failed: " + task["id"])
            if control["check_command_sha256"] != hashlib.sha256(check.command.encode()).hexdigest():
                raise ValueError("SWE control used a different public check: " + task["id"])
        elif task["benchmark"] == "aider":
            check = aider_check(task, args.sources)
        else:
            from course_eval.confirmation_terminal_materials import terminal_check
            from course_eval.inventory import REVISIONS
            if args.terminal_controls is None:
                raise ValueError("Terminal check qualification records are required")
            instruction = (args.sources / f"terminal-bench-2-1-{REVISIONS['terminal']}" / "tasks" / task["id"] / "instruction.md").read_text()
            check = terminal_check(task, instruction)
            control = json.loads((args.terminal_controls / task["id"] / "result.json").read_text())
            if control["original"]["state"] == "passed" or control["reference"]["state"] != "passed":
                raise ValueError("Terminal public check controls failed: " + task["id"])
            if control["check_command_sha256"] != hashlib.sha256(check.command.encode()).hexdigest():
                raise ValueError("Terminal control used a different public check: " + task["id"])
            task["candidate_scope"] = control["scope"]
        checks[task["id"]] = [asdict(check)]
        image = task.get("image") or "nju-course-aider:" + task["stratum"]
        inspected, = json.loads(subprocess.check_output([os.environ["COURSE_DOCKER_BIN"], "image", "inspect", image]))
        task["image_id"] = inspected["Id"]
        task["image_digests"] = inspected.get("RepoDigests", [])
    args.out.write_text(json.dumps(checks, ensure_ascii=False, indent=2) + "\n")
    if args.published_preflights:
        manifest["preflight_paths"] = {task["id"]: str(args.published_preflights / task["id"].replace("/", "__") / "preflight.json")
                                       for task in manifest["selected"]}
    if args.manifest_out:
        with args.manifest_out.open("x") as handle:
            json.dump(manifest, handle, ensure_ascii=False, indent=2)
            handle.write("\n")


if __name__ == "__main__":
    main()
