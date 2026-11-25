import ast
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "parallel-free-evaluation-20261124"))
from ready_coordinator import digest, read_json
from prepare_report_data import native_output


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def object_sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def main():
    root, folder = Path.cwd(), Path(__file__).parent.resolve()
    parent_folder = root / "work/parallel-free-evaluation-20261124/final-sql75-recovered"
    parent_paths = {arm: parent_folder / (arm + "-plan.json") for arm in ("main", "repeat")}
    parents = {arm: read_json(path) for arm, path in parent_paths.items()}
    parent = parents["main"]
    old, new = Path(parent["runtime_root"]), root / "work/frozen-performance-hy4-feal-linear-v19"
    qualification_path = folder / "delivery-qualification/result.json"
    qualification = read_json(qualification_path)
    linux_path = folder / "linux-qualification/result.json"
    linux = read_json(linux_path)
    if (qualification["phase"] != "actual_original_linux_helper_and_public_content_check_passed"
            or linux["phase"] != "actual_original_linux_generated_qualification_passed"
            or qualification["new_model_calls"] != 0 or qualification["original_grader_calls"] != 0
            or qualification["actual_failed_model_rejected"]["passed"] is not False
            or qualification["actual_public_cipher_derived_output_accepted"]["passed"] is not True
            or qualification["actual_omitted_record_rejected"]["passed"] is not False):
        raise ValueError("The actual Linux interface and public semantic qualification are incomplete")
    if (qualification["driver_sha256"] != digest(folder / "qualify_delivery.py")
            or linux["driver_sha256"] != digest(folder / "qualify_linux.py")):
        raise ValueError("An actual Linux qualification driver changed after execution")
    failed_score = root / qualification["original_failed_score"]
    if digest(failed_score) != qualification["original_failed_score_sha256"]:
        raise ValueError("The preserved original failed score changed")
    failed_artifact = native_output(failed_score.parent, "/app/plaintexts.txt")
    if digest(failed_artifact) != qualification["actual_failed_artifact_sha256"]:
        raise ValueError("The actual failed artifact differs from its semantic negative control")
    for name, expected in qualification["runtime_files_sha256"].items():
        if digest(new / "course_eval" / name) != expected:
            raise ValueError("The proposed helper differs from its actual Linux qualification")
    for item in qualification["public_helper_manifest"]["reusable_helper"]["files"]:
        if digest(new / "course_eval" / Path(item["path"]).name) != item["sha256"]:
            raise ValueError("The actual deployed source differs from the current qualified helper")
    if linux["source_sha256"] != digest(new / "course_eval/feal_known_pairs.c"):
        raise ValueError("The real Linux generated qualification belongs to another algorithm")
    for name, expected in (parent["runtime_sha256"] | parent["runtime_resources_sha256"]).items():
        if digest(old / name) != expected:
            raise ValueError("The original frozen core runtime changed")
    expected = {root / name: value for name, value in
        (parent["request_guard_sha256"] | parent["image_preparation_sha256"]).items()}
    expected.update({root / parent["coordinator_path"]: parent["coordinator_sha256"],
        root / parent["driver_path"]: parent["driver_sha256"],
        root / "work/codebuddy/node_modules/@tencent-ai/codebuddy-code/dist/codebuddy-headless.js": parent["client_sha256"],
        root / "work/free-channel-capabilities-20261122/cloud-model-metadata.json": parent["image_metadata_sha256"],
        root / "work/vmshare/elf-public-check-deps/pyelftools-0.33-py3-none-any.whl": parent["elf_wheel_sha256"]})
    for path, value in expected.items():
        if digest(path) != value:
            raise ValueError("A qualified fixed model, guard or image preparation dependency changed: " + str(path))
    old_files = {str(p.relative_to(old)): digest(p) for p in old.rglob("*") if p.is_file() and "__pycache__" not in p.parts}
    new_files = {str(p.relative_to(new)): digest(p) for p in new.rglob("*") if p.is_file() and "__pycache__" not in p.parts}
    added = {"course_eval/feal_known_pairs.c", "course_eval/feal_public_check.py"}
    if set(new_files) - set(old_files) != added or set(old_files) - set(new_files) or [
            name for name in old_files if old_files[name] != new_files[name]] != ["course_eval/terminal_runtime.py"]:
        raise ValueError("The local FEAL revision changed unrelated runtime source")
    old_module = load_module(old / "course_eval/terminal_runtime.py", "feal_scope_parent")
    new_module = load_module(new / "course_eval/terminal_runtime.py", "feal_scope_proposed")
    manifest_path, checks_path = parent_folder / "tasks.json", parent_folder / "checks.json"
    data, checks = read_json(manifest_path), read_json(checks_path)
    for source in parents.values():
        if (source["tasks_sha256"] != digest(manifest_path) or source["checks_sha256"] != digest(checks_path)
                or source["runtime_root"] != parent["runtime_root"] or source["limits"] != parent["limits"]
                or source["configuration_by_task"] != parent["configuration_by_task"]):
            raise ValueError("The two source cohorts differ in an input intended for inheritance")
    task_id = "feal-linear-cryptanalysis"
    unchanged = [task for task in data["selected"] if task["id"] != task_id]
    if len(unchanged) != 74:
        raise ValueError("Exactly74 original task definitions must be untouched")
    for task in unchanged:
        if old_module.reusable_helper_instructions(task.get("candidate_scope")) != new_module.reusable_helper_instructions(task.get("candidate_scope")):
            raise ValueError("Another task received new helper instructions")
    old_ast = ast.parse((old / "course_eval/terminal_runtime.py").read_text())
    new_ast = copy.deepcopy(ast.parse((new / "course_eval/terminal_runtime.py").read_text()))
    for function in new_ast.body:
        if isinstance(function, ast.FunctionDef) and function.name == "reusable_helper_instructions":
            function.body = [node for node in function.body if not (isinstance(node, ast.If)
                and ast.dump(node.test) == ast.dump(ast.parse("name == 'feal_known_pairs'", mode="eval").body))]
        if isinstance(function, ast.FunctionDef) and function.name == "prepare_public_runtime":
            index, = [index for index, node in enumerate(function.body) if isinstance(node, ast.If)
                and "feal_known_pairs" in ast.unparse(node.test)]
            function.body[index] = function.body[index].orelse[0]
    if ast.dump(new_ast) != ast.dump(old_ast):
        raise ValueError("Removing only the FEAL branches did not recover the exact parent runtime AST")
    task = copy.deepcopy(next(task for task in data["selected"] if task["id"] == task_id))
    task["candidate_scope"]["reusable_helper"] = "feal_known_pairs"
    task["candidate_scope"]["protected"] += ["/opt/course-tools/feal_known_pairs.c", "/opt/course-tools/feal_public_check.py"]
    changed_checks = copy.deepcopy(checks)
    entry, = changed_checks[task_id]
    if entry["check_id"] != "public-task":
        raise ValueError("Keep the original single public-task check interface")
    entry["command"] = "python3 /opt/course-tools/feal_public_check.py"
    entry["timeout_seconds"] = 120
    entry["dependencies"] += ["/app/feal", "/app/decrypt", "/opt/course-tools/feal_known_pairs.c", "/opt/course-tools/feal_public_check.py"]
    entry["coverage"] = ["Recover a key using only public known pairs; re-encrypt every known pair with the original public feal executable",
        "Each public-decrypt-derived plaintext is present as a decimal token, including multiplicity; diagnostic text and extra tokens allowed",
        "No ordering claim, hidden key or hidden answer file; a domain algorithm helper is added to the whole method package"]
    for item in unchanged:
        if checks[item["id"]] != changed_checks[item["id"]]:
            raise ValueError("Another task's selected public checks changed")
    pins_path = Path(parent["baseline_queue"]) / "environment-pins.json"
    if digest(pins_path) != parent["environment_pins_sha256"]:
        raise ValueError("The actual original image pins changed")
    pin = read_json(pins_path)["pins"][task_id]
    if qualification["pin"] != pin or linux["pin"] != pin:
        raise ValueError("A real qualification used a different original image")
    destination = folder / "frozen"
    destination.mkdir()
    selected, updated = destination / "tasks.json", destination / "checks.json"
    selected.write_text(json.dumps({"stage": "frozen", "selected": [task], "revisions": data["revisions"]}, indent=2) + "\n")
    updated.write_text(json.dumps(changed_checks, indent=2) + "\n")
    queue = "work/vmshare/performance-feal-linear-v19-20261125"
    policy_source = root / parent["artifact_capture_policy"]
    policy = read_json(policy_source)
    if policy["task_artifacts"][task_id] != task["candidate_scope"]["artifacts"]:
        raise ValueError("The original artifact collection differs from the unchanged FEAL output scope")
    policy["queues"] = [queue]
    policy_path = destination / "capture-policy.json"
    policy_path.write_text(json.dumps(policy, indent=2) + "\n")
    source_protocol = root / parent["queue"] / (task_id + "-C0-r1.protocol.json")
    protocol = {key: value for key, value in read_json(source_protocol).items() if key != "historical_unknown_calls_preserved"}
    protocol["runtime_root"] = str(new.relative_to(root))
    paths = [Path(__file__).resolve(), folder / "qualify_delivery.py", folder / "qualify_linux.py", qualification_path,
        linux_path, folder / "generated-qualification/result.json", selected, updated, policy_path,
        manifest_path, checks_path, pins_path, source_protocol, failed_score, failed_artifact, *parent_paths.values(),
        root / "work/parallel-free-evaluation-20261124/run_fixed_free_trials.py",
        root / "work/parallel-free-evaluation-20261124/resource_trial.py", root / parent["resource_driver"],
        root / "course_eval/resource_pool.py", root / "scripts/export_performance_evidence.py",
        root / "scripts/summarize_performance_comparison.py"]
    paths += [new / name for name in new_files]
    paths += list(expected)
    bindings = {str(path.relative_to(root)): digest(path) for path in set(paths)}
    plan = {"stage": "frozen_before_any_new_feal_helper_model_generation", "phase": "RUN", "task": task_id,
        "model": "hy4flash-free", "prospective_trials": ["feal-linear-main-r1", "feal-linear-repeat-r2"],
        "runtime_root": str(new.relative_to(root)), "manifest": str(selected.relative_to(root)),
        "checks": str(updated.relative_to(root)), "pin": pin, "limits": parent["limits"],
        "expected_protocol": protocol, "queue": queue, "driver": parent["driver_path"],
        "resource_driver": parent["resource_driver"], "image_copy_driver": parent["image_copy_driver"],
        "artifact_capture_policy": str(policy_path.relative_to(root)), "all_files_sha256": bindings,
        "main_variable": "FEAL-specific generic exact linear-attack tool plus public content verification; this is a joint whole-policy revision, not an isolated controller or underlying-model benefit",
        "unchanged_task_inputs": {item["id"]: {"task_sha256": object_sha(item),
            "selected_checks_sha256": object_sha(checks[item["id"]])} for item in unchanged},
        "other74_helper_instructions_identical": True, "removing_feal_branches_restores_parent_ast": True,
        "original_failed_score": qualification["original_failed_score"],
        "original_failed_score_sha256": qualification["original_failed_score_sha256"],
        "capture_qualification": "Reuse unchanged qualified collector/launcher and identical artifact scope; only queue admission list changes. Actual trial argv and native final bytes remain auditable.",
        "success": "Both prescribed fresh sessions pass actual original grading, final public/protected validation and every own zero-credit receipt",
        "failure": "Keep every valid result, stop on incomplete original grading or unknown/nonzero fee; never resample a valid low score",
        "reporting": "Preserve complete original225 plus all costs. Joint JSON+FEAL acceptance can inherit only unchanged73x2 sessions after completion and source revalidation, plus4 new fixed sessions. Never call this a newly rerun150 or official leaderboard performance.",
        "new_model_calls_during_preparation": 0}
    with (destination / "plan.json").open("x") as stream:
        stream.write(json.dumps(plan, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"status": "frozen", "prospective_sessions": 2, "other_unchanged_tasks": 74,
        "new_model_calls": 0}), flush=True)


if __name__ == "__main__":
    main()
