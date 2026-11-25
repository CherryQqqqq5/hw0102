import copy
import importlib.util
from pathlib import Path


ROOT = Path.cwd().resolve()
FOLDER = Path(__file__).resolve().parent
PARENT = ROOT / "work/nvidia75-idle-alignment-v31-20261125"
RECOVERY = ROOT / "work/free-recovery31-20261125"
spec = importlib.util.spec_from_file_location("prior_verified_preparation", PARENT / "prepare.py")
helpers = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helpers)
read, sha, write = helpers.read, helpers.sha, helpers.write


def main():
    if (FOLDER / "plan.json").exists():
        raise FileExistsError("Never overwrite a prepared continuation")
    parent_path = PARENT / "plan.json"
    parent = read(parent_path)
    if sha(parent_path) != "0995b63b9b2d06cef8a4348872a7757941c13c8fc1419a2da5b5c133e0dd4da3":
        raise ValueError("The exact v31 parent changed")
    acceptance_path = RECOVERY / "accepted-unknown31.json"
    accepted = read(acceptance_path)
    stop_path = ROOT / "work/performance-stop-20261122.json"
    stop = read(stop_path)
    if (stop["accepted_total_unknown_calls"] != 31 or stop["pending_unverified_calls"]
            or stop["unresolved_fee_stops"] or stop["active"] is not True or not stop.get("quota_pause")
            or accepted["historical_unknown_ordinal"] != 31 or accepted["actual_amount"] is not None
            or accepted["actual_usage"] is not None):
        raise ValueError("Only the exact accepted31 quota-only pause is eligible")
    review_path = PARENT / "expansion-review.json"
    review = read(review_path)
    if (review["status"] != "APPROVE" or review["blocking_findings"]
            or review["plan_sha256"] != sha(parent_path)):
        raise ValueError("The actual scored DSH continuation lacks its independent review")
    binding = dict(parent["all_files_sha256"])
    for extra in (accepted["source_sha256"], review["source_sha256"]):
        for name, expected in extra.items():
            if name in binding and binding[name] != expected:
                raise ValueError("An inherited source cannot be rebound: " + name)
            binding[name] = expected
    for name, expected in binding.items():
        if sha(ROOT / name) != expected:
            raise ValueError("A frozen source or actual closed outcome changed: " + name)
    state_path = ROOT / parent["queue"] / "dsh/state.json"
    state = read(state_path)
    inherited, = state["rows"]
    actual = review["actual_run"]
    if (inherited["task"] != "model-extraction-relu-logits"
            or inherited["run_dir"] != actual["run_dir"]
            or inherited["original_result"] != actual["original_result"]
            or inherited["original_result"]["scoreable"] is not True
            or inherited["original_result"]["passed"] is not True
            or inherited["billing"]["actual_requests"] != 16
            or inherited["billing"]["verified_nonbilled_service_calls"] != 16):
        raise ValueError("Keep the exact sixteen-proof original DSH success without rerunning")
    lanes = copy.deepcopy(parent["lanes"])
    lanes["dsh"]["tasks"] = [task for task in lanes["dsh"]["tasks"] if task != inherited["task"]]
    if any(len(lane["tasks"]) != 73 for lane in lanes.values()):
        raise ValueError("The continuation must contain exactly219 untouched positions")
    policy = FOLDER / "official-nvidia-policy.json"
    if sha(policy) != sha(PARENT / "official-nvidia-policy.json"):
        raise ValueError("The reused official free policy changed")
    write(FOLDER / "admission.json", {"accepted_quota_stop_sha256": sha(stop_path),
        "historical_unknown_calls": 31, "allowed_models": [lanes["dsh"]["model"]],
        "nvidia_policy": str(policy.relative_to(ROOT)), "nvidia_policy_sha256": sha(policy),
        "unknown_acceptance_sha256": sha(acceptance_path),
        "scope": "Only the exact accepted31 quota pause and fixed official free model; every new fee gap or nonzero blocks all channels."})
    queue = "work/vmshare/performance-nvidia75-parallel-dispatch-v32-20261125"
    capture = read(ROOT / parent["artifact_capture_policy"])
    capture["queues"] = [queue + "/" + lane for lane in lanes]
    write(FOLDER / "capture-policy.json", capture)
    write(FOLDER / "prior-generation-registry-snapshot.json", read(ROOT / parent["generation_registry"]))
    for path in [*FOLDER.iterdir(), parent_path, review_path, acceptance_path,
            RECOVERY / "hy4-resume.json", state_path]:
        if path.is_file():
            binding[str(path.relative_to(ROOT))] = sha(path)
    priority = parent["primary_priority"] | {
        "drain_new_tasks_at": "2026-11-28T00:00:00+08:00",
        "state": "work/free-recovery31-20261125/hy4-resume-state.json",
        "scope": "Through the review deadline,share the original ResourceLease pool with Hy4:two light tasks or one exclusive task total. No extra CPU/memory capacity,model budget or fee relaxation. Do not hold the whole auxiliary cohort until Hy4 finishes."}
    value = parent | {"queue": queue, "lanes": lanes, "historical_unknown_calls": 31,
        "all_files_sha256": binding, "primary_priority": priority,
        "admission": str((FOLDER / "admission.json").relative_to(ROOT)),
        "artifact_capture_policy": str((FOLDER / "capture-policy.json").relative_to(ROOT)),
        "additional_inherited_v31_dsh_relu_position": inherited,
        "runtime_delta_scope": [],
        "initial_execution": "The six actual v27/v30/v31 original scores are inherited. Dispatch only the remaining219fixed positions with the exact unchanged v31model runtime,using the existing shared resource pool concurrently with Hy4.",
        "scope": "Scheduling-only continuation:3v27ELF,2v30ReLU,1v31DSHReLU and219untouched positions. Model/runtime/prompts/checks/graders/tools/limits remain v31; old semantic false and every fee gap remain visible.",
        "new_model_calls_during_preparation": 0}
    write(FOLDER / "plan.json", value)
    print({"prepared_without_generation": True, "plan_sha256": sha(FOLDER / "plan.json"),
        "bindings": len(binding), "remaining_positions": 219, "runtime_changes": 0})


if __name__ == "__main__":
    main()
