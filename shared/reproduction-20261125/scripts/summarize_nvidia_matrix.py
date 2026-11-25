import argparse
import csv
import hashlib
import importlib.util
import json
from collections import Counter
from pathlib import Path
from statistics import median

from unidiff import PatchSet

from course_eval.candidate_io import protected_path, test_configuration
from scripts import run_nvidia_mechanism_comparison as default_coordinator
from scripts.run_nvidia_mechanism_comparison import digest, read_json, trial_directory
from scripts.summarize_performance_comparison import dsh_tool_metrics
from course_eval.nvidia_free import audit_nvidia_events
from course_eval.summarize import grader_seconds, run_metrics


def cohort_operations(root, plan):
    if "coordinator" not in plan:
        return default_coordinator
    path = root / plan["coordinator"]
    if plan["execution_files_sha256"].get(plan["coordinator"]) != digest(path):
        raise ValueError("The declared cohort reader is not bound to its exact source")
    specification = importlib.util.spec_from_file_location("frozen_nvidia_cohort", path)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def aggregate(rows, expected):
    return {
        "completed": len(rows), "required": expected,
        "passed": sum(row["passed"] for row in rows),
        "failed": sum(not row["passed"] for row in rows),
        "all_original_scores_passed": expected > 0 and len(rows) == expected and all(row["passed"] for row in rows),
        "actual_requests": sum(row["actual_requests"] for row in rows),
        "verified_nonbilled_service_calls": sum(row["verified_nonbilled_service_calls"] for row in rows),
        "actual_monetary_receipt_calls": sum(row["actual_monetary_receipt_calls"] for row in rows),
        "reported_monetary_cost": (sum(row["reported_monetary_cost"] for row in rows)
            if rows and all(row["reported_monetary_cost"] is not None for row in rows) else None),
        "input_tokens": sum(row["input_tokens"] for row in rows),
        "output_tokens": sum(row["output_tokens"] for row in rows),
        "tool_calls": sum(row["tool_calls"] for row in rows),
        "model_function_call_proposals": sum(row["model_function_call_proposals"] for row in rows),
        "sum_wall_seconds": sum(row["wall_seconds"] for row in rows),
        "median_wall_seconds": median(row["wall_seconds"] for row in rows) if rows else None,
        "final_control_states": dict(Counter(row["final_control_state"] for row in rows)),
        "known_protected_changes": [row["task"] for row in rows if row["final_protected_unchanged"] is False],
        "original_passes_with_known_protected_changes": [row["task"] for row in rows
            if row["passed"] and row["final_protected_unchanged"] is False],
        "patches_changing_existing_protected_files": [row["task"] for row in rows
            if row.get("patch_changed_existing_protected_files")],
        "patches_changing_test_configuration": [row["task"] for row in rows
            if row.get("patch_changed_test_configurations")],
        "controller_protection_not_recorded": sum(row["final_protected_unchanged"] is None for row in rows),
    }


def repository_patch_boundary(directory):
    path = directory / "candidate.patch"
    result = {"candidate_patch_sha256": None, "patch_changed_existing_protected_files": [],
              "patch_changed_test_configurations": [], "patch_added_test_files": [],
              "patch_removed_existing_protected_lines": 0}
    if not path.exists():
        return result
    result["candidate_patch_sha256"] = digest(path)
    patch = PatchSet.from_filename(str(path), encoding="utf-8")
    for changed in patch:
        source = changed.source_file.removeprefix("a/")
        target = changed.target_file.removeprefix("b/")
        if not changed.is_added_file and (protected_path(source) or protected_path(target)):
            result["patch_changed_existing_protected_files"].append(changed.path)
            result["patch_removed_existing_protected_lines"] += changed.removed
        if any(test_configuration(name) for name in (source, target)):
            result["patch_changed_test_configurations"].append(changed.path)
        if changed.is_added_file and protected_path(target):
            result["patch_added_test_files"].append(changed.path)
    return result


