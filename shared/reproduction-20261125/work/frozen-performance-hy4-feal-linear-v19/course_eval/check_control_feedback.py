import argparse
import base64
import json
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

from minisweagent.exceptions import Submitted
from pydantic import ValidationError

from course_eval.agent import RunLimits, SUBMIT
from course_eval.controller import Budget, ControlAction, ControlledEnvironment
from course_eval.verification import PublicCheck


class LocalCommandTarget:
    def __init__(self, directory):
        self.cwd = str(directory.resolve())
        self.input_path = directory.resolve() / "controller-input.json"
        self.system_info = {"kind": "local-engineering-check"}
        self.commands = []

    def upload_file(self, source, destination, *, timeout=20):
        assert destination == "/.course-controller-input.json"
        shutil.copyfile(source, self.input_path)

    def exec(self, command, *, cwd="", timeout):
        self.commands.append(command)
        # 将容器内的固定传输路径映射到工作区；每条命令均由真实子进程执行。
        if command.startswith("env LC_ALL=C.UTF-8 "):
            arguments = shlex.split(command)
            assert arguments[-1] == "/.course-controller-input.json"
            arguments[-1] = str(self.input_path)
            completed = subprocess.run(arguments, cwd=cwd or self.cwd, timeout=timeout, capture_output=True, text=True)
        else:
            if command.startswith("/usr/bin/sha256sum -- "):
                command = shlex.quote(shutil.which("sha256sum")) + command[len("/usr/bin/sha256sum"):]
            completed = subprocess.run(command, shell=True, executable="/bin/bash", cwd=cwd or self.cwd,
                                       timeout=timeout, capture_output=True, text=True)
        return {"stdout": completed.stdout, "stderr": completed.stderr, "returncode": completed.returncode}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    analysis = json.loads((args.evidence_root / "course-execution-failure-analysis-20261118.json").read_text())
    empty = analysis["real_empty_feedback_requests"]
    assert len(empty) == 37 and len({item["run_id"] for item in empty}) == 24
    example = next(item for item in empty if item["run_id"].startswith("C-aider-"))
    root = args.evidence_root / "confirmation-hy4flash-free-v16" / example["run_id"]
    candidate_path = sorted(root.rglob("candidate-*.json"))[0]
    record = json.loads(candidate_path.read_text())
    content = next(base64.b64decode(item["data"], validate=True) for item in record["files"].values() if "data" in item)
    target_directory = args.out / "target"
    target_directory.mkdir()
    artifact = target_directory / "candidate.bin"
    artifact.write_bytes(content + b"\ninitial candidate\n")
    expected = target_directory / "expected.bin"
    expected.write_bytes(content)
    dependency = target_directory / "dependency.bin"
    dependency.write_bytes(b"initial dependency\n")
    target = LocalCommandTarget(target_directory)
    limits = RunLimits(wall_seconds=600)
    budget = Budget(600)
    check = PublicCheck("suite", "local archived-candidate comparison", "cmp candidate.bin expected.bin",
                        ("candidate.bin", "dependency.bin"))
    env = ControlledEnvironment(target, args.out, limits, (check,),
        {"kind": "files", "artifacts": ["candidate.bin"], "python": sys.executable}, budget, True)
    artifact.write_bytes(content)
    first = env.execute(ControlAction(operation="bash", command="printf contract-ok").model_dump())
    assert first["output"].startswith("contract-ok")
    requested = env.execute(ControlAction(operation="verify", check_id="suite").model_dump())
    assert '"state": "passed"' in requested["output"]
    saved = env.execute(ControlAction(operation="save").model_dump())
    assert "candidate-001" in saved["output"]
    checks_before = sum(command == check.command for command in target.commands)
    assert env.before_decision(6) == "", "Valid requested check must not generate automatic empty feedback"
    assert sum(command == check.command for command in target.commands) == checks_before
    artifact.write_bytes(content + b"\nchanged candidate\n")
    changed = env.before_decision(8)
    assert '"state": "failed"' in changed and '"check_id": "suite"' in changed
    checks_after = sum(command == check.command for command in target.commands)
    assert env.before_decision(10) == "", "Same candidate and dependencies must not repeat feedback"
    assert sum(command == check.command for command in target.commands) == checks_after
    restored = env.execute(ControlAction(operation="restore", candidate_id="candidate-001").model_dump())
    assert '"restored": "candidate-001"' in restored["output"] and artifact.read_bytes() == content
    dependency.write_bytes(b"changed dependency\n")
    dependency_feedback = env.before_decision(12)
    assert '"check_id": "suite"' in dependency_feedback
    assert sum(command == check.command for command in target.commands) == checks_after + 1
    assert env.before_decision(20) == "", "Final phase must not generate empty feedback"
    commands_before = len(target.commands)
    try:
        env.execute({"operation": "submit", "command": "printf forbidden"})
    except ValidationError:
        pass
    else:
        raise AssertionError("Invalid submit executed")
    assert len(target.commands) == commands_before
    for action in (ControlAction(operation="submit", note="verified local delivery"),
                   ControlAction(operation="bash", command="printf " + shlex.quote(SUBMIT + "\nverified local delivery\n"))):
        try:
            env.execute(action.model_dump())
        except Submitted as result:
            assert result.messages[0]["extra"]["exit_status"] == "Submitted"
        else:
            raise AssertionError("Submit did not terminate")
    result = {"engineering_check": "pass", "new_model_requests": 0, "new_original_grader_executions": 0,
              "archived_empty_feedback_requests": 37, "archived_runs": 24,
              "archived_fixture": str(candidate_path.relative_to(args.evidence_root)),
              "checks": ["requested verification without empty feedback", "candidate change rechecks",
                         "unchanged failed candidate does not repeat", "restore exact bytes",
                         "dependency invalidation rechecks", "final phase without empty feedback",
                         "invalid action has no effects", "five operations return or terminate correctly"],
              "scope": "Real local subprocesses and archived candidate bytes; not a model-success experiment"}
    (args.out / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
