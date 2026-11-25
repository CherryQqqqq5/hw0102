import argparse
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path.cwd().resolve()
BASE = Path(__file__).resolve().parent
FOLDER = BASE / "terminal-light-probe-20261125"
ORIGINAL_RECOVERY = ROOT / "work/free-recovery32-20261125"
spec = importlib.util.spec_from_file_location("unchanged_hy4_recovery", BASE / "resume_verified_hy4.py")
old = importlib.util.module_from_spec(spec)
spec.loader.exec_module(old)


def save_state(value):
    temporary = FOLDER / "continuation-state.writing"
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(FOLDER / "continuation-state.json")


def validate():
    config = old.read(FOLDER / "continuation-config.json")
    original = old.verify_config(ORIGINAL_RECOVERY)
    if config["accepted_unknown_count"] != original["accepted_unknown_count"]:
        raise ValueError("The continuation cannot accept a new financial event")
    old.released_stop_still_valid(config)
    for name, expected in config["source_sha256"].items():
        if old.sha(ROOT / name) != expected:
            raise ValueError("The actual reviewed continuation source changed: " + name)
    return config


def prepare():
    output = FOLDER / "continuation-config.json"
    if output.exists():
        raise FileExistsError("Preserve the prospective continuation configuration")
    config = old.verify_config(ORIGINAL_RECOVERY)
    old.released_stop_still_valid(config)
    qualification = old.read(FOLDER / "qualification.json")
    if (qualification["status"] != "PASS_PRIVATE_OS_LOCK_AND_ACTUAL_SOURCE_CLASSIFICATION"
            or qualification["new_model_calls"] != 0 or qualification["live_pool_used"] is not False):
        raise ValueError("The actual zero-model probe concurrency qualification is required")
    metadata = FOLDER / "current-free-metadata"
    metadata.mkdir(exist_ok=False)
    with (FOLDER / "current-free-metadata.log").open("x") as log:
        subprocess.run([sys.executable, str(ROOT / "work/check_codebuddy_free_models.py"),
            "--cloud-only", "--output", str(metadata)], cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, check=True)
    helper_spec = importlib.util.spec_from_file_location("unchanged_free_metadata_reader", BASE / "recover_hy4_quota.py")
    helper = importlib.util.module_from_spec(helper_spec)
    helper_spec.loader.exec_module(helper)
    free = helper.verify_free_metadata(metadata / "cloud-model-metadata.json")
    paths = [Path(__file__).resolve(), BASE / "ready_coordinator_light_probe.py", BASE / "run_ready_queues_light_probe.py",
        FOLDER / "main-plan.json", FOLDER / "repeat-plan.json", FOLDER / "qualification.json",
        metadata / "cloud-model-metadata.json"]
    bindings = config["source_sha256"] | {str(path.relative_to(ROOT)): old.sha(path) for path in paths}
    value = {"accepted_unknown_count": config["accepted_unknown_count"], "source_sha256": bindings,
        "main_plan": str((FOLDER / "main-plan.json").relative_to(ROOT)),
        "repeat_plan": str((FOLDER / "repeat-plan.json").relative_to(ROOT)), "fifth_plan": config["fifth_plan"],
        "free_metadata": free, "new_model_calls_during_preparation": 0,
        "scope": "Continue the same original225 queues with classified interpreter-probe leases,then original3ablations and2preservation sessions. No STOP update,financial acceptance,paid fallback or model/input/budget change."}
    with output.open("x") as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"status": "prepared_not_started", "config_sha256": old.sha(output),
        "accepted_unknown_count": value["accepted_unknown_count"], "new_model_calls": 0}), flush=True)


def run():
    with (FOLDER / "continuation.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        config = validate()
        review = old.read(FOLDER / "continuation-review.json")
        if (review["status"] != "APPROVE" or review["blocking_findings"]
                or review["config_sha256"] != old.sha(FOLDER / "continuation-config.json")):
            raise ValueError("The exact prospective continuation requires source admission")
        environment = os.environ | {"PYTHONPATH": str(ROOT)}
        manager = [sys.executable, str(BASE / "run_ready_queues_light_probe.py"),
            "--main-plan", str(ROOT / config["main_plan"]), "--repeat-plan", str(ROOT / config["repeat_plan"]),
            "--run-label", "light-probe"]
        state = {"pid": os.getpid(), "status": "running_original_remaining_positions",
            "historical_unknown": config["accepted_unknown_count"], "config_sha256": old.sha(FOLDER / "continuation-config.json")}
        save_state(state)
        with (FOLDER / "actual-core.log").open("x") as log:
            subprocess.run([*manager, "--validate-only"], cwd=ROOT, env=environment, stdout=log, stderr=subprocess.STDOUT, check=True)
            validate()
            subprocess.run(manager, cwd=ROOT, env=environment, stdout=log, stderr=subprocess.STDOUT, check=True)
        validate()
        if not old.read(BASE / "ready-queues-state.json").get("all_original225_present"):
            raise RuntimeError("The actual original225 core did not complete")
        state["status"] = "running_three_original_reuse_ablations"
        save_state(state)
        with (FOLDER / "actual-ablation.log").open("x") as log:
            for command in ([sys.executable, str(BASE / "prepare_reuse_ablation.py"), "--wait-main-references"],
                    [sys.executable, str(BASE / "run_reuse_ablation.py"), "--validate-only"],
                    [sys.executable, str(BASE / "run_reuse_ablation.py"), "--wait-core"]):
                validate()
                subprocess.run(command, cwd=ROOT, env=environment, stdout=log, stderr=subprocess.STDOUT, check=True)
        validate()
        state["status"] = "running_two_original_preservation_sessions"
        save_state(state)
        command = [sys.executable, str(BASE / "run_fixed_free_trials.py"), "--plan", str(ROOT / config["fifth_plan"])]
        with (FOLDER / "actual-preservation.log").open("x") as log:
            subprocess.run([*command, "--validate-only"], cwd=ROOT, env=environment, stdout=log, stderr=subprocess.STDOUT, check=True)
            validate()
            subprocess.run(command, cwd=ROOT, env=environment, stdout=log, stderr=subprocess.STDOUT, check=True)
        validate()
        state["status"] = "actual_core_ablation_and_preservation_ended_require_final_review_and_delivery"
        save_state(state)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("prepare", "run"))
    arguments = parser.parse_args()
    try:
        prepare() if arguments.action == "prepare" else run()
    except Exception as error:
        save_state({"status": "stopped_without_retry", "error_type": type(error).__name__,
            "error": str(error), "new_model_calls_by_continuation": 0})
        raise
