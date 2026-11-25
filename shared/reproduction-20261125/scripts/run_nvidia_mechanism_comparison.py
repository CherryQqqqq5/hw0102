import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

os.environ.setdefault("MSWEA_GLOBAL_CONFIG_DIR", str(Path.cwd() / "work/miniswe-config"))
os.environ.setdefault("MSWEA_SILENT_STARTUP", "1")

from course_eval.nvidia_free import audit_nvidia_events
from course_eval.summarize import run_metrics
from scripts.run_performance_matrix import prepare_missing_image, release_scored_image
from scripts.summarize_performance_comparison import control_artifact_metrics


def read_json(path):
    return json.loads(path.read_text())


def digest(path):
    checksum = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            checksum.update(block)
    return checksum.hexdigest()


def save_json(path, value):
    temporary = path.with_suffix(".writing")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)


def verify_frozen(root, plan):
    if plan.get("eligible_for_matrix") is False:
        raise ValueError("The recorded actual admission rejected this model profile")
    source = read_json(root / plan["source_plan"])
    runtime = root / plan["runtime_root"]
    overrides = plan.get("runtime_sha256_overrides", {})
    if set(overrides) - {"course_eval/nvidia_free.py"}:
        raise ValueError("Only the declared NVIDIA reasoning-profile source may differ")
    expected = {runtime / name: value for name, value in
                (source["runtime_sha256"] | source["runtime_resources_sha256"] | overrides).items()}
    expected.update({root / plan.get("driver", "scripts/run_performance_trial.py"):
        plan.get("driver_sha256", source["driver_sha256"]),
        root / plan["manifest"]: source["tasks_sha256"],
        root / plan["checks"]: source["checks_sha256"],
        root / plan["environment_pins"]: plan["environment_pins_sha256"],
        root / plan["contract"]: source["contract_sha256"],
        root / plan["qualification"]: source["qualification_sha256"]})
    expected.update({root / name: checksum for name, checksum in plan.get("execution_files_sha256", {}).items()})
    for binding in plan.get("additional_runtime_bindings", []):
        other = read_json(root / binding["source_plan"])
        if other["model"] != source["model"] or other["limits"] != source["limits"]:
            raise ValueError("The native DSH runtime changed the model or comparison budgets")
        different = {name for name in source["runtime_sha256"] | other["runtime_sha256"]
                     if source["runtime_sha256"].get(name) != other["runtime_sha256"].get(name)}
        if different - {"course_eval/dsh_sandbox.py", "course_eval/dsh_runner.py", "course_eval/dsh_nvidia.py",
                        "course_eval/check_dsh_nvidia.py"}:
            raise ValueError("The DSH profile supplement changed shared inference, controller or scoring code")
        expected.update({root / binding["runtime_root"] / name: checksum for name, checksum in
                         (other["runtime_sha256"] | other["runtime_resources_sha256"]).items()})
        expected[root / other["driver"]] = other["driver_sha256"]
    if any(digest(path) != checksum for path, checksum in expected.items()):
        raise ValueError("A frozen model, runtime, task, check, driver or free-channel binding changed")
    for recovery in plan.get("mechanical_recoveries", {}).values():
        original = root / recovery["original_result"]
        outcome = read_json(original)
        if (outcome["scoreable"] is not False or outcome["passed"] is not None
                or digest(original) != recovery["original_result_sha256"]):
            raise ValueError("A mechanical replacement cannot discard or replace a valid original score")
    if plan.get("comparison_kind") == "complete75_matrix":
        expected_arms = [("main", "mini-swe", "C0", 1), ("dsh", "dsh", "B0", 1),
                         ("repeat", "mini-swe", "C0", 2), ("control", "mini-swe", "C1", 1)]
        arms = [(arm["id"], arm["framework"], arm["configuration"], arm["repetition"]) for arm in plan["arms"]]
        if (arms != expected_arms or len(plan["task_order"]) != 75
                or set(plan["task_order"]) != set(source["task_order"])
                or plan["configuration_by_task"] != source["configuration_by_task"]
                or plan["model"] != source["model"] or plan["limits"] != source["limits"]
                or plan["arms"][-1]["tasks"] != plan["mechanism_task_order"]
                or len(set(plan["mechanism_task_order"])) != 10
                or set(plan["mechanism_task_order"]) - set(plan["task_order"])):
            raise ValueError("The fixed full75, DSH, independent repeat or ten-task control plan changed")
        if any("tasks" in arm for arm in plan["arms"][:-1]):
            raise ValueError("Every primary comparison arm must cover all 75 original tasks")
        return
    full = plan.get("comparison_kind") == "complete75"
    framework = plan.get("framework", "mini-swe")
    expected_configurations = ["B0"] if framework == "dsh" else ["C0"] if full else ["C0", "C1"]
    if (plan["model"] != source["model"] or plan["limits"] != source["limits"]
            or plan["configurations"] != expected_configurations
            or len(set(plan["task_order"])) != plan["planned_pairs"]
            or framework not in {"mini-swe", "dsh"}):
        raise ValueError("The paired plan differs from its declared shared conditions")
    if full and (len(plan["task_order"]) != 75 or set(plan["task_order"]) != set(source["task_order"])):
        raise ValueError("The complete cohort must contain exactly the original 75 distinct tasks")
    if full and framework == "mini-swe" and plan.get("configuration_by_task") != source["configuration_by_task"]:
        raise ValueError("The full policy cohort must preserve every original task configuration")


