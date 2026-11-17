import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path
from zipfile import ZipFile


parser = argparse.ArgumentParser()
parser.add_argument("--recovery", type=int, choices=(1, 2, 3, 4, 5), default=1)
args = parser.parse_args()
if args.recovery == 4:
    stem = "hy4flash-v9-repair"
    archive_path = Path("outputs/作业一二_hy4flash_v9截断修复停止证据_20261117.zip")
    published = Path("work/hw0102-publish")
    destination = Path("work/verified-hy4flash-v9-repair-package")
    destination.mkdir(exist_ok=False)
    summary_name = f"作业二/evidence/{stem}-stopped-summary.json"
    summary = json.loads((published / summary_name).read_text())
    historical_name = "作业一二_hy4flash_v8首轮停止证据_20261117.zip"
    with ZipFile(archive_path) as archive:
        assert archive.testzip() is None
        names = archive.namelist()
        assert all(not name.startswith(("/", "../", ".git/", "work/"))
                   and ".." not in Path(name).parts and "/.env" not in name for name in names)
        for relative in ("README.md", summary_name, f"作业二/evidence/{stem}-stop-20261117.md"):
            assert archive.read(relative) == (published / relative).read_bytes()
        for assignment in ("一", "二"):
            relative = f"作业{assignment}/231880296_邱昱宁_作业{assignment}.pdf"
            assert archive.read(relative) == (Path("outputs") / Path(relative).name).read_bytes()
        assert archive.read("history/" + historical_name) == (Path("outputs") / historical_name).read_bytes()
        archive.extractall(destination)
    frozen = destination / "history/v8"
    with ZipFile(destination / "history" / historical_name) as archive:
        assert archive.testzip() is None
        assert all(not Path(name).is_absolute() and ".." not in Path(name).parts for name in archive.namelist())
        archive.extractall(frozen)
    shared = (frozen / "shared").resolve()
    command = [str(Path("work/.venv/bin/python").absolute()), "scripts/verify_free_stopped_run.py",
        "--runs", "../作业二/evidence/confirmation-hy4flash-free-v8",
        "--previous-runs", "../作业二/evidence/confirmation-hy4flash-free-v8-previous",
        "--summary", "../作业二/evidence/hy4flash-v8-stopped-summary.json",
        "--plan", "../作业二/configs/confirmation-plan-hy4flash-free-v8.json"]
    process = subprocess.run(command, cwd=shared, env=os.environ | {"PYTHONPATH": str(shared)},
                             capture_output=True, text=True, check=True)
    verification = json.loads(process.stdout)
    assert verification["scored"] == 90 and verification["passed"] == 82
    assert verification["new_missing_receipts"] + verification["historical_missing_receipts"] == 7
    probe_log = destination / "作业二/evidence/codebuddy-single-turn-probe-v9/truncated-64/model.jsonl"
    events = [json.loads(line) for line in probe_log.read_text().splitlines()]
    assert sum(event["event"] == "request" for event in events) == 1
    assert not any(event["event"] in {"response", "billing_verified"} for event in events)
    assert summary["probe"]["actual_model_credit"] is None and summary["total_unknown_cli_requests"] == 8
    assert summary["patched_client_live_validation"] is False and summary["formal_v9_launched"] is False
    assert summary["new_model_requests_after_stop"] == summary["new_formal_positions"] == 0
    fee_validator = destination / "shared/course_eval/codebuddy_free.py"
    assert hashlib.sha256(fee_validator.read_bytes()).hexdigest() == summary["patch"]["billing_validator_sha256"]
    result = {"archive": str(archive_path), "bytes": archive_path.stat().st_size, "members": len(names),
        "integrity": "passed", "historical_reports_match": True, "v8_archive_preserved_byte_for_byte": True,
        "frozen_v8_recomputation": verification, "new_probe_missing_receipts_preserved": 1,
        "total_unknown_cli_requests": 8, "patched_client_live_validation": False,
        "scope": "Repair preparation stop; no new formal score and no completed 270-position matrix"}
    Path(f"work/{stem}-package-verification.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result, ensure_ascii=False))
    raise SystemExit(0)
label = {1: "恢复补充证据", 2: "接电续跑停止证据", 3: "_v8首轮停止证据", 5: "_v10原题验证停止证据"}[args.recovery]
stem = {3: "hy4flash-v8", 5: "hy4flash-v10"}.get(args.recovery, f"hy4flash-v7-recovery{args.recovery}")
batch = {3: "confirmation-hy4flash-free-v8", 5: "confirmation-hy4flash-free-v10"}.get(args.recovery, "confirmation-hy4flash-free-v7")
archive_path = Path(f"outputs/作业一二_hy4flash{label}_20261117.zip")
published = Path("work/hw0102-publish")
summary = json.loads((published / f"作业二/evidence/{stem}-stopped-summary.json").read_text())
destination = Path(f"work/verified-{stem}-package")
destination.mkdir(exist_ok=False)
with ZipFile(archive_path) as archive:
    assert archive.testzip() is None
    names = archive.namelist()
    groups = [(batch, summary["started_positions"]),
              (batch + "-previous", {3: 9, 5: 10}.get(args.recovery, 6))]
    if args.recovery not in (3, 5):
        groups.append((batch + "-attempts", args.recovery))
    for group, expected in groups:
        prefix = f"作业二/evidence/{group}/"
        assert sum(name.startswith(prefix) and name.endswith("/trial.json")
                   and len(Path(name).parts) == 5 for name in names) == expected
    report_name = f"作业二/evidence/{stem}-{'stop-' if args.recovery == 5 else ''}20261117.md"
    for relative in ("README.md", f"作业二/evidence/{stem}-stopped-summary.json", report_name):
        assert archive.read(relative) == (published / relative).read_bytes()
    for assignment in ("一", "二"):
        name = f"作业{assignment}/231880296_邱昱宁_作业{assignment}.pdf"
        assert archive.read(name) == (Path("outputs") / Path(name).name).read_bytes()
    assert all(not name.startswith(("/", "../", ".git/", "work/")) and "/.env" not in name for name in names)
    if args.recovery == 5:
        historical_name = "作业一二_hy4flash_v9截断修复停止证据_20261117.zip"
        assert archive.read("history/" + historical_name) == (Path("outputs") / historical_name).read_bytes()
    archive.extractall(destination)
shared = (destination / "shared").resolve()
plan_version = {3: 8, 5: 10}.get(args.recovery, 7)
command = [
    str(Path("work/.venv/bin/python").absolute()), "scripts/verify_free_stopped_run.py",
    "--runs", f"../作业二/evidence/{batch}",
    "--previous-runs", f"../作业二/evidence/{batch}-previous",
    "--summary", f"../作业二/evidence/{stem}-stopped-summary.json",
    "--plan", f"../作业二/configs/confirmation-plan-hy4flash-free-v{plan_version}.json"]
if args.recovery not in (3, 5):
    command.extend(["--mechanical-runs", f"../作业二/evidence/{batch}-attempts"])
process = subprocess.run(command,
    cwd=shared, env=os.environ | {"PYTHONPATH": str(shared)}, capture_output=True, text=True, check=True)
verification = json.loads(process.stdout)
assert verification["scored"] == summary["valid_original_scores"] and verification["new_missing_receipts"] == 1
assert verification["historical_missing_receipts"] + verification["recovery_archive_missing_receipts"] == summary["all_free_formal_attempt_usage"]["usage_unreturned_requests"] - 1
result = {"archive": str(archive_path), "bytes": archive_path.stat().st_size, "members": len(names),
          "integrity": "passed", "historical_reports_match": True,
          "extracted_package_verification": verification,
          "scope": "Free evaluation recovery supplement; incomplete 270-position matrix"}
if args.recovery == 5:
    from course_eval.codebuddy_free import verify_free_response

    probe = destination / "作业二/evidence/hy4flash-recovery-probe-v10/model.jsonl"
    events = [json.loads(line) for line in probe.read_text().splitlines()]
    responses = [event for event in events if event["event"] == "response"]
    assert sum(event["event"] == "request" for event in events) == len(responses) == 2
    proofs = [verify_free_response(event["payload"]) for event in responses]
    assert all(proof["credit"] == 0 for proof in proofs)
    cap_outputs = [item["providerData"]["rawUsage"]["completion_tokens"]
        for event in responses for item in event["payload"] if "rawUsage" in item.get("providerData", {})]
    assert cap_outputs == [4096, 151]
    assert summary["old_unknown_cli_requests"] == 8 and summary["total_unknown_cli_requests"] == 9
    assert summary["new_model_requests_after_stop"] == summary["new_scored_positions"] == 0
    assert verification["scored"] == 90 and verification["passed"] == 82
    assert verification["historical_missing_receipts"] == 7
    result.update(preparation_returned_zero_credit_responses=2, preparation_outputs=cap_outputs,
        historical_unknown_cli_requests=8, total_unknown_cli_requests=9,
        historical_v9_archive_preserved_byte_for_byte=True, new_original_scores=0)
Path(f"work/{stem}-package-verification.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
print(json.dumps(result, ensure_ascii=False))
