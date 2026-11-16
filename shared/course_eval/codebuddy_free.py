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


class LocalTurnProvider(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    skipRun: Literal[True]
    error: LocalTurnError
    agent: Literal["cli"]
    conversationRequestId: str = Field(min_length=1)


class LocalTurnEvent(BaseModel):
    model_config = ConfigDict(extra="allow", strict=True)
    type: Literal["message"]
    role: Literal["assistant"]
    status: Literal["incomplete"]
    providerData: LocalTurnProvider


def verify_free_response(events: list[dict]) -> dict:
    events = TypeAdapter(list[dict]).validate_python(events, strict=True)
    evidence = []
    model_messages = set()
    billed_messages = set()
    model_contexts = set()
    local_errors = []
    for event in events:
        provider = event.get("providerData", {})
        if provider.get("skipRun") is True:
            local_errors.append(LocalTurnEvent.model_validate(event).providerData)
            continue
        model_event = event.get("type") in {"reasoning", "function_call", "model-usage"} or (
            event.get("type") == "message" and event.get("role") == "assistant")
        if model_event or "requestModelId" in provider or "model" in provider:
            identity = FreeProviderIdentity.model_validate(provider)
            model_messages.add(identity.messageId)
            context = provider.get("conversationRequestId")
            if isinstance(context, str) and context:
                model_contexts.add(context)
        if "rawUsage" in provider or event.get("type") == "model-usage":
            record = FreeProviderResponse.model_validate(provider)
            evidence.append(record)
            billed_messages.add(record.messageId)
    if not evidence:
        raise ValueError("The provider did not return actual model and credit evidence")
    if model_messages != billed_messages:
        raise ValueError("At least one model reply lacks its own zero-credit evidence")
    if any(error.conversationRequestId not in model_contexts for error in local_errors):
        raise ValueError("A local CLI error does not belong to a verified model request")
    return {"request_model": FREE_MODEL_ID, "provider_model": "hy4-flash-free",
            "credit": 0, "usage_records": len(evidence),
            "local_cli_errors": [error.model_dump() for error in local_errors]}
