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
PLAN = ROOT / "work/nvidia75-light-first-v33-20261125/plan.json"
PREVIOUS = ROOT / "work/free-recovery32-20261125/accepted-unknown32.json"
CONTINUATION = BASE / "terminal-light-probe-20261125"
EXPECTED_STOP_SHA = "bfa8754642743ed16d6ce3f70d61349cea0cf7be6dbb876605457a0101540617"
EXPECTED_PLAN_SHA = "18cef63f6033106e9f1ea8c019a0d9ad2ac178127cdbcc4c0cafa29419686d9e"
MODEL = "stepfun-ai/step-5-preview"
POLICY_URL = "https://build.nvidia.com/api/runtime/content/help-center-faq.yaml"
spec = importlib.util.spec_from_file_location("preserved_recovery32_helpers", PREVIOUS.with_name("prepare.py"))
old = importlib.util.module_from_spec(spec)
spec.loader.exec_module(old)
read, sha, require, encoded = old.read, old.sha, old.require, old.encoded
sys.path.insert(0, str(ROOT / "work/frozen-performance-free-v31"))
from course_eval.nvidia_free import admit_nvidia_channel, audit_nvidia_events


def create(name, value):
    with (FOLDER / name).open("xb") as stream:
        stream.write(value)


def no_dispatchers():
    paths = [PLAN.parent / name for name in ("run_lane.py", "benchmarks_entry.py")]
    paths += [BASE / name for name in ("continue_light_probe_hy4.py", "resume_verified_hy4.py", "run_ready_queues_light_probe.py", "ready_coordinator_light_probe.py", "run_ready_queues.py", "ready_coordinator.py", "run_fixed_free_trials.py", "run_reuse_ablation.py")]
    paths += [ROOT / "work/frozen-performance-free-v31/course_eval/nvidia_free.py"]
    targets = {str(p) for p in paths} | {str(p.relative_to(ROOT)) for p in paths}
    for line in subprocess.check_output(["ps", "-axo", "pid=,command="], text=True).splitlines():
        fields = line.strip().split(maxsplit=1)
        if len(fields) != 2:
            continue
        try:
            arguments = shlex.split(fields[1])
        except ValueError:
            require(not any(path in fields[1] for path in targets), "An undecodable command may contain a dispatcher")
            continue
        require(not targets.intersection(arguments), "A real dispatcher/model worker remains alive: " + fields[0])


def validate_stop(value, run):
    require(value["active"] is True and value["historical_unknown_calls"] == value["accepted_total_unknown_calls"] == 32
        and value["pending_unverified_calls"] == 1 and value["unverified_requests"] == [8]
        and value.get("quota_pause") is None and ROOT / value["accepted_unknown_evidence"] == PREVIOUS,
        "Only exact accepted32 plus the single request8 event without a quota pause is eligible")
    claim, = value["unresolved_fee_stops"]
    require(Path(claim["run_dir"]).resolve() == run and Path(value["run_dir"]).resolve() == run
        and claim["unverified_requests"] == [8], "A different or additional pending claim cannot be accepted")


def validate_unknown(events):
    require([e["event"] for e in events] == ["request", "response_headers", "request_error"], "The exact unknown has request/header/error and no complete response or receipt")
    request, headers, error = events
    require(request["request_id"] == headers["request_id"] == error["request_id"] == 8 and request["attempt"] == 1
        and request["endpoint"] == "https://integrate.api.nvidia.com/v1/chat/completions"
        and request["payload"]["model"] == MODEL and request["payload"]["max_tokens"] == 64000
        and request["payload"]["stream"] is True and headers["http_status"] == 200
        and error["response_identity_and_usage_verified"] is False and error["error_type"] == "TimeoutExpired"
        and "1271.2419851659797 seconds" in error["detail"], "A different model/receipt/deadline event is not this reviewed request")
    return request, headers, error


