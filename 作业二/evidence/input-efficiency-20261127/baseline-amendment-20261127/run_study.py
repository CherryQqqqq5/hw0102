import argparse
import hashlib
import json
import os
import subprocess
from contextlib import closing
from pathlib import Path

import docker

from scripts.export_performance_evidence import inspect_run
from scripts.summarize_performance_comparison import control_artifact_metrics
from course_eval.resource_pool import ResourceLease


ROOT = Path.cwd()
FOLDER = Path(__file__).parent.resolve()
RUNTIME = FOLDER / "runtime"
PYTHON = ROOT / "work/.venv/bin/python"
COMMON = ("\nCreate .course-public-check/check.py containing an executable reproducer and meaningful "
    "assertions derived from the visible task requirements. Run it before submission, include boundary "
    "cases and existing regression tests where relevant. A check must fail when its assertions are unmet; "
    "do not replace assertions with unconditional success. Preserve original tests and test configuration. "
    "The independent original benchmark grader determines the task outcome.\n\n")


def read(path):
    return json.loads(path.read_text())


def save(path, value):
    temporary = path.with_suffix(path.suffix + ".writing")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def hashes():
    paths = list((RUNTIME / "course_eval").rglob("*.py"))
    paths += [Path(__file__), FOLDER / "run_trial.py", FOLDER / "run_registered.py", FOLDER / "analyze_study.py", FOLDER / "candidate-tasks.json",
        FOLDER / "execution.json", FOLDER / "free-model-metadata/cloud-model-metadata.json"]
    paths += list((FOLDER / "preparation").glob("*/manifest.json"))
    paths += list((FOLDER / "preparation").glob("*/config.json"))
    paths += [ROOT / "scripts" / name for name in ("export_performance_evidence.py", "run_performance_queue.py",
        "summarize_performance_comparison.py")]
    paths += [FOLDER / name for name in ("prepare_runtime.py", "finalize_execution.py", "qualify_output.py")]
    return {str(path.relative_to(ROOT)): digest(path) for path in sorted(paths)}


def environment(task, arm):
    execution = read(FOLDER / "execution.json")
    endpoint = os.environ["COURSE_STUDY_DOCKER_HOST"]
    with closing(docker.DockerClient(base_url=endpoint, timeout=60)) as client:
        actual = client.info()
    if (execution["status"] != "PASS" or actual["ID"] != execution["docker_id"]
            or actual["Architecture"] != "x86_64" or execution["task_network"] != "none"):
        raise RuntimeError("The actual execution daemon differs from its qualified ModelArts environment")
    result = os.environ | {"PYTHONPATH": str(RUNTIME) + os.pathsep + str(ROOT),
        "PATH": str(ROOT / "work/vendor/docker") + os.pathsep + os.environ["PATH"],
        "DOCKER_HOST": endpoint, "DOCKER_CONFIG": str(ROOT / "work/docker-config"),
        "COURSE_DOCKER_BIN": str(ROOT / "work/vendor/docker/docker"),
        "COURSE_AIDER_PLATFORM": "linux/amd64",
        "COURSE_AIDER_PUBLIC_PYTHON": str(ROOT / "work/terminal-runtime/python-3.13.12-linux-x86_64.tar.gz"),
        "COURSE_FREE_STOP_PATH": str(ROOT / "work/performance-stop-20261122.json"),
        "COURSE_DSH_REMOTE_RUNTIME": execution["dsh_runtime_guest_path"],
        "COURSE_CODEBUDDY_GUARDED_BIN": execution["free_client_entry"],
        "COURSE_CODEBUDDY_RELAY_SOCKET": execution["free_client_socket"],
        "COURSE_CODEBUDDY_RELAY_CLIENT_SHA256": execution["free_client_sha256"],
        "MSWEA_GLOBAL_CONFIG_DIR": str(ROOT / "work/miniswe-config"), "MSWEA_SILENT_STARTUP": "1",
        "COURSE_COMMON_TASK_INSTRUCTION": COMMON if task["benchmark"] == "swe" else "",
        "COURSE_ENVIRONMENT_CONTEXT": "0" if arm == "base" else "1",
        "COURSE_TOOL_OUTPUT_POLICY": "digest" if arm == "digest" else "archive",
        "COURSE_COMPACT_SUCCESS_FEEDBACK": "0", "TMPDIR": str(ROOT / "work/process-tmp")}
    if arm == "dsh":
        result.pop("COURSE_TOOL_OUTPUT_POLICY", None)
    return result


