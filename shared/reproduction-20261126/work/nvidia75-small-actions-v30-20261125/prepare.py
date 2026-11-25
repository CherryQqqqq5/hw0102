import copy
import hashlib
import json
from pathlib import Path


ROOT = Path.cwd().resolve()
FOLDER = Path(__file__).resolve().parent
PARENT = ROOT / "work/nvidia75-resume-v29-20261125"
RECOVERY = ROOT / "work/free-recovery29-20261125"


def read(path):
    return json.loads(path.read_bytes())


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def main():
    if (FOLDER / "plan.json").exists():
        raise FileExistsError("Never rebind a prospective guidance intervention")
    parent = read(PARENT / "plan.json")
    stop_path = ROOT / "work/performance-stop-20261122.json"
    stop = read(stop_path)
    acceptance = RECOVERY / "accepted-unknown29.json"
    accepted = read(acceptance)
    if (stop["accepted_total_unknown_calls"] != 29 or stop["historical_unknown_calls"] != 29
            or stop["pending_unverified_calls"] or stop["unresolved_fee_stops"]
            or stop["active"] is not True or not stop["quota_pause"]
            or accepted["historical_unknown_ordinal"] != 29
            or accepted["actual_amount"] is not None or accepted["actual_usage"] is not None):
        raise ValueError("Only the already accepted29 quota-only pause is eligible")
    qualification = read(FOLDER / "qualification.json")
    if qualification["status"] != "PASS" or qualification["new_model_calls"] or qualification["new_grader_calls"]:
        raise ValueError("The exact common input transform needs its zero-model qualification")
    binding = parent["all_files_sha256"] | qualification["source_sha256"] | accepted["source_sha256"]
    for name, expected in binding.items():
        if sha(ROOT / name) != expected:
            raise ValueError("A prior frozen or closed-evidence source changed: " + name)
    review = read(PARENT / "execution-review.json")
    if review["status"] != "APPROVE" or review["blocking_findings"] or review["plan_sha256"] != sha(PARENT / "plan.json"):
        raise ValueError("The reused dispatcher/input inventory lacks exact prior admission")
    positions = accepted["interrupted_positions"]
    if {row["lane"] for row in positions} != set(parent["lanes"]) or any(
            row["original_result"]["scoreable"] is not False or row["original_result"]["passed"] is not None for row in positions):
        raise ValueError("Only actual unscored ReLU interruptions receive a new environment")
    lanes = copy.deepcopy(parent["lanes"])
    for lane in lanes.values():
        if len(lane["tasks"]) != 74 or len(set(lane["tasks"])) != 74 or lane["tasks"][0] != "model-extraction-relu-logits":
            raise ValueError("The original fixed remaining task order changed")
    official = ROOT / accepted["official_free_policy"]
    if sha(official) != accepted["official_free_policy_sha256"]:
        raise ValueError("The current official free-policy source changed")
    write(FOLDER / "admission.json", {"accepted_quota_stop_sha256": sha(stop_path),
        "historical_unknown_calls": 29, "allowed_models": [lanes["main"]["model"]],
        "nvidia_policy": str(official.relative_to(ROOT)), "nvidia_policy_sha256": sha(official),
        "unknown_acceptance_sha256": sha(acceptance),
        "scope": "Only the fixed official nonbilled NVIDIA route during the exact accepted29 quota pause; new unknown or nonzero evidence blocks all new requests."})
    queue = "work/vmshare/performance-nvidia75-small-actions-v30-20261125"
    capture = read(ROOT / parent["artifact_capture_policy"])
    capture["queues"] = [queue + "/" + name for name in lanes]
    write(FOLDER / "capture-policy.json", capture)
    write(FOLDER / "prior-generation-registry-snapshot.json", read(ROOT / parent["generation_registry"]))
    runtime = ROOT / "work/frozen-performance-free-v30"
    paths = [PARENT / "plan.json", PARENT / "execution-review.json", acceptance, official,
        RECOVERY / "hy4-resume.json", *[FOLDER / name for name in (
            "qualify.py", "qualification.json", "prepare.py", "run_lane.py", "benchmarks_entry.py",
            "admission.json", "capture-policy.json", "prior-generation-registry-snapshot.json")], *runtime.rglob("*")]
    for path in paths:
        if path.is_file() and "__pycache__" not in path.parts and path.name not in {"plan.json", "execution-review.json"}:
            binding[str(path.relative_to(ROOT))] = sha(path)
    binding[str((PARENT / "plan.json").relative_to(ROOT))] = sha(PARENT / "plan.json")
    binding[str((PARENT / "execution-review.json").relative_to(ROOT))] = sha(PARENT / "execution-review.json")
    plan = parent | {"runtime_root": str(runtime.relative_to(ROOT)), "queue": queue,
        "lanes": lanes, "historical_unknown_calls": 29, "all_files_sha256": binding,
        "admission": str((FOLDER / "admission.json").relative_to(ROOT)),
        "artifact_capture_policy": str((FOLDER / "capture-policy.json").relative_to(ROOT)),
        "primary_priority": parent["primary_priority"] | {"state": "work/free-recovery29-20261125/hy4-resume-state.json"},
        "mechanical_readmission": {row["lane"]: row["run_dir"] for row in positions},
        "retained_unscored_v29_relu_positions": positions,
        "initial_bounded_validation_task": "model-extraction-relu-logits",
        "initial_execution": "First launch only --single-task model-extraction-relu-logits in the three arms. Parent checks completed original scoring, actual proof completeness and command/access traces before expanding the fixed remaining queue. Real semantic false is retained; it is not resampled.",
        "runtime_delta_scope": ["course_eval/nvidia_free.py"],
        "scope": "Three actual original ELF positions retain v27. The other74 fixed tasks in every arm use v30 common short-command/reuse/access-priority guidance over unchanged v28 transport and tool/fee/validation rules. This is task-stratified evidence,not a single never-changing protocol or a pure isolated causal claim for one sentence. No Hy4 or pilot scores are pooled.",
        "protocol": "Same model,sampling,tools/local schemas,500 physical requests,3600s wall,120s command,64000 output,no retries,official free-policy proof and original graders. Only a copied common system guidance block changes model input in both mini-swe and native DSH.4096 is a soft action-length target,not a relaxed fee or validation rule.",
        "new_model_calls_during_preparation": 0}
    write(FOLDER / "plan.json", plan)
    print(json.dumps({"status": "prepared_without_generation", "plan_sha256": sha(FOLDER / "plan.json"),
        "bindings": len(binding), "initial_fixed_tasks": 3, "remaining_matrix_positions": 222}))


if __name__ == "__main__":
    main()
