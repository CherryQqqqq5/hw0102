import argparse
from copy import deepcopy
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]
FOLDER = Path(__file__).resolve().parent
BASE = ROOT / "work/parallel-free-evaluation-20261124"
R34 = ROOT / "work/free-recovery34-20261125"
STOP = ROOT / "work/performance-stop-20261122.json"
RUN = ROOT / "work/vmshare/performance75-hy4-sql-layout-v18-repeat-20261125/django__django-11999-C0-r2"
MAIN = ROOT / "work/vmshare/performance75-hy4-sql-layout-v18-main-20261125/django__django-11999-C0-r1"
EXPECTED_STOP_SHA = "535a63449978903ea016f0a4207522765468b8316d1e3dc5991818f5cdf9e293"
NATIVE = Path("/Users/cherry/.codebuddy/projects/Users-cherry-Documents-Codex-2026-11-04-https-nju-link-lab-feishu-cn-2-work-vmshare-performance75-hy4-sql-layout-v18-repeat-20261125-django__django-11999-C0-r2/69beacd4-6fba-4746-8bba-5de2c906fa2d.jsonl")
NATIVE_SHA = "ff9158147f632b0f660953a7c1e69bf52ab42ddd6c815f5377e57c4c28ad815b"
LOG = Path("/Users/cherry/.codebuddy/logs/2026-11-25/django__django-11999-C0-r2__e0eeaadba6f4375de34e5bb1a7fb03e2.log")
LOG_SHA = "6114c7caf2656f473a6622ab52b181d4e30f45cc404777cb0f80b597d0fc1a50"
OBSERVED_ID = "01a213932dbd78d5a15a92b8423a6c68"
SESSION = "69beacd4-6fba-4746-8bba-5de2c906fa2d"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


prior = load("accepted34_event_helpers", R34 / "prepare.py")
resume34 = load("accepted34_immutable_resume", R34 / "resume_hy4.py")
read, sha, require, encoded = prior.read, prior.sha, prior.require, prior.encoded
verify_free_response = prior.verify_free_response


def create(name, content):
    path = FOLDER / name
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(content)


def no_dispatchers():
    prior.no_dispatchers()
    paths = [R34 / name for name in ("ready_coordinator.py", "resume_hy4.py")]
    paths += [FOLDER / name for name in ("resume_hy4.py", "continuation.py")]
    paths += [BASE / name for name in ("run_ready_queues_light_probe.py", "ready_coordinator_light_probe.py",
        "continue_light_probe_hy4.py", "resume_verified_hy4.py", "run_fixed_free_trials.py", "run_reuse_ablation.py")]
    paths += [ROOT / "work/hy4-proxy-image-preparation-20261126/continuation.py"]
    paths += [ROOT / folder / name for folder in ("work/nvidia75-light-first-v33-20261125", "work/minimax-aider-onecase-20261125")
        for name in ("run_lane.py", "run_lane_owner.py", "benchmarks_entry.py")]
    targets = {str(p) for p in paths} | {str(p.relative_to(ROOT)) for p in paths}
    for line in subprocess.check_output(["ps", "-axo", "pid=,command="], text=True).splitlines():
        parts = line.strip().split(maxsplit=1)
        if len(parts) != 2 or int(parts[0]) == os.getpid():
            continue
        try:
            found = targets.intersection(shlex.split(parts[1]))
        except ValueError:
            found = {path for path in targets if path in parts[1]}
        require(not found, "A matching dispatcher remains alive:pid=" + parts[0] + ",path=" + ",".join(sorted(found)))


