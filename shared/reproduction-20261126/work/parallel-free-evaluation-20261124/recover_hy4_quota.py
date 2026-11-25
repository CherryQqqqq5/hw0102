import argparse
import copy
import fcntl
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FOLDER = Path(__file__).resolve().parent
RECOVERY = FOLDER / "quota-recovery-20261125"
DESTINATION = FOLDER / "final-sql75-quota-recovered"
STOP = ROOT / "work/performance-stop-20261122.json"


def read(path):
    return json.loads(path.read_text())


def digest(path):
    return hashlib.file_digest(path.open("rb"), "sha256").hexdigest()


def write(path, value, exclusive=False):
    if exclusive:
        with path.open("x") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        return
    temporary = path.with_name(path.name + ".writing")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)


def verify_free_metadata(path):
    metadata = read(path)
    model, = [row for row in metadata["available_models"] if row["id"] == "hy4flash-free"]
    age = (datetime.now(timezone.utc) - datetime.fromisoformat(metadata["observed_utc"])).total_seconds()
    if (metadata["model_generation_requests"] != 0 or metadata["builtins_disabled"] is not True
            or model["credits"] != "x0.00 credits" or model["maxOutputTokens"] < 64000
            or not 0 <= age <= 1200):
        raise RuntimeError("The current metadata does not establish this exact free route and output budget")
    return {"path": str(path.relative_to(ROOT)), "sha256": digest(path),
        "observed_utc": metadata["observed_utc"], "model": model}


def no_running_queues():
    processes = subprocess.check_output(["ps", "-axo", "pid,command"], text=True)
    relevant = (str(FOLDER / "ready_coordinator.py"), str(FOLDER / "run_ready_queues.py"),
        str(FOLDER / "run_fixed_free_trials.py"), str(FOLDER / "run_reuse_ablation.py"))
    for line in processes.splitlines()[1:]:
        if any(name in line for name in relevant):
            raise RuntimeError("A real evaluator remains alive; do not duplicate or interrupt it: " + line.strip())


