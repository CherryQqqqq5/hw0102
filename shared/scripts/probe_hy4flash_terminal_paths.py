import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path

from minisweagent.exceptions import FormatError

from course_eval.agent import RunLimits
from course_eval.codebuddy_free import verify_free_response
from course_eval.controller import Budget, ControlModel


root = Path("work/codebuddy-single-turn-probe-v12")
root.mkdir(exist_ok=True)
assert not (root / "model.jsonl").exists()
model = ControlModel(root, RunLimits(model_calls=3, wall_seconds=600,
    max_output_tokens=4096, strict_wall=True), "{{output}}")
model.budget = Budget(600)
headless = model.cli.parents[1] / "dist/codebuddy-headless.js"
assert hashlib.sha256(headless.read_bytes()).hexdigest() == "a52932ce3d059342d46c71ec8234da9e3c5f9b8b903260475d667d31d1d2085b"
records = []


def record(name, action=None, format_error=None):
    events = [json.loads(line) for line in model.trace.read_text().splitlines()]
    current = [event for event in events if event.get("request_id") == model.request_id]
    response, = [event for event in current if event["event"] == "response"]
    billing = verify_free_response(response["payload"])
    child, = [event for event in current if event["event"] == "cli_process_started"]
    usage = [event["providerData"]["rawUsage"] for event in response["payload"]
             if "rawUsage" in event.get("providerData", {})]
    stamp = datetime.fromtimestamp(child["time"]).astimezone()
    log_name = root.name + "__" + hashlib.md5(str(model.run_dir).encode()).hexdigest() + ".log"
    log = Path.home() / ".codebuddy/logs" / stamp.strftime("%Y-%m-%d") / log_name
    pid = child["provider_diagnostics"]["cli_pid"]
    diagnostic = model.inspect_cli_log(log, pid)
    assert diagnostic["model_requests_sent"] == 1, diagnostic
    assert diagnostic["truncation_retries"] == diagnostic["structured_output_retries"] == 0, diagnostic
    assert all(0 <= item["completion_tokens"] <= 4096 for item in usage)
    terminal, = [event for event in response["payload"] if event.get("type") == "result"]
    serialized_turn_errors = sum(f"[pid={pid}]" in line and
        "[CourseTerminalResponse] serialized_max_turns_history" in line for line in log.read_text().splitlines())
    item = {"case": name, "request_id": model.request_id, "validation": "Live request",
        "billing": billing, "completion_tokens": [item["completion_tokens"] for item in usage],
        "terminal_subtype": terminal["subtype"], "action": action,
        "format_error_messages": list(format_error.messages) if format_error else [],
        "max_turns_failure_json_emitted": serialized_turn_errors, "transport_diagnostic": diagnostic}
    records.append(item)
    (root / "summary.json").write_text(json.dumps({"scope": "Bounded interface probes; no benchmark commands executed or benchmark scores",
        "actual_cli_requests": len(records), "max_preparation_cli_requests": 3,
        "historical_unknown_cli_requests": 10, "shared_wall_seconds": 600,
        "client_sha256": hashlib.sha256(headless.read_bytes()).hexdigest(), "records": records},
        ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({key: item[key] for key in ("case", "request_id", "completion_tokens",
        "terminal_subtype", "max_turns_failure_json_emitted")}), flush=True)
    return item


model.request_id += 1
prompt = "Call Read exactly once on receipt-input.txt in the current directory. After reading, report its content. Do not use other tools or read other paths."
command = [str(model.cli), "--print", "--model", "hy4flash-free", "--tools", "Read", "--allowedTools", "Read",
    "--strict-mcp-config", "--permission-mode", "dontAsk", "--no-session-persistence", "--max-turns", "1",
    "--output-format", "json", "--system-prompt", "Inspect only the specified local test file using Read.",
    "--setting-sources", "", "--settings", '{"disableAllHooks":true}', "--mcp-config", '{"mcpServers":{}}', prompt]
process, attempt = model.request_with_timeout_recovery(
    lambda: model.run_cli(command, "", model.process_environment(), model.budget.request_seconds()),
    {"model": "hy4flash-free", "system": "Inspect only the specified local test file using Read.",
     "history": [{"role": "user", "content": prompt}], "schema": None,
     "configured_max_output_tokens": 4096}, subprocess.TimeoutExpired, 600)
try:
    model.process_completed_process(process, attempt)
except FormatError as exc:
    native_error = exc
else:
    raise AssertionError("The native Read probe did not exercise the known turn-limit failure")
item = record("native-read-max-turns", format_error=native_error)
assert item["terminal_subtype"] == "error_max_turns" and item["max_turns_failure_json_emitted"] == 1
messages = [{"role": "system", "content": "Select one structured bash command; do not execute it."},
    {"role": "user", "content": "Return one StructuredOutput action with operation bash. Its command must be echo followed by every literal integer from 1 through 6000 in ascending order separated by single spaces. Include all 6000 integers literally; do not use loops, scripts, generators, ellipses, substitutions or abbreviations."}]
try:
    model.query(messages)
except FormatError as exc:
    truncated = exc
else:
    raise AssertionError("The long-action probe did not exercise output truncation")
item = record("truncated-4096", format_error=truncated)
assert item["completion_tokens"] == [4096]
messages.extend(truncated.messages)
messages.append({"role": "user", "content": "The truncation exercise is complete. Return exactly one short action: operation bash, command printf COURSE_SINGLE_TURN_OK."})
action = model.query(messages)
assert action["extra"]["actions"][0]["command"] == "printf COURSE_SINGLE_TURN_OK"
record("outer-recovery-4096", action=action)
