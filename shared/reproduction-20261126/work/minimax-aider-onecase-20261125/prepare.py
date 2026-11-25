import argparse
import ast
from copy import deepcopy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path.cwd().resolve()
FOLDER = Path(__file__).resolve().parent
BASE = ROOT / "work/parallel-free-evaluation-20261124"
PARENT = ROOT / "work/nvidia75-light-first-v33-20261125/plan.json"
V34 = ROOT / "work/nvidia75-aider-dispatch-v34-20261125"
RUNTIME = ROOT / "work/frozen-performance-free-v31"
CHANNEL = ROOT / "work/minimax-free-qualification-20261125"
NATIVE = ROOT / "work/vmshare/minimax-native-64k-qualification-20261125"
RECOVERY = ROOT / "work/free-recovery33-20261125"
STOP = ROOT / "work/performance-stop-20261122.json"
MODEL = "minimaxai/minimax-m3.1-flash"
TASK = "cpp/all-your-base"
QUEUE = "work/vmshare/performance-minimax-aider-onecase-20261125"
EXPECTED_PARENT = "18cef63f6033106e9f1ea8c019a0d9ad2ac178127cdbcc4c0cafa29419686d9e"


def read(path):
    return json.loads(path.read_bytes())


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write(path, value):
    with path.open("x") as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def require(condition, detail):
    if not condition:
        raise ValueError(detail)


def load_owner():
    spec = importlib.util.spec_from_file_location("onecase_reviewed_dispatch_owner", FOLDER / "run_lane_owner.py")
    owner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(owner)
    return owner


def qualifications():
    sys.path.insert(0, str(RUNTIME))
    from course_eval.nvidia_free import admit_nvidia_channel, audit_nvidia_events

    records = []
    for contract, path, ceiling in ((CHANNEL / "free-contract.json", CHANNEL / "catalog-probe.json", 2048),
            (CHANNEL / "free-contract.json", ROOT / "work/vmshare/minimax-vision-function-qualification-20261125/channel-qualification.json", 1024),
            (CHANNEL / "evaluation-contract.json", NATIVE / "channel-qualification.json", 64000)):
        actual_contract, proof = admit_nvidia_channel(contract, path, ceiling)
        require(actual_contract["model"] == MODEL and proof["actual_reported_monetary_cost"] is None
            and proof["monetary_receipt_available"] is False, "Every actual qualification must retain its own identity/usage and null amount")
        records.append({"path": str(path.relative_to(ROOT)), "sha256": sha(path), "generation_id": proof["generation_id"],
            "model": MODEL, "request_max_tokens": proof["request"]["max_tokens"], "usage": proof["assembled_response"]["usage"], "actual_amount": None})
    require(len({row["generation_id"] for row in records}) == 3, "The three real qualification identities must be independent")
    native = read(NATIVE / "result.json")
    require(native["verified"] is True and native["requested_64000_parameter_accepted"] is True
        and native["actual_request_limit"] == 1 and native["tool_executions"] == native["new_original_grader_calls"] == 0
        and records[-1]["request_max_tokens"] == 64000 and native["generation_id"] == records[-1]["generation_id"], "The real64000 native-function qualification is mandatory")
    events = [json.loads(line) for line in (NATIVE / "model.jsonl").open()]
    billing = audit_nvidia_events(events, CHANNEL / "native64-bootstrap-contract.json", MODEL, 64000)
    require(billing["actual_requests"] == billing["verified_nonbilled_service_calls"] == 1 and not billing["unverified_requests"]
        and billing["reported_monetary_cost"] is None, "The actual native qualification lacks a complete policy proof")
    return records


