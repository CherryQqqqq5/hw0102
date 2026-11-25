import copy
import hashlib
import json
import os
import shlex
import sys
from pathlib import Path


def read(path):
    return json.loads(path.read_text())


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def main():
    root, folder = Path.cwd(), Path(__file__).parent.resolve()
    parents = root / "work/parallel-free-evaluation-20261124/final-sql75-quota-recovered"
    parent_path = parents / "main-plan.json"
    parent = read(parent_path)
    runtime = Path(parent["runtime_root"])
    sys.path.insert(0, str(runtime))
    os.environ["PATH"] = str(root / "work/vendor/docker") + os.pathsep + os.environ["PATH"]
    from course_eval import agent, benchmarks, controller, docker_target, verification
    from course_eval.resource_pool import ResourceLease

    loaded = {}
    for module in (agent, benchmarks, controller, docker_target, verification):
        path = Path(module.__file__).resolve()
        if not path.is_relative_to(runtime) or sha(path) != parent["runtime_sha256"][str(path.relative_to(runtime))]:
            raise ValueError("The actual qualification loaded another frozen implementation")
        loaded[str(path.relative_to(root))] = sha(path)
    task_id = "pytest-dev__pytest-5631"
    tasks_path, checks_path = parents / "tasks.json", parents / "checks.json"
    if sha(tasks_path) != parent["tasks_sha256"] or sha(checks_path) != parent["checks_sha256"]:
        raise ValueError("The original task or registered checks changed")
    task, = [task for task in read(tasks_path)["selected"] if task["id"] == task_id]
    pins_path = root / parent["baseline_queue"] / "environment-pins.json"
    if sha(pins_path) != parent["environment_pins_sha256"]:
        raise ValueError("The original image registry changed")
    pin = read(pins_path)["pins"][task_id]
    previous = root / parent["queue"] / (task_id + "-C0-r1")
    if read(previous / "result.json")["passed"] is not True:
        raise ValueError("The actual original true score must remain unchanged")
    old_final = read(previous / "final-verification.json")
    if old_final["protected_unchanged"] is not False or old_final["valid_verification"] is not False:
        raise ValueError("This qualification only covers the observed test-preservation violation")
    original_check, = read(checks_path)[task_id]
    check = copy.deepcopy(original_check)
    check["coverage"] += [
        "Preserve every existing tracked test and test configuration byte. Put extra regression tests in a separate scratch directory, not in testing/ or existing test modules.",
        "Before verify/save/finish inspect the changed paths. If a protected existing test/configuration was edited, restore that file exactly to the original checkout while retaining the production fix, then verify again. Never relax or bypass the protection check.",
        "The mature pytest6.0.0 num_mock_patch_args implementation compares mock DEFAULT sentinels by object identity, avoiding arbitrary equality: https://github.com/pytest-dev/pytest/blob/6.0.0/src/_pytest/compat.py",
    ]
    if {key: value for key, value in check.items() if key != "coverage"} != {
            key: value for key, value in original_check.items() if key != "coverage"}:
        raise ValueError("This revision may change only task-local public guidance")
    public = verification.PublicCheck(**check)
    public.validate((previous / "instruction.txt").read_text())
    destination, inputs = folder / "qualification", folder / "inputs"
    destination.mkdir()
    inputs.mkdir()
    checks = read(checks_path)
    checks[task_id] = [check]
    manifest = read(tasks_path)
    manifest["selected"] = [task]
    write(inputs / "tasks.json", manifest)
    write(inputs / "checks.json", checks)
    source_files = {str(path.relative_to(root)): sha(path) for path in (
        Path(__file__).resolve(), tasks_path, checks_path, parent_path, pins_path,
        previous / "result.json", previous / "candidate.patch", previous / "final-verification.json",
        previous / "model.jsonl", previous / "tools.jsonl", previous.with_suffix(".protocol.json"))}
    rows = []
    variants = (("base", None, False, True),
        ("recorded_full_candidate", None, False, False),
        ("recorded_production_only", "src/_pytest/compat.py", True, True))
    with ResourceLease(root / parent["resource_pool"], exclusive=True, label="qualify-pytest5631-preservation"):
        for name, include, expected_valid, expected_trusted in variants:
            output = destination / name
            output.mkdir()
            options = benchmarks.swe_public_dependencies(task)
            options["read_only_mounts"] = options.get("read_only_mounts", ()) + benchmarks.runtime_mounts("linux/amd64")
            with docker_target.DockerTarget(task["image"], "/testbed", platform="linux/amd64", memory_mb=3072, cpus=2,
                    read_only_empty_dirs=benchmarks.SWE_HIDDEN_CACHES, **options) as target:
                if target.image != pin:
                    raise ValueError("The actual target differs from the frozen original pin")
                benchmarks.check_swe_checkout(task, target, output)
                environment = controller.ControlledEnvironment(target, output, agent.RunLimits(**parent["limits"]), (public,),
                    {"kind": "repository", "python": "/opt/miniconda3/envs/testbed/bin/python"}, controller.Budget(3600), False)
                if name != "base":
                    target.upload_file(previous / "candidate.patch", "/qualification.patch")
                    selection = " --include=" + shlex.quote(include) if include else ""
                    applied = target.exec("git apply --check" + selection + " /qualification.patch && git apply" + selection + " /qualification.patch", timeout=30)
                    if applied["returncode"]:
                        raise ValueError("The recorded candidate did not apply: " + str(applied))
                actual = environment.verify(public.check_id, "zero_model_test_preservation_qualification")
                final = environment.finish("zero_model_test_preservation_qualification")
                write(output / "actual-verification.json", actual)
                if ((actual["state"] == "passed") is not expected_valid
                        or final["valid_verification"] is not expected_valid
                        or final["protected_unchanged"] is not expected_trusted):
                    raise ValueError("The unchanged C0 check/guard did not distinguish the actual preservation defect: " + name)
                diff = target.exec("git diff --check && git diff --binary", timeout=30)
                if diff["returncode"]:
                    raise ValueError("The actual qualified candidate diff is malformed")
                (output / "actual-candidate.patch").write_text(diff["stdout"])
                rows.append({"variant": name, "state": actual["state"], "final": final,
                    "actual_verification_sha256": sha(output / "actual-verification.json"),
                    "actual_candidate_sha256": sha(output / "actual-candidate.patch")})
            print(json.dumps({"variant": name, "state": actual["state"], "protected_unchanged": final["protected_unchanged"]}), flush=True)
    for path, expected in source_files.items():
        if sha(root / path) != expected:
            raise ValueError("An original source changed during the independent engineering qualification")
    write(destination / "result.json", {"phase": "actual_unchanged_c0_public_check_and_protected_guard_qualified",
        "new_model_calls": 0, "new_original_grader_calls": 0, "task": task_id, "pin": pin,
        "driver_sha256": sha(Path(__file__)), "source_files_sha256": source_files,
        "actual_loaded_runtime_modules": loaded, "variants": rows,
        "new_checks_sha256": sha(inputs / "checks.json"), "new_tasks_sha256": sha(inputs / "tasks.json"),
        "original_result_unchanged": True,
        "interpretation": "Offline engineering only. The recorded main production fix is semantically correct under its retained original true grade; editing an existing testing module caused the C0 protection failure. The full recorded patch remains rejected; applying only its production edit passes the unchanged public check and unchanged protection. This does not turn the original model result into qualified success or prove that a fresh model follows the additional guidance."})


if __name__ == "__main__":
    main()
