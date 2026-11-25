import argparse
from copy import deepcopy
from datetime import datetime, timezone
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys

import requests


ROOT = Path.cwd().resolve()
FOLDER = Path(__file__).resolve().parent
BASE = ROOT / "work/parallel-free-evaluation-20261124"
STOP = ROOT / "work/performance-stop-20261122.json"
PREVIOUS = ROOT / "work/free-recovery33-20261125/accepted-unknown33.json"
PLAN = ROOT / "work/minimax-aider-onecase-20261125/plan.json"
RUN = ROOT / "work/vmshare/performance-minimax-aider-onecase-20261125/main/cpp-all-your-base-C0-r1"
HY4 = ROOT / "work/vmshare/performance75-hy4-sql-layout-v18-main-20261125/llm-inference-batching-scheduler-C0-r1"
OLD_PLANS = BASE / "terminal-light-probe-20261125"
EXPECTED_STOP_SHA = "3d363fbb95c5691251df26aad727acb21e8e6d6f3863cb9479675482a2dffcc3"
EXPECTED_PLAN_SHA = "73e84af77b298e0c2d336a2872ac27a74f01593e2a2cf9b708994f77f289710e"
MODEL = "minimaxai/minimax-m3.1-flash"
spec = importlib.util.spec_from_file_location("unchanged_recovery33_helpers", PREVIOUS.with_name("prepare.py"))
old = importlib.util.module_from_spec(spec)
spec.loader.exec_module(old)
old.MODEL = MODEL
read, sha, require, encoded = old.read, old.sha, old.require, old.encoded
sys.path.insert(0, str(ROOT / "work/frozen-performance-hy4-sql-layout-v18"))
from course_eval.codebuddy_free import verify_free_response
from course_eval.summarize import run_metrics


def create(name, value):
    path = FOLDER / name
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(value)


def no_dispatchers():
    paths = [PREVIOUS.with_name("resume_hy4.py"), PLAN.parent / "run_lane.py", PLAN.parent / "run_lane_owner.py",
        PLAN.parent / "benchmarks_entry.py", FOLDER / "resume_hy4.py"]
    paths += [BASE / name for name in ("run_ready_queues_light_probe.py", "ready_coordinator_light_probe.py", "run_fixed_free_trials.py", "run_reuse_ablation.py", "continue_light_probe_hy4.py")]
    paths += [ROOT / "work/frozen-performance-free-v31/course_eval/nvidia_free.py"]
    targets = {str(p) for p in paths} | {str(p.relative_to(ROOT)) for p in paths}
    for line in subprocess.check_output(["ps", "-axo", "pid=,command="], text=True).splitlines():
        fields = line.strip().split(maxsplit=1)
        if len(fields) != 2 or int(fields[0]) == os.getpid():
            continue
        try:
            arguments = shlex.split(fields[1])
        except ValueError:
            require(not any(path in fields[1] for path in targets), "A possible dispatcher has undecodable arguments")
            continue
        require(not targets.intersection(arguments), "A real model/queue actor remains alive: " + fields[0])


def validate_stop(stop):
    require(stop["active"] is True and stop["historical_unknown_calls"] == stop["accepted_total_unknown_calls"] == 33
        and stop["pending_unverified_calls"] == 1 and stop["unverified_requests"] == [2]
        and stop.get("quota_pause") is None and ROOT / stop["accepted_unknown_evidence"] == PREVIOUS,
        "Only exact accepted33 plus one current MiniMax request2 without quota is eligible")
    claim, = stop["unresolved_fee_stops"]
    require(Path(claim["run_dir"]).resolve() == RUN and Path(stop["run_dir"]).resolve() == RUN
        and claim["unverified_requests"] == [2], "The physical unknown is not this exact closed MiniMax run")


