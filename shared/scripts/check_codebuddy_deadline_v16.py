import hashlib
import json
import subprocess
import sys
from pathlib import Path

from course_eval.agent import FREE_REQUEST_MIN_SECONDS


root = Path("work/codebuddy-deadline-v16")
diagnostic = json.loads((root / "diagnostic.json").read_text())
source = json.loads(Path("work/confirmation-plan-hy4flash-free-v15.json").read_text())
assert FREE_REQUEST_MIN_SECONDS == 150 and diagnostic["completed_cli_responses"] == 2659
assert diagnostic["latency_max_seconds"] < FREE_REQUEST_MIN_SECONDS
process = subprocess.run([sys.executable, "-m", "unittest", "course_eval.check_codebuddy_free", "-q"],
                         capture_output=True, text=True, check=True)
(root / "regression.txt").write_text(process.stdout + process.stderr)
digest = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
client_sha = digest("work/codebuddy/node_modules/@tencent-ai/codebuddy-code/dist/codebuddy-headless.js")
validator_sha = digest("course_eval/codebuddy_free.py")
assert client_sha == source["codebuddy_headless_sha256"]
assert validator_sha == source["runtime_sha256"]["codebuddy_free.py"]
changed = [name for name, expected in source["runtime_sha256"].items() if digest(Path("course_eval") / name) != expected]
assert changed == ["agent.py"]
result = {
    "status": "passed", "model_calls": 0, "boundary_test_backend": "/usr/bin/false (real local non-network process)",
    "request_window_min_seconds": FREE_REQUEST_MIN_SECONDS, "previous_request_window_min_seconds": 60,
    "real_failed_73_second_window_rejected_before_request": True,
    "sufficient_151_second_window_admitted_to_local_process": True,
    "baseline_and_control_model_tested": True, "existing_missing_paid_and_truncation_checks_passed": True,
    "regression_command": "python -m unittest course_eval.check_codebuddy_free -q", "regression_exit_code": process.returncode,
    "regression_log": "regression.txt", "changed_frozen_runtime_files": changed,
    "agent_sha256": digest("course_eval/agent.py"), "client_sha256": client_sha,
    "billing_validator_sha256": validator_sha, "billing_rules_unchanged": True,
    "old_unknown_cli_requests_preserved": 13, "upstream_queue_or_network_cause_resolved": False,
    "live_matched_original_recovery_verified": False,
    "scope": "Offline budget-boundary and actual recorded response regression; no new provider response, no original grade",
}
(root / "validation.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
print(json.dumps(result, ensure_ascii=False))