def paired(rows, left_arm, right_arm, task_order):
    left = {row["task"]: row for row in rows if row["arm"] == left_arm}
    right = {row["task"]: row for row in rows if row["arm"] == right_arm}
    common = [task for task in task_order if task in left and task in right]
    return {"left": left_arm, "right": right_arm, "completed_pairs": len(common),
        "required_pairs": len(task_order),
        "both_passed": [task for task in common if left[task]["passed"] and right[task]["passed"]],
        "left_only_passed": [task for task in common if left[task]["passed"] and not right[task]["passed"]],
        "right_only_passed": [task for task in common if not left[task]["passed"] and right[task]["passed"]],
        "both_failed": [task for task in common if not left[task]["passed"] and not right[task]["passed"]],
        "left_metrics_on_paired_tasks": aggregate([left[task] for task in common], len(task_order)),
        "right_metrics_on_paired_tasks": aggregate([right[task] for task in common], len(task_order))}


def inspect_events(directory, plan, root, seen_generations):
    traces = list(directory.rglob("model.jsonl"))
    if not traces:
        score = read_json(directory / "result.json")
        evidence = read_json(directory / "nvidia-free-evidence.json")
        if (score["scoreable"] is not False or score["passed"] is not None
                or evidence["actual_requests"] != 0 or evidence["verified_nonbilled_service_calls"] != 0
                or evidence["unverified_requests"]):
            raise ValueError("A missing trace is permitted only for an explicitly recorded zero-request setup failure")
        events = []
    else:
        trace, = traces
        events = [json.loads(line) for line in trace.read_text().splitlines()]
    billing = audit_nvidia_events(events, root / plan["contract"], plan["model"],
                                  plan["limits"]["max_output_tokens"])
    if not traces and billing != evidence:
        raise ValueError("The recorded zero-request financial evidence differs from the actual contract audit")
    for event in events:
        if event["event"] != "billing_verified":
            continue
        generation = event["generation_id"]
        if generation in seen_generations:
            raise ValueError("Two separate matrix attempts share an actual generation identity")
        seen_generations.add(generation)
    return billing | {"model_function_call_proposals": sum(
        len(choice["message"].get("tool_calls") or []) for event in events if event["event"] == "response"
        for choice in event["payload"]["choices"])}


