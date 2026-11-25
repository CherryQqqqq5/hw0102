import copy
import importlib.util
import json
from pathlib import Path
import sys


ROOT = Path.cwd()
BASE = Path(__file__).resolve().parent


def load(name):
    spec = importlib.util.spec_from_file_location(name, BASE / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    def audit(event, arguments):
        if event in {"socket.connect", "subprocess.Popen", "os.system"}:
            raise PermissionError("This offline qualification cannot make network or subprocess calls")

    sys.addaudithook(audit)
    helpers = load("export_nvidia_v28")
    history = load("export_nvidia_history")
    reports = load("prepare_report_data")
    snapshot_path = BASE / "nvidia-v33-consumer-qualification/summary.json"
    snapshot = helpers.read(snapshot_path)
    plan = helpers.read(ROOT / snapshot["plan_path"])
    parent = helpers.read(ROOT / "work/nvidia75-v27-20261125/plan.json")
    tasks = {task["id"]: task for task in helpers.read(ROOT / plan["manifest"])["selected"]}
    positions = helpers.positions(plan, parent, tasks, helpers.V33_SHA, "plan-v33.json")
    rows = [json.loads(line) for line in (ROOT / snapshot["trials_path"]).read_text().splitlines()]
    assert len(positions) == len(rows) == 225
    for expected, actual in zip(positions, rows, strict=True):
        assert expected["source_relative"] == actual["run_dir"]
        assert all(expected[key] == actual[key] for key in (
            "lane", "task", "actual_source_plan_sha256", "transport_stratum"))
    assert len(history.rows_from(snapshot)) == 19
    rejected = []

    def reject(label, operation):
        try:
            operation()
        except ValueError:
            rejected.append(label)
        else:
            raise AssertionError("Accepted corrupted actual metadata: " + label)

    for label, field, value in (
            ("unknown32_amount_filled_zero", "unknown_actual_amount", 0),
            ("unknown32_usage_filled_zero", "unknown_actual_usage", {}),
            ("unknown32_gap_deleted", "accepted_unknown_requests", []),
            ("unknown32_semantic_false_invented", "passed", False),
            ("unknown32_ordinal_removed", "historical_unknown_ordinal", None)):
        changed = copy.deepcopy(snapshot)
        unknown = next(row for row in changed["retained_unscored_v32_xarray"]
            if row.get("historical_unknown_ordinal") == 32)
        unknown[field] = value
        reject(label, lambda: history.rows_from(changed))
    changed = copy.deepcopy(snapshot)
    changed["retained_unscored_v32_xarray"].pop()
    reject("blocked_zero_request_attempt_omitted", lambda: history.rows_from(changed))
    changed_plan = copy.deepcopy(plan)
    changed_plan["lanes"]["main"]["tasks"].reverse()
    reject("public_task_order_changed", lambda: helpers.positions(
        changed_plan, parent, tasks, helpers.V33_SHA, "plan-v33.json"))
    portable = BASE / "nvidia-v32-partial-6inherited-20261125"
    previous = helpers.verify(portable, False)
    assert previous["unique_physical_runs"] == 6 and previous["actual_requests"] == 110
    reject("partial_portable_bundle_declared_complete", lambda: helpers.verify(portable, True))
    report = reports.nvidia_report_sources(snapshot_path, ROOT, tasks)
    assert report["complete_all225"] is False
    assert report["explicit_retained_unknown_ordinals"] == [26, 27, 28, 29, 30, 31, 32]
    assert len(report["retained_unscored_v32_xarray"]) == 3
    assert sum(group["completed"] for group in report["groups"].values()) == 7
    assert sum(group["passed"] for group in report["groups"].values()) == 5
    result = {"status": "PASS_OFFLINE_SOURCE_CONSUMPTION_NOT_COMPLETE225",
        "summary": str(snapshot_path.relative_to(ROOT)), "summary_sha256": helpers.digest(snapshot_path),
        "source_sha256": {str(path.relative_to(ROOT)): helpers.digest(path) for path in (
            BASE / "analyze_nvidia_v28.py", BASE / "export_nvidia_v28.py",
            BASE / "export_nvidia_history.py", BASE / "prepare_report_data.py", Path(__file__).resolve())},
        "actual_matrix_positions": 225, "closed_original_positions": 7, "original_true": 5,
        "original_false": 2, "complete_matrix_policy_proofs": 135,
        "all_consumed_distinct_complete_policy_ids": snapshot["identity_audit"]["distinct_consumed_generation_ids"],
        "retained_attempts": 19, "retained_unknown_ordinals": report["explicit_retained_unknown_ordinals"],
        "negative_cases_rejected": rejected, "prior_portable_validation": previous,
        "new_model_calls": 0, "new_original_grader_calls": 0, "network_calls": 0,
        "original_or_stop_mutations": 0,
        "scope": "Actual closed source consumption, metadata rejection and existing portable regression. No new v33 portable export was generated or claimed verified."}
    output = BASE / "nvidia-v33-consumer-qualification/check-result.json"
    if output.exists():
        raise FileExistsError("Retain the actual qualification result; do not overwrite it")
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({key: result[key] for key in (
        "status", "closed_original_positions", "all_consumed_distinct_complete_policy_ids",
        "negative_cases_rejected", "new_model_calls")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
