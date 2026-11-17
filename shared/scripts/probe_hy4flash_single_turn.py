import hashlib
import json
import time
from datetime import datetime
from pathlib import Path

from minisweagent.exceptions import FormatError

from course_eval.agent import CodeBuddyModel, RunLimits
from course_eval.codebuddy_free import verify_free_response
from course_eval.controller import Budget


root = Path("work/codebuddy-single-turn-probe-v10")
root.mkdir(exist_ok=True)
model = CodeBuddyModel(root, RunLimits(model_calls=2, wall_seconds=600,
    max_output_tokens=4096, strict_wall=True), "{{output}}")
model.budget = Budget(600)
existing = [json.loads(line) for line in model.trace.read_text().splitlines()] if model.trace.exists() else []
if existing:
    request, = [event for event in existing if event["event"] == "request"]
    assert request["request_id"] == 1
    model.budget.deadline -= time.time() - request["time"]
    model.request_id = 1
    replay_dir = root.with_name(root.name + "-recorded-replay")
    replay_dir.mkdir(exist_ok=False)
    replay_model = CodeBuddyModel(replay_dir, model.limits, "{{output}}")
    replay_model.request_id = 1
headless = model.cli.parents[1] / "dist/codebuddy-headless.js"
assert hashlib.sha256(headless.read_bytes()).hexdigest() == "13a753853deca12c96eba94598a855f76f45f89ae7b790b2d7b2f68932cdb111"
assert hashlib.sha256(Path("course_eval/codebuddy_free.py").read_bytes()).hexdigest() == "a794f3f5c638636fa1ba21600e862e6c1b1242a75401e28dad2538afb2988b28"
messages = [{"role": "system", "content": "Select one structured bash command; do not execute it."},
    {"role": "user", "content": "Return one StructuredOutput action. Its command must be echo followed by every literal integer from 1 through 6000 in ascending order, separated by single spaces. Include all 6000 integers literally in the command field. Do not use ellipses, loops, scripts, generators, substitutions, repetition expressions, or abbreviations."}]
records = []
for name in ("truncated-4096", "outer-recovery-4096"):
    format_error = None
    try:
        if name == "truncated-4096" and existing:
            saved_response, = [event for event in existing if event["event"] == "response"]
            action = replay_model.process_response(saved_response["payload"])
        else:
            action = model.query(messages)
    except FormatError as exc:
        format_error = exc
        action = None
    # query先执行原计费校验；未知或非零异常直接退出，不能进入下一调用。
    events = [json.loads(line) for line in model.trace.read_text().splitlines()]
    current = [event for event in events if event.get("request_id") == model.request_id]
    response, = [event for event in current if event["event"] == "response"]
    proof = verify_free_response(response["payload"])
    usage = [item["providerData"] for item in response["payload"]
             if "rawUsage" in item.get("providerData", {})]
    child, = [event for event in current if event["event"] == "cli_process_started"]
    stamp = datetime.fromtimestamp(child["time"]).astimezone()
    log_name = model.run_dir.name + "__" + hashlib.md5(str(model.run_dir).encode()).hexdigest() + ".log"
    diagnostic = model.inspect_cli_log(Path.home() / ".codebuddy/logs" / stamp.strftime("%Y-%m-%d") / log_name,
                                      child["provider_diagnostics"]["cli_pid"])
    assert diagnostic["model_requests_sent"] == diagnostic["completed_streams"] == 1, diagnostic
    assert diagnostic["truncation_retries"] == diagnostic["structured_output_retries"] == 0, diagnostic
    assert len({item["messageId"] for item in usage}) == 1, usage
    assert all(0 <= item["rawUsage"]["completion_tokens"] <= 4096 for item in usage), usage
    if name == "truncated-4096":
        assert format_error is not None, "The real response did not exercise truncation recovery"
        assert any(item["rawUsage"]["completion_tokens"] == 4096 for item in usage), usage
        messages.extend(format_error.messages)
        messages.append({"role": "user", "content": "The truncation exercise is complete. Replace the long command with exactly one short StructuredOutput action whose command is printf COURSE_SINGLE_TURN_OK."})
    else:
        assert format_error is None, "The shorter recovery action was still invalid"
        assert action["extra"]["actions"][0]["command"] == "printf COURSE_SINGLE_TURN_OK"
    records.append({"case": name, "max_output_tokens": 4096, "action": action,
        "validation": "Actual first receipt replayed after generic output-cap repair"
            if name == "truncated-4096" and existing else "Live request",
        "format_error_messages": list(format_error.messages) if format_error else [],
        "billing": proof, "completion_tokens": [item["rawUsage"]["completion_tokens"] for item in usage],
        "transport_diagnostic": diagnostic})
    (root / "summary.json").write_text(json.dumps({"scope": "Synthetic interface probes; not benchmark scores",
        "actual_cli_requests": len(records), "historical_unknown_cli_requests": 8,
        "max_preparation_cli_requests": 2, "shared_wall_seconds": 600,
        "client_sha256": hashlib.sha256(headless.read_bytes()).hexdigest(), "records": records},
        ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"case": name, "actual_free_usage": proof["usage_records"],
        "completion_tokens": records[-1]["completion_tokens"],
        "native_model_requests": diagnostic["model_requests_sent"],
        "action_received": action is not None}), flush=True)
