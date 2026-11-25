import argparse
import fcntl
import json
import os
import shlex
import signal
import subprocess
import sys
import time
from pathlib import Path


def read(path):
    return json.loads(path.read_text())


def process_command(pid):
    result = subprocess.run(["ps", "-p", str(pid), "-o", "command="], capture_output=True, text=True)
    return result.stdout.strip() if result.returncode == 0 else None


def queue_command(plan, root, queue):
    source = (root / read(plan)["coordinator_path"]).resolve(strict=True)
    if not source.is_relative_to(root.resolve()):
        raise ValueError("The declared coordinator leaves this project")
    return [sys.executable, str(source), "--plan", str(plan.resolve()), "--queue-dir", str(queue)]


def dispatcher_argv(command, scripts, queues):
    first = command.split(maxsplit=2)
    if len(first) < 2 or not Path(first[0]).name.startswith("python"):
        return None
    try:
        args = shlex.split(command)
    except ValueError:
        if Path(first[1]).resolve() in scripts:
            raise RuntimeError("Cannot safely parse an existing coordinator command")
        return None
    if Path(args[1]).resolve() in scripts:
        return args
    if "--plan" in args and "--queue-dir" in args:
        index = args.index("--queue-dir") + 1
        if index < len(args) and Path(args[index]).resolve() in queues:
            return args
    return None


def children(pid):
    text = subprocess.check_output(["ps", "-axo", "pid,ppid,state,command"], text=True)
    rows = [line.split(maxsplit=3) for line in text.splitlines()[1:]]
    return [row for row in rows if int(row[1]) == pid and "Z" not in row[2] and "caffeinate" not in row[3]]


def queue_progress(queue, process):
    path = queue / "state.json"
    if not path.exists():
        code = process.poll()
        if code is not None:
            return {"status": "ended_before_first_state", "returncode": code}
        return {"status": "starting_before_first_state"}
    return {key: value for key, value in read(path).items()
        if key in ("status", "current_task", "current_arm", "baseline_completed", "policy_completed")}