def validate_stop(stop):
    require(stop["active"] is True and stop["historical_unknown_calls"] == stop["accepted_total_unknown_calls"] == 34
        and stop["pending_unverified_calls"] == 1 and stop["unverified_requests"] == [8]
        and stop.get("quota_pause") is None and ROOT / stop["accepted_unknown_evidence"] == R34 / "accepted-unknown34.json",
        "Only accepted34 plus this single unverified Hy4 request8 without quota is eligible")
    claim, = stop["unresolved_fee_stops"]
    require(Path(claim["run_dir"]).resolve() == RUN and Path(stop["run_dir"]).resolve() == RUN
        and claim["unverified_requests"] == [8] and "lacks its own valid financial evidence" in claim["reason"],
        "A different or additional financial event cannot be accepted")


def validate_events(events):
    requests_seen, responses, bills, ids, observed = [], [], [], [], set()
    payload, errors = None, []
    for event in events:
        if event["event"] == "request":
            requests_seen.append(event["request_id"])
            require(event["model"] == "hy4flash-free" and event["attempt"] == 1
                and event["native_session_id"] == SESSION and event["configured_max_output_tokens"] == 64000,
                "The actual model, independent session, budget or no-retry request changed")
        elif event["event"] == "response":
            verify_free_response(event["payload"])
            payload = event["payload"]
            responses.append(event["request_id"])
        elif event["event"] == "billing_verified":
            require(payload is not None and responses[-1] == event["request_id"], "A receipt has no corresponding actual response")
            current = {row["providerData"]["messageId"] for row in payload
                if "rawUsage" in row.get("providerData", {}) or row.get("type") == "model-usage"}
            fresh = current - observed
            require(event["request_model"] == "hy4flash-free" and event["provider_model"] == "hy4-flash-free"
                and event["credit"] == 0 and event["fresh_usage_records"] == 1 and not event["local_cli_errors"]
                and fresh == set(event["fresh_model_message_ids"]) and len(fresh) == 1,
                "Each completed request needs its own new actual zero-credit receipt")
            ids.extend(fresh)
            observed |= current
            bills.append(event["request_id"])
            payload = None
        elif event["event"] == "request_error":
            errors.append(event)
    require(requests_seen == list(range(1, 9)) and responses == bills == list(range(1, 8)) and len(set(ids)) == 7,
        "Preserve exactly8 requests,7 own-zero responses,and one missing receipt")
    error, = errors
    require(error["request_id"] == 8 and error["attempt"] == 1 and error["returncode"] == 0
        and error["failure_category"] == "invalid_cli_json" and error["billing_status"] == "unknown"
        and error["stdout"] == "" and "finish_reason=error" in error["stderr"] and "elapsed=91220ms" in error["stderr"],
        "Only the actual empty upstream-error response is covered")
    return ids, error


def closed_originals():
    groups, sources = {}, {}
    for arm, key in (("main", "policy_results"), ("repeat", "policy_results"), ("dsh", "baseline_results")):
        queue_arm = "main" if arm == "dsh" else arm
        state = read(ROOT / ("work/vmshare/performance75-hy4-sql-layout-v18-" + queue_arm + "-20261125/state.json"))
        rows = state[key]
        require(len(rows) == (63 if arm == "dsh" else 57) and len({r["task"] for r in rows}) == len(rows), "The retained177 original slots changed")
        saved = []
        for row in rows:
            directory = Path(row["run_dir"])
            outcome = read(directory / "result.json")
            require(outcome["scoreable"] is True and type(outcome["passed"]) is bool
                and outcome["passed"] == row["passed"], "A retained original score changed")
            entry = {"task": row["task"], "run_dir": str(directory.relative_to(ROOT)), "passed": row["passed"]}
            for path in (directory / "result.json", directory.with_suffix(".protocol.json")):
                sources[str(path.relative_to(ROOT))] = sha(path)
            saved.append(entry)
        groups[arm] = saved
    require([sum(r["passed"] for r in groups[a]) for a in ("main", "repeat", "dsh")] == [53, 55, 57], "Keep all165true/12false originals")
    return groups, sources