def summarize(root, plan_path, *, state_path=None):
    plan = read_json(plan_path)
    coordinator = cohort_operations(root, plan)
    coordinator.verify_frozen(root, plan)
    read_completed_result = coordinator.completed_result
    if plan["comparison_kind"] != "complete75_matrix":
        raise ValueError("This reader requires the declared four-arm 75-task NVIDIA matrix")
    manifest = read_json(root / plan["manifest"])
    tasks = {task["id"]: task for task in manifest["selected"]}
    if len(tasks) != 75 or Counter(task["benchmark"] for task in tasks.values()) != {
            "aider": 25, "swe": 25, "terminal": 25}:
        raise ValueError("The original three-stratum 75-task union changed")
    queue = root / plan["queue"]
    state_bytes = (state_path or queue / "state.json").read_bytes()
    state = json.loads(state_bytes)
    if state["plan_sha256"] != digest(plan_path):
        raise ValueError("The live snapshot belongs to a different matrix plan")
    scheduled = {(task, arm): (configuration, execution_plan)
        for task in plan["task_order"]
        for configuration, execution_plan, arm in coordinator.scheduled_trials(plan, task)}
    if len(scheduled) != plan["planned_executions"]:
        raise ValueError("The scheduled matrix has duplicate positions")
    rows, seen_positions, seen_generations = [], set(), set()
    for saved in state["results"]:
        position = saved["task"], saved["arm"]
        if position in seen_positions or position not in scheduled:
            raise ValueError("A completed position is duplicated or outside the frozen matrix")
        seen_positions.add(position)
        configuration, execution_plan = scheduled[position]
        directory = trial_directory(queue, position[0], configuration, execution_plan)
        actual = read_completed_result(root, execution_plan, tasks[position[0]], configuration, directory)
        if actual | {"arm": position[1]} != saved:
            raise ValueError("The saved position differs from its independently recomputed original record")
        actual.update(inspect_events(directory, plan, root, seen_generations))
        score = read_json(directory / "result.json")
        actual.update(arm=position[1], framework=execution_plan["framework"],
                      run_dir=str(directory.relative_to(root)),
                      origin_split=tasks[position[0]]["split"],
                      grader_seconds=grader_seconds(directory, score),
                      protocol_sha256=digest(directory.with_suffix(".protocol.json")),
                      sdk_tool_results=None, sdk_tool_errors=None, sdk_tool_unreturned=None)
        if execution_plan["framework"] == "dsh":
            actual.update(dsh_tool_metrics(directory))
        actual.update(repository_patch_boundary(directory))
        rows.append(actual)
    mechanical = []
    for key, recovery in plan.get("mechanical_recoveries", {}).items():
        source = root / recovery["original_result"]
        score = read_json(source)
        directory = source.parent
        billing = inspect_events(directory, plan, root, seen_generations)
        framework = read_json(directory / "trial.json")["framework"]
        metrics = run_metrics(directory)
        if framework == "dsh":
            metrics.update(dsh_tool_metrics(directory))
        mechanical.append({"position": key, "run_dir": str(directory.relative_to(root)),
            "framework": framework,
            "scoreable": score["scoreable"], "passed": score["passed"],
            "result_sha256": digest(source), "wall_seconds": score["wall_seconds"],
            "excluded_from_scored_denominator": True, **billing, **metrics})
    unscored, completed_not_indexed = [], []
    for position, (configuration, execution_plan) in scheduled.items():
        if position in seen_positions:
            continue
        directory = trial_directory(queue, position[0], configuration, execution_plan)
        result = directory / "result.json"
        if not result.exists():
            continue
        score = read_json(result)
        if score["scoreable"]:
            actual = read_completed_result(root, execution_plan, tasks[position[0]], configuration, directory)
            actual.update(inspect_events(directory, plan, root, seen_generations))
            actual.update(arm=position[1], framework=execution_plan["framework"],
                          run_dir=str(directory.relative_to(root)), indexed_in_live_state=False,
                          excluded_from_indexed_completion_count=True)
            if execution_plan["framework"] == "dsh":
                actual.update(dsh_tool_metrics(directory))
            completed_not_indexed.append(actual)
            continue
        if score["passed"] is not None:
            raise ValueError("An unscored attempt cannot have an invented pass/fail score")
        billing = inspect_events(directory, plan, root, seen_generations)
        metrics = run_metrics(directory)
        if execution_plan["framework"] == "dsh":
            metrics.update(dsh_tool_metrics(directory))
        unscored.append({"task": position[0], "arm": position[1],
            "framework": execution_plan["framework"], "configuration": configuration,
            "run_dir": str(directory.relative_to(root)), "scoreable": False, "passed": None,
            "result_sha256": digest(result), "wall_seconds": score["wall_seconds"],
            "excluded_from_scored_denominator": True,
            "all_request_usage_available": not billing["unverified_requests"],
            "tokens_are_known_response_subtotals": bool(billing["unverified_requests"]),
            **billing, **metrics})
    selection = []
    for attempt in plan.get("selection_attempts", []):
        source_plan = root / attempt["source_plan"]
        directory = root / attempt["run_dir"]
        if (digest(source_plan) != attempt["source_plan_sha256"]
                or digest(directory / "result.json") != attempt["original_result_sha256"]):
            raise ValueError("A retained scored selection experiment changed")
        old_plan = read_json(source_plan)
        old_coordinator = cohort_operations(root, old_plan)
        old_coordinator.verify_frozen(root, old_plan)
        execution_plan = old_plan | {key: attempt[key] for key in ("framework", "repetition")}
        expected_directory = old_coordinator.trial_directory(root / old_plan["queue"], attempt["task"],
                                                            attempt["configuration"], execution_plan)
        if expected_directory.resolve() != directory.resolve():
            raise ValueError("A retained selection run differs from its original position")
        actual = old_coordinator.completed_result(root, execution_plan, tasks[attempt["task"]],
                                                  attempt["configuration"], directory)
        actual.update(inspect_events(directory, old_plan, root, seen_generations))
        actual.update(framework=attempt["framework"], run_dir=str(directory.relative_to(root)),
                      scoreable=True, excluded_from_new_matrix_denominator=True,
                      reason=attempt["reason"])
        selection.append(actual)
    stop = read_json(root / "work/performance-stop-20261122.json")
    arms = {}
    for arm in plan["arms"]:
        arm_tasks = arm.get("tasks", plan["task_order"])
        selected = [row for row in rows if row["arm"] == arm["id"]]
        arms[arm["id"]] = aggregate(selected, len(arm_tasks)) | {
            "pending": [task for task in arm_tasks if (task, arm["id"]) not in seen_positions],
            "by_benchmark": {name: aggregate([row for row in selected if row["benchmark"] == name],
                sum(tasks[task]["benchmark"] == name for task in arm_tasks))
                for name in ("aider", "swe", "terminal")}}
    return {
        "format_version": 2, "stage": state["stage"], "model": plan["model"],
        "reasoning_effort": plan.get("actual_request_reasoning_profile", {}).get(
            "effective_mode", plan["reasoning_effort"]), "limits": plan["limits"],
        "reported_model": plan.get("reported_model", plan["model"]),
        "public_checkpoint_equivalence_verified": plan.get("public_checkpoint_equivalence_verified"),
        "actual_request_reasoning_profile": plan.get("actual_request_reasoning_profile"),
        "plan_sha256": digest(plan_path),
        "state_sha256": hashlib.sha256(state_bytes).hexdigest(),
        "analysis_sha256": digest(Path(__file__)), "new_model_calls_by_analysis": 0,
        "completed_executions": len(rows), "required_executions": len(scheduled),
        "complete_matrix": len(rows) == len(scheduled) and state["stage"] == "complete",
        "arms": arms,
        "main_vs_dsh": paired(rows, "main", "dsh", plan["task_order"]),
        "independent_repeat": paired(rows, plan.get("repeat_reference_arm", "main"), "repeat", plan["task_order"]),
        "control_ablation": paired(rows, "main", "control", plan["mechanism_task_order"]),
        "mechanical_attempts": mechanical,
        "unscored_attempts": unscored,
        "scored_selection_attempts": selection,
        "completed_not_yet_indexed": completed_not_indexed,
        "completed_and_mechanical_usage": {key: sum(row[key] for row in [*rows, *mechanical])
            for key in ("actual_requests", "verified_nonbilled_service_calls", "input_tokens", "output_tokens")},
        "all_recorded_attempt_usage": {key: sum(row[key] for row in [*rows, *mechanical, *unscored, *selection, *completed_not_indexed])
            for key in ("actual_requests", "verified_nonbilled_service_calls", "input_tokens", "output_tokens",
                        "usage_unreturned_requests")},
        "billing": {"active_stop": stop["active"],
            "accepted_historical_unknown_calls": stop.get("accepted_total_unknown_calls", stop["historical_unknown_calls"]),
            "inflight_excluded_from_completed_totals": True,
            "missing_nvidia_monetary_receipts_remain_null": True},
        "all_recorded_usage_complete": not any(row["unverified_requests"] for row in [*rows, *mechanical, *unscored, *selection, *completed_not_indexed]),
        "interpretation": [
            "All 75 tasks were previously exposed; these are not unseen tasks or a complete official benchmark.",
            "A complete original-score table still requires a separate instruction and source-boundary audit.",
            "Candidate patches are separately checked for edits to tracked test files and test configuration; adding a regression to an existing file still violates the course controller's stricter byte-preservation rule even when the independent original grader passes.",
            "Main versus DSH compares complete frameworks; it does not isolate one mechanism.",
            "The ten main scores also serve as the C0 side of the predeclared control ablation.",
            "tool_calls reads the main shell log or all official DSH tool/call events; it is not a matched action count.",
            "model_function_call_proposals counts returned model tool calls, including proposals that may not execute.",
            "Historical mechanical failures are separate from scored samples and retained in attempt usage.",
            "Started unscored attempts remain separate; missing response usage is unknown, and token sums cover only known responses.",
            "Predeclared scored selection experiments keep their real failures and usage outside the new matrix positions; they are not mechanical replacements.",
            "An existing completed score not yet visited by the live coordinator is audited separately and included in usage without inflating indexed completion.",
            "Usage covers this matrix and its declared recoveries, not all earlier development or qualification calls.",
        ],
        "rows": rows,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--state", type=Path)
    args = parser.parse_args()
    result = summarize(Path.cwd(), args.plan, state_path=args.state)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "summary.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    if result["rows"]:
        with (args.out / "trials.csv").open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(result["rows"][0]))
            writer.writeheader()
            writer.writerows(result["rows"])
    print(json.dumps({"completed": result["completed_executions"],
        "required": result["required_executions"], "stage": result["stage"],
        "arms": {name: {key: arm[key] for key in ("completed", "passed", "required", "actual_requests")}
                 for name, arm in result["arms"].items()}, "billing": result["billing"],
        "new_model_calls_by_analysis": 0}, ensure_ascii=False))


if __name__ == "__main__":
    main()
