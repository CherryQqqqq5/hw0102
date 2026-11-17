import json
import shutil
from pathlib import Path

from audit_confirmation_sources import audit_free_billing, compare_files, evidence_files, same_usage
from course_eval.confirmation import prepare
from course_eval.confirmation_summary import merge_usage
from course_eval.summarize import read_runs, run_metrics
from course_eval.verify_scores import verify


def copy_evidence(source, destination):
    destination.mkdir(parents=True, exist_ok=False)
    for relative in evidence_files(source):
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source / relative, target)
    return compare_files(source, destination)


root = Path("work/vmshare")
source = root / "confirmation-hy4flash-free-v8"
destination = root / "confirmation-hy4flash-free-v10"
previous = root / "confirmation-hy4flash-free-v10-previous"
plan_path = Path("work/confirmation-plan-hy4flash-free-v10.json")
assert not destination.exists() and not previous.exists() and not plan_path.exists()
source_plan = json.loads(Path("work/confirmation-plan-hy4flash-free-v8.json").read_text())
probe = json.loads(Path("work/codebuddy-single-turn-probe-v10/summary.json").read_text())
assert [record["case"] for record in probe["records"]] == ["truncated-4096", "outer-recovery-4096"]
assert probe["actual_cli_requests"] == 2
assert probe["records"][0]["completion_tokens"] == [4096]
assert all(record["billing"]["credit"] == 0 for record in probe["records"])
audit_free_billing(Path("work/codebuddy-single-turn-probe-v10"))
rows = read_runs(source)
reused = [row for row in rows if row["scoreable"]]
unscored = [row for row in rows if not row["scoreable"]]
assert len(rows) == 91 and len(reused) == 90 and len(unscored) == 1
assert sum(not row["passed"] for row in reused) == 8
source_scores = verify(source, allow_unscored=True)
for row in reused:
    directory = source / row["run_id"]
    trial = json.loads((directory / "trial.json").read_text())
    source_slot = next(slot for slot in source_plan["slots"] if slot["run_id"] == row["run_id"])
    assert trial["protocol_commit"] == source_slot.get("source_protocol_commit", "fadb4083ac1bbf63bec97095d0702943a40f92ff")
    assert all(trial[key] == source_plan[key] for key in ("model", "backend", "limits"))
    audit_free_billing(directory)

prepare(Path("work/confirmation-frozen-v1.json"), Path("work/confirmation-public-checks-v1.json"),
        root / "confirmation-preflights-v1", plan_path, attempt_cap=290)
plan = json.loads(plan_path.read_text())
assert all(plan[key] == source_plan[key] for key in (
    "seed", "model", "backend", "codebuddy_version", "limits", "manifest_sha256", "checks_sha256",
    "python_version", "package_versions"))
assert {name for name, checksum in plan["runtime_sha256"].items()
        if checksum != source_plan["runtime_sha256"][name]} == {"agent.py", "confirmation.py"}
assert plan["codebuddy_headless_sha256"] == probe["client_sha256"]
destination.mkdir()
previous.mkdir()
slots = {slot["run_id"]: slot for slot in plan["slots"]}
copied = 0
for row in reused:
    copied += copy_evidence(source / row["run_id"], destination / row["run_id"])
    trial = json.loads((source / row["run_id"] / "trial.json").read_text())
    slots[row["run_id"]].update(source_batch=source.name, source_protocol_commit=trial["protocol_commit"])
preserved = []
old_previous = source.with_name(source.name + "-previous")
for item in source_plan["preserved_previous_attempts"]:
    copied += copy_evidence(old_previous / item["preserved_run_id"], previous / item["preserved_run_id"])
    preserved.append(item)
for row in unscored:
    name = "v8__" + row["run_id"]
    copied += copy_evidence(source / row["run_id"], previous / name)
    preserved.append({"source_batch": source.name, "source_run_id": row["run_id"], "preserved_run_id": name})
assert len(preserved) == 10
assert len(read_runs(destination)) == 90 and len(read_runs(previous)) == 10
before = merge_usage([run_metrics(source), run_metrics(old_previous)])
after = merge_usage([run_metrics(destination), run_metrics(previous)])
same_usage(before, after)
assert after["usage_unreturned_requests"] == 7
plan.update(reused_positions=90, new_positions=180, preserved_previous_attempts=preserved,
            cumulative_attempt_cap=300,
            network_policy={"inherit_proxy_environment": True, "proxy_config_file_disabled": True,
                            "sdk_proxy_source": "env", "new_request_unknown_or_nonzero_credit": "stop"},
            historical_unknown_cost="Preserved as unknown; never replaced by new request receipts",
            historical_unknown_cli_requests={"formal": 7, "preparation": 1, "total": 8,
                "preparation_trace": "work/codebuddy-single-turn-probe-v9/truncated-64/model.jsonl"},
            transport_sensitivity_excluded_task="django__django-11999",
            diagnostic_policy={"cli_pid_recorded": True, "timeout_reads_own_workspace_sdk_log": True,
                               "sdk_log_never_proves_billing": True, "model_arguments_and_timeouts_unchanged": True},
            mechanical_recovery={"scope": "Disable two SDK-internal recovery chains; preserve original StructuredOutput interface",
                "environment": {"COURSE_CODEBUDDY_EXTERNAL_RECOVERY": "1"},
                "outer_recovery": "Only after actual zero-credit receipt; charged to existing 24 decisions and 600 seconds",
                "preparation_evidence": "work/codebuddy-single-turn-probe-v10/summary.json",
                "preparation_cli_requests": 2, "preparation_scores": 0},
            resumed_unscored_run_id=unscored[0]["run_id"], resumed_position_total_attempt_number=2)
plan_path.write_text(json.dumps(plan, indent=2) + "\n")
verification = {"stage": "frozen_resume_ready", "new_model_requests": 0,
                "source_scores": source_scores, "reused_positions": 90,
                "preserved_valid_failures": 8, "new_positions": 180, "previous_attempts": 10,
                "evidence_files_compared": copied, "usage_source_partitions_match": True,
                "all_free_formal_usage_before_resume": after,
                "actual_model_identity_and_credit_rules_unchanged": True,
                "local_timeout_diagnostics": "PID-scoped phases; internal recovery disabled with opt-in SDK patch; original billing guard unchanged",
                "reused_original_scores": verify(destination),
                "previous_original_scores": verify(previous, allow_unscored=True)}
Path("work/hy4flash-v10-resume-validation.json").write_text(json.dumps(verification, ensure_ascii=False, indent=2) + "\n")
print(json.dumps({key: verification[key] for key in (
    "stage", "new_model_requests", "reused_positions", "preserved_valid_failures", "new_positions",
    "previous_attempts", "evidence_files_compared", "usage_source_partitions_match")}, ensure_ascii=False))
