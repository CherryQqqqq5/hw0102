from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter


FREE_MODEL_ID = "hy4flash-free"


class FreeUsage(BaseModel):
    model_config = ConfigDict(extra="allow", strict=True)
    credit: float = Field(ge=0, le=0)


class FreeProviderIdentity(BaseModel):
    model_config = ConfigDict(extra="allow", strict=True)
    requestModelId: Literal["hy4flash-free"]
    model: Literal["hy4-flash-free"]
    messageId: str = Field(min_length=1)


class FreeProviderResponse(FreeProviderIdentity):
    rawUsage: FreeUsage


class LocalTurnError(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    message: Literal["Max turns (1) exceeded"]
    isNetworkError: Literal[False]
    networkErrorAutoRetry: Literal[False]
    isStreamTimeout: Literal[False]
    isRetryable: Literal[False]


class LocalToolNotFoundError(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    message: str = Field(pattern=r'^Tool "[A-Za-z0-9_.:/-]{1,128}" does not exist in the current tool set\.$')
    isNetworkError: Literal[False]
    networkErrorAutoRetry: Literal[False]
    isStreamTimeout: Literal[False]
    isRetryable: Literal[True]


class LocalCliProvider(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    skipRun: Literal[True]
    error: LocalTurnError | LocalToolNotFoundError
    agent: Literal["cli"]
    conversationRequestId: str = Field(min_length=1)


class LocalCliErrorEvent(BaseModel):
    model_config = ConfigDict(extra="allow", strict=True)
    type: Literal["message"]
    role: Literal["assistant"]
    status: Literal["incomplete"]
    providerData: LocalCliProvider


def verify_free_response(events: list[dict]) -> dict:
    events = TypeAdapter(list[dict]).validate_python(events, strict=True)
    evidence = []
    model_messages = set()
    billed_messages = set()
    local_errors = []
    associated_messages = set()
    latest_model_message = None
    latest_usage = None
    latest_usage_context = None
    for event in events:
        provider = event.get("providerData", {})
        if provider.get("skipRun") is True:
            local = LocalCliErrorEvent.model_validate(event).providerData
            if (latest_usage is None or latest_usage.messageId != latest_model_message
                    or latest_usage.messageId in associated_messages
                    or latest_usage_context != local.conversationRequestId):
                raise ValueError("A local CLI error lacks its own preceding verified model usage")
            associated_messages.add(latest_usage.messageId)
            local_errors.append(local.model_dump() | {"model_message_id": latest_usage.messageId})
            continue
        model_event = event.get("type") in {"reasoning", "function_call", "model-usage"} or (
            event.get("type") == "message" and event.get("role") == "assistant")
        if model_event or "requestModelId" in provider or "model" in provider:
            identity = FreeProviderIdentity.model_validate(provider)
            model_messages.add(identity.messageId)
            latest_model_message = identity.messageId
        if "rawUsage" in provider or event.get("type") == "model-usage":
            record = FreeProviderResponse.model_validate(provider)
            evidence.append(record)
            billed_messages.add(record.messageId)
            latest_usage = record
            latest_usage_context = provider.get("conversationRequestId")
    if not evidence:
        raise ValueError("The provider did not return actual model and credit evidence")
    if model_messages != billed_messages:
        raise ValueError("At least one model reply lacks its own zero-credit evidence")
    return {"request_model": FREE_MODEL_ID, "provider_model": "hy4-flash-free",
            "credit": 0, "usage_records": len(evidence),
            "local_cli_errors": local_errors}
