import copy
import json
import hashlib
import os
import subprocess
import sys
import tempfile
import time
from decimal import Decimal
from pathlib import Path

os.environ.setdefault("MSWEA_GLOBAL_CONFIG_DIR", str(Path.cwd() / "work/miniswe-config"))
os.environ.setdefault("MSWEA_SILENT_STARTUP", "1")

import keyring
import requests
from openai import LengthFinishReasonError
from openai._streaming import SSEDecoder
from openai.lib.streaming.chat._completions import ChatCompletionStreamState
from openai.types.chat import ChatCompletionChunk
from jsonschema import Draft202012Validator, ValidationError as JsonSchemaError
from pydantic import BaseModel, ConfigDict, Field

from minisweagent.models.openrouter_model import OpenRouterModel
from minisweagent.exceptions import FormatError, TimeExceeded

from course_eval.agent import append_event
from course_eval.image_input import native_image_turn, split_image_output
from course_eval.openrouter_free import OpenRouterFreeModel
from course_eval.financial_stop import free_query_blocked, preserve_free_stop
from course_eval.generation_registry import claim_generation


INFERENCE_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
FREE_POLICY_URL = "https://build.nvidia.com/api/runtime/content/help-center-faq.yaml"
VERIFICATION_TYPE = "official_non_billed_free_endpoint_with_per_request_identity_and_usage"
MONEY_FIELDS = ("cost", "cost_usd", "total_cost", "total_cost_usd", "credits")


class NvidiaFeeError(ValueError):
    pass


class NvidiaUsage(BaseModel):
    model_config = ConfigDict(extra="allow", strict=True)
    prompt_tokens: int = Field(ge=0)
    completion_tokens: int = Field(ge=0)
    total_tokens: int = Field(ge=0)


class NvidiaReceipt(BaseModel):
    model_config = ConfigDict(extra="allow", strict=True)
    id: str = Field(min_length=1)
    model: str = Field(min_length=1)
    usage: NvidiaUsage


def reported_model_identity(contract):
    model = contract.get("reported_model", contract["model"])
    if not isinstance(model, str) or not model.strip():
        raise ValueError("The contract must fix a nonempty exact reported model identity")
    if model != contract["model"] and contract.get("public_checkpoint_equivalence_verified") is not False:
        raise ValueError("A distinct reported identity must not assert public checkpoint equivalence")
    return model


def verify_nvidia_contract(contract, model):
    if (contract["inference_url"] != INFERENCE_URL or contract["provider"] != "nvidia"
            or contract["paid_fallbacks"] is not False or contract["model"] != model
            or contract["official_free_policy_url"] != FREE_POLICY_URL
            or "no per-token billing" not in contract["official_policy"]
            or contract["verification_type"] != VERIFICATION_TYPE
            or not contract["user_authorization"]):
        raise NvidiaFeeError("The request is outside the authorized official non-billed service")
    reported_model_identity(contract)


def reported_nvidia_cost(raw):
    reported = []
    for values in (raw, raw.get("usage") or {}):
        for field in MONEY_FIELDS:
            if field in values:
                value = values[field]
                if value is None:
                    continue
                if type(value) not in (int, float) or Decimal(str(value)) != 0:
                    raise NvidiaFeeError("The official free response reports a nonzero or invalid monetary cost")
                reported.append(value)
    return 0 if reported else None


def preserve_nvidia_fee_stop(stop_path, **details):
    preserve_free_stop(stop_path, **details)


def verify_nvidia_receipt(raw, model, output_limit):
    reported_nvidia_cost(raw)
    receipt = NvidiaReceipt.model_validate(raw)
    if receipt.model != model:
        raise ValueError("The actual model does not match the fixed NVIDIA model")
    if receipt.usage.completion_tokens > output_limit:
        raise ValueError("The provider exceeded the configured output budget")
    return receipt