def prepare():
    no_running_queues()
    stop = read(STOP)
    authorization = ROOT / "work/free-experiment-unknown-authorization-20261124.json"
    if (stop["active"] is not True or stop["accepted_total_unknown_calls"] != 24
            or stop["pending_unverified_calls"] != 1 or stop["unverified_requests"] != [3]
            or read(authorization)["same_class_unknown_receipt_policy"]["repeat_user_confirmation_required"] is not False):
        raise RuntimeError("The exact pending stop and standing free-channel authorization must match")
    previous = Path(stop["run_dir"])
    if previous != ROOT / "work/vmshare/performance75-hy4-sql-layout-v18-main-20261125/python-grep-C0-r1":
        raise ValueError("This recovery only covers the observed Python/grep quota rejection")
    outcome = read(previous / "result.json")
    if outcome["scoreable"] is not False or outcome["passed"] is not None:
        raise ValueError("A real scored failure cannot be readmitted by this quota recovery")
    trace, = previous.rglob("model.jsonl")
    events = [json.loads(line) for line in trace.read_text().splitlines()]
    requests = [row for row in events if row["event"] == "request"]
    receipts = [row for row in events if row["event"] == "billing_verified"]
    error, = [row for row in events if row["event"] == "request_error"]
    if ([row["request_id"] for row in requests] != [1, 2, 3]
            or any(row["model"] != "hy4flash-free" for row in requests)
            or [row["request_id"] for row in receipts] != [1, 2]
            or any(row["credit"] != 0 or row["fresh_usage_records"] != 1 for row in receipts)
            or error["request_id"] != 3 or error["billing_status"] != "unknown" or error["stdout"] != ""):
        raise ValueError("The actual request, own receipts, or missing receipt differs from this bounded recovery")
    match = re.fullmatch(r"429 .*将在 (\d{4}-\d\d-\d\d \d\d:\d\d:\d\d) UTC\+8 重置，.*\n?", error["stderr"])
    if match is None:
        raise ValueError("Only the provider's explicit quota reset message is eligible")
    reset = datetime.strptime(match[1], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone(timedelta(hours=8)))
    free = verify_free_metadata(RECOVERY / "free-metadata-before/cloud-model-metadata.json")
    plans = {lane: read(FOLDER / "final-sql75-recovered" / (lane + "-plan.json")) for lane in ("main", "repeat")}
    repeat_directory = ROOT / plans["repeat"]["queue"] / "scikit-learn__scikit-learn-25232-C0-r2"
    if repeat_directory.exists() or repeat_directory.with_suffix(".protocol.json").exists():
        raise ValueError("The repeat dispatch acquired real task evidence and requires a separate audit")
    resource_path = repeat_directory.with_suffix(".resources.json")
    resource = read(resource_path)
    if resource["returncode"] != 1 or "released_at" not in resource:
        raise ValueError("The stopped repeat's resource lease has not ended")
    shutil.copy2(STOP, RECOVERY / "stop-before-accepting-25.json")
    snapshots = {}
    for path in (resource_path, resource_path.with_suffix(".warmup.json")):
        saved = RECOVERY / ("repeat-unstarted-" + path.name)
        shutil.copy2(path, saved)
        snapshots[str(saved.relative_to(ROOT))] = digest(saved)
    acceptance_path = RECOVERY / "accepted-unknown25.json"
    source_hashes = {str(path.relative_to(ROOT)): digest(path) for path in previous.rglob("*") if path.is_file()}
    write(acceptance_path, {"historical_unknown_ordinal": 25, "request_id": 3,
        "run_dir": str(previous.relative_to(ROOT)), "configured_model": "hy4flash-free",
        "native_session_id": requests[-1]["native_session_id"], "actual_model_identity": None,
        "actual_usage": None, "actual_amount": None, "actual_request_error": error,
        "preceding_actual_own_zero_receipts": receipts, "source_sha256": source_hashes,
        "reason": "Provider quota exhausted; the rejected third request has no own financial receipt",
        "quota_reset_at": reset.isoformat(), "resume_not_before": (reset + timedelta(seconds=15)).isoformat(),
        "current_free_metadata": free, "authorization": str(authorization.relative_to(ROOT)),
        "authorization_sha256": digest(authorization), "repeat_unstarted_dispatch_snapshots": snapshots,
        "repeat_model_calls": 0, "repeat_original_scores": 0,
        "new_model_calls_during_acceptance": 0}, exclusive=True)
    DESTINATION.mkdir()
    for name in ("tasks.json", "checks.json", "scopes.json"):
        shutil.copy2(FOLDER / "final-sql75-recovered" / name, DESTINATION / name)
    replacement = previous.with_name("python-grep-C0-quota-readmission-r1")
    if replacement.exists():
        raise FileExistsError("The only declared fresh Python/grep readmission already exists")
    plans["main"]["mechanical_policy_recoveries"]["python/grep"] = {
        "original_run": str(previous), "original_result_sha256": digest(previous / "result.json"),
        "original_error": outcome["error"], "replacement_run": str(replacement),
        "reason": "One unscored provider-quota interruption; preserve two real zero receipts and unknown25; wait for official reset",
        "historical_unknown_retained": True}
    consumers = [{"queue": plan["queue"], "repeat": plan["repeat"],
        "mechanical_policy_recoveries": copy.deepcopy(plan["mechanical_policy_recoveries"])} for plan in plans.values()]
    for lane, plan in plans.items():
        parent = FOLDER / "final-sql75-recovered" / (lane + "-plan.json")
        plan.update(stage="frozen_after_observed_provider_quota_interruption",
            source_plan=str(parent.relative_to(ROOT)), source_plan_sha256=digest(parent),
            historical_unknown_preserved=25, cache_consumers=copy.deepcopy(consumers),
            operation_revision_scope="One unscored Python/grep fresh environment after the official reset; original runtime, tasks, public checks, graders, budgets, and all scored results unchanged")
        plan["request_guard_sha256"][str(acceptance_path.relative_to(ROOT))] = digest(acceptance_path)
        plan["request_guard_sha256"][str(Path(__file__).relative_to(ROOT))] = digest(Path(__file__))
        write(DESTINATION / (lane + "-plan.json"), plan, exclusive=True)
    updated = stop | {"active": True, "historical_unknown_calls": 25, "accepted_total_unknown_calls": 25,
        "pending_unverified_calls": 0, "unverified_requests": [], "unresolved_fee_stops": [],
        "previous_pending_stop": str((RECOVERY / "stop-before-accepting-25.json").relative_to(ROOT)),
        "accepted_unknown_evidence": str(acceptance_path.relative_to(ROOT)),
        "quota_pause": {"resume_not_before": (reset + timedelta(seconds=15)).isoformat(),
            "reason": "Wait for the actual provider reset; no generation probes before reset"},
        "reason": "Unknown25 preserved under standing permission; all generations remain paused until the provider's actual quota reset and a fresh free-route recheck"}
    write(STOP, updated)
    write(RECOVERY / "prepared.json", {"status": "prepared_without_new_generations", "stop_sha256": digest(STOP),
        "recovery_script_sha256": digest(Path(__file__)), "acceptance_sha256": digest(acceptance_path),
        "plan_sha256": {lane: digest(DESTINATION / (lane + "-plan.json")) for lane in plans},
        "new_model_calls": 0}, exclusive=True)
    print(json.dumps({"historical_unknown": 25, "quota_paused": True,
        "resume_not_before": updated["quota_pause"]["resume_not_before"], "new_model_calls": 0}), flush=True)


