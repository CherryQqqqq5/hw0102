import copy
import hashlib
import json
import os
from pathlib import Path
import shlex
import sys
import time
import traceback


ROOT = Path.cwd().resolve()
FOLDER = Path(__file__).resolve().parent
PARENTS = ROOT / "work/free-recovery35-20261126/hy4-plans"
RUNTIME = ROOT / "work/frozen-performance-hy4-submit-boundary-v20"
TASK = "pydata__xarray-4695"
SNAPSHOT = ROOT / "work/parallel-free-evaluation-20261124/hy4-snapshot-0311-20261126/summary.json"
GUIDANCE = [
    "Preserve every existing tracked test and test configuration exactly. Put additional self-tests in a separate scratch directory outside xarray/tests and existing test/configuration files;do not append regression cases to the protected suite.",
    "Before verify,save and submit,compare tracked test/configuration paths with the original checkout. Restore only any edited protected test/configuration to its original bytes while retaining the production fix;then rerun the unchanged registered check.",
    "A pytest returncode0 alone is insufficient. Read the registered check state and protection result;protected_dependency_changed,pending or stale is not passed. Repair preservation,verify the current artifact and save an eligible candidate before submitting;the existing C0 submit gate rejects invalid current evidence.",
]


def read(path):
    return json.loads(path.read_bytes())


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write(path, value):
    with path.open("xb") as stream:
        stream.write((json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode())


def main():
    parent = read(PARENTS / "main-plan.json")
    sys.path[:0] = [str(RUNTIME), str(ROOT), str(ROOT / "work/parallel-free-evaluation-20261124")]
    from minisweagent.exceptions import Submitted
    from course_eval import agent, benchmarks, controller, docker_target, verification
    from course_eval.resource_pool import ResourceLease
    from ready_coordinator_light_probe import prepare_missing_image
    modules = (agent, benchmarks, controller, docker_target, verification)
    manifest_path = ROOT / "work/hy4-submit-boundary-20261125/runtime-manifest.json"
    manifest = read(manifest_path)
    loaded = {}
    for name, expected in manifest["files"].items():
        if sha(RUNTIME / name) != expected:
            raise ValueError("The previously reviewed v20 runtime changed:" + name)
    for module in modules:
        path = Path(module.__file__).resolve()
        if not path.is_relative_to(RUNTIME) or sha(path) != manifest["files"][str(path.relative_to(RUNTIME))]:
            raise ValueError("The actual qualification imported a different frozen module")
        loaded[str(path.relative_to(ROOT))] = sha(path)
    tasks_path, checks_path = PARENTS / "tasks.json", PARENTS / "checks.json"
    pins_path = ROOT / parent["baseline_queue"] / "environment-pins.json"
    for path, expected in ((tasks_path, parent["tasks_sha256"]), (checks_path, parent["checks_sha256"]), (pins_path, parent["environment_pins_sha256"])):
        if sha(path) != expected:
            raise ValueError("The original task/check/pin source changed")
    task, = [item for item in read(tasks_path)["selected"] if item["id"] == TASK]
    pin = read(pins_path)["pins"][TASK]
    runs = {arm: ROOT / read(PARENTS / (arm + "-plan.json"))["queue"] / (TASK + "-C0-r" + str(index))
        for arm, index in (("main", 1), ("repeat", 2))}
    selected = [row for row in read(SNAPSHOT)["rows"] if row["task"] == TASK and row["arm"] in runs]
    if len(read(SNAPSHOT)["rows"]) != 200 or len(selected) != 2 or any(row["passed"] is not True for row in selected):
        raise ValueError("The fixed original200 snapshot must retain both actual true grades")
    if read(runs["repeat"] / "final-verification.json")["protected_unchanged"] is not False:
        raise ValueError("This qualification targets the recorded protected-test violation")
    checks = read(checks_path)
    original_check, = checks[TASK]
    check = copy.deepcopy(original_check)
    check["coverage"] = original_check.get("coverage", []) + GUIDANCE
    if {k: v for k, v in check.items() if k != "coverage"} != {k: v for k, v in original_check.items() if k != "coverage"}:
        raise ValueError("Only task-local public guidance may change")
    public = verification.PublicCheck(**check)
    public.validate((runs["main"] / "instruction.txt").read_text())
    destination, inputs = FOLDER / "qualification", FOLDER / "inputs"
    destination.mkdir()
    inputs.mkdir()
    checks[TASK] = [check]
    write(inputs / "checks.json", checks)
    tasks = read(tasks_path)
    tasks["selected"] = [task]
    write(inputs / "tasks.json", tasks)
    sources = {str(path.relative_to(ROOT)): sha(path) for path in (Path(__file__), FOLDER / "PLAN.md", manifest_path,
        SNAPSHOT, tasks_path, checks_path, pins_path, PARENTS / "main-plan.json", PARENTS / "repeat-plan.json")}
    for run in runs.values():
        for path in [run / name for name in ("instruction.txt", "result.json", "candidate.patch", "model.jsonl", "tools.jsonl", "controller.jsonl", "final-verification.json")] + [run.with_suffix(".protocol.json")]:
            sources[str(path.relative_to(ROOT))] = sha(path)
    record = {"phase": "waiting_original_pool_exclusive", "task": TASK, "pin": pin, "new_model_calls": 0,
        "new_original_grader_calls": 0, "source_files_sha256": sources, "actual_loaded_runtime_modules": loaded}
    rows = []
    try:
        environment = os.environ | {"PYTHONPATH": str(RUNTIME) + os.pathsep + str(ROOT),
            "COURSE_PINNED_IMAGE_COPY_DRIVER": str(ROOT / parent["image_copy_driver"])}
        prepare_missing_image(task, environment)
        write(FOLDER / "resource-request.json", {"requested_at": time.time(), "exclusive": True, "label": "qualify-xarray4695-preservation", "new_model_calls": 0})
        with ResourceLease(ROOT / parent["resource_pool"], exclusive=True, label="qualify-xarray4695-preservation"):
            write(FOLDER / "resource-admission.json", {"admitted_at": time.time(), "exclusive": True, "memory_mb": 3072, "cpus": 2, "new_model_calls": 0})
            for name, patch_arm, restore_tests, expected_state, expected_trusted in (
                    ("base", None, False, "passed", True),
                    ("recorded_bad_repeat", "repeat", False, "protected_dependency_changed", False),
                    ("recorded_good_main", "main", False, "passed", True),
                    ("recorded_repeat_tests_restored", "repeat", True, "passed", True)):
                output = destination / name
                output.mkdir()
                options = benchmarks.swe_public_dependencies(task)
                options["read_only_mounts"] = options.get("read_only_mounts", ()) + benchmarks.runtime_mounts("linux/amd64")
                with docker_target.DockerTarget(pin, "/testbed", platform="linux/amd64", memory_mb=3072, cpus=2,
                        read_only_empty_dirs=benchmarks.SWE_HIDDEN_CACHES, **options) as target:
                    if target.image != pin:
                        raise ValueError("The actual engineering target differs from the original pin")
                    benchmarks.check_swe_checkout(task, target, output)
                    original_test = target.exec("sha256sum xarray/tests/test_dataarray.py", timeout=20)
                    if original_test["returncode"]:
                        raise ValueError("The original protected public test is unavailable")
                    controlled = controller.ControlledEnvironment(target, output, agent.RunLimits(**parent["limits"]), (public,),
                        {"kind": "repository", "python": "/opt/miniconda3/envs/testbed/bin/python"}, controller.Budget(3600), False)
                    if patch_arm:
                        target.upload_file(runs[patch_arm] / "candidate.patch", "/qualification.patch")
                        applied = target.exec("git apply --check /qualification.patch && git apply /qualification.patch", timeout=30)
                        write(output / "patch-process.json", applied)
                        if applied["returncode"]:
                            raise ValueError("The actual archived candidate did not apply:" + name)
                    if restore_tests:
                        restored = target.exec("git apply -R --include=xarray/tests/test_dataarray.py /qualification.patch", timeout=30)
                        write(output / "restore-test-process.json", restored)
                        if restored["returncode"]:
                            raise ValueError("The original test hunk could not be restored exactly")
                    issue = "import numpy as np;from xarray import DataArray;d=DataArray(np.zeros((2,2)),dims=['dim1','method'],coords={'dim1':['x','y'],'method':['a','b']});assert d.loc[dict(dim1='x',method='a')].item()==0;print('original-issue-example-passed')"
                    issue_process = target.exec("/opt/miniconda3/envs/testbed/bin/python -c " + shlex.quote(issue), timeout=30)
                    write(output / "original-issue-process.json", issue_process)
                    if (issue_process["returncode"] == 0) != (patch_arm is not None):
                        raise ValueError("The actual original issue behavior differs from the retained candidate diagnosis")
                    submit = {"operation": "submit", "note": "Engineering replay of existing C0 submit gate"}
                    pending = controlled.execute(submit)
                    write(output / "pending-submit.json", pending)
                    if "submission_rejected" not in pending["output"] or controlled.final_report is not None:
                        raise ValueError("The existing v20 C0 gate accepted pending public evidence")
                    actual = controlled.verify(public.check_id, "zero_model_original_public_check_and_preservation")
                    write(output / "actual-verification.json", actual)
                    if actual["state"] != expected_state:
                        raise ValueError("The real unchanged check/guard did not classify:" + name)
                    saved = controlled.execute({"operation": "save", "note": "Engineering save of actual verified state"})
                    write(output / "save-process.json", saved)
                    accepted = False
                    try:
                        outcome = controlled.execute(submit)
                    except Submitted:
                        outcome = {"submitted": True}
                        accepted = True
                    write(output / "post-verification-submit.json", outcome)
                    if accepted != expected_trusted:
                        raise ValueError("The actual existing C0 submit gate misclassified:" + name)
                    if not accepted and "submission_rejected" not in outcome["output"]:
                        raise ValueError("The bad candidate lacks explicit recoverable refusal")
                    final = controlled.finish("zero_model_preservation_diagnostic")
                    final_test = target.exec("sha256sum xarray/tests/test_dataarray.py && git diff --check && git diff --binary", timeout=30)
                    write(output / "actual-candidate-process.json", final_test)
                    if final["protected_unchanged"] is not expected_trusted or final["valid_verification"] is not expected_trusted:
                        raise ValueError("The actual terminal protection/evidence changed:" + name)
                    if expected_trusted and final_test["stdout"].splitlines()[0] != original_test["stdout"].strip():
                        raise ValueError("An accepted candidate did not preserve the exact original test bytes")
                    rows.append({"variant": name, "state": actual["state"], "submit_accepted": accepted,
                        "original_issue_example_passed": issue_process["returncode"] == 0, "final": final,
                        "pending_submit_rejected": True, "original_test_sha256": original_test["stdout"].split()[0],
                        "final_test_sha256": final_test["stdout"].split()[0],
                        "actual_verification_sha256": sha(output / "actual-verification.json")})
                print(json.dumps({"variant": name, "state": actual["state"], "submit_accepted": accepted}), flush=True)
        for name, expected in sources.items():
            if sha(ROOT / name) != expected:
                raise ValueError("An original200/archived/source byte changed during engineering qualification:" + name)
        record.update(phase="actual_v20_original_pin_unchanged_public_check_protection_and_submit_gate_qualified", variants=rows,
            runtime_root=str(RUNTIME.relative_to(ROOT)), runtime_manifest_sha256=sha(manifest_path),
            new_checks_sha256=sha(inputs / "checks.json"), new_tasks_sha256=sha(inputs / "tasks.json"),
            driver_sha256=sha(Path(__file__)), original200_snapshot_sha256=sha(SNAPSHOT),
            interpretation="Engineering replay,not model behavior. The unchanged base public subset passes while the original issue fails;no claim that the old public command covers this bug. Bad repeat has passing pytest but invalid protection and rejected submission. Good main and repeat with exactly restored original tests pass verify/save/submit. Original raw/q values and all costs remain unchanged.")
    except BaseException as error:
        record.update(phase="engineering_qualification_failed", variants=rows, error_type=type(error).__name__, error=str(error), traceback=traceback.format_exc())
        raise
    finally:
        write(destination / "result.json", record)


if __name__ == "__main__":
    main()