def scan(run, contract, expected_requests, expected_proofs):
    trace, = run.rglob("model.jsonl")
    policies, bundle, proofs, requests_seen, first = [], [], [], [], None
    digest = hashlib.sha256()
    for raw in trace.open("rb"):
        digest.update(raw)
        event = json.loads(raw)
        if event["event"] == "free_service_policy_verified":
            policies.append(event)
        elif event["event"] in {"request", "response_headers", "response", "billing_verified", "request_error"}:
            if event["event"] == "request":
                require(not bundle, "A physical request preceded an unfinished prior proof")
                requests_seen.append(event["request_id"])
            bundle.append(event)
            if event["event"] == "billing_verified":
                audited = audit_nvidia_events(policies + bundle, contract, MODEL, 64000)
                require(audited["actual_requests"] == audited["verified_nonbilled_service_calls"] == 1
                    and not audited["unverified_requests"] and audited["reported_monetary_cost"] is None, "A complete proof changed")
                proofs.append({"generation_id": event["generation_id"], "request_id": event["request_id"], "usage": event["usage"], "reported_monetary_cost": None})
                first = first or deepcopy(policies + bundle)
                bundle = []
    require(requests_seen == list(range(1, expected_requests + 1)) and len(proofs) == expected_proofs
        and [p["request_id"] for p in proofs] == list(range(1, expected_proofs + 1)), "The closed physical request/proof sequence changed")
    return trace, digest.hexdigest(), proofs, bundle, first