def prepare(task):
    folder = FOLDER / "preparation" / task["id"]
    prepared = read(folder / "record.json")
    if prepared["status"] != "ready":
        raise RuntimeError("The original task image has not been prepared")
    preflight = FOLDER / "preflight" / task["id"]
    if not preflight.exists():
        preflight.parent.mkdir(parents=True, exist_ok=True)
        with ResourceLease(FOLDER / "resources", exclusive=True, label="original-control-" + task["id"]), \
                preflight.with_suffix(".log").open("x") as log:
            subprocess.run([str(PYTHON), "-m", "course_eval.preflight", "--manifest",
                str(FOLDER / "candidate-tasks.json"), "--sources", str(ROOT / "work/datasets"),
                "--id", task["id"], "--out", str(preflight)], cwd=RUNTIME, env=environment(task, "base"),
                stdout=log, stderr=subprocess.STDOUT, check=True)
    controls = read(preflight / "preflight.json")
    if (controls["original_starter"].get("passed") is not False
            or controls["upstream_reference"].get("passed") is not True
            or not all(controls[key]["scoreable"] for key in ("original_starter", "upstream_reference"))):
        raise RuntimeError("The original scorer must reject the starter and accept its upstream reference")
    inputs = FOLDER / "inputs" / task["id"]
    inputs.mkdir(parents=True, exist_ok=True)
    manifest = inputs / "task.json"
    checks = inputs / "checks.json"
    expected = {"stage": "frozen", "revisions": read(FOLDER / "candidate-tasks.json")["revisions"],
        "selected": [task], "original_image_id": prepared["image_id"],
        "original_manifest_digest": prepared.get("manifest_digest")}
    expected_checks = {} if task["benchmark"] == "aider" else {task["id"]: [{
        "check_id": "agent-check", "source_quote": "Create .course-public-check/check.py",
        "command": "/opt/miniconda3/envs/testbed/bin/python .course-public-check/check.py",
        "dependencies": [".course-public-check/check.py"],
        "coverage": ["Agent-authored visible-task reproducer and assertions"], "timeout_seconds": 120}]}
    for path, value in ((manifest, expected), (checks, expected_checks)):
        if path.exists() and read(path) != value:
            raise RuntimeError("The registered task input changed: " + str(path))
        if not path.exists():
            save(path, value)
    admission = {str(path.relative_to(ROOT)): digest(path)
        for path in (manifest, checks, preflight / "preflight.json", folder / "record.json")}
    path = inputs / "admission.json"
    if path.exists() and read(path) != admission:
        raise RuntimeError("The qualified task admission changed")
    if not path.exists():
        save(path, admission)
    return manifest, checks


def inspect(task, arm, directory):
    framework = "dsh" if arm == "dsh" else "mini-swe"
    row = inspect_run(directory, framework)
    protocol = read(directory.with_suffix(".protocol.json"))
    trial = read(directory / "trial.json")
    policy = None if arm == "dsh" else "digest" if arm == "digest" else "archive"
    instruction = COMMON if task["benchmark"] == "swe" else ""
    if (trial["task"] != task or trial["configuration"] != ("B0" if arm == "dsh" else "C0")
            or trial["limits"] != protocol["limits"]
            or protocol["model"] != "hy4flash-free" or protocol["backend"] != "codebuddy"
            or protocol["framework"] != framework or not protocol["persistent_native_session"]
            or protocol["environment_context"] != (arm != "base")
            or protocol["tool_output_policy"] != policy
            or protocol["compact_success_feedback"]
            or protocol["common_instruction_sha256"] != hashlib.sha256(instruction.encode()).hexdigest()
            or protocol["limits"] != read(FOLDER / "candidate-tasks.json")["limits"] | {"strict_wall": True}):
        raise RuntimeError("The completed position differs from its frozen protocol")
    budget, = directory.rglob("execution-budget.json")
    events = [json.loads(line) for path in directory.rglob("model.jsonl") for line in path.read_text().splitlines()]
    sessions = sorted({event["native_session_id"] for event in events if event["event"] == "request"})
    return row | control_artifact_metrics(directory, framework, trial["configuration"]) | {
        "arm": arm, "benchmark": task["benchmark"], "run_dir": str(directory),
        "agent_seconds": read(budget)["elapsed_seconds"],
        "total_tokens": row["input_tokens"] + row["output_tokens"], "native_sessions": sessions}


