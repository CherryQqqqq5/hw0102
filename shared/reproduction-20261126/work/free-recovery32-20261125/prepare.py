import argparse
from copy import deepcopy
from datetime import datetime, timezone
import fcntl
import hashlib
import importlib.util
import json
from pathlib import Path
import shlex
import subprocess
import sys

import requests


ROOT = Path.cwd().resolve()
FOLDER = Path(__file__).resolve().parent
BASE = ROOT / "work/parallel-free-evaluation-20261124"
STOP = ROOT / "work/performance-stop-20261122.json"
PLAN = ROOT / "work/nvidia75-parallel-dispatch-v32-20261125/plan.json"
RUN = ROOT / "work/vmshare/performance-nvidia75-parallel-dispatch-v32-20261125/repeat/pydata__xarray-4687-C0-r2"
TRACE = RUN / "model.jsonl"
PREVIOUS = ROOT / "work/free-recovery31-20261125/accepted-unknown31.json"
OLD_CONFIG = PREVIOUS.with_name("hy4-resume.json")
EXPECTED_STOP_SHA = "a6b365ab9634bbad5fd74c8b4d17e140a075ab035a99e49042ec5ec0f7e2f1c7"
EXPECTED_PLAN_SHA = "f5971565bd5b18374b065f0b2aeb7659727310beef85a0e375b9fd18c9f7dae2"
POLICY_URL = "https://build.nvidia.com/api/runtime/content/help-center-faq.yaml"
MODEL = "stepfun-ai/step-5-preview"
RESET = "2026-11-25T19:54:04+08:00"
spec = importlib.util.spec_from_file_location("existing_generic_hy4_waiter", BASE / "resume_verified_hy4.py")
waiter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(waiter)
read, sha = waiter.read, waiter.sha
sys.path.insert(0, str(ROOT / "work/frozen-performance-free-v31"))
from course_eval.nvidia_free import audit_nvidia_events


def require(condition, message):
    if not condition:
        raise ValueError(message)


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode()


def create(name, data):
    with (FOLDER / name).open("xb") as stream:
        stream.write(data)


def no_dispatchers():
    paths = [PLAN.parent / name for name in ("run_lane.py", "benchmarks_entry.py")]
    paths += [BASE / name for name in ("resume_verified_hy4.py", "run_ready_queues.py", "ready_coordinator.py", "run_fixed_free_trials.py", "run_reuse_ablation.py")]
    paths.append(ROOT / "work/frozen-performance-free-v31/course_eval/nvidia_free.py")
    targets = {str(p) for p in paths} | {str(p.relative_to(ROOT)) for p in paths}
    for line in subprocess.check_output(["ps", "-axo", "pid,command"], text=True).splitlines()[1:]:
        fields = line.strip().split(maxsplit=1)
        if len(fields) == 2 and targets.intersection(shlex.split(fields[1])[1:]):
            raise RuntimeError("A dispatcher,model worker or Hy4 waiter remains alive: " + fields[0])


def validate_stop(stop):
    require(stop["active"] is True and stop["historical_unknown_calls"] == stop["accepted_total_unknown_calls"] == 31
        and stop["pending_unverified_calls"] == 1 and stop["unverified_requests"] == [27]
        and stop["quota_pause"]["resume_not_before"] == RESET
        and (ROOT / stop["accepted_unknown_evidence"]).resolve() == PREVIOUS, "Only exact accepted31 plus pending request27 is eligible")
    claim, = stop["unresolved_fee_stops"]
    require(Path(claim["run_dir"]).resolve() == RUN and claim["unverified_requests"] == [27]
        and Path(stop["run_dir"]).resolve() == RUN, "The physical pending claim is not this exact closed repeat run")


def validate_unknown(events):
    require([e["event"] for e in events] == ["request", "request_error"], "The unknown must have exactly one request/error and no response,headers or receipt")
    request, error = events
    require(request["request_id"] == error["request_id"] == 27 and request["attempt"] == 1
        and request["endpoint"] == "https://integrate.api.nvidia.com/v1/chat/completions"
        and request["payload"]["model"] == MODEL and request["payload"]["max_tokens"] == 64000
        and request["payload"]["stream"] is True and error["response_identity_and_usage_verified"] is False
        and error.get("http_status") is None and "SSLError" in error["detail"] and "SSLEOFError" in error["detail"], "A different model,receipt or transport event is not eligible")
    return request, error


