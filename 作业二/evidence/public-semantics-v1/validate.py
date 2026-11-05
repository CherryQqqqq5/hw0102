import copy
import importlib.util
import json
import math
import os
import pathlib
import shutil
import subprocess
import sys

from course_eval.public_semantics import capture_baseline, check_scheduler, read_jsonl, scheduler_metrics


ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = pathlib.Path(__file__).resolve().parent
DOCKER = os.environ["COURSE_DOCKER_BIN"]
DATA = ROOT / "work/datasets/terminal-bench-2-1-7131e4375048a0e408a8fb404b5f499d726b695b/tasks"
HISTORY = ROOT / "work/vmshare/revision-jsonlines-recovery-v2"
CASES = {"B0": "llm-inference-batching-scheduler__KaMs9vc",
         "RP": "llm-inference-batching-scheduler__Z7XZgu5"}
checks = []


def run(*args, success=True, timeout=180):
    completed = subprocess.run([str(value) for value in args], capture_output=True,
                               text=True, timeout=timeout)
    if success and completed.returncode:
        raise RuntimeError(f"Command failed: {args}: {completed.stderr}")
    return completed


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def require(name, predicate):
    if not predicate:
        raise AssertionError(name)
    checks.append(name)
    print(name, flush=True)


def condition(report, key):
    return next(item for item in report["conditions"] if item["id"] == key)


def copy_checker(container):
    run(DOCKER, "exec", container, "mkdir", "-p", "/opt/public-checker")
    for name in ("public_semantics.py", "check_public_semantics.py"):
        run(DOCKER, "cp", ROOT / "course_eval" / name, f"{container}:/opt/public-checker/{name}")


def scheduler_replays():
    source = DATA / "llm-inference-batching-scheduler/environment/task_file"
    module_spec = importlib.util.spec_from_file_location("public_original_cost_model", source / "scripts/cost_model.py")
    public_model = importlib.util.module_from_spec(module_spec)
    sys.modules[module_spec.name] = public_model
    module_spec.loader.exec_module(public_model)
    baseline = capture_baseline("scheduler", source)
    for arm, trial in CASES.items():
        directory = OUT / arm
        directory.mkdir(exist_ok=True)
        path = HISTORY / f"D-terminal-llm-inference-batching-scheduler-{arm}-r1" / trial / "agent/tools.jsonl"
        events = [json.loads(line) for line in path.read_text().splitlines()]
        event = next(item for item in events if item["tool_call_id"] == "codebuddy-7")
        command = event["command"]
        require(arm + ": replay command has no prohibited paths", "/tmp" not in command and "/tests" not in command and "/solution/" not in command)
        # 保存原日志中的完整命令，不修改候选算法或历史输出。
        (directory / "original-command.sh").write_text(command + "\n")
        save(directory / "provenance.json", {"kind": "reconstructed_from_logged_command",
                                             "source": str(path.relative_to(ROOT)),
                                             "event_id": "codebuddy-7", "logged_returncode": event["returncode"],
                                             "historical_deliverables_saved": False,
                                             "logged_stdout": event["stdout"]})
        save(directory / "baseline.json", baseline)
        container = "course-public-semantics-" + arm.lower()
        run(DOCKER, "run", "-d", "--platform", "linux/amd64", "--network", "none",
            "--name", container, "--entrypoint", "sleep",
            "alexgshaw/llm-inference-batching-scheduler:20251031", "infinity")
        try:
            copy_checker(container)
            run(DOCKER, "exec", container, "mkdir", "-p", "/app/work")
            run(DOCKER, "cp", directory / "original-command.sh", f"{container}:/app/work/replay.sh")
            replay = run(DOCKER, "exec", container, "bash", "/app/work/replay.sh")
            (directory / "replay.stdout").write_text(replay.stdout)
            (directory / "replay.stderr").write_text(replay.stderr)
            run(DOCKER, "cp", directory / "baseline.json", f"{container}:/opt/public-checker/baseline.json")
            checked = run(DOCKER, "exec", container, "python3", "/opt/public-checker/check_public_semantics.py",
                          "scheduler", "--baseline", "/opt/public-checker/baseline.json", success=False)
            report = json.loads(checked.stdout)
            save(directory / "public-check.json", report)
            require(arm + ": structured checker exit status", checked.returncode == (0 if report["passed"] else 1))
            shape_count = condition(report, "scheduler.global_shape_cap")["actual"]
            require(arm + ": expected global shape count", shape_count == (13 if arm == "B0" else 7))
            failures = [item["id"] for item in report["conditions"] if not item["passed"]]
            require(arm + ": expected hard-condition outcome", failures == (["scheduler.global_shape_cap"] if arm == "B0" else []))
            replay_root = directory / "task_file"
            run(DOCKER, "cp", f"{container}:/app/task_file", replay_root)
            for bucket in (1, 2):
                requests = {row["request_id"]: row for row in read_jsonl(replay_root / f"input_data/requests_bucket_{bucket}.jsonl")}
                plan = read_jsonl(replay_root / f"output_data/plan_b{bucket}.jsonl")
                expected = public_model.CostModel(64).plan_metrics(requests, plan)
                actual = scheduler_metrics(requests, plan)
                require(f"{arm}: bucket {bucket} reproduces public cost model", all(math.isclose(actual[key], expected[key], rel_tol=1e-12, abs_tol=1e-8) for key in ("cost", "pad_ratio", "p95_latency_ms", "sequential_timecost", "pad_tokens", "real_tokens")))
        finally:
            run(DOCKER, "rm", "-f", container)
    return baseline


