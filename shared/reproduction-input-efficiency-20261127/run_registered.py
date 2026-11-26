import json
import os
import subprocess
import time
from pathlib import Path

from run_study import FOLDER, ROOT, RUNTIME, read, save
from course_eval.resource_pool import ResourceLease


PROJECT = ROOT.parent
PYTHON = ROOT / "work/.venv/bin/python"
environment = os.environ | {"COURSE_STUDY_DOCKER_HOST": "unix://" + str(PROJECT / "guest/docker.sock"),
    "PYTHONPATH": str(RUNTIME) + os.pathsep + str(ROOT), "MSWEA_SILENT_STARTUP": "1",
    "MSWEA_GLOBAL_CONFIG_DIR": str(ROOT / "work/miniswe-config"),
    "COURSE_CODEBUDDY_BIN": str(RUNTIME / "course_eval/remote_codebuddy.py"),
    "COURSE_DOCKER_BIN": str(ROOT / "work/vendor/docker/docker"),
    "DOCKER_HOST": "unix://" + str(PROJECT / "guest/docker.sock"),
    "DOCKER_CONFIG": str(ROOT / "work/docker-config"), "COURSE_AIDER_PLATFORM": "linux/amd64",
    "COURSE_AIDER_PUBLIC_PYTHON": str(ROOT / "work/terminal-runtime/python-3.13.12-linux-x86_64.tar.gz")}


def status(phase, **values):
    record = {"phase": phase, "time_unix": time.time(), "pid": os.getpid(), **values}
    save(FOLDER / "owner-state.json", record)
    with (FOLDER / "owner-events.jsonl").open("a") as handle:
        handle.write(json.dumps(record) + "\n")


def run(phase, command, *, cwd=ROOT):
    status(phase)
    with (FOLDER / "registered-owner.log").open("ab") as log:
        log.write(("\nPHASE " + phase + "\n").encode())
        log.flush()
        subprocess.run([str(value) for value in command], cwd=cwd, env=environment,
            stdout=log, stderr=subprocess.STDOUT, check=True)


def wait_preparation(candidate, *, confirmation=False):
    started = time.monotonic()
    while True:
        marker = FOLDER / "image-build.exit"
        if marker.exists() and marker.read_text().strip() != "0":
            raise RuntimeError("Aider image construction failed; inspect its actual build log")
        swe_ready = all(read(FOLDER / "preparation" / task["id"] / "record.json")["status"] == "ready"
            for task in candidate["selected"] if task["benchmark"] == "swe"
            and (confirmation or task["id"] in candidate["diagnostic_ids"]))
        if marker.exists() and swe_ready:
            return
        for name, ready in (("course-images-20261126", marker.exists()), ("course-native-images-20261126", swe_ready)):
            if not ready and subprocess.run(["tmux", "has-session", "-t", name], capture_output=True).returncode:
                raise RuntimeError("An unfinished preparation owner stopped: " + name)
        if time.monotonic() - started > 10800:
            raise TimeoutError("Image preparation exceeded the registered three-hour owner wait")
        status("waiting_for_original_images", swe_images_ready=swe_ready)
        time.sleep(30)


def main():
    candidate = read(FOLDER / "candidate-tasks.json")
    wait_preparation(candidate)
    with ResourceLease(FOLDER / "resources", exclusive=True, label="runtime-and-isolation-qualification"):
        run("qualify_dsh_and_aider_images", [PYTHON, FOLDER / "prepare_runtime.py", "--language", "all"])
        phase = read(PROJECT / "guest/state.json")
        if phase["stage"] == "trusted_image_preparation_only":
            run("qualify_isolated_task_environment", [PROJECT / ".venv-course/bin/python", "-B",
                PROJECT / "guest_phase.py", "tasks"], cwd=PROJECT)
    run("bind_actual_execution", [PYTHON, FOLDER / "finalize_execution.py"])
    replay = FOLDER / "replay-original/tools.jsonl"
    environment.update(COURSE_OUTPUT_REPLAY_LOG=str(replay),
        COURSE_OUTPUT_QUALIFICATION="remote-output-qualification")
    if not (FOLDER / "remote-output-qualification/result.json").exists():
        with ResourceLease(FOLDER / "resources", exclusive=True, label="remote-output-qualification"):
            run("qualify_actual_remote_output_archive", [PYTHON, FOLDER / "qualify_output.py"], cwd=RUNTIME)
    if read(FOLDER / "remote-output-qualification/result.json")["status"] != "PASS":
        raise RuntimeError("Actual remote output archival qualification did not pass")
    first = candidate["diagnostic_ids"][0]
    run("first_original_control", [PYTHON, FOLDER / "run_study.py", "--task", first, "--prepare-only"])
    if not (FOLDER / "study-plan.json").exists():
        run("freeze_before_first_generation", [PYTHON, FOLDER / "run_study.py", "--freeze"])
    for name in candidate["diagnostic_ids"]:
        run("diagnostic_" + name, [PYTHON, FOLDER / "run_study.py", "--task", name, "--stage", "diagnostic"])
    wait_preparation(candidate, confirmation=True)
    for name in candidate["confirmation_ids"]:
        run("confirmation_" + name, [PYTHON, FOLDER / "run_study.py", "--task", name, "--stage", "confirmation"])
    run("select_registered_repeat", [PYTHON, FOLDER / "analyze_study.py"])
    plan = FOLDER / "repeat-plan.json"
    if plan.exists():
        for name, arm in read(plan)["configuration_by_task"].items():
            run("independent_repeat_" + name, [PYTHON, FOLDER / "run_study.py", "--task", name,
                "--stage", "repeat", "--arm", arm])
        run("analyze_complete_repeat", [PYTHON, FOLDER / "analyze_study.py"])
    status("completed_registered_model_matrix", study_results=str(FOLDER / "study-results.json"),
        repeat_results=str(FOLDER / "repeat-results.json"))


if __name__ == "__main__":
    try:
        main()
    except BaseException as error:
        status("stopped_with_actual_error", error_type=type(error).__name__, detail=str(error))
        raise