def read_nvidia_stream(response, on_event, byte_iterator=None, on_done=None):
    state = ChatCompletionStreamState()
    complete = False
    identity = None
    if byte_iterator is None:
        byte_iterator = response.iter_content(chunk_size=4096)
    for event in SSEDecoder().iter_bytes(byte_iterator):
        if event.data == "[DONE]":
            complete = True
            if on_done is not None:
                on_done()
            break
        raw = json.loads(event.data)
        on_event(raw)
        reported_nvidia_cost(raw)
        if raw.get("error"):
            raise ValueError("The provider reported a stream error")
        if raw.get("usage") is not None:
            NvidiaUsage.model_validate(raw["usage"])
        chunk = ChatCompletionChunk.model_validate(raw, strict=True)
        if identity is None:
            identity = (chunk.id, chunk.model)
        elif (chunk.id, chunk.model) != identity:
            raise ValueError("The stream changed its actual generation or model identity")
        list(state.handle_chunk(chunk))
    if not complete:
        raise ValueError("The stream ended without its terminal DONE event")
    try:
        completion = state.get_final_completion()
    except LengthFinishReasonError as exc:
        completion = exc.completion
    return completion.model_dump(exclude_none=True)


def admit_nvidia_channel(contract_path, qualification_path, output_limit):
    contract = json.loads(contract_path.read_text())
    verify_nvidia_contract(contract, contract["model"])
    qualification = json.loads(qualification_path.read_text())
    qualification_contract_path = contract_path
    if contract.get("qualification_contract_path"):
        qualification_contract_path = Path(contract["qualification_contract_path"])
        if not qualification_contract_path.is_absolute():
            qualification_contract_path = contract_path.parent / qualification_contract_path
    qualification_contract = json.loads(qualification_contract_path.read_text())
    verify_nvidia_contract(qualification_contract, contract["model"])
    if reported_model_identity(qualification_contract) != reported_model_identity(contract):
        raise NvidiaFeeError("The qualification fixes a different exact reported provider model")
    if (qualification["verified"] is not True or qualification["http_status"] != 200
            or qualification["contract_sha256"] != hashlib.sha256(qualification_contract_path.read_bytes()).hexdigest()
            or qualification["free_policy_verified"] is not True
            or qualification["response_identity_and_usage_verified"] is not True
            or output_limit > contract["maximum_output_tokens"]):
        raise NvidiaFeeError("The fixed NVIDIA channel lacks its bound successful real qualification")
    raw = (qualification["assembled_response"] if "assembled_response" in qualification
           else json.loads(qualification["raw_response"]))
    receipt = verify_nvidia_receipt(raw, reported_model_identity(contract), qualification["request"]["max_tokens"])
    if receipt.id != qualification["generation_id"]:
        raise NvidiaFeeError("The qualification generation does not match its actual response")
    return contract, qualification


def nvidia_queue_snapshot(contract):
    expected = "https://buildapi.ngc.nvidia.com/v2/predict/queues/models/qc69jvmznzxy/" + contract["model"].split("/", 1)[1]
    if contract["queue_url"] != expected:
        raise ValueError("The capacity check does not match the qualified public model")
    response = requests.get(expected, timeout=20, allow_redirects=False)
    response.raise_for_status()
    data = response.json()
    if data["functionId"] != contract["observed_nvcf_function_id"]:
        raise ValueError("The live public model routing changed")
    active = [row for row in data["queues"] if row["functionStatus"] == "ACTIVE"]
    if not active or any(type(row["queueDepth"]) is not int or row["queueDepth"] < 0 for row in active):
        raise ValueError("The active model queue depth is unavailable")
    return {"url": expected, "response": data,
            "ready": min(row["queueDepth"] for row in active) <= contract["maximum_admission_queue_depth"]}


