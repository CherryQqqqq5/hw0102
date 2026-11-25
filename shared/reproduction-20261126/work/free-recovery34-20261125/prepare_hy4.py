from copy import deepcopy
import importlib.util
import json
from pathlib import Path


ROOT = Path.cwd().resolve()
FOLDER = Path(__file__).resolve().parent
BASE = ROOT / "work/parallel-free-evaluation-20261124"
OLD = BASE / "terminal-light-probe-20261125"
spec = importlib.util.spec_from_file_location("unknown34_event_preparation", FOLDER / "prepare.py")
event = importlib.util.module_from_spec(spec)
spec.loader.exec_module(event)
read, sha, require, encoded = event.read, event.sha, event.require, event.encoded


def main():
    destination = FOLDER / "hy4-plans"
    require(not destination.exists(), "Never overwrite a prospective recovery plan")
    actual = event.inspect()
    proposal_path = FOLDER / "accepted-unknown34.proposed.json"
    proposal, prepared = read(proposal_path), read(FOLDER / "prepared.json")
    require(sha(proposal_path) == prepared["proposal_sha256"] and proposal["source_sha256"] == actual["sources"], "The prepared34 event or actual sources changed")
    plans = {arm: read(OLD / (arm + "-plan.json")) for arm in ("main", "repeat")}
    replacement = event.HY4.with_name("llm-inference-batching-scheduler-C0-free-stop34-readmission-r1")
    require(not replacement.exists(), "The only new scheduler readmission must be unused")
    require("llm-inference-batching-scheduler" not in plans["main"]["mechanical_policy_recoveries"], "Do not replace a prior registered scheduler recovery")
    plans["main"]["mechanical_policy_recoveries"]["llm-inference-batching-scheduler"] = {
        "original_run": str(event.HY4), "original_result_sha256": sha(event.HY4 / "result.json"), "original_error": None,
        "original_inner_exception": actual["hy4_interruption"]["inner_exception"], "replacement_run": str(replacement),
        "reason": "One actual unscored shared-financial-STOP interruption;retain original null and2 own-zero responses as additional cost;same task/runtime/budgets/fees",
        "historical_unknown_retained": False, "unknown34_source_evidence": str(proposal_path.relative_to(ROOT)),
        "original_known_request_count": 2, "original_own_zero_receipts": 2}
    consumers = [{"queue": p["queue"], "repeat": p["repeat"], "mechanical_policy_recoveries": deepcopy(p["mechanical_policy_recoveries"])} for p in plans.values()]
    destination.mkdir()
    for name in ("tasks.json", "checks.json", "scopes.json"):
        with (destination / name).open("xb") as stream:
            stream.write((OLD / name).read_bytes())
    registered_counts = {}
    for arm, plan in plans.items():
        guards = plan["request_guard_sha256"]
        additions = actual["sources"] | {str(path.relative_to(ROOT)): sha(path) for path in (
            Path(__file__), FOLDER / "ready_coordinator.py", FOLDER / "resume_hy4.py", proposal_path, OLD / (arm + "-plan.json"))}
        for name, expected in additions.items():
            require(name not in guards or guards[name] == expected, "Never overwrite a prior guard expectation: " + name)
            guards[name] = expected
        count = 0
        for score in (ROOT / plan["queue"]).glob("*/result.json"):
            result = read(score)
            if result.get("scoreable") is not True:
                continue
            count += 1
            protocol_path = score.parent.with_suffix(".protocol.json")
            protocol = read(protocol_path)
            saved = {"result_sha256": sha(score), "runtime_root": str((ROOT / protocol["runtime_root"]).resolve())}
            prior = plan["registered_existing_runs"].get(str(score.parent.resolve()))
            require(prior is None or all(prior[key] == value for key, value in saved.items()), "An original scored outcome/runtime changed")
            plan["registered_existing_runs"][str(score.parent.resolve())] = prior or saved
            for path in (score, protocol_path):
                name, expected = str(path.relative_to(ROOT)), sha(path)
                require(name not in guards or guards[name] == expected, "A preserved original score source changed")
                guards[name] = expected
        registered_counts[arm] = count
        require(count == (41 if arm == "main" else 54), "The exact completed original cohort changed before recovery freezing")
        plan.update(coordinator_path=str((FOLDER / "ready_coordinator.py").relative_to(ROOT)), coordinator_sha256=sha(FOLDER / "ready_coordinator.py"),
            historical_unknown_preserved=34, cache_consumers=deepcopy(consumers),
            source_plan=str((OLD / (arm + "-plan.json")).relative_to(ROOT)), source_plan_sha256=sha(OLD / (arm + "-plan.json")),
            operation_revision_scope="Same75/order/inputs/runtime/budget/grade/fee guards and classified light probes. Only one registered unscored main scheduler gets a unique readmission;null and its2 known responses retained. Coordinator only changes result['error'] to result.get('error') under unchanged SHA/scoreablefalse/passednull gates.")
        with (destination / (arm + "-plan.json")).open("x") as stream:
            stream.write(encoded(plan).decode())
    old_config = read(ROOT / "work/free-recovery33-20261125/hy4-resume.json")
    source = dict(old_config["source_sha256"])
    def bind(path):
        name, expected = str(path.relative_to(ROOT)), sha(path)
        require(name not in source or source[name] == expected, "An old immutable resumption dependency changed")
        source[name] = expected
    for path in (Path(__file__), FOLDER / "prepare.py", FOLDER / "ready_coordinator.py", FOLDER / "resume_hy4.py", proposal_path,
            destination / "main-plan.json", destination / "repeat-plan.json", destination / "tasks.json", destination / "checks.json", destination / "scopes.json"):
        bind(path)
    revision = ROOT / "work/hy4-submit-boundary-20261125/frozen-pair-r2"
    for path in (revision / "plan.json", revision / "execution-review.json", revision / "capture-admission-qualification.json", BASE / "run_fixed_free_trials.py"):
        bind(path)
    admitted = read(revision / "execution-review.json")
    require(admitted["status"] == "APPROVE" and not admitted["blocking_findings"] and admitted["plan_sha256"] == sha(revision / "plan.json"), "The fixed pre-core ReLU plan lacks exact admission")
    accepted_path = FOLDER / "accepted-unknown34.json"
    source[str(accepted_path.relative_to(ROOT))] = sha(proposal_path)
    config = {"accepted_unknown_count": 34, "accepted_evidence": str(accepted_path.relative_to(ROOT)), "recovery_folder": str(FOLDER.relative_to(ROOT)),
        "accepted_stop_sha256": sha(FOLDER / "stop-after-parent-acceptance.proposed.json"), "source_sha256": source,
        "main_plan": str((destination / "main-plan.json").relative_to(ROOT)), "repeat_plan": str((destination / "repeat-plan.json").relative_to(ROOT)),
        "fifth_plan": old_config["fifth_plan"], "pre_core_revision": {"plan": str((revision / "plan.json").relative_to(ROOT)),
            "plan_sha256": sha(revision / "plan.json"), "review": str((revision / "execution-review.json").relative_to(ROOT))},
        "scope": "Exact accepted34/noquota release after metadata and review. First two fixed ReLU sessions must actually close original+qualifiedtrue;otherwise retain and stop without resampling. Then unchanged original225 core,3ablations,2preservation. No MiniMax retry or new auxiliary model is authorized by this wrapper."}
    event.create("hy4-resume.pending-acceptance.json", encoded(config))
    event.create("hy4-plans-prepared.json", encoded({"status": "prospective_plans_not_accepted_or_started", "source_sha256": source,
        "plan_sha256": {arm: sha(destination / (arm + "-plan.json")) for arm in plans}, "pending_config_sha256": sha(FOLDER / "hy4-resume.pending-acceptance.json"),
        "completed_original_policy_scores_preserved": registered_counts, "original_dsh_baseline_count_expected": 51,
        "replacement_run": str(replacement), "unscored_original_own_zero_receipts_preserved": 2,
        "same75_inputs_and_order": True, "new_model_calls": 0, "stop_modified": False}))
    print(json.dumps({"status": "plans_prepared_no_run", "main_originals": 41, "repeat_originals": 54, "pending_config_sha256": sha(FOLDER / "hy4-resume.pending-acceptance.json")}))


if __name__ == "__main__":
    main()
