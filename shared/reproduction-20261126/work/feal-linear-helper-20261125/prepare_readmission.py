import copy
import hashlib
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    root, folder = Path.cwd(), Path(__file__).parent.resolve()
    old_path = folder / "frozen/plan.json"
    old = json.loads(old_path.read_text())
    for name, expected in old["all_files_sha256"].items():
        if sha(root / name) != expected:
            raise ValueError("The stopped FEAL launch dependency changed: " + name)
    inputs = folder / "readmission-inputs"
    qualification_path = folder / "controller-qualification/result.json"
    qualification = json.loads(qualification_path.read_text())
    failed = root / old["queue"] / "feal-linear-cryptanalysis-C0-feal-linear-main-r1"
    outcome = json.loads((failed / "result.json").read_text())
    preparation = json.loads((inputs / "preparation.json").read_text())
    if (outcome["scoreable"] is not False or outcome["passed"] is not None
            or list(failed.rglob("model.jsonl"))
            or preparation["source_unscored_result_sha256"] != sha(failed / "result.json")
            or preparation["source_plan_sha256"] != sha(old_path)):
        raise ValueError("The repair must retain the exact unscored, zero-model initialization failure")
    if (qualification["phase"] != "real_publiccheck_controller_and_helper_protection_passed"
            or qualification["new_model_calls"] != 0 or qualification["original_grader_calls"] != 0
            or qualification["pin"] != old["pin"] or qualification["runtime_root"] != old["runtime_root"]
            or qualification["old_wrong_state"] != "failed" or qualification["correct_state"] != "passed"
            or qualification["helper_tamper_state"] != "protected_dependency_changed"
            or qualification["restored_state"] != "passed"
            or qualification["final"]["valid_verification"] is not True
            or qualification["final"]["protected_unchanged"] is not True):
        raise ValueError("Actual controller initialization, content validation and protected restoration are incomplete")
    for key, path in (("checks_sha256", inputs / "checks.json"), ("tasks_sha256", inputs / "tasks.json"),
            ("driver_sha256", folder / "qualify_controller.py")):
        if qualification[key] != sha(path):
            raise ValueError("The actual qualification belongs to a different readmission input")
    for module in qualification["actual_loaded_modules"].values():
        if sha(root / module["path"]) != module["sha256"] or old["all_files_sha256"][module["path"]] != module["sha256"]:
            raise ValueError("The actual controller used a different frozen runtime")
    for item in qualification["public_helper_manifest"]["reusable_helper"]["files"]:
        if sha(root / old["runtime_root"] / "course_eval" / Path(item["path"]).name) != item["sha256"]:
            raise ValueError("The actual protected helper differs from the frozen source")
    previous = json.loads((root / old["checks"]).read_text())
    actual = json.loads((inputs / "checks.json").read_text())
    helpers = {"/opt/course-tools/feal_known_pairs.c", "/opt/course-tools/feal_public_check.py"}
    expected = copy.deepcopy(previous)
    check, = expected[old["task"]]
    check["dependencies"] = [name for name in check["dependencies"] if name not in helpers]
    if actual != expected or preparation["new_checks_sha256"] != sha(inputs / "checks.json"):
        raise ValueError("Readmission may only remove the two already-protected redundant dependency paths")
    for name in ("tasks.json", "capture-policy.json"):
        if (inputs / name).read_bytes() != (folder / "frozen" / name).read_bytes():
            raise ValueError("Task and artifact capture inputs must remain byte-identical")
    task, = json.loads((inputs / "tasks.json").read_text())["selected"]
    if not helpers.issubset(set(task["candidate_scope"]["protected"])):
        raise ValueError("Both helper sources must remain protected by CandidateStore")
    destination = folder / "readmission"
    destination.mkdir()
    plan = copy.deepcopy(old)
    plan.update({"stage": "frozen_after_actual_zero_model_controller_readmission_qualification",
        "manifest": str((inputs / "tasks.json").relative_to(root)),
        "checks": str((inputs / "checks.json").relative_to(root)),
        "artifact_capture_policy": str((inputs / "capture-policy.json").relative_to(root)),
        "prospective_trials": ["feal-linear-main-readmission-r1", "feal-linear-repeat-r2"],
        "source_stopped_plan": str(old_path.relative_to(root)),
        "source_unscored_zero_model_attempt": str(failed.relative_to(root)),
        "readmission_qualification": str(qualification_path.relative_to(root)),
        "readmission_change": preparation["only_change"]})
    paths = [old_path, Path(__file__).resolve(), folder / "prepare_readmission_inputs.py",
        folder / "qualify_controller.py", qualification_path, folder / "controller.resources.json",
        failed / "result.json", *inputs.glob("*.json")]
    plan["all_files_sha256"].update({str(path.relative_to(root)): sha(path) for path in paths})
    with (destination / "plan.json").open("x") as stream:
        stream.write(json.dumps(plan, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"status": "frozen", "prospective_sessions": 2, "new_model_calls": 0,
        "controller_qualification": qualification["phase"], "bound_files": len(plan["all_files_sha256"])}), flush=True)


if __name__ == "__main__":
    main()
