import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from datetime import datetime, timezone


ROOT = Path.cwd().resolve()
BASE = ROOT / "work/parallel-free-evaluation-20261124"
STOP = ROOT / "work/performance-stop-20261122.json"


def read(path):
    return json.loads(path.read_bytes())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def state(folder, value):
    temporary = folder / "hy4-resume-state.writing"
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(folder / "hy4-resume-state.json")


def accepted_pause(folder, stop):
    count = stop["accepted_total_unknown_calls"]
    if (type(count) is not int or count < 1 or stop["historical_unknown_calls"] != count
            or stop["active"] is not True or stop["pending_unverified_calls"] or stop["unresolved_fee_stops"]
            or not stop.get("quota_pause")):
        raise ValueError("Only an already accepted quota-only pause is eligible; this script never accepts a financial event")
    evidence = (ROOT / stop["accepted_unknown_evidence"]).resolve(strict=True)
    if evidence.parent != folder or read(evidence)["historical_unknown_ordinal"] != count:
        raise ValueError("The accepted evidence ordinal and selected recovery folder differ from the actual STOP")
    reset = datetime.fromisoformat(stop["quota_pause"]["resume_not_before"])
    if reset.tzinfo is None:
        raise ValueError("The actual provider reset requires an explicit timezone")
    return count, evidence, reset


def verify_config(folder):
    config = read(folder / "hy4-resume.json")
    if config["recovery_folder"] != str(folder.relative_to(ROOT)) or len(config["source_sha256"]) != 14:
        raise ValueError("The immutable recovery folder or fourteen dependencies changed")
    for name, expected in config["source_sha256"].items():
        if sha(ROOT / name) != expected:
            raise ValueError("The bounded resumption dependency changed: " + name)
    evidence = ROOT / config["accepted_evidence"]
    if (evidence.resolve().parent != folder or read(evidence)["historical_unknown_ordinal"] != config["accepted_unknown_count"]
            or sha(evidence) != config["source_sha256"][config["accepted_evidence"]]):
        raise ValueError("The frozen accepted evidence no longer matches this exact count")
    return config


