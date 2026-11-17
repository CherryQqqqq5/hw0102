import argparse
import hashlib
import importlib.metadata
import json
import os
import shutil
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from course_eval.agent import RunLimits
from course_eval.boyue_transport import BoyueTransport
from course_eval.confirmation_selection import SEED, order


RUNTIME_FILES = ("agent.py", "benchmarks.py", "candidate_io.py", "controller.py", "docker_target.py",
                 "harbor_agent.py", "verification.py", "terminal_setup.py", "terminal_runtime.py", "aider_runtime.py",
                 "terminal-no-network.yaml", "confirmation.py", "boyue_transport.py", "boyue_rpc.py",
                 "codebuddy_free.py", "action_output.py")
LIMITS = RunLimits(model_calls=24, wall_seconds=600, command_seconds=60, timeout_retries=2, strict_wall=True)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sequence(tasks):
    arms = ("B0", "C0", "C1")
    ordered = sorted(tasks, key=lambda task: order("execution/" + task["id"]))
    slots = []
    for repeat in range(1, 4):
        for index, task in enumerate(ordered):
            shift = (index + repeat - 1) % 3
            for arm in arms[shift:] + arms[:shift]:
                slots.append({"task": task["id"], "benchmark": task["benchmark"], "arm": arm,
                              "repeat": repeat, "run_id": f"C-{task['benchmark']}-{task['id'].replace('/', '__')}-{arm}-r{repeat}"})
    return slots


def prepare(manifest_path, checks_path, preflights, destination, attempt_cap=300):
    if not 270 <= attempt_cap <= 300:
        raise ValueError("Attempt cap must cover 270 positions and stay within 300")
    manifest = json.loads(manifest_path.read_text())
    tasks = manifest["selected"]
    if Counter(task["benchmark"] for task in tasks) != {"swe": 10, "terminal": 10, "aider": 10}:
        raise ValueError("Confirmation requires ten tasks per benchmark")
    if manifest["stage"] != "frozen":
        raise ValueError("Environment-verified task manifest must be frozen first")
    if len({task["group"] for task in tasks}) != 30:
        raise ValueError("Duplicate task families")
    checks = json.loads(checks_path.read_text())
    for task in tasks:
        result = json.loads((preflights / task["id"].replace("/", "__") / "preflight.json").read_text())
        if (result["original_starter"]["passed"] is not False or result["upstream_reference"]["passed"] is not True):
            raise ValueError("Invalid original grader controls: " + task["id"])
        if not checks.get(task["id"]):
            raise ValueError("Missing frozen public check: " + task["id"])
    backend = os.environ["COURSE_MODEL_BACKEND"]
    provider = {}
    if backend == "codebuddy":
        provider["codebuddy_version"] = subprocess.check_output(
            [os.environ["COURSE_CODEBUDDY_BIN"], "--version"], text=True).strip()
    elif backend == "course":
        provider["provider_profile"] = BoyueTransport().metadata()
        if provider["provider_profile"]["runtime_sha256"] != digest(Path(__file__).with_name("boyue_rpc.py")):
            raise ValueError("Remote provider entry point differs from the local source")
    else:
        raise ValueError("Unsupported confirmation backend")
    limits = RunLimits.model_validate_json(os.environ.get("COURSE_RUN_LIMITS", LIMITS.model_dump_json()))
    plan = {"stage": "frozen_before_first_model_request", "created_utc": datetime.now(timezone.utc).isoformat(),
            "seed": SEED, "model": os.environ["COURSE_MODEL_ID"], "backend": os.environ["COURSE_MODEL_BACKEND"],
            **provider, "limits": limits.model_dump(), "workers": 1, "planned_trials": 270, "max_total_attempts": attempt_cap,
            "python_version": sys.version,
            "package_versions": {name: importlib.metadata.version(name) for name in (
                "mini-swe-agent", "swebench", "harbor", "pydantic", *(
                    ("mcp",) if backend == "codebuddy" and os.environ["COURSE_MODEL_ID"] == "hy4flash-free" else ()))},
            "max_extra_mechanical_attempts_per_slot": 2,
            "manifest_sha256": digest(manifest_path), "checks_sha256": digest(checks_path),
            "runtime_sha256": {name: digest(Path(__file__).parent / name) for name in RUNTIME_FILES},
            "slots": sequence(tasks)}
    with destination.open("x") as handle:
        json.dump(plan, handle, indent=2)
        handle.write("\n")