def audit_nvidia_events(events, contract_path, model, output_limit):
    checksum = hashlib.sha256(contract_path.read_bytes()).hexdigest()
    contract = json.loads(contract_path.read_text())
    verify_nvidia_contract(contract, model)
    expected_reported_model = reported_model_identity(contract)
    requests_by_id = {}
    responses = {}
    proofs = {}
    for row in events:
        if row["event"] in {"request", "response", "billing_verified"}:
            selected = {"request": requests_by_id, "response": responses, "billing_verified": proofs}[row["event"]]
            if row["request_id"] in selected:
                raise ValueError("The NVIDIA trace repeats a physical request, response or proof")
            selected[row["request_id"]] = row
    seen_generations = set()
    first_request = next((index for index, row in enumerate(events) if row["event"] == "request"), len(events))
    policies = [row for row in events[:first_request] if row["event"] == "free_service_policy_verified"]
    if requests_by_id and (not policies or any(row["verification_type"] != VERIFICATION_TYPE
            or row["policy_url"] != FREE_POLICY_URL or row["contract_sha256"] != checksum for row in policies)):
        raise NvidiaFeeError("The actual NVIDIA calls lack their verified official free-service policy")
    for request_id, proof in proofs.items():
        request = requests_by_id[request_id]
        if request["endpoint"] != INFERENCE_URL or request["payload"]["model"] != model:
            raise NvidiaFeeError("The actual NVIDIA request differs from its fixed free endpoint")
        raw = responses[request_id]["payload"]
        receipt = verify_nvidia_receipt(raw, expected_reported_model, output_limit)
        actual_cost = reported_nvidia_cost(raw)
        if (receipt.id in seen_generations or proof["generation_id"] != receipt.id
                or proof["request_model"] != model or proof["provider_model"] != expected_reported_model
                or proof["verification_type"] != VERIFICATION_TYPE
                or proof["contract_sha256"] != checksum or proof["usage"] != receipt.usage.model_dump()
                or proof["reported_monetary_cost"] != actual_cost
                or proof["monetary_receipt_available"] is not (actual_cost is not None)):
            raise ValueError("The NVIDIA proof does not match its actual individual response")
        seen_generations.add(receipt.id)
    return {"actual_requests": len(requests_by_id), "verified_nonbilled_service_calls": len(proofs),
            "actual_monetary_receipt_calls": sum(row["monetary_receipt_available"] for row in proofs.values()),
            "unverified_requests": sorted(set(requests_by_id) - set(proofs)),
            "reported_monetary_cost": None if not proofs or not all(row["monetary_receipt_available"] for row in proofs.values()) else 0,
            "verification_type": VERIFICATION_TYPE, "contract_sha256": checksum}


def run_json_process(command, value, timeout, directory):
    with tempfile.TemporaryFile(dir=directory) as output, tempfile.TemporaryFile(dir=directory) as errors:
        completed = subprocess.run(command, input=json.dumps(value, ensure_ascii=False).encode(),
            stdout=output, stderr=errors, timeout=timeout, check=False)
        output.seek(0)
        body = output.read()
        errors.seek(0)
        detail = errors.read().decode("utf-8", errors="replace")
    if completed.returncode:
        raise RuntimeError(f"The NVIDIA request process exited {completed.returncode}: {detail[:2000]}")
    return json.loads(body)


def nvidia_http_worker(spec):
    contract_path = Path(os.environ["COURSE_NVIDIA_FREE_CONTRACT"])
    contract = json.loads(contract_path.read_text())
    verify_nvidia_contract(contract, spec["payload"]["model"])
    if type(keyring.get_keyring()).__module__ != "keyring.backends.macOS":
        raise RuntimeError("Expected the authorized macOS Keychain backend")
    secret = keyring.get_password("course-eval-free-nvidia", "course-eval-local")
    if not secret:
        raise RuntimeError("The configured NVIDIA credential is missing")
    remaining = spec["deadline_monotonic"] - time.monotonic()
    if remaining <= 0:
        raise TimeoutError("The NVIDIA deadline expired before transport startup")
    trace = Path(spec["trace"])
    stream_trace = Path(spec["stream_trace"])
    if free_query_blocked(Path(os.environ["COURSE_FREE_STOP_PATH"]), spec["payload"]["model"]):
        raise RuntimeError("No HTTP dispatch: a new shared financial stop arrived before the worker POST")
    append_event(trace, "request", request_id=spec["request_id"], attempt=1,
        endpoint=INFERENCE_URL, payload=spec["payload"], verification_type=VERIFICATION_TYPE)
    with requests.post(INFERENCE_URL, json=spec["payload"],
            headers={"Authorization": "Bearer " + secret, "Accept": "text/event-stream"},
            timeout=(min(10, remaining), remaining), stream=True, allow_redirects=False) as response:
        append_event(trace, "response_headers", request_id=spec["request_id"],
            http_status=response.status_code, response_ids={key: value for key, value in response.headers.items()
                if key.lower() in {"nvcf-reqid", "x-request-id", "x-generation-id"}},
            response_rate_limits={key: value for key, value in response.headers.items()
                if key.lower() == "retry-after" or key.lower().startswith(("x-ratelimit-", "ratelimit-"))})
        if response.status_code != 200:
            pieces = []
            for piece in response.iter_content(chunk_size=4096):
                pieces.append(piece)
                if sum(map(len, pieces)) >= 16384:
                    break
            detail = b"".join(pieces)[:16384].decode("utf-8", errors="replace").replace(secret, "[REDACTED API KEY]")
            append_event(trace, "http_error_body", request_id=spec["request_id"],
                         http_status=response.status_code, body=detail)
        response.raise_for_status()
        return read_nvidia_stream(response, lambda event: append_event(stream_trace,
            "stream_packet", request_id=spec["request_id"], payload=event),
            on_done=lambda: append_event(stream_trace, "stream_done", request_id=spec["request_id"]))


