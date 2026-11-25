import argparse
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path.cwd().resolve()
FOLDER = Path(__file__).resolve().parent
BASE = ROOT / "work/parallel-free-evaluation-20261124"
STOP = ROOT / "work/performance-stop-20261122.json"
spec = importlib.util.spec_from_file_location("unchanged_hy4_resume_helpers", BASE / "resume_verified_hy4.py")
old = importlib.util.module_from_spec(spec)
spec.loader.exec_module(old)


def verify_config(config):
    if config["accepted_unknown_count"] != 34 or config["recovery_folder"] != str(FOLDER.relative_to(ROOT)):
        raise ValueError("Only this explicitly prepared accepted34 recovery is eligible")
    for name, expected in config["source_sha256"].items():
        if old.sha(ROOT / name) != expected:
            raise ValueError("The reviewed recovery source changed: " + name)
    evidence = ROOT / config["accepted_evidence"]
    if evidence.parent != FOLDER or old.read(evidence)["historical_unknown_ordinal"] != 34:
        raise ValueError("The evidence and current recovery folder must identify the same event")
    light = FOLDER / "hy4-plans"
    if config["main_plan"] != str((light / "main-plan.json").relative_to(ROOT)) or config["repeat_plan"] != str((light / "repeat-plan.json").relative_to(ROOT)):
        raise ValueError("Do not revert the actual current light-probe plans")
    return config


def exact_accepted_hold(config, stop):
    if (old.sha(STOP) != config["accepted_stop_sha256"] or stop["active"] is not True
            or stop["accepted_total_unknown_calls"] != 34 or stop["historical_unknown_calls"] != 34):
        raise ValueError("The actual financial hold is not the exact reviewed accepted34 bytes")
    if (stop["accepted_total_unknown_calls"] != 34 or stop["historical_unknown_calls"] != 34
            or stop["pending_unverified_calls"] or stop["unverified_requests"] or stop["unresolved_fee_stops"]
            or stop.get("quota_pause") is not None or stop["accepted_unknown_evidence"] != config["accepted_evidence"]):
        raise ValueError("A new pending/nonzero/quota event cannot be released")


