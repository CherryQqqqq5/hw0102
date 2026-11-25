import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile


FOLDER = Path(__file__).resolve().parent
ROOT = FOLDER.parents[1]


def main():
    spec = importlib.util.spec_from_file_location("prospective_continuation_gate", FOLDER / "continuation.py")
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    base = runner.recovery.verify_config(runner.read(runner.RECOVERY / "hy4-resume.json"))
    if len(base["source_sha256"]) != 82:
        raise AssertionError("The actual R34 ancestry is not its source-bound82 configuration")
    negatives = []
    def reject(label, callback):
        try:
            callback()
        except (ValueError, RuntimeError) as exc:
            negatives.append({"name": label, "rejected": True, "reason": str(exc)})
        else:
            raise AssertionError("An engineering negative was accepted: " + label)
    live_stop = runner.read(runner.STOP)
    actual_blocked = False
    try:
        runner.admitted_base()
    except RuntimeError as exc:
        actual_blocked = True
        actual_error = str(exc)
    if not actual_blocked or not live_stop["active"] or live_stop["accepted_total_unknown_calls"] != 34 or live_stop["pending_unverified_calls"] != 1:
        raise AssertionError("The actual new pending event must block the old34 continuation")
    reject("actual_run_entry_blocks_new_pending_before_config", runner.verify_config)
    old_stop, old_helper_stop, old_folder = runner.STOP, runner.recovery.old.STOP, runner.FOLDER
    with tempfile.TemporaryDirectory(prefix="continuation-private-", dir=FOLDER) as temp:
        private = Path(temp)
        stop_path = private / "private-stop.json"
        clean = copy.deepcopy(live_stop)
        clean.update(active=False, accepted_total_unknown_calls=34, historical_unknown_calls=34,
            pending_unverified_calls=0, unverified_requests=[], unresolved_fee_stops=[],
            accepted_unknown_evidence=base["accepted_evidence"], quota_pause=None)
        runner.STOP = runner.recovery.old.STOP = stop_path
        runner.FOLDER = private
        try:
            runner.save(stop_path, clean)
            runner.financial_gate(base)
            for label, fields in (("new_pending", {"pending_unverified_calls": 1}),
                    ("active_stop", {"active": True}), ("nonzero_unresolved", {"unresolved_fee_stops": [{"actual_amount": 1}]}),
                    ("next_accepted35", {"accepted_total_unknown_calls": 35}),
                    ("old_unverified_request", {"unverified_requests": [8]})):
                runner.save(stop_path, clean | fields)
                reject(label, lambda: runner.financial_gate(base))
            runner.save(stop_path, clean)
            source = private / "source.txt"
            source.write_text("actual private source\n")
            config = {"source_sha256": {str(source.relative_to(ROOT)): runner.sha(source)}}
            runner.bound_sources(config)
            source.write_text("changed private source\n")
            reject("source_bytes_changed", lambda: runner.bound_sources(config))
            runner.save(private / "continuation-config.json", {"private_engineering_fixture": True})
            cfg_sha = runner.sha(private / "continuation-config.json")
            runner.save(private / "continuation-review.json", {"status": "REJECT", "blocking_findings": [], "config_sha256": cfg_sha})
            reject("unapproved_review", runner.independent_review)
            runner.save(private / "continuation-review.json", {"status": "APPROVE", "blocking_findings": [], "config_sha256": "0" * 64})
            reject("wrong_review_config_sha", runner.independent_review)
        finally:
            runner.STOP, runner.recovery.old.STOP, runner.FOLDER = old_stop, old_helper_stop, old_folder
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(2)"])
    identity = runner.process_identity(child.pid)
    if identity is None or runner.actor_state({"pid": child.pid, "identity": identity}) != "original_actor_alive":
        raise AssertionError("The actual live private child must block dispatch")
    wrong_identity = dict(identity, lstart="private different start identity")
    if runner.actor_state({"pid": child.pid, "identity": wrong_identity}) != "pid_reused_original_actor_ended":
        raise AssertionError("A reused PID must not be mistaken for the original actor")
    child.wait(timeout=10)
    if runner.actor_state({"pid": child.pid, "identity": identity}) != "original_actor_ended":
        raise AssertionError("The real private child did not exit naturally")
    proof = {"status": "PASS_PRIVATE_GATES_ONLY_NO_PIPELINE_DISPATCH", "runner_sha256": runner.sha(FOLDER / "continuation.py"),
        "qualifier_sha256": runner.sha(Path(__file__)), "actual_R34_source_count_verified": 82,
        "actual_current_stop_blocked": {"active": live_stop["active"], "accepted_unknown": 34,
            "pending": 1, "sha256": runner.sha(runner.STOP), "actual_error": actual_error},
        "private_fee_source_and_admission_negatives": negatives,
        "private_real_child_identity": identity, "private_child_natural_exit": True, "signals_sent": 0,
        "actual_old_actors": [{"pid": pid, "identity": runner.process_identity(pid)} for pid in runner.OLD_PIDS],
        "private_fixtures_removed": True, "new_model_calls": 0, "new_original_grader_calls": 0,
        "vm_commands": 0, "cloud_metadata_requests": 0, "actual_pipeline_executed": False,
        "actual_continuation_review_created": False, "actual_config_created": False,
        "scope": "Real local files and ps/lstart/comm plus a naturally exiting Python child;private fee states are explicit engineering fixtures,not acceptance/release or model/grader evidence."}
    runner.save(FOLDER / "continuation-qualification.json", proof)
    print(json.dumps({key: proof[key] for key in ("status", "actual_current_stop_blocked", "new_model_calls")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
