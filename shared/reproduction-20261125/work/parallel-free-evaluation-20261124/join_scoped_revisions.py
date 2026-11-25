import argparse
import ast
import copy
import csv
import hashlib
import importlib.util
import json
import statistics
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from scripts.export_performance_evidence import digest, inspect_run
from scripts.summarize_performance_comparison import control_artifact_metrics


def read(path):
    return json.loads(path.read_text())


def object_sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_plan(root, path):
    plan = read(path)
    for name, expected in plan["all_files_sha256"].items():
        if digest(root / name) != expected:
            raise ValueError("A prospective revision dependency changed: " + name)
    return plan


def validate_scope(root, parents, tasks, checks, revisions):
    json_plan, feal_plan = revisions["json"], revisions["feal"]
    changed = {plan["task"] for plan in revisions.values()}
    if changed != {"django__django-13346", "feal-linear-cryptanalysis", "pydata__xarray-2905", "pytest-dev__pytest-7205", "pytest-dev__pytest-5631"}:
        raise ValueError("The joint scope must contain exactly the five declared task revisions")
    core_runtime = Path(parents["main"]["runtime_root"])
    feal_runtime = root / feal_plan["runtime_root"]
    if (root / json_plan["runtime_root"]).resolve() != core_runtime.resolve():
        raise ValueError("The JSON revision changed the core model runtime")
    if (root / revisions["xarray"]["runtime_root"]).resolve() != core_runtime.resolve():
        raise ValueError("The xarray contract revision changed the core model runtime")
    if (root / revisions["pytest"]["runtime_root"]).resolve() != core_runtime.resolve():
        raise ValueError("The pytest contract revision changed the core model runtime")
    if (root / revisions["preservation"]["runtime_root"]).resolve() != core_runtime.resolve():
        raise ValueError("The preservation guidance revision changed the core model runtime")
    old_files = {str(p.relative_to(core_runtime)): digest(p) for p in core_runtime.rglob("*")
        if p.is_file() and "__pycache__" not in p.parts}
    new_files = {str(p.relative_to(feal_runtime)): digest(p) for p in feal_runtime.rglob("*")
        if p.is_file() and "__pycache__" not in p.parts}
    if (set(new_files) - set(old_files) != {"course_eval/feal_known_pairs.c", "course_eval/feal_public_check.py"}
            or set(old_files) - set(new_files)
            or [name for name in old_files if old_files[name] != new_files[name]] != ["course_eval/terminal_runtime.py"]):
        raise ValueError("The proposed runtime contains an unrelated source change")
    previous = ast.parse((core_runtime / "course_eval/terminal_runtime.py").read_text())
    proposed = ast.parse((feal_runtime / "course_eval/terminal_runtime.py").read_text())
    for function in proposed.body:
        if isinstance(function, ast.FunctionDef) and function.name == "reusable_helper_instructions":
            function.body = [node for node in function.body if not (isinstance(node, ast.If)
                and ast.dump(node.test) == ast.dump(ast.parse("name == 'feal_known_pairs'", mode="eval").body))]
        if isinstance(function, ast.FunctionDef) and function.name == "prepare_public_runtime":
            index, = [i for i, node in enumerate(function.body) if isinstance(node, ast.If)
                and "feal_known_pairs" in ast.unparse(node.test)]
            function.body[index] = function.body[index].orelse[0]
    if ast.dump(previous) != ast.dump(proposed):
        raise ValueError("Removing only the FEAL conditional branches did not recover the exact core AST")
    old_module = load_module(core_runtime / "course_eval/terminal_runtime.py", "join_core_terminal")
    new_module = load_module(feal_runtime / "course_eval/terminal_runtime.py", "join_feal_terminal")
    pins_path = root / parents["main"]["baseline_queue"] / "environment-pins.json"
    if digest(pins_path) != parents["main"]["environment_pins_sha256"]:
        raise ValueError("The original image pin registry changed")
    pins = read(pins_path)["pins"]
    inherited = {}
    for task_id in sorted(tasks.keys() - changed):
        task = tasks[task_id]
        entry = {"task_sha256": object_sha(task), "selected_checks_sha256": object_sha(checks[task_id])}
        for plan in revisions.values():
            registered = plan["unchanged_task_inputs"][task_id]
            optional = {"original_image_id": pins[task_id], "configuration": parents["main"]["configuration_by_task"][task_id]}
            if (any(registered[key] != value for key, value in entry.items())
                    or any(key not in optional or registered[key] != optional[key] for key in registered.keys() - entry.keys())
                    or read(root / plan["checks"])[task_id] != checks[task_id]):
                raise ValueError("A claimed inherited task has different registered inputs: " + task_id)
        if (old_module.reusable_helper_instructions(task.get("candidate_scope"))
                != new_module.reusable_helper_instructions(task.get("candidate_scope"))):
            raise ValueError("The proposed method changes an inherited task's helper instructions")
        if any(parent["configuration_by_task"][task_id] != parents["main"]["configuration_by_task"][task_id]
                or parent["limits"] != parents["main"]["limits"] for parent in parents.values()):
            raise ValueError("Inherited configurations or budgets differ between the two cohorts")
        inherited[task_id] = entry
    if len(inherited) != 70:
        raise ValueError("Only70 task definitions may be inherited into the joint policy")
    return inherited


