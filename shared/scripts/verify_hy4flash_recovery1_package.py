import argparse
import hashlib
import io
import json
import os
import subprocess
from pathlib import Path
from zipfile import ZipFile


parser = argparse.ArgumentParser()
parser.add_argument("--recovery", type=int, choices=(1, 2, 3, 4, 5, 6, 7, 8, 9, 10), default=1)
args = parser.parse_args()
if args.recovery == 10:
    archive_path = Path("outputs/作业一二_hy4flash_v16_完整270条评分与报告_20261118.zip")
    published = Path("work/hw0102-publish")
    destination = Path("work/verified-hy4flash-v16-package")
    destination.mkdir(exist_ok=False)
    historical_name = "作业一二_hy4flash_v15_260条评分与停止证据_20261118.zip"
    batch = "confirmation-hy4flash-free-v16"
    with ZipFile(archive_path) as archive:
        assert archive.testzip() is None
        names = archive.namelist()
        assert len(names) == len(set(names))
        assert all(not name.startswith(("/", "../", ".git/", "work/"))
                   and ".." not in Path(name).parts and "/.env" not in name for name in names)
        for assignment in ("一", "二"):
            relative = f"作业{assignment}/231880296_邱昱宁_作业{assignment}.pdf"
            assert archive.read(relative) == (published / relative).read_bytes()
            assert archive.read(relative) == (Path("outputs") / Path(relative).name).read_bytes()
        history = archive.read("history/" + historical_name)
        assert history == (Path("outputs") / historical_name).read_bytes()
        for group, count in ((batch, 270), (batch + "-previous", 15)):
            prefix = "作业二/evidence/" + group + "/"
            assert sum(name.startswith(prefix) and name.endswith("/trial.json")
                       and len(Path(name).parts) == 5 for name in names) == count
        archive.extractall(destination)
    plan = json.loads((destination / f"作业二/configs/confirmation-plan-hy4flash-free-v16.json").read_text())
    compared = 0
    with ZipFile(io.BytesIO(history)) as old:
        def compare_source(directory, prefix):
            actual = {path.relative_to(directory).as_posix(): path.read_bytes()
                      for path in directory.rglob("*") if path.is_file()}
            expected = {name.removeprefix(prefix): old.read(name)
                        for name in old.namelist() if name.startswith(prefix) and not name.endswith("/")}
            assert actual == expected, str(directory)
            return len(actual)

        for slot in plan["slots"]:
            if slot.get("source_batch"):
                assert slot["source_batch"] == "confirmation-hy4flash-free-v15"
                compared += compare_source(destination / "作业二/evidence" / batch / slot["run_id"],
                    f"作业二/evidence/{slot['source_batch']}/{slot['run_id']}/")
        old_names = set(old.namelist())
        for item in plan["preserved_previous_attempts"]:
            prefix = f"作业二/evidence/confirmation-hy4flash-free-v15-previous/{item['preserved_run_id']}/"
            if prefix + "trial.json" not in old_names:
                assert item["source_batch"] == "confirmation-hy4flash-free-v15"
                prefix = f"作业二/evidence/{item['source_batch']}/{item['source_run_id']}/"
            compared += compare_source(destination / "作业二/evidence" / (batch + "-previous") / item["preserved_run_id"], prefix)
    assert compared == 3622
    shared = (destination / "shared").resolve()
    command = [str(Path("work/.venv/bin/python").absolute()), "scripts/verify_free_stopped_run.py",
        "--runs", "../作业二/evidence/" + batch,
        "--previous-runs", "../作业二/evidence/" + batch + "-previous",
        "--summary", "../作业二/evidence/" + batch + "-summary/summary.json",
        "--plan", "../作业二/configs/confirmation-plan-hy4flash-free-v16.json",
        "--runtime", "../frozen-runtime/v16/course_eval",
        "--trials", "../作业二/evidence/" + batch + "-summary/trials.json",
        "--source-audit", "../作业二/evidence/" + batch + "-source-audit.json",
        "--preparation-root", "../作业二/evidence/preparation-free"]
    process = subprocess.run(command, cwd=shared,
        env=os.environ | {"PYTHONPATH": str(shared) + os.pathsep + str(shared / "scripts")},
        capture_output=True, text=True, check=True)
    verification = json.loads(process.stdout)
    assert verification["scored"] == 270 and verification["historical_unknown_cli_requests"] == 13
    assert verification["historical_known_zero_local_metadata_rejections"] == 1
    assert hashlib.sha256((shared / "course_eval/codebuddy_free.py").read_bytes()).hexdigest() == "a794f3f5c638636fa1ba21600e862e6c1b1242a75401e28dad2538afb2988b28"
    result = {"archive": str(archive_path), "bytes": archive_path.stat().st_size, "members": len(names),
        "integrity": "passed", "current_report_files_match": True, "v15_archive_preserved_byte_for_byte": True,
        "historical_reports_preserved_inside_v15_archive": True, "source_files_compared_byte_for_byte": compared,
        "original_scores_verified": 270, "genuine_failures_preserved": verification["failed"],
        "historical_unscored_attempts_preserved": 15, "total_unknown_cli_requests": 13,
        "known_zero_local_metadata_rejection_preserved": 1, "billing_validator_unchanged": True,
        "extracted_package_verification": verification, "new_model_or_grader_calls": 0,
        "scope": "Complete 270-position free-model scores; historical unknown fees and runtime-policy differences preserved"}
    Path("work/hy4flash-v16-package-verification.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result, ensure_ascii=False))
    raise SystemExit(0)
if args.recovery == 9:
    archive_path = Path("outputs/作业一二_hy4flash_v15_260条评分与停止证据_20261118.zip")
    published = Path("work/hw0102-publish")
    destination = Path("work/verified-hy4flash-v15-package")
    destination.mkdir(exist_ok=False)
    summary_name = "作业二/evidence/hy4flash-v15-stopped-summary.json"
    historical_name = "作业一二_hy4flash_v13评分与空流修复停止证据_20261118.zip"
    with ZipFile(archive_path) as archive:
        assert archive.testzip() is None
        names = archive.namelist()
        assert len(names) == len(set(names))
        assert all(not name.startswith(("/", "../", ".git/", "work/"))
                   and ".." not in Path(name).parts and "/.env" not in name for name in names)
        for relative in ("README.md", summary_name, "作业二/evidence/hy4flash-v15-stop-20261118.md"):
            assert archive.read(relative) == (published / relative).read_bytes()
        for assignment in ("一", "二"):
            relative = f"作业{assignment}/231880296_邱昱宁_作业{assignment}.pdf"
            assert archive.read(relative) == (Path("outputs") / Path(relative).name).read_bytes()
        assert archive.read("history/" + historical_name) == (Path("outputs") / historical_name).read_bytes()
        for group, expected in (("confirmation-hy4flash-free-v15", 261),
                                ("confirmation-hy4flash-free-v15-previous", 14)):
            prefix = "作业二/evidence/" + group + "/"
            assert sum(name.startswith(prefix) and name.endswith("/trial.json")
                       and len(Path(name).parts) == 5 for name in names) == expected
        archive.extractall(destination)
    summary = json.loads((destination / summary_name).read_text())
    shared = (destination / "shared").resolve()
    interpreter = str(Path("work/.venv/bin/python").absolute())
    child_env = os.environ | {"PYTHONPATH": str(shared) + os.pathsep + str(shared / "scripts")}
    command = [interpreter, "scripts/verify_free_stopped_run.py",
        "--runs", "../作业二/evidence/confirmation-hy4flash-free-v15",
        "--previous-runs", "../作业二/evidence/confirmation-hy4flash-free-v15-previous",
        "--summary", "../" + summary_name,
        "--plan", "../作业二/configs/confirmation-plan-hy4flash-free-v15.json",
        "--runtime", "../frozen-runtime/v15/course_eval",
        "--trials", "../作业二/evidence/hy4flash-v15-scored-trials.json"]
    process = subprocess.run(command, cwd=shared, env=child_env, capture_output=True, text=True, check=True)
    verification = json.loads(process.stdout)
    assert verification["scored"] == 260 and verification["passed"] == 202
    assert verification["new_missing_receipts"] == 1 and verification["historical_missing_receipts"] == 9
    assert verification["historical_returned_unknown_responses"] == 1
    assert verification["historical_known_zero_local_metadata_rejections"] == 1
    preparation_code = (
        "import json; from pathlib import Path; from audit_confirmation_sources import audit_free_recovery_preparation; "
        "base=Path('../作业二/evidence/preparation-free'); "
        "print(json.dumps(audit_free_recovery_preparation(base/'codebuddy-quota-probe',base/'hy4flash-interface-v1')))"
    )
    preparation_process = subprocess.run([interpreter, "-c", preparation_code], cwd=shared, env=child_env,
                                        capture_output=True, text=True, check=True)
    preparation = json.loads(preparation_process.stdout)
    expected_preparation = summary["all_free_preparation"]
    for key in ("usage", "actual_model_usage_records", "missing_responses", "reported_credit_for_returned_responses", "initial_preparation"):
        assert preparation[key] == expected_preparation[key]
    for actual, expected in zip(preparation["recovery_preparation"], expected_preparation["recovery_preparation"], strict=True):
        assert {key: value for key, value in actual.items() if key != "source"} == {key: value for key, value in expected.items() if key != "source"}
    fee = (destination / "shared/course_eval/codebuddy_free.py").read_bytes()
    assert hashlib.sha256(fee).hexdigest() == "a794f3f5c638636fa1ba21600e862e6c1b1242a75401e28dad2538afb2988b28"
    assert summary["total_unknown_cli_requests"] == 13 and preparation["missing_responses"] == 2
    assert summary["new_model_requests_after_stop"] == 0 and summary["complete_report_generated"] is False
    diagnostic = summary["failure"]
    assert diagnostic["request_id"] == 24 and diagnostic["actual_provider_credit"] is None
    assert diagnostic["provider_diagnostics"]["model_requests_sent"] == 1
    assert diagnostic["provider_diagnostics"]["first_raw_chunks"] == 0
    result = {"archive": str(archive_path), "bytes": archive_path.stat().st_size, "members": len(names),
        "integrity": "passed", "historical_reports_match": True, "v13_archive_preserved_byte_for_byte": True,
        "frozen_v15_recomputation": verification, "original_scores_verified": 260,
        "genuine_failures_preserved": 58, "main_unscored_attempts_preserved": 1,
        "historical_unscored_attempts_preserved": 14, "remaining_scores": 10,
        "formal_missing_receipts_preserved": 10, "formal_returned_unknown_preserved": 1,
        "historical_preparation_unknown_receipts_preserved": 2, "total_unknown_cli_requests": 13,
        "known_zero_local_metadata_rejection_preserved": 1, "preparation_requests_verified": 14,
        "preparation_returned_responses_verified": 12, "billing_validator_unchanged": True,
        "scored_trial_analysis_recomputed": True, "new_model_requests": 0,
        "scope": "Preserved 260-position partial comparison; frozen 270-position primary comparison incomplete"}
    Path("work/hy4flash-v15-package-verification.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result, ensure_ascii=False))
    raise SystemExit(0)
if args.recovery == 8:
    from audit_confirmation_sources import audit_free_billing

    archive_path = Path("outputs/作业一二_hy4flash_v13评分与空流修复停止证据_20261118.zip")
    published = Path("work/hw0102-publish")
    destination = Path("work/verified-hy4flash-v13-package")
    destination.mkdir(exist_ok=False)
    summary_name = "作业二/evidence/hy4flash-v13-stopped-summary.json"
    historical_name = "作业一二_hy4flash_v12评分与输出修复停止证据_20261117.zip"
    with ZipFile(archive_path) as archive:
        assert archive.testzip() is None
        names = archive.namelist()
        assert len(names) == len(set(names))
        assert all(not name.startswith(("/", "../", ".git/", "work/"))
                   and ".." not in Path(name).parts and "/.env" not in name for name in names)
        for relative in ("README.md", summary_name, "作业二/evidence/hy4flash-v13-stop-20261118.md"):
            assert archive.read(relative) == (published / relative).read_bytes()
        for assignment in ("一", "二"):
            relative = f"作业{assignment}/231880296_邱昱宁_作业{assignment}.pdf"
            assert archive.read(relative) == (Path("outputs") / Path(relative).name).read_bytes()
        assert archive.read("history/" + historical_name) == (Path("outputs") / historical_name).read_bytes()
        for group, expected in (("confirmation-hy4flash-free-v13", 139),
                                ("confirmation-hy4flash-free-v13-previous", 12)):
            prefix = "作业二/evidence/" + group + "/"
            assert sum(name.startswith(prefix) and name.endswith("/trial.json")
                       and len(Path(name).parts) == 5 for name in names) == expected
        archive.extractall(destination)
    summary = json.loads((destination / summary_name).read_text())
    shared = (destination / "shared").resolve()
    command = [str(Path("work/.venv/bin/python").absolute()), "scripts/verify_free_stopped_run.py",
        "--runs", "../作业二/evidence/confirmation-hy4flash-free-v13",
        "--previous-runs", "../作业二/evidence/confirmation-hy4flash-free-v13-previous",
        "--summary", "../" + summary_name,
        "--plan", "../作业二/configs/confirmation-plan-hy4flash-free-v13.json",
        "--runtime", "../frozen-runtime/v13/course_eval"]
    process = subprocess.run(command, cwd=shared,
        env=os.environ | {"PYTHONPATH": str(shared) + os.pathsep + str(shared / "scripts")},
        capture_output=True, text=True, check=True)
    verification = json.loads(process.stdout)
    assert verification["scored"] == 138 and verification["passed"] == 115
    assert verification["new_missing_receipts"] == 0 and verification["historical_missing_receipts"] == 9
    assert verification["returned_unverified_responses"] == 1
    probe = audit_free_billing(destination / "作业二/evidence/codebuddy-stdout-probe-v13")
    assert probe == summary["preparation_billing"] and probe["responses"] == 1
    assert summary["total_unknown_cli_requests"] == 12 and summary["failure"]["actual_model_credit"] is None
    assert summary["failure"]["later_known_model_credit"] == 0
    assert summary["new_model_requests_after_stop"] == 0 and summary["complete_report_generated"] is False
    fee = (destination / "shared/course_eval/codebuddy_free.py").read_bytes()
    assert hashlib.sha256(fee).hexdigest() == "a794f3f5c638636fa1ba21600e862e6c1b1242a75401e28dad2538afb2988b28"
    patch = json.loads((destination / "作业二/evidence/hy4flash-v13-client-patch.json").read_text())
    assert patch["live_provider_validation_after_patch"] is False and patch["new_model_calls_after_stop"] == 0
    result = {"archive": str(archive_path), "bytes": archive_path.stat().st_size, "members": len(names),
        "integrity": "passed", "historical_reports_match": True, "v12_archive_preserved_byte_for_byte": True,
        "frozen_v13_recomputation": verification, "live_preparation_requests_verified": 1,
        "original_scores_verified": 138, "genuine_failures_preserved": 23,
        "formal_missing_receipts_preserved": 9, "formal_returned_unverified_preserved": 1,
        "historical_preparation_unknown_receipts_preserved": 2, "total_unknown_cli_requests": 12,
        "empty_stream_repair_local_validation_passed": True, "empty_stream_repair_live_validated": False,
        "new_model_requests": 0, "scope": "Preserved partial comparison; 270-position matrix incomplete"}
    Path("work/hy4flash-v13-package-verification.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result, ensure_ascii=False))
    raise SystemExit(0)
if args.recovery == 7:
    from audit_confirmation_sources import audit_free_billing

    archive_path = Path("outputs/作业一二_hy4flash_v12评分与输出修复停止证据_20261117.zip")
    published = Path("work/hw0102-publish")
    destination = Path("work/verified-hy4flash-v12-package")
    destination.mkdir(exist_ok=False)
    summary_name = "作业二/evidence/hy4flash-v12-stopped-summary.json"
    historical_name = "作业一二_hy4flash_v11序列化修复停止证据_20261117.zip"
    with ZipFile(archive_path) as archive:
        assert archive.testzip() is None
        names = archive.namelist()
        assert all(not name.startswith(("/", "../", ".git/", "work/"))
                   and ".." not in Path(name).parts and "/.env" not in name for name in names)
        for relative in ("README.md", summary_name, "作业二/evidence/hy4flash-v12-stop-20261117.md"):
            assert archive.read(relative) == (published / relative).read_bytes()
        for assignment in ("一", "二"):
            relative = f"作业{assignment}/231880296_邱昱宁_作业{assignment}.pdf"
            assert archive.read(relative) == (Path("outputs") / Path(relative).name).read_bytes()
        assert archive.read("history/" + historical_name) == (Path("outputs") / historical_name).read_bytes()
        for group, expected in (("confirmation-hy4flash-free-v12", 96),
                                ("confirmation-hy4flash-free-v12-previous", 11)):
            prefix = "作业二/evidence/" + group + "/"
            assert sum(name.startswith(prefix) and name.endswith("/trial.json")
                       and len(Path(name).parts) == 5 for name in names) == expected
        archive.extractall(destination)
    summary = json.loads((destination / summary_name).read_text())
    shared = (destination / "shared").resolve()
    command = [str(Path("work/.venv/bin/python").absolute()), "scripts/verify_free_stopped_run.py",
        "--runs", "../作业二/evidence/confirmation-hy4flash-free-v12",
        "--previous-runs", "../作业二/evidence/confirmation-hy4flash-free-v12-previous",
        "--summary", "../" + summary_name,
        "--plan", "../作业二/configs/confirmation-plan-hy4flash-free-v12.json",
        "--runtime", "../frozen-runtime/v12/course_eval"]
    process = subprocess.run(command, cwd=shared, env=os.environ | {"PYTHONPATH": str(shared)},
                             capture_output=True, text=True, check=True)
    verification = json.loads(process.stdout)
    assert verification["scored"] == 95 and verification["passed"] == 84
    assert verification["new_missing_receipts"] == 1 and verification["historical_missing_receipts"] == 8
    probe = audit_free_billing(destination / "作业二/evidence/codebuddy-single-turn-probe-v12")
    assert probe == summary["preparation_billing"] and probe["responses"] == 3
    replay = json.loads((destination / "作业二/evidence/hy4flash-v12-stdout-replay.json").read_text())
    assert replay["regular_file_exact_bytes"] and replay["parsed_values_and_actual_billing_unchanged"]
    assert replay["real_model_requests"] == 0 and replay["live_cli_validation_after_fix"] is False
    assert summary["total_unknown_cli_requests"] == 11 and summary["failure"]["actual_model_credit"] is None
    assert summary["new_model_requests_after_stop"] == 0 and summary["complete_report_generated"] is False
    fee = (destination / "shared/course_eval/codebuddy_free.py").read_bytes()
    assert hashlib.sha256(fee).hexdigest() == "a794f3f5c638636fa1ba21600e862e6c1b1242a75401e28dad2538afb2988b28"
    assert (destination / "shared/course_eval/agent.py").read_bytes() != (destination / "frozen-runtime/v12/course_eval/agent.py").read_bytes()
    result = {"archive": str(archive_path), "bytes": archive_path.stat().st_size, "members": len(names),
        "integrity": "passed", "historical_reports_match": True, "v11_archive_preserved_byte_for_byte": True,
        "frozen_v12_recomputation": verification, "live_preparation_requests_verified": 3,
        "original_scores_verified": 95, "genuine_failures_preserved": 11,
        "formal_unknown_receipts_preserved": 9, "historical_preparation_unknown_receipts_preserved": 2,
        "total_unknown_cli_requests": 11, "stdout_repair_local_transport_replay_passed": True,
        "stdout_repair_live_validated": False, "new_model_requests": 0,
        "scope": "Preserved partial comparison and local stdout repair; 270-position matrix incomplete"}
    Path("work/hy4flash-v12-package-verification.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result, ensure_ascii=False))
    raise SystemExit(0)
if args.recovery in (4, 6):
    earlier = args.recovery == 4
    stem = "hy4flash-v9-repair" if earlier else "hy4flash-v11"
    label = "v9截断修复" if earlier else "v11序列化修复"
    archive_path = Path(f"outputs/作业一二_hy4flash_{label}停止证据_20261117.zip")
    published = Path("work/hw0102-publish")
    destination = Path(f"work/verified-{stem}-package")
    destination.mkdir(exist_ok=False)
    summary_name = f"作业二/evidence/{stem}-stopped-summary.json"
    summary = json.loads((published / summary_name).read_text())
    historical_name = "作业一二_hy4flash_v8首轮停止证据_20261117.zip" if earlier else "作业一二_hy4flash_v10原题验证停止证据_20261117.zip"
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
    version = 8 if earlier else 10
    frozen = destination / f"history/v{version}"
    with ZipFile(destination / "history" / historical_name) as archive:
        assert archive.testzip() is None
        assert all(not Path(name).is_absolute() and ".." not in Path(name).parts for name in archive.namelist())
        archive.extractall(frozen)
    shared = (frozen / "shared").resolve()
    command = [str(Path("work/.venv/bin/python").absolute()), "scripts/verify_free_stopped_run.py",
        "--runs", f"../作业二/evidence/confirmation-hy4flash-free-v{version}",
        "--previous-runs", f"../作业二/evidence/confirmation-hy4flash-free-v{version}-previous",
        "--summary", f"../作业二/evidence/hy4flash-v{version}-stopped-summary.json",
        "--plan", f"../作业二/configs/confirmation-plan-hy4flash-free-v{version}.json"]
    process = subprocess.run(command, cwd=shared, env=os.environ | {"PYTHONPATH": str(shared)},
                             capture_output=True, text=True, check=True)
    verification = json.loads(process.stdout)
    assert verification["scored"] == 90 and verification["passed"] == 82
    assert verification["new_missing_receipts"] + verification["historical_missing_receipts"] == (7 if earlier else 8)
    if not earlier:
        from course_eval.codebuddy_free import verify_free_response

        probe_log = destination / "作业二/evidence/codebuddy-single-turn-probe-v11/model.jsonl"
        events = [json.loads(line) for line in probe_log.read_text().splitlines()]
        responses = [event for event in events if event["event"] == "response"]
        errors = [event for event in events if event["event"] == "request_error"]
        assert sum(event["event"] == "request" for event in events) == 2
        assert len(responses) == len(errors) == 1
        assert verify_free_response(responses[0]["payload"])["credit"] == 0
        assert errors[0]["request_id"] == 2 and errors[0]["billing_status"] == "unknown"
        assert summary["failure"]["actual_model_credit"] is None
        assert summary["total_unknown_cli_requests"] == 10
        assert summary["corrected_client_live_validation"] is False and summary["formal_v11_launched"] is False
        assert summary["new_model_requests_after_stop"] == summary["new_formal_positions"] == 0
        patch = json.loads((destination / "作业二/configs/codebuddy-external-recovery-patch.json").read_text())
        assert hashlib.sha256((destination / "shared/course_eval/codebuddy_free.py").read_bytes()).hexdigest() == patch["billing_validator_sha256"]
        assert patch["patched_sha256"].startswith("a52932ce")
        replay = json.loads((destination / "作业二/evidence/hy4flash-v11-render-replay.json").read_text())
        assert replay["actual_export_maps_verified"] and replay["failed_cf1edc0d_namespace_rejected"]
        assert verify_free_response(replay["fixed"]["payload"])["credit"] == 0
        for name in ("missing_receipt", "paid_receipt"):
            try:
                verify_free_response(replay[name]["payload"])
            except ValueError:
                pass
            else:
                raise AssertionError("Offline replay weakened actual fee validation: " + name)
        result = {"archive": str(archive_path), "bytes": archive_path.stat().st_size, "members": len(names),
            "integrity": "passed", "historical_reports_match": True, "v10_archive_preserved_byte_for_byte": True,
            "frozen_v10_recomputation": verification, "new_preparation_requests": 2,
            "new_returned_zero_credit_responses": 1, "new_missing_receipts_preserved": 1,
            "total_unknown_cli_requests": 10, "actual_export_map_regression_verified": True,
            "corrected_client_live_validation": False,
            "scope": "Serialization repair preparation stop; no new formal score and no completed 270-position matrix"}
        Path(f"work/{stem}-package-verification.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        print(json.dumps(result, ensure_ascii=False))
        raise SystemExit(0)
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