def inspect(metadata):
    no_dispatchers()
    require(sha(STOP) == EXPECTED_STOP_SHA, "The stopped event changed;never accept a later event")
    stop = read(STOP)
    validate_stop(stop)
    base = resume34.verify_config(read(R34 / "hy4-resume.json"))
    require(len(base["source_sha256"]) == 82, "Keep the actual82-source R34 verifier")
    outcome = read(RUN / "result.json")
    require(outcome["scoreable"] is False and outcome["passed"] is None and outcome["error"] == "CodeBuddy returned a non-JSON response",
        "Only the real unscored upstream interruption may get readmission")
    protocol = read(RUN.with_suffix(".protocol.json"))
    require(protocol["model"] == "hy4flash-free" and protocol["configuration"] == "C0"
        and protocol["limits"] == {"model_calls": 500, "wall_seconds": 3600.0, "command_seconds": 120, "max_output_tokens": 64000, "timeout_retries": 0, "strict_wall": True},
        "The original model/protocol/budget changed")
    ids, error = validate_events([json.loads(line) for line in (RUN / "model.jsonl").open()])
    require(not MAIN.exists() and sha(NATIVE) == NATIVE_SHA and sha(LOG) == LOG_SHA, "Main has no actual run;exact native/log followup must remain unchanged")
    native = [json.loads(line) for line in NATIVE.open()]
    usages = [row for row in native if "rawUsage" in row.get("providerData", {})]
    verify_free_response(usages)
    require(len(native) == 52 and [r["providerData"]["messageId"] for r in usages] == ids
        and native[-1]["type"] == "session-meta" and native[-1]["contextWindow"]["messageId"] == OBSERVED_ID,
        "The native followup does not supply an eighth receipt")
    previous = read(R34 / "accepted-unknown34.json")
    require(previous["historical_unknown_ordinal"] == 34, "Keep the previous34 chain")
    chain, link = [], R34 / "accepted-unknown34.json"
    groups, sources = closed_originals()
    while True:
        evidence = read(link)
        sources[str(link.relative_to(ROOT))] = sha(link)
        chain.append({"path": str(link.relative_to(ROOT)), "sha256": sha(link), "ordinal": evidence["historical_unknown_ordinal"]})
        if "previous_accepted_evidence" not in evidence:
            break
        link = ROOT / evidence["previous_accepted_evidence"]
        require(sha(link) == evidence["previous_accepted_evidence_sha256"], "A prior accepted event changed")
    model, = [r for r in read(metadata)["available_models"] if r["id"] == "hy4flash-free"]
    require(model["credits"] == "x0.00 credits" and model["maxOutputTokens"] >= 64000
        and read(metadata)["model_generation_requests"] == 0 and read(metadata)["builtins_disabled"] is True,
        "This snapshot must be actual free metadata;release must independently refresh its1200-second validity")
    for path in (Path(__file__), R34 / "prepare.py", R34 / "resume_hy4.py", R34 / "hy4-resume.json", R34 / "hy4-resume-review.json",
            RUN / "result.json", RUN / "trial.json", RUN / "model.jsonl", RUN.with_suffix(".protocol.json"), metadata,
            ROOT / "work/frozen-performance-hy4-sql-layout-v18/course_eval/codebuddy_free.py"):
        sources[str(path.relative_to(ROOT))] = sha(path)
    require(sha(Path(sys.modules[verify_free_response.__module__].__file__)) == sha(ROOT / "work/frozen-performance-hy4-sql-layout-v18/course_eval/codebuddy_free.py"),
        "The loaded receipt verifier must be the original frozen one")
    return {"stop": stop, "previous": previous, "chain": chain, "source_sha256": sources,
        "original_result": outcome, "hy4_prefix_ids": ids, "actual_error": error, "original177": groups,
        "native_followup_sha256": NATIVE_SHA, "cli_log_source_sha256": LOG_SHA}


