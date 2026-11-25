import json
import os
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import keyring
import requests
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from minisweagent.exceptions import FormatError, TimeExceeded
from minisweagent.models.openrouter_model import OpenRouterModel

from course_eval.agent import BashArguments, RunLimits, append_event
from course_eval.financial_stop import guard_free_query


class FreeUsage(BaseModel):
    model_config = ConfigDict(extra="allow", strict=True)
    cost: float = Field(ge=0, le=0)
    prompt_tokens: int = Field(ge=0)
    completion_tokens: int = Field(ge=0)
    total_tokens: int = Field(ge=0)


class FreeReceipt(BaseModel):
    model_config = ConfigDict(extra="allow", strict=True)
    id: str = Field(min_length=1)
    model: str = Field(min_length=1)
    usage: FreeUsage


class DailyFreeQuota(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)
    used: int = Field(ge=0)
    limit: int = Field(ge=0)
    remaining: int = Field(ge=0)


class FreeAccountQuota(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)
    is_free_tier: bool
    limit: float | None
    free_model_daily_requests: DailyFreeQuota


def available_free_requests(data: dict, local_requests: int = 0) -> int:
    account = FreeAccountQuota.model_validate(data)
    if account.is_free_tier is not True and account.limit != 0:
        raise ValueError("The live account is not verified free-only")
    if local_requests < 0:
        raise ValueError("The actual local request count cannot be negative")
    return min(account.free_model_daily_requests.remaining,
               max(0, account.free_model_daily_requests.limit - local_requests))


def recorded_free_requests(vmshare: Path, day: str) -> int:
    seen = set()
    for batch in vmshare.glob("performance*"):
        if not batch.is_dir():
            continue
        for trace in batch.rglob("model.jsonl"):
            run = str(trace.parent.relative_to(batch))
            for line in trace.read_text().splitlines():
                row = json.loads(line)
                if row["event"] != "request" or not row.get("payload", {}).get("model", "").endswith(":free"):
                    continue
                if datetime.fromtimestamp(row["time"], timezone.utc).date().isoformat() == day:
                    seen.add((batch.name, run, row["request_id"]))
    return len(seen)


def verify_free_receipt(response: dict, requested_model: str, output_limit: int) -> FreeReceipt:
    receipt = FreeReceipt.model_validate(response)
    if receipt.model not in {requested_model, requested_model.removesuffix(":free")}:
        raise ValueError("The returned model does not match the selected free route")
    if receipt.usage.completion_tokens > output_limit:
        raise ValueError("The provider exceeded the configured output budget")
    return receipt


