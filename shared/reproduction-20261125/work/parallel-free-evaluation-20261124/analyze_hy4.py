import argparse
import csv
import importlib.util
import json
import statistics
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from scripts.export_performance_evidence import digest, inspect_run
from course_eval.codebuddy_free import verify_free_response
from course_eval.summarize import run_metrics
from scripts.summarize_performance_comparison import control_artifact_metrics


def read(path):
    return json.loads(path.read_text())


def coordinator(path, expected):
    if digest(path) != expected:
        raise ValueError("The actual coordinator differs from its frozen source")
    spec = importlib.util.spec_from_file_location("audit_" + path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def verify_resolved(task, template, queue):
    if task == template:
        return
    path = queue / "resolved-inputs" / (task["id"].replace("/", "-") + ".environment.json")
    probe = read(path)
    expected = json.loads(json.dumps(template))
    if (probe["native_python_probe"]["returncode"] != 127
            or expected.get("candidate_scope", {}).get("python") != "python3"
            or probe["resolved_python"] != "/opt/course-runtime/bin/python3"):
        raise ValueError("The resolved task changed outside its original interpreter admission rule")
    expected["candidate_scope"]["python"] = probe["resolved_python"]
    if task != expected:
        raise ValueError("An actual task differs from its frozen template")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=Path("work/parallel-free-evaluation-20261124/hy4-summary"))
    parser.add_argument("--main-plan", type=Path)
    parser.add_argument("--repeat-plan", type=Path)
    args = parser.parse_args()
    root, folder = Path.cwd(), Path(__file__).parent.resolve()
    plans = {"main": args.main_plan or folder / "ready-main-plan.json",
        "repeat": args.repeat_plan or folder / "ready-repeat-plan.json"}
    queues = {lane: root / read(path)["queue"] for lane, path in plans.items()}
    validations, modules = {}, {}
    for lane, plan_path in plans.items():
        plan = read(plan_path)
        code = root / plan["coordinator_path"]
        modules[lane] = coordinator(code, plan["coordinator_sha256"])
        completed = subprocess.run([sys.executable, str(code), "--plan", str(plan_path),
            "--queue-dir", str(queues[lane]), "--validate-only"], capture_output=True, text=True, check=True)
        validations[lane] = json.loads(completed.stdout)
    primary = read(plans["main"])
    manifest = plans["main"].resolve().parent / "tasks.json"
    if digest(manifest) != primary["tasks_sha256"]:
        raise ValueError("The analysis task manifest differs from its frozen plan")
    tasks = {row["id"]: row for row in read(manifest)["selected"]}
    if len(tasks) != 75 or Counter(row["benchmark"] for row in tasks.values()) != {"aider": 25, "swe": 25, "terminal": 25}:
        raise ValueError("The report requires all original75 tasks")
    snapshots = {lane: read(queue / "state.json") for lane, queue in queues.items()}
    groups = {"dsh": snapshots["main"]["baseline_results"],
        "main": snapshots["main"]["policy_results"], "repeat": snapshots["repeat"]["policy_results"]}
    discovered = {"main": [], "repeat": []}
    for lane in queues:
        plan = read(plans[lane])
        saved_tasks = {row["task"] for row in groups[lane]}
        for task_id in plan["task_order"]:
            if task_id in saved_tasks:
                continue
            configuration = plan["configuration_by_task"][task_id]
            directory = modules[lane].policy_directory(task_id, configuration, queues[lane], plan)
            score = directory / "result.json"
            if not score.exists() or read(score).get("scoreable") is not True:
                continue
            task, = read(queues[lane] / "resolved-inputs" / (task_id.replace("/", "-") + ".json"))["selected"]
            actual = modules[lane].policy_result(task, directory, configuration,
                modules[lane].recorded_runtime(directory, Path(plan["runtime_root"]), plan))
            groups[lane].append(actual)
            discovered[lane].append(task_id)
    rows, observed = [], set()
    for arm, records in groups.items():
        if len({row["task"] for row in records}) != len(records):
            raise ValueError("A report arm repeats an actual task")
        for saved in records:
            task_id, directory = saved["task"], Path(saved["run_dir"])
            framework = "dsh" if arm == "dsh" else "mini-swe"
            protocol = read(directory.with_suffix(".protocol.json"))
            if arm != "dsh":
                task, = read(queues[arm] / "resolved-inputs" / (task_id.replace("/", "-") + ".json"))["selected"]
                verify_resolved(task, tasks[task_id], queues[arm])
                plan = read(plans[arm])
                modules[arm].policy_result(task, directory, plan["configuration_by_task"][task_id],
                    modules[arm].recorded_runtime(directory, Path(plan["runtime_root"]), plan))
            metrics = inspect_run(directory, framework)
            if metrics["usage_missing_input_responses"] or metrics["usage_missing_output_responses"]:
                raise ValueError("A cost comparison cannot turn missing input/output usage into zero: " + str(directory))
            if any(metrics[key] != saved[key] for key in ("task", "passed", "wall_seconds", "actual_requests")):
                raise ValueError("The original score or individual receipt counts differ from the source snapshot")
            trace, = directory.rglob("model.jsonl")
            for line in trace.read_text().splitlines():
                event = json.loads(line)
                if event["event"] == "request":
                    session = event["native_session_id"]
                elif event["event"] == "billing_verified":
                    for message in event["fresh_model_message_ids"]:
                        identity = session, message
                        if identity in observed:
                            raise ValueError("An actual generation was reused across distinct original positions")
                        observed.add(identity)
            control = control_artifact_metrics(directory, framework, protocol["configuration"])
            qualified = metrics["passed"] and (not control["final_control_applicable"] or
                (control["final_protected_unchanged"] is True and control["final_valid_verification"] is True))
            rows.append({"arm": arm, "task": task_id, "benchmark": tasks[task_id]["benchmark"],
                "configuration": protocol["configuration"], "passed": metrics["passed"], "qualified_passed": qualified,
                "wall_seconds": metrics["wall_seconds"], "actual_requests": metrics["actual_requests"],
                "verified_zero_credit_requests": metrics["verified_zero_credit_requests"],
                "input_tokens": metrics["input_tokens"], "output_tokens": metrics["output_tokens"],
                "final_control_applicable": control["final_control_applicable"],
                "final_protected_unchanged": control["final_protected_unchanged"],
                "final_valid_verification": control["final_valid_verification"],
                "runtime_root": str((root / protocol["runtime_root"]).resolve().relative_to(root)),
                "run_dir": str(directory.relative_to(root)), "original_score_sha256": digest(directory / "result.json"),
                "protocol_sha256": digest(directory.with_suffix(".protocol.json")), "trace_sha256": digest(trace)})
    summaries = {}
    by_arm = {arm: {row["task"]: row for row in rows if row["arm"] == arm} for arm in groups}
    for arm, indexed in by_arm.items():
        actual = list(indexed.values())
        summaries[arm] = {"required": 75, "completed": len(actual), "passed": sum(row["passed"] for row in actual),
            "qualified_passed": sum(row["qualified_passed"] for row in actual),
            "pending_tasks": sorted(tasks.keys() - indexed.keys()),
            "actual_requests": sum(row["actual_requests"] for row in actual),
            "input_tokens": sum(row["input_tokens"] for row in actual), "output_tokens": sum(row["output_tokens"] for row in actual),
            "median_wall_seconds": statistics.median(row["wall_seconds"] for row in actual) if actual else None,
            "by_benchmark": {benchmark: {"required": 25, "completed": sum(row["benchmark"] == benchmark for row in actual),
                "passed": sum(row["benchmark"] == benchmark and row["passed"] for row in actual)}
                for benchmark in ("aider", "swe", "terminal")}}
    paired = tasks.keys() & by_arm["main"].keys() & by_arm["dsh"].keys()
    repeated = tasks.keys() & by_arm["main"].keys() & by_arm["repeat"].keys()
    comparison = {"matched": len(paired), "required": 75,
        "method_only_pass": sorted(task for task in paired if by_arm["main"][task]["passed"] and not by_arm["dsh"][task]["passed"]),
        "dsh_only_pass": sorted(task for task in paired if by_arm["dsh"][task]["passed"] and not by_arm["main"][task]["passed"]),
        "both_failed": sorted(task for task in paired if not by_arm["dsh"][task]["passed"] and not by_arm["main"][task]["passed"])}
    stop = read(root / "work/performance-stop-20261122.json")
    interruptions = []
    for lane, plan_path in plans.items():
        for task_id, recovery in read(plan_path).get("mechanical_policy_recoveries", {}).items():
            directory = Path(recovery["original_run"])
            outcome = read(directory / "result.json")
            logs = list(directory.rglob("model.jsonl"))
            if len(logs) > 1:
                raise ValueError("An interrupted logical position has multiple model traces")
            events = [json.loads(line) for line in logs[0].read_text().splitlines()] if logs else []
            requested = {event["request_id"] for event in events if event["event"] == "request"}
            verified = {event["request_id"] for event in events if event["event"] == "billing_verified"}
            returned = {event["request_id"] for event in events if event["event"] == "response"}
            if returned != verified or not verified <= requested:
                raise ValueError("Interrupted returned usage requires its own actual financial receipt")
            session = None
            for event in events:
                if event["event"] == "request":
                    session = event["native_session_id"]
                elif event["event"] == "response":
                    verify_free_response(event["payload"])
                elif event["event"] == "billing_verified":
                    if (event["credit"] != 0 or event["fresh_usage_records"] != 1
                            or len(event["fresh_model_message_ids"]) != 1):
                        raise ValueError("Interrupted known receipts must retain real zero credit and fresh identities")
                    identity = session, event["fresh_model_message_ids"][0]
                    if identity in observed:
                        raise ValueError("An interrupted generation was reused in another original position")
                    observed.add(identity)
            usage = run_metrics(directory)
            if usage["model_responses"] != len(returned):
                raise ValueError("The interruption's actual responses differ from its returned usage")
            interruptions.append({"arm": lane, "task": task_id,
                "run_dir": str(directory.relative_to(root)), "scoreable": outcome["scoreable"],
                "passed": outcome["passed"], "record_origin": outcome.get("record_origin", "original_runtime_record"),
                "result_sha256": digest(directory / "result.json"),
                "model_request_events": len(requested), "own_verified_receipts": len(verified),
                "unverified_request_ids": sorted(requested - verified),
                "actual_unverified_amount": None, "actual_unverified_usage": None,
                "known_returned_input_tokens": usage["input_tokens"] if not usage["usage_missing_input_responses"] else None,
                "known_returned_output_tokens": usage["output_tokens"] if not usage["usage_missing_output_responses"] else None,
                "known_returned_usage_excludes_unreturned_requests": True,
                "wall_seconds": outcome.get("wall_seconds"),
                "counted_in_core_original_scores": False,
                "trace_sha256": digest(logs[0]) if logs else None})
    unscored = []
    for arm, queue in queues.items():
        for trial_path in queue.glob("*/trial.json"):
            score = trial_path.with_name("result.json")
            outcome = read(score) if score.exists() else None
            if outcome is None or outcome.get("scoreable") is not True:
                unscored.append({"arm": arm, "run_dir": str(trial_path.parent.relative_to(root)),
                    "original_outcome": outcome, "state": "in_progress" if outcome is None else "ended_without_original_score",
                    "counted_as_original_failure": False})
    summary = {"observed_utc": datetime.now(timezone.utc).isoformat(), "groups": summaries,
        "source_manifest_path": str(manifest.relative_to(root)), "source_manifest_sha256": digest(manifest),
        "source_plan_paths": {lane: str(path.resolve().relative_to(root)) for lane, path in plans.items()},
        "source_plan_sha256": {lane: digest(path) for lane, path in plans.items()}, "frozen_validations": validations,
        "completed_original_files_ahead_of_parked_parent_snapshot": discovered,
        "paired_same75": comparison, "independent_repeat": {"matched": len(repeated), "required": 75,
            "both_pass": sum(by_arm["main"][task]["passed"] and by_arm["repeat"][task]["passed"] for task in repeated)},
        "complete_all225": all(group["completed"] == 75 for group in summaries.values()),
        "main_and_repeat_all75_qualified_pass": all(summaries[arm]["qualified_passed"] == 75 for arm in ("main", "repeat")),
        "distinct_actual_generations": sum(row["actual_requests"] for row in rows),
        "additional_known_interrupted_generations": sum(row["own_verified_receipts"] for row in interruptions),
        "new_model_calls_by_analysis": 0,
        "historical_unknown_calls_preserved": stop["accepted_total_unknown_calls"], "active_financial_stop": stop["active"],
        "analysis_sha256": digest(Path(__file__)), "rows": rows, "unscored_attempts": unscored,
        "mechanical_interruption_costs": interruptions,
        "additional_interrupted_request_events": sum(row["model_request_events"] for row in interruptions),
        "additional_unverified_request_events": sum(len(row["unverified_request_ids"]) for row in interruptions),
        "interpretation": "The same previously exposed75 tasks with unchanged original graders, model name and declared budgets. C0 disables automatic checks; public helpers, prompts and action interfaces form a combined policy. Historical source versions retain exact per-position bindings. A declared non-model scheduler revision prefers cached original images and preserves all required positions; service state is uncontrolled. This is not a full public leaderboard replication or an isolated controller causal effect."}
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    with (args.out / "trials.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps({"groups": summaries, "paired": comparison, "new_model_calls": 0}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