def inspect():
    no_dispatchers()
    require(sha(STOP) == EXPECTED_STOP_SHA and sha(PLAN) == EXPECTED_PLAN_SHA, "The actual final STOP or admitted v33 plan changed")
    stop, plan, previous = read(STOP), read(PLAN), read(PREVIOUS)
    review = read(PLAN.parent / "execution-review.json")
    require(review["status"] == "APPROVE" and not review["blocking_findings"] and review["plan_sha256"] == EXPECTED_PLAN_SHA
        and len(plan["all_files_sha256"]) == 1134 and previous["historical_unknown_ordinal"] == 32
        and previous["known_complete_generation_count"] == 95, "The prior admission or historical chain changed")
    sources = {}
    def bind(path):
        sources[str(path.relative_to(ROOT))] = sha(path)
    for path in (PLAN, PLAN.parent / "execution-review.json", Path(__file__), PREVIOUS.with_name("prepare.py"), BASE / "resume_verified_hy4.py"):
        bind(path)
    reader = ROOT / "work/frozen-performance-free-v31/course_eval/nvidia_free.py"
    require(Path(sys.modules[audit_nvidia_events.__module__].__file__).resolve() == reader
        and sha(reader) == plan["all_files_sha256"][str(reader.relative_to(ROOT))], "The actual frozen proof validator changed")
    bind(reader)
    policy = read(FOLDER / "official-nvidia-policy.json")
    require(any("no per-token billing" in row["answer"] for row in policy), "Current official non-billed policy absent")
    followup = read(FOLDER / "request8-status-followup.json")
    require(followup["complete_response_recovered"] is False and followup["http_status"] == 410
        and followup["original_physical_request"] == 8 and followup["original_nvcf_reqid"] == "2011f9c7-1fef-4533-bafd-c2a479cce417"
        and followup["original_stop_sha256"] == EXPECTED_STOP_SHA and followup["model_generation_requests"] == 0,
        "The exact read-only410 follow-up changed or a complete response was recovered")
    bind(FOLDER / "request8-status-followup.json")
    registry_path = ROOT / plan["generation_registry"]
    registry_bytes = registry_path.read_bytes()
    registry, seed, prior = json.loads(registry_bytes), read(ROOT / plan["generation_seed"]), read(PLAN.parent / "prior-generation-registry-snapshot.json")
    require(all(registry["generations"].get(key) == value for key, value in prior["generations"].items()), "An earlier actual registry claim changed")
    positions, all_ids, all_proofs, unknown, first = [], [], [], None, None
    for lane, suffix, count, complete in (("main", "C0-r1", 8, 7), ("repeat", "C0-r2", 7, 7), ("dsh", "B0-r1", 6, 6)):
        run = ROOT / plan["queue"] / lane / ("llm-inference-batching-scheduler-" + suffix)
        result, trial, protocol = read(run / "result.json"), read(run / "trial.json"), read(run.with_suffix(".protocol.json"))
        require(protocol["plan_sha256"] == EXPECTED_PLAN_SHA and protocol["task"] == result["task"] == trial["task"]["id"] == "llm-inference-batching-scheduler"
            and protocol["model"] == trial["model"] == MODEL and protocol["limits"] == trial["limits"] == plan["limits"]
            and protocol["framework"] == trial["framework"] == ("dsh" if lane == "dsh" else "mini-swe")
            and protocol["configuration"] == ("B0" if lane == "dsh" else "C0"), "A closed task/protocol/model/budget changed")
        inner = run / result["harbor_result"]
        actual = read(inner)
        require(result["scoreable"] is (lane != "dsh") and result["passed"] is (None if lane == "dsh" else False), "Preserve both original false scores and the real DSH null")
        if lane != "dsh":
            reward = inner.parent / "verifier/reward.txt"
            require(reward.read_text().strip() == "0" and actual["verifier_result"]["rewards"]["reward"] == 0 and actual["exception_info"] is None, "The original false grade changed")
            bind(reward)
        else:
            require(actual["verifier_result"] is None and "shared financial stop is active" in actual["exception_info"]["exception_message"], "The DSH null is not the closed shared-STOP interruption")
        contract = ROOT / plan["lanes"][lane]["contract"]
        trace, trace_sha, proofs, tail, sample = scan(run, contract, count, complete)
        if lane == "main":
            validate_stop(stop, trace.parent)
            unknown = tail
            validate_unknown(unknown)
        else:
            require(not tail, "Another lane has an unknown request")
        for proof in proofs:
            gid = proof["generation_id"]
            require(registry["generations"].get(gid) == {"model": MODEL, "trace": str(trace), "request_id": proof["request_id"]}, "An actual proof lacks its exact registry claim")
            all_ids.append(gid)
        first = first or sample
        all_proofs.extend(proofs)
        for path in (run / "result.json", run / "trial.json", run.with_suffix(".protocol.json"), inner, contract, trace.parent / "model-stream.jsonl"):
            bind(path)
        sources[str(trace.relative_to(ROOT))] = trace_sha
        positions.append({"lane": lane, "run_dir": str(run.relative_to(ROOT)), "original_result": result, "actual_requests": count,
            "complete_policy_proofs": complete, "generation_ids": [p["generation_id"] for p in proofs], "proofs": proofs})
    require(len(all_ids) == len(set(all_ids)) == 20 and not set(all_ids).intersection(seed["generation_ids"])
        and not set(all_ids).intersection(prior["generations"]) and not set(all_ids).intersection(previous["known_complete_generation_ids"]), "The20 new complete IDs reuse retained history")
    chain, link = [], PREVIOUS
    while True:
        evidence = read(link)
        bind(link)
        chain.append({"path": str(link.relative_to(ROOT)), "sha256": sha(link), "ordinal": evidence["historical_unknown_ordinal"]})
        if "previous_accepted_evidence" not in evidence:
            break
        link = ROOT / evidence["previous_accepted_evidence"]
        require(sha(link) == evidence["previous_accepted_evidence_sha256"], "An earlier unknown acceptance changed")
    config_path = CONTINUATION / "continuation-config.json"
    config, approved = read(config_path), read(CONTINUATION / "continuation-review.json")
    require(approved["status"] == "APPROVE" and not approved["blocking_findings"] and approved["config_sha256"] == sha(config_path)
        and config["accepted_unknown_count"] == 32 and len(config["source_sha256"]) == 21, "The current light-probe continuation lacks its exact admission")
    for name, expected in config["source_sha256"].items():
        require(sha(ROOT / name) == expected, "A reviewed light-probe continuation dependency changed: " + name)
        sources[name] = expected
    for path in (config_path, CONTINUATION / "continuation-review.json", ROOT / plan["generation_seed"], PLAN.parent / "prior-generation-registry-snapshot.json", FOLDER / "official-nvidia-policy.json", FOLDER / "policy-get.json"):
        bind(path)
    mini = ROOT / "work/minimax-free-qualification-20261125"
    vision = ROOT / "work/vmshare/minimax-vision-function-qualification-20261125"
    minimax = []
    for qualification in (mini / "catalog-probe.json", vision / "channel-qualification.json"):
        contract, receipt = admit_nvidia_channel(mini / "free-contract.json", qualification, 1024)
        require(receipt["actual_reported_monetary_cost"] is None and receipt["monetary_receipt_available"] is False, "Never invent a MiniMax monetary zero")
        minimax.append({"source": str(qualification.relative_to(ROOT)), "generation_id": receipt["generation_id"], "model": contract["model"],
            "usage": receipt["assembled_response"]["usage"], "actual_amount": None, "benchmark_score": None})
        bind(qualification)
    vision_audit = audit_nvidia_events([json.loads(line) for line in (vision / "model.jsonl").open()], mini / "free-contract.json", "minimaxai/minimax-m3.1-flash", 1024)
    require(vision_audit["actual_requests"] == vision_audit["verified_nonbilled_service_calls"] == 1 and not vision_audit["unverified_requests"], "The actual MiniMax vision proof changed")
    require(len({v["generation_id"] for v in minimax}) == 2 and not {v["generation_id"] for v in minimax}.intersection(set(all_ids) | set(previous["known_complete_generation_ids"])), "MiniMax IDs collide with retained proofs")
    for path in (mini / "free-contract.json", mini / "catalog-official-policy.json", vision / "result.json", vision / "model.jsonl", vision / "model-stream.jsonl"):
        bind(path)
    return {"stop": stop, "previous": previous, "positions": positions, "ids": all_ids, "proofs": all_proofs, "unknown": unknown,
        "registry_bytes": registry_bytes, "chain": chain, "sources": sources, "first": first, "continuation": config, "minimax": minimax}


