import argparse
import ast
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import shutil
import sys


ROOT = Path.cwd().resolve()
BASE = Path(__file__).resolve().parent


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def check(module, output):
    membership = module.validate_revision_membership
    plan = module.read(ROOT / "work/json-in-semantics-20261125/oracle-bool/ascii-transport/frozen/plan.json")
    task, = module.read(ROOT / plan["manifest"])["selected"]
    rows, identities, counts = [], set(), {}
    for arm, label in zip(("main", "repeat"), plan["prospective_trials"], strict=True):
        directory = ROOT / plan["queue"] / (task["id"] + "-C0-" + label)
        rows.append(module.actual_row(ROOT, directory, arm, task, identities, counts))
    membership(ROOT, rows, {"json": plan})
    negatives = {}
    def rejects(name, call):
        try:
            call()
        except (ValueError, KeyError):
            negatives[name] = "rejected"
        else:
            raise AssertionError(name)
    wrong = deepcopy(rows)
    wrong[0]["arm"] = "repeat"
    rejects("actual_json_wrong_arm", lambda: membership(ROOT, wrong, {"json": plan}))
    rejects("duplicate_fixed_slot", lambda: membership(ROOT, [rows[0], rows[0]], {"json": plan}))
    wrong_plan = deepcopy(plan)
    wrong_plan["prospective_trials"][0] += "-not-the-frozen-label"
    rejects("actual_json_wrong_label", lambda: membership(ROOT, rows, {"json": wrong_plan}))
    historical_plan = module.read(ROOT / "work/json-in-semantics-20261125/expanded/frozen/plan.json")
    historical = ROOT / historical_plan["queue"] / (task["id"] + "-C0-" + historical_plan["prospective_trials"][0])
    assert (historical / "result.json").exists()
    wrong = deepcopy(rows[0])
    wrong["run_dir"] = str(historical.relative_to(ROOT))
    rejects("real_historical_same_task_is_not_new_revision", lambda: membership(ROOT, [wrong], {"json": plan}))
    dev_paths = {"development_json_types": "work/json-in-semantics-20261125/frozen/plan.json",
        "development_json_contract": "work/json-in-semantics-20261125/expanded/frozen/plan.json",
        "development_json_unicode_transport": "work/json-in-semantics-20261125/oracle-bool/frozen/plan.json"}
    dev_plans = {name: module.read(ROOT / path) for name, path in dev_paths.items()}
    dev_rows = []
    for name, legacy in dev_plans.items():
        for arm, label in zip(("main", "repeat"), legacy["prospective_trials"], strict=True):
            directory = ROOT / legacy["queue"] / (legacy["task"] + "-C0-" + label)
            if (directory / "result.json").exists() and module.read(directory / "result.json").get("scoreable") is True:
                dev_rows.append({"run_dir": str(directory.relative_to(ROOT)), "task": legacy["task"], "arm": arm})
    membership(ROOT, dev_rows, dev_plans)
    rejects("final_json_rows_are_not_development_rows", lambda: membership(ROOT, [rows[0]], dev_plans))
    private = output.parent / "private-membership-fixture"
    private.mkdir()
    manifest = private / plan["manifest"]
    manifest.parent.mkdir(parents=True)
    manifest.write_bytes((ROOT / plan["manifest"]).read_bytes())
    directory = private / rows[0]["run_dir"]
    directory.mkdir(parents=True)
    for name in ("trial.json", "result.json"):
        (directory / name).write_bytes((ROOT / rows[0]["run_dir"] / name).read_bytes())
    protocol = directory.with_suffix(".protocol.json")
    original_protocol = (ROOT / rows[0]["run_dir"]).with_suffix(".protocol.json").read_bytes()
    protocol.write_bytes(original_protocol)
    membership(private, [rows[0]], {"json": plan})
    value = json.loads(original_protocol)
    value["runtime_root"] = "work/not-the-admitted-runtime"
    protocol.write_text(json.dumps(value))
    rejects("private_copy_wrong_actual_protocol", lambda: membership(private, [rows[0]], {"json": plan}))
    protocol.write_bytes(original_protocol)
    trial = directory / "trial.json"
    original_trial = trial.read_bytes()
    value = json.loads(original_trial)
    value["task"]["id"] += "-explicit-private-negative"
    trial.write_text(json.dumps(value))
    rejects("private_copy_wrong_actual_task", lambda: membership(private, [rows[0]], {"json": plan}))
    trial.write_bytes(original_trial)
    result = directory / "result.json"
    value = json.loads(result.read_bytes())
    value.update(scoreable=False, passed=None)
    result.write_text(json.dumps(value))
    rejects("private_copy_unscored_cannot_be_revision", lambda: membership(private, [rows[0]], {"json": plan}))
    shutil.rmtree(private)
    old_rows = []
    source_tasks = {item["id"]: item for item in module.read(ROOT / "work/free-recovery34-20261125/hy4-plans/tasks.json")["selected"]}
    for task_id in ("model-extraction-relu-logits", "pytest-dev__pytest-5631"):
        directory = ROOT / "work/vmshare/performance75-hy4-sql-layout-v18-main-20261125" / (task_id + "-C0-r1")
        row = module.actual_row(ROOT, directory, "main", source_tasks[task_id], set(), {})
        assert row["passed"] is True and row["qualified_passed"] is False
        old_rows.append({key: row[key] for key in ("task", "passed", "qualified_passed", "final_valid_verification", "final_protected_unchanged", "actual_requests", "original_score_sha256", "protocol_sha256", "trace_sha256")})
    interrupted = ROOT / "work/vmshare/performance75-hy4-sql-layout-v18-main-20261125/llm-inference-batching-scheduler-C0-r1"
    rejects("actual_unscored_scheduler_is_not_scored", lambda: module.actual_row(ROOT, interrupted, "main", source_tasks["llm-inference-batching-scheduler"], set(), {}))
    tree = ast.parse((BASE / "prepare_report_data.py").read_text())
    owner, = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "incremental_sources"]
    calls = [node for node in ast.walk(owner) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        and node.func.attr == "validate_revision_membership"]
    assert len(calls) == 2
    return {"status": "PASS_ZERO_MODEL_EXACT_REVISION_MEMBERSHIP", "actual_final_json_positions": len(rows),
        "actual_final_json_own_zero_receipts": sum(row["verified_zero_credit_requests"] for row in rows), "actual_final_json_unique_ids": len(identities),
        "actual_previous_json_development_positions": len(dev_rows), "real_historical_path_rejected": str(historical.relative_to(ROOT)),
        "negative_cases": negatives, "old_raw_true_but_unqualified_preserved": old_rows,
        "consumer_checks_both_new_and_development_rows": True,
        "private_fixture_scope": "Copies of actual closed JSON metadata only;original run files were never altered. No new ReLU model or session was opened.",
        "source_sha256": {str(path.relative_to(ROOT)): module.digest(path) for path in (Path(__file__), BASE / "join_scoped_revisions.py", BASE / "prepare_report_data.py")},
        "new_model_calls": 0, "new_original_grader_calls": 0, "Docker_VM_calls": 0, "STOP_modified": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    module = load(BASE / "join_scoped_revisions.py", "actual_membership_owner")
    try:
        result = check(module, args.out)
    except Exception as error:
        result = {"status": "FAILED_ZERO_MODEL_CHECK", "error_type": type(error).__name__, "error": str(error),
            "join_source_sha256": module.digest(BASE / "join_scoped_revisions.py"), "new_model_calls": 0}
        with args.out.open("x") as stream:
            stream.write(json.dumps(result, indent=2) + "\n")
        raise
    with args.out.open("x") as stream:
        stream.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({key: result[key] for key in ("status", "actual_final_json_positions", "actual_final_json_own_zero_receipts", "actual_previous_json_development_positions")}))


if __name__ == "__main__":
    main()