class OpenRouterFreeModel(OpenRouterModel):
    argument_type = BashArguments
    action_name = "bash"
    # 上游默认重试十次；免费实验在任一调用失败后立即交回停止逻辑。
    abort_exceptions = [Exception, KeyboardInterrupt]

    def __init__(self, run_dir: Path, limits: RunLimits, observation_template: str):
        self.model_id = os.environ["COURSE_MODEL_ID"]
        metadata_path = Path(os.environ["COURSE_FREE_MODEL_METADATA"])
        metadata = json.loads(metadata_path.read_text())
        account = metadata["account"]
        if account["is_free_tier"] is not True and account["limit"] != 0:
            raise RuntimeError("The saved account metadata does not prove free-only eligibility")
        selected = next(row for row in metadata["free_tool_models"] if row["id"] == self.model_id)
        if (not self.model_id.endswith(":free")
                or any(Decimal(value) != 0 for value in selected["pricing"].values())
                or "tools" not in selected["supported_parameters"]):
            raise RuntimeError("The selected route is not a fixed zero-price tool model")
        maximum = selected["top_provider"]["max_completion_tokens"]
        if maximum is None or limits.max_output_tokens > maximum:
            raise ValueError("The output limit exceeds the advertised provider capability")
        super().__init__(model_name=self.model_id, observation_template=observation_template,
            model_kwargs={"max_tokens": limits.max_output_tokens,
                          "provider": {"allow_fallbacks": False}, "plugins": []})
        if type(keyring.get_keyring()).__module__ != "keyring.backends.macOS":
            raise RuntimeError("Expected the authorized macOS keychain backend")
        self._api_key = keyring.get_password("course-eval-free-openrouter", "course-eval-local")
        if not self._api_key:
            raise RuntimeError("The configured OpenRouter credential is missing")
        self.trace = run_dir / "model.jsonl"
        self.limits = limits
        self.request_id = 0
        self.generation_ids = set(json.loads(os.environ.get("COURSE_PRIOR_FREE_GENERATION_IDS", "[]")))
        self.session = requests.Session()
        self.session.max_redirects = 0
        self.vmshare = Path(os.environ["COURSE_FREE_REQUEST_HISTORY"])

    @guard_free_query
    def query(self, messages, **kwargs):
        return super().query(messages, **kwargs)

    def _query(self, messages, **kwargs):
        if getattr(self, "budget", None) is not None:
            self.budget.require_time()
        quota_response = self.session.get("https://openrouter.ai/api/v1/key",
            headers={"Authorization": "Bearer " + self._api_key}, timeout=30, allow_redirects=False)
        quota_response.raise_for_status()
        day = datetime.now(timezone.utc).date().isoformat()
        local_requests = recorded_free_requests(self.vmshare, day)
        remaining = available_free_requests(quota_response.json()["data"], local_requests)
        append_event(self.trace, "free_quota_checked", remaining_requests=remaining,
                     actual_local_daily_requests=local_requests, quota_day_utc=day)
        if not remaining:
            raise TimeExceeded({"role": "exit", "content": "The free daily model quota is exhausted",
                                "extra": {"exit_status": "FreeQuotaExhausted", "submission": ""}})
        if remaining <= 6:
            messages = messages + [{"role": "user", "content":
                f"Account budget: {remaining} free model requests remain today. "
                "Leave a complete runnable candidate now and use the remaining calls to validate it."}]
        from course_eval.financial_stop import free_query_blocked
        if free_query_blocked(Path(os.environ["COURSE_FREE_STOP_PATH"]), self.model_id):
            raise RuntimeError("No HTTP dispatch: a new shared financial stop arrived during quota admission")
        self.request_id += 1
        payload = {"model": self.model_id, "messages": messages,
            "tools": [{"type": "function", "function": {"name": self.action_name,
                "description": "Execute an action in the isolated task environment.",
                "parameters": self.argument_type.model_json_schema()}}],
            "usage": {"include": True}, "stream": False, **self.config.model_kwargs, **kwargs}
        timeout = min(900, self.budget.request_seconds()) if getattr(self, "budget", None) else 900
        append_event(self.trace, "request", request_id=self.request_id, attempt=1, payload=payload)
        try:
            response = self.session.post(self._api_url,
                headers={"Authorization": "Bearer " + self._api_key, "Content-Type": "application/json"},
                json=payload, timeout=timeout, allow_redirects=False)
        except requests.RequestException as exc:
            append_event(self.trace, "request_error", request_id=self.request_id,
                         error_type=type(exc).__name__, billing_status="unknown")
            raise RuntimeError("OpenRouter request failed without a verified receipt; stop model calls") from exc
        if response.status_code != 200:
            append_event(self.trace, "request_error", request_id=self.request_id,
                         http_status=response.status_code, body=response.text, billing_status="unknown",
                         response_ids={name: value for name, value in response.headers.items()
                                       if name.lower() in {"x-request-id", "x-generation-id", "request-id"}})
            raise RuntimeError(f"OpenRouter HTTP {response.status_code}; no further model calls")
        try:
            raw = response.json()
        except requests.JSONDecodeError as exc:
            append_event(self.trace, "request_error", request_id=self.request_id,
                         error_type=type(exc).__name__, body=response.text, billing_status="unknown")
            raise RuntimeError("OpenRouter returned invalid JSON without a verified receipt") from exc
        append_event(self.trace, "response", request_id=self.request_id, attempt=1, payload=raw)
        return raw

    def _calculate_cost(self, response):
        try:
            receipt = verify_free_receipt(response, self.model_id, self.limits.max_output_tokens)
            if receipt.id in self.generation_ids:
                raise ValueError("The actual OpenRouter generation identity has already been consumed")
        except (ValidationError, ValueError) as exc:
            append_event(self.trace, "billing_error", request_id=self.request_id, detail=str(exc))
            raise RuntimeError("OpenRouter actual model or zero-cost receipt is unverified; stop") from exc
        self.generation_ids.add(receipt.id)
        append_event(self.trace, "billing_verified", request_id=self.request_id,
                     request_model=self.model_id, provider_model=receipt.model,
                     generation_id=receipt.id, credit=receipt.usage.cost, usage_records=1)
        return {"cost": receipt.usage.cost}

    def _parse_actions(self, response):
        if (len(response.get("choices", [])) != 1
                or response["choices"][0].get("finish_reason") not in {"tool_calls", "stop"}):
            raise FormatError({"role": "user", "content": "Return complete tool actions within the output budget.",
                               "extra": {"interrupt_type": "FormatError"}})
        if self.argument_type is BashArguments:
            actions = super()._parse_actions(response)
            try:
                for action in actions:
                    BashArguments.model_validate({"command": action["command"]})
                return actions
            except ValidationError as exc:
                raise FormatError({"role": "user", "content": str(exc),
                                   "extra": {"interrupt_type": "FormatError"}}) from exc
        try:
            calls = response["choices"][0]["message"].get("tool_calls") or []
            if len(calls) != 1 or calls[0]["function"]["name"] != self.action_name:
                raise ValueError("Return exactly one registered control action")
            action = self.argument_type.model_validate_json(calls[0]["function"]["arguments"])
            return [action.model_dump() | {"tool_call_id": calls[0]["id"]}]
        except (ValidationError, ValueError, KeyError, TypeError) as exc:
            raise FormatError({"role": "user", "content": str(exc),
                               "extra": {"interrupt_type": "FormatError"}}) from exc

