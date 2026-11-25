import copy
import hashlib
import json
from pathlib import Path

from qualify_preservation import GUIDANCE


ROOT = Path.cwd().resolve()
FOLDER = Path(__file__).resolve().parent
PARENTS = ROOT / "work/free-recovery35-20261126/hy4-plans"
RUNTIME = ROOT / "work/frozen-performance-hy4-submit-boundary-v20"
TASK = "pydata__xarray-4695"


def read(path):
    return json.loads(path.read_bytes())


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def object_sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def write(path, value):
    with path.open("xb") as stream:
        stream.write((json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode())


def main():
    qualification = FOLDER / "qualification/result.json"
    proof = read(qualification)
    if (proof["phase"] != "actual_v20_original_pin_unchanged_public_check_protection_and_submit_gate_qualified"
            or proof["new_model_calls"] != 0 or proof["new_original_grader_calls"] != 0
            or proof["driver_sha256"] != sha(FOLDER / "qualify_preservation.py")):
        raise ValueError("The actual original-pin Controller qualification must finish first")
    expected = {"base": ("passed", True, True), "recorded_bad_repeat": ("protected_dependency_changed", False, False),
        "recorded_good_main": ("passed", True, True), "recorded_repeat_tests_restored": ("passed", True, True)}
    actual = {row["variant"]: (row["state"], row["final"]["protected_unchanged"], row["submit_accepted"]) for row in proof["variants"]}
    if actual != expected or not all(row["pending_submit_rejected"] for row in proof["variants"]):
        raise ValueError("Real protection, pending/invalid submit refusal or normal acceptance is incomplete")
    parents = {arm: read(PARENTS / (arm + "-plan.json")) for arm in ("main", "repeat")}
    parent = parents["main"]
    tasks_path, checks_path = PARENTS / "tasks.json", PARENTS / "checks.json"
    manifest_path, new_checks = FOLDER / "inputs/tasks.json", FOLDER / "inputs/checks.json"
    if sha(manifest_path) != proof["new_tasks_sha256"] or sha(new_checks) != proof["new_checks_sha256"]:
        raise ValueError("The actually qualified input/check bytes changed")
    task, = read(manifest_path)["selected"]
    tasks, original, proposed = read(tasks_path), read(checks_path), read(new_checks)
    if task["id"] != TASK or task not in tasks["selected"]:
        raise ValueError("The prospective task is not the original task")
    before, = original[TASK]
    after, = proposed[TASK]
    if ({k: v for k, v in before.items() if k != "coverage"} != {k: v for k, v in after.items() if k != "coverage"}
            or after["coverage"] != before.get("coverage", []) + GUIDANCE):
        raise ValueError("Only the three qualified public preservation guidance entries may change")
    files = {}

    def bind(path, expected_sha=None):
        path = path.resolve(strict=True)
        if not path.is_relative_to(ROOT):
            raise ValueError("A frozen source escaped the author project")
        actual_sha = sha(path)
        if expected_sha is not None and actual_sha != expected_sha or path in files and files[path] != actual_sha:
            raise ValueError("A retained expected source hash changed:" + str(path))
        files[path] = actual_sha

    for name, expected_sha in proof["source_files_sha256"].items():
        bind(ROOT / name, expected_sha)
    runtime_manifest = ROOT / "work/hy4-submit-boundary-20261125/runtime-manifest.json"
    runtime = read(runtime_manifest)
    bind(runtime_manifest, proof["runtime_manifest_sha256"])
    for name, expected_sha in runtime["files"].items():
        bind(RUNTIME / name, expected_sha)
    if (runtime["files"]["course_eval/codebuddy_free.py"] != parent["billing_validator_sha256"]
            or runtime["files"]["course_eval/financial_stop.py"] != parent["runtime_sha256"]["course_eval/financial_stop.py"]
            or runtime["changed_original_resources"] != ["course_eval/controller.py", "course_eval/terminal_runtime.py"]
            or runtime["new_resources"] != ["course_eval/oracle_access.py", "course_eval/relu_export.py"]):
        raise ValueError("Reuse only the previously reviewed v20 boundary; fee semantics must stay original")
    for arm, source in parents.items():
        if (source["tasks_sha256"] != sha(tasks_path) or source["checks_sha256"] != sha(checks_path)
                or source["limits"] != parent["limits"] or source["model"] != parent["model"]
                or source["runtime_sha256"] != parent["runtime_sha256"] or source["configuration_by_task"][TASK] != "C0"):
            raise ValueError("The actual original two cohorts differ:" + arm)
        for category in ("request_guard_sha256", "image_preparation_sha256"):
            for name, expected_sha in source[category].items():
                bind(ROOT / name, expected_sha)
        for path_key, sha_key in (("driver_path", "driver_sha256"), ("coordinator_path", "coordinator_sha256")):
            bind(ROOT / source[path_key], source[sha_key])
    for path, expected_sha in ((ROOT / "work/codebuddy/node_modules/@tencent-ai/codebuddy-code/dist/codebuddy-headless.js", parent["client_sha256"]),
            (ROOT / "work/free-channel-capabilities-20261122/cloud-model-metadata.json", parent["image_metadata_sha256"]),
            (ROOT / "work/vmshare/elf-public-check-deps/pyelftools-0.33-py3-none-any.whl", parent["elf_wheel_sha256"])):
        bind(path, expected_sha)
    pin_path = ROOT / parent["baseline_queue"] / "environment-pins.json"
    bind(pin_path, parent["environment_pins_sha256"])
    pins = read(pin_path)["pins"]
    if pins[TASK] != proof["pin"]:
        raise ValueError("The prospective and actually qualified image pin differ")
    unchanged = {}
    for item in tasks["selected"]:
        name = item["id"]
        if name != TASK:
            if proposed[name] != original[name]:
                raise ValueError("An unrelated task/check changed:" + name)
            unchanged[name] = {"task_sha256": object_sha(item), "selected_checks_sha256": object_sha(original[name]),
                "original_image_id": pins[name], "configuration": parent["configuration_by_task"][name]}
    previous_paths = {
        "json": "work/json-in-semantics-20261125/oracle-bool/ascii-transport/frozen/plan.json",
        "feal": "work/feal-linear-helper-20261125/readmission/plan.json",
        "xarray": "work/xarray-2905-semantics-20261125/frozen/plan.json",
        "pytest": "work/pytest-7205-semantics-20261125/frozen/plan.json",
        "preservation": "work/pytest-5631-preservation-20261125/frozen/plan.json",
        "relu": "work/hy4-submit-boundary-20261125/frozen-pair-r2/plan.json",
        "sklearn": "work/sklearn-25232-semantics-20261126/frozen/plan.json"}
    previous = {name: read(ROOT / path) for name, path in previous_paths.items()}
    changed = {plan["task"] for plan in previous.values()} | {TASK}
    combined = {}
    for name, entry in unchanged.items():
        if name in changed:
            continue
        for plan in previous.values():
            if (any(entry[key] != value for key, value in plan["unchanged_task_inputs"][name].items())
                    or read(ROOT / plan["checks"])[name] != original[name] or plan["limits"] != parent["limits"]):
                raise ValueError("An inherited67-task definition differs:" + name)
        combined[name] = entry
    if len(unchanged) != 74 or len(changed) != 8 or len(combined) != 67:
        raise ValueError("Exactly eight task scopes/67 inherited definitions are required")
    protocols = []
    for arm, index in (("main", 1), ("repeat", 2)):
        path = ROOT / parents[arm]["queue"] / (TASK + "-C0-r" + str(index) + ".protocol.json")
        protocols.append({key: value for key, value in read(path).items() if key != "historical_unknown_calls_preserved"})
        bind(path)
    if protocols[0] != protocols[1]:
        raise ValueError("The original task protocols differ")
    expected_protocol = protocols[0] | {"runtime_root": str(RUNTIME.relative_to(ROOT))}
    queue = "work/vmshare/performance-xarray-loc-preservation-v20-20261126"
    if (ROOT / queue).exists():
        raise FileExistsError("The two prospective labels require a genuinely unused queue")
    destination = FOLDER / "frozen"
    destination.mkdir()
    original_policy = read(ROOT / parent["artifact_capture_policy"])
    policy = copy.deepcopy(original_policy)
    if queue in policy["queues"]:
        raise ValueError("The proposed capture queue was already registered")
    policy["queues"].append(queue)
    if {key: value for key, value in policy.items() if key != "queues"} != {key: value for key, value in original_policy.items() if key != "queues"}:
        raise ValueError("Only the new queue whitelist may change in artifact capture")
    write(destination / "capture-policy.json", policy)
    additional = [Path(__file__), FOLDER / "PLAN.md", FOLDER / "qualify_preservation.py", FOLDER / "root-cause-review.json",
        qualification, manifest_path, new_checks, tasks_path, checks_path, ROOT / parent["resource_driver"],
        ROOT / "work/parallel-free-evaluation-20261124/resource_trial.py", ROOT / "course_eval/resource_pool.py",
        ROOT / "work/parallel-free-evaluation-20261124/run_fixed_free_trials.py", ROOT / "scripts/export_performance_evidence.py",
        ROOT / "scripts/summarize_performance_comparison.py", ROOT / parent["artifact_capture_policy"], destination / "capture-policy.json"]
    additional += [PARENTS / (arm + "-plan.json") for arm in parents] + [ROOT / path for path in previous_paths.values()]
    additional += [path for path in (FOLDER / "qualification").rglob("*") if path.is_file() and not path.is_symlink()]
    additional += [FOLDER / "resource-request.json", FOLDER / "resource-admission.json"]
    for path in additional:
        bind(path)
    write(destination / "plan.json", {"stage": "frozen_after_actual_v20_original_pin_preservation_and_submit_gate_qualification", "phase": "RUN",
        "task": TASK, "prospective_trials": ["loc-preserve-main-r1", "loc-preserve-repeat-r2"], "model": "hy4flash-free",
        "runtime_root": str(RUNTIME.relative_to(ROOT)), "limits": parent["limits"], "pin": pins[TASK],
        "manifest": str(manifest_path.relative_to(ROOT)), "checks": str(new_checks.relative_to(ROOT)), "expected_protocol": expected_protocol,
        "driver": parent["driver_path"], "resource_driver": parent["resource_driver"], "image_copy_driver": parent["image_copy_driver"],
        "coordinator_path": parent["coordinator_path"], "artifact_capture_policy": str((destination / "capture-policy.json").relative_to(ROOT)), "queue": queue,
        "unchanged_task_inputs": unchanged, "combined_eight_scope_unchanged_task_inputs": combined,
        "source_cohorts": {arm: source["queue"] for arm, source in parents.items()},
        "all_files_sha256": {str(path.relative_to(ROOT)): expected_sha for path, expected_sha in sorted(files.items())},
        "main_variable": "Task-local three preservation guidance entries plus reuse of existing v20 C0 current-public/protection submit gate;unchanged original public command/check/scope",
        "runtime_scope": "Only these two new xarray4695 trials use v20 here. Existing ReLU v20 and other v18/scoped runtimes retain their actual origins. No claim of v20 equivalence or rerun for the other67 inherited tasks.",
        "model_input_boundary": "Original public task/repository,unchanged public check and three preservation instructions. No archived candidate,engineering replay,grade fixture or gold patch is provided as model input.",
        "failure": "Retain both fixed new actual outcomes and all original true/false/null/costs;no score-based resampling;new unknown/nonzero financial evidence stops dispatch",
        "inheritance": "Prospective eight-scope join may use67x2 inherited positions plus16 fixed revised positions only after actual results/input/source audit;not accepted by this preparation.",
        "all_original200_and_remaining225_scores_preserved": True, "new_model_calls_during_preparation": 0})
    print(json.dumps({"status": "frozen_for_parent_review_not_started", "prospective_sessions": 2, "bindings": len(files), "combined_inherited_definitions": 67, "new_model_calls": 0}), flush=True)


if __name__ == "__main__":
    main()
