import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import traceback


ROOT = Path.cwd().resolve()
FOLDER = Path(__file__).resolve().parent
RUNTIME = ROOT / "work/frozen-performance-hy4-submit-boundary-v20"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(RUNTIME))
os.environ.setdefault("MSWEA_GLOBAL_CONFIG_DIR", str(ROOT / "work/miniswe-config"))
os.environ.setdefault("MSWEA_SILENT_STARTUP", "1")
from minisweagent.exceptions import Submitted
from course_eval.agent import RunLimits
from course_eval.controller import Budget, ControlledEnvironment
from course_eval.docker_target import DockerTarget
from course_eval.resource_pool import ResourceLease
from course_eval.terminal_runtime import prepare_public_runtime
from course_eval.verification import PublicCheck


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def actual_action(lane, request_id):
    repetition = 1 if lane == "main" else 2
    run = ROOT / f"work/vmshare/performance75-hy4-sql-layout-v18-{lane}-20261125/model-extraction-relu-logits-C0-r{repetition}"
    trace, = run.rglob("model.jsonl")
    for line in trace.open():
        event = json.loads(line)
        if event["event"] == "response" and event["request_id"] == request_id:
            return next(row["structured_output"] for row in reversed(event["payload"]) if row.get("type") == "result")
    raise ValueError("The actual archived action is missing")


class RecordedTarget(DockerTarget):
    def __init__(self, *args, **kwargs):
        self.commands = []
        super().__init__(*args, **kwargs)

    def exec(self, command, *, cwd="", timeout):
        result = super().exec(command, cwd=cwd, timeout=timeout)
        self.commands.append({"command": command, "cwd": cwd, "timeout": timeout, **result})
        return result


def main():
    output = FOLDER / "linux-integration-r1"
    output.mkdir(exist_ok=False)
    logs = output / "controller"
    logs.mkdir()
    started = time.monotonic()
    record = {"status": "WAITING_SHARED_LIGHT_SLOT", "new_model_calls": 0,
        "new_original_grader_calls": 0, "source_sha256": {str(Path(__file__).resolve().relative_to(ROOT)): sha(Path(__file__))}}
    try:
        qualification = read(FOLDER / "qualification.json")
        for name, expected in qualification["runtime_delta"]["files"].items():
            source = RUNTIME / name
            if sha(source) != expected:
                raise ValueError("The reviewed v20 runtime changed: " + name)
            record["source_sha256"][str(source.relative_to(ROOT))] = expected
        parent_path = ROOT / "work/parallel-free-evaluation-20261124/final-sql75-quota-recovered/main-plan.json"
        parent = read(parent_path)
        tasks_path, checks_path = parent_path.parent / "tasks.json", parent_path.parent / "checks.json"
        pins_path = ROOT / parent["baseline_queue"] / "environment-pins.json"
        for path, expected in ((tasks_path, parent["tasks_sha256"]), (checks_path, parent["checks_sha256"]),
                (pins_path, parent["environment_pins_sha256"])):
            if sha(path) != expected:
                raise ValueError("The original task/check/image pin changed")
            record["source_sha256"][str(path.relative_to(ROOT))] = expected
        task = next(task for task in read(tasks_path)["selected"] if task["id"] == "model-extraction-relu-logits")
        pin = read(pins_path)["pins"][task["id"]]
        checks = tuple(PublicCheck(**(item | {"dependencies": tuple(item["dependencies"])}))
            for item in read(checks_path)[task["id"]])
        print(json.dumps({"status": record["status"], "image": pin, "new_model_calls": 0}), flush=True)
        with ResourceLease(ROOT / parent["resource_pool"], exclusive=False, label="zero-model-v20-relu-original-pin"):
            with RecordedTarget(pin, "/app", platform="linux/amd64", memory_mb=2048, cpus=1,
                    read_only_empty_dirs=("/tests",)) as target:
                if target.image != pin:
                    raise ValueError("The actual engineering container differs from the original image pin")
                network = target.exec("ls /sys/class/net", timeout=10)
                if network["returncode"] or network["stdout"].strip() != "lo":
                    raise ValueError("The actual engineering container is not offline")
                scope = copy.deepcopy(task["candidate_scope"])
                deployment = prepare_public_runtime(target, scope)
                if "/opt/course-tools/relu_export.py" not in scope["protected"]:
                    raise ValueError("The actual uploaded exporter is not protected")
                env = ControlledEnvironment(target, logs, RunLimits(wall_seconds=240, command_seconds=120),
                    checks, scope, Budget(240), False)
                before = len(target.commands)
                rejected_read = env.execute(actual_action("main", 2))
                if "oracle_access_rejected" not in rejected_read["output"] or len(target.commands) != before:
                    raise ValueError("The actual archived implementation read reached the original-pin shell")
                rejected_submit = env.execute(actual_action("main", 10))
                if "submission_rejected" not in rejected_submit["output"] or env.final_report is not None:
                    raise ValueError("The actual archived pending submission was accepted")
                exported = env.execute({"operation": "bash", "command":
                    "python3 /opt/course-tools/relu_export.py --dimension 10 --oracle-module forward --oracle-function forward --output /app/steal.py"})
                if exported["returncode"]:
                    raise ValueError("The actual original-pin self-contained export failed: " + exported["output"])
                independent = target.exec("set -e\nmv /opt/course-tools /opt/course-tools.qualification\n"
                    "trap 'mv /opt/course-tools.qualification /opt/course-tools' EXIT\ncd /app\npython3 /app/steal.py", timeout=120)
                if independent["returncode"]:
                    raise ValueError("The exported script failed with course-tools temporarily unavailable: " + independent["stderr"])
                verified = env.execute(actual_action("repeat", 4))
                if '"state": "passed"' not in verified["output"]:
                    raise ValueError("The actual registered numerical check rejected the exported original-pin result")
                saved = env.execute(actual_action("repeat", 5))
                if '"eligible": true' not in saved["output"]:
                    raise ValueError("The actual original-pin candidate is not eligible")
                try:
                    env.execute(actual_action("main", 10))
                except Submitted:
                    pass
                else:
                    raise ValueError("The verified original-pin candidate did not reach submission")
                if not env.final_report["valid_verification"] or not env.final_report["protected_unchanged"]:
                    raise ValueError("The original-pin final verification/protection is invalid")
                for name in ("steal.py", "stolen_A1.npy"):
                    if not target.download_file(name, output / name):
                        raise ValueError("An actual engineering output is missing")
                record.update(status="PASS_ORIGINAL_PIN_ENGINEERING_NOT_MODEL_OR_ORIGINAL_SCORE",
                    system_info=target.system_info, deployment=deployment, actual_scope=scope,
                    archived_read_blocked_before_exec=True, archived_pending_submit_rejected=True,
                    independent_script_with_course_tools_hidden=independent,
                    structured_verify=verified, eligible_save=saved, final_verification=env.final_report,
                    actual_target_commands=target.commands)
    except BaseException as error:
        record.update(status="FAILED_ENGINEERING_QUALIFICATION", error_type=type(error).__name__,
            error=str(error), traceback=traceback.format_exc())
        raise
    finally:
        record["wall_seconds_including_resource_wait"] = time.monotonic() - started
        record["scope"] = "Fresh original image pin;actual offline Docker deployment,public callable queries,self-contained execution and Controller actions. Archived actions replayed by engineering driver;zero new model behavior or original task grading."
        (output / "result.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n")
        print(json.dumps({key: record[key] for key in ("status", "new_model_calls", "new_original_grader_calls")}), flush=True)


if __name__ == "__main__":
    main()
