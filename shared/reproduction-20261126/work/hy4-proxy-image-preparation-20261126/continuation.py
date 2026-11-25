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


ROOT = Path(__file__).resolve().parents[2]
FOLDER = Path(__file__).resolve().parent
BASE = ROOT / "work/parallel-free-evaluation-20261124"
RECOVERY = ROOT / "work/free-recovery34-20261125"
STOP = ROOT / "work/performance-stop-20261122.json"
OLD_PIDS = (44136, 48061, 48108, 92656)
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(BASE))


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


recovery = load("original_accepted34_resume", RECOVERY / "resume_hy4.py")
read = recovery.old.read


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def save(path, value):
    temporary = path.with_suffix(path.suffix + ".writing")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)


def financial_gate(base):
    recovery.old.released_stop_still_valid(base)
    stop = read(STOP)
    if (base["accepted_unknown_count"] != 34 or stop["historical_unknown_calls"] != 34
            or stop["accepted_total_unknown_calls"] != 34 or stop["unverified_requests"]
            or stop["accepted_unknown_evidence"] != base["accepted_evidence"] or stop.get("quota_pause") is not None):
        raise RuntimeError("Only the already released accepted34 event is eligible;no next unknown may be accepted")


def admitted_base():
    path = RECOVERY / "hy4-resume.json"
    base = recovery.verify_config(read(path))
    if len(base["source_sha256"]) != 82:
        raise ValueError("The current R34 configuration must retain its actual82 bindings")
    review = read(RECOVERY / "hy4-resume-review.json")
    if review["status"] != "APPROVE" or review["blocking_findings"] or review["config_sha256"] != sha(path):
        raise ValueError("The original accepted34 recovery lost its exact independent admission")
    financial_gate(base)
    return base


def process_identity(pid):
    result = subprocess.run(["ps", "-p", str(pid), "-o", "pid=,lstart=,comm="],
        capture_output=True, text=True, check=False)
    if result.returncode == 1 and not result.stdout.strip():
        return None
    result.check_returncode()
    fields = result.stdout.strip().split(maxsplit=6)
    if len(fields) != 7 or int(fields[0]) != pid:
        raise ValueError("The exact actor pid/lstart/comm metadata cannot be parsed")
    return {"pid": pid, "lstart": " ".join(fields[1:6]), "comm": fields[6]}


def actor_state(record):
    current = process_identity(record["pid"])
    if record["identity"] is None:
        return "absent_when_prepared"
    if current is None:
        return "original_actor_ended"
    return "original_actor_alive" if current == record["identity"] else "pid_reused_original_actor_ended"


def bound_sources(config):
    for name, expected in config["source_sha256"].items():
        path = ROOT / name
        if path.is_symlink() or not path.resolve().is_relative_to(ROOT) or sha(path) != expected:
            raise ValueError("A prospective continuation source changed: " + name)


def verify_config():
    base = admitted_base()
    config = read(FOLDER / "continuation-config.json")
    if config["accepted_unknown_count"] != 34 or config["recovery_config_sha256"] != sha(RECOVERY / "hy4-resume.json"):
        raise ValueError("The continuation cannot migrate to another financial event")
    bound_sources(config)
    return config, base


def prepare():
    output = FOLDER / "continuation-config.json"
    if output.exists():
        raise FileExistsError("Keep the prospective continuation configuration immutable")
    base = admitted_base()
    qualification = read(FOLDER / "continuation-qualification.json")
    if (qualification["status"] != "PASS_PRIVATE_GATES_ONLY_NO_PIPELINE_DISPATCH"
            or qualification["runner_sha256"] != sha(Path(__file__)) or qualification["new_model_calls"] != 0
            or qualification["qualifier_sha256"] != sha(FOLDER / "qualify_continuation.py")):
        raise ValueError("The actual zero-model local gate qualification is required")
    review = read(FOLDER / "execution-review.json")
    if review["status"] != "APPROVE" or review["blocking_findings"]:
        raise ValueError("The exact image-preparation plans require their existing independent review")
    paths = [Path(__file__), FOLDER / "qualify_continuation.py", FOLDER / "continuation-qualification.json",
        FOLDER / "execution-review.json", FOLDER / "prepared.json", RECOVERY / "hy4-resume.json",
        RECOVERY / "hy4-resume-review.json", RECOVERY / "resume_hy4.py", BASE / "resume_verified_hy4.py",
        BASE / "recover_hy4_quota.py", ROOT / "work/check_codebuddy_free_models.py",
        BASE / "run_ready_queues_light_probe.py", BASE / "ready_coordinator_light_probe.py",
        BASE / "prepare_reuse_ablation.py", BASE / "run_reuse_ablation.py", BASE / "run_fixed_free_trials.py",
        ROOT / base["fifth_plan"]]
    for arm in ("main", "repeat"):
        path = FOLDER / "plans" / (arm + "-plan.json")
        if sha(path) != review["plan_sha256"][arm]:
            raise ValueError("The admitted public-image plan changed")
        plan = read(path)
        paths.extend([path, *[path.parent / name for name in ("tasks.json", "checks.json", "scopes.json")]])
        paths.extend(ROOT / name for name in plan["image_preparation_sha256"])
    config = {"accepted_unknown_count": 34, "recovery_config_sha256": sha(RECOVERY / "hy4-resume.json"),
        "main_plan": str((FOLDER / "plans/main-plan.json").relative_to(ROOT)),
        "repeat_plan": str((FOLDER / "plans/repeat-plan.json").relative_to(ROOT)), "fifth_plan": base["fifth_plan"],
        "old_actors": [{"pid": pid, "identity": process_identity(pid)} for pid in OLD_PIDS],
        "source_sha256": {str(path.resolve().relative_to(ROOT)): sha(path) for path in paths},
        "new_model_calls_during_preparation": 0,
        "scope": "Wait for old actors to exit without signals;fresh read-only free metadata;original225 then3ablations then2preservation. Never accept or clear financial STOP."}
    financial_gate(base)
    with output.open("x") as stream:
        stream.write(json.dumps(config, ensure_ascii=False, indent=2) + "\n")
    return {"status": "prepared_not_started", "config_sha256": sha(output), "sources": len(config["source_sha256"])}