def actual_row(root, directory, arm, task, identities, position_counts):
    metrics = inspect_run(directory, "dsh" if arm == "dsh" else "mini-swe")
    if metrics["usage_missing_input_responses"] or metrics["usage_missing_output_responses"]:
        raise ValueError("An actual cost record lacks input or output usage")
    if metrics["actual_requests"] != metrics["verified_zero_credit_requests"]:
        raise ValueError("An actual request lacks its own fresh zero-credit receipt")
    protocol_path = directory.with_suffix(".protocol.json")
    protocol = read(protocol_path)
    trace, = directory.rglob("model.jsonl")
    fresh = set()
    for line in trace.read_text().splitlines():
        event = json.loads(line)
        if event["event"] == "billing_verified":
            for message in event["fresh_model_message_ids"]:
                if message in fresh or message in identities:
                    raise ValueError("A model generation is reused within or across scored positions")
                fresh.add(message)
    identities.update(fresh)
    position_counts[str(directory.relative_to(root))] = len(fresh)
    control = control_artifact_metrics(directory, "dsh" if arm == "dsh" else "mini-swe", protocol["configuration"])
    qualified = metrics["passed"] and (not control["final_control_applicable"] or
        (control["final_protected_unchanged"] is True and control["final_valid_verification"] is True))
    return {"arm": arm, "task": task["id"], "benchmark": task["benchmark"], "configuration": protocol["configuration"],
        **{key: metrics[key] for key in ("passed", "wall_seconds", "actual_requests", "verified_zero_credit_requests", "input_tokens", "output_tokens")},
        "qualified_passed": qualified,
        **{key: control[key] for key in ("final_control_applicable", "final_protected_unchanged", "final_valid_verification")},
        "runtime_root": str((root / protocol["runtime_root"]).resolve().relative_to(root)),
        "run_dir": str(directory.relative_to(root)), "original_score_sha256": digest(directory / "result.json"),
        "protocol_sha256": digest(protocol_path), "trace_sha256": digest(trace)}


