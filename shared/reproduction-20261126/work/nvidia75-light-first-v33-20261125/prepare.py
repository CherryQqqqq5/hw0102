import copy
import hashlib
import importlib.util
from pathlib import Path
import sys


ROOT = Path.cwd().resolve()
FOLDER = Path(__file__).resolve().parent
PARENT = ROOT / "work/nvidia75-parallel-dispatch-v32-20261125"
RECOVERY = ROOT / "work/free-recovery32-20261125"
EXPECTED_PARENT = "f5971565bd5b18374b065f0b2aeb7659727310beef85a0e375b9fd18c9f7dae2"
spec = importlib.util.spec_from_file_location("prior_scheduling_preparation", PARENT / "prepare.py")
helpers = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helpers)
read, sha, write = helpers.read, helpers.sha, helpers.write
sys.path.insert(0, str(ROOT / "work/frozen-performance-free-v31"))
from course_eval.nvidia_free import audit_nvidia_events


def merge(binding, more):
    for name, expected in more.items():
        if name in binding and binding[name] != expected:
            raise ValueError("An inherited source cannot be rebound: " + name)
        binding[name] = expected


def closed_trace(directory, contract):
    import json

    traces = list(directory.rglob("model.jsonl"))
    if len(traces) > 1:
        raise ValueError("A closed logical position has multiple model traces")
    policies, bundle, ids, requests, hashes = [], [], [], [], {}
    for path in traces:
        digest = hashlib.sha256()
        for raw in path.open("rb"):
            digest.update(raw)
            event = json.loads(raw)
            if event["event"] == "free_service_policy_verified":
                policies.append(event)
            elif event["event"] in {"request", "response", "billing_verified", "request_error"}:
                bundle.append(event)
                if event["event"] == "request":
                    requests.append(event["request_id"])
                elif event["event"] == "billing_verified":
                    billing = audit_nvidia_events(policies + bundle, contract, "stepfun-ai/step-5-preview", 64000)
                    if billing["actual_requests"] != 1 or billing["unverified_requests"] or billing["reported_monetary_cost"] is not None:
                        raise ValueError("An actual complete policy proof differs from the retained prefix")
                    ids.append(event["generation_id"])
                    bundle = []
        hashes[str(path.relative_to(ROOT))] = digest.hexdigest()
    if len(ids) != len(set(ids)):
        raise ValueError("A closed position reuses a generation ID")
    return requests, ids, hashes