def prepare():
    require(not (FOLDER / "plan.json").exists(), "Never overwrite a prospective plan")
    require(sha(PARENT) == EXPECTED_PARENT, "The reviewed original1134 source plan changed")
    parent, source = read(PARENT), {}
    original = parent["all_files_sha256"]
    qualification = read(V34 / "qualification.json")
    require(qualification["status"] == "PASS_ZERO_MODEL_DISPATCH_REPAIR_CANDIDATE_NOT_ACTIVATED", "Reuse only the actual zero-model Aider/provider-lock qualification")
    for name, expected in qualification["source_sha256"].items():
        require(sha(ROOT / name) == expected, "A qualified v34 dependency changed: " + name)
    def bind(path):
        name = str(path.relative_to(ROOT))
        actual = sha(path)
        require(name not in original or actual == original[name], "A reused v33 source changed: " + name)
        require(name not in source or source[name] == actual, "Conflicting immutable source: " + name)
        source[name] = actual
    records = qualifications()
    stop = read(STOP)
    require(stop["active"] is False and stop["historical_unknown_calls"] == stop["accepted_total_unknown_calls"] == 33
        and stop["pending_unverified_calls"] == 0 and not stop["unresolved_fee_stops"] and stop.get("quota_pause") is None
        and stop["accepted_unknown_evidence"] == str((RECOVERY / "accepted-unknown33.json").relative_to(ROOT)), "Current accepted33 must be released without any new unresolved event")
    actual_stop = sha(STOP)
    config, review = read(RECOVERY / "hy4-resume.json"), read(RECOVERY / "hy4-resume-review.json")
    require(review["status"] == "APPROVE" and not review["blocking_findings"] and review["config_sha256"] == sha(RECOVERY / "hy4-resume.json"), "The actual current Hy4 continuation requires exact source admission")
    priority = {"drain_new_tasks_at": "2026-11-28T00:00:00+08:00", "state": str((RECOVERY / "hy4-resume-state.json").relative_to(ROOT)),
        "config": str((RECOVERY / "hy4-resume.json").relative_to(ROOT)), "config_sha256": sha(RECOVERY / "hy4-resume.json"),
        "review": str((RECOVERY / "hy4-resume-review.json").relative_to(ROOT)), "review_sha256": sha(RECOVERY / "hy4-resume-review.json"),
        "producer": str((RECOVERY / "resume_hy4.py").relative_to(ROOT)), "producer_sha256": sha(RECOVERY / "resume_hy4.py"),
        "ready_field": "status", "ready_value": "actual_core_ablation_and_preservation_ended_require_final_review_and_delivery"}
    load_owner().verified_primary_state(ROOT, priority)
    for name in original:
        if name.startswith("work/frozen-performance-free-v31/"):
            bind(ROOT / name)
    paths = [PARENT, V34 / "run_lane.py", V34 / "external_runtimes.py", V34 / "qualification.json",
        RECOVERY / "accepted-unknown33.json", RECOVERY / "hy4-resume.json", RECOVERY / "hy4-resume-review.json", RECOVERY / "resume_hy4.py",
        ROOT / parent["manifest"], ROOT / parent["checks"], ROOT / parent["generation_seed"],
        BASE / "resource_warm_trial.py", BASE / "resource_trial.py", ROOT / "course_eval/resource_pool.py",
        BASE / "ready_coordinator.py", BASE / "image_copy_http1.py", ROOT / "scripts/run_performance_queue.py",
        ROOT / "scripts/run_performance_matrix.py", ROOT / "scripts/run_pinned_image_copy.py", ROOT / "scripts/import_pinned_image_copy.py",
        ROOT / "scripts/prepare_registry_export_tool.py", ROOT / "scripts/summarize_performance_comparison.py", ROOT / "scripts/harbor_artifact_capture.py",
        ROOT / "work/.venv/bin/harbor", CHANNEL / "free-contract.json", CHANNEL / "native64-bootstrap-contract.json", CHANNEL / "evaluation-contract.json",
        CHANNEL / "qualify_native_64k.py", CHANNEL / "catalog-official-policy.json", NATIVE / "result.json", NATIVE / "model.jsonl",
        ROOT / "work/vmshare/minimax-vision-function-qualification-20261125/result.json", ROOT / "work/vmshare/minimax-vision-function-qualification-20261125/model.jsonl"]
    paths += [ROOT / row["path"] for row in records]
    paths += [FOLDER / name for name in ("prepare.py", "run_lane.py", "run_lane_owner.py", "benchmarks_entry.py")]
    for path in paths:
        bind(path)
    task = next(t for t in read(ROOT / parent["manifest"])["selected"] if t["id"] == TASK)
    require(task["benchmark"] == "aider" and task["stratum"] == "cpp" and task["image_id"] == parent["pins"][TASK], "The original task/pin changed")
    task_root = ROOT / "work/datasets/polyglot-benchmark-7e0611e77b54e2dea774cdc0aa00cf9f7ed6144f/cpp/exercises/practice/all-your-base"
    for path in task_root.rglob("*"):
        if path.is_file():
            require(not path.is_symlink(), "The original task source must not contain a substituted symlink")
            bind(path)
    admission = {"allowed_models": [MODEL], "historical_unknown_calls": 33, "accepted_quota_stop_sha256": None,
        "accepted_evidence": str((RECOVERY / "accepted-unknown33.json").relative_to(ROOT)), "accepted_evidence_sha256": sha(RECOVERY / "accepted-unknown33.json"),
        "paid_fallbacks": False, "new_unknown_or_nonzero_fee_stops": True, "missing_monetary_amount_is_null": True,
        "scope": "Exactly one separate MiniMax original Aider task,with the fixed existing common limits; not Step5 or Hy4 score replacement or75-task completion"}
    capture = deepcopy(read(ROOT / parent["artifact_capture_policy"]))
    capture.update(queues=[QUEUE + "/main"], purpose="One independent MiniMax Aider comparison; unchanged collector,original solution/test/grade path and capture whitelist")
    write(FOLDER / "admission.json", admission)
    write(FOLDER / "capture-policy.json", capture)
    registry_path = ROOT / parent["generation_registry"]
    write(FOLDER / "prior-generation-registry-snapshot.json", read(registry_path))
    for path in (FOLDER / "admission.json", FOLDER / "capture-policy.json", FOLDER / "prior-generation-registry-snapshot.json"):
        bind(path)
    value = {"experiment": "single_original_aider_case_new_minimax_model", "scope": "Prospective one-case comparison,not a replacement or complete75/225 matrix",
        "queue": QUEUE, "manifest": parent["manifest"], "checks": parent["checks"], "runtime_root": parent["runtime_root"],
        "limits": parent["limits"], "historical_unknown_calls": 33, "admission": str((FOLDER / "admission.json").relative_to(ROOT)),
        "lanes": {"main": {"backend": "nvidia-free", "model": MODEL, "framework": "mini-swe", "configuration": "C0", "repetition": 1,
            "tasks": [TASK], "contract": str((CHANNEL / "evaluation-contract.json").relative_to(ROOT)), "qualification": str((NATIVE / "channel-qualification.json").relative_to(ROOT))}},
        "pins": {TASK: parent["pins"][TASK]}, "first_control_qualification_task": TASK, "primary_priority": priority,
        "provider_task_lease": {"lock": "work/parallel-free-evaluation-20261124/resources/nvidia-provider-task.lock", "capacity": 1},
        "resource_driver": parent["resource_driver"], "image_copy_driver": parent["image_copy_driver"],
        "artifact_capture_policy": str((FOLDER / "capture-policy.json").relative_to(ROOT)), "generation_seed": parent["generation_seed"],
        "generation_registry": parent["generation_registry"], "historical_generation_ids": [row["generation_id"] for row in records],
        "actual_channel_qualifications": records, "all_files_sha256": source, "parent_plan_sha256": EXPECTED_PARENT,
        "observed_stop_sha256_at_preparation": actual_stop, "old_scores_reused": 0, "new_model_calls_during_preparation": 0,
        "complete75_or225": False, "public_checkpoint_equivalence_verified": False,
        "source_versions": "Unmodified v31 runtime and original Aider task. v34 dispatcher plus historical-ID environment merge and truthful no-quota protocol flag only."}
    require(not (ROOT / QUEUE).exists() and sha(STOP) == actual_stop, "A queue or new financial event appeared during preparation")
    write(FOLDER / "plan.json", value)
    print(json.dumps({"status": "prepared_not_admitted_no_calls", "plan_sha256": sha(FOLDER / "plan.json"), "source_count": len(source), "tasks": 1, "model": MODEL}))