def prepare():
    require(not (FOLDER / "prepared.json").exists(), "Never overwrite prepared recovery evidence")
    response = requests.get(POLICY_URL, timeout=20, allow_redirects=False)
    response.raise_for_status()
    require(response.status_code == 200 and any("no per-token billing" in row["answer"] for row in response.json()), "Official current free policy GET failed")
    create("official-nvidia-policy.json", response.content)
    create("policy-get.json", encoded({"url": POLICY_URL, "http_status": 200, "response_sha256": hashlib.sha256(response.content).hexdigest(), "observed_utc": datetime.now(timezone.utc).isoformat(), "model_calls": 0}))
    with STOP.with_suffix(".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        actual = inspect()
        raw_stop = STOP.read_bytes()
        proposal = {"historical_unknown_ordinal": 33, "previous_historical_unknown": 32, "physical_unknown_requests": 1,
            "canonical_trace": str((ROOT / actual["stop"]["run_dir"] / "model.jsonl").relative_to(ROOT)), "request_id": 8, "configured_model": MODEL,
            "complete_actual_model_identity": None, "actual_generation_id": None, "actual_usage": None, "actual_amount": None,
            "observed_response_headers": actual["unknown"][1], "actual_error": actual["unknown"][2], "own_zero_receipt_available": False,
            "official_status_followup": {"path": str((FOLDER / "request8-status-followup.json").relative_to(ROOT)), "sha256": sha(FOLDER / "request8-status-followup.json")},
            "previous_accepted_evidence": str(PREVIOUS.relative_to(ROOT)), "previous_accepted_evidence_sha256": sha(PREVIOUS), "previous_accepted_chain": actual["chain"],
            "source_sha256": actual["sources"], "raw_stop_sha256": EXPECTED_STOP_SHA, "raw_stop_snapshot": str((FOLDER / "stop-before-accepting-33.json").relative_to(ROOT)),
            "retained_original_nvidia_positions": actual["previous"]["retained_original_nvidia_positions"],
            "additional_closed_v31_dsh_position": actual["previous"]["additional_closed_v31_dsh_position"],
            "additional_closed_v33_positions": actual["positions"], "retained_minimax_qualification_calls": actual["minimax"],
            "known_complete_generation_ids": actual["previous"]["known_complete_generation_ids"] + actual["ids"], "known_complete_generation_count": 115,
            "new_closed_prefix_proofs": actual["proofs"], "current_registry_claims": len(json.loads(actual["registry_bytes"])["generations"]),
            "known_complete_proof_scope": "Selected prior95 plus main7/repeat7/DSH6 Step5 complete proofs. Two actual MiniMax qualifications are separately retained,not benchmark scores or dollar-zero receipts.",
            "new_model_calls_during_acceptance": 0, "new_original_grader_calls": 0,
            "scope": "Preparation only. Preserve main/repeat original false and DSH null; no future event accepted,no quota fabricated,no STOP released or model resampled."}
        future = actual["stop"] | {"historical_unknown_calls": 33, "accepted_total_unknown_calls": 33, "pending_unverified_calls": 0,
            "unverified_requests": [], "unresolved_fee_stops": [], "accepted_unknown_evidence": str((FOLDER / "accepted-unknown33.json").relative_to(ROOT)),
            "previous_pending_stop": proposal["raw_stop_snapshot"], "reason": "Exact Step5 request8 deadline cancellation retained as unknown33; selected115 complete Step5 proofs and2 separate MiniMax qualifications retained; active financial hold remains,no quota pause fabricated"}
        proposal_bytes, future_bytes = encoded(proposal), encoded(future)
        source = dict(actual["continuation"]["source_sha256"])
        source.update(actual["sources"])
        source[str((FOLDER / "accepted-unknown33.json").relative_to(ROOT))] = hashlib.sha256(proposal_bytes).hexdigest()
        source[str((FOLDER / "resume_hy4.py").relative_to(ROOT))] = sha(FOLDER / "resume_hy4.py")
        config = {"accepted_unknown_count": 33, "accepted_evidence": future["accepted_unknown_evidence"], "recovery_folder": str(FOLDER.relative_to(ROOT)),
            "accepted_stop_sha256": hashlib.sha256(future_bytes).hexdigest(), "source_sha256": source,
            "main_plan": actual["continuation"]["main_plan"], "repeat_plan": actual["continuation"]["repeat_plan"], "fifth_plan": actual["continuation"]["fifth_plan"],
            "scope": "No quota/reset wait. Only exact accepted33 financial hold may be released after fresh metadata and independent admission; resume current light-probe225 then original3ablations then2preservation. No model/runtime/input/budget change."}
        for name, data in (("stop-before-accepting-33.json", raw_stop), ("generation-registry-at-prepare33.json", actual["registry_bytes"]),
                ("accepted-unknown33.proposed.json", proposal_bytes), ("stop-after-parent-acceptance.proposed.json", future_bytes), ("hy4-resume.pending-acceptance.json", encoded(config))):
            create(name, data)
        prepared = {"status": "prepared_not_accepted_no_wait_started", "expected_stop_sha256": EXPECTED_STOP_SHA, "proposal_sha256": hashlib.sha256(proposal_bytes).hexdigest(),
            "expected_accepted_stop_sha256": hashlib.sha256(future_bytes).hexdigest(), "pending_config_sha256": sha(FOLDER / "hy4-resume.pending-acceptance.json"),
            "writer_sha256": sha(Path(__file__)), "reused_recovery32_writer_sha256": sha(PREVIOUS.with_name("prepare.py")),
            "scope": "No accept action. Parent re-runs inspect under shared STOP lock and compares exact prepared sources/registry/proposal,then explicitly accepts only this event. New no-quota wrapper retains current light-probe plans and requires independent admission before run."}
        create("prepared.json", encoded(prepared))
    require(STOP.read_bytes() == raw_stop and not (FOLDER / "accepted-unknown33.json").exists(), "Preparation changed real financial state")
    print(json.dumps({"status": prepared["status"], "prepared_sha256": sha(FOLDER / "prepared.json"), "new_step5_proofs": 20, "minimax_qualifications": 2, "stop_unchanged": True}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("prepare",))
    parser.parse_args()
    prepare()
