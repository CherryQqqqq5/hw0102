import copy
import json
from pathlib import Path

from course_eval.agent import append_event
from course_eval.nvidia_free import NvidiaFreeModel, audit_nvidia_events


class NvidiaDshProvider(NvidiaFreeModel):
    def __init__(self, directory, limits, stop_path, budget):
        super().__init__(directory, limits, "{{output.output}}")
        if self.stop_path.resolve() != Path(stop_path).resolve():
            raise ValueError("The DSH free-service stop file differs from the shared boundary")
        self.budget = budget

    def __call__(self, body, index):
        if index != self.request_id + 1:
            raise ValueError("The SDK request sequence differs from actual model calls")
        if body.get("model") != self.model_id or body.get("reasoning_effort") not in {None, self.reasoning_effort}:
            raise ValueError("The SDK selected a different model or reasoning effort")
        cap = body.get("max_tokens")
        if type(cap) is not int or not 0 < cap <= self.limits.max_output_tokens:
            raise ValueError("The SDK output budget exceeds the fixed comparison allowance")
        tools = copy.deepcopy(body.get("tools", []))
        schemas = {row["function"]["name"]: row["function"]["parameters"] for row in tools}
        if len(schemas) != len(tools) or any(row["type"] != "function" for row in tools):
            raise ValueError("The actual SDK function catalog is invalid or ambiguous")
        payload = {"model": self.model_id, "messages": self._prepare_messages_for_api(body["messages"]),
            "max_tokens": cap, "reasoning_effort": self.reasoning_effort,
            "temperature": 1, "top_p": 0.95, "stream": True, "stream_options": {"include_usage": True}}
        if tools:
            payload.update(tools=tools, tool_choice=body.get("tool_choice", "auto"), parallel_tool_calls=False)
        raw = self.request_payload(payload)
        self._calculate_cost(raw)
        if raw["usage"]["completion_tokens"] > cap:
            raise ValueError("The actual response exceeded this request's smaller native SDK output cap")
        choice, = raw["choices"]
        if choice["finish_reason"] not in {"stop", "tool_calls", "length"}:
            raise ValueError("The SDK received an unsupported model termination reason")
        # 官方SDK在执行前验证原生工具参数，并将未知工具或非法参数反馈给模型。
        # length由SDK映射为max-tokens，在执行任何工具前结束该轮。
        append_event(self.trace.parent / "dsh-responses.jsonl", "verified_provider_response",
                     response=raw, transport="native_sdk_messages_and_functions_without_flat_action_conversion")
        return {"status": 200, "body": raw}

    def preserve_billing_stop(self):
        if not self.trace.exists():
            return
        rows = [json.loads(line) for line in self.trace.read_text().splitlines()]
        audit = audit_nvidia_events(rows, self.contract_path, self.model_id, self.limits.max_output_tokens)
        append_event(self.trace.parent / "dsh-responses.jsonl", "final_provider_audit", **audit)