def execute(args):
    plan = json.loads(args.plan.read_text())
    if (digest(args.manifest) != plan["manifest_sha256"] or digest(args.checks) != plan["checks_sha256"]
            or any(digest(Path(__file__).parent / name) != checksum for name, checksum in plan["runtime_sha256"].items())):
        raise ValueError("Frozen protocol or execution code differs")
    tracked_plan = subprocess.check_output(["git", "show", args.protocol_commit + ":" + args.published_plan],
                                           cwd=args.published_repo)
    if tracked_plan != args.plan.read_bytes():
        raise ValueError("Protocol commit does not contain the exact run plan")
    if os.environ["COURSE_MODEL_ID"] != plan["model"] or os.environ["COURSE_MODEL_BACKEND"] != plan["backend"]:
        raise ValueError("Model configuration differs from frozen protocol")
    if plan["backend"] == "codebuddy":
        version = subprocess.check_output([os.environ["COURSE_CODEBUDDY_BIN"], "--version"], text=True).strip()
        if version != plan["codebuddy_version"]:
            raise ValueError("CodeBuddy version changed")
    elif BoyueTransport().metadata() != plan["provider_profile"]:
        raise ValueError("Remote provider runtime changed")
    if sys.version != plan["python_version"] or any(importlib.metadata.version(name) != version
                                                   for name, version in plan["package_versions"].items()):
        raise ValueError("Frozen Python runtime dependencies changed")
    tasks = json.loads(args.manifest.read_text())["selected"]
    for task in tasks:
        image = task.get("image") or "nju-course-aider:" + task["stratum"]
        image_id = subprocess.check_output([os.environ["COURSE_DOCKER_BIN"], "image", "inspect", "--format", "{{.Id}}", image], text=True).strip()
        if image_id != task["image_id"]:
            raise ValueError("Frozen container image changed: " + task["id"])
    args.runs.mkdir(parents=True, exist_ok=True)
    archive = args.runs.with_name(args.runs.name + "-attempts")
    if args.recover:
        if not args.recovery_reason:
            raise ValueError("Recovery requires a documented mechanical cause")
        if args.recover not in {slot["run_id"] for slot in plan["slots"]}:
            raise ValueError("Recovery is outside the frozen matrix")
        original = args.runs / args.recover
        result = json.loads((original / "result.json").read_text())
        if result.get("scoreable"):
            raise ValueError("A scored semantic outcome cannot be rerun")
        previous = len(list(archive.glob(args.recover + "-attempt*")))
        if previous >= plan["max_extra_mechanical_attempts_per_slot"]:
            raise ValueError("Mechanical attempt allowance exhausted")
        archive.mkdir(exist_ok=True)
        destination = archive / (args.recover + f"-attempt{previous + 1}")
        shutil.move(str(original), destination)
        (destination / "recovery.json").write_text(json.dumps({"reason": args.recovery_reason,
            "time_utc": datetime.now(timezone.utc).isoformat(), "protocol_commit": args.protocol_commit}, indent=2) + "\n")
    environment = os.environ | {"COURSE_RUN_LIMITS": json.dumps(plan["limits"]),
                                 "COURSE_PROTOCOL_COMMIT": args.protocol_commit}
    for slot in plan["slots"]:
        directory = args.runs / slot["run_id"]
        if slot.get("source_protocol_commit") and not directory.exists():
            raise ValueError("Declared reused record is missing: " + slot["run_id"])
        if directory.exists():
            result = json.loads((directory / "result.json").read_text())
            trial = json.loads((directory / "trial.json").read_text())
            expected_commit = slot.get("source_protocol_commit", args.protocol_commit)
            if (not result["scoreable"] or trial.get("protocol_commit") != expected_commit
                    or trial["limits"] != plan["limits"]):
                raise ValueError("Unscored or mismatched position requires diagnosis: " + slot["run_id"])
            continue
        attempts = len(list(args.runs.glob("*/trial.json"))) + len(list(archive.glob("*/trial.json")))
        if attempts >= plan["max_total_attempts"]:
            raise RuntimeError("Frozen attempt cap reached")
        print("START " + slot["run_id"], flush=True)
        result = subprocess.run([sys.executable, "-m", "course_eval.benchmarks", "--manifest", str(args.manifest),
            "--sources", str(args.sources), "--checks", str(args.checks), "--id", slot["task"],
            "--configuration", slot["arm"], "--run-dir", str(directory)], env=environment, check=False)
        scored = json.loads((directory / "result.json").read_text())
        if result.returncode or not scored["scoreable"]:
            raise RuntimeError("Unscored position; inspect preserved attempt: " + slot["run_id"])
        print(f"DONE {slot['run_id']} passed={scored['passed']}", flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--checks", type=Path, required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--sources", type=Path, default=Path("work/datasets"))
    parser.add_argument("--preflights", type=Path)
    parser.add_argument("--runs", type=Path)
    parser.add_argument("--protocol-commit")
    parser.add_argument("--published-repo", type=Path, default=Path("work/hw0102-publish"))
    parser.add_argument("--published-plan", default="作业二/configs/confirmation-plan-v1.json")
    parser.add_argument("--attempt-cap", type=int, default=300)
    parser.add_argument("--recover")
    parser.add_argument("--recovery-reason")
    args = parser.parse_args()
    if args.preflights:
        prepare(args.manifest, args.checks, args.preflights, args.plan, args.attempt_cap)
    else:
        if not args.runs or not args.protocol_commit:
            parser.error("Execution requires --runs and --protocol-commit")
        execute(args)


if __name__ == "__main__":
    main()