def trial_directory(queue, task_id, configuration, plan):
    key = f"{task_id}:{plan.get('framework', 'mini-swe')}:{configuration}:{plan.get('repetition', 1)}"
    if key in plan.get("mechanical_recoveries", {}):
        return Path(plan["mechanical_recoveries"][key]["replacement_run"]).resolve()
    tag = "-" + plan["run_tag"] if plan.get("run_tag") else ""
    if plan.get("framework") == "dsh":
        tag += "-dsh"
    return queue / (task_id.replace("/", "-") + "-" + configuration + tag + "-r" + str(plan.get("repetition", 1)))


def scheduled_trials(plan, task_id):
    if plan.get("comparison_kind") == "complete75_matrix":
        for arm in plan["arms"]:
            if "tasks" in arm and task_id not in arm["tasks"]:
                continue
            configuration = (plan["configuration_by_task"][task_id] if arm["id"] in {"main", "repeat"}
                             else arm["configuration"])
            yield configuration, plan | {"framework": arm["framework"], "repetition": arm["repetition"],
                "runtime_root": arm.get("runtime_root", plan["runtime_root"])}, arm["id"]
    else:
        for configuration in plan["configurations"]:
            yield plan.get("configuration_by_task", {}).get(task_id, configuration), plan, configuration


