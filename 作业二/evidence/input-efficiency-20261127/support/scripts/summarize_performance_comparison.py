import argparse
import csv
import hashlib
import json
import os
from collections import Counter
from pathlib import Path
from statistics import median

os.environ.setdefault("MSWEA_GLOBAL_CONFIG_DIR", str(Path.cwd() / "work/miniswe-config"))
os.environ.setdefault("MSWEA_SILENT_STARTUP", "1")

from course_eval.summarize import run_metrics
from scripts.run_performance_queue import audit_billing


def read_json(path):
    return json.loads(path.read_text())


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dsh_tool_metrics(directory):
    session, = directory.rglob("session.v4.jsonl")
    events = [json.loads(line) for line in session.read_text().splitlines()]
    calls = [row["data"]["callId"] for row in events if row["type"] == "tool/call"]
    results = [row["data"]["message"] for row in events if row["type"] == "tool/result"]
    completed = [row["toolCallId"] for row in results]
    if len(set(calls)) != len(calls) or len(set(completed)) != len(completed) or set(completed) - set(calls):
        raise ValueError("The actual SDK tool event identities are inconsistent")
    return {"tool_calls": len(calls), "sdk_tool_results": len(results),
            "sdk_tool_errors": sum(bool(row.get("isError")) for row in results),
            "sdk_tool_unreturned": len(set(calls) - set(completed))}


def control_artifact_metrics(directory, framework, configuration):
    applicable = framework == "mini-swe" and configuration in ("C0", "C1")
    values = {"final_control_applicable": applicable, "final_control_state": "not_applicable",
        "final_protected_unchanged": None, "final_valid_verification": None,
        "final_verification_sha256": None}
    if not applicable:
        return values
    paths = list(directory.rglob("final-verification.json"))
    if not paths:
        return values | {"final_control_state": "missing_record"}
    if len(paths) != 1:
        raise ValueError("The actual trial has multiple final control records")
    path, = paths
    final = read_json(path)
    if (type(final["protected_unchanged"]) is not bool or type(final["valid_verification"]) is not bool
            or (final["valid_verification"] and not final["protected_unchanged"])):
        raise ValueError("The final control record contains invalid Boolean states")
    events = [json.loads(line) for line in path.with_name("controller.jsonl").read_text().splitlines()]
    endings = [event for event in events if event["event"] == "final_artifact"]
    if not endings or any(endings[-1].get(key) != value for key, value in final.items()):
        raise ValueError("The final control file differs from the actual controller event")
    return values | {"final_control_state": "valid" if final["valid_verification"] else "invalid",
        "final_protected_unchanged": final["protected_unchanged"],
        "final_valid_verification": final["valid_verification"], "final_verification_sha256": sha256(path)}


