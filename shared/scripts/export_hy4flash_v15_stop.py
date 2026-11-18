import json
import shutil
import subprocess
import sys
from pathlib import Path

from course_eval.export_revision import sanitize_model


published = Path("work/hw0102-publish")
evidence = published / "作业二/evidence"
exports = [(Path("work/vmshare") / name, evidence / name) for name in (
    "confirmation-hy4flash-free-v15", "confirmation-hy4flash-free-v15-previous")]
preparation = evidence / "preparation-free"
exports.append((Path("work/vmshare/hy4flash-interface-v1"), preparation / "hy4flash-interface-v1"))
for name in ("codebuddy-single-turn-probe-v9", "codebuddy-single-turn-probe-v10",
             "codebuddy-single-turn-probe-v11", "codebuddy-single-turn-probe-v12",
             "codebuddy-stdout-probe-v13", "codebuddy-empty-stream-probe-v14"):
    exports.append((Path("work") / name, preparation / name))
for source, destination in exports:
    subprocess.run([sys.executable, "-m", "course_eval.export_revision", "--runs", str(source),
                    "--out", str(destination)], check=True)
for name in ("hy4flash-free-smoke-exactroute.stdout.json", "hy4flash-output-cap-4096-v1/events.json"):
    payload = json.loads((Path("work/codebuddy-quota-probe") / name).read_text())
    sanitized = json.loads(sanitize_model(json.dumps({"event": "response", "payload": payload})))
    target = preparation / "codebuddy-quota-probe" / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(sanitized["payload"], ensure_ascii=False, indent=2) + "\n")
for source, target in (
    ("work/hy4flash-v15-stopped-summary.json", "hy4flash-v15-stopped-summary.json"),
    ("work/hy4flash-v15-scored-trials.json", "hy4flash-v15-scored-trials.json"),
    ("work/codebuddy-first-response-v15/diagnostic.json", "hy4flash-v15-first-response-diagnostic.json"),
    ("work/codebuddy-local-result-v14/live-validation-v15.json", "hy4flash-v15-local-result-live-validation.json"),
    ("work/codebuddy-external-recovery-patch.json", "hy4flash-v15-client-patch.json"),
    ("docs/FREE_CHANNEL_SETUP.md", "free-channel-setup-20261118.md"),
):
    shutil.copyfile(source, evidence / target)
report = Path("docs/HY4FLASH_V15_STOP_20261118.md").read_text()
(evidence / "hy4flash-v15-stop-20261118.md").write_text(report.replace("../work/vmshare/", ""))
for name in ("summarize_hy4flash_v15_stop.py", "summarize_hy4flash_v15_live.py", "export_hy4flash_v15_stop.py"):
    shutil.copyfile(Path("work") / name, published / "shared/scripts" / name)
print(json.dumps({"sanitized_groups": len(exports), "initial_preparation_payloads": 2,
                  "published_report": "作业二/evidence/hy4flash-v15-stop-20261118.md", "new_model_requests": 0}))