def completed_result(root, plan, task, configuration, directory):
    score = read_json(directory / "result.json")
    trial = read_json(directory / "trial.json")
    protocol = read_json(directory.with_suffix(".protocol.json"))
    if (score["task"] != task["id"] or not score["scoreable"] or type(score["passed"]) is not bool
            or trial["task"] != task or trial["configuration"] != configuration
            or trial["model"] != plan["model"] or protocol["backend"] != plan["backend"]
            or trial.get("framework", "mini-swe") != plan.get("framework", "mini-swe")
            or protocol.get("framework", "mini-swe") != plan.get("framework", "mini-swe")
            or protocol["configuration"] != configuration or protocol["limits"] != plan["limits"]
            or protocol["reasoning_effort"] != plan.get("reasoning_effort", "high")
            or (root / protocol["runtime_root"]).resolve() != (root / plan["runtime_root"]).resolve()):
        raise ValueError("An actual trial lacks its original score or differs from the paired conditions")
    traces = list(directory.rglob("model.jsonl"))
    if len(traces) != 1:
        raise ValueError("An independent trial must have exactly one actual model trace")
    events = [json.loads(line) for line in traces[0].read_text().splitlines()]
    if any(row["payload"].get("reasoning_effort") != plan.get("reasoning_effort", "high")
           for row in events if row["event"] == "request"):
        raise ValueError("An actual model request differs from the frozen reasoning profile")
    billing = audit_nvidia_events(events, root / plan["contract"], plan["model"], 64000)
    if billing["unverified_requests"] or any(row["event"] in {"billing_error", "request_error"} for row in events):
        raise RuntimeError("A completed trial lacks its own complete authorized free-service evidence")
    returned = {row["request_id"]: row["payload"] for row in events if row["event"] == "response"}
    for request in (row for row in events if row["event"] == "request"):
        cap = request["payload"]["max_tokens"]
        if (type(cap) is not int or not 0 < cap <= plan["limits"]["max_output_tokens"]
                or returned[request["request_id"]]["usage"]["completion_tokens"] > cap):
            raise ValueError("An actual generation violated its individual requested output limit")
    if task["benchmark"] == "swe" and configuration == "C1" and plan.get("comparison_kind") != "complete75":
        baseline = trial_directory(directory.parent, task["id"], "C0", plan)
        if read_json(directory / "checkout.json") != read_json(baseline / "checkout.json"):
            raise ValueError("The paired repository checkouts differ before model execution")
    return {"task": task["id"], "benchmark": task["benchmark"], "configuration": configuration,
        "run_dir": str(directory), "passed": score["passed"], "wall_seconds": score["wall_seconds"],
        "original_score_sha256": digest(directory / "result.json"), **billing, **run_metrics(directory),
        **control_artifact_metrics(directory, plan.get("framework", "mini-swe"), configuration)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    root = Path.cwd()
    plan = read_json(args.plan)
    verify_frozen(root, plan)
    tasks = {row["id"]: row for row in read_json(root / plan["manifest"])["selected"]}
    pins = read_json(root / plan["environment_pins"])["pins"]
    if set(plan["task_order"]) - tasks.keys():
        raise ValueError("A comparison task is outside the original frozen manifest")
    if any(task_id not in pins or (tasks[task_id].get("image_id") is not None
            and tasks[task_id]["image_id"] != pins[task_id]) for task_id in plan["task_order"]):
        raise ValueError("A declared original image identity is missing or inconsistent")
    if args.validate_only:
        print(json.dumps({"validated_tasks": len(plan["task_order"]),
                          "planned_executions": sum(1 for task in plan["task_order"] for _ in scheduled_trials(plan, task)),
                          "new_model_calls": 0}))
        return
    queue = root / plan["queue"]
    queue.mkdir(parents=True, exist_ok=True)
    previous_state = queue / "state.json"
    if previous_state.exists() and read_json(previous_state).get("stage") == "closed_for_runtime_repair":
        raise RuntimeError("This development cohort is closed; use the qualified replacement runtime and preserve its results")
    environment = os.environ | {"PYTHONPATH": str(root), "LIMA_HOME": str(root / ".v"),
        "COURSE_DOCKER_BIN": str(root / "work/vendor/docker/docker"),
        "DOCKER_HOST": "unix://" + str(root / "work/v/c/sock/docker.sock"),
        "DOCKER_CONFIG": str(root / "work/docker-config")}
    state = {"stage": "running", "planned_pairs": plan["planned_pairs"], "results": [],
        "plan_sha256": digest(args.plan), "source_plan_sha256": digest(root / plan["source_plan"])}
    try:
        for task_id in plan["task_order"]:
            task = tasks[task_id]
            for configuration, execution_plan, arm in scheduled_trials(plan, task_id):
                state.update(current_task=task_id, configuration=configuration, current_arm=arm)
                save_json(queue / "state.json", state)
                if read_json(root / "work/performance-stop-20261122.json")["active"]:
                    raise RuntimeError("All new models are stopped for unresolved actual fees")
                verify_frozen(root, plan)
                directory = trial_directory(queue, task_id, configuration, execution_plan)
                if not (directory / "result.json").exists():
                    if directory.exists():
                        raise RuntimeError("An unfinished attempt exists; preserve it instead of restarting")
                    inspected = subprocess.run([str(root / "work/vendor/docker/docker"), "image", "inspect",
                        "--format", "{{.Id}}", task["image"]], env=environment, capture_output=True, text=True)
                    if inspected.returncode:
                        prepare_missing_image(task, environment)
                        inspected = subprocess.run([str(root / "work/vendor/docker/docker"), "image", "inspect",
                            "--format", "{{.Id}}", task["image"]], env=environment,
                            capture_output=True, text=True, check=True)
                    if inspected.stdout.strip() != pins[task_id]:
                        raise ValueError("The actual task image differs from its frozen content identity")
                    command = [sys.executable, str(root / plan.get("driver", "scripts/run_performance_trial.py")),
                        "--task", task_id, "--manifest", str(root / plan["manifest"]),
                        "--configuration", configuration, "--checks", str(root / plan["checks"]),
                        "--runtime-root", str(root / execution_plan["runtime_root"]), "--backend", plan["backend"],
                        "--model", plan["model"], "--nvidia-contract", str(root / plan["contract"]),
                        "--nvidia-qualification", str(root / plan["qualification"]), "--run-dir", str(directory)]
                    if execution_plan.get("framework") == "dsh":
                        command += ["--framework", "dsh"]
                    subprocess.run(command, env=environment, check=True)
                result = completed_result(root, execution_plan, task, configuration, directory) | {"arm": arm}
                state["results"].append(result)
                save_json(queue / "state.json", state)
                print(json.dumps({key: result[key] for key in
                    ("task", "configuration", "passed", "wall_seconds", "actual_requests")}), flush=True)
            release_scored_image(task, task["image"], environment, queue)
        state.update(stage="complete", current_task=None, configuration=None)
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        state.update(stage="stopped", error_type=type(exc).__name__, error=str(exc))
        save_json(queue / "state.json", state)
        raise
    save_json(queue / "state.json", state)


if __name__ == "__main__":
    main()