def core_complete(config):
    plans = {arm: read(ROOT / config[arm + "_plan"]) for arm in ("main", "repeat")}
    states = {arm: read(ROOT / plan["queue"] / "state.json") for arm, plan in plans.items()}
    expected = set(plans["main"]["task_order"])
    actual = [states["main"]["baseline_results"], states["main"]["policy_results"], states["repeat"]["policy_results"]]
    return (states["main"]["status"] == states["repeat"]["status"] == "complete"
        and states["main"]["baseline_completed"] == states["main"]["policy_completed"] == states["repeat"]["policy_completed"] == 75
        and all(len(rows) == 75 and {row["task"] for row in rows} == expected for rows in actual))


def independent_review():
    path = FOLDER / "continuation-review.json"
    review = read(path)
    if (review["status"] != "APPROVE" or review["blocking_findings"]
            or review["config_sha256"] != sha(FOLDER / "continuation-config.json")):
        raise ValueError("The exact continuation configuration requires independent parent admission")
    return sha(path)


def closed_stage(plan_path, required):
    plan = read(plan_path)
    state = read(ROOT / plan["queue"] / "state.json")
    rows = state["rows"]
    if (state["plan_sha256"] != sha(plan_path) or state["stage"] != "complete"
            or state["required"] != required or state["completed"] != required or len(rows) != required
            or len({row["run_dir"] for row in rows}) != required):
        raise RuntimeError("The actual fixed stage has not closed all original-scored positions")
    for row in rows:
        path = ROOT / row["run_dir"] / "result.json"
        result = read(path)
        if (sha(path) != row["original_score_sha256"] or result["scoreable"] is not True
                or type(result["passed"]) is not bool or row["passed"] != result["passed"]):
            raise RuntimeError("Retain an incomplete or changed outcome for parent diagnosis without resampling")
    return {"scored": required, "raw_passed": sum(row["passed"] for row in rows),
        "qualified_passed": state.get("qualified_passed"), "plan_sha256": sha(plan_path)}


