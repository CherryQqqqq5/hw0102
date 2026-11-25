import copy
import hashlib
import json
import time
import uuid
from pathlib import Path
from typing import ClassVar

from jsonschema import Draft202012Validator, ValidationError as JsonSchemaError
from minisweagent.exceptions import FormatError, TimeExceeded
from pydantic import BaseModel, ConfigDict, model_validator

from course_eval.agent import CodeBuddyModel, append_event
from course_eval.controller import Budget


def normalized_history(messages):
    normalized = copy.deepcopy(messages)
    for message in normalized:
        if message.get("role") == "assistant":
            if message.get("content") is None:
                message["content"] = ""
            for call in message.get("tool_calls", []):
                arguments = call["function"]["arguments"]
                if isinstance(arguments, str):
                    call["function"]["arguments"] = json.loads(arguments)
    return normalized


class AssistantResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    external_tools: ClassVar[tuple[dict, ...]] = ()
    parameter_fields: ClassVar[tuple[str, ...]] = ("command", "file_path", "cd")
    action: str
    content: str = ""
    command: str | None = None
    file_path: str | None = None
    cd: str | None = None

    @model_validator(mode="after")
    def require_response(self):
        functions = {item["function"]["name"]: item["function"] for item in self.external_tools}
        if self.action == "final":
            if not self.content.strip() or any(getattr(self, name) is not None for name in self.parameter_fields):
                raise ValueError("A final response requires nonempty content and no tool arguments")
        else:
            if self.action not in functions:
                raise ValueError("The selected action is absent from the actual SDK catalog")
            parameters = functions[self.action]["parameters"]
            if any(getattr(self, name) is not None for name in self.parameter_fields
                   if name not in parameters.get("properties", {})):
                raise ValueError("An argument belongs to a different SDK tool")
            try:
                Draft202012Validator(parameters).validate(self.tool_arguments())
            except JsonSchemaError as exc:
                raise ValueError(exc.message) from exc
        return self

    def tool_arguments(self):
        return {name: getattr(self, name) for name in self.parameter_fields if getattr(self, name) is not None}

    @classmethod
    def __get_pydantic_json_schema__(cls, core_schema, handler):
        schema = handler.resolve_ref_schema(handler(core_schema))
        alternatives = []
        for item in cls.external_tools:
            function = item["function"]
            arguments = copy.deepcopy(function["parameters"])
            properties = arguments.get("properties", {})
            if (function["name"] == "final" or arguments.get("type") != "object"
                    or '"$ref"' in json.dumps(arguments) or set(properties) - set(cls.parameter_fields)
                    or any(value.get("type") != "string" for value in properties.values())):
                raise ValueError("The SDK catalog requires an explicit flat-schema adapter before inference")
            alternatives.append({"properties": {"action": {"const": function["name"]}, **{
                name: (properties[name] if name in arguments.get("required", []) else
                       {"anyOf": [properties[name], {"type": "null"}]}) if name in properties else {"type": "null"}
                for name in cls.parameter_fields}},
                "required": ["action", *arguments.get("required", [])]})
        alternatives.append({"properties": {"action": {"const": "final"},
            "content": {"type": "string", "minLength": 1, "pattern": r"\S"},
            **{name: {"type": "null"} for name in cls.parameter_fields}}, "required": ["action", "content"]})
        schema["oneOf"] = alternatives
        return schema


