import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path

from course_eval.agent import CodeBuddyModel, RunLimits
from course_eval.codebuddy_free import verify_free_response


parser = argparse.ArgumentParser()
parser.add_argument("--model-log", type=Path, default=Path("work/vmshare/confirmation-hy4flash-free-v12/C-swe-pydata__xarray-7393-C0-r2/model.jsonl"))
parser.add_argument("--out", type=Path, default=Path("work/codebuddy-stdout-replay-v12"))
args = parser.parse_args()
root = args.out
root.mkdir(parents=True, exist_ok=True)
source = args.model_log
events = [json.loads(line) for line in source.read_text().splitlines()]
payload, = [event["payload"] for event in events
            if event["event"] == "response" and event["request_id"] == 20]
receipt = verify_free_response(payload)
# 只增加标准JSON排版空白；保留已返回的真实内容、模型身份和计费字段。
raw = json.dumps(payload, ensure_ascii=False, indent=4096) + "\n"
fixture = root / "recorded-response.pretty.json"
fixture.write_text(raw)
assert len(raw.encode()) > 1_048_576
command = ["node", "-e",
    "process.stdout.write(require('node:fs').readFileSync(process.argv[1]));process.exit(0)",
    str(fixture.resolve())]
old = subprocess.run(command, input="", capture_output=True, text=True, check=True)
assert len(old.stdout.encode()) < len(raw.encode())
model = CodeBuddyModel(root, RunLimits(), "{{output}}")
model.request_id = 1
new = model.run_cli(command, "", dict(os.environ), 10)
assert new.returncode == 0 and new.stderr == ""
assert new.stdout == raw
assert json.loads(new.stdout) == payload
assert verify_free_response(json.loads(new.stdout)) == receipt
result = {
    "scope": "Controlled local byte-transport replay of a returned provider response; no model call",
    "source_request_id": 20,
    "source_batch": "confirmation-hy4flash-free-v12",
    "source_run_id": source.parent.name,
    "fixture_bytes": len(raw.encode()), "fixture_sha256": hashlib.sha256(raw.encode()).hexdigest(),
    "old_pipe_bytes": len(old.stdout.encode()), "regular_file_bytes": len(new.stdout.encode()),
    "old_zero_exit_lost_output": True, "regular_file_exact_bytes": True,
    "parsed_values_and_actual_billing_unchanged": True,
    "real_model_requests": 0,
    "live_cli_validation_after_fix": False,
}
(root / "summary.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
print(json.dumps(result, ensure_ascii=False))