def main():
    if (FOLDER / "plan.json").exists():
        raise FileExistsError("Never overwrite a prepared continuation")
    parent_path, stop_path = PARENT / "plan.json", ROOT / "work/performance-stop-20261122.json"
    if sha(parent_path) != EXPECTED_PARENT:
        raise ValueError("The exact1100binding v32 parent changed")
    parent, stop = read(parent_path), read(stop_path)
    stop_sha = sha(stop_path)
    acceptance, config = read(RECOVERY / "accepted-unknown32.json"), read(RECOVERY / "hy4-resume.json")
    if (stop["accepted_total_unknown_calls"] != 32 or stop["historical_unknown_calls"] != 32
            or stop["pending_unverified_calls"] or stop["unresolved_fee_stops"]
            or acceptance["historical_unknown_ordinal"] != 32 or acceptance["actual_amount"] is not None
            or acceptance["actual_usage"] is not None or config["accepted_unknown_count"] != 32
            or sha(RECOVERY / "accepted-unknown32.json") != config["source_sha256"][config["accepted_evidence"]]):
        raise ValueError("Only the verified accepted32 state without new financial events is eligible")
    if stop["active"] and (not stop.get("quota_pause") or stop_sha != config["quota_stop_sha256"]):
        raise ValueError("An active financial STOP cannot use this continuation")
    review = read(PARENT / "execution-review.json")
    if review["status"] != "APPROVE" or review["blocking_findings"] or review["plan_sha256"] != EXPECTED_PARENT:
        raise ValueError("The reused dispatcher lacks its exact prior admission")
    binding = dict(parent["all_files_sha256"])
    merge(binding, acceptance["source_sha256"])
    for name, expected in binding.items():
        if sha(ROOT / name) != expected:
            raise ValueError("A frozen source or closed outcome changed: " + name)
    task_map = {t["id"]: t for t in read(ROOT / parent["manifest"])["selected"]}
    state_path = ROOT / parent["queue"] / "main/state.json"
    inherited, = [r for r in read(state_path)["rows"] if r["task"] == "pydata__xarray-4687"]
    directory = ROOT / inherited["run_dir"]
    result, protocol = read(directory / "result.json"), read(directory.with_suffix(".protocol.json"))
    if (result != inherited["original_result"] or result["scoreable"] is not True or result["passed"] is not False
            or protocol["plan_sha256"] != EXPECTED_PARENT or protocol["limits"] != parent["limits"]
            or protocol["model"] != parent["lanes"]["main"]["model"]):
        raise ValueError("The real v32 main semantic failure must be inherited without resampling")
    contract = ROOT / parent["lanes"]["main"]["contract"]
    requested, ids, trace_hashes = closed_trace(directory, contract)
    if requested != list(range(1, 26)) or len(ids) != 25 or ids != inherited["billing"]["generation_ids"]:
        raise ValueError("The actual main failure must retain exactly25 complete policy proofs")
    registry = read(ROOT / parent["generation_registry"])
    trace = next(directory.rglob("model.jsonl"))
    if any(registry["generations"].get(gid) != {"model": protocol["model"], "trace": str(trace), "request_id": rid} for gid, rid in zip(ids, requested)):
        raise ValueError("A completed failure proof differs from its actual registry claim")
    merge(binding, trace_hashes)
    interrupted = []
    old_queue = ROOT / parent["queue"]
    for lane, task, suffix, expected_requests in (("repeat", "pydata__xarray-4687", "C0-r2", 27), ("dsh", "pydata__xarray-4687", "B0-r1", 0), ("main", "pydata__xarray-6599", "C0-r1", 0)):
        run = old_queue / lane / (task + "-" + suffix)
        outcome = read(run / "result.json")
        requests, verified_ids, hashes = closed_trace(run, contract)
        if outcome["scoreable"] is not False or outcome["passed"] is not None or len(requests) != expected_requests:
            raise ValueError("Only the three real unscored attempts receive fresh environments")
        if lane == "repeat" and (len(verified_ids) != 26 or ids and set(ids).intersection(verified_ids)):
            raise ValueError("The interrupted repeat prefix changed or reused a main generation")
        merge(binding, hashes)
        paths = [run / "result.json", run / "trial.json", run.with_suffix(".protocol.json")]
        sources = {str(path.relative_to(ROOT)): sha(path) for path in paths if path.exists()}
        merge(binding, sources)
        interrupted.append({"lane": lane, "task": task, "run_dir": str(run.relative_to(ROOT)), "original_result": outcome,
            "actual_requests": len(requests), "complete_policy_proofs": len(verified_ids), "unknown_request_ids": sorted(set(requests) - set(range(1, len(verified_ids) + 1))),
            "missing_actual_identity": None, "missing_usage": None, "missing_amount": None, "source_sha256": sources | hashes})
    lanes = copy.deepcopy(parent["lanes"])
    lanes["main"]["tasks"].remove("pydata__xarray-4687")
    order = {task: i for i, task in enumerate(task_map)}

    def schedule(task):
        category = 2 if task == "video-processing" else int(task_map[task]["benchmark"] == "swe" or task in {"query-optimize", "tune-mjcf"})
        return category, order[task]

    for lane in lanes.values():
        lane["tasks"].sort(key=schedule)
    if [len(lanes[k]["tasks"]) for k in ("main", "dsh", "repeat")] != [72, 73, 73]:
        raise ValueError("Retain exactly218 untouched positions plus7 original grades")
    queue = "work/vmshare/performance-nvidia75-light-first-v33-20261125"
    policy = RECOVERY / "official-nvidia-policy.json"
    if not any("no per-token billing" in row["answer"] for row in read(policy)):
        raise ValueError("The current saved official free policy is unverified")
    write(FOLDER / "admission.json", {"accepted_quota_stop_sha256": config["quota_stop_sha256"], "historical_unknown_calls": 32,
        "allowed_models": [lanes["main"]["model"]], "nvidia_policy": str(policy.relative_to(ROOT)), "nvidia_policy_sha256": sha(policy),
        "unknown_acceptance_sha256": sha(RECOVERY / "accepted-unknown32.json"),
        "scope": "Accepted32 only; original exact quota snapshot remains bound even after verified Hy4 reset. New unresolved or nonzero evidence blocks every service."})
    capture = read(ROOT / parent["artifact_capture_policy"])
    capture["queues"] = [queue + "/" + lane for lane in lanes]
    write(FOLDER / "capture-policy.json", capture)
    write(FOLDER / "prior-generation-registry-snapshot.json", registry)
    paths = [state_path, directory / "result.json", directory / "trial.json", directory / "candidate.patch", directory.with_suffix(".protocol.json"),
        PARENT / "execution-review.json", parent_path, RECOVERY / "accepted-unknown32.json", RECOVERY / "qualification.json", RECOVERY / "prepared.json", RECOVERY / "hy4-resume.json", policy,
        *[FOLDER / name for name in ("prepare.py", "run_lane.py", "benchmarks_entry.py", "admission.json", "capture-policy.json", "prior-generation-registry-snapshot.json")]]
    merge(binding, {str(path.relative_to(ROOT)): sha(path) for path in paths})
    value = parent | {"queue": queue, "lanes": lanes, "historical_unknown_calls": 32, "all_files_sha256": binding,
        "admission": str((FOLDER / "admission.json").relative_to(ROOT)), "artifact_capture_policy": str((FOLDER / "capture-policy.json").relative_to(ROOT)),
        "additional_inherited_v32_main_xarray_position": inherited, "retained_unscored_v32_positions": interrupted,
        "primary_priority": parent["primary_priority"] | {"state": "work/free-recovery32-20261125/hy4-resume-state.json"},
        "execution_order": "Public task-type priority:non-SWE except query-optimize/tune-mjcf first;SWE/query/tune next;video last;original manifest order breaks ties identically in all lanes. Scores never enter the sort key.",
        "runtime_delta_scope": [], "inherited_original_position_count": 7, "remaining_original_position_count": 218,
        "initial_execution": "Continue218 fixed untouched positions in the unchanged original shared pool. Seven real original grades,including main ReLU and xarray false,are inherited without rerun. No model execution during preparation.",
        "scope": "Scheduling-only accepted32 continuation.3v27ELF,2v30miniReLU,1v31DSHReLU,1v32mainxarray and218 remaining. Runtime/model/prompts/tools/checks/graders/fees/budgets/resource limits unchanged; all prior null/false/cost evidence retained.",
        "new_model_calls_during_preparation": 0}
    if sha(stop_path) != stop_sha:
        raise RuntimeError("Financial state changed during preparation; do not freeze a stale admission")
    write(FOLDER / "plan.json", value)
    print({"prepared_without_generation": True, "plan_sha256": sha(FOLDER / "plan.json"), "bindings": len(binding), "remaining_positions": 218, "inherited_positions": 7, "runtime_changes": 0})


if __name__ == "__main__":
    main()
