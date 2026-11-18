import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path


parser = argparse.ArgumentParser()
parser.add_argument("--version", type=int, choices=(15, 16), default=15)
args = parser.parse_args()
version = args.version
published = Path("work/hw0102-publish")
evidence = published / "作业二/evidence"
plan = json.loads(Path(f"work/confirmation-plan-hy4flash-free-v{version}.json").read_text())
shutil.copyfile("course_eval/export_revision.py", published / "shared/course_eval/export_revision.py")
for name, expected in plan["runtime_sha256"].items():
    source = Path("course_eval") / name
    assert hashlib.sha256(source.read_bytes()).hexdigest() == expected
    for base in (Path(f"work/frozen-runtime-v{version}/course_eval"), published / f"frozen-runtime/v{version}/course_eval"):
        target = base / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    shutil.copyfile(source, published / "shared/course_eval" / name)
    older = published / f"frozen-runtime/v{version - 1}/course_eval" / name
    older.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(Path(f"work/frozen-runtime-v{version - 1}/course_eval") / name, older)
for source, target in (
    (f"work/confirmation-plan-hy4flash-free-v{version}.json", f"作业二/configs/confirmation-plan-hy4flash-free-v{version}.json"),
    (f"docs/CONFIRMATION_HY4FLASH_PROTOCOL_V{version}.md", f"作业二/configs/confirmation-protocol-hy4flash-free-v{version}.md"),
    (f"work/hy4flash-v{version - 1}-stopped-summary.json", f"作业二/evidence/hy4flash-v{version - 1}-stopped-summary.json"),
    (f"work/hy4flash-v{version}-resume-validation.json", f"作业二/evidence/hy4flash-v{version}-resume-validation.json"),
    ("work/codebuddy-local-result-v14/diagnostic.json", "作业二/evidence/hy4flash-v14-local-result-diagnostic.json"),
    ("work/codebuddy-local-result-v14/validation.json", "作业二/evidence/hy4flash-v14-local-result-validation.json"),
    ("work/codebuddy-external-recovery-patch.json", "作业二/evidence/hy4flash-v15-client-patch.json"),
):
    shutil.copyfile(source, published / target)
for name in ("audit_confirmation_sources.py", "prepare_hy4flash_resume.py", "summarize_hy4flash_v14_stop.py",
             "diagnose_hy4flash_v14_local_result.py", "check_codebuddy_local_result.py",
             "check_codebuddy_local_result.cjs", "format_codebuddy_local_result.cjs"):
    shutil.copyfile(Path("work") / name, published / "shared/scripts" / name)
before = Path("work/codebuddy-local-result-v14/codebuddy-headless.formatted.js")
active = Path("work/codebuddy/node_modules/@tencent-ai/codebuddy-code/dist/codebuddy-headless.js")
patch = subprocess.run(["diff", "-u", "--label", "formatted-parent", "--label", "patched-client", str(before), str(active)],
                       capture_output=True, check=False)
assert patch.returncode == 1 and b"function_call_result" in patch.stdout
(evidence / "hy4flash-v14-local-result.patch").write_bytes(patch.stdout)
assert hashlib.sha256(active.read_bytes()).hexdigest() == plan["codebuddy_headless_sha256"]
if version == 16:
    for name in ("diagnostic.json", "validation.json", "regression.txt"):
        shutil.copyfile(Path("work/codebuddy-deadline-v16") / name, evidence / ("hy4flash-v16-deadline-" + name))
    for name in ("check_codebuddy_deadline_v16.py", "diagnose_hy4flash_v16_deadline.py", "export_hy4flash_v15_support.py"):
        shutil.copyfile(Path("work") / name, published / "shared/scripts" / name)
    shutil.copyfile("course_eval/check_codebuddy_free.py", published / "shared/course_eval/check_codebuddy_free.py")
print(json.dumps({"protocol_version": version, "frozen_runtime_files": len(plan["runtime_sha256"]),
                  "new_model_calls": 0, "client_sha256": plan["codebuddy_headless_sha256"]}))