def proposal(actual, metadata):
    return {"historical_unknown_ordinal": 35, "previous_historical_unknown": 34, "physical_unknown_requests": 1,
        "canonical_trace": str((RUN / "model.jsonl").relative_to(ROOT)), "request_id": 8, "configured_model": "hy4flash-free",
        "complete_actual_model_identity": None, "actual_generation_id": None, "actual_usage": None, "actual_amount": None,
        "observed_transport_message_id_not_receipt": OBSERVED_ID, "own_zero_receipt_available": False,
        "original_result": actual["original_result"], "actual_error": actual["actual_error"],
        "hy4_interruption": {"run_dir": str(RUN.relative_to(ROOT)), "requests": 8, "own_zero_receipts": 7,
            "fresh_model_message_ids": actual["hy4_prefix_ids"], "native_session_id": SESSION},
        "known_complete_generation_ids": actual["previous"]["known_complete_generation_ids"],
        "known_complete_generation_count": actual["previous"]["known_complete_generation_count"],
        "known_generation_scope": "Inherited NVIDIA/MiniMax list unchanged;the7 Hy4 IDs are separate,not NVIDIA registry claims",
        "source_sha256": actual["source_sha256"], "raw_stop_sha256": EXPECTED_STOP_SHA,
        "raw_stop_snapshot": str((FOLDER / "stop-before-accepting-35.json").relative_to(ROOT)),
        "previous_accepted_evidence": str((R34 / "accepted-unknown34.json").relative_to(ROOT)),
        "previous_accepted_evidence_sha256": sha(R34 / "accepted-unknown34.json"), "previous_accepted_chain": actual["chain"],
        "retained_original177": actual["original177"], "main11999_has_no_run_or_model": True,
        "native_followup": {"path": str((FOLDER / "native-session-followup.jsonl").relative_to(ROOT)), "source_path": str(NATIVE), "sha256": NATIVE_SHA},
        "cli_log_source": {"path": str(LOG), "sha256": LOG_SHA, "whole_log_archived": False},
        "prepared_metadata": {"path": str(metadata.relative_to(ROOT)), "sha256": sha(metadata), "scope": "Historical snapshot;not an own receipt or future release freshness proof"},
        "scope": "Exact upstream-error interruption only;preserve null,7 own-zero and177 original grades. No scoredfalse resampling,no quota fabricated;parent acceptance retainsactive hold;release requiresfresh metadata+independent exact configuration admission.",
        "new_model_calls_during_acceptance": 0, "new_original_grader_calls": 0}


