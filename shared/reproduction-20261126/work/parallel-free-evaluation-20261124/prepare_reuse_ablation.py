import argparse
import ast
import json
import shutil
import time
from pathlib import Path

from run_reuse_ablation import digest, read


def main():
    root, folder = Path.cwd(), Path(__file__).parent.resolve()
    parser = argparse.ArgumentParser()
    parser.add_argument("--main-plan", type=Path, default=folder / "final-sql75-recovered/main-plan.json")
    parser.add_argument("--repeat-plan", type=Path, default=folder / "final-sql75-recovered/repeat-plan.json")
    parser.add_argument("--out", type=Path, default=folder / "final-reuse-ablation")
    parser.add_argument("--wait-main-references", action="store_true")
    args = parser.parse_args()
    parent_path = args.main_plan
    parent = read(parent_path)
    source = Path(parent["runtime_root"])
    runtime = root / "work/frozen-performance-hy4-sql-layout-v18-guidance-off"
    source_files = {str(path.relative_to(source)) for path in source.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts}
    runtime_files = {str(path.relative_to(runtime)) for path in runtime.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts}
    if source_files != runtime_files:
        raise ValueError("The ablation runtime added or removed source or resource files")
    changed = [str(path.relative_to(runtime)) for path in runtime.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts and digest(path) != digest(source / path.relative_to(runtime))]
    if changed != ["course_eval/terminal_runtime.py"]:
        raise ValueError("The intended isolated guidance ablation changed another runtime file")
    old = ast.parse((source / changed[0]).read_text())
    new = ast.parse((runtime / changed[0]).read_text())
    old_nodes = {node.name: ast.dump(node) for node in old.body if isinstance(node, (ast.FunctionDef, ast.ClassDef))}
    new_nodes = {node.name: ast.dump(node) for node in new.body if isinstance(node, (ast.FunctionDef, ast.ClassDef))}
    if old_nodes.keys() != new_nodes.keys() or [name for name in old_nodes if old_nodes[name] != new_nodes[name]] != ["reusable_helper_instructions"]:
        raise ValueError("The helper implementation or preparation behavior changed")
    for index, node in enumerate(new.body):
        if isinstance(node, ast.FunctionDef) and node.name == "reusable_helper_instructions":
            new.body[index] = next(node for node in old.body
                if isinstance(node, ast.FunctionDef) and node.name == "reusable_helper_instructions")
    if ast.dump(old) != ast.dump(new):
        raise ValueError("A module-level behavior changed outside the declared guidance function")
    destination = args.out
    main_queue = root / parent["queue"]
    ids = ["model-extraction-relu-logits", "extract-elf", "video-processing"]
    image_metadata = root / "work/free-channel-capabilities-20261122/cloud-model-metadata.json"
    elf_wheel = root / "work/vmshare/elf-public-check-deps/pyelftools-0.33-py3-none-any.whl"
    admission = {image_metadata: parent["image_metadata_sha256"], elf_wheel: parent["elf_wheel_sha256"],
        root / "work/codebuddy/node_modules/@tencent-ai/codebuddy-code/dist/codebuddy-headless.js": parent["client_sha256"],
        root / parent["driver_path"]: parent["driver_sha256"],
        root / parent["coordinator_path"]: parent["coordinator_sha256"]}
    inputs = [path for path in runtime.rglob("*") if path.is_file() and "__pycache__" not in path.parts]
    inputs.extend([parent_path, args.repeat_plan, Path(__file__).resolve(), folder / "run_reuse_ablation.py",
        parent_path.parent / "tasks.json", parent_path.parent / "checks.json", parent_path.parent / "scopes.json"])
    inputs.extend(root / name for name in (parent["request_guard_sha256"] | parent["image_preparation_sha256"]))
    for path in inputs:
        observed = digest(path)
        if path in admission and admission[path] != observed:
            raise ValueError("An input differs from its final-core declared hash: " + str(path))
        admission[path] = observed
    deadline = time.monotonic() + 48 * 3600
    while True:
        for path, expected in admission.items():
            if digest(path) != expected:
                raise ValueError("A declared ablation input changed before freezing: " + str(path))
        if read(root / "work/performance-stop-20261122.json")["active"]:
            raise RuntimeError("The actual financial stop prevents ablation preparation")
        if all((main_queue / (task + "-C0-r1") / "result.json").exists() for task in ids):
            break
        if not args.wait_main_references:
            raise RuntimeError("Wait for all three final main references before freezing the ablation")
        if time.monotonic() > deadline:
            raise TimeoutError("The three final references did not finish within the declared48-hour preparation window")
        time.sleep(10)
    tasks, references = [], {}
    for task_id in ids:
        task, = read(main_queue / "resolved-inputs" / (task_id + ".json"))["selected"]
        tasks.append(task)
        run = main_queue / (task_id + "-C0-r1")
        outcome = read(run / "result.json")
        if outcome["scoreable"] is not True or type(outcome["passed"]) is not bool:
            raise ValueError("The declared reference needs its actual original score, irrespective of success")
        references[task_id] = {"result": str((run / "result.json").relative_to(root)),
            "result_sha256": digest(run / "result.json"), "trial": str((run / "trial.json").relative_to(root)),
            "interpretation": "A prior actual reference only; not a new model call, scoring event or independent repeat"}
    destination.mkdir()
    manifest = destination / "tasks.json"
    manifest.write_text(json.dumps({"stage": "frozen", "selected": tasks,
        "revisions": read(parent_path.parent / "tasks.json")["revisions"]}, indent=2) + "\n")
    checks = destination / "checks.json"
    shutil.copy2(parent_path.parent / "checks.json", checks)
    queue = "work/vmshare/performance75-hy4-v18-reuse-guidance-ablation-20261125"
    capture_policy = destination / "artifact-capture-policy.json"
    policy = read(root / parent["artifact_capture_policy"])
    policy["queues"] = [queue]
    capture_policy.write_text(json.dumps(policy, indent=2) + "\n")
    pins = read(Path(parent["baseline_queue"]) / "environment-pins.json")["pins"]
    files = [path for path in runtime.rglob("*") if path.is_file() and "__pycache__" not in path.parts]
    files.extend([manifest, checks, Path(__file__).resolve(), folder / "run_reuse_ablation.py", parent_path,
        args.repeat_plan, capture_policy, root / parent["driver_path"], root / parent["resource_driver"],
        root / parent["coordinator_path"],
        root / "scripts/export_performance_evidence.py", root / "scripts/summarize_performance_comparison.py",
        root / "work/codebuddy/node_modules/@tencent-ai/codebuddy-code/dist/codebuddy-headless.js"])
    files.extend(admission)
    plan = {"stage": "frozen_before_any_ablated_generation", "phase": "DESIGN",
        "decision": "Test whether prescribing early reuse adds benefit when the same helper algorithms remain available",
        "main_variable": "Only the prescriptive reuse sentences in reusable_helper_instructions are removed",
        "unchanged": ["all helper algorithm bytes", "original task text and inputs", "candidate scopes and protected files",
            "registered public checks", "C0 structured actions", "free model identity and every-call credit validation",
            "images and original graders", "one fresh persistent native session", "500 requests/3600 seconds/64k output"],
        "hypothesis": "Explicit early reuse can avoid unnecessary rewrites; success and complete request/token/time costs are measured independently",
        "task_selection": "The three existing public-helper families, selected by mechanism, previously exposed development tasks",
        "counterevidence": "Equal or better ablated results limit the incremental claim for explicit reuse guidance; retain every actual outcome",
        "claims_excluded": ["helper availability ablation", "automatic control ablation", "unseen-task generalization", "a full75 result for this three-task ablation"],
        "runtime_root": str(runtime.relative_to(root)), "manifest": str(manifest.relative_to(root)),
        "checks": str(checks.relative_to(root)), "driver": parent["driver_path"], "resource_driver": parent["resource_driver"],
        "queue": queue, "artifact_capture_policy": str(capture_policy.relative_to(root)),
        "image_copy_driver": parent["image_copy_driver"],
        "core_queues": {"main": str(main_queue.relative_to(root)), "repeat": read(args.repeat_plan)["queue"]},
        "task_ids": ids, "pins": {task: pins[task] for task in ids}, "limits": parent["limits"],
        "main_references": references, "actual_source_differences": changed,
        "changed_behavior_functions": ["reusable_helper_instructions"], "new_model_calls_during_preparation": 0,
        "all_files_sha256": {str(path.relative_to(root)): digest(path) for path in files}}
    with (destination / "plan.json").open("x") as handle:
        handle.write(json.dumps(plan, indent=2) + "\n")
    print(json.dumps({"tasks": 3, "changed_behavior_functions": 1, "new_model_calls": 0}), flush=True)


if __name__ == "__main__":
    main()