def wait_and_resume():
    with (RECOVERY / "resume.lock").open("a") as single:
        fcntl.flock(single, fcntl.LOCK_EX | fcntl.LOCK_NB)
        prepared = read(RECOVERY / "prepared.json")
        review = read(RECOVERY / "independent-review.json")
        if (review["status"] != "APPROVE" or review["blocking_findings"]
                or review["recovery_script_sha256"] != digest(Path(__file__))
                or prepared["recovery_script_sha256"] != digest(Path(__file__))):
            raise RuntimeError("The exact bounded recovery has not passed independent source review")
        acceptance_path = RECOVERY / "accepted-unknown25.json"
        if digest(acceptance_path) != prepared["acceptance_sha256"]:
            raise ValueError("The historical unknown evidence changed")
        acceptance = read(acceptance_path)
        for name, expected in acceptance["source_sha256"].items():
            if digest(ROOT / name) != expected:
                raise ValueError("The interrupted evidence changed: " + name)
        reset = datetime.fromisoformat(acceptance["resume_not_before"])
        write(RECOVERY / "resume-state.json", {"status": "waiting_for_official_quota_reset", "pid": os.getpid(),
            "resume_not_before": reset.isoformat(), "new_model_calls_by_waiter": 0})
        while datetime.now(timezone.utc) < reset:
            if digest(STOP) != prepared["stop_sha256"]:
                raise RuntimeError("Another stop or user change superseded this prepared recovery")
            time.sleep(min(30, max(0.1, (reset - datetime.now(timezone.utc)).total_seconds())))
        no_running_queues()
        if digest(STOP) != prepared["stop_sha256"]:
            raise RuntimeError("The actual stop changed; do not clear an unrelated financial stop")
        output = RECOVERY / "free-metadata-after-reset"
        output.mkdir()
        with (RECOVERY / "free-metadata-after-reset.log").open("x") as log:
            subprocess.run([sys.executable, str(ROOT / "work/check_codebuddy_free_models.py"),
                "--cloud-only", "--output", str(output)], cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, check=True)
        free = verify_free_metadata(output / "cloud-model-metadata.json")
        for lane, expected in prepared["plan_sha256"].items():
            if digest(DESTINATION / (lane + "-plan.json")) != expected:
                raise ValueError("A prospective recovery plan changed")
        manager = [sys.executable, str(FOLDER / "run_ready_queues.py"),
            "--main-plan", str(DESTINATION / "main-plan.json"),
            "--repeat-plan", str(DESTINATION / "repeat-plan.json"), "--run-label", "quota25"]
        environment = os.environ | {"PYTHONPATH": str(ROOT)}
        subprocess.run([*manager, "--validate-only"], cwd=ROOT, env=environment, check=True)
        with STOP.with_suffix(".lock").open("a") as financial_lock:
            fcntl.flock(financial_lock, fcntl.LOCK_EX)
            if digest(STOP) != prepared["stop_sha256"]:
                raise RuntimeError("A new stop arrived during metadata or plan validation")
            stop = read(STOP)
            if (stop["accepted_total_unknown_calls"] != 25 or stop["pending_unverified_calls"] != 0
                    or stop["unresolved_fee_stops"] or stop["quota_pause"]["resume_not_before"] != reset.isoformat()):
                raise RuntimeError("Only this accepted unknown25 quota pause can be released")
            write(STOP, stop | {"active": False, "quota_pause": None,
                "reset_free_metadata": free, "reason": "Official quota reset time elapsed; fresh current free-route metadata and all frozen inputs validated; strict per-call billing remains unchanged"})
        write(RECOVERY / "resume-state.json", {"status": "running_original_remaining_positions", "pid": os.getpid(),
            "reset_free_metadata": free, "new_model_calls_by_waiter": 0})
        with (RECOVERY / "resumed-core.log").open("x") as log:
            subprocess.run(manager, cwd=ROOT, env=environment, stdout=log, stderr=subprocess.STDOUT, check=True)
        if not read(FOLDER / "ready-queues-state.json")["all_original225_present"] or read(STOP)["active"]:
            raise RuntimeError("The original remaining evaluation stopped before completion; preserve and diagnose")
        with (RECOVERY / "resumed-ablation.log").open("x") as log:
            for command in ([sys.executable, str(FOLDER / "prepare_reuse_ablation.py"), "--wait-main-references"],
                    [sys.executable, str(FOLDER / "run_reuse_ablation.py"), "--validate-only"],
                    [sys.executable, str(FOLDER / "run_reuse_ablation.py"), "--wait-core"]):
                subprocess.run(command, cwd=ROOT, env=environment, stdout=log, stderr=subprocess.STDOUT, check=True)
        write(RECOVERY / "resume-state.json", {"status": "core_and_declared_ablation_ended_require_final_audit_and_delivery",
            "pid": os.getpid(), "new_model_calls_by_waiter": 0})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("prepare", "wait"))
    arguments = parser.parse_args()
    try:
        if arguments.action == "prepare":
            with STOP.with_suffix(".lock").open("a") as financial_lock:
                fcntl.flock(financial_lock, fcntl.LOCK_EX)
                prepare()
        else:
            wait_and_resume()
    except Exception as error:
        write(RECOVERY / "recovery-error.json", {"status": "stopped_without_retry", "error_type": type(error).__name__,
            "error": str(error), "new_model_calls_by_recovery_script": 0, "time": datetime.now(timezone.utc).isoformat()})
        raise
