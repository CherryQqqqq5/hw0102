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
    module = load(BASE / "join_scoped_revisions.py", "seven_scope_owner")
    core = module.read(BASE / "hy4-snapshot-0122-20261126/summary.json")
    parents = {arm: module.read(ROOT / name) for arm, name in core["source_plan_paths"].items()}
    tasks = {task["id"]: task for task in module.read(ROOT / core["source_manifest_path"])["selected"]}
    checks = module.read((ROOT / core["source_plan_paths"]["main"]).parent / "checks.json")
    paths = {"json": "work/json-in-semantics-20261125/oracle-bool/ascii-transport/frozen/plan.json",
        "feal": "work/feal-linear-helper-20261125/readmission/plan.json",
        "xarray": "work/xarray-2905-semantics-20261125/frozen/plan.json",
        "pytest": "work/pytest-7205-semantics-20261125/frozen/plan.json",
        "preservation": "work/pytest-5631-preservation-20261125/frozen/plan.json",
        "relu": "work/hy4-submit-boundary-20261125/frozen-pair-r2/plan.json",
        "sklearn": "work/sklearn-25232-semantics-20261126/frozen/plan.json"}
    plans = {name: module.read(ROOT / path) for name, path in paths.items()}
    inherited = module.validate_scope(ROOT, parents, tasks, checks, plans)
    assert len(inherited) == 68
    consumer = load(BASE / "prepare_report_data.py", "seven_scope_consumer")
    negatives = {}

    def rejects(name, call):
        try:
            call()
        except (ValueError, KeyError):
            negatives[name] = "rejected"
        else:
            raise AssertionError("An actual wrong input was accepted:" + name)

    rejects("old_six_scope_set_not_seven", lambda: module.validate_scope(ROOT, parents, tasks, checks,
        {name: plan for name, plan in plans.items() if name != "sklearn"}))
    wrong = deepcopy(plans)
    wrong["sklearn"]["runtime_root"] = plans["relu"]["runtime_root"]
    rejects("nan_cannot_inherit_relu_v20_runtime", lambda: module.validate_scope(ROOT, parents, tasks, checks, wrong))
    wrong_budget = deepcopy(plans)
    wrong_budget["sklearn"]["limits"]["model_calls"] += 1
    rejects("nan_attempt_budget_changed", lambda: module.validate_scope(ROOT, parents, tasks, checks, wrong_budget))
    wrong_registration = deepcopy(plans)
    neighbor = next(iter(inherited))
    wrong_registration["sklearn"]["unchanged_task_inputs"][neighbor]["task_sha256"] = "0" * 64
    rejects("one_of68_inherited_definitions_changed", lambda: module.validate_scope(ROOT, parents, tasks, checks, wrong_registration))
    summary_path = FOLDER / "consumption-qualification/joint-seven/summary.json"
    summary = module.read(summary_path)
    identities = set()
    acceptance = consumer.incremental_sources(summary, ROOT, BASE, identities)
    assert acceptance["original_core_rows"] == core["rows"] and len(identities) == 3251
    assert len(acceptance["new_revision_rows"]) == 10 and len(acceptance["previous_json_development_rows"]) == 5
    assert summary["complete_all225"] is False and summary["main_and_repeat_all75_qualified_pass"] is False
    assert acceptance["all_listed_actual_requests"] == len(identities)
    for name in ("mechanical_interruption_costs", "additional_unverified_request_events", "additional_interrupted_request_events"):
        assert summary[name] == core[name]
    original = [row for row in core["rows"] if row["task"] == plans["sklearn"]["task"] and row["arm"] != "dsh"]
    assert len(original) == 2 and all(row["passed"] and row["qualified_passed"] for row in original)
    rejects("actual_old_qtrue_main_is_not_new_nan_contract", lambda: module.validate_revision_membership(ROOT, [original[0]], {"sklearn": plans["sklearn"]}))
    rejects("actual_old_qtrue_repeat_is_not_new_nan_contract", lambda: module.validate_revision_membership(ROOT, [original[1]], {"sklearn": plans["sklearn"]}))
    assert all(row not in summary["rows"] for row in original)
    assert all(row in acceptance["displaced_original_rows"] for row in original)
    progress = acceptance["scope_progress"]["sklearn"]
    assert progress["completed"] == 0 and all(slot["passed"] is None and slot["qualified_passed"] is None
        and slot["status"] == "pending_original_score" for slot in progress["positions"])
    wrong_pending = deepcopy(summary)
    wrong_pending["incremental_acceptance"]["scope_progress"]["sklearn"]["positions"][0].update(passed=True, qualified_passed=True)
    rejects("pending_nan_cannot_be_promoted_to_true", lambda: consumer.incremental_sources(wrong_pending, ROOT, BASE))
    wrong_complete = deepcopy(summary)
    wrong_complete["complete_all225"] = True
    rejects("partial_original177_cannot_be_complete225", lambda: consumer.incremental_sources(wrong_complete, ROOT, BASE))
    missing_cost = deepcopy(summary)
    missing_cost["incremental_acceptance"]["original_core_rows"].remove(original[0])
    rejects("displaced_original_cost_cannot_be_removed", lambda: consumer.incremental_sources(missing_cost, ROOT, BASE))
    counts = {arm: {"completed": 75} for arm in ("main", "repeat", "dsh")}
    assert module.scoped_scores_complete(False, counts, [None] * 14) is False
    assert module.scoped_scores_complete(True, counts, [None] * 12) is False
    assert module.scoped_scores_complete(True, counts, [None] * 14) is True
    pending_review = consumer.nan_completed_review_or_pending(ROOT, acceptance)
    assert pending_review["status"] == "pending" and pending_review["review_consumed"] is False
    rejects("complete_nan_mechanism_requires_real_sessions_and_review",
        lambda: consumer.nan_completed_review_or_pending(ROOT, acceptance, require_complete=True))
    facts, observations = consumer.nan_contract_case_observations(ROOT, acceptance)
    assert {row["variant"]: row["public_passed"] for row in facts["engineering_variants"]} == {
        "base": 1, "actual_main": 8, "actual_repeat": 9, "public_reference": 12}
    assert len(facts["numerical_negative_controls"]) == 4
    assert facts["separate_engineering_original_grade"]["original_grader_calls"] == 1
    assert all(row["passed"] is None for row in facts["fixed_model_sessions"])
    engineering_row = deepcopy(original[0])
    engineering_row["run_dir"] = "work/sklearn-25232-semantics-20261126/qualification/public_reference"
    rejects("engineering_reference_is_not_a_model_score",
        lambda: module.validate_revision_membership(ROOT, [engineering_row], {"sklearn": plans["sklearn"]}))
    private = FOLDER / "consumption-qualification/private-observation-fixture"
    private.mkdir()
    try:
        for name in observations["files_sha256"]:
            target = private / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((ROOT / name).read_bytes())
        consumer.nan_contract_case_observations(private, acceptance)
        target = private / "work/sklearn-25232-semantics-20261126/qualification/result.json"
        modified = module.read(target)
        modified["separate_engineering_original_grade"]["passed"] = False
        target.write_text(json.dumps(modified))
        rejects("private_engineering_outcome_tamper", lambda: consumer.nan_contract_case_observations(private, acceptance))
    finally:
        shutil.rmtree(private)
    old_check = load(BASE / "check_six_scope_membership.py", "existing_membership_regression")
    original_membership = old_check.check(module, FOLDER / "consumption-qualification/existing-membership-regression.json")
    return {"status": "PASS_ZERO_MODEL_SEVEN_SCOPE_CONSUMPTION", "original_snapshot_rows": len(core["rows"]),
        "inherited_task_definitions": len(inherited), "required_inherited_positions": 136, "required_new_positions": 14,
        "actual_revision_positions": len(acceptance["new_revision_rows"]),
        "actual_old_json_development_positions": len(acceptance["previous_json_development_rows"]),
        "all_distinct_own_zero_ids": len(identities), "original_raw_true": sum(row["passed"] for row in core["rows"]),
        "original_raw_false": sum(not row["passed"] for row in core["rows"]),
        "pending_nan_positions": progress, "nan_contract_case_observations": facts,
        "nan_contract_source_sha256": observations["files_sha256"], "negative_cases": negatives,
        "existing_membership_regression": original_membership,
        "completion_fixture_scope": "Pure count-only inputs exercise the completion gate;they are not scored experiments. Actual snapshot remains177 original rows plus10 revisions and5 old JSON development rows.",
        "source_versions": {"join_preimage": {"path": str((FOLDER / "prior-six-scope-join.py.txt").relative_to(ROOT)),
            "sha256": module.digest(FOLDER / "prior-six-scope-join.py.txt")},
            "consumer_preimage": {"path": str((FOLDER / "consumption-qualification/prepare_report_data.before-seven.py.txt").relative_to(ROOT)),
            "sha256": module.digest(FOLDER / "consumption-qualification/prepare_report_data.before-seven.py.txt")}},
        "source_sha256": {str(path.relative_to(ROOT)): module.digest(path) for path in
            [Path(__file__), BASE / "join_scoped_revisions.py", BASE / "prepare_report_data.py",
             BASE / "check_six_scope_membership.py", summary_path, BASE / "hy4-snapshot-0122-20261126/summary.json"]
             + [ROOT / path for path in paths.values()]},
        "new_model_calls": 0, "new_original_grader_calls": 0, "Docker_VM_calls": 0, "STOP_modified": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = check()
    except Exception as error:
        result = {"status": "FAILED_ZERO_MODEL_CONSUMPTION_CHECK", "error_type": type(error).__name__,
            "error": str(error), "new_model_calls": 0, "new_original_grader_calls": 0, "Docker_VM_calls": 0}
        with args.out.open("x") as stream:
            stream.write(json.dumps(result, indent=2) + "\n")
        raise
    with args.out.open("x") as stream:
        stream.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({key: result[key] for key in ("status", "inherited_task_definitions", "required_new_positions")}))


if __name__ == "__main__":
    main()
