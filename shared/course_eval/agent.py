import json
import os
import shlex
import subprocess
import time
from dataclasses import asdict
from pathlib import Path
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from minisweagent.agents.default import DefaultAgent
from minisweagent.config import builtin_config_dir, get_config_from_spec
from minisweagent.exceptions import FormatError, InterruptAgentFlow, Submitted
from minisweagent.models.utils.actions_toolcall import format_toolcall_observation_messages

from course_eval.verification import PublicCheck, VerificationState
from course_eval.boyue_transport import BoyueTimeout, BoyueTransport, BoyueTransportError
from course_eval.codebuddy_free import FREE_MODEL_ID, verify_free_response


SUBMIT = "COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT"
DELIVERABLE_CHECKPOINT = 6


class BashArguments(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    command: str = Field(min_length=1, max_length=65_536)


class RunLimits(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    model_calls: int = Field(default=24, gt=0)
    wall_seconds: int = Field(default=600, gt=0)
    command_seconds: int = Field(default=60, gt=0)
    max_output_tokens: int = Field(default=4096, gt=0)
    timeout_retries: int = Field(default=0, ge=0, le=2)
    strict_wall: bool = False


class ProviderTimeout(InterruptAgentFlow):
    pass


def append_event(path: Path, event: str, **data) -> None:
    if os.environ.get("COURSE_PROTOCOL_COMMIT"):
        data = {"protocol_commit": os.environ["COURSE_PROTOCOL_COMMIT"], **data}
    with path.open("a", encoding="utf-8") as log:
        log.write(json.dumps({"event": event, "time": time.time(), **data}, ensure_ascii=False) + "\n")


class ModelFormatting:
    def request_with_timeout_recovery(self, send, request_fields: dict, timeout_type: type[Exception],
                                      timeout_seconds: int):
        attempt = 1
        while True:
            if getattr(self, "budget", None) is not None:
                self.budget.require_time()
            identity = {"request_id": self.request_id, "attempt": attempt}
            append_event(self.trace, "request", **identity, **request_fields)
            try:
                return send(), attempt
            except timeout_type as exc:
                diagnostics = {}
                if isinstance(exc, BoyueTimeout):
                    diagnostics = {"provider_diagnostics": exc.diagnostics}
                if isinstance(exc, subprocess.TimeoutExpired):
                    diagnostics = {key: value.decode("utf-8", errors="replace") if isinstance(value, bytes) else value
                                   for key, value in {"stdout": exc.stdout or "", "stderr": exc.stderr or ""}.items()}
                effective_timeout = exc.timeout if isinstance(exc, subprocess.TimeoutExpired) else timeout_seconds
                append_event(self.trace, "request_error", **identity, error_type=type(exc).__name__,
                             timeout_seconds=effective_timeout, **diagnostics)
                if getattr(self, "model_id", None) == FREE_MODEL_ID:
                    raise RuntimeError("Free model request timed out before billing could be verified") from exc
                if not self.timeout_retries_remaining:
                    raise ProviderTimeout({
                        "role": "exit", "content": f"Model request exceeded {timeout_seconds} seconds",
                        "extra": {"exit_status": "ProviderTimeout", "submission": ""},
                    }) from None
                self.timeout_retries_remaining -= 1
                attempt += 1

    @staticmethod
    def format_message(**kwargs) -> dict:
        return kwargs

    def format_observation_messages(self, message: dict, outputs: list[dict], template_vars=None) -> list[dict]:
        return format_toolcall_observation_messages(
            actions=message["extra"]["actions"], outputs=outputs,
            observation_template=self.observation_template, template_vars=template_vars,
        )

    def get_template_vars(self) -> dict:
        return {}


class CourseModel(ModelFormatting):
    argument_type = BashArguments
    action_name = "bash"

    def __init__(self, run_dir: Path, limits: RunLimits, observation_template: str):
        self.limits = limits
        self.model_id = os.environ["COURSE_MODEL_ID"]
        self.trace = run_dir / "model.jsonl"
        self.observation_template = observation_template
        self.transport = BoyueTransport()
        self.request_id = 0
        self.timeout_retries_remaining = limits.timeout_retries

    def query(self, messages: list[dict], **kwargs) -> dict:
        self.request_id += 1
        history = [{key: val for key, val in message.items() if key != "extra"} for message in messages]
        tool = {"type": "function", "function": {"name": self.action_name,
                "description": "Execute one action in the isolated benchmark environment.",
                "parameters": self.argument_type.model_json_schema()}}
        payload = {
            "model": self.model_id, "messages": history, "tools": [tool],
            "max_tokens": self.limits.max_output_tokens, "reasoning_effort": "max",
            "stream": False, "tool_choice": "auto",
        }
        timeout = min(150, self.limits.wall_seconds)
        try:
            response, attempt = self.request_with_timeout_recovery(
                lambda: self.transport.send(payload, min(timeout, self.budget.request_seconds())
                                            if getattr(self, "budget", None) else timeout),
                {"payload": payload}, BoyueTimeout, timeout,
            )
        except ProviderTimeout:
            raise
        except BoyueTransportError as exc:
            append_event(self.trace, "request_error", request_id=self.request_id,
                         **exc.diagnostics)
            raise
        raw = response.payload
        append_event(self.trace, "response", request_id=self.request_id, attempt=attempt, payload=raw,
                     transport=response.model_dump(exclude={"payload"}, exclude_none=True))
        actions = []
        try:
            if len(raw["choices"]) != 1:
                raise ValueError("Exactly one response choice is required")
            choice = raw["choices"][0]
            if choice["finish_reason"] not in {"tool_calls", "stop"}:
                raise ValueError("Incomplete model response: " + str(choice["finish_reason"]))
            message = choice["message"]
            calls = message.get("tool_calls") or []
            if len(calls) != 1:
                raise ValueError("Return exactly one structured tool action")
            call = calls[0]
            if call["type"] != "function" or call["function"]["name"] != self.action_name:
                raise ValueError("Only the registered action function is available")
            args = self.argument_type.model_validate_json(call["function"]["arguments"])
            actions.append(args.model_dump() | {"tool_call_id": call["id"]})
        except (ValidationError, ValueError, KeyError, TypeError) as exc:
            raise FormatError({"role": "user", "content": str(exc),
                               "extra": {"request_id": self.request_id, "response": raw}}) from None
        message["extra"] = {"actions": actions, "request_id": self.request_id}
        return message

    def serialize(self) -> dict:
        return {"info": {"config": {"model": self.model_id, "transport": "chat-completions",
                                    "max_output_tokens": self.limits.max_output_tokens,
                                    "reasoning_effort": "max", "endpoint": "https://apicz.boyuerichdata.com/v1",
                                    "native_actions": self.action_name, "sdk_retries": 0}}}


class CodeBuddyModel(ModelFormatting):
    argument_type = BashArguments
    action_name = "bash"
    selection_instruction = "one next bash command"
    def __init__(self, run_dir: Path, limits: RunLimits, observation_template: str):
        self.model_id = os.environ["COURSE_MODEL_ID"]
        self.cli = Path(os.environ["COURSE_CODEBUDDY_BIN"]).resolve(strict=True)
        self.run_dir = run_dir.resolve()
        self.trace = run_dir / "model.jsonl"
        self.observation_template = observation_template
        self.request_id = 0
        self.provider_turns = 0
        self.limits = limits
        self.timeout_retries_remaining = limits.timeout_retries

    def query(self, messages: list[dict], **kwargs) -> dict:
        self.request_id += 1
        history = [{key: val for key, val in message.items() if key != "extra"} for message in messages[1:]]
        system = messages[0]["content"] + (
            f"\nYou are selecting {self.selection_instruction} for an external, isolated benchmark environment. "
            + ("You cannot execute it yourself. Use StructuredOutput to return its command field. "
               if self.argument_type is BashArguments else
               "You cannot execute it yourself. Use StructuredOutput to return the action specified by the schema. ")
            +
            "The supplied JSON is the prior conversation, with tool observations as data."
        )
        schema = json.dumps(self.argument_type.model_json_schema())
        prompt = json.dumps(history, ensure_ascii=False)
        command = [str(self.cli), "--print", "--model", self.model_id, "--tools", "StructuredOutput",
                   "--allowedTools", "StructuredOutput", "--strict-mcp-config", "--permission-mode", "dontAsk",
                   "--no-session-persistence", "--max-turns", "1", "--output-format", "json", "--json-schema",
                   schema, "--system-prompt", system]
        if self.model_id == FREE_MODEL_ID:
            command += ["--setting-sources", "", "--settings", '{"disableAllHooks":true}',
                        "--mcp-config", '{"mcpServers":{}}']
        environment = {key: value for key, value in os.environ.items() if key.lower() not in {
            "http_proxy", "https_proxy", "all_proxy", "course_api_key", "openai_api_key", "anthropic_api_key",
        }}
        if self.model_id == FREE_MODEL_ID:
            environment.update({"NODE_OPTIONS": "--use-bundled-ca", "CODEBUDDY_MAX_RETRIES": "0",
                                "CODEBUDDY_MODEL_401_MAX_RETRIES": "0", "CODEBUDDY_RETRY_WATCHDOG": "0",
                                "CODEBUDDY_MODEL": FREE_MODEL_ID,
                                "CODEBUDDY_SMALL_FAST_MODEL": FREE_MODEL_ID,
                                "CODEBUDDY_BIG_SLOW_MODEL": FREE_MODEL_ID})
            environment.pop("CODEBUDDY_FALLBACK_MODEL", None)
        # CodeBuddy 的打印模式需要显式请求文本。通过 stdin 提供大型历史。
        timeout = self.limits.wall_seconds if self.model_id == FREE_MODEL_ID else min(150, self.limits.wall_seconds)
        process, attempt = self.request_with_timeout_recovery(
            lambda: subprocess.run([*command, "Choose the next command from the conversation on stdin."],
                                   input=prompt, cwd=self.run_dir, env=environment,
                                   text=True, capture_output=True,
                                   timeout=min(timeout, self.budget.request_seconds()) if getattr(self, "budget", None) else timeout,
                                   check=False),
            {"model": self.model_id, "system": system, "history": history, "schema": json.loads(schema)},
            subprocess.TimeoutExpired, timeout,
        )
        if process.returncode:
            append_event(self.trace, "request_error", request_id=self.request_id, attempt=attempt,
                         returncode=process.returncode, stderr=process.stderr, stdout=process.stdout)
            raise RuntimeError(f"CodeBuddy failed with exit code {process.returncode}")
        try:
            raw = json.loads(process.stdout)
        except json.JSONDecodeError:
            append_event(self.trace, "request_error", request_id=self.request_id, attempt=attempt,
                         returncode=process.returncode, stderr=process.stderr, stdout=process.stdout)
            raise RuntimeError("CodeBuddy returned a non-JSON response") from None
        append_event(self.trace, "response", request_id=self.request_id, attempt=attempt, payload=raw)
        if self.model_id == FREE_MODEL_ID:
            try:
                billing = verify_free_response(raw)
            except (ValidationError, ValueError, TypeError) as exc:
                append_event(self.trace, "billing_error", request_id=self.request_id, detail=str(exc))
                raise RuntimeError("Free model billing validation failed") from exc
            append_event(self.trace, "billing_verified", request_id=self.request_id, **billing)
        result = next(event for event in reversed(raw) if event.get("type") == "result")
        if result.get("is_error") or result.get("subtype") != "success":
            raise RuntimeError(f"CodeBuddy returned {result.get('subtype')}")
        self.provider_turns += result["num_turns"]
        try:
            action = self.argument_type.model_validate(result.get("structured_output"))
        except ValidationError as exc:
            raise FormatError({"role": "user", "content": f"Invalid structured output: {exc}",
                               "extra": {"request_id": self.request_id}}) from None
        call_id = f"codebuddy-{self.request_id}"
        return {
            "role": "assistant", "content": result.get("result") or "",
            "tool_calls": [{"type": "function", "id": call_id,
                            "function": {"name": self.action_name, "arguments": action.model_dump_json()}}],
            "extra": {"actions": [action.model_dump() | {"tool_call_id": call_id}],
                      "request_id": self.request_id},
        }

    def serialize(self) -> dict:
        return {"info": {"config": {"model": self.model_id, "transport": "codebuddy-structured-output"},
                         "provider_reported_turns": self.provider_turns,
                         "output_token_limit_enforced_by_adapter": False}}


class TracedEnvironment:
    def __init__(self, target, run_dir: Path, limits: RunLimits, verification: VerificationState | None = None,
                 *, automatic_checks: bool = False, budget_feedback: bool = False):
        self.target = target
        self.run_dir = run_dir
        self.limits = limits
        self.verification = verification
        self.commands_executed = 0
        self.automatic_checks = automatic_checks
        self.budget_feedback = budget_feedback
        self.started = time.monotonic()
        self.midpoint_checked = False

    def run_public_checks(self, reason: str) -> str:
        results = self.verification.inspect(self.target, self.limits.command_seconds)
        messages = []
        for check_id, record in results.items():
            if record.state == "passed":
                continue
            check = self.verification.checks[check_id]
            before = self.verification.snapshot(check, self.target, self.limits.command_seconds)
            output = self.target.exec(check.command, timeout=self.limits.command_seconds)
            after = self.verification.snapshot(check, self.target, self.limits.command_seconds)
            observed = self.verification.observe(check, before, after, output["returncode"])
            append_event(self.run_dir / "verification.jsonl", "automatic_public_check", reason=reason,
                         step=self.commands_executed, check=asdict(check), before=before, after=after,
                         evidence=asdict(observed), **output)
            messages.append(f"Public check {check_id}: {observed.state}, exit {output['returncode']}\n"
                            + output["stdout"] + output["stderr"])
        return "\n".join(messages)

    def budget_message(self) -> str:
        seconds = max(0, self.limits.wall_seconds - (time.monotonic() - self.started))
        remaining = max(0, self.limits.model_calls - self.commands_executed)
        return (f"\nExecution budget: approximately {seconds:.0f} seconds and {remaining} decisions remaining. "
                "Save runnable changes at the required paths; use remaining time to validate task semantics and repair failures.")

    def get_template_vars(self) -> dict:
        return self.target.system_info

    def serialize(self) -> dict:
        return {"info": {"environment": self.target.system_info}}

    def deliverable_reminder(self) -> str:
        if self.verification is None or self.commands_executed != DELIVERABLE_CHECKPOINT:
            return ""
        deliverables = dict.fromkeys(name for check in self.verification.checks.values() for name in check.deliverables)
        if not deliverables:
            return ""
        paths = shlex.join(deliverables)
        command = f"for file in {paths}; do test -s \"$file\" || printf '%s\\n' \"$file\"; done"
        probe = self.target.exec(command, timeout=min(5, self.limits.command_seconds))
        missing = probe["stdout"].splitlines() if probe["returncode"] == 0 else []
        append_event(self.run_dir / "verification.jsonl", "deliverable_checkpoint",
                     step=self.commands_executed, missing=missing, **probe)
        if missing:
            return "\nRequired deliverables still missing or empty: " + ", ".join(missing) + ". Save a draft before further exploration."
        return ""

    def execute(self, action: dict, cwd: str = "") -> dict:
        command = BashArguments.model_validate({"command": action["command"]}).command
        check = self.verification.commands.get(command.strip()) if self.verification and not cwd else None
        current = self.verification if check and self.verification.invalidate else None
        before = current.snapshot(check, self.target, self.limits.command_seconds) if current else None
        output = self.target.exec(command, cwd=cwd, timeout=self.limits.command_seconds)
        self.commands_executed += 1
        append_event(self.run_dir / "tools.jsonl", "bash", command=command,
                     cwd=cwd or self.target.cwd, tool_call_id=action.get("tool_call_id"), **output)
        if check:
            after = current.snapshot(check, self.target, self.limits.command_seconds) if current else None
            record = self.verification.observe(check, before, after, output["returncode"])
            append_event(self.run_dir / "verification.jsonl", "public_check", check=asdict(check),
                         before=before, after=after, **asdict(record))
        lines = output["stdout"].lstrip().splitlines(keepends=True)
        if output["returncode"] == 0 and lines and lines[0].strip() == SUBMIT:
            submission = "".join(lines[1:])
            if self.verification:
                automatic_report = self.run_public_checks("submission") if self.automatic_checks else ""
                evidence = self.verification.inspect(self.target, self.limits.command_seconds)
                unmet = [check_id for check_id, result in evidence.items() if result.state != "passed"]
                partial = submission.startswith("PARTIAL:") and bool(submission.removeprefix("PARTIAL:").strip())
                append_event(self.run_dir / "verification.jsonl", "submission_check",
                             state={key: asdict(value) for key, value in evidence.items()}, partial=partial,
                             blocked=bool(unmet and not partial))
                if unmet and not partial:
                    diagnostics = "\n".join(
                        f"{key}: {evidence[key].state}; run `{self.verification.checks[key].command}`"
                        for key in unmet
                    )
                    return {"output": automatic_report + "\nSubmission paused. Verify the current artifact:\n" + diagnostics
                            + "\nFor a partial result, put PARTIAL: followed by the unresolved issues on the next line.",
                            "returncode": 2, "exception_info": ""}
            raise Submitted({"role": "exit", "content": submission,
                             "extra": {"exit_status": "Submitted", "submission": submission}})
        reminder = self.deliverable_reminder()
        if self.automatic_checks and not self.midpoint_checked and (
            self.commands_executed >= 8 or time.monotonic() - self.started >= self.limits.wall_seconds / 2
        ):
            self.midpoint_checked = True
            reminder += "\n" + self.run_public_checks("midpoint")
        if self.budget_feedback:
            reminder += self.budget_message()
        return {"output": output["stdout"] + output["stderr"] + reminder, "returncode": output["returncode"],
                "exception_info": output.get("exception_info", "")}


def run_baseline(task: str, target, directory: Path, limits: RunLimits, *,
                 configuration: str = "B0", checks: tuple[PublicCheck, ...] = (), scope: dict | None = None) -> dict:
    if configuration in {"C0", "C1"} or limits.strict_wall:
        from course_eval.controller import run_controlled
        return run_controlled(task, target, directory, limits, configuration, checks, scope)
    if configuration not in {"B0", "BP", "A", "F", "R", "RP"}:
        raise ValueError(f"Unknown configuration: {configuration}")
    for check in checks:
        check.validate(task)
    if configuration != "B0" and not checks:
        raise ValueError("A treatment trial requires a task-visible check plan")
    config = get_config_from_spec(builtin_config_dir / "mini.yaml")
    state = (VerificationState(checks, invalidate=configuration in {"F", "R", "RP"})
             if configuration in {"A", "F", "R", "RP"} else None)
    env = TracedEnvironment(target, directory, limits, state, automatic_checks=configuration == "R",
                            budget_feedback=configuration in {"R", "RP"})
    if configuration != "B0":
        checks_text = "\n".join(f"- {check.source_quote} Execute `{check.command}` as its own command." for check in checks)
        config["agent"]["instance_template"] += (
            "\n\nBefore submitting, run these public checks on the current artifact. Repeat a check if "
            "its dependencies changed. If you submit a partial result, print a second line starting with "
            "PARTIAL: and name the unresolved requirements.\n" + checks_text
        )
        deliverables = dict.fromkeys(name for check in checks for name in check.deliverables)
        if deliverables:
            config["agent"]["instance_template"] += (
                f"\nBy shell step {DELIVERABLE_CHECKPOINT}, check whether these required deliverables exist and are nonempty: "
                + ", ".join(deliverables) + ". Save a draft before further exploration if any are missing."
            )
    if configuration in {"R", "RP"}:
        config["agent"]["instance_template"] += (
            "\nWork within the stated execution budget. Produce a runnable candidate early, then improve it. "
            "Derive a small executable reproducer from the task requirements and verify the requested behavior, "
            "including boundary conditions and preserved behavior. A syntax check or a test that repeats your "
            "implementation's assumptions cannot establish semantic correctness. Reserve time to run and repair "
            "tests; leave the best validated runnable candidate in the required files before time expires. "
            "If a compound shell command contains a failing step, diagnose that failure even when its final exit code is zero."
        )
    backend = {"course": CourseModel, "codebuddy": CodeBuddyModel}[os.environ["COURSE_MODEL_BACKEND"]]
    model = backend(directory, limits, config["model"]["observation_template"])
    agent = DefaultAgent(model, env, system_template=config["agent"]["system_template"],
                         instance_template=config["agent"]["instance_template"],
                         step_limit=limits.model_calls, cost_limit=0,
                         wall_time_limit_seconds=limits.wall_seconds,
                         output_path=directory / "agent.json")
    (directory / "instruction.txt").write_text(task, encoding="utf-8")
    return agent.run(task)
