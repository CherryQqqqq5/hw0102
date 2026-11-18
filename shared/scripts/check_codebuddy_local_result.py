import copy
import hashlib
import json
import tempfile
from pathlib import Path

from minisweagent.exceptions import FormatError

from course_eval.agent import CodeBuddyModel, RunLimits
from course_eval.codebuddy_free import verify_free_response
from audit_confirmation_sources import audit_local_tool_identity_rejection


root = Path("work/codebuddy-local-result-v14")
trace = Path("work/vmshare/confirmation-hy4flash-free-v14/C-swe-django__django-11999-B0-r3/model.jsonl")
events = [json.loads(line) for line in trace.read_text().splitlines()]
original = next(event["payload"] for event in events if event["event"] == "response" and event["request_id"] == 5)
replay = json.loads((root / "replay.json").read_text())
fixed = replay["fixed"]


def reject(payload):
    try:
        verify_free_response(payload)
    except ValueError:
        return
    raise AssertionError("Invalid actual billing evidence was accepted")


reject(original)
classification = audit_local_tool_identity_rejection(original)
assert classification["actual_native_billing"]["usage_records"] == 2
assert classification["original_whole_response_accepted"] is False
for name in ("no_parent", "wrong_message", "wrong_request"):
    reject(replay[name])
proof = verify_free_response(fixed)
assert proof["usage_records"] == 2 and proof["credit"] == 0
actual = [item for item in original if "rawUsage" in item.get("providerData", {})]
assert verify_free_response(actual)["usage_records"] == 2
for variant in ("missing_usage", "paid_credit", "wrong_native_identity"):
    payload = copy.deepcopy(original)
    usage = next(item for item in payload if "rawUsage" in item.get("providerData", {}))
    if variant == "missing_usage":
        del usage["providerData"]["rawUsage"]
    elif variant == "paid_credit":
        usage["providerData"]["rawUsage"]["credit"] = 1
    else:
        usage["providerData"]["model"] = "different-actual-model"
    reject(payload)
    try:
        audit_local_tool_identity_rejection(payload)
    except ValueError:
        pass
    else:
        raise AssertionError("The local identity diagnosis hid invalid actual billing")
old = Path("work/vmshare/confirmation-hy4flash-free-v13/C-aider-javascript__house-C1-r2/model.jsonl")
old_events = [json.loads(line) for line in old.read_text().splitlines()]
reject(next(event["payload"] for event in old_events if event["event"] == "response" and event["request_id"] == 7))
try:
    audit_local_tool_identity_rejection(next(event["payload"] for event in old_events
                                            if event["event"] == "response" and event["request_id"] == 7))
except ValueError:
    pass
else:
    raise AssertionError("The historical unknown response was reclassified as local-only")
directory = Path(tempfile.mkdtemp(prefix="adapter-replay-", dir=root))
model = CodeBuddyModel(directory, RunLimits(max_output_tokens=4096, timeout_retries=0), "{{output}}")
model.request_id = 5
try:
    model.process_response(fixed)
except FormatError:
    pass
else:
    raise AssertionError("The final 4096-token segment was executed")
recorded = [json.loads(line) for line in (directory / "model.jsonl").read_text().splitlines()]
assert [event["event"] for event in recorded] == ["billing_verified", "local_cli_error", "output_cap_reached"]
validator_sha = hashlib.sha256(Path("course_eval/codebuddy_free.py").read_bytes()).hexdigest()
assert validator_sha == "a794f3f5c638636fa1ba21600e862e6c1b1242a75401e28dad2538afb2988b28"
result = {
    "status": "passed", "billing_checks": 14, "model_calls": 0, "benchmark_actions": 0,
    "scope": "Offline replay only; original response and historical rejection remain unchanged",
    "actual_native_receipts": [{"model": item["providerData"]["model"],
        "messageId": item["providerData"]["messageId"], "credit": item["providerData"]["rawUsage"]["credit"],
        "completion_tokens": item["providerData"]["rawUsage"]["completion_tokens"]} for item in actual],
    "corrected_local_metadata_proof": proof, "billing_validator_sha256": validator_sha,
    "client_sha256": hashlib.sha256(Path("work/codebuddy/node_modules/@tencent-ai/codebuddy-code/dist/codebuddy-headless.js").read_bytes()).hexdigest(),
    "agent_sha256": hashlib.sha256(Path("course_eval/agent.py").read_bytes()).hexdigest(),
    "actual_native_events_unchanged": True, "final_4096_segment_rejected": True,
    "old_true_unknown_still_rejected": True, "live_fixed_client_verified": False,
}
(root / "validation.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
print(json.dumps(result, ensure_ascii=False))