class NvidiaFreeModel(OpenRouterFreeModel):
    reasoning_effort = "low"
    minimum_request_seconds = 900.0
    minimum_request_interval_seconds = 15.0
    _previous_request_started = 0.0
    image_input_limit_instruction = "\nThis endpoint accepts at most eight images in one request. Older images leave the request window after eight; their archived observations remain available. Use labeled contact sheets and retain important visual findings in text.\n"
    control_instance_template = """Please solve this issue: {{task}}

You can inspect files, execute shell commands and edit files in the task environment.
Available native functions are bash, verify, save, restore and submit. Every turn
must call exactly one function with its own parameters. For example, call bash with
{"command":"ls -la"}; call verify with {"check_id":"..."}; call submit with {}.
Do not add an operation field or call a function named action.
Use the registered JSON Schema for the parameters of each operation.
Analyze the relevant files, reproduce the issue, implement a solution, and test relevant
edge cases. Deliver the required artifact and call submit with {}
when finished. Submission ends the task.
Before submit, call verify with each registered check_id on the final artifact.
Running a checker through bash does not record registered verification evidence.
After the registered checks pass, call save to preserve the verified candidate.
Each shell command runs in a new subshell; working-directory and environment changes
do not persist. Use an explicit cd or environment assignment in each command as needed.

<system_information>
{{system}} {{release}} {{version}} {{machine}}
</system_information>
"""

    def __init__(self, run_dir, limits, observation_template):
        self.stop_path = Path(os.environ["COURSE_FREE_STOP_PATH"])
        self.contract_path = Path(os.environ["COURSE_NVIDIA_FREE_CONTRACT"])
        self.qualification_path = Path(os.environ["COURSE_NVIDIA_FREE_QUALIFICATION"])
        self.contract, self.qualification = admit_nvidia_channel(
            self.contract_path, self.qualification_path, limits.max_output_tokens)
        self.model_id = os.environ["COURSE_MODEL_ID"]
        if self.model_id != self.contract["model"]:
            raise NvidiaFeeError("The requested NVIDIA model differs from the qualified fixed model")
        self.images_enabled = self.model_id in {
            "mistralai/mistral-large-4-1t-a52b", "nvidia/nemotron-3.5-super-vl-120b-a12b",
            "stepfun-ai/step-5-preview"}
        OpenRouterModel.__init__(self, model_name=self.model_id, observation_template=observation_template,
                                 model_kwargs={"max_tokens": limits.max_output_tokens})
        if type(keyring.get_keyring()).__module__ != "keyring.backends.macOS":
            raise RuntimeError("Expected the authorized macOS Keychain backend")
        self.trace = run_dir / "model.jsonl"
        self.stream_trace = run_dir / "model-stream.jsonl"
        self.limits = limits
        self.request_id = 0
        self.generation_ids = {self.qualification["generation_id"]} | set(json.loads(os.environ.get("COURSE_PRIOR_FREE_GENERATION_IDS", "[]")))
        self.session = requests.Session()
        self.session.max_redirects = 0
        try:
            policy = self.session.get(FREE_POLICY_URL, timeout=20, allow_redirects=False)
            policy.raise_for_status()
            if not any("no per-token billing" in row["answer"] for row in policy.json()):
                raise NvidiaFeeError("The official free-service policy could not be verified")
        except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
            preserve_nvidia_fee_stop(self.stop_path, reason="The current official NVIDIA non-billing policy is unverified",
                                    local_error_type=type(exc).__name__)
            raise
        append_event(self.trace, "free_service_policy_verified", provider="nvidia",
            verification_type=VERIFICATION_TYPE, policy_url=FREE_POLICY_URL,
            policy_sha256=hashlib.sha256(policy.content).hexdigest(),
            contract_sha256=hashlib.sha256(self.contract_path.read_bytes()).hexdigest(),
            qualification_generation_id=self.qualification["generation_id"],
            reported_monetary_cost=None, monetary_receipt_available=False)

    def _prepare_messages_for_api(self, messages):
        prepared = copy.deepcopy(super()._prepare_messages_for_api(messages))
        positions = [(message_index, part_index) for message_index, message in enumerate(prepared)
            if isinstance(message.get("content"), list) for part_index, part in enumerate(message["content"])
            if part.get("type") == "image_url"]
        for message_index, part_index in positions[-8:]:
            native_image_turn([{"role": "user", "content": [prepared[message_index]["content"][part_index]]}])
        for message_index, part_index in positions[:-8]:
            prepared[message_index]["content"][part_index] = {"type": "text",
                "text": "[Earlier image omitted from this request to respect the eight-image limit; the original remains in the archived observation.]"}
        if len(positions) > 8:
            append_event(self.trace, "image_history_window", omitted_images=len(positions) - 8, retained_images=8)
        return prepared

    def format_observation_messages(self, message, outputs, template_vars=None):
        if not getattr(self, "images_enabled", False):
            return super().format_observation_messages(message, outputs, template_vars)
        cleaned, attachments = [], []
        for output in outputs:
            try:
                text, images = split_image_output(output["output"])
                if images:
                    native_image_turn([{"role": "user", "content": images}])
            except ValueError as exc:
                text = "<image_input_error>" + str(exc) + ". Regenerate a complete, smaller inline image observation.</image_input_error>"
                images = []
                append_event(self.trace, "image_input_rejected", detail=str(exc))
            cleaned.append(output | {"output": text})
            attachments.append(images)
        observations = super().format_observation_messages(message, cleaned, template_vars)
        for observation, images in zip(observations, attachments, strict=True):
            if images:
                observation["content"] = [{"type": "text", "text": observation["content"]}, *images]
                append_event(self.trace, "image_observation", tool_call_id=observation["tool_call_id"],
                             image_count=len(images), transport="openai_image_url_content_parts")
        return observations

    def tool_definitions(self):
        if not hasattr(self.argument_type, "required_fields"):
            return [{"type": "function", "function": {"name": self.action_name,
                "description": "Return one complete result using the registered schema.",
                "parameters": self.argument_type.model_json_schema()}}]
        schema = self.argument_type.model_json_schema()
        tools = []
        for branch in schema["oneOf"]:
            operation = branch["properties"]["operation"]["const"]
            field = self.argument_type.required_fields[operation]
            properties = {"note": copy.deepcopy(schema["properties"]["note"])}
            if field:
                original = schema["properties"][field]
                text = next(item for item in original.get("anyOf", [original]) if item.get("type") == "string")
                properties[field] = copy.deepcopy(text) | branch["properties"][field]
            tools.append({"type": "function", "function": {"name": operation,
                "description": "Execute the " + operation + " operation in the isolated task environment.",
                "parameters": {"type": "object", "properties": properties,
                    "required": [field] if field else [], "additionalProperties": False}}})
        return tools

    def _parse_actions(self, response):
        if not hasattr(self.argument_type, "required_fields"):
            return super()._parse_actions(response)
        try:
            if len(response.get("choices", [])) != 1 or response["choices"][0].get("finish_reason") not in {"tool_calls", "stop"}:
                raise ValueError("Return one complete native function call within the output budget")
            calls = response["choices"][0]["message"].get("tool_calls") or []
            if len(calls) != 1:
                raise ValueError("Return exactly one registered native function")
            call = calls[0]
            schemas = {item["function"]["name"]: item["function"]["parameters"] for item in self.tool_definitions()}
            name = call["function"]["name"]
            if name not in schemas:
                raise ValueError("The returned function is outside the registered native catalog")
            arguments = json.loads(call["function"]["arguments"])
            Draft202012Validator(schemas[name]).validate(arguments)
            action = self.argument_type.model_validate({"operation": name, **arguments})
            return [action.model_dump() | {"tool_call_id": call["id"]}]
        except (ValueError, TypeError, KeyError, JsonSchemaError) as exc:
            raise FormatError({"role": "user", "content": str(exc),
                               "extra": {"interrupt_type": "FormatError"}}) from exc

    def _query(self, messages, **kwargs):
        if kwargs:
            raise ValueError("Unexpected per-request overrides would change the frozen NVIDIA protocol")
        tools = self.tool_definitions()
        payload = {"model": self.model_id, "messages": messages,
            "tools": tools,
            "tool_choice": "required" if len(tools) > 1 else {"type": "function", "function": {"name": self.action_name}},
            "parallel_tool_calls": False,
            "max_tokens": self.limits.max_output_tokens, "temperature": 1, "top_p": 0.95,
            "stream": True, "stream_options": {"include_usage": True}}
        if self.model_id == "mistralai/mistral-large-4-1t-a52b":
            payload["reasoning_effort"] = self.reasoning_effort
        return self.request_payload(payload)

    def request_payload(self, payload):
        return self._single_request_payload(payload)

    def _single_request_payload(self, payload):
        if free_query_blocked(self.stop_path, self.model_id):
            raise NvidiaFeeError("New model calls are stopped for an unresolved fee")
        if (payload.get("model") != self.model_id or type(payload.get("max_tokens")) is not int
                or not 0 < payload["max_tokens"] <= self.limits.max_output_tokens):
            raise ValueError("The actual payload differs from the fixed free model or output allowance")
        if self.request_id >= self.limits.model_calls:
            raise TimeExceeded({"role": "exit", "content": "Actual model generation budget exhausted",
                                "extra": {"exit_status": "LimitsExceeded", "submission": ""}})
        budget = getattr(self, "budget", None)
        while True:
            if free_query_blocked(self.stop_path, self.model_id):
                raise NvidiaFeeError("New model calls are stopped for an unresolved fee")
            available = budget.request_seconds() if budget is not None else 900
            pause = max(0.0, self.minimum_request_interval_seconds
                        - (time.monotonic() - self._previous_request_started))
            if available < self.minimum_request_seconds + pause:
                append_event(self.trace, "request_skipped_for_deadline", available_seconds=available,
                             minimum_request_seconds=self.minimum_request_seconds,
                             rate_wait_seconds=pause, required_seconds=self.minimum_request_seconds + pause)
                raise TimeExceeded({"role": "exit", "content": "Insufficient time for another complete NVIDIA request",
                                    "extra": {"exit_status": "TimeExceeded", "submission": ""}})
            if not pause:
                break
            append_event(self.trace, "request_rate_wait", seconds=pause)
            time.sleep(pause)
        timeout = min(900, available)
        self._previous_request_started = time.monotonic()
        self.request_id += 1
        deadline = time.monotonic() + timeout
        try:
            result = run_json_process([sys.executable, str(Path(__file__).resolve()), "--http-worker"],
                {"payload": payload, "trace": str(self.trace), "stream_trace": str(self.stream_trace),
                 "request_id": self.request_id, "deadline_monotonic": deadline},
                timeout, self.trace.parent)
            if result.get("ok") is not True:
                if result.get("error_type") == "NvidiaFeeError":
                    raise NvidiaFeeError(result["detail"])
                raise RuntimeError("NVIDIA request process failed: " + json.dumps(result, ensure_ascii=False))
            raw = result["response"]
            append_event(self.trace, "response", request_id=self.request_id, attempt=1, payload=raw)
            return raw
        except NvidiaFeeError as exc:
            append_event(self.trace, "billing_error", request_id=self.request_id, detail=str(exc))
            preserve_nvidia_fee_stop(self.stop_path, run_dir=str(self.trace.parent),
                unverified_requests=[self.request_id], reason="The actual NVIDIA response violates its free-service policy")
            raise
        except (subprocess.SubprocessError, RuntimeError, ValueError, KeyError, TypeError, TimeoutError) as exc:
            try:
                dispatched = any(json.loads(line).get("event") == "request" and json.loads(line).get("request_id") == self.request_id
                    for line in self.trace.read_text().splitlines()) if self.trace.exists() else False
            except (json.JSONDecodeError, UnicodeDecodeError):
                dispatched = True
            if not dispatched:
                append_event(self.trace, "local_dispatch_blocked", request_id=self.request_id,
                    error_type=type(exc).__name__, detail=str(exc), physical_request_sent=False)
                raise
            append_event(self.trace, "request_error", request_id=self.request_id,
                error_type=type(exc).__name__, detail=str(exc),
                billing_status="official_non_billed_policy_verified_monetary_receipt_unavailable",
                response_identity_and_usage_verified=False)
            preserve_nvidia_fee_stop(self.stop_path, run_dir=str(self.trace.parent),
                unverified_requests=[self.request_id],
                reason="An attempted NVIDIA request lacks a complete verified response; preserve the attempt and stop dispatch")
            if (isinstance(exc, subprocess.TimeoutExpired) and budget is not None
                    and budget.remaining() <= budget.request_reserve + 0.25):
                raise TimeExceeded({"role": "exit", "content": "Task request window expired during NVIDIA response",
                                    "extra": {"exit_status": "TimeExceeded", "submission": ""}}) from exc
            raise RuntimeError("The NVIDIA response did not complete; preserve it and stop this trial") from exc

    def _calculate_cost(self, response):
        try:
            receipt = verify_nvidia_receipt(response, reported_model_identity(self.contract), self.limits.max_output_tokens)
            if receipt.id in self.generation_ids:
                raise ValueError("The NVIDIA generation identity has already been consumed")
            claim_generation(receipt.id, receipt.model, self.trace, self.request_id)
        except NvidiaFeeError as exc:
            append_event(self.trace, "billing_error", request_id=self.request_id, detail=str(exc))
            preserve_nvidia_fee_stop(self.stop_path, run_dir=str(self.trace.parent),
                unverified_requests=[self.request_id], reason="The NVIDIA actual monetary evidence is invalid")
            raise
        self.generation_ids.add(receipt.id)
        actual_cost = reported_nvidia_cost(response)
        append_event(self.trace, "billing_verified", request_id=self.request_id, provider="nvidia",
            request_model=self.model_id, provider_model=receipt.model, generation_id=receipt.id,
            verification_type=VERIFICATION_TYPE, reported_monetary_cost=actual_cost,
            monetary_receipt_available=actual_cost is not None, usage=receipt.usage.model_dump(),
            usage_records=1, contract_sha256=hashlib.sha256(self.contract_path.read_bytes()).hexdigest())
        return {"cost": 0.0, "cost_provenance": VERIFICATION_TYPE, "reported_monetary_cost": actual_cost}


if __name__ == "__main__":
    if sys.argv[1:] != ["--http-worker"]:
        raise SystemExit("Use the registered NVIDIA request worker")
    try:
        actual = nvidia_http_worker(json.load(sys.stdin))
        outcome = {"ok": True, "response": actual}
    except (requests.RequestException, RuntimeError, ValueError, KeyError, TypeError, TimeoutError) as exc:
        outcome = {"ok": False, "error_type": type(exc).__name__, "detail": str(exc)}
    print(json.dumps(outcome, ensure_ascii=False), flush=True)