def validate_unknown(events):
    require([e["event"] for e in events] == ["request", "response_headers", "request_error"], "An unknown request must retain only its actual request/header/error")
    request, headers, error = events
    require(request["request_id"] == headers["request_id"] == error["request_id"] == 2 and request["attempt"] == 1
        and request["endpoint"] == "https://integrate.api.nvidia.com/v1/chat/completions"
        and request["payload"]["model"] == MODEL and request["payload"]["max_tokens"] == 64000
        and headers["http_status"] == 503 and headers["response_ids"]["Nvcf-Reqid"] == "3bb51585-1b35-4957-a86a-447d98e56334"
        and error["response_identity_and_usage_verified"] is False and "503 Server Error" in error["detail"], "This is not the exact503 event or it has a complete receipt")


def inspect():
    no_dispatchers()
    require(sha(STOP) == EXPECTED_STOP_SHA and sha(PLAN) == EXPECTED_PLAN_SHA, "Actual STOP or one-case MiniMax plan changed")
    stop, plan, previous = read(STOP), read(PLAN), read(PREVIOUS)
    validate_stop(stop)
    review = read(PLAN.parent / "execution-review.json")
    require(review["status"] == "APPROVE" and not review["blocking_findings"] and review["plan_sha256"] == EXPECTED_PLAN_SHA
        and previous["historical_unknown_ordinal"] == 33, "The exact prior acceptance or model admission changed")
    contract = ROOT / plan["lanes"]["main"]["contract"]
    trace, trace_sha, proofs, unknown, first = old.scan(RUN, contract, 2, 1)
    validate_unknown(unknown)
    outcome = read(RUN / "result.json")
    require(outcome["scoreable"] is False and outcome["passed"] is None, "The MiniMax interrupted attempt must remain null")
    registry_bytes = (ROOT / plan["generation_registry"]).read_bytes()
    registry, prior = json.loads(registry_bytes), read(PLAN.parent / "prior-generation-registry-snapshot.json")
    require(all(registry["generations"].get(gid) == value for gid, value in prior["generations"].items()), "An earlier actual registry claim changed")
    proof, = proofs
    require(proof["generation_id"] not in plan["historical_generation_ids"] and proof["generation_id"] not in previous["known_complete_generation_ids"]
        and proof["generation_id"] not in prior["generations"] and registry["generations"].get(proof["generation_id"]) == {"model": MODEL, "trace": str(trace), "request_id": 1}, "The actual prefix generation is reused or lacks its exact claim")
    hy4_result = read(HY4 / "result.json")
    inner = HY4 / hy4_result["harbor_result"]
    require(hy4_result["scoreable"] is False and hy4_result["passed"] is None and "error" not in hy4_result
        and read(inner)["verifier_result"] is None and "shared financial stop is active" in read(inner)["exception_info"]["exception_message"], "Only the real shared-STOP unscored scheduler may be readmitted")
    hy4_trace, = HY4.rglob("model.jsonl")
    requests_seen, returned, receipts, ids, session, payload = [], [], [], [], None, None
    observed_usage_ids = set()
    for raw in hy4_trace.open("rb"):
        event = json.loads(raw)
        if event["event"] == "request":
            requests_seen.append(event["request_id"])
            require(event["model"] == "hy4flash-free" and (session is None or event["native_session_id"] == session), "The interrupted Hy4 model/session changed")
            session = event["native_session_id"]
        elif event["event"] == "response":
            verify_free_response(event["payload"])
            payload = event["payload"]
            returned.append(event["request_id"])
        elif event["event"] == "billing_verified":
            actual_ids = {row["providerData"]["messageId"] for row in payload
                if "rawUsage" in row.get("providerData", {}) or row.get("type") == "model-usage"}
            fresh = actual_ids - observed_usage_ids
            require(event["credit"] == 0 and event["fresh_usage_records"] == 1 and fresh == set(event["fresh_model_message_ids"]) and len(fresh) == 1,
                "The interrupted Hy4 responses require their own fresh actual zero-credit proofs")
            ids.extend(fresh)
            observed_usage_ids |= actual_ids
            receipts.append(event["request_id"])
    require(requests_seen == returned == receipts == [1, 2] and len(set(ids)) == 2, "The interrupted Hy4 run must preserve exactly2/2 fresh known responses and no unknown")
    sources = {}
    def bind(path):
        sources[str(path.relative_to(ROOT))] = sha(path)
    for path in (Path(__file__), PREVIOUS.with_name("prepare.py"), PLAN, PLAN.parent / "execution-review.json", contract,
            RUN / "result.json", RUN / "trial.json", RUN.with_suffix(".protocol.json"), trace,
            HY4 / "result.json", HY4 / "trial.json", HY4.with_suffix(".protocol.json"), hy4_trace, inner,
            FOLDER / "official-nvidia-policy.json", FOLDER / "policy-get.json", FOLDER / "service-status.json", FOLDER / "root-cause-note.json",
            ROOT / "work/frozen-performance-free-v31/course_eval/nvidia_free.py", ROOT / "work/frozen-performance-free-v31/course_eval/generation_registry.py",
            ROOT / "work/frozen-performance-hy4-sql-layout-v18/course_eval/codebuddy_free.py", ROOT / "work/free-recovery33-20261125/hy4-resume.json"):
        bind(path)
    actual_hy4_validator = Path(sys.modules[verify_free_response.__module__].__file__).resolve()
    require(sha(actual_hy4_validator) == sha(ROOT / "work/frozen-performance-hy4-sql-layout-v18/course_eval/codebuddy_free.py"), "The loaded Hy4 receipt validator differs from the frozen original")
    bind(actual_hy4_validator)
    require(sources[str(trace.relative_to(ROOT))] == trace_sha, "The actual model trace changed during inspection")
    chain, link = [], PREVIOUS
    while True:
        evidence = read(link)
        bind(link)
        chain.append({"path": str(link.relative_to(ROOT)), "sha256": sha(link), "ordinal": evidence["historical_unknown_ordinal"]})
        if "previous_accepted_evidence" not in evidence:
            break
        link = ROOT / evidence["previous_accepted_evidence"]
        require(sha(link) == evidence["previous_accepted_evidence_sha256"], "The old accepted chain changed")
    require(any("no per-token billing" in row["answer"] for row in read(FOLDER / "official-nvidia-policy.json")), "The current official non-billed policy is absent")
    return {"stop": stop, "plan": plan, "previous": previous, "sources": sources, "proofs": proofs, "unknown": unknown,
        "first": first, "registry_bytes": registry_bytes, "chain": chain, "minimax_result": outcome,
        "hy4_interruption": {"run_dir": str(HY4.relative_to(ROOT)), "original_result": hy4_result, "inner_exception": read(inner)["exception_info"],
            "requests": 2, "own_zero_receipts": 2, "native_session_id": session, "fresh_model_message_ids": ids, "usage": run_metrics(HY4)}}


