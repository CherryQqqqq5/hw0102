import base64
import copy
import hashlib
import json
import os
from pathlib import Path
import shlex
import sys


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    root, folder = Path.cwd(), Path(__file__).parent.resolve()
    parent_folder = root / "work/parallel-free-evaluation-20261124/final-sql75-recovered"
    parent_path = parent_folder / "main-plan.json"
    parent = read(parent_path)
    runtime = Path(parent["runtime_root"])
    sys.path.insert(0, str(runtime))
    os.environ["PATH"] = str(root / "work/vendor/docker") + os.pathsep + os.environ["PATH"]
    from course_eval import agent, benchmarks, controller, docker_target, verification

    loaded = {}
    for module in (agent, benchmarks, controller, docker_target, verification):
        path = Path(module.__file__).resolve()
        if not path.is_relative_to(runtime) or sha(path) != parent["runtime_sha256"][str(path.relative_to(runtime))]:
            raise ValueError("The actual qualification loaded a different frozen runtime")
        loaded[str(path.relative_to(root))] = sha(path)
    tasks_path, original_checks = parent_folder / "tasks.json", parent_folder / "checks.json"
    if sha(tasks_path) != parent["tasks_sha256"] or sha(original_checks) != parent["checks_sha256"]:
        raise ValueError("The original task inputs changed")
    task, = [task for task in read(tasks_path)["selected"] if task["id"] == "pydata__xarray-2905"]
    pin_path = root / parent["baseline_queue"] / "environment-pins.json"
    if sha(pin_path) != parent["environment_pins_sha256"]:
        raise ValueError("The original environment registry changed")
    pin = read(pin_path)["pins"][task["id"]]
    checks = read(original_checks)
    before = copy.deepcopy(checks)
    check, = checks[task["id"]]
    program = (folder / "public_object_probe.py").read_bytes()
    encoded = base64.b64encode(program).decode("ascii")
    stub = "import base64;exec(compile(base64.b64decode(" + repr(encoded) + ").decode('utf-8'),'<course-public-object-contract>','exec'))"
    check["command"] += " && /opt/miniconda3/envs/testbed/bin/python -c " + shlex.quote(stub)
    check["coverage"] = ["Original visible assignment tests plus26 public task-derived object-identity and named-container cases",
        "Constructor, shared as_compatible_data, Variable and DataArray direct/loc assignment; arbitrary values properties remain opaque",
        "Official xarray explicitly recognizes supported xarray and pandas containers rather than unwrapping arbitrary values attributes: https://github.com/pydata/xarray/blob/main/xarray/core/variable.py"]
    if not check["command"].isascii() or base64.b64decode(encoded) != program:
        raise ValueError("The actual registered command must carry exact public bytes through ASCII argv")
    for name in checks:
        if name != task["id"] and checks[name] != before[name]:
            raise ValueError("An unrelated task check changed")
    first = root / parent["queue"] / (task["id"] + "-C0-r1")
    instruction = (first / "instruction.txt").read_text()
    public = verification.PublicCheck(**check)
    public.validate(instruction)
    destination, inputs = folder / "qualification", folder / "inputs"
    destination.mkdir()
    inputs.mkdir()
    (inputs / "checks.json").write_text(json.dumps(checks, ensure_ascii=False, indent=2) + "\n")
    manifest = read(tasks_path)
    manifest["selected"] = [task]
    (inputs / "tasks.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    reference = folder / "separate-public-reference.patch"
    runs = [root / read(parent_folder / (arm + "-plan.json"))["queue"] / (task["id"] + "-C0-r" + str(i))
        for i, arm in enumerate(("main", "repeat"), 1)]
    scores = {str((run / "result.json").relative_to(root)): sha(run / "result.json") for run in runs}
    variants = [("base", None, False), ("actual_main", runs[0] / "candidate.patch", False),
        ("actual_repeat", runs[1] / "candidate.patch", False), ("public_reference", reference, True)]
    rows, actual_reference = [], None
    for name, patch, expected in variants:
        output = destination / name
        output.mkdir()
        options = benchmarks.swe_public_dependencies(task)
        options["read_only_mounts"] = options.get("read_only_mounts", ()) + benchmarks.runtime_mounts("linux/amd64")
        with docker_target.DockerTarget(task["image"], "/testbed", platform="linux/amd64", memory_mb=3072, cpus=2,
                read_only_empty_dirs=benchmarks.SWE_HIDDEN_CACHES, **options) as target:
            if target.image != pin:
                raise ValueError("The actual object-contract target differs from the original image pin")
            benchmarks.check_swe_checkout(task, target, output)
            environment = controller.ControlledEnvironment(target, output, agent.RunLimits(**parent["limits"]), (public,),
                {"kind": "repository", "python": "/opt/miniconda3/envs/testbed/bin/python"}, controller.Budget(3600), False)
            if patch is not None:
                target.upload_file(patch, "/qualification.patch")
                result = target.exec("git apply --check /qualification.patch && git apply /qualification.patch", timeout=30)
                if result["returncode"]:
                    raise ValueError("The public or actual candidate patch could not apply: " + str(result))
            actual = environment.verify(public.check_id, "zero_model_public_object_contract_qualification")
            final = environment.finish("zero_model_public_object_contract_qualification")
            (output / "actual-verification.json").write_text(json.dumps(actual, indent=2) + "\n")
            if (actual["state"] == "passed") is not expected or final["valid_verification"] is not expected or final["protected_unchanged"] is not True:
                raise ValueError("The actual C0 command did not distinguish the public object contract: " + name)
            lines = [line for line in actual["stdout"].splitlines() if line.startswith('{"passed":')]
            details, = [json.loads(line) for line in lines]
            if details["total"] != 26 or details["passed"] is not expected:
                raise ValueError("The exact public26 program did not execute or returned an unexpected result")
            rows.append({"variant": name, "patch_sha256": sha(patch) if patch else None,
                "state": actual["state"], "final": final, "details": details,
                "actual_verification_sha256": sha(output / "actual-verification.json")})
            if expected:
                result = target.exec("git diff --check && git diff --binary", timeout=30)
                if result["returncode"]:
                    raise ValueError("The public engineering reference has an invalid diff")
                actual_reference = result["stdout"]
                (destination / "actual-reference.patch").write_text(actual_reference)
        print(json.dumps({"variant": name, "state": rows[-1]["state"],
            "public_passed": sum(case["passed"] for case in details["cases"])}), flush=True)
    proof = {"phase": "actual_c0_public_object_contract_qualified", "new_model_calls": 0,
        "original_grader_calls": 0, "pin": pin, "source_plan_sha256": sha(parent_path),
        "driver_sha256": sha(Path(__file__)), "probe_sha256": hashlib.sha256(program).hexdigest(),
        "reference_patch_sha256": sha(reference), "actual_loaded_runtime_modules": loaded,
        "new_tasks_sha256": sha(inputs / "tasks.json"), "new_checks_sha256": sha(inputs / "checks.json"),
        "source_original_scores_sha256": scores, "variants": rows,
        "public_source": "https://github.com/pydata/xarray/blob/main/xarray/core/variable.py",
        "scope": "Public problem-derived object identity and known container conversion cases only. Exact original pin and C0 command. The engineering reference is not a model candidate or supplied solution."}
    proof_path = destination / "result.json"
    if sha(folder / "public_object_probe.py") != proof["probe_sha256"]:
        raise ValueError("The public program changed after its exact registered command was qualified")
    proof.update(phase="public_reference_original_grader_started", original_grader_function_invocations=1, original_grader_calls=None)
    proof_path.write_text(json.dumps(proof, ensure_ascii=False, indent=2) + "\n")
    row, = [row for row in read(root / "work/datasets/swe-grader.json") if row["instance_id"] == task["id"]]
    grade = destination / "reference-original-grade"
    grade.mkdir()
    outcome = benchmarks.grade_swe(row, actual_reference, grade)
    actual_grader_evidence = list(grade.rglob("test_output.txt"))
    proof.update(phase="public_reference_original_grader_returned",
        original_grader_calls=1 if outcome["scoreable"] is True and actual_grader_evidence else None,
        original_grader_test_outputs=[str(path.relative_to(root)) for path in actual_grader_evidence],
        separate_engineering_original_grade=outcome)
    proof_path.write_text(json.dumps(proof, ensure_ascii=False, indent=2) + "\n")
    if outcome["scoreable"] is not True or outcome["passed"] is not True:
        raise ValueError("The original scorer rejected the separately derived public mature reference")
    for name, expected in scores.items():
        if sha(root / name) != expected:
            raise ValueError("An original model score changed during qualification")
    proof.update(phase="actual_c0_public_contract_and_separate_original_grader_passed", original_model_scores_unchanged=True)
    proof_path.write_text(json.dumps(proof, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"phase": proof["phase"], "new_model_calls": 0, "original_grader_calls": 1}), flush=True)


if __name__ == "__main__":
    main()