def run(task, arm, stage):
    manifest, checks = prepare(task)
    plan = read(FOLDER / "study-plan.json")
    if plan["source_hashes"] != hashes():
        raise RuntimeError("The frozen runtime or model inputs changed")
    directory = FOLDER / ("repeat" if stage == "repeat" else "trials") / task["id"] / arm
    if not directory.exists():
        phase = read(Path(read(FOLDER / "execution.json")["guest_state_path"]))
        if phase["restricted"] is not True or phase["stage"] != "qualified_tcg_guest_small_container_only":
            raise RuntimeError("The actual guest is in preparation mode; model execution remains disabled")
        if read(ROOT / "work/performance-stop-20261122.json")["active"]:
            raise RuntimeError("New model requests remain stopped for an unresolved fee")
        directory.parent.mkdir(parents=True, exist_ok=True)
        print(json.dumps({"task": task["id"], "arm": arm, "stage": stage, "status": "starting"}), flush=True)
        with ResourceLease(FOLDER / "resources", exclusive=True, label="trial-" + task["id"] + "-" + arm):
            subprocess.run([str(PYTHON), str(FOLDER / "run_trial.py"), "--task", task["id"],
                "--manifest", str(manifest), "--checks", str(checks), "--configuration", "B0" if arm == "dsh" else "C0",
                "--runtime-root", str(RUNTIME), "--run-dir", str(directory), "--persistent-session",
                "--framework", "dsh" if arm == "dsh" else "mini-swe"], env=environment(task, arm), check=True)
    row = inspect(task, arm, directory)
    for previous in list((FOLDER / "trials").rglob("*.audited.json")) + list((FOLDER / "repeat").rglob("*.audited.json")):
        if previous != directory.with_suffix(".audited.json"):
            if set(row["native_sessions"]) & set(read(previous)["native_sessions"]):
                raise RuntimeError("Independent positions reused the same native model session")
    save(directory.with_suffix(".audited.json"), row)
    print(json.dumps(row, ensure_ascii=False), flush=True)
    return row


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--task")
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--freeze", action="store_true")
    parser.add_argument("--stage", choices=("diagnostic", "confirmation", "repeat"), default="diagnostic")
    parser.add_argument("--arm", choices=("base", "environment", "digest", "dsh"))
    args = parser.parse_args()
    candidate = read(FOLDER / "candidate-tasks.json")
    if args.freeze:
        plan = {"stage": "frozen_before_generation", "source_hashes": hashes(),
            "registered_design": candidate, "aider_common_instruction": "", "swe_common_instruction": COMMON,
            "single_primary_variable": "new successful long tool output presentation; full log recall in both C0 arms"}
        path = FOLDER / "study-plan.json"
        if path.exists() and read(path) != plan:
            raise RuntimeError("A different study is already frozen")
        save(path, plan)
        return
    task, = [task for task in candidate["selected"] if task["id"] == args.task]
    if args.prepare_only:
        prepare(task)
        print(json.dumps({"task": task["id"], "qualified_original_scorer": True}), flush=True)
        return
    diagnostic = args.task in candidate["diagnostic_ids"]
    if diagnostic != (args.stage == "diagnostic"):
        raise ValueError("The task is outside the registered stage")
    digest_qualified = True
    if args.stage != "diagnostic":
        results = [read(FOLDER / "trials" / name / (arm + ".audited.json"))
            for name in candidate["diagnostic_ids"] for arm in ("base", "environment", "digest")]
        digest_qualified = all(row["passed"] and row["final_valid_verification"]
            for row in results if row["arm"] == "digest")
        if args.arm == "digest" and not digest_qualified:
            raise RuntimeError("Digest did not qualify for fresh confirmation")
    if args.stage == "repeat" and not (FOLDER / "repeat-plan.json").is_file():
        raise RuntimeError("Select and freeze the registered repeat configuration first")
    arms = [args.arm] if args.arm else (["base", "environment", "digest"] if diagnostic
        else ["dsh", "environment"] + (["digest"] if digest_qualified else []))
    if not args.arm:
        positions = candidate["diagnostic_ids"] if diagnostic else candidate["confirmation_ids"]
        offset = positions.index(args.task) % len(arms)
        arms = arms[offset:] + arms[:offset]
    if args.stage == "repeat":
        expected_arm = read(FOLDER / "repeat-plan.json")["configuration_by_task"][task["id"]]
        if arms != [expected_arm]:
            raise ValueError("Repeat must use exactly the preselected configuration for this task")
    for arm in arms:
        run(task, arm, args.stage)


if __name__ == "__main__":
    main()
