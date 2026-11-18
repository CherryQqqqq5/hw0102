import base64
import json
import os
import shlex
import subprocess
import time
from dataclasses import asdict
from pathlib import Path
from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from minisweagent.agents.default import DefaultAgent
from minisweagent.config import builtin_config_dir, get_config_from_spec
from minisweagent.exceptions import Submitted, TimeExceeded

from course_eval.agent import CodeBuddyModel, CourseModel, SUBMIT, TracedEnvironment, append_event
from course_eval.verification import Evidence, VerificationState


class ControlAction(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    required_fields: ClassVar[dict[str, str | None]] = {
        "bash": "command", "verify": "check_id", "save": None, "restore": "candidate_id", "submit": None,
    }
    operation: Literal["bash", "verify", "save", "restore", "submit"]
    command: str | None = Field(default=None, max_length=65536)
    check_id: str | None = None
    candidate_id: str | None = None
    note: str = ""

    @model_validator(mode="after")
    def validate_action(self):
        required = self.required_fields[self.operation]
        if required and not getattr(self, required):
            raise ValueError(f"{self.operation} requires {required}")
        for name in ("command", "check_id", "candidate_id"):
            if name != required and getattr(self, name) is not None:
                raise ValueError(f"{name} is not valid for {self.operation}")
        return self

    @classmethod
    def __get_pydantic_json_schema__(cls, core_schema, handler):
        schema = handler.resolve_ref_schema(handler(core_schema))
        # 发送端与本地校验共用每种操作的字段定义，禁止其他操作的非空参数。
        schema["oneOf"] = [
            {"properties": {"operation": {"const": operation}, **{
                name: {"type": "string", "minLength": 1} if name == required else {"type": "null"}
                for name in ("command", "check_id", "candidate_id")}},
             "required": ["operation", required] if required else ["operation"]}
            for operation, required in cls.required_fields.items()
        ]
        return schema


class ControlModel(CodeBuddyModel):
    argument_type = ControlAction
    action_name = "action"
    selection_instruction = "one structured action (bash, verify, save, restore, submit)"


class CourseControlModel(CourseModel):
    argument_type = ControlAction
    action_name = "action"


class Budget:
    def __init__(self, seconds):
        self.started = time.monotonic()
        self.deadline = self.started + seconds
        self.request_reserve = 0.0

    def remaining(self):
        return max(0.0, self.deadline - time.monotonic())

    def require_time(self):
        if self.remaining() <= self.request_reserve + 0.25:
            raise TimeExceeded({"role": "exit", "content": "Execution deadline",
                                "extra": {"exit_status": "TimeExceeded", "submission": ""}})

    def request_seconds(self):
        self.require_time()
        return max(0.1, self.remaining() - self.request_reserve)


class BoundedTarget:
    def __init__(self, target, budget):
        self.target = target
        self.budget = budget

    def __getattr__(self, name):
        return getattr(self.target, name)

    def exec(self, command, *, cwd="", timeout):
        seconds = min(timeout, int(self.budget.remaining() - 3))
        if seconds < 1:
            raise TimeExceeded({"role": "exit", "content": "Execution deadline",
                                "extra": {"exit_status": "TimeExceeded", "submission": ""}})
        return self.target.exec(command, cwd=cwd, timeout=seconds)

    def upload_file(self, source, destination, *, timeout=20):
        seconds = min(timeout, int(self.budget.remaining() - 3))
        if seconds < 1:
            raise TimeExceeded({"role": "exit", "content": "Execution deadline",
                                "extra": {"exit_status": "TimeExceeded", "submission": ""}})
        return self.target.upload_file(source, destination, timeout=seconds)


class CandidateOperationError(RuntimeError):
    pass


class CandidateStore:
    def __init__(self, target, directory, scope, budget):
        self.target, self.directory, self.scope, self.budget = target, directory, scope.copy(), budget
        self.script = Path(__file__).with_name("candidate_io.py").read_text()
        encoded = base64.b64encode(self.script.encode()).decode()
        self.bootstrap = "import base64; exec(compile(base64.b64decode(" + repr(encoded) + "), '<course-candidate-io>', 'exec'))"
        self.known = set()
        self.candidates = []
        self.original = self.call("initial")
        if "head" in self.original:
            self.scope["head"] = self.original["head"]
        self.original_files = self.original["files"].copy()

    def call(self, operation, **fields):
        started = time.monotonic()
        request = {"operation": operation, "scope": self.scope, "cwd": self.target.cwd, **fields}
        payload = self.directory / ".controller-input.json"
        payload.write_text(json.dumps(request))
        # Python 3.6的C区域设置会把Git输出及文件名按ASCII处理。
        command = shlex.join(("env", "LC_ALL=C.UTF-8", self.scope.get("python", "python3"),
                              "-c", self.bootstrap, "/.course-controller-input.json"))
        try:
            self.target.upload_file(payload.resolve(), "/.course-controller-input.json")
            output = self.target.exec(command, timeout=20)
        except (OSError, TimeoutError, subprocess.SubprocessError) as exc:
            raise CandidateOperationError(f"Candidate {operation} transport failed: {type(exc).__name__}: {exc}") from exc
        append_event(self.directory / "controller.jsonl", "candidate_operation", operation=operation,
                     seconds=time.monotonic() - started, returncode=output["returncode"])
        if output["returncode"]:
            raise CandidateOperationError("Candidate operation failed: " + output["stderr"][-3000:])
        try:
            return json.loads(output["stdout"])
        except json.JSONDecodeError as exc:
            raise CandidateOperationError(f"Candidate {operation} returned invalid JSON: {exc}") from exc

    def capture(self):
        current = self.call("capture", known=sorted(self.known))
        new = set(current["files"]) - self.known
        if new and self.scope["kind"] == "repository":
            self.original_files.update(self.call("original", names=sorted(new)))
        self.known.update(current["files"])
        return current

    def trusted(self, current):
        return current["protected_digest"] == self.original["protected_digest"]

    def save(self, current, evidence):
        eligible = self.trusted(current) and all(record["state"] == "passed" for record in evidence.values())
        if (self.candidates and self.candidates[-1]["artifact_digest"] == current["artifact_digest"]
                and self.candidates[-1]["evidence"] == evidence and self.candidates[-1]["eligible"] == eligible):
            return self.candidates[-1]
        identifier = f"candidate-{len(self.candidates) + 1:03d}"
        record = {"candidate_id": identifier, "artifact_digest": current["artifact_digest"],
                  "protected_digest": current["protected_digest"], "eligible": eligible,
                  "evidence": evidence, "saved_elapsed": time.monotonic() - self.budget.started,
                  "files": current["files"]}
        folder = self.directory / "candidates"
        folder.mkdir(exist_ok=True)
        (folder / (identifier + ".json")).write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n")
        self.candidates.append(record)
        return record

    def restore(self, identifier):
        record = next(item for item in self.candidates if item["candidate_id"] == identifier)
        self.capture()
        files = {name: self.original_files[name] for name in self.known}
        files.update(record["files"])
        self.call("restore", files=files)
        return record


class ControlledEnvironment:
    def __init__(self, target, directory, limits, checks, scope, budget, enabled):
        self.target, self.directory, self.limits = target, directory, limits
        self.budget, self.enabled = budget, enabled
        self.state = VerificationState(checks, invalidate=True)
        self.store = CandidateStore(target, directory, scope, budget)
        self.steps = 0
        self.decisions = 0
        self.last_automatic_step = -2
        self.final_phase = False
        self.check_seconds = min(60.0, limits.command_seconds * len(checks))
        self.last_checks = {}
        self.checked_artifacts = {}
        self.checked_contexts = {}
        self.final_report = None

    def event(self, event, **fields):
        append_event(self.directory / "controller.jsonl", event, step=self.steps,
                     remaining_seconds=self.budget.remaining(), **fields)

    def get_template_vars(self):
        return self.target.system_info

    def serialize(self):
        return {"info": {"environment": self.target.system_info, "controller_enabled": self.enabled}}

    def status(self):
        current = self.store.capture()
        evidence = self.state.inspect(self.target, min(20, self.limits.command_seconds))
        for key, record in evidence.items():
            if record.state == "passed" and self.checked_artifacts.get(key) != current["artifact_digest"]:
                evidence[key] = type(record)("stale", record.returncode, record.snapshot)
                self.state.evidence[key] = evidence[key]
        if not self.store.trusted(current):
            for key in evidence:
                evidence[key] = type(evidence[key])("protected_dependency_changed")
        return current, {key: asdict(value) for key, value in evidence.items()}

    def verify(self, check_id, reason, reserve_seconds=0):
        if check_id not in self.state.checks:
            return {"error": "Unknown check_id", "available": sorted(self.state.checks)}
        check = self.state.checks[check_id]
        current = self.store.capture()
        started = time.monotonic()
        before = self.state.snapshot(check, self.target, 20)
        if self.enabled:
            reserve_seconds = max(reserve_seconds, 30 if any(item["eligible"] for item in self.store.candidates) else 15)
        available = int(self.budget.remaining() - reserve_seconds)
        if available < 1:
            return {"check_id": check_id, "state": "unknown", "reason": "reserved_for_candidate_recovery"}
        output = self.target.exec(check.command, timeout=min(check.timeout_seconds, self.limits.command_seconds, available))
        after = self.state.snapshot(check, self.target, 20)
        record = self.state.observe(check, before, after, output["returncode"])
        after_candidate = self.store.capture()
        if current["artifact_digest"] != after_candidate["artifact_digest"]:
            self.state.evidence[check_id] = type(record)("stale", output["returncode"], before)
        if not self.store.trusted(after_candidate):
            self.state.evidence[check_id] = type(record)("protected_dependency_changed", output["returncode"])
        seconds = time.monotonic() - started
        self.last_checks[check_id] = seconds
        self.check_seconds = sum(self.last_checks.get(key, min(self.limits.command_seconds, item.timeout_seconds))
                                 for key, item in self.state.checks.items())
        observed = self.state.evidence[check_id]
        self.checked_artifacts[check_id] = after_candidate["artifact_digest"]
        report = {"check_id": check_id, "reason": reason, "state": observed.state,
                  "coverage": check.coverage, "artifact_digest": after_candidate["artifact_digest"],
                  "before": before, "after": after, "seconds": seconds, **output}
        self.event("verification", **report)
        if (observed.state in {"passed", "failed"} and before == after and after is not None
                and current["artifact_digest"] == after_candidate["artifact_digest"]
                and self.store.trusted(after_candidate)):
            self.checked_contexts[check_id] = (after_candidate["artifact_digest"], after_candidate["protected_digest"], after)
        if self.enabled:
            current, evidence = self.status()
            if all(item["state"] == "passed" for item in evidence.values()):
                saved = self.store.save(current, evidence)
                self.event("candidate_saved", candidate_id=saved["candidate_id"], eligible=saved["eligible"])
        return report

    def verify_pending(self, reason, reserve_seconds=0, *, only_changed=False):
        current, evidence = self.status()
        results = []
        for key, record in evidence.items():
            if record["state"] != "passed":
                if only_changed:
                    snapshot = self.state.snapshot(self.state.checks[key], self.target, 20)
                    context = (current["artifact_digest"], current["protected_digest"], snapshot)
                    if snapshot is not None and self.checked_contexts.get(key) == context:
                        continue
                results.append(self.verify(key, reason, reserve_seconds))
        return results

    def restore_candidate(self, identifier):
        record = self.store.restore(identifier)
        current = self.store.capture()
        if current["artifact_digest"] != record["artifact_digest"]:
            raise CandidateOperationError("Restored artifact does not match the saved candidate")
        if self.store.trusted(current):
            for key, item in record["evidence"].items():
                self.state.evidence[key] = Evidence(**item)
                self.checked_artifacts[key] = current["artifact_digest"]
        evidence = self.status()[1]
        self.event("candidate_restored", candidate_id=identifier, artifact_digest=current["artifact_digest"],
                   verification=evidence)
        return record

    def final_reserve(self):
        return min(180.0, max(30.0, 2.5 * self.check_seconds + 20.0))

    def before_decision(self, calls):
        self.decisions = calls
        if not self.enabled:
            return ""
        self.budget.request_reserve = self.final_reserve()
        if self.budget.remaining() <= self.final_reserve() + 25 or calls >= self.limits.model_calls - 1:
            self.finish("deadline_or_decision_limit")
            raise Submitted({"role": "exit", "content": "Controller finalized the saved artifact",
                             "extra": {"exit_status": "ControllerFinalized", "submission": ""}})
        if self.budget.remaining() <= max(180, 2 * self.final_reserve()) or calls >= self.limits.model_calls - 4:
            self.final_phase = True
            reports = self.verify_pending("final_phase", only_changed=True)
            self.last_automatic_step = calls
            if reports:
                self.event("final_phase", reports=reports)
                return "Final verification phase: repair these public failures within the remaining budget. " + json.dumps(reports)
        elif calls >= 6 and calls - self.last_automatic_step >= 2:
            current = self.store.capture()
            if current["artifact_digest"] != self.store.original["artifact_digest"] or self.checked_contexts:
                reports = self.verify_pending("candidate_change", self.final_reserve(), only_changed=True)
                self.last_automatic_step = calls
                if reports:
                    return "Public verification of the changed candidate: " + json.dumps(reports)
        return ""

    def finish(self, reason):
        if self.final_report is not None:
            return self.final_report
        recovery_reserve = 30 if any(item["eligible"] for item in self.store.candidates) else 15
        reports = self.verify_pending(reason, recovery_reserve) if self.enabled else []
        current, evidence = self.status()
        restored = None
        if self.enabled and not all(item["state"] == "passed" for item in evidence.values()):
            eligible = [item for item in self.store.candidates if item["eligible"]]
            if eligible and self.store.trusted(current):
                restored = eligible[-1]["candidate_id"]
                self.restore_candidate(restored)
                current, evidence = self.status()
        self.final_report = {"reason": reason, "artifact_digest": current["artifact_digest"],
                             "protected_unchanged": self.store.trusted(current), "restored_candidate": restored,
                             "valid_verification": all(item["state"] == "passed" for item in evidence.values()),
                             "evidence": evidence, "elapsed_seconds": time.monotonic() - self.budget.started}
        self.event("final_artifact", **self.final_report)
        (self.directory / "final-verification.json").write_text(json.dumps(self.final_report, indent=2) + "\n")
        return self.final_report

    def execute(self, raw, cwd=""):
        action = ControlAction.model_validate({key: value for key, value in raw.items() if key != "tool_call_id"})
        self.steps += 1
        self.decisions += 1
        if action.operation == "bash":
            output = self.target.exec(action.command, cwd=cwd,
                                      timeout=min(self.limits.command_seconds, max(1, int(self.budget.remaining() - (
                                          self.final_reserve() if self.enabled else 0)))))
            append_event(self.directory / "tools.jsonl", "bash", command=action.command,
                         cwd=cwd or self.target.cwd, tool_call_id=raw.get("tool_call_id"), **output)
            lines = output["stdout"].lstrip().splitlines()
            if output["returncode"] == 0 and lines and lines[0] == SUBMIT:
                action = ControlAction(operation="submit", note="\n".join(lines[1:]))
            else:
                return self.observation(output["stdout"] + output["stderr"], output["returncode"])
        if action.operation == "verify":
            result = self.verify(action.check_id, "requested")
        elif action.operation == "save":
            current, evidence = self.status()
            record = self.store.save(current, evidence)
            result = {key: value for key, value in record.items() if key != "files"}
            self.event("candidate_saved", **result)
        elif action.operation == "restore":
            try:
                record = self.restore_candidate(action.candidate_id)
            except StopIteration:
                result = {"error": "Unknown candidate_id"}
            else:
                result = {"restored": record["candidate_id"], "verification": self.status()[1]}
                self.event("candidate_restored", **result)
        elif action.operation == "submit":
            self.finish("submission")
            raise Submitted({"role": "exit", "content": action.note,
                             "extra": {"exit_status": "Submitted", "submission": action.note}})
        return self.observation(json.dumps(result, ensure_ascii=False))

    def observation(self, text, returncode=0):
        return {"output": text + f"\nBudget: {self.budget.remaining():.1f}s, {max(0,self.limits.model_calls-self.decisions)} decisions remaining.",
                "returncode": returncode, "exception_info": ""}


class ControlAgent(DefaultAgent):
    def step(self):
        if isinstance(self.env, ControlledEnvironment):
            message = self.env.before_decision(self.n_calls)
            if message:
                self.add_messages({"role": "user", "content": message})
        return super().step()


CONTROL_PROMPT = """\nUse the structured action schema. The native bash action remains available; submit ends the task.
For this interface, a non-bash action is also a valid complete turn: verify, save, restore or submit.
verify(check_id) runs the registered public check and records the exact candidate and dependencies.
save stores the current candidate and verification evidence; restore(candidate_id) restores its files.
Save a feasible candidate before further exploration. Existing tests, inputs and check dependencies must be preserved.
Public checks cover only the stated conditions. Derive a task reproducer and check semantic boundary cases too.
Produce the required artifact early. Reserve time for final verification and repair; leave the best feasible version.
Every model request, retry, command, verification and candidate operation shares the same execution deadline.
"""


def run_controlled(task, target, directory, limits, configuration, checks, scope):
    if configuration not in {"B0", "C0", "C1"}:
        raise ValueError("Strict confirmation supports only B0/C0/C1")
    if os.environ["COURSE_MODEL_BACKEND"] not in {"codebuddy", "course"}:
        raise ValueError("Unsupported confirmation backend")
    budget = Budget(limits.wall_seconds)
    try:
        return _run_controlled(task, target, directory, limits, configuration, checks, scope, budget)
    except CandidateOperationError as exc:
        append_event(directory / "controller.jsonl", "controller_error", error_type=type(exc).__name__, detail=str(exc))
        return {"exit_status": "CandidateOperationError", "submission": "", "controller_error": str(exc)}
    except TimeExceeded:
        append_event(directory / "controller.jsonl", "controller_deadline_exhausted")
        return {"exit_status": "TimeExceeded", "submission": ""}
    finally:
        (directory / "execution-budget.json").write_text(json.dumps({
            "limit_seconds": limits.wall_seconds, "elapsed_seconds": time.monotonic() - budget.started,
            "strict": True, "configuration": configuration,
        }, indent=2) + "\n")


def _run_controlled(task, target, directory, limits, configuration, checks, scope, budget):
    target = BoundedTarget(target, budget)
    config = get_config_from_spec(builtin_config_dir / "mini.yaml")
    template = config["agent"]["instance_template"]
    baseline_model, control_model = {"codebuddy": (CodeBuddyModel, ControlModel),
                                     "course": (CourseModel, CourseControlModel)}[os.environ["COURSE_MODEL_BACKEND"]]
    if configuration == "B0":
        environment = TracedEnvironment(target, directory, limits)
        model = baseline_model(directory, limits, config["model"]["observation_template"])
    else:
        if not checks or scope is None:
            raise ValueError("Controller requires public checks and an explicit candidate scope")
        for check in checks:
            check.validate(task)
        environment = ControlledEnvironment(target, directory, limits, checks, scope, budget, configuration == "C1")
        model = control_model(directory, limits, config["model"]["observation_template"])
        template += CONTROL_PROMPT + "\nRegistered checks:\n" + json.dumps([
            {"check_id": check.check_id, "source_quote": check.source_quote, "coverage": check.coverage,
             "dependencies": check.dependencies, "deliverables": check.deliverables,
             "timeout_seconds": check.timeout_seconds} for check in checks])
    model.budget = budget
    agent = ControlAgent(model, environment, system_template=config["agent"]["system_template"],
                         instance_template=template, step_limit=limits.model_calls, cost_limit=0,
                         wall_time_limit_seconds=limits.wall_seconds, output_path=directory / "agent.json")
    (directory / "instruction.txt").write_text(task)
    try:
        result = agent.run(task)
    except CandidateOperationError as exc:
        append_event(directory / "controller.jsonl", "controller_error", error_type=type(exc).__name__, detail=str(exc))
        result = {"exit_status": "CandidateOperationError", "submission": "", "controller_error": str(exc)}
    finally:
        if isinstance(environment, ControlledEnvironment) and environment.final_report is None:
            try:
                environment.finish("agent_exit")
            except TimeExceeded:
                environment.event("finalization_deadline_exhausted")
            except CandidateOperationError as exc:
                environment.event("finalization_error", error_type=type(exc).__name__, detail=str(exc))
    return result