def prepare():
    output = FOLDER / "hy4-resume.json"
    if output.exists():
        raise FileExistsError("Never rebind an existing recovery")
    config = verify_config(old.read(FOLDER / "hy4-resume.pending-acceptance.json"))
    with STOP.with_suffix(".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        exact_accepted_hold(config, old.read(STOP))
        with output.open("xb") as stream:
            stream.write((FOLDER / "hy4-resume.pending-acceptance.json").read_bytes())
    print(json.dumps({"status": "prepared_without_generation", "config_sha256": old.sha(output), "sources": len(config["source_sha256"]), "wait_started": False}))


def save(value):
    old.state(FOLDER, value)


def run():
    with (FOLDER / "hy4-resume.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        config = verify_config(old.read(FOLDER / "hy4-resume.json"))
        review = old.read(FOLDER / "hy4-resume-review.json")
        config_sha = old.sha(FOLDER / "hy4-resume.json")
        if review["status"] != "APPROVE" or review["blocking_findings"] or review["config_sha256"] != config_sha:
            raise ValueError("The exact no-quota recovery requires independent admission")
        exact_accepted_hold(config, old.read(STOP))
        spec = importlib.util.spec_from_file_location("reviewed_unknown34_inspector", FOLDER / "prepare.py")
        checker = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(checker)
        checker.no_dispatchers()
        metadata = FOLDER / "fresh-hy4-free-metadata"
        metadata.mkdir()
        with (FOLDER / "fresh-hy4-free-metadata.log").open("x") as log:
            subprocess.run([sys.executable, str(ROOT / "work/check_codebuddy_free_models.py"), "--cloud-only", "--output", str(metadata)],
                cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, check=True)
        helper_spec = importlib.util.spec_from_file_location("existing_free_metadata_validator", BASE / "recover_hy4_quota.py")
        helper = importlib.util.module_from_spec(helper_spec)
        helper_spec.loader.exec_module(helper)
        free = helper.verify_free_metadata(metadata / "cloud-model-metadata.json")
        with STOP.with_suffix(".lock").open("a") as financial_lock:
            fcntl.flock(financial_lock, fcntl.LOCK_EX)
            verify_config(config)
            checker.no_dispatchers()
            stop = old.read(STOP)
            exact_accepted_hold(config, stop)
            stop.update(active=False, reset_free_metadata=free,
                reason="Exact accepted34 financial event retained; current free Hy4 metadata verified; resume light-probe plans with one registered unscored scheduler readmission and unchanged per-request financial guards")
            temporary = STOP.with_suffix(".release34-writing")
            with temporary.open("x") as stream:
                stream.write(json.dumps(stop, ensure_ascii=False, indent=2) + "\n")
            temporary.replace(STOP)
        environment = os.environ | {"PYTHONPATH": str(ROOT)}
        revision = config["pre_core_revision"]
        revision_plan = ROOT / revision["plan"]
        admitted = old.read(ROOT / revision["review"])
        if (old.sha(revision_plan) != revision["plan_sha256"] or admitted["status"] != "APPROVE"
                or admitted["blocking_findings"] or admitted["plan_sha256"] != revision["plan_sha256"]):
            raise ValueError("The exact fixed ReLU revision requires its existing independent admission")
        state = {"pid": os.getpid(), "status": "running_two_fixed_relu_pre_core_sessions", "historical_unknown": 34,
            "config_sha256": config_sha}
        save(state)
        fixed = [sys.executable, str(BASE / "run_fixed_free_trials.py"), "--plan", str(revision_plan)]
        with (FOLDER / "pre-core-relu.log").open("x") as log:
            for command in ([*fixed, "--validate-only"], fixed):
                verify_config(config)
                old.released_stop_still_valid(config)
                subprocess.run(command, cwd=ROOT, env=environment, stdout=log, stderr=subprocess.STDOUT, check=True)
        verify_config(config)
        old.released_stop_still_valid(config)
        scored = old.read(ROOT / old.read(revision_plan)["queue"] / "state.json")
        if (scored["plan_sha256"] != revision["plan_sha256"] or scored["stage"] != "complete"
                or scored["required"] != 2 or scored["completed"] != 2 or len(scored["rows"]) != 2
                or scored["passed"] != 2 or scored["qualified_passed"] != 2
                or any(row["passed"] is not True or row["qualified_passed"] is not True for row in scored["rows"])):
            raise RuntimeError("Retain the two actual ReLU outcomes and stop for parent diagnosis;no resampling or core dispatch")
        manager = [sys.executable, str(BASE / "run_ready_queues_light_probe.py"), "--main-plan", str(ROOT / config["main_plan"]),
            "--repeat-plan", str(ROOT / config["repeat_plan"]), "--run-label", "accepted34-light-probe"]
        status = {"pid": os.getpid(), "status": "running_original_remaining_positions", "historical_unknown": 34, "config_sha256": config_sha}
        save(status)
        def still_valid():
            verify_config(config)
            old.released_stop_still_valid(config)
        with (FOLDER / "hy4-core.log").open("x") as log:
            for command in ([*manager, "--validate-only"], manager):
                still_valid()
                subprocess.run(command, cwd=ROOT, env=environment, stdout=log, stderr=subprocess.STDOUT, check=True)
        still_valid()
        if not old.read(BASE / "ready-queues-state.json").get("all_original225_present"):
            raise RuntimeError("The actual original225 core did not complete")
        status["status"] = "running_three_original_reuse_ablations"
        save(status)
        with (FOLDER / "hy4-ablation.log").open("x") as log:
            for command in ([sys.executable, str(BASE / "prepare_reuse_ablation.py"), "--wait-main-references"],
                    [sys.executable, str(BASE / "run_reuse_ablation.py"), "--validate-only"], [sys.executable, str(BASE / "run_reuse_ablation.py"), "--wait-core"]):
                still_valid()
                subprocess.run(command, cwd=ROOT, env=environment, stdout=log, stderr=subprocess.STDOUT, check=True)
        still_valid()
        status["status"] = "running_two_original_preservation_sessions"
        save(status)
        command = [sys.executable, str(BASE / "run_fixed_free_trials.py"), "--plan", str(ROOT / config["fifth_plan"])]
        with (FOLDER / "hy4-preservation.log").open("x") as log:
            for actual in ([*command, "--validate-only"], command):
                still_valid()
                subprocess.run(actual, cwd=ROOT, env=environment, stdout=log, stderr=subprocess.STDOUT, check=True)
        still_valid()
        status["status"] = "actual_core_ablation_and_preservation_ended_require_final_review_and_delivery"
        save(status)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("prepare", "run"))
    args = parser.parse_args()
    try:
        prepare() if args.action == "prepare" else run()
    except Exception as error:
        save({"status": "stopped_without_retry", "error_type": type(error).__name__, "error": str(error)})
        raise