def describe(rows, tasks):
    return {"required": 75, "completed": len(rows), "passed": sum(r["passed"] for r in rows),
        "qualified_passed": sum(r["qualified_passed"] for r in rows),
        "pending_tasks": sorted(tasks.keys() - {r["task"] for r in rows}),
        **{key: sum(r[key] for r in rows) for key in ("actual_requests", "input_tokens", "output_tokens")},
        "median_wall_seconds": statistics.median(r["wall_seconds"] for r in rows) if rows else None,
        "by_benchmark": {benchmark: {"required": 25, "completed": sum(r["benchmark"] == benchmark for r in rows),
            "passed": sum(r["benchmark"] == benchmark and r["passed"] for r in rows)} for benchmark in ("aider", "swe", "terminal")}}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--core-summary", type=Path, default=Path("work/parallel-free-evaluation-20261124/final-hy4-summary/summary.json"))
    parser.add_argument("--out", type=Path, default=Path("work/parallel-free-evaluation-20261124/joint-policy-summary"))
    parser.add_argument("--require-complete", action="store_true")
    args = parser.parse_args()
    root, folder = Path.cwd(), Path(__file__).parent.resolve()
    args.core_summary, args.out = args.core_summary.resolve(), args.out.resolve()
    core = read(args.core_summary)
    if core["analysis_sha256"] != digest(folder / "analyze_hy4.py"):
        raise ValueError("The original cohort summary must be recomputed with its actual producer")
    parents = {}
    for arm, name in core["source_plan_paths"].items():
        if digest(root / name) != core["source_plan_sha256"][arm]:
            raise ValueError("The original analysis belongs to another frozen plan")
        parents[arm] = read(root / name)
    source_manifest = root / core["source_manifest_path"]
    if digest(source_manifest) != core["source_manifest_sha256"]:
        raise ValueError("The original task manifest changed")
    manifest = read(source_manifest)
    tasks = {task["id"]: task for task in manifest["selected"]}
    if len(tasks) != 75 or Counter(t["benchmark"] for t in tasks.values()) != {"aider": 25, "swe": 25, "terminal": 25}:
        raise ValueError("The joint policy requires exactly the original75 tasks")
    checks = read(Path(core["source_plan_paths"]["main"]).parent / "checks.json")
    paths = {"json": root / "work/json-in-semantics-20261125/oracle-bool/ascii-transport/frozen/plan.json",
        "feal": root / "work/feal-linear-helper-20261125/readmission/plan.json",
        "xarray": root / "work/xarray-2905-semantics-20261125/frozen/plan.json",
        "pytest": root / "work/pytest-7205-semantics-20261125/frozen/plan.json",
        "preservation": root / "work/pytest-5631-preservation-20261125/frozen/plan.json",
        "development_json_types": root / "work/json-in-semantics-20261125/frozen/plan.json",
        "development_json_contract": root / "work/json-in-semantics-20261125/expanded/frozen/plan.json",
        "development_json_unicode_transport": root / "work/json-in-semantics-20261125/oracle-bool/frozen/plan.json"}
    all_plans = {name: validate_plan(root, path) for name, path in paths.items()}
    revisions = {name: all_plans[name] for name in ("json", "feal", "xarray", "pytest", "preservation")}
    inherited = validate_scope(root, parents, tasks, checks, revisions)
    changed = {plan["task"] for plan in revisions.values()}
    identities, position_counts, raw_rows = set(), {}, []
    for saved in core["rows"]:
        actual = actual_row(root, root / saved["run_dir"], saved["arm"], tasks[saved["task"]], identities, position_counts)
        if actual != saved:
            raise ValueError("The source-bound original cohort row no longer matches its actual score or trace")
        raw_rows.append(actual)
    effective = [row for row in raw_rows if row["arm"] == "dsh" or row["task"] not in changed]
    revision_rows, previous_json = [], []
    for name, plan in all_plans.items():
        task, = read(root / plan["manifest"])["selected"]
        if task["id"] != plan["task"] or plan["model"] != "hy4flash-free":
            raise ValueError("A fixed scope revision changed task or model")
        if name in revisions:
            manifest["selected"] = [copy.deepcopy(task) if item["id"] == task["id"] else item for item in manifest["selected"]]
        for arm, label in zip(("main", "repeat"), plan["prospective_trials"], strict=True):
            directory = root / plan["queue"] / (task["id"] + "-C0-" + label)
            score = directory / "result.json"
            if not score.exists() or read(score).get("scoreable") is not True:
                continue
            protocol = {key: value for key, value in read(directory.with_suffix(".protocol.json")).items()
                if key != "historical_unknown_calls_preserved"}
            if protocol != plan["expected_protocol"] or read(directory / "trial.json")["task"] != task:
                raise ValueError("A revision's actual task or execution protocol differs from its fixed plan")
            row = actual_row(root, directory, arm, task, identities, position_counts)
            (revision_rows if name in revisions else previous_json).append(row)
            if name in revisions:
                effective.append(row)
    indexed = {arm: {r["task"]: r for r in effective if r["arm"] == arm} for arm in ("main", "repeat", "dsh")}
    for arm in indexed:
        if len(indexed[arm]) != sum(row["arm"] == arm for row in effective):
            raise ValueError("The effective policy contains a duplicate task position")
    groups = {arm: describe(list(indexed[arm].values()), tasks) for arm in indexed}
    paired = tasks.keys() & indexed["main"].keys() & indexed["dsh"].keys()
    repeated = tasks.keys() & indexed["main"].keys() & indexed["repeat"].keys()
    comparison = {"matched": len(paired), "required": 75,
        "method_only_pass": sorted(t for t in paired if indexed["main"][t]["passed"] and not indexed["dsh"][t]["passed"]),
        "dsh_only_pass": sorted(t for t in paired if indexed["dsh"][t]["passed"] and not indexed["main"][t]["passed"]),
        "both_failed": sorted(t for t in paired if not indexed["main"][t]["passed"] and not indexed["dsh"][t]["passed"])}
    complete = core["complete_all225"] and all(g["completed"] == 75 for g in groups.values())
    if args.require_complete and not complete:
        raise RuntimeError("The complete original225 and all ten fixed revision scores are required")
    args.out.mkdir(parents=True, exist_ok=True)
    joined_manifest = args.out / "tasks.json"
    joined_manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    summary = copy.deepcopy(core)
    summary.update({"observed_utc": datetime.now(timezone.utc).isoformat(), "rows": effective, "groups": groups,
        "distinct_actual_generations": sum(position_counts[row["run_dir"]] for row in effective),
        "source_manifest_path": str(joined_manifest.relative_to(root)), "source_manifest_sha256": digest(joined_manifest),
        "complete_all225": complete,
        "main_and_repeat_all75_qualified_pass": all(groups[a]["qualified_passed"] == 75 for a in ("main", "repeat")),
        "paired_same75": comparison, "independent_repeat": {"matched": len(repeated), "required": 75,
            "both_pass": sum(indexed["main"][t]["passed"] and indexed["repeat"][t]["passed"] for t in repeated)},
        "incremental_acceptance": {"producer": str(Path(__file__).relative_to(root)), "producer_sha256": digest(Path(__file__)),
            "core_summary": str(args.core_summary.relative_to(root)), "core_summary_sha256": digest(args.core_summary),
            "revision_plans": {name: {"path": str(path.relative_to(root)), "sha256": digest(path)} for name, path in paths.items()},
            "inherited_task_definitions": inherited, "required_inherited_positions": 140, "required_new_positions": 10,
            "completed_inherited_positions": sum(r["arm"] != "dsh" and r["task"] not in changed for r in effective),
            "completed_new_positions": len(revision_rows), "per_task_non_feal_runtime_ast_equivalence": True,
            "original_core_rows": raw_rows, "new_revision_rows": revision_rows, "previous_json_development_rows": previous_json,
            "displaced_original_rows": [r for r in raw_rows if r["arm"] != "dsh" and r["task"] in changed],
            "all_listed_model_scored_positions": len(raw_rows) + len(revision_rows) + len(previous_json),
            "all_listed_distinct_actual_generations": len(identities),
            "all_listed_actual_requests": sum(r["actual_requests"] for r in raw_rows + revision_rows + previous_json),
            "all_listed_input_tokens": sum(r["input_tokens"] for r in raw_rows + revision_rows + previous_json),
            "all_listed_output_tokens": sum(r["output_tokens"] for r in raw_rows + revision_rows + previous_json),
            "retired_unstarted_development_slot": {"path": "work/json-in-semantics-20261125/oracle-bool/ascii-transport/retirement.json",
                "sha256": digest(root / "work/json-in-semantics-20261125/oracle-bool/ascii-transport/retirement.json"),
                "actual_model_calls": 0, "original_grader_calls": 0},
            "cost_scope": "Original core225 plus ten final scope-revision sessions and all five previous model-scored JSON development sessions. The unstarted r6 slot has no model call or score. The three guidance ablations, supplementary different-model experiments and earlier SQL pilots are reported separately; no discarded scores are removed from cost.",
            "method": "Task-conditional incremental revalidation. Both original cohorts remain intact. No claim of225 newly generated positions after the last policy freeze."},
        "interpretation": core["interpretation"] + " Five declared task-local changes are accepted only via their fixed fresh independent sessions;70 unchanged task definitions are inherited after source, input, check, helper-prompt and conditional runtime AST validation. All displaced and earlier JSON results and costs remain separate. Other models do not fill Hy4 positions."})
    (args.out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    with (args.out / "trials.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(effective[0]))
        writer.writeheader()
        writer.writerows(effective)
    print(json.dumps({"status": "complete" if complete else "partial", "core_positions": len(raw_rows),
        "inherited_positions": summary["incremental_acceptance"]["completed_inherited_positions"],
        "new_revision_positions": len(revision_rows), "earlier_json_positions": len(previous_json),
        "new_model_calls": 0}), flush=True)


if __name__ == "__main__":
    main()