def validate():
    plan = read(FOLDER / "plan.json")
    require(list(plan["lanes"]) == ["main"] and plan["lanes"]["main"]["tasks"] == [TASK]
        and plan["lanes"]["main"]["model"] == MODEL and plan["old_scores_reused"] == 0 and plan["complete75_or225"] is False,
        "The prospective one-case scope changed")
    for name, expected in plan["all_files_sha256"].items():
        require(sha(ROOT / name) == expected, "A frozen source changed: " + name)
    require(qualifications() == plan["actual_channel_qualifications"], "Actual qualification identities or usage changed")
    os.environ.update(COURSE_PARALLEL_FREE_ADMISSION=str(ROOT / plan["admission"]), COURSE_PARALLEL_FREE_ADMISSION_SHA256=sha(ROOT / plan["admission"]))
    from course_eval.financial_stop import free_query_blocked

    require(not free_query_blocked(STOP, MODEL), "A current financial event blocks any prospective generation")
    owner = load_owner()
    primary = owner.verified_primary_state(ROOT, plan["primary_priority"])
    registry = read(ROOT / plan["generation_registry"])
    prior = read(FOLDER / "prior-generation-registry-snapshot.json")
    require(all(registry["generations"].get(key) == value for key, value in prior["generations"].items()), "A prior actual generation claim changed")
    tree = ast.parse((FOLDER / "run_lane_owner.py").read_text())
    assignment, = [node for node in ast.walk(tree) if isinstance(node, ast.Assign) and any(isinstance(t, ast.Subscript)
        and isinstance(t.slice, ast.Constant) and t.slice.value == "COURSE_PRIOR_FREE_GENERATION_IDS" for t in node.targets)]
    namespace = {"json": json, "plan": plan, "records": [{"billing": {"generation_ids": ["explicit-local-environment-fixture"]}}], "environment": {}}
    exec(compile(ast.Module(body=[assignment], type_ignores=[]), "actual_prior_identity_environment", "exec"), namespace)
    require(set(json.loads(namespace["environment"]["COURSE_PRIOR_FREE_GENERATION_IDS"])) == set(plan["historical_generation_ids"]) | {"explicit-local-environment-fixture"}, "The actual environment assignment omitted a qualification or prior position")
    command = [sys.executable, "-B", str(FOLDER / "run_lane.py"), "main", "--single-task", TASK, "--image-preflight", str(PARENT)]
    cached = json.loads(subprocess.check_output(command, cwd=ROOT, text=True))
    require(cached["status"] == "actual_cached_original_pin_verified" and cached["pin"] == plan["pins"][TASK], "The actual CLI must consume the cached original Aider pin")
    modules = json.loads(subprocess.check_output([sys.executable, "-B", str(FOLDER / "benchmarks_entry.py"), "--import-proof"], cwd=ROOT, text=True))
    for row in modules["actual_module_resolution"].values():
        require(plan["all_files_sha256"][str(Path(row["path"]).relative_to(ROOT))] == row["sha256"], "The actual benchmark entry imports an unbound module")
    result = {"status": "validated_zero_model_not_admitted", "plan_sha256": sha(FOLDER / "plan.json"), "source_count": len(plan["all_files_sha256"]),
        "actual_cached_image_cli": cached, "actual_module_import_proof": modules, "prior_identity_environment_preserves_all_three_qualifications": True,
        "primary_state_attestation": primary, "qualifications": plan["actual_channel_qualifications"], "new_model_calls": 0, "new_original_grader_calls": 0,
        "containers_started": 0, "stop_modified": False, "execution_review_exists": (FOLDER / "execution-review.json").exists(),
        "scope": "Source/real saved receipt/actual CLI image-metadata/import validation only. Reuses v34 private OS lock proof; not a benchmark result or end-to-end one-case run."}
    write(FOLDER / "validation.json", result)
    print(json.dumps({"status": result["status"], "plan_sha256": result["plan_sha256"], "source_count": result["source_count"], "tasks": 1, "new_model_calls": 0}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("prepare", "validate"))
    args = parser.parse_args()
    prepare() if args.action == "prepare" else validate()