class AdoptedQueue:
    def __init__(self, pid, queue, expected):
        self.pid, self.queue, self.returncode, self.expected = pid, queue, None, expected

    def poll(self):
        command = process_command(self.pid)
        if command is not None:
            if shlex.split(command)[1:] != self.expected[1:]:
                raise RuntimeError("The adopted queue PID no longer belongs to the verified dispatcher")
            return None
        self.returncode = 0 if read(self.queue / "state.json")["status"] == "complete" else 1
        return self.returncode


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--previous-main", type=int)
    parser.add_argument("--adopt-repeat", type=int)
    parser.add_argument("--main-plan", type=Path)
    parser.add_argument("--repeat-plan", type=Path)
    parser.add_argument("--run-label", default="ready")
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    root, folder = Path.cwd(), Path(__file__).parent.resolve()
    plans = {"main": args.main_plan or folder / "ready-main-plan.json",
        "repeat": args.repeat_plan or folder / "ready-repeat-plan.json"}
    queues = {lane: (root / read(path)["queue"]).resolve() for lane, path in plans.items()}
    scripts = {Path(queue_command(path, root, queues[lane])[1]) for lane, path in plans.items()}
    scripts.update(folder / name for name in ("ready_coordinator.py", "hy4_repeat.py", "hy4_coordinator.py"))
    if args.previous_main is not None and args.adopt_repeat is not None:
        raise ValueError("Adopt an existing repeat or hand over an old main dispatcher, not both")
    if not args.run_label.replace("-", "").isalnum():
        raise ValueError("The run label must be a plain filename component")
    environment = os.environ | {"PYTHONPATH": str(root)}
    capture_policies = {read(path).get("artifact_capture_policy") for path in plans.values()}
    if capture_policies != {None}:
        if None in capture_policies or len(capture_policies) != 1:
            raise ValueError("Both final queues must use the same declared output capture policy")
        environment["COURSE_HARBOR_CAPTURE_POLICY"] = str((root / capture_policies.pop()).resolve(strict=True))
    state = {"pid": os.getpid(), "stage": "validating_identical_model_conditions_and_ready_task_scheduler",
        "new_model_calls_by_supervisor": 0, "old_task_or_grader_children_interrupted": False,
        "previous_main": args.previous_main, "children": {},
        "plans": {lane: str(path.resolve().relative_to(root)) for lane, path in plans.items()}}

    def save():
        temporary = folder / "ready-queues-state.writing"
        temporary.write_text(json.dumps(state, indent=2) + "\n")
        temporary.replace(folder / "ready-queues-state.json")

    def command(lane):
        return queue_command(plans[lane], root, queues[lane])

    def start(lane):
        if read(root / "work/performance-stop-20261122.json")["active"]:
            raise RuntimeError("The actual financial stop prevents a queue launch")
        probe = read(plans[lane]).get("required_startup_probe")
        if probe is not None:
            import hashlib
            path = root / probe["path"]
            if (hashlib.sha256(path.read_bytes()).hexdigest() != probe["sha256"]
                    or read(path).get(probe.get("success_field", "stage")) != probe.get(
                        "success_value", "passed_actual_startup_and_pristine_checkout")):
                raise RuntimeError("The exact zero-model startup qualification has not passed")
        with (folder / (args.run_label + "-" + lane + ".log")).open("x") as log:
            process = subprocess.Popen(["caffeinate", "-i", *command(lane)], env=environment, stdout=log, stderr=subprocess.STDOUT)
        state["children"][lane] = process.pid
        save()
        return process

    with (folder / "ready-queues.lock").open("a") as single:
        fcntl.flock(single, fcntl.LOCK_EX | fcntl.LOCK_NB)
        for lane in queues:
            validated = subprocess.run([*command(lane), "--validate-only"], env=environment,
                capture_output=True, text=True, check=True)
            state[lane + "_validation"] = json.loads(validated.stdout)
        if args.validate_only:
            print(json.dumps(state), flush=True)
            return
        actual = subprocess.check_output(["ps", "-axo", "pid,command"], text=True)
        for line in actual.splitlines()[1:]:
            fields = line.split(maxsplit=1)
            if len(fields) != 2:
                continue
            pid, executable = int(fields[0]), fields[1]
            actual_args = dispatcher_argv(executable, scripts, set(queues.values()))
            if pid == args.adopt_repeat:
                if actual_args is None or actual_args[1:] != command("repeat")[1:]:
                    raise ValueError("The adopted PID is not the exact existing repeat queue")
                continue
            if actual_args is not None and not (pid == args.previous_main
                    and Path(actual_args[1]).resolve() == folder / "hy4_coordinator.py"):
                raise RuntimeError("An existing queue dispatcher must be adopted before starting another")
        if args.previous_main is not None:
            original_command = process_command(args.previous_main)
            if original_command is None or "parallel-free-evaluation-20261124/hy4_coordinator.py --plan" not in original_command:
                raise ValueError("The handover PID is not the actual previous main dispatcher")
            while True:
                os.kill(args.previous_main, signal.SIGSTOP)
                previous = read(queues["main"] / "state.json")
                if previous["status"] == "complete" or (previous["status"] == "running" and previous.get("current_task") is not None):
                    break
                os.kill(args.previous_main, signal.SIGCONT)
                time.sleep(1)
            state["stage"] = "new_repeat_running_while_old_main_task_finishes_naturally"
            save()
        try:
            if args.adopt_repeat is None:
                processes = {"repeat": start("repeat")}
            else:
                if process_command(args.adopt_repeat) is None:
                    raise RuntimeError("The existing repeat dispatcher exited before adoption")
                processes = {"repeat": AdoptedQueue(args.adopt_repeat, queues["repeat"], command("repeat"))}
                state["children"]["repeat"] = args.adopt_repeat
                state["adopted_inflight_repeat_without_interrupting"] = True
                save()
            if args.previous_main is not None:
                while children(args.previous_main):
                    time.sleep(1)
                if process_command(args.previous_main) != original_command:
                    raise RuntimeError("The previous queue PID changed during the safe handover")
                os.kill(args.previous_main, signal.SIGTERM)
                os.kill(args.previous_main, signal.SIGCONT)
        finally:
            if args.previous_main is not None and process_command(args.previous_main) == original_command:
                try:
                    os.kill(args.previous_main, signal.SIGCONT)
                except ProcessLookupError:
                    pass
        processes["main"] = start("main")
        state["stage"] = "both_original75_queues_use_cached_ready_tasks_with_same_frozen_model"
        save()
        last = None
        while any(process.poll() is None for process in processes.values()):
            progress = {lane: queue_progress(queue, processes[lane]) for lane, queue in queues.items()}
            state.update(progress=progress, financial_stop_active=read(root / "work/performance-stop-20261122.json")["active"],
                returncodes={lane: process.poll() for lane, process in processes.items()})
            if any(code not in (None, 0) for code in state["returncodes"].values()):
                state["stage"] = "one_queue_error_other_actual_inflight_work_retained"
            save()
            current = json.dumps(progress, sort_keys=True)
            if current != last:
                print(json.dumps({"progress": progress, "financial_stop_active": state["financial_stop_active"]}), flush=True)
                last = current
            time.sleep(10)
        completed = {lane: queue_progress(queue, processes[lane]) for lane, queue in queues.items()}
        state["all_original225_present"] = (completed["main"]["status"] == "complete" and completed["main"].get("baseline_completed") == 75
            and completed["main"].get("policy_completed") == 75 and completed["repeat"]["status"] == "complete"
            and completed["repeat"].get("policy_completed") == 75)
        state["stage"] = "full_core_complete_follow_declared_ablation_and_report" if state["all_original225_present"] else "actual_error_requires_diagnosis"
        state["returncodes"] = {lane: process.returncode for lane, process in processes.items()}
        save()


if __name__ == "__main__":
    main()
