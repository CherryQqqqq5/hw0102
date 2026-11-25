import copy
import importlib.util
from pathlib import Path


ROOT = Path.cwd().resolve()
FOLDER = Path(__file__).resolve().parent
PARENT = ROOT / "work/nvidia75-small-actions-v30-20261125"
RECOVERY = ROOT / "work/free-recovery30-20261125"
spec = importlib.util.spec_from_file_location("prior_frozen_plan_helpers", PARENT / "prepare.py")
helpers = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helpers)
read, sha, write = helpers.read, helpers.sha, helpers.write


def main():
    if (FOLDER / "plan.json").exists():
        raise FileExistsError("Never rebind an admitted or prepared experiment")
    parent = read(PARENT / "plan.json")
    if sha(PARENT / "plan.json") != "c0fe4961f310f979bec7da1101e75f0b86db240cb5b40364ccd76f4e2b528f18":
        raise ValueError("The exact original75 parent changed")
    accepted = read(RECOVERY / "accepted-unknown30.json")
    stop_path = ROOT / "work/performance-stop-20261122.json"
    stop = read(stop_path)
    if (stop["accepted_total_unknown_calls"] != 30 or stop["pending_unverified_calls"]
            or stop["unresolved_fee_stops"] or stop["active"] is not True or not stop["quota_pause"]
            or accepted["historical_unknown_ordinal"] != 30 or accepted["actual_amount"] is not None
            or accepted["actual_usage"] is not None):
        raise ValueError("Only the actual accepted30 quota-only pause is eligible")
    qualification_path = ROOT / "work/dsh-idle-alignment-20261125/qualification.json"
    qualification = read(qualification_path)
    repair_review = read(FOLDER / "repair-review.json")
    if (qualification["status"] != "PASS" or qualification["new_model_calls"]
            or qualification["new_original_grader_calls"] or repair_review["status"] != "APPROVE"
            or repair_review["blocking_findings"] or repair_review["qualification_sha256"] != sha(qualification_path)):
        raise ValueError("The actual native SDK repair needs its exact zero-model qualification and review")
    binding = parent["all_files_sha256"] | accepted["source_sha256"] | qualification["source_sha256"]
    for name, expected in binding.items():
        if sha(ROOT / name) != expected:
            raise ValueError("An unchanged source or closed actual outcome changed: " + name)
    lanes = copy.deepcopy(parent["lanes"])
    inherited = {}
    for lane in ("main", "repeat", "dsh"):
        row, = [row for row in accepted["retained_original_nvidia_positions"] if row["lane"] == lane]
        result = row["original_result"]
        if lane == "dsh":
            if result["scoreable"] is not False or result["passed"] is not None:
                raise ValueError("Only the unscored native bridge interruption may receive a fresh environment")
            interrupted = row
        else:
            if result["scoreable"] is not True or result["passed"] is not (lane == "repeat"):
                raise ValueError("The true main false and repeat true must be inherited without resampling")
            state = read(ROOT / parent["queue"] / lane / "state.json")
            actual, = [item for item in state["rows"] if item["task"] == "model-extraction-relu-logits"]
            if actual["original_result"] != result or actual["billing"]["actual_requests"] != (14 if lane == "main" else 32):
                raise ValueError("A completed original row differs from its exact retained source")
            inherited[lane] = actual
            lanes[lane]["tasks"] = [task for task in lanes[lane]["tasks"] if task != "model-extraction-relu-logits"]
    if sum(len(lane["tasks"]) for lane in lanes.values()) != 220:
        raise ValueError("Retain exactly225 original positions:3 ELF,2 ReLU and220 remaining")
    policy = FOLDER / "official-nvidia-policy.json"
    if not any("no per-token billing" in row["answer"] for row in read(policy)):
        raise ValueError("The current official nonbilling policy is unverified")
    write(FOLDER / "admission.json", {"accepted_quota_stop_sha256": sha(stop_path),
        "historical_unknown_calls": 30, "allowed_models": [lanes["dsh"]["model"]],
        "nvidia_policy": str(policy.relative_to(ROOT)), "nvidia_policy_sha256": sha(policy),
        "unknown_acceptance_sha256": sha(RECOVERY / "accepted-unknown30.json"),
        "scope": "Only this exact accepted30 quota-only STOP and the fixed official free model; every new fee gap or nonzero stops dispatch"})
    queue = "work/vmshare/performance-nvidia75-idle-alignment-v31-20261125"
    capture = read(ROOT / parent["artifact_capture_policy"])
    capture["queues"] = [queue + "/" + lane for lane in lanes]
    write(FOLDER / "capture-policy.json", capture)
    write(FOLDER / "prior-generation-registry-snapshot.json", read(ROOT / parent["generation_registry"]))
    runtime = ROOT / "work/frozen-performance-free-v31"
    for path in [*runtime.rglob("*"), *FOLDER.iterdir(), qualification_path, RECOVERY / "accepted-unknown30.json",
            RECOVERY / "hy4-resume.json", PARENT / "plan.json", PARENT / "first-three-completed-review.json"]:
        if path.is_file() and "__pycache__" not in path.parts:
            binding[str(path.relative_to(ROOT))] = sha(path)
    value = parent | {"runtime_root": str(runtime.relative_to(ROOT)), "queue": queue, "lanes": lanes,
        "historical_unknown_calls": 30, "all_files_sha256": binding,
        "admission": str((FOLDER / "admission.json").relative_to(ROOT)),
        "artifact_capture_policy": str((FOLDER / "capture-policy.json").relative_to(ROOT)),
        "primary_priority": parent["primary_priority"] | {"state": "work/free-recovery30-20261125/hy4-resume-state.json"},
        "additional_inherited_v30_relu_positions": inherited,
        "retained_unscored_v30_dsh_interruption": interrupted,
        "runtime_delta_scope": ["course_eval/dsh_runner.py"],
        "initial_execution": "First launch only dsh --single-task model-extraction-relu-logits. Parent reviews its actual grade and complete fee proofs before expanding220 fixed remaining positions. Main false and repeat true are never resampled.",
        "scope": "Exactly75 tasks per arm. Three ELF retain v27,two completed ReLU retain v30,220 remaining positions use v31 with unchanged prompts/model/tools/fees/budgets and only a loopback idle bound aligned with the original whole-task deadline. No pure single-version or causal performance claim.",
        "new_model_calls_during_preparation": 0}
    write(FOLDER / "plan.json", value)
    print({"prepared_without_generation": True, "plan_sha256": sha(FOLDER / "plan.json"), "bindings": len(binding)})


if __name__ == "__main__":
    main()
