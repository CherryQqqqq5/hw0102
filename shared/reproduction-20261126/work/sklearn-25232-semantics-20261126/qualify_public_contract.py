import ast
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


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def main():
    root, folder = Path.cwd(), Path(__file__).parent.resolve()
    parent_folder = root / "work/free-recovery35-20261126/hy4-plans"
    parent_path = parent_folder / "main-plan.json"
    parent = read(parent_path)
    runtime = Path(parent["runtime_root"]).resolve()
    sys.path.insert(0, str(runtime))
    os.environ["PATH"] = str(root / "work/vendor/docker") + os.pathsep + os.environ["PATH"]
    from course_eval import agent, benchmarks, controller, docker_target, verification

    loaded = {}
    for module in (agent, benchmarks, controller, docker_target, verification):
        path = Path(module.__file__).resolve()
        relative = str(path.relative_to(runtime))
        if not path.is_relative_to(runtime) or sha(path) != parent["runtime_sha256"][relative]:
            raise ValueError("The actual qualification loaded a different frozen runtime")
        loaded[str(path.relative_to(root))] = sha(path)
    tasks_path, checks_path = parent_folder / "tasks.json", parent_folder / "checks.json"
    if sha(tasks_path) != parent["tasks_sha256"] or sha(checks_path) != parent["checks_sha256"]:
        raise ValueError("The original task inputs changed")
    task, = [item for item in read(tasks_path)["selected"] if item["id"] == "scikit-learn__scikit-learn-25232"]
    pin_path = root / parent["baseline_queue"] / "environment-pins.json"
    if sha(pin_path) != parent["environment_pins_sha256"]:
        raise ValueError("The original environment registry changed")
    pin = read(pin_path)["pins"][task["id"]]
    if pin != "sha256:2b2069e2a3f12ddcf3fc1c811468da25f2b349a08ea0dd98a5dbe3eecb0c4ca1":
        raise ValueError("The original25232 pin differs from the independently checked cache")
    checks = read(checks_path)
    before = copy.deepcopy(checks)
    check, = checks[task["id"]]
    program = (folder / "public_nan_probe.py").read_bytes()
    encoded = base64.b64encode(program).decode("ascii")
    stub = "import base64;exec(compile(base64.b64decode(" + repr(encoded) + ").decode('utf-8'),'<course-public-nan-contract>','exec'))"
    probe_command = "/opt/miniconda3/envs/testbed/bin/python -c " + shlex.quote(stub)
    check["command"] += " && " + probe_command
    check["coverage"] = [
        "Original visible fill_value check plus12 public cases for constant initialization, NaN-tolerant tree iteration and fitted feature range",
        "Derive empty-feature status from the original training missing-value mask, cache it on fit and reuse on transform;NaN initialization statistics do not imply an empty training column",
        "Public mature mechanism:https://github.com/scikit-learn/scikit-learn/blob/main/sklearn/impute/_iterative.py ;1.5.2 still used statistics_ and is not claimed fixed",
        "Every probe training feature contains observed values;this is not an exhaustive all-empty training-column contract"]
    if not check["command"].isascii() or base64.b64decode(encoded) != program:
        raise ValueError("The registered command must transport the exact public program through ASCII argv")
    for name in checks:
        if name != task["id"] and checks[name] != before[name]:
            raise ValueError("An unrelated task check changed")
    runs = [root / read(parent_folder / (arm + "-plan.json"))["queue"] / (task["id"] + "-C0-r" + str(index))
        for index, arm in enumerate(("main", "repeat"), 1)]
    public = verification.PublicCheck(**check)
    public.validate((runs[0] / "instruction.txt").read_text())
    destination, inputs = folder / "qualification", folder / "inputs"
    destination.mkdir()
    inputs.mkdir()
    write(inputs / "checks.json", checks)
    manifest = read(tasks_path)
    manifest["selected"] = [task]
    write(inputs / "tasks.json", manifest)
    reference = folder / "separate-public-reference.patch"
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
                raise ValueError("The actual NaN-contract target differs from the original pin")
            benchmarks.check_swe_checkout(task, target, output)
            base = target.exec("sha256sum sklearn/impute/_iterative.py", timeout=30)
            if base["returncode"] or base["stdout"].split()[0] != sha(folder / "public-sources/base-iterative.py"):
                raise ValueError("The separately downloaded public production source differs from the original container")
            environment = controller.ControlledEnvironment(target, output, agent.RunLimits(**parent["limits"]), (public,),
                {"kind": "repository", "python": "/opt/miniconda3/envs/testbed/bin/python"}, controller.Budget(3600), False)
            if patch is not None:
                target.upload_file(patch, "/qualification.patch")
                applied = target.exec("git apply --check /qualification.patch && git apply /qualification.patch", timeout=30)
                write(output / "patch-process.json", applied)
                if applied["returncode"]:
                    raise ValueError("The separately derived or actual model patch did not apply:" + name)
            # 单独执行完整探针，保留原命令短路时base的12项真实诊断。
            process = target.exec(probe_command, timeout=check["timeout_seconds"])
            write(output / "public-probe-process.json", process)
            documents = [json.loads(line) for line in process["stdout"].splitlines() if line.startswith('{"passed":')]
            details, = documents
            if details["total"] != 12 or details["passed"] is not expected or process["returncode"] != (0 if expected else 1):
                raise ValueError("The actual public12 process did not distinguish the registered contract:" + name)
            actual = environment.verify(public.check_id, "zero_model_public_nan_contract_qualification")
            final = environment.finish("zero_model_public_nan_contract_qualification")
            write(output / "actual-verification.json", actual)
            if ((actual["state"] == "passed") is not expected or final["valid_verification"] is not expected
                    or final["protected_unchanged"] is not True):
                raise ValueError("The actual C0 verify/finish did not distinguish the public NaN contract:" + name)
            rows.append({"variant": name, "patch_sha256": sha(patch) if patch else None, "state": actual["state"],
                "final": final, "details": details, "actual_verification_sha256": sha(output / "actual-verification.json"),
                "actual_public_probe_process_sha256": sha(output / "public-probe-process.json")})
            if expected:
                negative_program = "import ast\nprogram=" + repr(program.decode("utf-8")) + "\n" + "\n".join([
                    "tree=ast.parse(program)",
                    "assert isinstance(tree.body[-1],ast.Raise)",
                    "tree.body=tree.body[:-1]",
                    "exec(compile(tree,'<qualified-public-probe>','exec'))",
                    "controls=[]",
                    "for value in (0.0,1.0):",
                    "    wrong=source.copy();mask=np.isnan(wrong);wrong[mask]=value",
                    "    try: assert_tree_predictions(wrong,mask)",
                    "    except AssertionError: controls.append({'operation':'tree','value':value,'rejected':True})",
                    "    else: raise AssertionError('A zero/one-fill tree fallback passed the actual public numerical predicate')",
                    "    train=np.array([[1.,2.],[3.,4.],[5.,6.],[7.,8.]])",
                    "    wrong=np.array([[value,3.],[value,5.],[value,7.],[value,9.]])",
                    "    try: assert_transform_predictions(wrong,train)",
                    "    except AssertionError: controls.append({'operation':'transform','value':value,'rejected':True})",
                    "    else: raise AssertionError('A zero/one-fill transform fallback passed the actual public numerical predicate')",
                    "print(json.dumps({'negative_controls':controls}))"])
                ast.parse(negative_program)
                negative_encoded = base64.b64encode(negative_program.encode()).decode("ascii")
                negative_stub = "import base64;exec(compile(base64.b64decode(" + repr(negative_encoded) + "),'<public-numeric-negative-controls>','exec'))"
                negative = target.exec("/opt/miniconda3/envs/testbed/bin/python -c " + shlex.quote(negative_stub), timeout=60)
                write(output / "numeric-negative-controls-process.json", negative)
                controls, = [json.loads(line) for line in negative["stdout"].splitlines() if line.startswith('{"negative_controls":')]
                if negative["returncode"] or len(controls["negative_controls"]) != 4 or not all(item["rejected"] for item in controls["negative_controls"]):
                    raise ValueError("The real public predicates did not reject trivial zero/one fallbacks")
                rows[-1]["numeric_negative_controls"] = controls["negative_controls"]
                result = target.exec("git diff --check && git diff --binary", timeout=30)
                if result["returncode"]:
                    raise ValueError("The public engineering reference has an invalid diff")
                actual_reference = result["stdout"]
                (destination / "actual-reference.patch").write_text(actual_reference)
        print(json.dumps({"variant": name, "state": rows[-1]["state"],
            "public_passed": sum(case["passed"] for case in details["cases"])}), flush=True)
    proof = {"phase": "actual_c0_public_nan_contract_qualified", "new_model_calls": 0, "original_grader_calls": 0,
        "pin": pin, "source_plan_sha256": sha(parent_path), "driver_sha256": sha(Path(__file__)),
        "probe_sha256": hashlib.sha256(program).hexdigest(), "reference_patch_sha256": sha(reference),
        "reference_source_sha256": sha(folder / "reference-iterative.py"), "actual_loaded_runtime_modules": loaded,
        "new_tasks_sha256": sha(inputs / "tasks.json"), "new_checks_sha256": sha(inputs / "checks.json"),
        "source_original_scores_sha256": scores, "variants": rows,
        "scope": "Public12 independent observations-bearing training cases. Exact original pin, real C0 snapshot/verify/finish and preserved original tests. Independent engineering reference is not a model candidate or model input."}
    proof_path = destination / "result.json"
    if sha(folder / "public_nan_probe.py") != proof["probe_sha256"]:
        raise ValueError("The public program changed after registration")
    proof.update(phase="public_reference_original_grader_started", original_grader_function_invocations=1, original_grader_calls=None)
    write(proof_path, proof)
    row, = [item for item in read(root / "work/datasets/swe-grader.json") if item["instance_id"] == task["id"]]
    grade = destination / "reference-original-grade"
    grade.mkdir()
    outcome = benchmarks.grade_swe(row, actual_reference, grade)
    actual_grader_evidence = list(grade.rglob("test_output.txt"))
    proof.update(phase="public_reference_original_grader_returned",
        original_grader_calls=1 if outcome["scoreable"] is True and actual_grader_evidence else None,
        original_grader_test_outputs=[str(path.relative_to(root)) for path in actual_grader_evidence],
        separate_engineering_original_grade=outcome)
    write(proof_path, proof)
    if outcome["scoreable"] is not True or outcome["passed"] is not True:
        raise ValueError("The original scorer rejected the separately derived public mature reference")
    for name, expected in scores.items():
        if sha(root / name) != expected:
            raise ValueError("An original model score changed during qualification")
    proof.update(phase="actual_c0_public_contract_and_separate_original_grader_passed", original_model_scores_unchanged=True)
    write(proof_path, proof)
    print(json.dumps({"phase": proof["phase"], "new_model_calls": 0, "original_grader_calls": 1}), flush=True)


if __name__ == "__main__":
    main()
