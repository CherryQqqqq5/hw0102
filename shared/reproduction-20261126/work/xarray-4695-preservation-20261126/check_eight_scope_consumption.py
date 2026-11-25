import argparse
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import shutil


ROOT = Path.cwd().resolve()
FOLDER = Path(__file__).resolve().parent
BASE = ROOT / "work/parallel-free-evaluation-20261124"


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def check():
    owner = load(BASE / "join_scoped_revisions.py", "eight_scope_owner")
    consumer = load(BASE / "prepare_report_data.py", "eight_scope_consumer")
    summary_path = FOLDER / "consumer-qualification/joint-eight/summary.json"
    summary = owner.read(summary_path)
    identities = set()
    acceptance = consumer.incremental_sources(summary, ROOT, BASE, identities)
    core = owner.read(ROOT / acceptance["core_summary"])
    parents = {arm: owner.read(ROOT / name) for arm, name in core["source_plan_paths"].items()}
    tasks = {task["id"]: task for task in owner.read(ROOT / core["source_manifest_path"])["selected"]}
    checks = owner.read((ROOT / core["source_plan_paths"]["main"]).parent / "checks.json")
    plans = {key: owner.read(ROOT / value["path"]) for key, value in acceptance["revision_plans"].items()
        if key in owner.REVISION_TASKS}
    inherited = owner.validate_scope(ROOT, parents, tasks, checks, plans)
    assert len(core["rows"]) == 201 and len(inherited) == 67
    assert acceptance["required_inherited_positions"] == 134 and acceptance["required_new_positions"] == 16
    assert len(acceptance["new_revision_rows"]) == 12 and len(acceptance["previous_json_development_rows"]) == 5
    assert len(identities) == acceptance["all_listed_actual_requests"]
    assert summary["complete_all225"] is False and summary["main_and_repeat_all75_qualified_pass"] is False
    negatives = {}

    def rejects(name, call):
        try:
            call()
        except (ValueError, KeyError):
            negatives[name] = "rejected"
        else:
            raise AssertionError("Invalid evidence was accepted:" + name)

    rejects("old_seven_scopes_cannot_fill_eighth", lambda: owner.validate_scope(ROOT, parents, tasks, checks,
        {name: value for name, value in plans.items() if name != "loc_preservation"}))
    wrong = deepcopy(plans)
    wrong["loc_preservation"]["runtime_root"] = parents["main"]["runtime_root"]
    rejects("loc_cannot_claim_old_v18_has_new_submit_gate", lambda: owner.validate_scope(ROOT, parents, tasks, checks, wrong))
    wrong_budget = deepcopy(plans)
    wrong_budget["loc_preservation"]["limits"]["wall_seconds"] += 1
    rejects("loc_attempt_budget_changed", lambda: owner.validate_scope(ROOT, parents, tasks, checks, wrong_budget))
    wrong_registration = deepcopy(plans)
    wrong_registration["loc_preservation"]["unchanged_task_inputs"][next(iter(inherited))]["task_sha256"] = "0" * 64
    rejects("one_inherited_definition_changed", lambda: owner.validate_scope(ROOT, parents, tasks, checks, wrong_registration))
    task_id = plans["loc_preservation"]["task"]
    original = [row for row in core["rows"] if row["task"] == task_id and row["arm"] != "dsh"]
    assert len(original) == 2 and all(row["passed"] for row in original)
    assert sum(row["qualified_passed"] for row in original) == 1
    assert all(row in acceptance["displaced_original_rows"] and row not in summary["rows"] for row in original)
    for row in original:
        rejects("old_" + row["arm"] + "_raw_true_cannot_fill_new_loc_slot",
            lambda row=row: owner.validate_revision_membership(ROOT, [row], {"loc_preservation": plans["loc_preservation"]}))
    progress = acceptance["scope_progress"]["loc_preservation"]
    assert progress["completed"] == 0 and all(slot["passed"] is None and slot["qualified_passed"] is None
        and slot["status"] == "pending_original_score" for slot in progress["positions"])
    wrong_pending = deepcopy(summary)
    wrong_pending["incremental_acceptance"]["scope_progress"]["loc_preservation"]["positions"][0].update(passed=True)
    rejects("pending_loc_cannot_be_promoted_to_true", lambda: consumer.incremental_sources(wrong_pending, ROOT, BASE))
    wrong_complete = deepcopy(summary)
    wrong_complete["complete_all225"] = True
    rejects("partial201_cannot_be_complete225", lambda: consumer.incremental_sources(wrong_complete, ROOT, BASE))
    missing_cost = deepcopy(summary)
    missing_cost["incremental_acceptance"]["original_core_rows"].remove(original[1])
    rejects("old_protection_failure_cost_cannot_be_removed", lambda: consumer.incremental_sources(missing_cost, ROOT, BASE))
    counts = {arm: {"completed": 75} for arm in ("main", "repeat", "dsh")}
    assert owner.scoped_scores_complete(False, counts, [None] * 16) is False
    assert owner.scoped_scores_complete(True, counts, [None] * 14) is False
    assert owner.scoped_scores_complete(True, counts, [None] * 16) is True
    facts, sources = consumer.loc_preservation_case_observations(ROOT, acceptance)
    states = {row["variant"]: row for row in facts["engineering_variants"]}
    assert states["base"]["controller_state"] == "passed" and states["base"]["original_issue_example_passed"] is False
    assert states["recorded_bad_repeat"]["public_command_returncode"] == 0
    assert states["recorded_bad_repeat"]["submit_accepted"] is False
    assert all(states[name]["submit_accepted"] for name in ("recorded_good_main", "recorded_repeat_tests_restored"))
    assert all(row["passed"] is None for row in facts["fixed_model_sessions"])
    private = FOLDER / "consumer-qualification/private-observation-fixture"
    private.mkdir()
    try:
        for name in sources["files_sha256"]:
            target = private / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((ROOT / name).read_bytes())
        assert consumer.loc_preservation_case_observations(private, acceptance)[0] == facts
        target = private / "work/xarray-4695-preservation-20261126/qualification/recorded_bad_repeat/post-verification-submit.json"
        target.write_text(json.dumps({"submitted": True}))
        rejects("private_bad_submission_tamper", lambda: consumer.loc_preservation_case_observations(private, acceptance))
    finally:
        shutil.rmtree(private)
    old_check = load(BASE / "check_six_scope_membership.py", "existing_membership_regression")
    regression = old_check.check(owner, FOLDER / "consumer-qualification/existing-membership-regression.json")
    for name in ("mechanical_interruption_costs", "additional_unverified_request_events", "additional_interrupted_request_events"):
        assert summary[name] == core[name]
    return {"status": "PASS_ZERO_MODEL_EIGHT_SCOPE_CONSUMPTION", "core_positions": 201,
        "required_inherited_positions": 134, "required_new_positions": 16,
        "actual_revision_positions": 12, "earlier_json_positions": 5,
        "all_distinct_own_zero_ids": len(identities), "negative_cases": negatives,
        "existing_membership_regression": regression, "loc_case_observations": facts,
        "loc_case_source_sha256": sources["files_sha256"],
        "source_sha256": {str(path.relative_to(ROOT)): owner.digest(path) for path in
            (Path(__file__), BASE / "join_scoped_revisions.py", BASE / "prepare_report_data.py", summary_path)},
        "completion_fixture_scope": "Count-only completion inputs are not scored experiments. This real frozen snapshot contains201 original positions,12 revised model positions and5 earlier JSON model positions;new loc slots remain pending.",
        "new_model_calls": 0, "new_original_grader_calls": 0, "Docker_VM_calls": 0, "STOP_modified": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = check()
    with args.out.open("x") as stream:
        stream.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({key: result[key] for key in ("status", "core_positions", "required_new_positions", "all_distinct_own_zero_ids")}))


if __name__ == "__main__":
    main()
