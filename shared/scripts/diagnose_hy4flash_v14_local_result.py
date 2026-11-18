import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from course_eval.agent import CodeBuddyModel
from course_eval.codebuddy_free import verify_free_response


root = Path("work/vmshare/confirmation-hy4flash-free-v14/C-swe-django__django-11999-B0-r3")
events = [json.loads(line) for line in (root / "model.jsonl").read_text().splitlines()]
response = next(event for event in events if event["event"] == "response" and event["request_id"] == 5)
child = next(event for event in events if event["event"] == "cli_process_started" and event["request_id"] == 5)
pid = child["provider_diagnostics"]["cli_pid"]
stamp = datetime.fromtimestamp(child["time"], timezone.utc)
log = Path.home() / ".codebuddy/logs" / stamp.strftime("%Y-%m-%d") / (
    root.name + "__" + hashlib.md5(str(root.resolve()).encode()).hexdigest() + ".log")
diagnostic = CodeBuddyModel.inspect_cli_log(log, pid)
payload = response["payload"]
usage = [item for item in payload if "rawUsage" in item.get("providerData", {})]
proof = verify_free_response(usage)
native = [item for item in payload if item.get("type") in {"reasoning", "function_call", "model-usage"}
          or item.get("type") == "message" and item.get("role") == "assistant"
          and item.get("providerData", {}).get("skipRun") is not True]
native_ids = {item["providerData"]["messageId"] for item in native}
usage_ids = {item["providerData"]["messageId"] for item in usage}
assert native_ids == usage_ids and len(usage_ids) == proof["usage_records"] == 2
local, = [item for item in payload if item.get("type") == "function_call_result"]
parent, = [item for item in payload if item.get("type") == "function_call" and item["callId"] == local["callId"]]
assert all(parent["providerData"][key] == local["providerData"][key]
           for key in ("messageId", "conversationRequestId", "requestModelId"))
assert diagnostic["model_requests_sent"] == diagnostic["completed_streams"] == len(usage_ids)
result = {
    "source_run_id": root.name, "request_id": 5, "cli_pid": pid,
    "failure_category": "local_tool_result_overwrites_actual_model_with_configured_alias",
    "strict_original_response_accepted": False, "original_score": None,
    "provider_diagnostics": diagnostic, "observed_native_message_ids": sorted(native_ids),
    "actual_native_billing": proof, "native_requests_with_unmatched_usage": 0,
    "local_result": {"type": local["type"], "model": local["providerData"]["model"],
        "parent_model": parent["providerData"]["model"], "same_call_id": True,
        "same_message_id": True, "same_conversation_request_id": True},
    "billing_boundary": "Two sent and completed native requests each have their own actual free zero-credit receipt; original whole response stays rejected because the local tool result contains an alias",
    "real_model_requests_in_diagnosis": 0,
}
output = Path("work/codebuddy-local-result-v14/diagnostic.json")
output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
print(json.dumps(result, ensure_ascii=False))