def prepare(metadata):
    require(not (FOLDER / "prepared.json").exists(), "Never overwrite a preparation")
    with STOP.with_suffix(".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        actual = inspect(metadata)
        raw = STOP.read_bytes()
        create("native-session-followup.jsonl", NATIVE.read_bytes())
        for path in (MAIN.with_suffix(".resources.json"), MAIN.with_suffix(".resources.warmup.json")):
            target = "main-pre-model/" + path.name
            create(target, path.read_bytes())
            actual["source_sha256"][str((FOLDER / target).relative_to(ROOT))] = sha(path)
        actual["source_sha256"][str((FOLDER / "native-session-followup.jsonl").relative_to(ROOT))] = NATIVE_SHA
        evidence = proposal(actual, metadata)
        future = actual["stop"] | {"historical_unknown_calls": 35, "accepted_total_unknown_calls": 35,
            "pending_unverified_calls": 0, "unverified_requests": [], "unresolved_fee_stops": [],
            "accepted_unknown_evidence": str((FOLDER / "accepted-unknown35.json").relative_to(ROOT)),
            "previous_pending_stop": evidence["raw_stop_snapshot"],
            "reason": "Exact Hy4 upstream-error request8 retained as unknown35;7 own-zero prefix and177 originals retained;active hold remains,no quota fabricated"}
        for name, content in (("stop-before-accepting-35.json", raw), ("accepted-unknown35.proposed.json", encoded(evidence)),
                ("stop-after-parent-acceptance.proposed.json", encoded(future))):
            create(name, content)
        create("prepared.json", encoded({"status": "prepared_not_accepted_no_models", "writer_sha256": sha(Path(__file__)),
            "proposal_sha256": sha(FOLDER / "accepted-unknown35.proposed.json"), "expected_stop_sha256": EXPECTED_STOP_SHA,
            "expected_accepted_stop_sha256": sha(FOLDER / "stop-after-parent-acceptance.proposed.json"),
            "retained_originals": 177, "own_zero_prefix": 7, "unknown_requests": 1, "new_model_calls": 0}))
    require(STOP.read_bytes() == raw, "Preparation must not change actual financial state")
    return read(FOLDER / "prepared.json")


def accept(expected_prepared_sha):
    prepared = read(FOLDER / "prepared.json")
    qualification = read(FOLDER / "qualification.json")
    require(sha(FOLDER / "prepared.json") == expected_prepared_sha and qualification["status"] == "passed"
        and qualification["prepared_sha256"] == expected_prepared_sha and qualification["writer_sha256"] == sha(Path(__file__))
        and qualification["qualifier_sha256"] == sha(FOLDER / "qualify.py"), "Only explicitly reviewed exact preparation/qualification may be accepted")
    evidence_path, future_path = FOLDER / "accepted-unknown35.proposed.json", FOLDER / "stop-after-parent-acceptance.proposed.json"
    evidence, future = read(evidence_path), read(future_path)
    with STOP.with_suffix(".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        actual = inspect(ROOT / evidence["prepared_metadata"]["path"])
        for name, expected in evidence["source_sha256"].items():
            require(sha(ROOT / name) == expected, "An actual preserved source changed: " + name)
        actual["source_sha256"] = evidence["source_sha256"]
        require(proposal(actual, ROOT / evidence["prepared_metadata"]["path"]) == evidence
            and sha(Path(__file__)) == prepared["writer_sha256"] and sha(evidence_path) == prepared["proposal_sha256"]
            and sha(future_path) == prepared["expected_accepted_stop_sha256"], "The reviewed event/proposal changed")
        changed = {key for key in actual["stop"].keys() | future.keys() if actual["stop"].get(key) != future.get(key)}
        require(changed == {"historical_unknown_calls", "accepted_total_unknown_calls", "pending_unverified_calls", "unverified_requests",
            "unresolved_fee_stops", "accepted_unknown_evidence", "previous_pending_stop", "reason"}
            and future["active"] is True and future["accepted_total_unknown_calls"] == future["historical_unknown_calls"] == 35
            and future["pending_unverified_calls"] == 0 and not future["unverified_requests"] and not future["unresolved_fee_stops"]
            and future.get("quota_pause") is None, "Keep the exact accepted35 hold without clearing or accepting another event")
        create("accepted-unknown35.json", evidence_path.read_bytes())
        temporary = STOP.with_suffix(".accept35-writing")
        with temporary.open("xb") as stream:
            stream.write(future_path.read_bytes())
        temporary.replace(STOP)
    return {"accepted_unknown": 35, "financial_hold_retained": True, "stop_sha256": sha(STOP), "new_model_calls": 0}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("prepare", "inspect", "accept"))
    parser.add_argument("--metadata", type=Path, default=FOLDER / "fresh-hy4-free-metadata/cloud-model-metadata.json")
    parser.add_argument("--expected-prepared-sha")
    args = parser.parse_args()
    if args.action == "prepare":
        result = prepare(args.metadata.resolve())
    elif args.action == "accept":
        require(args.expected_prepared_sha is not None, "Parent must supply the explicitly reviewed prepared SHA")
        result = accept(args.expected_prepared_sha)
    else:
        checked = inspect(args.metadata.resolve())
        result = {"status": "inspected_no_acceptance", "own_zero": len(checked["hy4_prefix_ids"]), "originals": 177, "new_model_calls": 0}
    print(json.dumps(result, ensure_ascii=False))
