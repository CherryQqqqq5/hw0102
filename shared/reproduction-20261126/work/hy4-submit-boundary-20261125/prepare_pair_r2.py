import copy
import hashlib
import json
from pathlib import Path


ROOT = Path.cwd().resolve()
FOLDER = Path(__file__).resolve().parent
BASE = ROOT / "work/parallel-free-evaluation-20261124"
PARENT = BASE / "final-sql75-quota-recovered"
TASK = "model-extraction-relu-logits"
RUNTIME = ROOT / "work/frozen-performance-hy4-submit-boundary-v20"


def read(path):
    return json.loads(path.read_bytes())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def object_sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def write(path, value):
    with path.open("x") as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def main():
    destination = FOLDER / "frozen-pair-r2"
    if destination.exists():
        raise FileExistsError("Do not overwrite a prospective two-session plan")
    qualification_path = FOLDER / "linux-integration-r3/result.json"
    proof = read(qualification_path)
    if (proof["status"] != "PASS_ORIGINAL_PIN_ENGINEERING_NOT_MODEL_OR_ORIGINAL_SCORE"
            or proof["new_model_calls"] != 0 or proof["new_original_grader_calls"] != 0
            or proof["final_verification"]["valid_verification"] is not True
            or proof["final_verification"]["protected_unchanged"] is not True):
        raise ValueError("Actual original-pin public deployment and final Controller validation must pass first")
    parents = {arm: read(PARENT / (arm + "-plan.json")) for arm in ("main", "repeat")}
    parent = parents["main"]
    tasks, checks = read(PARENT / "tasks.json"), read(PARENT / "checks.json")
    original = next(task for task in tasks["selected"] if task["id"] == TASK)
    task = copy.deepcopy(original)
    task["candidate_scope"]["protected"].append("/opt/course-tools/relu_export.py")
    pins_path = ROOT / parent["baseline_queue"] / "environment-pins.json"
    pins = read(pins_path)["pins"]
    if proof["system_info"]["image"] != pins[TASK]:
        raise ValueError("The actual engineering qualification used another task image")
    unchanged = {item["id"]: {"task_sha256": object_sha(item),
        "selected_checks_sha256": object_sha(checks[item["id"]]), "original_image_id": pins[item["id"]],
        "configuration": parent["configuration_by_task"][item["id"]]} for item in tasks["selected"] if item["id"] != TASK}
    bindings = dict(proof["source_sha256"])
    bindings.update(parent["request_guard_sha256"] | parent["image_preparation_sha256"])
    protocols = []
    for arm, source in parents.items():
        if source["limits"] != parent["limits"] or source["configuration_by_task"][TASK] != "C0":
            raise ValueError("The original two source cohorts use different model budgets or task routes")
        directory = ROOT / source["queue"] / (TASK + "-C0-r" + str(source["repeat"]))
        protocol_path = directory.with_suffix(".protocol.json")
        protocols.append({key: value for key, value in read(protocol_path).items() if key != "historical_unknown_calls_preserved"})
        paths = [protocol_path, directory / "result.json", directory / "trial.json"]
        paths += list(directory.rglob("model.jsonl")) + list(directory.rglob("final-verification.json"))
        bindings.update({str(path.relative_to(ROOT)): sha(path) for path in paths})
    if protocols[0] != protocols[1]:
        raise ValueError("The two actual original source protocols differ")
    expected = protocols[0] | {"runtime_root": str(RUNTIME.relative_to(ROOT))}
    paths = [Path(__file__).resolve(), qualification_path, FOLDER / "qualification.json", FOLDER / "runtime-manifest.json",
        ROOT / parent["driver_path"], ROOT / parent["resource_driver"], BASE / "resource_trial.py",
        BASE / "run_fixed_free_trials.py", ROOT / "scripts/export_performance_evidence.py",
        ROOT / "scripts/summarize_performance_comparison.py", ROOT / parent["artifact_capture_policy"],
        ROOT / "work/codebuddy/node_modules/@tencent-ai/codebuddy-code/dist/codebuddy-headless.js",
        ROOT / "work/free-channel-capabilities-20261122/cloud-model-metadata.json",
        PARENT / "main-plan.json", PARENT / "repeat-plan.json", PARENT / "tasks.json", PARENT / "checks.json", pins_path]
    bindings.update({str(path.relative_to(ROOT)): sha(path) for path in paths})
    for name, expected_sha in bindings.items():
        if sha(ROOT / name) != expected_sha:
            raise ValueError("A reviewed original or engineering source changed: " + name)
    destination.mkdir()
    manifest_path, checks_path = destination / "tasks.json", destination / "checks.json"
    write(manifest_path, {"stage": "frozen", "revisions": tasks["revisions"], "selected": [task]})
    write(checks_path, checks)
    capture = copy.deepcopy(read(ROOT / parent["artifact_capture_policy"]))
    queue = "work/vmshare/performance-relu-submit-boundary-v20-20261125"
    if queue in capture["queues"]:
        raise ValueError("The parent already includes the new prospective queue")
    capture["queues"].append(queue)
    capture_path = destination / "capture-policy.json"
    write(capture_path, capture)
    bindings.update({str(path.relative_to(ROOT)): sha(path) for path in (manifest_path, checks_path, capture_path)})
    write(destination / "plan.json", {"stage": "frozen_after_actual_original_pin_public_deployment", "phase": "RUN",
        "task": TASK, "prospective_trials": ["query-boundary-main-r1", "query-boundary-repeat-r2"],
        "main_variable": "Task-local query-only access/submission enforcement and public self-contained export guidance;unchanged numerical algorithm,original public check,model and budgets",
        "runtime_root": str(RUNTIME.relative_to(ROOT)), "limits": parent["limits"], "model": "hy4flash-free",
        "pin": pins[TASK], "manifest": str(manifest_path.relative_to(ROOT)), "checks": str(checks_path.relative_to(ROOT)),
        "expected_protocol": expected, "driver": parent["driver_path"], "resource_driver": parent["resource_driver"],
        "image_copy_driver": parent["image_copy_driver"], "artifact_capture_policy": str(capture_path.relative_to(ROOT)),
        "queue": queue, "unchanged_task_inputs": unchanged,
        "source_cohorts": {arm: source["queue"] for arm, source in parents.items()}, "all_files_sha256": bindings,
        "new_model_calls_during_preparation": 0,
        "model_input_boundary": "Only original public task,unchanged mathematical helper,public export CLI and task-local access/submission guidance. No archived response,candidate,engineering output or original scorer is supplied to the model.",
        "failure": "Two fixed fresh sessions retain all outcomes;strict own zero-credit receipts;any new unknown or nonzero fee stops dispatch",
        "integration_required": "Do not overwrite the original raw-true/qualified-false main or its access violation. Other74 tasks keep their original task-local runtimes and independent five scoped revisions. This sixth repair needs both fresh original scores,full access/delivery review and an explicit source-verified join;no unrun record is promoted."})
    print(json.dumps({"status": "frozen_pair_not_admitted_or_started", "plan_sha256": sha(destination / "plan.json"),
        "bindings": len(bindings), "prospective_sessions": 2, "new_model_calls": 0}))


if __name__ == "__main__":
    main()
