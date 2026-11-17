import hashlib
import json
from datetime import datetime
from pathlib import Path

from minisweagent.exceptions import FormatError

from course_eval.agent import CodeBuddyModel, RunLimits
from course_eval.codebuddy_free import verify_free_response
from course_eval.controller import Budget, ControlModel


root = Path("work/codebuddy-single-turn-probe-v11")
root.mkdir(exist_ok=False)
model = ControlModel(root, RunLimits(model_calls=2, wall_seconds=600,
    max_output_tokens=4096, strict_wall=True), "{{output}}")
model.budget = Budget(600)
headless = model.cli.parents[1] / "dist/codebuddy-headless.js"
assert hashlib.sha256(headless.read_bytes()).hexdigest() == "cf1edc0d2fc5cf2cb9ee680f381ba379967a27e408b387e3714ca4b9349a2cb2"
assert hashlib.sha256(Path("course_eval/codebuddy_free.py").read_bytes()).hexdigest() == "a794f3f5c638636fa1ba21600e862e6c1b1242a75401e28dad2538afb2988b28"
source_root = Path("work/vmshare/confirmation-hy4flash-free-v10/C-terminal-feal-linear-cryptanalysis-C0-r2")
source_log, = source_root.rglob("model.jsonl")
source_events = [json.loads(line) for line in source_log.read_text().splitlines()]
source_request, = [event for event in source_events if event["event"] == "request" and event["request_id"] == 2]
assert model.argument_type.model_json_schema() == source_request["schema"]
messages = [{"role": "system", "content": source_request["system"].rsplit("\nYou are selecting", 1)[0]},
    *source_request["history"]]
records = []
for name in ("matched-4096-max-turns", "outer-recovery-4096"):
    format_error = None
    try:
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
    if name == "matched-4096-max-turns":
        sent, = [event for event in current if event["event"] == "request"]
        assert all(sent[key] == source_request[key] for key in ("system", "history", "schema"))
        assert format_error is not None, "The real response did not exercise truncation recovery"
        assert any(item["rawUsage"]["completion_tokens"] == 4096 for item in usage), usage
        terminal, = [event for event in response["payload"] if event.get("type") == "result"]
        assert terminal["subtype"] == "error_max_turns" and terminal["is_error"] is True, terminal["subtype"]
        messages.extend(format_error.messages)
        messages.append({"role": "user", "content": "The interface truncation exercise is complete. Return exactly one short StructuredOutput action: operation is bash and command is printf COURSE_SINGLE_TURN_OK. Do not continue solving the benchmark in this interface probe."})
    else:
        assert format_error is None, "The shorter recovery action was still invalid"
        assert action["extra"]["actions"][0]["command"] == "printf COURSE_SINGLE_TURN_OK"
    records.append({"case": name, "max_output_tokens": 4096, "action": action,
        "validation": "Live request",
        "format_error_messages": list(format_error.messages) if format_error else [],
        "billing": proof, "completion_tokens": [item["rawUsage"]["completion_tokens"] for item in usage],
        "transport_diagnostic": diagnostic})
    (root / "summary.json").write_text(json.dumps({"scope": "Matched original failing request and short interface recovery; no commands executed and no benchmark scores",
        "matched_source_request": {"batch": source_root.parent.name, "run_id": source_root.name, "request_id": 2},
        "actual_cli_requests": len(records), "historical_unknown_cli_requests": 9,
        "max_preparation_cli_requests": 2, "shared_wall_seconds": 600,
        "client_sha256": hashlib.sha256(headless.read_bytes()).hexdigest(), "records": records},
        ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"case": name, "actual_free_usage": proof["usage_records"],
        "completion_tokens": records[-1]["completion_tokens"],
        "native_model_requests": diagnostic["model_requests_sent"],
        "action_received": action is not None}), flush=True)
