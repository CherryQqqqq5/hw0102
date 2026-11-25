import copy
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path.cwd() / "work/frozen-performance-hy4-feal-linear-v19"))
from course_eval.verification import PublicCheck


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    root, folder = Path.cwd(), Path(__file__).parent.resolve()
    old = folder / "frozen"
    plan = json.loads((old / "plan.json").read_text())
    for name, expected in plan["all_files_sha256"].items():
        if sha(root / name) != expected:
            raise ValueError("The stopped original FEAL launch source changed")
    failed = root / plan["queue"] / "feal-linear-cryptanalysis-C0-feal-linear-main-r1"
    outcome = json.loads((failed / "result.json").read_text())
    if outcome["scoreable"] is not False or outcome["passed"] is not None or list(failed.rglob("model.jsonl")):
        raise ValueError("This repair is limited to the demonstrated zero-model, unscored setup failure")
    instruction = (failed / "feal-linear-cryptanalysis/instruction.md").read_text()
    checks = json.loads((old / "checks.json").read_text())
    previous = copy.deepcopy(checks)
    check, = checks[plan["task"]]
    helpers = {"/opt/course-tools/feal_known_pairs.c", "/opt/course-tools/feal_public_check.py"}
    if not helpers.issubset(set(check["dependencies"])):
        raise ValueError("The old invalid dependency pair differs from its actual startup error")
    try:
        PublicCheck(**check).validate(instruction)
    except ValueError as error:
        if "Unsafe check dependency" not in str(error):
            raise
        original_error = str(error)
    else:
        raise ValueError("The original setup error no longer reproduces")
    check["dependencies"] = [name for name in check["dependencies"] if name not in helpers]
    PublicCheck(**check).validate(instruction)
    task, = json.loads((old / "tasks.json").read_text())["selected"]
    if not helpers.issubset(set(task["candidate_scope"]["protected"])):
        raise ValueError("Both helper sources must remain in the original protected snapshot")
    for task_id in checks:
        if task_id != plan["task"] and checks[task_id] != previous[task_id]:
            raise ValueError("An unrelated public check changed")
    destination = folder / "readmission-inputs"
    destination.mkdir()
    (destination / "checks.json").write_text(json.dumps(checks, indent=2) + "\n")
    for name in ("tasks.json", "capture-policy.json"):
        (destination / name).write_bytes((old / name).read_bytes())
    record = {"phase": "original_dependency_failure_reproduced_and_valid_configuration_prepared",
        "new_model_calls": 0, "original_grader_calls": 0, "old_error": original_error,
        "source_plan_sha256": sha(old / "plan.json"), "source_unscored_result_sha256": sha(failed / "result.json"),
        "only_change": "Remove the two helper paths from public check dependency metadata; both remain in CandidateStore protected scope. The original path validator is unchanged.",
        "removed_redundant_dependency_paths": sorted(helpers), "both_helper_sources_still_protected": True,
        "new_checks_sha256": sha(destination / "checks.json"), "driver_sha256": sha(Path(__file__))}
    (destination / "preparation.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"phase": record["phase"], "new_model_calls": 0}), flush=True)


if __name__ == "__main__":
    main()
