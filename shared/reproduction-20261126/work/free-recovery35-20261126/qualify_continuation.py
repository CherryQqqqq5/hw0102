from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import shutil


FOLDER = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("prospective35_resume", FOLDER / "resume_hy4.py")
owner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(owner)


def main():
    raw_stop = owner.STOP.read_bytes()
    config = owner.read(FOLDER / "hy4-resume.pending-acceptance.json")
    checked, base = owner.verify_config(config, allow_pending=True)
    owner.require(len(base["source_sha256"]) == 82 and checked == config, "Keep the original82-source ancestry")
    negatives = []

    def rejected(name, function):
        try:
            function()
        except (ValueError, RuntimeError, FileNotFoundError, AssertionError):
            negatives.append({"case": name, "rejected": True})
        else:
            raise AssertionError("A negative continuation input was accepted: " + name)

    rejected("actual_pending35_blocks_release", lambda: owner.exact_hold(config, owner.read(owner.STOP)))
    rejected("actual_pending35_blocks_formal_prepare", owner.prepare)
    require = owner.require
    changed = deepcopy(config)
    name = next(iter(changed["source_sha256"]))
    changed["source_sha256"][name] = "0" * 64
    rejected("changed_static_source", lambda: owner.verify_config(changed, allow_pending=True))
    changed = deepcopy(config)
    changed["accepted_unknown_count"] = 36
    rejected("wrong_event_configuration", lambda: owner.verify_config(changed, allow_pending=True))
    differences = {}
    for arm in ("main", "repeat"):
        before = owner.read(owner.ROOT / "work/hy4-proxy-image-preparation-20261126/plans" / (arm + "-plan.json"))
        after = owner.read(FOLDER / "hy4-plans" / (arm + "-plan.json"))
        different = {k for k in before.keys() | after.keys() if before.get(k) != after.get(k)}
        allowed = {"request_guard_sha256", "registered_existing_runs", "historical_unknown_preserved", "cache_consumers",
            "source_plan", "source_plan_sha256", "operation_revision_scope"}
        if arm == "repeat":
            allowed.add("mechanical_policy_recoveries")
        require(different <= allowed, "The recovery altered an input/model/check/budget/resource/grade field")
        require(all(after["request_guard_sha256"][k] == v for k, v in before["request_guard_sha256"].items()), "An inherited guard changed")
        require(all(after["registered_existing_runs"][k] == v for k, v in before["registered_existing_runs"].items()), "An old score binding changed")
        require(after["task_order"] == before["task_order"] and len(after["task_order"]) == 75, "Retain the entire ordered75")
        differences[arm] = sorted(different)
    fixture = FOLDER / "private-continuation-fixture"
    fixture.mkdir(exist_ok=False)
    original_stop, old_stop, original_released = owner.STOP, owner.resume34.old.STOP, owner.RELEASED_STOP
    try:
        owner.STOP = owner.resume34.old.STOP = fixture / "stop.json"
        owner.RELEASED_STOP = fixture / "released-stop.json"
        future = owner.read(FOLDER / "stop-after-parent-acceptance.proposed.json")
        owner.STOP.write_bytes(owner.encoded(future))
        local = deepcopy(config)
        local["accepted_stop_sha256"] = owner.sha(owner.STOP)
        owner.exact_hold(local, future)
        for name, changes in (("new_pending", {"pending_unverified_calls": 1, "unverified_requests": [9]}),
            ("next_unknown", {"accepted_total_unknown_calls": 36, "historical_unknown_calls": 36}),
            ("nonzero_unresolved", {"unresolved_fee_stops": [{"actual_amount": 1}]}),
            ("quota_added", {"quota_pause": {"active": True}}), ("inactive_hold", {"active": False})):
            bad = future | changes
            owner.STOP.write_bytes(owner.encoded(bad))
            local["accepted_stop_sha256"] = owner.sha(owner.STOP)
            rejected("private_" + name, lambda bad=bad: owner.exact_hold(local, bad))
        released = future | {"active": False}
        owner.STOP.write_bytes(owner.encoded(released))
        owner.RELEASED_STOP.write_bytes(owner.encoded({"sha256": owner.sha(owner.STOP)}))
        owner.financial_gate(config)
        require(owner.flow_config(config, allow_pending=True) == (config, config), "The actual command adapter accepts the qualified private released state")
        for name, changes in (("active", {"active": True}), ("pending", {"pending_unverified_calls": 1}),
            ("nonzero", {"unresolved_fee_stops": [{"actual_amount": 1}]})):
            owner.STOP.write_bytes(owner.encoded(released | changes))
            owner.RELEASED_STOP.write_bytes(owner.encoded({"sha256": owner.sha(owner.STOP)}))
            rejected("actual_flow_config_command_entry_" + name, lambda: owner.flow_config(config, allow_pending=True))
        owner.STOP.write_bytes(owner.encoded(released))
        owner.RELEASED_STOP.write_bytes(owner.encoded({"sha256": owner.sha(owner.STOP)}))
        owner.STOP.write_bytes(owner.encoded(released | {"reason": "different future bytes"}))
        rejected("actual_flow_config_released_stop_sha_drift_same_counter", lambda: owner.flow_config(config, allow_pending=True))
    finally:
        owner.STOP, owner.resume34.old.STOP, owner.RELEASED_STOP = original_stop, old_stop, original_released
        shutil.rmtree(fixture)
    require(original_stop.read_bytes() == raw_stop and not (FOLDER / "hy4-resume.json").exists()
        and not (FOLDER / "accepted-unknown35.json").exists(), "No actual acceptance/release/formal preparation is permitted")
    result = {"status": "PASS_PRIVATE_GATES_ONLY_NO_PIPELINE_DISPATCH", "runner_sha256": owner.sha(FOLDER / "resume_hy4.py"),
        "qualifier_sha256": owner.sha(Path(__file__)), "plan_freezer_sha256": owner.sha(FOLDER / "prepare_hy4.py"),
        "pending_config_sha256": owner.sha(FOLDER / "hy4-resume.pending-acceptance.json"), "source_bindings": len(config["source_sha256"]),
        "ancestor_bindings": 82, "plan_field_differences": differences, "negative_cases": negatives,
        "actual_current_stop_blocks_prepare_and_release": True, "actual_stop_sha256": owner.sha(original_stop),
        "new_model_calls": 0, "new_original_grader_calls": 0, "new_vm_calls": 0,
        "accept_executed": False, "release_executed": False, "pipeline_executed": False,
        "scope": "Actual pending35 blocks;actual prospective sources and unchanged plan fields verified;financial negatives use explicitly private files deleted after test. Existing reviewed continuation order reused,not claimed end-to-end executed."}
    owner.create("continuation-qualification.json", owner.encoded(result))
    print(json.dumps({"status": result["status"], "negative_cases": len(negatives), "source_bindings": result["source_bindings"],
        "qualification_sha256": owner.sha(FOLDER / "continuation-qualification.json")}))


if __name__ == "__main__":
    main()