def scheduler_mutations(baseline):
    root = OUT / "mutations"
    shutil.copytree(OUT / "RP/task_file", root, dirs_exist_ok=True)
    plan_path = root / "output_data/plan_b1.jsonl"
    original = plan_path.read_text()
    rows = read_jsonl(plan_path)
    cases = [
        ("duplicate_request", lambda data: data.append(copy.deepcopy(data[0])), "request_coverage"),
        ("missing_request", lambda data: data.pop(), "request_coverage"),
        ("wrong_heads", lambda data: data[0]["shape"].update(heads_align=16), "fixed_dimensions"),
        ("unaligned_shape", lambda data: data[0]["shape"].update(seq_align=65), "seq_alignment"),
        ("small_shape", lambda data: data[0]["shape"].update(seq_align=0), "prompt_coverage"),
        ("boolean_shape", lambda data: data[0]["shape"].update(seq_align=True), "jsonl_schema"),
    ]
    for name, mutate, key in cases:
        candidate = copy.deepcopy(rows)
        mutate(candidate)
        plan_path.write_text("".join(json.dumps(row) + "\n" for row in candidate))
        report = check_scheduler(root, baseline)
        require(name + ": rejected by named condition", not report["passed"] and not condition(report, "scheduler.bucket_1." + key)["passed"])
    plan_path.write_text(original)
    input_path = root / "input_data/requests_bucket_1.jsonl"
    input_path.write_text(input_path.read_text() + " ")
    report = check_scheduler(root, baseline)
    require("input byte mutation: rejected", not condition(report, "scheduler.input_data_unchanged")["passed"])


def cached_scheduler():
    source = DATA / "llm-inference-batching-scheduler/environment/task_file"
    module_spec = importlib.util.spec_from_file_location("public_original_cost_model", source / "scripts/cost_model.py")
    public_model = importlib.util.module_from_spec(module_spec)
    sys.modules[module_spec.name] = public_model
    module_spec.loader.exec_module(public_model)
    baseline = capture_baseline("scheduler", source)
    for arm in CASES:
        replay_root = OUT / arm / "task_file"
        report = check_scheduler(replay_root, baseline)
        save(OUT / arm / "public-check-current.json", report)
        failures = [item["id"] for item in report["conditions"] if item["passed"] is False]
        require(arm + ": cached replay outcome", failures == (["scheduler.global_shape_cap"] if arm == "B0" else []))
        require(arm + ": cached replay shape count", condition(report, "scheduler.global_shape_cap")["actual"] == (13 if arm == "B0" else 7))
        checked = run(ROOT / "work/.venv/bin/python", ROOT / "course_eval/check_public_semantics.py", "scheduler", "--root", replay_root,
                      "--baseline", OUT / arm / "baseline.json", success=False)
        require(arm + ": final CLI exit code", checked.returncode == (1 if arm == "B0" else 0))
        for bucket in (1, 2):
            requests = {row["request_id"]: row for row in read_jsonl(replay_root / f"input_data/requests_bucket_{bucket}.jsonl")}
            plan = read_jsonl(replay_root / f"output_data/plan_b{bucket}.jsonl")
            expected = public_model.CostModel(64).plan_metrics(requests, plan)
            actual = scheduler_metrics(requests, plan)
            require(f"{arm}: bucket {bucket} public formula equivalence", all(math.isclose(actual[key], expected[key], rel_tol=1e-12, abs_tol=1e-8) for key in ("cost", "pad_ratio", "p95_latency_ms", "sequential_timecost", "pad_tokens", "real_tokens")))
    return baseline


if __name__ == "__main__":
    baseline = cached_scheduler()
    scheduler_mutations(baseline)
    save(OUT / "scheduler-validation.json", {"passed": True, "model_calls": 0, "checks": checks})
    print(json.dumps({"passed": True, "checks": len(checks), "model_calls": 0}))