def prepare(folder):
    config_path = folder / "hy4-resume.json"
    if config_path.exists():
        raise FileExistsError("Never rebind a prepared or admitted waiter; preserve the old configuration")
    with STOP.with_suffix(".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        count, evidence, reset = accepted_pause(folder, read(STOP))
        parent = BASE / "final-sql75-quota-recovered"
        fifth = ROOT / "work/pytest-5631-preservation-20261125"
        review = read(fifth / "admission-review.json")
        if (review["status"] != "APPROVE" or review["blocking_findings"]
                or review["plan_sha256"] != sha(fifth / "frozen/plan.json")
                or review["runner_sha256"] != sha(fifth / "prepare_and_run.py")):
            raise ValueError("The unchanged two-session preservation revision lacks its exact prior admission")
        paths = [Path(__file__).resolve(), evidence, BASE / "recover_hy4_quota.py",
            BASE / "quota-recovery-20261125/prepared.json", BASE / "quota-recovery-20261125/accepted-unknown25.json",
            BASE / "run_ready_queues.py", BASE / "prepare_reuse_ablation.py", BASE / "run_reuse_ablation.py",
            BASE / "run_fixed_free_trials.py", ROOT / "work/check_codebuddy_free_models.py",
            fifth / "frozen/plan.json", fifth / "admission-review.json", parent / "main-plan.json", parent / "repeat-plan.json"]
        value = {"accepted_unknown_count": count, "quota_stop_sha256": sha(STOP),
            "accepted_evidence": str(evidence.relative_to(ROOT)), "recovery_folder": str(folder.relative_to(ROOT)),
            "resume_not_before": reset.isoformat(), "source_sha256": {str(path.relative_to(ROOT)): sha(path) for path in paths},
            "main_plan": str((parent / "main-plan.json").relative_to(ROOT)),
            "repeat_plan": str((parent / "repeat-plan.json").relative_to(ROOT)),
            "fifth_plan": str((fifth / "frozen/plan.json").relative_to(ROOT)),
            "fifth_source_review": str((fifth / "admission-review.json").relative_to(ROOT)),
            "no_new_model_calls_during_preparation": True,
            "scope": "Freeze only the actual already accepted STOP/evidence count selected at explicit preparation. Waiter never accepts the next unknown or clears another STOP. After reset,recheck metadata-only free route and unchanged frozen original plans; finish original225,then3 ablations,then the previously admitted2 preservation sessions. Model/runtime/tasks/checks/limits/graders remain unchanged."}
        if len(value["source_sha256"]) != 14:
            raise ValueError("The expected fourteen immutable dependencies are not unique")
        with config_path.open("x") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
    print(json.dumps({"status": "prepared_without_generation", "accepted_unknown_count": count,
        "config_sha256": sha(config_path), "sources": len(paths), "wait_started": False}))


def released_stop_still_valid(config):
    stop = read(STOP)
    if (stop["active"] or stop["pending_unverified_calls"] or stop["unresolved_fee_stops"]
            or stop["accepted_total_unknown_calls"] != config["accepted_unknown_count"]):
        raise RuntimeError("A newer financial event supersedes this frozen recovery")


def wait(folder):
    with (folder / "hy4-resume.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        config = verify_config(folder)
        config_path = folder / "hy4-resume.json"
        review = read(folder / "hy4-resume-review.json")
        if review["status"] != "APPROVE" or review["blocking_findings"] or review["config_sha256"] != sha(config_path):
            raise ValueError("The exact replacement waiter requires independent source admission")
        count = config["accepted_unknown_count"]
        reset = datetime.fromisoformat(config["resume_not_before"])
        state(folder, {"status": "waiting_for_official_reset", "pid": os.getpid(),
            "resume_not_before": reset.isoformat(), "historical_unknown": count, "new_model_calls_by_waiter": 0})
        while datetime.now(timezone.utc) < reset:
            if sha(STOP) != config["quota_stop_sha256"]:
                raise RuntimeError("A newer financial stop supersedes this exact quota resumption")
            time.sleep(min(30, max(.1, (reset - datetime.now(timezone.utc)).total_seconds())))
        verify_config(folder)
        if sha(STOP) != config["quota_stop_sha256"]:
            raise RuntimeError("Do not clear a newer stop")
        spec = importlib.util.spec_from_file_location("existing_quota_recovery_helpers", BASE / "recover_hy4_quota.py")
        old = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(old)
        old.no_running_queues()
        output = folder / "hy4-free-metadata-after-reset"
        output.mkdir()
        with (folder / "hy4-free-metadata-after-reset.log").open("x") as log:
            subprocess.run([sys.executable, str(ROOT / "work/check_codebuddy_free_models.py"),
                "--cloud-only", "--output", str(output)], cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, check=True)
        free = old.verify_free_metadata(output / "cloud-model-metadata.json")
        environment = os.environ | {"PYTHONPATH": str(ROOT)}
        manager = [sys.executable, str(BASE / "run_ready_queues.py"), "--main-plan", str(ROOT / config["main_plan"]),
            "--repeat-plan", str(ROOT / config["repeat_plan"]), "--run-label", "quota" + str(count)]
        subprocess.run([*manager, "--validate-only"], cwd=ROOT, env=environment, check=True)
        with STOP.with_suffix(".lock").open("a") as financial_lock:
            fcntl.flock(financial_lock, fcntl.LOCK_EX)
            verify_config(folder)
            if sha(STOP) != config["quota_stop_sha256"]:
                raise RuntimeError("A new actual fee stop arrived during read-only requalification")
            stop = read(STOP)
            actual_count, evidence, actual_reset = accepted_pause(folder, stop)
            if actual_count != count or actual_reset != reset or str(evidence.relative_to(ROOT)) != config["accepted_evidence"]:
                raise RuntimeError("Only the exact frozen accepted quota pause may be released")
            stop.update(active=False, quota_pause=None, reset_free_metadata=free,
                reason="Official reset elapsed; current exact free metadata and frozen original plans verified; per-call financial rules unchanged")
            temporary = STOP.with_suffix(".writing")
            temporary.write_text(json.dumps(stop, ensure_ascii=False, indent=2) + "\n")
            temporary.replace(STOP)
        state(folder, {"status": "running_original_remaining_positions", "pid": os.getpid(), "historical_unknown": count})
        with (folder / "hy4-core.log").open("x") as log:
            subprocess.run(manager, cwd=ROOT, env=environment, stdout=log, stderr=subprocess.STDOUT, check=True)
        released_stop_still_valid(config)
        if not read(BASE / "ready-queues-state.json").get("all_original225_present"):
            raise RuntimeError("The real remaining core did not complete; retain actual results")
        with (folder / "hy4-ablation.log").open("x") as log:
            for command in ([sys.executable, str(BASE / "prepare_reuse_ablation.py"), "--wait-main-references"],
                    [sys.executable, str(BASE / "run_reuse_ablation.py"), "--validate-only"],
                    [sys.executable, str(BASE / "run_reuse_ablation.py"), "--wait-core"]):
                verify_config(folder)
                released_stop_still_valid(config)
                subprocess.run(command, cwd=ROOT, env=environment, stdout=log, stderr=subprocess.STDOUT, check=True)
        verify_config(folder)
        released_stop_still_valid(config)
        command = [sys.executable, str(BASE / "run_fixed_free_trials.py"), "--plan", str(ROOT / config["fifth_plan"])]
        with (folder / "hy4-preservation.log").open("x") as log:
            subprocess.run([*command, "--validate-only"], cwd=ROOT, env=environment, stdout=log, stderr=subprocess.STDOUT, check=True)
            subprocess.run(command, cwd=ROOT, env=environment, stdout=log, stderr=subprocess.STDOUT, check=True)
        released_stop_still_valid(config)
        state(folder, {"status": "actual_core_ablation_and_preservation_ended_require_final_review_and_delivery",
            "pid": os.getpid(), "historical_unknown": count})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--folder", type=Path, required=True)
    parser.add_argument("action", choices=("prepare", "wait"))
    args = parser.parse_args()
    folder = args.folder.absolute()
    if (not folder.resolve().is_relative_to(ROOT / "work") or not folder.is_dir()
            or any(path.is_symlink() for path in (folder, *folder.parents))):
        raise ValueError("Use the explicit existing project recovery directory without symlinks")
    folder = folder.resolve()
    try:
        prepare(folder) if args.action == "prepare" else wait(folder)
    except Exception as exc:
        state(folder, {"status": "stopped_without_retry", "error_type": type(exc).__name__, "error": str(exc),
            "new_model_calls_by_waiter": 0, "observed_utc": datetime.now(timezone.utc).isoformat()})
        raise
