import argparse
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from prepare import FOLDER, ROOT, BASE, R34, STOP, load, read, sha, require, encoded, create, no_dispatchers, resume34


flow = load("reviewed_proxy_continuation_order", ROOT / "work/hy4-proxy-image-preparation-20261126/continuation.py")
RELEASED_STOP = FOLDER / "released-stop.json"


def verify_config(config=None, allow_pending=False):
    base = resume34.verify_config(read(R34 / "hy4-resume.json"))
    require(len(base["source_sha256"]) == 82, "The original R34 immutable82-source validation remains mandatory")
    formal = config is None
    config = read(FOLDER / "hy4-resume.json") if formal else config
    if formal:
        require(sha(FOLDER / "continuation-config.json") == sha(FOLDER / "hy4-resume.json"),
            "The reused continuation configuration alias must be byte-identical to the formal recovery")
    require(config["accepted_unknown_count"] == 35 and config["recovery_folder"] == str(FOLDER.relative_to(ROOT))
        and config["recovery_config_sha256"] == sha(R34 / "hy4-resume.json"), "Only this exact accepted35 configuration is eligible")
    for name, expected in config["source_sha256"].items():
        path = ROOT / name
        if allow_pending and name == config["accepted_evidence"] and not path.exists():
            path = FOLDER / "accepted-unknown35.proposed.json"
        require(not path.is_symlink() and path.resolve().is_relative_to(ROOT) and sha(path) == expected,
            "A bound recovery source changed: " + name)
    evidence = read(FOLDER / "accepted-unknown35.proposed.json" if allow_pending else ROOT / config["accepted_evidence"])
    require(evidence["historical_unknown_ordinal"] == 35 and evidence["request_id"] == 8
        and all(evidence[key] is None for key in ("complete_actual_model_identity", "actual_generation_id", "actual_usage", "actual_amount")),
        "Missing financial evidence remains null;never accept a future event")
    require(config["main_plan"] == str((FOLDER / "hy4-plans/main-plan.json").relative_to(ROOT))
        and config["repeat_plan"] == str((FOLDER / "hy4-plans/repeat-plan.json").relative_to(ROOT)), "Use the registered same-queue proxy plans")
    return config, base


def exact_hold(config, stop):
    require(sha(STOP) == config["accepted_stop_sha256"] and stop["active"] is True
        and stop["accepted_total_unknown_calls"] == stop["historical_unknown_calls"] == 35
        and stop["pending_unverified_calls"] == 0 and not stop["unverified_requests"] and not stop["unresolved_fee_stops"]
        and stop.get("quota_pause") is None and stop["accepted_unknown_evidence"] == config["accepted_evidence"],
        "Only the exact parent-accepted35 hold may be released;new STOP blocks immediately")


def financial_gate(config):
    resume34.old.released_stop_still_valid(config)
    stop = read(STOP)
    released = read(RELEASED_STOP)
    require(sha(STOP) == released["sha256"] and stop["historical_unknown_calls"] == 35
        and not stop["unverified_requests"] and stop.get("quota_pause") is None
        and stop["accepted_unknown_evidence"] == config["accepted_evidence"], "A future STOP cannot be erased or bypassed")


def flow_config(config=None, allow_pending=False):
    current, _ = verify_config(config, allow_pending=allow_pending)
    financial_gate(current)
    return current, current


def prepare():
    pending = FOLDER / "hy4-resume.pending-acceptance.json"
    config, _ = verify_config(read(pending))
    with STOP.with_suffix(".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        exact_hold(config, read(STOP))
        no_dispatchers()
        create("hy4-resume.json", pending.read_bytes())
        create("continuation-config.json", pending.read_bytes())
    return {"status": "prepared_without_dispatch", "config_sha256": sha(FOLDER / "hy4-resume.json"), "new_model_calls": 0}


def run():
    with (FOLDER / "hy4-release.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        config, _ = verify_config()
        flow.FOLDER = FOLDER
        flow.independent_review()
        exact_hold(config, read(STOP))
        no_dispatchers()
        metadata = FOLDER / ("release-free-metadata-" + str(time.time_ns()))
        with (FOLDER / "release-metadata.log").open("x") as log:
            subprocess.run([sys.executable, str(ROOT / "work/check_codebuddy_free_models.py"), "--cloud-only", "--output", str(metadata)],
                cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, check=True)
        validator = load("original1200second_metadata_validator", BASE / "recover_hy4_quota.py")
        free = validator.verify_free_metadata(metadata / "cloud-model-metadata.json")
        with STOP.with_suffix(".lock").open("a") as financial_lock:
            fcntl.flock(financial_lock, fcntl.LOCK_EX)
            verify_config(config)
            flow.independent_review()
            no_dispatchers()
            stop = read(STOP)
            exact_hold(config, stop)
            stop.update(active=False, reset_free_metadata=free,
                reason="Exact unknown35 preserved;fresh verified free metadata;one registered null11999 readmission;unchanged original225 then3 then2")
            temporary = STOP.with_suffix(".release35-writing")
            with temporary.open("xb") as stream:
                stream.write(encoded(stop))
            temporary.replace(STOP)
            create("released-stop.json", encoded({"sha256": sha(STOP), "accepted_unknown_count": 35, "config_sha256": sha(FOLDER / "hy4-resume.json")}))
        flow.verify_config = flow_config
        flow.financial_gate = financial_gate
        return flow.run()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("prepare", "validate", "run"))
    args = parser.parse_args()
    try:
        if args.action == "prepare":
            result = prepare()
        elif args.action == "validate":
            config, _ = verify_config()
            exact_hold(config, read(STOP))
            no_dispatchers()
            result = {"status": "validated_no_generation", "config_sha256": sha(FOLDER / "hy4-resume.json")}
        else:
            result = run()
        print(json.dumps(result, ensure_ascii=False))
    except Exception as error:
        flow.save(FOLDER / ("failure-" + args.action + "-" + str(time.time_ns()) + ".json"),
            {"status": "stopped_without_retry", "action": args.action, "error_type": type(error).__name__, "error": str(error),
                "new_model_calls": None if args.action == "run" else 0, "actual_child_logs_are_authoritative": True})
        raise