class DshFreeProvider(CodeBuddyModel):
    action_name = "assistant_response"
    selection_instruction = "one flat action using StructuredOutput: an external tool or a final answer"

    def __init__(self, directory, limits, stop_path):
        super().__init__(directory, limits, "")
        if self.model_id != "hy4flash-free" or not self.persist_native_session:
            raise ValueError("DSH requires the verified free model and persistent native context")
        self.budget = Budget(limits.wall_seconds)
        self.stop_path = Path(stop_path)
        self.previous_messages = None
        self.previous_tool_digest = None
        self.fresh_usage = {}

    def preserve_billing_stop(self):
        events = [json.loads(line) for line in self.trace.read_text().splitlines()] if self.trace.exists() else []
        requested = {row["request_id"] for row in events if row["event"] == "request"}
        verified = {row["request_id"] for row in events if row["event"] == "billing_verified"}
        if requested != verified or any(row["event"] in {"billing_error", "request_error"} for row in events):
            from course_eval.financial_stop import preserve_free_stop
            preserve_free_stop(self.stop_path, run_dir=str(self.run_dir),
                unverified_requests=sorted(requested - verified),
                reason="New DSH provider call lacks an individual valid zero-credit receipt")

    def process_response(self, raw):
        before = set(self.native_model_message_ids)
        try:
            return super().process_response(raw)
        finally:
            fresh = self.native_model_message_ids - before
            self.fresh_usage = {row["providerData"]["messageId"]: row["providerData"]["rawUsage"]
                                for row in raw if "rawUsage" in row.get("providerData", {})
                                and row["providerData"]["messageId"] in fresh}

    def require_single_generation(self):
        if len(self.fresh_usage) != 1:
            from course_eval.financial_stop import preserve_free_stop
            preserve_free_stop(self.stop_path, run_dir=str(self.run_dir), unverified_requests=[self.request_id],
                reason="A CLI invocation violated the single-generation protocol; receipts remain preserved")
            raise RuntimeError("The client must return exactly one fresh verified native generation")

    def reconcile_context(self, messages, tool_digest):
        normalized = normalized_history(messages)
        prefix_matches = (self.previous_messages is None or (
            normalized[:len(self.previous_messages)] == self.previous_messages
            and tool_digest == self.previous_tool_digest))
        if not prefix_matches:
            self.native_session_id = str(uuid.uuid4())
            self.native_session_started = False
            self.native_messages_seen = 1
            append_event(self.trace, "native_context_reset", reason="DSH changed its context or tool prefix",
                         native_session_id=self.native_session_id)
        return prefix_matches

    def __call__(self, body, index):
        stop = json.loads(self.stop_path.read_text())
        if stop["active"]:
            raise RuntimeError("New model calls remain stopped at the actual billing boundary")
        if index > self.limits.model_calls or self.request_id >= self.limits.model_calls:
            raise TimeExceeded({"role": "exit", "content": "Actual generation budget exhausted",
                                "extra": {"exit_status": "LimitsExceeded", "submission": ""}})
        if body.get("model") != self.model_id or body.get("reasoning_effort") not in {None, "high"}:
            raise ValueError("The SDK selected an unapproved model or reasoning setting")
        cap = body.get("max_tokens")
        if type(cap) is not int or not 0 < cap <= 64000:
            raise ValueError("Missing or unsupported actual SDK output limit")
        messages = copy.deepcopy(body["messages"])
        if not messages or messages[0]["role"] != "system" or not isinstance(messages[0]["content"], str):
            raise ValueError("DSH must provide its actual initial system text")
        tools = body.get("tools", [])
        schemas = {row["function"]["name"]: row["function"]["parameters"] for row in tools}
        if len(schemas) != len(tools) or any(row["type"] != "function" for row in tools):
            raise ValueError("The actual SDK tool catalog has an invalid or duplicate entry")
        self.argument_type = type("TaskAssistantResponse", (AssistantResponse,), {"external_tools": tuple(tools)})
        self.argument_type.model_json_schema()
        tool_digest = hashlib.sha256(json.dumps(tools, sort_keys=True).encode()).hexdigest()
        self.reconcile_context(messages, tool_digest)
        original_messages = copy.deepcopy(messages)
        messages[0]["content"] += ("\nUse StructuredOutput with the flat fields action, command, file_path, cd, content. "
            "Select one registered external tool in action and put its argument directly in the matching field. "
            "For example: action=bash with command containing the complete shell command. "
            "Do not encode a calls array or a JSON arguments object. Return action=final and nonempty content "
            "when the task is finished. The registered external tool definitions follow:\n"
            + json.dumps(tools, ensure_ascii=False))
        self.limits = self.limits.model_copy(update={"max_output_tokens": cap})
        response_usage = {}
        for attempt in range(3):
            if self.request_id >= self.limits.model_calls:
                raise TimeExceeded({"role": "exit", "content": "Actual generation budget exhausted",
                                    "extra": {"exit_status": "LimitsExceeded", "submission": ""}})
            self.fresh_usage = {}
            try:
                response = self.query(messages)
            except FormatError as exc:
                if not self.fresh_usage:
                    raise
                self.require_single_generation()
                response_usage.update(self.fresh_usage)
                if attempt == 2:
                    raise
                messages.extend(copy.deepcopy(exc.messages))
                append_event(self.trace, "external_format_recovery", request_id=self.request_id,
                             recovery=attempt + 1, billing_already_verified=True)
                continue
            except BaseException:
                self.preserve_billing_stop()
                raise
            self.require_single_generation()
            response_usage.update(self.fresh_usage)
            break
        action = self.argument_type.model_validate({key: value for key, value in response["extra"]["actions"][0].items()
                                                   if key != "tool_call_id"})
        calls = []
        if action.action != "final":
            arguments = action.tool_arguments()
            Draft202012Validator(schemas[action.action]).validate(arguments)
            calls.append({"id": f"course-{index}-0", "type": "function",
                          "function": {"name": action.action, "arguments": json.dumps(arguments)}})
        usage = {key: sum(row[key] for row in response_usage.values())
                 for key in ("prompt_tokens", "completion_tokens")}
        usage["total_tokens"] = usage["prompt_tokens"] + usage["completion_tokens"]
        message = {"role": "assistant", "content": action.content}
        if calls:
            message["tool_calls"] = calls
        result = {"id": f"course-free-{index}", "object": "chat.completion", "created": int(time.time()),
            "model": self.model_id, "choices": [{"index": 0, "message": message,
                "finish_reason": "tool_calls" if calls else "stop"}], "usage": usage,
            "actual_billing": {"credit": 0, "model": self.model_id,
                               "fresh_native_message_ids": sorted(response_usage)}}
        append_event(self.run_dir / "dsh-responses.jsonl", "verified_provider_response", response=result)
        self.previous_messages = normalized_history([*original_messages, message])
        self.previous_tool_digest = tool_digest
        self.native_messages_seen = len(original_messages) + 1
        return {"status": 200, "body": result}