def run():
    with (FOLDER / "continuation.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        config, base = verify_config()
        approval_sha = independent_review()
        state = {"pid": os.getpid(), "status": "waiting_for_old_actors_natural_exit", "accepted_unknown_count": config["accepted_unknown_count"],
            "config_sha256": sha(FOLDER / "continuation-config.json")}
        deadline = time.monotonic() + 48 * 3600
        while True:
            financial_gate(base)
            bound_sources(config)
            actors = [actor_state(row) for row in config["old_actors"]]
            state["old_actor_states"] = actors
            save(FOLDER / "continuation-state.json", state)
            if "original_actor_alive" not in actors:
                break
            if time.monotonic() > deadline:
                raise TimeoutError("The old actors did not naturally exit within48hours;no signals sent")
            time.sleep(10)
        environment = os.environ | {"PYTHONPATH": str(ROOT), "DOCKER_HOST": "unix://" + str(ROOT / "work/v/c/sock/docker.sock"),
            "DOCKER_CONFIG": str(ROOT / "work/docker-config"), "LIMA_HOME": str(ROOT / ".v"),
            "COURSE_DOCKER_BIN": str(ROOT / "work/vendor/docker/docker"),
            "COURSE_PINNED_IMAGE_COPY_DRIVER": str(ROOT / read(ROOT / config["main_plan"])["image_copy_driver"]),
            "COURSE_FREE_STOP_PATH": str(STOP)}
        def gate():
            verify_config()
            if independent_review() != approval_sha:
                raise ValueError("The independent admission changed during continuation")
        def command(arguments, log):
            gate()
            subprocess.run(arguments, cwd=ROOT, env=environment, stdout=log, stderr=subprocess.STDOUT, check=True)
            gate()
        gate()
        metadata = FOLDER / "fresh-free-metadata"
        metadata.mkdir(exist_ok=False)
        with (FOLDER / "metadata.log").open("x") as log:
            command([sys.executable, str(ROOT / "work/check_codebuddy_free_models.py"), "--cloud-only", "--output", str(metadata)], log)
        metadata_owner = load("original_free_metadata_validation", BASE / "recover_hy4_quota.py")
        state["free_metadata"] = metadata_owner.verify_free_metadata(metadata / "cloud-model-metadata.json")
        manager = [sys.executable, str(BASE / "run_ready_queues_light_probe.py"), "--main-plan", str(ROOT / config["main_plan"]),
            "--repeat-plan", str(ROOT / config["repeat_plan"]), "--run-label", "proxy-image-natural-continuation"]
        state["status"] = "validating_original_core"
        save(FOLDER / "continuation-state.json", state)
        with (FOLDER / "core.log").open("x") as log:
            command([*manager, "--validate-only"], log)
            if not core_complete(config):
                command(manager, log)
        if not core_complete(config):
            raise RuntimeError("The actual original225 core is incomplete")
        state["core_original225_present"] = True
        state["status"] = "preparing_original_three_guidance_ablations"
        save(FOLDER / "continuation-state.json", state)
        ablation_path = BASE / "final-reuse-ablation/plan.json"
        with (FOLDER / "ablation.log").open("x") as log:
            if not ablation_path.exists():
                command([sys.executable, str(BASE / "prepare_reuse_ablation.py"), "--main-plan", str(ROOT / config["main_plan"]),
                    "--repeat-plan", str(ROOT / config["repeat_plan"]), "--out", str(ablation_path.parent)], log)
            command([sys.executable, str(BASE / "run_reuse_ablation.py"), "--plan", str(ablation_path), "--validate-only"], log)
            warm_plan(ablation_path, config, gate, environment)
            command([sys.executable, str(BASE / "run_reuse_ablation.py"), "--plan", str(ablation_path), "--wait-core"], log)
        state["ablation"] = closed_stage(ablation_path, 3)
        state["status"] = "running_original_two_preservation_sessions"
        save(FOLDER / "continuation-state.json", state)
        fifth = ROOT / config["fifth_plan"]
        fixed = [sys.executable, str(BASE / "run_fixed_free_trials.py"), "--plan", str(fifth)]
        with (FOLDER / "preservation.log").open("x") as log:
            command([*fixed, "--validate-only"], log)
            warm_plan(fifth, config, gate, environment)
            command(fixed, log)
        state["preservation"] = closed_stage(fifth, 2)
        gate()
        state["status"] = "actual_stages_closed_require_parent_final_audit_and_report"
        save(FOLDER / "continuation-state.json", state)
        return state


def warm_plan(path, config, gate, environment):
    plan = read(path)
    tasks = read(ROOT / plan["manifest"])["selected"]
    pins = read(ROOT / "work/vmshare/performance75-dsh-hy4-v10/environment-pins.json")["pins"]
    helper = load("original_locked_image_preparation", BASE / "ready_coordinator_light_probe.py")
    for task in tasks:
        labels = plan.get("prospective_trials")
        directories = ([ROOT / plan["queue"] / (task["id"] + "-C0-" + label) for label in labels] if labels
            else [ROOT / plan["queue"] / (task["id"] + "-C0-reuse-guidance-off-r1")])
        if all((directory / "result.json").exists() for directory in directories):
            continue
        if any(directory.exists() and not (directory / "result.json").exists() for directory in directories):
            raise RuntimeError("An unfinished fixed position requires diagnosis,not a new sample")
        expected = plan["pins"][task["id"]] if "pins" in plan else plan["pin"]
        if pins[task["id"]] != expected:
            raise ValueError("Do not warm another image than the original fixed task pin")
        gate()
        helper.prepare_missing_image(task, environment)
        gate()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("prepare", "validate", "run"))
    args = parser.parse_args()
    try:
        if args.action == "prepare":
            result = prepare()
        elif args.action == "validate":
            config, _ = verify_config()
            result = {"status": "validated_without_dispatch", "config_sha256": sha(FOLDER / "continuation-config.json"),
                "old_actors": [actor_state(row) for row in config["old_actors"]], "new_model_calls": 0}
        else:
            result = run()
        print(json.dumps(result, ensure_ascii=False), flush=True)
    except Exception as error:
        record = {"status": "stopped_without_retry", "action": args.action, "error_type": type(error).__name__,
            "error": str(error), "new_model_calls": None if args.action == "run" else 0,
            "actual_child_logs_are_authoritative": True}
        save(FOLDER / ("failure-" + args.action + "-" + str(time.time_ns()) + ".json"), record)
        raise