def inspect():
    no_dispatchers()
    require(sha(STOP) == EXPECTED_STOP_SHA and sha(PLAN) == EXPECTED_PLAN_SHA, "Exact STOP or admitted plan changed")
    stop, plan, previous, old_config = read(STOP), read(PLAN), read(PREVIOUS), read(OLD_CONFIG)
    validate_stop(stop)
    review = read(PLAN.parent / "execution-review.json")
    require(review["status"] == "APPROVE" and not review["blocking_findings"] and review["plan_sha256"] == EXPECTED_PLAN_SHA, "The actual v32 plan lacks its independent admission")
    require(len(plan["all_files_sha256"]) == 1100 and previous["historical_unknown_ordinal"] == 31
        and previous["known_complete_generation_count"] == 69, "Original31 chain or admitted1100 scope changed")
    sources = {}
    for path in (PLAN, PLAN.parent / "execution-review.json", PREVIOUS, OLD_CONFIG, Path(__file__), BASE / "resume_verified_hy4.py"):
        sources[str(path.relative_to(ROOT))] = sha(path)
    runtime_reader = ROOT / "work/frozen-performance-free-v31/course_eval/nvidia_free.py"
    require(Path(sys.modules[audit_nvidia_events.__module__].__file__).resolve() == runtime_reader
        and sha(runtime_reader) == plan["all_files_sha256"][str(runtime_reader.relative_to(ROOT))], "The real frozen proof validator was not loaded")
    sources[str(runtime_reader.relative_to(ROOT))] = sha(runtime_reader)
    contract = ROOT / plan["lanes"]["repeat"]["contract"]
    policy = read(FOLDER / "official-nvidia-policy.json")
    require(any("no per-token billing" in row["answer"] for row in policy), "Current official no-per-token-billing policy not verified")
    protocol, trial, result = read(RUN.with_suffix(".protocol.json")), read(RUN / "trial.json"), read(RUN / "result.json")
    require(protocol["plan_sha256"] == EXPECTED_PLAN_SHA and protocol["task"] == trial["task"]["id"] == result["task"] == "pydata__xarray-4687"
        and protocol["model"] == trial["model"] == MODEL and protocol["configuration"] == "C0" and protocol["framework"] == "mini-swe"
        and protocol["limits"] == plan["limits"] and result["scoreable"] is False and result["passed"] is None, "The closed position or original null outcome changed")
    policies, bundle, ids, proofs, first_bundle = [], [], [], [], None
    trace_hash = hashlib.sha256()
    for raw in TRACE.open("rb"):
        trace_hash.update(raw)
        event = json.loads(raw)
        if event["event"] == "free_service_policy_verified":
            policies.append(event)
        elif event["event"] in {"request", "response", "billing_verified", "request_error", "response_headers"}:
            if event["event"] == "request":
                require(not bundle, "A new request preceded the previous complete proof")
            bundle.append(event)
            if event["event"] == "billing_verified":
                audited = audit_nvidia_events(policies + bundle, contract, MODEL, 64000)
                require(audited["actual_requests"] == audited["verified_nonbilled_service_calls"] == 1
                    and not audited["unverified_requests"] and audited["reported_monetary_cost"] is None, "Prefix monetary/identity proof changed")
                ids.append(event["generation_id"])
                proofs.append({"generation_id": event["generation_id"], "request_id": event["request_id"], "usage": event["usage"], "reported_monetary_cost": None})
                if first_bundle is None:
                    first_bundle = deepcopy(policies + bundle)
                bundle = []
    request, error = validate_unknown(bundle)
    require(len(ids) == len(set(ids)) == 26 and [p["request_id"] for p in proofs] == list(range(1, 27)), "The exact26 complete fresh prefix proofs changed")
    registry_path, seed_path = ROOT / plan["generation_registry"], ROOT / plan["generation_seed"]
    registry_bytes = registry_path.read_bytes()
    registry, seed, prior = json.loads(registry_bytes), read(seed_path), read(PLAN.parent / "prior-generation-registry-snapshot.json")
    require(not set(ids).intersection(seed["generation_ids"]) and not set(ids).intersection(prior["generations"])
        and not set(ids).intersection(previous["known_complete_generation_ids"]), "The26 prefix generations reuse historical identities")
    require(all(registry["generations"].get(key) == value for key, value in prior["generations"].items()), "A prior actual registry claim changed")
    for proof in proofs:
        require(registry["generations"].get(proof["generation_id"]) == {"model": MODEL, "trace": str(TRACE), "request_id": proof["request_id"]}, "A prefix proof lacks its exact actual registry claim")
    chain, link = [], PREVIOUS
    while True:
        evidence = read(link)
        chain.append({"path": str(link.relative_to(ROOT)), "sha256": sha(link), "ordinal": evidence["historical_unknown_ordinal"]})
        sources[str(link.relative_to(ROOT))] = sha(link)
        if "previous_accepted_evidence" not in evidence:
            break
        link = ROOT / evidence["previous_accepted_evidence"]
        require(sha(link) == evidence["previous_accepted_evidence_sha256"], "An accepted historical link changed")
    for path in (RUN / "result.json", RUN / "trial.json", RUN.with_suffix(".protocol.json"), contract, seed_path, PLAN.parent / "prior-generation-registry-snapshot.json", FOLDER / "official-nvidia-policy.json", FOLDER / "policy-get.json"):
        sources[str(path.relative_to(ROOT))] = sha(path)
    sources[str(TRACE.relative_to(ROOT))] = trace_hash.hexdigest()
    return stop, old_config, previous, error, ids, proofs, registry_bytes, chain, sources, first_bundle, bundle


