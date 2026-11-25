import hashlib
import json
from pathlib import Path


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def object_sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def main():
    root, folder = Path.cwd(), Path(__file__).parent.resolve()
    parent_folder = root / "work/parallel-free-evaluation-20261124/final-sql75-recovered"
    parents = {arm: read(parent_folder / (arm + "-plan.json")) for arm in ("main", "repeat")}
    parent = parents["main"]
    qualification = folder / "qualification/result.json"
    proof = read(qualification)
    inputs = folder / "inputs"
    if (proof["phase"] != "actual_c0_public_contract_and_separate_original_grader_passed"
            or proof["new_model_calls"] != 0 or proof["original_grader_calls"] != 1
            or proof["separate_engineering_original_grade"]["passed"] is not True
            or proof["driver_sha256"] != sha(folder / "qualify_public_contract.py")
            or proof["probe_sha256"] != sha(folder / "public_object_probe.py")
            or proof["reference_patch_sha256"] != sha(folder / "separate-public-reference.patch")
            or proof["new_checks_sha256"] != sha(inputs / "checks.json")
            or proof["new_tasks_sha256"] != sha(inputs / "tasks.json")
            or proof["source_plan_sha256"] != sha(parent_folder / "main-plan.json")):
        raise ValueError("The actual C0 public contract and separate reference original grade are not complete")
    if {row["variant"]: row["state"] for row in proof["variants"]} != {
            "base": "failed", "actual_main": "failed", "actual_repeat": "failed", "public_reference": "passed"}:
        raise ValueError("The actual original and repaired contracts were not distinguished")
    tasks_path, checks_path = parent_folder / "tasks.json", parent_folder / "checks.json"
    task, = read(inputs / "tasks.json")["selected"]
    tasks = read(tasks_path)
    checks, original_checks = read(inputs / "checks.json"), read(checks_path)
    task_id = "pydata__xarray-2905"
    if task["id"] != task_id or task not in tasks["selected"]:
        raise ValueError("The prospective task differs from the actual original75 scope")
    for arm, source in parents.items():
        if (source["tasks_sha256"] != sha(tasks_path) or source["checks_sha256"] != sha(checks_path)
                or source["runtime_root"] != parent["runtime_root"] or source["limits"] != parent["limits"]
                or source["configuration_by_task"] != parent["configuration_by_task"]
                or source["runtime_sha256"] != parent["runtime_sha256"]
                or source["runtime_resources_sha256"] != parent["runtime_resources_sha256"]
                or source["configuration_by_task"][task_id] != "C0"):
            raise ValueError("An input intended for unchanged-task inheritance differs: " + arm)
    runtime = Path(parent["runtime_root"])
    files = {runtime / name: expected for name, expected in
        (parent["runtime_sha256"] | parent["runtime_resources_sha256"]).items()}
    files.update({root / name: expected for name, expected in
        (parent["request_guard_sha256"] | parent["image_preparation_sha256"]).items()})
    files.update({root / parent["driver_path"]: parent["driver_sha256"],
        root / parent["coordinator_path"]: parent["coordinator_sha256"],
        root / "work/codebuddy/node_modules/@tencent-ai/codebuddy-code/dist/codebuddy-headless.js": parent["client_sha256"],
        root / "work/free-channel-capabilities-20261122/cloud-model-metadata.json": parent["image_metadata_sha256"],
        root / "work/vmshare/elf-public-check-deps/pyelftools-0.33-py3-none-any.whl": parent["elf_wheel_sha256"]})
    for path, expected in files.items():
        if sha(path) != expected:
            raise ValueError("A frozen runtime, client or financial guard dependency changed: " + str(path))
    pins_path = root / parent["baseline_queue"] / "environment-pins.json"
    if sha(pins_path) != parent["environment_pins_sha256"]:
        raise ValueError("The actual original environment registry changed")
    pins = read(pins_path)["pins"]
    if pins[task_id] != proof["pin"]:
        raise ValueError("The actual qualification used a different original image")
    unchanged = {}
    for item in tasks["selected"]:
        name = item["id"]
        if name != task_id:
            if checks[name] != original_checks[name]:
                raise ValueError("The public-contract revision changed an unrelated task")
            unchanged[name] = {"task_sha256": object_sha(item), "selected_checks_sha256": object_sha(checks[name]),
                "original_image_id": pins[name], "configuration": parent["configuration_by_task"][name]}
    if len(unchanged) != 74:
        raise ValueError("Exactly74 unchanged task definitions must be registered")
    protocols, protocol_paths = [], []
    for index, source in enumerate(parents.values(), 1):
        path = root / source["queue"] / (task_id + "-C0-r" + str(index) + ".protocol.json")
        protocols.append({key: value for key, value in read(path).items() if key != "historical_unknown_calls_preserved"})
        protocol_paths.append(path)
    if protocols[0] != protocols[1]:
        raise ValueError("The two original task protocols differ")
    for name, expected in proof["source_original_scores_sha256"].items():
        if sha(root / name) != expected:
            raise ValueError("An original failed score changed")
    additional = [Path(__file__).resolve(), folder / "public_object_probe.py", folder / "qualify_public_contract.py",
        folder / "separate-public-reference.patch", folder / "public-sources/original-variable.py",
        folder / "public-sources/current-variable.py", qualification, inputs / "tasks.json", inputs / "checks.json",
        tasks_path, checks_path, pins_path, root / parent["resource_driver"],
        root / "work/parallel-free-evaluation-20261124/resource_trial.py", root / "course_eval/resource_pool.py",
        root / "work/parallel-free-evaluation-20261124/run_fixed_free_trials.py",
        root / "scripts/export_performance_evidence.py", root / "scripts/summarize_performance_comparison.py",
        root / parent["artifact_capture_policy"], folder / "root-cause-review.json"]
    additional += [parent_folder / (arm + "-plan.json") for arm in parents] + protocol_paths
    additional += [root / name for name in proof["source_original_scores_sha256"]]
    additional += [root / name for name in proof["actual_loaded_runtime_modules"]]
    additional += [path for path in (folder / "qualification").rglob("*") if path.is_file() and not path.is_symlink()]
    additional += [folder / "qualification-context-failed-r0/failure.json",
        folder / "qualification-context-failed-r0/reference.patch"]
    bindings = {str(path.relative_to(root)): sha(path) for path in set(files) | set(additional)}
    destination = folder / "frozen"
    destination.mkdir()
    plan = {"stage": "frozen_after_exact_original_c0_public_object_contract_qualification", "phase": "RUN",
        "task": task_id, "prospective_trials": ["object-contract-main-r1", "object-contract-repeat-r2"],
        "main_variable": "Append26 public problem-derived identity/conversion cases and official named-container guidance to the same public-regression interface; all model runtime, budgets and original scoring remain unchanged",
        "runtime_root": str(runtime.relative_to(root)), "limits": parent["limits"], "model": "hy4flash-free",
        "pin": pins[task_id], "manifest": str((inputs / "tasks.json").relative_to(root)),
        "checks": str((inputs / "checks.json").relative_to(root)), "expected_protocol": protocols[0],
        "driver": parent["driver_path"], "resource_driver": parent["resource_driver"],
        "image_copy_driver": parent["image_copy_driver"], "coordinator_path": parent["coordinator_path"],
        "artifact_capture_policy": parent["artifact_capture_policy"],
        "queue": "work/vmshare/performance-xarray-object-contract-v1-20261125",
        "unchanged_task_inputs": unchanged, "source_cohorts": {arm: source["queue"] for arm, source in parents.items()},
        "qualification_source_results_sha256": proof["source_original_scores_sha256"], "all_files_sha256": bindings,
        "success": "Both fixed fresh native sessions must pass actual original scoring and final public/protected checks",
        "failure": "Preserve valid failures without resampling; new unknown/nonzero cost or unscoreable execution stops dispatch",
        "model_input_boundary": "Only original public problem/repository, public26 checks and published container-identification guidance. Separate engineering reference and original hidden grading details are never supplied as model input.",
        "inheritance": "This plan changes one task only. A combined policy also changing JSON and FEAL may inherit only72x2 unchanged task records, and must obtain all6 fixed fresh revision scores. Entire original225 plus5 prior JSON development scores,6 final revisions and3 guidance ablations are retained; earlier SQL pilots and engineering original grading are separate.",
        "new_model_calls_during_preparation": 0}
    with (destination / "plan.json").open("x") as stream:
        stream.write(json.dumps(plan, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"status": "frozen", "prospective_sessions": 2, "unchanged_task_inputs": 74,
        "bound_files": len(bindings), "new_model_calls": 0}), flush=True)


if __name__ == "__main__":
    main()
