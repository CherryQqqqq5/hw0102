from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


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


def verify_free_response(events: list[dict]) -> dict:
    evidence = []
    model_messages = set()
    billed_messages = set()
    for event in events:
        provider = event.get("providerData", {})
        model_event = event.get("type") in {"reasoning", "function_call"} or (
            event.get("type") == "message" and event.get("role") == "assistant")
        if model_event or "requestModelId" in provider or "model" in provider:
            identity = FreeProviderIdentity.model_validate(provider)
            model_messages.add(identity.messageId)
        if "rawUsage" in provider:
            record = FreeProviderResponse.model_validate(provider)
            evidence.append(record)
            billed_messages.add(record.messageId)
    if not evidence:
        raise ValueError("The provider did not return actual model and credit evidence")
    if model_messages != billed_messages:
        raise ValueError("At least one model reply lacks its own zero-credit evidence")
    return {"request_model": FREE_MODEL_ID, "provider_model": "hy4-flash-free",
            "credit": 0, "usage_records": len(evidence)}
