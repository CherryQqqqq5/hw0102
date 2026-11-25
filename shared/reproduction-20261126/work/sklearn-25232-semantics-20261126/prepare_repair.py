import copy
import hashlib
import json
from pathlib import Path


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def object_sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def main():
    root, folder = Path.cwd(), Path(__file__).parent.resolve()
    parent_folder = root / "work/free-recovery35-20261126/hy4-plans"
    parents = {arm: read(parent_folder / (arm + "-plan.json")) for arm in ("main", "repeat")}
    parent = parents["main"]
    qualification = folder / "qualification/result.json"
    proof, inputs = read(qualification), folder / "inputs"
    if (proof["phase"] != "actual_c0_public_contract_and_separate_original_grader_passed"
            or proof["new_model_calls"] != 0 or proof["original_grader_calls"] != 1
            or proof["separate_engineering_original_grade"]["passed"] is not True
            or proof["driver_sha256"] != sha(folder / "qualify_public_contract.py")
            or proof["probe_sha256"] != sha(folder / "public_nan_probe.py")
            or proof["reference_patch_sha256"] != sha(folder / "separate-public-reference.patch")
            or proof["reference_source_sha256"] != sha(folder / "reference-iterative.py")
            or proof["new_checks_sha256"] != sha(inputs / "checks.json")
            or proof["new_tasks_sha256"] != sha(inputs / "tasks.json")
            or proof["source_plan_sha256"] != sha(parent_folder / "main-plan.json")):
        raise ValueError("The original-pin public C0 qualification and separate engineering grade are incomplete")
    if {row["variant"]: row["state"] for row in proof["variants"]} != {
            "base": "failed", "actual_main": "failed", "actual_repeat": "failed", "public_reference": "passed"}:
        raise ValueError("The real base/candidate/reference contracts were not distinguished")
    for row in proof["variants"]:
        output = folder / "qualification" / row["variant"]
        if (sha(output / "public-probe-process.json") != row["actual_public_probe_process_sha256"]
                or sha(output / "actual-verification.json") != row["actual_verification_sha256"]
                or row["details"]["total"] != 12 or row["final"]["protected_unchanged"] is not True):
            raise ValueError("The actual public12/Controller result changed")
    reference, = [row for row in proof["variants"] if row["variant"] == "public_reference"]
    controls = reference["numeric_negative_controls"]
    if len(controls) != 4 or not all(item["rejected"] is True for item in controls):
        raise ValueError("Actual zero/one numerical fallback rejection is missing")
    tasks_path, checks_path = parent_folder / "tasks.json", parent_folder / "checks.json"
    task, = read(inputs / "tasks.json")["selected"]
    task_id = "scikit-learn__scikit-learn-25232"
    tasks = read(tasks_path)
    checks, original_checks = read(inputs / "checks.json"), read(checks_path)
    if task["id"] != task_id or task not in tasks["selected"]:
        raise ValueError("The prospective task differs from the fixed original75 manifest")
    for arm, source in parents.items():
        if (source["tasks_sha256"] != sha(tasks_path) or source["checks_sha256"] != sha(checks_path)
                or source["runtime_root"] != parent["runtime_root"] or source["limits"] != parent["limits"]
                or source["configuration_by_task"] != parent["configuration_by_task"]
                or source["runtime_sha256"] != parent["runtime_sha256"]
                or source["runtime_resources_sha256"] != parent["runtime_resources_sha256"]
                or source["configuration_by_task"][task_id] != "C0"):
            raise ValueError("An unchanged parent runtime/input/budget differs:" + arm)
    files = {}

    def bind(path, expected=None):
        path = path.resolve()
        actual = sha(path)
        if expected is not None and actual != expected:
            raise ValueError("A frozen dependency changed:" + str(path))
        if path in files and files[path] != actual:
            raise ValueError("A merged source expectation conflicts:" + str(path))
        files[path] = actual

    runtime = Path(parent["runtime_root"])
    for source in parents.values():
        for name, expected in (source["runtime_sha256"] | source["runtime_resources_sha256"]).items():
            bind(runtime / name, expected)
        for category in ("request_guard_sha256", "image_preparation_sha256"):
            for name, expected in source[category].items():
                bind(root / name, expected)
        for path_key, sha_key in (("driver_path", "driver_sha256"), ("coordinator_path", "coordinator_sha256")):
            bind(root / source[path_key], source[sha_key])
    bind(root / "work/codebuddy/node_modules/@tencent-ai/codebuddy-code/dist/codebuddy-headless.js", parent["client_sha256"])
    bind(root / "work/free-channel-capabilities-20261122/cloud-model-metadata.json", parent["image_metadata_sha256"])
    bind(root / "work/vmshare/elf-public-check-deps/pyelftools-0.33-py3-none-any.whl", parent["elf_wheel_sha256"])
    pins_path = root / parent["baseline_queue"] / "environment-pins.json"
    bind(pins_path, parent["environment_pins_sha256"])
    pins = read(pins_path)["pins"]
    if pins[task_id] != proof["pin"]:
        raise ValueError("The original image and actual qualification pin differ")
    unchanged = {}
    for item in tasks["selected"]:
        name = item["id"]
        if name != task_id:
            if checks[name] != original_checks[name]:
                raise ValueError("An unrelated check changed:" + name)
            unchanged[name] = {"task_sha256": object_sha(item), "selected_checks_sha256": object_sha(checks[name]),
                "original_image_id": pins[name], "configuration": parent["configuration_by_task"][name]}
    if len(unchanged) != 74:
        raise ValueError("Exactly74 unchanged definitions must be registered")
    previous_paths = {
        "json": "work/json-in-semantics-20261125/oracle-bool/ascii-transport/frozen/plan.json",
        "feal": "work/feal-linear-helper-20261125/readmission/plan.json",
        "xarray": "work/xarray-2905-semantics-20261125/frozen/plan.json",
        "pytest": "work/pytest-7205-semantics-20261125/frozen/plan.json",
        "preservation": "work/pytest-5631-preservation-20261125/frozen/plan.json",
        "relu": "work/hy4-submit-boundary-20261125/frozen-pair-r2/plan.json"}
    previous = {name: read(root / path) for name, path in previous_paths.items()}
    changed = {plan["task"] for plan in previous.values()} | {task_id}
    if len(changed) != 7:
        raise ValueError("The proposed combined policy requires exactly seven distinct task scopes")
    combined = {}
    for item in tasks["selected"]:
        name = item["id"]
        if name in changed:
            continue
        entry = unchanged[name]
        for plan in previous.values():
            registered = plan["unchanged_task_inputs"][name]
            if (any(entry[key] != value for key, value in registered.items())
                    or read(root / plan["checks"])[name] != original_checks[name]
                    or plan["limits"] != parent["limits"]):
                raise ValueError("A proposed68-task inherited input differs:" + name)
        combined[name] = entry
    if len(combined) != 68:
        raise ValueError("Seven scopes permit only68 inherited task definitions")
    protocols, protocol_paths = [], []
    for index, source in enumerate(parents.values(), 1):
        path = root / source["queue"] / (task_id + "-C0-r" + str(index) + ".protocol.json")
        protocols.append({key: value for key, value in read(path).items() if key != "historical_unknown_calls_preserved"})
        protocol_paths.append(path)
    if protocols[0] != protocols[1]:
        raise ValueError("The original main/repeat task protocols differ")
    for name, expected in proof["source_original_scores_sha256"].items():
        bind(root / name, expected)
    queue = "work/vmshare/performance-sklearn-nan-contract-20261126"
    destination = folder / "frozen"
    destination.mkdir()
    capture = read(root / parent["artifact_capture_policy"])
    revised_capture = copy.deepcopy(capture)
    revised_capture["queues"].append(queue)
    if {key: value for key, value in capture.items() if key != "queues"} != {
            key: value for key, value in revised_capture.items() if key != "queues"}:
        raise ValueError("Only the prospective queue may change in the capture policy")
    write(destination / "capture-policy.json", revised_capture)
    additional = [Path(__file__), folder / "PLAN.md", folder / "public_nan_probe.py", folder / "reference-iterative.py",
        folder / "qualify_public_contract.py", folder / "separate-public-reference.patch", folder / "prior-six-scope-join.py.txt",
        qualification, folder / "qualification.resources.json", inputs / "tasks.json", inputs / "checks.json", tasks_path,
        checks_path, root / parent["resource_driver"], root / "work/parallel-free-evaluation-20261124/resource_trial.py",
        root / "course_eval/resource_pool.py", root / "work/parallel-free-evaluation-20261124/run_fixed_free_trials.py",
        root / "scripts/export_performance_evidence.py", root / "scripts/summarize_performance_comparison.py",
        root / parent["artifact_capture_policy"], destination / "capture-policy.json"]
    additional += [parent_folder / (arm + "-plan.json") for arm in parents] + protocol_paths
    additional += [root / path for path in previous_paths.values()]
    additional += [folder / "public-sources" / name for name in ("base-iterative.py", "current-main-iterative.py",
        "sklearn-1.5.2-iterative.py", "base-public-test-impute.py")]
    additional += [path for path in (folder / "qualification").rglob("*") if path.is_file() and not path.is_symlink()]
    for path in additional:
        bind(path)
    plan = {"stage": "frozen_after_exact_original_c0_public_nan_contract_qualification", "phase": "RUN", "task": task_id,
        "prospective_trials": ["nan-contract-main-r1", "nan-contract-repeat-r2"], "model": "hy4flash-free",
        "runtime_root": str(runtime.relative_to(root)), "limits": parent["limits"], "pin": pins[task_id],
        "manifest": str((inputs / "tasks.json").relative_to(root)), "checks": str((inputs / "checks.json").relative_to(root)),
        "expected_protocol": protocols[0], "driver": parent["driver_path"], "resource_driver": parent["resource_driver"],
        "image_copy_driver": parent["image_copy_driver"], "coordinator_path": parent["coordinator_path"],
        "artifact_capture_policy": str((destination / "capture-policy.json").relative_to(root)), "queue": queue,
        "unchanged_task_inputs": unchanged, "combined_seven_scope_unchanged_task_inputs": combined,
        "source_cohorts": {arm: source["queue"] for arm, source in parents.items()},
        "qualification_source_results_sha256": proof["source_original_scores_sha256"],
        "all_files_sha256": {str(path.relative_to(root)): expected for path, expected in sorted(files.items())},
        "main_variable": "Append the same public12 NaN-initialization/tree-iteration/fitted-range contract and public training-mask guidance to this task's original public-issue command only",
        "model_input_boundary": "Original problem/repository plus public12 probe and published generic missing-mask mechanism. No engineering reference, old model candidate, original hidden test or gold patch is provided to the model.",
        "success": "Two fixed fresh native sessions, actual original score and final current public/protected verification reported separately",
        "failure": "Retain every actual low score;no success-based resampling. New unknown/nonzero fee or unscoreable execution stops dispatch",
        "inheritance": "This single-task revision registers74 unchanged definitions. A future seven-scope joint policy may inherit68x2 unchanged positions plus14 prospective revision positions only after exact input/result review;the joint acceptance has not been performed.",
        "all_original225_scores_and_development_costs_preserved": True, "new_model_calls_during_preparation": 0}
    with (destination / "plan.json").open("x") as stream:
        stream.write(json.dumps(plan, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"status": "frozen", "prospective_sessions": 2, "unchanged_task_inputs": 74,
        "combined_inherited_task_definitions": 68, "bound_files": len(files), "new_model_calls": 0}), flush=True)


if __name__ == "__main__":
    main()
