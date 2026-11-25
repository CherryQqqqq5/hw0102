import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FOLDER = Path(__file__).resolve().parent
PLAN = FOLDER / "frozen/plan.json"
TASK = "pytest-dev__pytest-5631"


def read(path):
    return json.loads(path.read_text())


def read_in_progress(path):
    for attempt in range(3):
        try:
            return read(path)
        except json.JSONDecodeError:
            if attempt == 2:
                raise
            time.sleep(0.2)


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def object_sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def write(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def prepare():
    parent_folder = ROOT / "work/parallel-free-evaluation-20261124/final-sql75-quota-recovered"
    parents = {arm: read(parent_folder / (arm + "-plan.json")) for arm in ("main", "repeat")}
    parent = parents["main"]
    proof_path = FOLDER / "qualification/result.json"
    proof = read(proof_path)
    review_path = FOLDER / "completed-qualification-review.json"
    review = read(review_path)
    if (proof["phase"] != "actual_unchanged_c0_public_check_and_protected_guard_qualified"
            or proof["new_model_calls"] != 0 or proof["new_original_grader_calls"] != 0
            or review["status"] != "APPROVE" or review["blocking_findings"]
            or review["qualification_sha256"] != sha(proof_path)):
        raise ValueError("The actual unchanged protection/check qualification needs source review")
    if {row["variant"]: (row["state"], row["final"]["protected_unchanged"]) for row in proof["variants"]} != {
            "base": ("failed", True), "recorded_full_candidate": ("protected_dependency_changed", False),
            "recorded_production_only": ("passed", True)}:
        raise ValueError("The qualification did not distinguish the actual preservation violation")
    bindings = dict(proof["source_files_sha256"])
    tasks_path, checks_path = parent_folder / "tasks.json", parent_folder / "checks.json"
    tasks, original_checks = read(tasks_path), read(checks_path)
    manifest, checks = FOLDER / "inputs/tasks.json", FOLDER / "inputs/checks.json"
    task, = read(manifest)["selected"]
    proposed_checks = read(checks)
    if task not in tasks["selected"] or task["id"] != TASK:
        raise ValueError("The public guidance may not change the original task")
    before, = original_checks[TASK]
    after, = proposed_checks[TASK]
    if ({key: value for key, value in before.items() if key != "coverage"}
            != {key: value for key, value in after.items() if key != "coverage"}
            or after["coverage"][:len(before["coverage"])] != before["coverage"]
            or len(after["coverage"]) != len(before["coverage"]) + 3):
        raise ValueError("Only the three reviewed task-local guidance entries may change")
    pins_path = ROOT / parent["baseline_queue"] / "environment-pins.json"
    pins = read(pins_path)["pins"]
    unchanged = {}
    for item in tasks["selected"]:
        name = item["id"]
        if name == TASK:
            continue
        if proposed_checks[name] != original_checks[name]:
            raise ValueError("Another task check changed")
        unchanged[name] = {"task_sha256": object_sha(item), "selected_checks_sha256": object_sha(original_checks[name]),
            "original_image_id": pins[name], "configuration": parent["configuration_by_task"][name]}
    runtime = Path(parent["runtime_root"])
    bindings.update({str((runtime / name).relative_to(ROOT)): expected for name, expected in
        (parent["runtime_sha256"] | parent["runtime_resources_sha256"]).items()})
    bindings.update(parent["request_guard_sha256"] | parent["image_preparation_sha256"])
    protocols = []
    for arm, source in parents.items():
        if (source["runtime_sha256"] != parent["runtime_sha256"] or source["limits"] != parent["limits"]
                or source["configuration_by_task"][TASK] != "C0"):
            raise ValueError("The source cohorts have different actual model conditions")
        directory = ROOT / source["queue"] / (TASK + "-C0-r" + str(source["repeat"]))
        protocol = directory.with_suffix(".protocol.json")
        protocols.append({key: value for key, value in read(protocol).items() if key != "historical_unknown_calls_preserved"})
        for path in (protocol, directory / "model.jsonl", directory / "tools.jsonl", directory / "candidate.patch",
                directory / "result.json", directory / "final-verification.json"):
            bindings[str(path.relative_to(ROOT))] = sha(path)
    if protocols[0] != protocols[1]:
        raise ValueError("The two retained original task protocols differ")
    paths = [Path(__file__).resolve(), proof_path, review_path, manifest, checks, tasks_path, checks_path, pins_path,
        ROOT / parent["driver_path"], ROOT / parent["resource_driver"],
        ROOT / "work/parallel-free-evaluation-20261124/resource_trial.py",
        ROOT / "work/parallel-free-evaluation-20261124/run_fixed_free_trials.py",
        ROOT / "scripts/export_performance_evidence.py", ROOT / "scripts/summarize_performance_comparison.py",
        ROOT / parent["artifact_capture_policy"], ROOT / "work/codebuddy/node_modules/@tencent-ai/codebuddy-code/dist/codebuddy-headless.js",
        ROOT / "work/free-channel-capabilities-20261122/cloud-model-metadata.json",
        ROOT / "work/vmshare/elf-public-check-deps/pyelftools-0.33-py3-none-any.whl"]
    paths += [parent_folder / (arm + "-plan.json") for arm in parents]
    paths += [path for path in (FOLDER / "qualification").rglob("*") if path.is_file()]
    bindings.update({str(path.relative_to(ROOT)): sha(path) for path in paths})
    for name, expected in bindings.items():
        if sha(ROOT / name) != expected:
            raise ValueError("A qualified or frozen source changed: " + name)
    PLAN.parent.mkdir()
    write(PLAN, {"stage": "frozen_after_actual_unchanged_check_and_protection_qualification", "phase": "RUN",
        "task": TASK, "prospective_trials": ["preserve-tests-main-r1", "preserve-tests-repeat-r2"],
        "main_variable": "Only three public coverage/guidance entries about scratch regression tests, exact preservation and official mock sentinel identity; actual check and protected scope unchanged",
        "runtime_root": str(runtime.relative_to(ROOT)), "limits": parent["limits"], "model": "hy4flash-free",
        "pin": pins[TASK], "manifest": str(manifest.relative_to(ROOT)), "checks": str(checks.relative_to(ROOT)),
        "expected_protocol": protocols[0], "driver": parent["driver_path"], "resource_driver": parent["resource_driver"],
        "image_copy_driver": parent["image_copy_driver"], "artifact_capture_policy": parent["artifact_capture_policy"],
        "queue": "work/vmshare/performance-pytest-preservation-v1-20261125",
        "unchanged_task_inputs": unchanged, "source_cohorts": {arm: source["queue"] for arm, source in parents.items()},
        "all_files_sha256": bindings, "new_model_calls_during_preparation": 0,
        "model_input_boundary": "Original public task/repository plus the unchanged check and three public guidance entries. Recorded candidate patches, engineering qualification artifacts and hidden scoring fixtures are never supplied to the model.",
        "failure": "Keep both valid outcomes; no score-based resampling; new missing or nonzero financial receipt stops dispatch",
        "integration_required": "This fifth task-local revision is not yet in the four-scope joint summary. Only after both actual sessions may the source-verified join use70x2 inherited records plus10 fixed revisions; retain original225, JSON development5 and guidance ablation3 (243 model-scored positions), with early SQL pilots/engineering/unscored attempts separate."})
    print(json.dumps({"status": "frozen", "prospective_sessions": 2, "bindings": len(bindings), "new_model_calls": 0}), flush=True)


def wait_and_run():
    import fcntl

    with (FOLDER / "runner.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        plan = read(PLAN)
        admission = read(FOLDER / "admission-review.json")
        if (admission["status"] != "APPROVE" or admission["blocking_findings"]
                or admission["plan_sha256"] != sha(PLAN) or admission["runner_sha256"] != sha(Path(__file__))):
            raise ValueError("The exact two-session experiment lacks independent admission")
        evidence = {"status": "waiting_for_original225_and_three_ablation_positions", "pid": os.getpid(), "new_model_calls_by_waiter": 0}
        state_path = FOLDER / "wait-state.json"
        state_path.write_text(json.dumps(evidence, indent=2) + "\n")
        started = time.monotonic()
        while time.monotonic() - started < 48 * 3600:
            stop = read(ROOT / "work/performance-stop-20261122.json")
            if stop["pending_unverified_calls"] or stop["accepted_total_unknown_calls"] != 25:
                raise RuntimeError("A new financial stop supersedes this prepared experiment")
            base = ROOT / "work/parallel-free-evaluation-20261124"
            core = read(base / "ready-queues-state.json")
            ablation_plan = base / "final-reuse-ablation/plan.json"
            if not stop["active"] and core.get("all_original225_present") and ablation_plan.exists():
                ablation_state = ROOT / read_in_progress(ablation_plan)["queue"] / "state.json"
                if ablation_state.exists() and read_in_progress(ablation_state).get("completed") == 3:
                    break
            time.sleep(30)
        else:
            raise TimeoutError("The bounded48-hour wait ended without all required original and ablation scores")
        for name, expected in plan["all_files_sha256"].items():
            if sha(ROOT / name) != expected:
                raise ValueError("A prospective source changed while waiting: " + name)
        command = [sys.executable, str(ROOT / "work/parallel-free-evaluation-20261124/run_fixed_free_trials.py"), "--plan", str(PLAN)]
        environment = os.environ | {"PYTHONPATH": str(ROOT)}
        with (FOLDER / "actual-fixed-trials.log").open("x") as log:
            subprocess.run([*command, "--validate-only"], cwd=ROOT, env=environment, stdout=log, stderr=subprocess.STDOUT, check=True)
            subprocess.run(command, cwd=ROOT, env=environment, stdout=log, stderr=subprocess.STDOUT, check=True)
        evidence.update(status="two_fixed_sessions_ended_require_actual_source_review_and_joint_integration")
        state_path.write_text(json.dumps(evidence, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("prepare", "wait"))
    args = parser.parse_args()
    prepare() if args.action == "prepare" else wait_and_run()
