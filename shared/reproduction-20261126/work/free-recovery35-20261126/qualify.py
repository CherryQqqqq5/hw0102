from copy import deepcopy
import json
from pathlib import Path

import importlib.util
import subprocess
import sys


FOLDER = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("actual_unknown35_preparation", FOLDER / "prepare.py")
owner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(owner)


def main():
    prepared = owner.read(FOLDER / "prepared.json")
    evidence = owner.read(FOLDER / "accepted-unknown35.proposed.json")
    raw_stop = owner.STOP.read_bytes()
    actual = owner.inspect(owner.ROOT / evidence["prepared_metadata"]["path"])
    events = [json.loads(line) for line in (owner.RUN / "model.jsonl").open()]
    negatives = []

    def rejected(name, function):
        try:
            function()
        except (ValueError, RuntimeError, AssertionError, KeyError, TypeError):
            negatives.append({"case": name, "rejected": True})
        else:
            raise AssertionError("A negative event was accepted: " + name)

    def changed_stop(name, **changes):
        value = deepcopy(actual["stop"])
        value.update(changes)
        rejected(name, lambda: owner.validate_stop(value))

    for name, changes in (
        ("next_accepted_event", {"historical_unknown_calls": 35, "accepted_total_unknown_calls": 35}),
        ("inactive_stop", {"active": False}), ("additional_unknown", {"pending_unverified_calls": 2}),
        ("another_request", {"unverified_requests": [9]}), ("fabricated_quota", {"quota_pause": {"active": True}}),
        ("nonzero_fee_claim", {"unresolved_fee_stops": [{"run_dir": str(owner.RUN), "unverified_requests": [8], "reason": "nonzero amount"}]})):
        changed_stop(name, **changes)

    def changed_event(name, kind, field, value):
        copied = deepcopy(events)
        next(row for row in copied if row["event"] == kind)[field] = value
        rejected(name, lambda: owner.validate_events(copied))

    for name, kind, field, value in (
        ("paid_model", "request", "model", "paid-model"), ("retry", "request", "attempt", 2),
        ("budget_changed", "request", "configured_max_output_tokens", 32000),
        ("session_changed", "request", "native_session_id", "different-session"),
        ("nonzero_receipt", "billing_verified", "credit", 0.1),
        ("no_fresh_receipt", "billing_verified", "fresh_usage_records", 0),
        ("invented_message_id", "billing_verified", "fresh_model_message_ids", [owner.OBSERVED_ID]),
        ("unknown_reported_as_verified", "request_error", "billing_status", "verified")):
        changed_event(name, kind, field, value)
    missing = [r for r in events if not (r["event"] == "request" and r["request_id"] == 8)]
    rejected("erase_actual_unknown_request", lambda: owner.validate_events(missing))
    duplicate = deepcopy(events)
    bill = [r for r in duplicate if r["event"] == "billing_verified"][1]
    bill["fresh_model_message_ids"] = [actual["hy4_prefix_ids"][0]]
    rejected("replay_prior_message_id", lambda: owner.validate_events(duplicate))
    child = subprocess.Popen([sys.executable, "-B", "-c", "import time; time.sleep(1)", str(owner.R34 / "ready_coordinator.py")],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        rejected("actual_private_process_with_old_coordinator_argv_blocks", owner.no_dispatchers)
    finally:
        child.wait(timeout=5)
    owner.no_dispatchers()
    for key in ("complete_actual_model_identity", "actual_generation_id", "actual_usage", "actual_amount"):
        value = deepcopy(evidence)
        value[key] = 0
        rejected("unknown_" + key + "_filled_zero", lambda value=value: owner.require(
            value == owner.proposal(actual | {"source_sha256": evidence["source_sha256"]}, owner.ROOT / evidence["prepared_metadata"]["path"]),
            "The actual proposal cannot replace missing evidence with zero"))
    owner.require(owner.STOP.read_bytes() == raw_stop and not (FOLDER / "accepted-unknown35.json").exists(),
        "No real financial state may be accepted or changed during qualification")
    result = {"status": "passed", "prepared_sha256": owner.sha(FOLDER / "prepared.json"),
        "writer_sha256": owner.sha(FOLDER / "prepare.py"), "qualifier_sha256": owner.sha(Path(__file__)),
        "proposal_sha256": owner.sha(FOLDER / "accepted-unknown35.proposed.json"),
        "actual_requests": 8, "actual_own_zero_receipts": 7, "actual_prefix_ids": actual["hy4_prefix_ids"],
        "native_session_id": owner.SESSION, "native_followup_records": 52, "native_followup_sha256": owner.NATIVE_SHA,
        "retained_original_scores": {arm: {"scored": len(rows), "raw_passed": sum(r["passed"] for r in rows)}
            for arm, rows in actual["original177"].items()}, "negative_cases": negatives,
        "actual_stop_sha256": owner.sha(owner.STOP), "actual_stop_unchanged": True,
        "new_model_calls": 0, "new_original_grader_calls": 0, "accept_executed": False,
        "release_executed": False, "scope": "Actual closed input/receipt/proposal validation plus copies of actual records for negative cases;no mocked model,grade,acceptance or pipeline success"}
    owner.create("qualification.json", owner.encoded(result))
    print(json.dumps({"status": result["status"], "negative_cases": len(negatives), "qualification_sha256": owner.sha(FOLDER / "qualification.json")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