def prepare():
    require(not (FOLDER / "prepared.json").exists(), "Never overwrite prepared evidence")
    policy = requests.get(old.POLICY_URL, timeout=20, allow_redirects=False)
    policy.raise_for_status()
    require(policy.status_code == 200, "The current official policy GET failed")
    create("official-nvidia-policy.json", policy.content)
    create("policy-get.json", encoded({"url": old.POLICY_URL, "http_status": 200, "sha256": hashlib.sha256(policy.content).hexdigest(), "observed_utc": datetime.now(timezone.utc).isoformat(), "model_calls": 0}))
    status = requests.get("https://status.ngc.nvidia.com/api/v2/summary.json", timeout=20, allow_redirects=False)
    status.raise_for_status()
    create("service-status.json", encoded({"url": status.url, "observed_utc": datetime.now(timezone.utc).isoformat(), "http_status": status.status_code, "body": status.json(), "model_calls": 0,
        "scope": "Aggregate status only; it does not prove capacity or per-model inference availability"}))
    with STOP.with_suffix(".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        actual = inspect()
        raw_stop = STOP.read_bytes()
        proposal = {"historical_unknown_ordinal": 34, "previous_historical_unknown": 33, "physical_unknown_requests": 1,
            "canonical_trace": str((RUN / "model.jsonl").relative_to(ROOT)), "request_id": 2, "configured_model": MODEL,
            "complete_actual_model_identity": None, "actual_generation_id": None, "actual_usage": None, "actual_amount": None,
            "observed_response_headers": actual["unknown"][1], "actual_error": actual["unknown"][2], "own_zero_receipt_available": False,
            "original_minimax_result": actual["minimax_result"], "new_closed_prefix_proofs": actual["proofs"],
            "hy4_interruption": actual["hy4_interruption"], "source_sha256": actual["sources"], "raw_stop_sha256": EXPECTED_STOP_SHA,
            "raw_stop_snapshot": str((FOLDER / "stop-before-accepting-34.json").relative_to(ROOT)),
            "previous_accepted_evidence": str(PREVIOUS.relative_to(ROOT)), "previous_accepted_evidence_sha256": sha(PREVIOUS), "previous_accepted_chain": actual["chain"],
            "known_complete_generation_ids": actual["previous"]["known_complete_generation_ids"] + [actual["proofs"][0]["generation_id"]],
            "known_complete_generation_count": actual["previous"]["known_complete_generation_count"] + 1,
            "current_registry_claims": len(json.loads(actual["registry_bytes"])["generations"]),
            "retained_minimax_qualification_calls": actual["plan"]["actual_channel_qualifications"],
            "scope": "Preparation only. Retain prior33chain,all three MiniMax qualification identities/usage,the single complete benchmark prefix and two known Hy4 calls. MiniMax and Hy4 attempts remain null; no semantic failure is resampled or new MiniMax call admitted.",
            "new_model_calls_during_acceptance": 0, "new_original_grader_calls": 0}
        future = actual["stop"] | {"historical_unknown_calls": 34, "accepted_total_unknown_calls": 34, "pending_unverified_calls": 0, "unverified_requests": [], "unresolved_fee_stops": [],
            "accepted_unknown_evidence": str((FOLDER / "accepted-unknown34.json").relative_to(ROOT)), "previous_pending_stop": proposal["raw_stop_snapshot"],
            "reason": "Only exact MiniMax HTTP503 request2 retained as unknown34;prior33chain,one complete MiniMax prefix and two complete Hy4 calls preserved;active hold remains,no quota fabricated"}
        for name, value in (("stop-before-accepting-34.json", raw_stop), ("generation-registry-at-prepare34.json", actual["registry_bytes"]),
                ("accepted-unknown34.proposed.json", encoded(proposal)), ("stop-after-parent-acceptance.proposed.json", encoded(future))):
            create(name, value)
        create("prepared.json", encoded({"status": "event_prepared_not_accepted_no_models_or_wait_started", "expected_stop_sha256": EXPECTED_STOP_SHA,
            "proposal_sha256": sha(FOLDER / "accepted-unknown34.proposed.json"), "expected_accepted_stop_sha256": sha(FOLDER / "stop-after-parent-acceptance.proposed.json"),
            "writer_sha256": sha(Path(__file__)), "scope": "Parent must re-run inspect under shared STOP lock and compare exact proposal/sources/registry. This source has no accept action;separate plans/config must register the real Hy4 null interruption before resumption."}))
    require(STOP.read_bytes() == raw_stop and not (FOLDER / "accepted-unknown34.json").exists(), "Preparation changed actual financial state")
    print(json.dumps({"status": "prepared_not_accepted", "prepared_sha256": sha(FOLDER / "prepared.json"), "minimax_prefix": 1, "hy4_own_zero": 2, "stop_unchanged": True}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("prepare",))
    parser.parse_args()
    prepare()
