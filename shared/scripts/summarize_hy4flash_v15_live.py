import hashlib
import json
from pathlib import Path

from audit_confirmation_sources import audit_free_billing


root = Path("work/vmshare/confirmation-hy4flash-free-v15/C-swe-django__django-11999-B0-r3")
events = [json.loads(line) for line in (root / "model.jsonl").read_text().splitlines()]
result = json.loads((root / "result.json").read_text())
report = json.loads(next(root.rglob("report.json")).read_text())["django__django-11999"]
assert result["scoreable"] is True and result["passed"] is report["resolved"]
proof = audit_free_billing(root)
local_results = []
for event in events:
    if event["event"] != "response":
        continue
    payload = event["payload"]
    for index, item in enumerate(payload):
        if item.get("type") != "function_call_result":
            continue
        parent, = [candidate for candidate in payload[:index] if candidate.get("type") == "function_call"
                   and candidate.get("callId") == item.get("callId")]
        for key in ("messageId", "conversationRequestId", "model", "requestModelId"):
            assert item["providerData"][key] == parent["providerData"][key]
        assert item["providerData"]["model"] == "hy4-flash-free"
        local_results.append({"request_id": event["request_id"], "parent_identity_matched": True})
assert len(local_results) == 9
record = {
    "status": "live_client_receipts_and_local_result_identity_verified_original_score_failed",
    "source_run_id": root.name, "batch": "confirmation-hy4flash-free-v15",
    "protocol_commit": "081a796c7bceca10e390fa983c18173289c4fe7a",
    "client_sha256": hashlib.sha256(Path("work/codebuddy/node_modules/@tencent-ai/codebuddy-code/dist/codebuddy-headless.js").read_bytes()).hexdigest(),
    "billing": proof, "local_tool_results_with_matching_actual_parent": len(local_results),
    "original_scoreable": True, "original_passed": result["passed"], "exit_status": result["exit_status"],
    "failed_original_tests": {key: value["failure"] for key, value in report["tests_status"].items()},
    "wall_seconds": result["wall_seconds"], "grader_seconds": result["grader_seconds"],
    "independent_preparation_model_calls": 0, "model_calls_in_this_summarizer": 0,
    "validation_boundary": "Real matched original benchmark attempt with patched client; negative original score retained. Forced empty-stream failure path was not exercised.",
}
Path("work/codebuddy-local-result-v14/live-validation-v15.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n")
print(json.dumps(record, ensure_ascii=False))