def prepare():
    require(not (FOLDER / "prepared.json").exists(), "Never overwrite prepared evidence")
    response = requests.get(POLICY_URL, timeout=20, allow_redirects=False)
    response.raise_for_status()
    require(response.status_code == 200 and any("no per-token billing" in row["answer"] for row in response.json()), "Official current free policy GET failed")
    create("official-nvidia-policy.json", response.content)
    create("policy-get.json", encoded({"url": POLICY_URL, "http_status": response.status_code, "response_sha256": hashlib.sha256(response.content).hexdigest(), "observed_utc": datetime.now(timezone.utc).isoformat(), "model_calls": 0}))
    with STOP.with_suffix(".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        stop, config, previous, error, ids, proofs, registry, chain, sources, first, unknown = inspect()
        raw_stop = STOP.read_bytes()
        proposal = {"historical_unknown_ordinal": 32, "previous_historical_unknown": 31, "physical_unknown_requests": 1,
            "canonical_trace": str(TRACE.relative_to(ROOT)), "request_id": 27, "configured_model": MODEL,
            "complete_actual_model_identity": None, "actual_generation_id": None, "actual_usage": None, "actual_amount": None,
            "own_zero_receipt_available": False, "actual_error": error, "original_result": read(RUN / "result.json"),
            "previous_accepted_evidence": str(PREVIOUS.relative_to(ROOT)), "previous_accepted_evidence_sha256": sha(PREVIOUS), "previous_accepted_chain": chain,
            "source_sha256": sources, "raw_stop_sha256": EXPECTED_STOP_SHA, "raw_stop_snapshot": str((FOLDER / "stop-before-accepting-32.json").relative_to(ROOT)),
            "retained_original_nvidia_positions": previous["retained_original_nvidia_positions"],
            "additional_closed_v31_dsh_position": previous["additional_closed_v31_dsh_position"],
            "known_complete_generation_ids": previous["known_complete_generation_ids"] + ids, "known_complete_generation_count": 95,
            "new_closed_prefix_proofs": proofs, "current_registry_claims": len(read(ROOT / read(PLAN)["generation_registry"])["generations"]),
            "known_complete_proof_scope": "Previously selected69 plus current repeat26. Other registry claims remain preserved,not regraded or counted as new zero-dollar receipts here.",
            "new_model_calls_during_acceptance": 0, "new_original_grader_calls": 0, "scope": "Preparation only; no financial acceptance,quota clearing,model resampling or waiter launch. TLS attempt27 has no response headers or complete identity/usage/amount."}
        future = stop | {"historical_unknown_calls": 32, "accepted_total_unknown_calls": 32, "pending_unverified_calls": 0, "unverified_requests": [], "unresolved_fee_stops": [],
            "accepted_unknown_evidence": str((FOLDER / "accepted-unknown32.json").relative_to(ROOT)), "previous_pending_stop": proposal["raw_stop_snapshot"],
            "reason": "Exact NVIDIA TLS EOF attempt27 retained as unknown32; all prior31chain and selected95 complete policy proofs preserved; Hy4 quota-only pause retained; no future event accepted"}
        proposed_bytes, future_bytes = encoded(proposal), encoded(future)
        old_evidence = config["accepted_evidence"]
        config.update(accepted_unknown_count=32, quota_stop_sha256=hashlib.sha256(future_bytes).hexdigest(), accepted_evidence=future["accepted_unknown_evidence"], recovery_folder=str(FOLDER.relative_to(ROOT)))
        config["source_sha256"] = {config["accepted_evidence"] if name == old_evidence else name: hashlib.sha256(proposed_bytes).hexdigest() if name == old_evidence else expected for name, expected in config["source_sha256"].items()}
        require(len(config["source_sha256"]) == 14, "The unchanged generic waiter needs exactly14 bindings")
        for name, expected in config["source_sha256"].items():
            require(name == config["accepted_evidence"] or sha(ROOT / name) == expected, "An original225/3/2 waiter dependency changed: " + name)
        create("stop-before-accepting-32.json", raw_stop)
        create("generation-registry-at-prepare32.json", registry)
        create("accepted-unknown32.proposed.json", proposed_bytes)
        create("stop-after-parent-acceptance.proposed.json", future_bytes)
        create("hy4-resume.pending-acceptance.json", encoded(config))
        prepared = {"status": "prepared_not_accepted_no_wait_started", "expected_stop_sha256": EXPECTED_STOP_SHA, "proposal_sha256": hashlib.sha256(proposed_bytes).hexdigest(),
            "expected_accepted_stop_sha256": hashlib.sha256(future_bytes).hexdigest(), "pending_config_sha256": sha(FOLDER / "hy4-resume.pending-acceptance.json"), "writer_sha256": sha(Path(__file__)),
            "scope": "Parent separately reviews and explicitly applies exact proposal/future STOP bytes under the shared STOP lock. Then unchanged generic prepare must produce the pending14binding config. This preparer has no accept action."}
        create("prepared.json", encoded(prepared))
    negative = {}
    for name, mutate in (("extra_pending", lambda x: x.update(pending_unverified_calls=2)), ("future_count", lambda x: x.update(accepted_total_unknown_calls=32)), ("other_request", lambda x: x["unresolved_fee_stops"][0].update(unverified_requests=[28])), ("quota_change", lambda x: x["quota_pause"].update(resume_not_before="2026-11-25T19:00:00+08:00"))):
        value = deepcopy(stop)
        mutate(value)
        try:
            validate_stop(value)
        except ValueError:
            negative[name] = "rejected"
        else:
            raise AssertionError(name)
    for name, mutate in (("returned_unknown_receipt", lambda x: x.append({"event": "response"})), ("wrong_model", lambda x: x[0]["payload"].update(model="another-model")), ("other_endpoint", lambda x: x[0].update(endpoint="https://example.invalid"))):
        value = deepcopy(unknown)
        mutate(value)
        try:
            validate_unknown(value)
        except ValueError:
            negative[name] = "rejected"
        else:
            raise AssertionError(name)
    altered = deepcopy(first)
    next(e for e in altered if e["event"] == "response")["payload"]["usage"]["cost"] = 1
    try:
        audit_nvidia_events(altered, ROOT / read(PLAN)["lanes"]["repeat"]["contract"], MODEL, 64000)
    except ValueError:
        negative["nonzero_response"] = "rejected"
    else:
        raise AssertionError("nonzero_response")
    require(STOP.read_bytes() == raw_stop and not (FOLDER / "accepted-unknown32.json").exists(), "Preparation changed the real financial state")
    qualification = {"status": "passed", "prepared_sha256": sha(FOLDER / "prepared.json"), "writer_sha256": sha(Path(__file__)), "source_sha256": sources,
        "negative_cases": negative, "new_complete_policy_proofs": 26, "retained_selected_policy_proofs": 95, "unknown_amount": None, "unknown_usage": None, "unknown_model_identity": None,
        "registry_claims_preserved": len(json.loads(registry)["generations"]), "real_stop_bytes_unchanged": True, "model_calls": 0, "original_grader_calls": 0, "VM_calls": 0, "wait_started": False,
        "scope": "Actual closed prefix,response+proof validation and exact registry/source checks,plus private in-memory negatives. Prior1100 runtime source admission reused; no bulk rehash or new NVIDIA execution admission."}
    create("qualification.json", encoded(qualification))
    print(json.dumps({"status": qualification["status"], "prepared_sha256": qualification["prepared_sha256"], "qualification_sha256": sha(FOLDER / "qualification.json"), "known_prefix": 26, "unknown_request": 27, "stop_unchanged": True}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("prepare",))
    parser.parse_args()
    prepare()