def read_cohort(queue, framework, *, policy_plan=None, state_snapshot=None):
    manifest = read_json(policy_plan.parent / "tasks.json" if policy_plan else queue / "tasks.json")
    tasks = {row["id"]: row for row in manifest["selected"]}
    if len(tasks) != 75 or Counter(row["benchmark"] for row in tasks.values()) != {
            "aider": 25, "swe": 25, "terminal": 25}:
        raise ValueError("The comparison requires the original complete 75-task union")
    state = state_snapshot if state_snapshot is not None else read_json(queue / "state.json")
    rows = []
    seen = set()
    key = "policy_results" if policy_plan else "baseline_results" if state_snapshot is not None else "results"
    for saved in state[key]:
        task = saved["task"]
        if task in seen or task not in tasks:
            raise ValueError("A completed task is duplicated or outside the original manifest")
        seen.add(task)
        directory = Path(saved["run_dir"])
        trial = read_json(directory / "trial.json")
        expected_task = tasks[task]
        if policy_plan:
            resolved = queue / "resolved-inputs" / (task.replace("/", "-") + ".json")
            actual_task, = read_json(resolved)["selected"]
            expected_task = json.loads(json.dumps(expected_task))
            if actual_task != expected_task:
                probe = read_json(resolved.with_name(task.replace("/", "-") + ".environment.json"))
                if (probe["native_python_probe"]["returncode"] != 127
                        or expected_task.get("candidate_scope", {}).get("python") != "python3"
                        or probe["resolved_python"] != "/opt/course-runtime/bin/python3"):
                    raise ValueError("A resolved input differs from the frozen interpreter rule")
                expected_task["candidate_scope"]["python"] = probe["resolved_python"]
            if expected_task != actual_task:
                raise ValueError("The actual policy input changed outside its declared resolution rule")
        if (trial["task"] != expected_task or trial["model"] != "hy4flash-free"
                or trial.get("framework", "mini-swe") != framework):
            raise ValueError("The actual trial differs from the recorded comparison cohort")
        score_path = Path(saved.get("score_source", directory / "result.json"))
        score = read_json(score_path)
        if (score["task"] != task or not score["scoreable"] or type(score["passed"]) is not bool
                or score["passed"] != saved["passed"]):
            raise ValueError("The independent original task score differs from the saved summary")
        if "score_source" in saved and (score["new_model_calls"] != 0
                or score["independent_model_repeat"]
                or Path(score["source_model_run"]).resolve() != directory.resolve()):
            raise ValueError("An original candidate scoring recovery changed its declared scope")
        billing = audit_billing(directory, allow_context_resets=framework == "dsh")
        if any(billing[key] != saved[key] for key in billing):
            raise ValueError("Recomputed individual billing differs from the saved queue")
        metrics = run_metrics(directory)
        metrics.update(sdk_tool_results=None, sdk_tool_errors=None, sdk_tool_unreturned=None)
        if framework == "dsh":
            metrics.update(dsh_tool_metrics(directory))
        if metrics["model_calls"] != billing["actual_requests"]:
            raise ValueError("Actual request totals differ across independent readers")
        protocol_path = directory.with_suffix(".protocol.json")
        protocol = read_json(protocol_path)
        metrics.update(control_artifact_metrics(directory, framework, protocol["configuration"]))
        if policy_plan:
            plan = read_json(policy_plan)
            if (protocol["configuration"] != plan["configuration_by_task"][task]
                    or (Path.cwd() / protocol["runtime_root"]).resolve() != Path(plan["runtime_root"]).resolve()
                    or protocol["limits"] != plan["limits"] or not protocol["persistent_native_session"]
                    or billing["actual_requests"] != billing["fresh_native_usage_records"]):
                raise ValueError("The fixed policy protocol differs from its frozen plan")
        rows.append({"cohort": queue.name, "framework": framework, "task": task,
            "configuration": protocol["configuration"],
            "benchmark": tasks[task]["benchmark"], "origin_split": tasks[task]["split"],
            "passed": score["passed"], "wall_seconds": saved["wall_seconds"],
            "run_dir": str(directory), "score_source": str(score_path),
            "original_score_sha256": sha256(score_path), "runtime_root": protocol["runtime_root"],
            "protocol_sha256": sha256(protocol_path),
            "zero_model_score_recovery": "score_source" in saved,
            "maintenance_delay_included": saved.get("maintenance_delay_included", False),
            **billing, **metrics})
    return {"queue": str(queue), "status": state["status"], "completed": len(rows),
        "passed": sum(row["passed"] for row in rows),
        "final_control_states": dict(Counter(row["final_control_state"] for row in rows)),
        "original_passed_without_valid_control": [row["task"] for row in rows
            if row["passed"] and row["final_control_applicable"] and row["final_valid_verification"] is not True],
        "required_total": 75, "pending": sorted(set(tasks) - seen),
        "runtime_cohorts": dict(Counter(row["runtime_root"] for row in rows)),
        "by_benchmark": {name: {"completed": sum(row["benchmark"] == name for row in rows),
            "passed": sum(row["benchmark"] == name and row["passed"] for row in rows)}
            for name in ("aider", "swe", "terminal")},
        "actual_requests": sum(row["actual_requests"] for row in rows),
        "verified_zero_credit_requests": sum(row["verified_zero_credit_requests"] for row in rows),
        "fresh_native_usage_records": sum(row["fresh_native_usage_records"] for row in rows),
        "input_tokens": sum(row["input_tokens"] for row in rows),
        "output_tokens": sum(row["output_tokens"] for row in rows),
        "median_wall_seconds": median(row["wall_seconds"] for row in rows) if rows else None,
        "rows": rows}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--native-queue", type=Path, required=True)
    parser.add_argument("--dsh-queue", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--policy-plan", type=Path)
    parser.add_argument("--policy-queue", type=Path)
    args = parser.parse_args()
    if bool(args.policy_plan) != bool(args.policy_queue):
        parser.error("The fixed policy requires both its frozen plan and actual queue")
    matrix_state = None
    if args.policy_plan:
        plan = read_json(args.policy_plan)
        if Path(plan["baseline_queue"]).resolve() != args.dsh_queue.resolve():
            raise ValueError("The paired coordinator references a different public baseline")
        matrix_state = read_json(args.policy_queue / "state.json")
    native = read_cohort(args.native_queue.resolve(), "mini-swe")
    dsh = read_cohort(args.dsh_queue.resolve(), "dsh", state_snapshot=matrix_state)
    left = {row["task"]: row for row in native["rows"]}
    paired = [{"task": row["task"], "native_passed": left[row["task"]]["passed"],
               "dsh_passed": row["passed"]} for row in dsh["rows"] if row["task"] in left]
    stop = read_json(Path("work/performance-stop-20261122.json"))
    result = {"native_development_coverage": native, "dsh_fixed_configuration": dsh,
        "paired": {"completed": len(paired),
            "native_only_passed": [row["task"] for row in paired if row["native_passed"] and not row["dsh_passed"]],
            "dsh_only_passed": [row["task"] for row in paired if row["dsh_passed"] and not row["native_passed"]],
            "both_failed": [row["task"] for row in paired if not row["native_passed"] and not row["dsh_passed"]],
            "rows": paired},
        "billing": {"accepted_historical_unknown": stop.get("accepted_total_unknown_calls", stop["historical_unknown_calls"]),
            "active_stop": stop["active"], "completed_records_reaudited": True,
            "inflight_excluded_from_completed_totals": True},
        "new_model_calls_by_this_analysis": 0,
        "limits": ["Native development coverage spans explicitly different client/runtime versions.",
            "DSH images are enabled; the earlier native cohort did not share this setting.",
            "These observations do not isolate a causal framework effect or reproduce a public full benchmark.",
            "All 75 tasks were previously exposed; final independent repeats remain separate."]}
    policy = None
    if args.policy_plan:
        policy = read_cohort(args.policy_queue.resolve(), "mini-swe", policy_plan=args.policy_plan.resolve(),
                             state_snapshot=matrix_state)
        result["fixed_artifact_policy"] = policy
        baseline = {row["task"]: row for row in dsh["rows"]}
        matched = [{"task": row["task"], "public_dsh_passed": baseline[row["task"]]["passed"],
            "fixed_policy_passed": row["passed"]} for row in policy["rows"] if row["task"] in baseline]
        result["fixed_policy_vs_public_dsh"] = {"paired_tasks": len(matched),
            "policy_only_passed": [row["task"] for row in matched if row["fixed_policy_passed"] and not row["public_dsh_passed"]],
            "dsh_only_passed": [row["task"] for row in matched if row["public_dsh_passed"] and not row["fixed_policy_passed"]],
            "both_failed": [row["task"] for row in matched if not row["public_dsh_passed"] and not row["fixed_policy_passed"]],
            "rows": matched,
            "interpretation": "Previously exposed identical tasks, original scores, common model and declared budgets; controller, tools and qualified helpers differ as a complete policy. Incomplete pairs are excluded."}
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "summary.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    rows = [*native["rows"], *dsh["rows"], *(policy["rows"] if policy else [])]
    with (args.out / "trials.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps({"native": {key: native[key] for key in ("completed", "passed", "actual_requests")},
        "dsh": {key: dsh[key] for key in ("completed", "passed", "actual_requests")},
        "paired_count": len(paired),
        "fixed_policy": {key: policy[key] for key in ("completed", "passed", "actual_requests")} if policy else None,
        "billing": result["billing"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
