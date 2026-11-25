import argparse
import base64
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import sys


TASK = "pytest-dev__pytest-7205"
CONFLICTS = (
    "test_show_fixtures_with_parameters",
    "test_show_fixtures_with_parameter_ids",
    "test_show_fixtures_with_parameter_ids_function",
)


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def ascii_python(program):
    encoded = base64.b64encode(program).decode("ascii")
    stub = ("import base64;exec(compile(base64.b64decode(" + repr(encoded)
            + ").decode('utf-8'),'<course-public-safe-repr>','exec'))")
    return "/opt/miniconda3/envs/testbed/bin/python -c " + shlex.quote(stub)


def protected_snapshot(target):
    program = (
        "import hashlib,json,pathlib,stat,subprocess\n"
        "root=pathlib.Path('/testbed')\n"
        "names=subprocess.check_output(['git','ls-files','-z','--','testing'],cwd=str(root)).decode().split('\\0')\n"
        "names += [p.name for p in root.iterdir() if p.is_file() and (p.suffix in ('.ini','.cfg','.toml') or p.name=='setup.py')]\n"
        "rows={}\n"
        "for name in sorted(set(names)-{''}):\n"
        " p=root/name\n"
        " if p.is_file(): rows[name]={'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'mode':stat.S_IMODE(p.stat().st_mode)}\n"
        "print(json.dumps(rows,sort_keys=True))\n"
    ).encode()
    result = target.exec(ascii_python(program), timeout=30)
    if result["returncode"]:
        raise ValueError("The original test/configuration snapshot failed: " + result["stderr"])
    return json.loads(result["stdout"])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    root, folder = Path.cwd(), Path(__file__).parent.resolve()
    destination = (args.out or folder / "qualification").resolve()
    if destination == folder or not destination.is_relative_to(folder):
        raise ValueError("Qualification output must be a new directory within this work scope")
    destination.mkdir()
    inputs = folder / ("inputs" if destination.name == "qualification" else destination.name + "-inputs")
    if inputs.exists():
        raise FileExistsError("Do not overwrite a previous public contract")
    parent_folder = root / "work/parallel-free-evaluation-20261124/final-sql75-recovered"
    parent_path = parent_folder / "main-plan.json"
    parent = read(parent_path)
    runtime = Path(parent["runtime_root"]).resolve()
    sys.path.insert(0, str(runtime))
    os.environ["PATH"] = str(root / "work/vendor/docker") + os.pathsep + os.environ["PATH"]
    from course_eval import agent, benchmarks, controller, docker_target, verification

    loaded = {}
    for module in (agent, benchmarks, controller, docker_target, verification):
        path = Path(module.__file__).resolve()
        if not path.is_relative_to(runtime) or sha(path) != parent["runtime_sha256"][str(path.relative_to(runtime))]:
            raise ValueError("The actual qualification loaded a different frozen runtime")
        loaded[str(path.relative_to(root))] = sha(path)
    tasks_path, checks_path = parent_folder / "tasks.json", parent_folder / "checks.json"
    if sha(tasks_path) != parent["tasks_sha256"] or sha(checks_path) != parent["checks_sha256"]:
        raise ValueError("The original task inputs changed")
    task, = [item for item in read(tasks_path)["selected"] if item["id"] == TASK]
    pins_path = root / parent["baseline_queue"] / "environment-pins.json"
    if sha(pins_path) != parent["environment_pins_sha256"]:
        raise ValueError("The original image registry changed")
    pin = read(pins_path)["pins"][TASK]
    old_checks = read(checks_path)
    original_check, = old_checks[TASK]
    source_run = root / "work/vmshare/performance75-hy4-sql-layout-v18-repeat-20261125" / (TASK + "-C0-r2")
    instruction = (source_run / "instruction.txt").read_text()
    source_score = read(source_run / "result.json")
    if source_score["scoreable"] is not True or source_score["passed"] is not False:
        raise ValueError("The existing real repeat failure must remain an original false score")
    reference = folder / "separate-public-reference.patch"
    probe = folder / "public_setup_repr_probe.py"
    program = probe.read_bytes()
    source_paths = [Path(__file__).resolve(), reference, probe, folder / "README.md",
        *sorted((folder / "public-sources").glob("*")), parent_path, tasks_path, checks_path, pins_path,
        source_run / "result.json", source_run / "candidate.patch"]
    sources = {str(path.relative_to(root)): sha(path) for path in source_paths if path.is_file()}
    limits = agent.RunLimits(**parent["limits"])
    scope = {"kind": "repository", "python": "/opt/miniconda3/envs/testbed/bin/python"}
    proof = {"phase": "legacy_reference_conflict_check_started", "new_model_calls": 0,
        "original_grader_calls": 0, "pin": pin, "source_plan_sha256": sha(parent_path),
        "driver_sha256": sha(Path(__file__)), "probe_sha256": hashlib.sha256(program).hexdigest(),
        "reference_patch_sha256": sha(reference), "actual_loaded_runtime_modules": loaded,
        "source_files_sha256": sources,
        "source_original_scores_sha256": {str((source_run / "result.json").relative_to(root)): sha(source_run / "result.json")},
        "public_sources": {"original_module": "https://raw.githubusercontent.com/pytest-dev/pytest/5e7f1ab4bf58e473e5d7f878eb2b499d7deabd29/src/_pytest/setuponly.py",
            "original_tests": "https://raw.githubusercontent.com/pytest-dev/pytest/5e7f1ab4bf58e473e5d7f878eb2b499d7deabd29/testing/test_setuponly.py",
            "mature_module": "https://raw.githubusercontent.com/pytest-dev/pytest/6.0.0/src/_pytest/setuponly.py"}}
    proof_path = destination / "result.json"
    write(proof_path, proof)

    def target_for(output):
        options = benchmarks.swe_public_dependencies(task)
        options["read_only_mounts"] = options.get("read_only_mounts", ()) + benchmarks.runtime_mounts("linux/amd64")
        target = docker_target.DockerTarget(task["image"], "/testbed", platform="linux/amd64",
            memory_mb=3072, cpus=2, read_only_empty_dirs=benchmarks.SWE_HIDDEN_CACHES, **options)
        try:
            if target.image != pin:
                raise ValueError("The actual qualification used another original image pin")
            benchmarks.check_swe_checkout(task, target, output)
            actual_sources = target.exec(ascii_python(
                b"import hashlib,json,pathlib\nprint(json.dumps({name:hashlib.sha256(pathlib.Path('/testbed',name).read_bytes()).hexdigest() for name in ['src/_pytest/setuponly.py','testing/test_setuponly.py']}))\n"), timeout=30)
            if actual_sources["returncode"]:
                raise ValueError("Could not verify the actual original public source bytes")
            expected_sources = {
                "src/_pytest/setuponly.py": sha(folder / "public-sources/original-setuponly.py"),
                "testing/test_setuponly.py": sha(folder / "public-sources/original-test_setuponly.py"),
            }
            if json.loads(actual_sources["stdout"]) != expected_sources:
                raise ValueError("The actual pinned public source differs from the cited original source")
        except BaseException:
            target.__exit__(*sys.exc_info())
            raise
        return target

    def apply(target, patch):
        target.upload_file(patch, "/qualification.patch")
        result = target.exec("git apply --check /qualification.patch && git apply /qualification.patch", timeout=30)
        if result["returncode"]:
            raise ValueError("The actual public or retained candidate patch could not apply: " + str(result))

    legacy = destination / "legacy-reference-conflict"
    legacy.mkdir()
    legacy_item = copy.deepcopy(original_check)
    legacy_item["command"] += " --basetemp /course-public-legacy-tmp"
    legacy_check = verification.PublicCheck(**legacy_item)
    legacy_check.validate(instruction)
    with target_for(legacy) as target:
        original = protected_snapshot(target)
        write(legacy / "protected-original-files.json", original)
        environment = controller.ControlledEnvironment(target, legacy, limits, (legacy_check,), scope,
            controller.Budget(3600), False)
        apply(target, reference)
        actual = environment.verify(legacy_check.check_id, "zero_model_full_legacy_format_conflict")
        final = environment.finish("zero_model_full_legacy_format_conflict")
        write(legacy / "actual-verification.json", actual)
        matches = re.findall(r"(\d+) failed, (\d+) passed", actual["stdout"])
        functions = set(re.findall(r"^FAILED [^\n]*::(test_\w+)", actual["stdout"], re.MULTILINE))
        if (not matches or tuple(map(int, matches[-1])) != (9, 16) or functions != set(CONFLICTS)
                or actual["state"] != "failed" or final["valid_verification"] is not False
                or final["protected_unchanged"] is not True or protected_snapshot(target) != original):
            raise ValueError("The full old suite did not expose exactly the declared9 obsolete format assertions")
        proof["legacy_public_conflict"] = {"failed": 9, "passed": 16, "conflicting_functions": list(CONFLICTS),
            "original_test_file_sha256": original["testing/test_setuponly.py"]["sha256"],
            "actual_verification_sha256": sha(legacy / "actual-verification.json"),
            "protected_original_file_count": len(original), "protected_original_files_unchanged": True}
    proof["phase"] = "legacy_conflict_recorded_before_public_contract_replacement"
    write(proof_path, proof)

    checks = copy.deepcopy(old_checks)
    check, = checks[TASK]
    exclusions = "".join(" --deselect " + shlex.quote("testing/test_setuponly.py::" + name) for name in CONFLICTS)
    check["command"] += exclusions + " --basetemp /course-public-nonformat-tmp && " + ascii_python(program)
    check["coverage"] = ["Preserve16 non-format original public regressions; explicitly replace9 old unquoted parameter-display assertions with18 public safe-repr CLI cases",
        "Actual Python -bb in setup-show/setup-only/setup-plan: self-chosen ASCII/non-ASCII bytes, string/integer and explicit/callable ids",
        "Original problem explicitly suggests saferepr. Official pytest6.0.0 uniformly applies saferepr(cached_param,maxsize=42): https://github.com/pytest-dev/pytest/blob/6.0.0/src/_pytest/setuponly.py",
        "Expected output follows standard repr of short public values; alternate correct implementations are admitted. No hidden fixture or engineering patch is supplied."]
    if not check["command"].isascii():
        raise ValueError("The exact registered command must use ASCII transport")
    public = verification.PublicCheck(**check)
    public.validate(instruction)
    inputs.mkdir()
    write(inputs / "checks.json", checks)
    manifest = read(tasks_path)
    manifest["selected"] = [task]
    write(inputs / "tasks.json", manifest)
    proof.update(new_checks_path=str((inputs / "checks.json").relative_to(root)),
        new_tasks_path=str((inputs / "tasks.json").relative_to(root)),
        new_checks_sha256=sha(inputs / "checks.json"), new_tasks_sha256=sha(inputs / "tasks.json"))
    variants = [("base", None, False), ("actual_repeat", source_run / "candidate.patch", False),
        ("public_reference", reference, True)]
    rows, actual_reference = [], None
    for name, patch, expected in variants:
        output = destination / name
        output.mkdir()
        with target_for(output) as target:
            original = protected_snapshot(target)
            write(output / "protected-original-files.json", original)
            environment = controller.ControlledEnvironment(target, output, limits, (public,), scope,
                controller.Budget(3600), False)
            if patch is not None:
                apply(target, patch)
            actual = environment.verify(public.check_id, "zero_model_exact_public_safe_repr_qualification")
            final = environment.finish("zero_model_exact_public_safe_repr_qualification")
            write(output / "actual-verification.json", actual)
            details, = [json.loads(line) for line in actual["stdout"].splitlines() if line.startswith('{"passed":')]
            transcript = output / "actual-cli-processes.json"
            target.docker("cp", target.container + ":/course-public-setup-repr-processes.json", str(transcript.resolve()))
            processes = read(transcript)["actual_processes"]
            if (details["total"] != 18 or len(processes) != 18 or details["passed"] is not expected
                    or (actual["state"] == "passed") is not expected or final["valid_verification"] is not expected
                    or final["protected_unchanged"] is not True or protected_snapshot(target) != original):
                raise ValueError("The actual original C0 command did not distinguish the safe-repr contract: " + name)
            for process, case in zip(processes, details["cases"]):
                if (process["scenario"] != case["scenario"] or process["mode"] != case["mode"]
                        or process["command"][1:4] != ["-bb", "-m", "pytest"]
                        or "error_type" in process or "error_type" in case
                        or process.get("returncode") != case.get("returncode")):
                    raise ValueError("The public case differs from its actual Python -bb CLI process")
                for stream in ("stdout", "stderr"):
                    if stream in process and hashlib.sha256(process[stream].encode()).hexdigest() != case.get(stream + "_sha256"):
                        raise ValueError("The actual CLI transcript differs from the public summary")
            positions = {(case["scenario"], case["mode"]) for case in details["cases"]}
            expected_positions = {(scenario, mode) for scenario in (
                "default_ascii_bytes", "default_non_ascii_bytes", "default_string", "default_integer",
                "explicit_id", "callable_id") for mode in ("--setup-show", "--setup-only", "--setup-plan")}
            if positions != expected_positions or len(details["cases"]) != 18:
                raise ValueError("The real processes did not cover every fixed public case exactly once")
            if not all(case["passed"] for case in details["cases"] if case["scenario"] == "default_integer"):
                raise ValueError("The non-format-sensitive integer control failed; do not accept infrastructure failure as a negative control")
            rows.append({"variant": name, "patch_sha256": sha(patch) if patch else None,
                "state": actual["state"], "final": final, "details": details,
                "actual_verification_sha256": sha(output / "actual-verification.json"),
                "actual_cli_transcript_sha256": sha(transcript),
                "protected_original_file_count": len(original), "protected_original_files_unchanged": True})
            if expected:
                result = target.exec("git diff --check && git diff --binary", timeout=30)
                if result["returncode"]:
                    raise ValueError("The separately derived reference has an invalid production diff")
                actual_reference = result["stdout"]
                (destination / "actual-reference.patch").write_text(actual_reference)
        proof.update(phase="public_safe_repr_contract_controls_in_progress", variants=rows)
        write(proof_path, proof)
        print(json.dumps({"variant": name, "public_passed": sum(case["passed"] for case in details["cases"]),
            "total": 18, "state": rows[-1]["state"]}), flush=True)
    for name, expected in sources.items():
        if sha(root / name) != expected:
            raise ValueError("A qualified public source or retained model record changed: " + name)
    proof.update(phase="public_reference_original_grader_started", original_grader_function_invocations=1,
        original_grader_calls=None)
    write(proof_path, proof)
    row, = [row for row in read(root / "work/datasets/swe-grader.json") if row["instance_id"] == TASK]
    grade = destination / "reference-original-grade"
    grade.mkdir()
    outcome = benchmarks.grade_swe(row, actual_reference, grade)
    actual_outputs = list(grade.rglob("test_output.txt"))
    proof.update(phase="public_reference_original_grader_returned", separate_engineering_original_grade=outcome,
        original_grader_calls=1 if outcome["scoreable"] is True and actual_outputs else None,
        original_grader_test_outputs=[str(path.relative_to(root)) for path in actual_outputs])
    write(proof_path, proof)
    if outcome["scoreable"] is not True or outcome["passed"] is not True or proof["original_grader_calls"] != 1:
        raise ValueError("The unchanged original scorer did not validate the public mature reference")
    for name, expected in sources.items():
        if sha(root / name) != expected:
            raise ValueError("A public source or original model record changed during engineering grading")
    proof.update(phase="actual_c0_public_safe_repr_contract_and_separate_original_grader_passed",
        original_model_score_unchanged=True,
        scope="Explicitly replaces9 obsolete public display assertions while retaining16 old non-format tests and18 self-chosen real -bb CLI cases. Original test/configuration bytes and original grader are unchanged; no model instantiated.")
    write(proof_path, proof)
    print(json.dumps({"phase": proof["phase"], "new_model_calls": 0, "original_grader_calls": 1}), flush=True)


if __name__ == "__main__":
    main()
