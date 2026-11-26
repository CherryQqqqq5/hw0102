import time

from run_study import FOLDER, ROOT, digest, hashes, read, save


archive = FOLDER / "baseline-amendment-20261127"
record_path = archive / "amendment.json"
if record_path.exists():
    raise FileExistsError("The additional baseline is already registered")
old_plan = read(archive / "study-plan-v2.json")
old_candidate = read(archive / "candidate-tasks.json")
candidate = read(FOLDER / "candidate-tasks.json")
expected = old_candidate | {
    "maximum_model_task_trials": 39,
    "confirmation_arms": ["base", "dsh", "environment", "digest"],
    "baseline_amendment": candidate["baseline_amendment"],
}
if candidate != expected or old_candidate["maximum_model_task_trials"] != 33:
    raise RuntimeError("The amendment changes more than the six original baseline positions")
current = hashes()
changed = {name for name in old_plan["source_hashes"] | current
    if old_plan["source_hashes"].get(name) != current.get(name)}
allowed = {str((FOLDER / name).relative_to(ROOT))
    for name in ("candidate-tasks.json", "run_study.py", "analyze_study.py")}
if changed != allowed:
    raise RuntimeError("Unexpected model, grading or fee-source change")
for name in ("run_study.py", "analyze_study.py"):
    before = (archive / name).read_text()
    expected_text = before.replace('["dsh", "environment"]', '["base", "dsh", "environment"]')
    if before.count('["dsh", "environment"]') != 1 or (FOLDER / name).read_text() != expected_text:
        raise RuntimeError("Unexpected behavior beyond adding the original baseline: " + name)
fresh_files = [str(path) for name in candidate["confirmation_ids"]
    for path in (FOLDER / "trials" / name).rglob("model.jsonl")]
if fresh_files or (FOLDER / "repeat-plan.json").exists():
    raise RuntimeError("Fresh-task generation has already started")
if read(ROOT / "work/performance-stop-20261122.json")["active"]:
    raise RuntimeError("An unresolved fee prevents continuation")
completed = [read(path) for path in (FOLDER / "trials").rglob("*.audited.json")]
record = {
    "stage": "registered_before_first_fresh_generation",
    "registered_unix": time.time(),
    "reason": "Diagnostics show that environment guidance has task-dependent costs; compare the simplest same-framework baseline on every fixed fresh task",
    "fresh_model_files": fresh_files,
    "completed_diagnostic_positions": len(completed),
    "completed_diagnostic_all_passed": all(row["passed"] for row in completed),
    "maximum_model_task_trials_before": 33,
    "maximum_model_task_trials_after": 39,
    "maximum_extra_agent_seconds": 10800,
    "maximum_extra_swe_grading_seconds": 5400,
    "all_six_base_positions_required": True,
    "model_inputs_task_selection_limits_fee_selection_repeat_rules_unchanged": True,
    "original_plan_sha256": digest(archive / "study-plan-v2.json"),
    "source_changes": {name: {"before": old_plan["source_hashes"][name], "after": current[name]}
        for name in sorted(changed)},
    "new_model_calls": 0,
}
save(record_path, record)
save(FOLDER / "study-plan.json", old_plan | {
    "stage": "frozen_with_original_baseline_before_fresh_generation",
    "source_hashes": current,
    "registered_design": candidate,
    "baseline_amendment": record,
})
print(record)
