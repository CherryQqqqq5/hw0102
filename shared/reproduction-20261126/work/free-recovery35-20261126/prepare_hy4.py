from copy import deepcopy
from pathlib import Path
import json

import prepare as event


ROOT, FOLDER, BASE = event.ROOT, event.FOLDER, event.BASE
OLD = ROOT / "work/hy4-proxy-image-preparation-20261126"
read, sha, require, encoded = event.read, event.sha, event.require, event.encoded


def main():
    destination = FOLDER / "hy4-plans"
    require(not destination.exists(), "Do not overwrite prospective plans")
    evidence = read(FOLDER / "accepted-unknown35.proposed.json")
    actual = event.inspect(ROOT / evidence["prepared_metadata"]["path"])
    for name, expected in evidence["source_sha256"].items():
        require(sha(ROOT / name) == expected, "Actual preserved evidence changed")
    qualification = read(FOLDER / "qualification.json")
    require(qualification["status"] == "passed" and qualification["writer_sha256"] == sha(FOLDER / "prepare.py")
        and qualification["prepared_sha256"] == sha(FOLDER / "prepared.json"), "The exact event qualification must pass first")
    review = read(OLD / "execution-review.json")
    require(review["status"] == "APPROVE" and not review["blocking_findings"], "Use the independently admitted image route")
    plans = {arm: read(OLD / "plans" / (arm + "-plan.json")) for arm in ("main", "repeat")}
    require(all(sha(OLD / "plans" / (arm + "-plan.json")) == review["plan_sha256"][arm] for arm in plans), "The approved source plans changed")
    replacement = event.RUN.with_name("django__django-11999-C0-upstream-error35-readmission-r2")
    require(not replacement.exists() and "django__django-11999" not in plans["repeat"]["mechanical_policy_recoveries"], "Exactly one unused null readmission is eligible")
    plans["repeat"]["mechanical_policy_recoveries"]["django__django-11999"] = {
        "original_run": str(event.RUN), "original_result_sha256": sha(event.RUN / "result.json"),
        "original_error": actual["original_result"]["error"], "replacement_run": str(replacement),
        "reason": "Exact unscored upstream-error interruption;retain7 own-zero calls and unknown8 as extra cost;same task/runtime/budgets/fees",
        "historical_unknown_retained": True, "unknown35_source_evidence": str((FOLDER / "accepted-unknown35.proposed.json").relative_to(ROOT)),
        "original_known_request_count": 8, "original_own_zero_receipts": 7}
    consumers = [{"queue": plan["queue"], "repeat": plan["repeat"], "mechanical_policy_recoveries": deepcopy(plan["mechanical_policy_recoveries"])} for plan in plans.values()]
    destination.mkdir()
    for name in ("tasks.json", "checks.json", "scopes.json"):
        (destination / name).write_bytes((OLD / "plans" / name).read_bytes())
    additions = evidence["source_sha256"] | {str(path.relative_to(ROOT)): sha(path) for path in (
        FOLDER / "prepare.py", FOLDER / "qualify.py", FOLDER / "qualification.json", FOLDER / "prepared.json",
        FOLDER / "accepted-unknown35.proposed.json", Path(__file__), FOLDER / "resume_hy4.py", OLD / "execution-review.json")}
    def merge(target, source):
        for name, expected in source.items():
            require(name not in target or target[name] == expected, "Never replace a frozen expectation: " + name)
            target[name] = expected
    for arm, plan in plans.items():
        merge(plan["request_guard_sha256"], additions)
        for row in actual["original177"][arm]:
            directory = ROOT / row["run_dir"]
            protocol = read(directory.with_suffix(".protocol.json"))
            saved = {"result_sha256": sha(directory / "result.json"), "runtime_root": str((ROOT / protocol["runtime_root"]).resolve())}
            prior = plan["registered_existing_runs"].get(str(directory))
            require(prior is None or all(prior[k] == v for k, v in saved.items()), "A registered actual score/runtime changed")
            plan["registered_existing_runs"][str(directory)] = prior or saved
        source_plan = OLD / "plans" / (arm + "-plan.json")
        plan.update(historical_unknown_preserved=35, cache_consumers=deepcopy(consumers),
            source_plan=str(source_plan.relative_to(ROOT)), source_plan_sha256=sha(source_plan),
            operation_revision_scope="Same75/order/input/checks/scopes/runtime/model/budget/fee/grade/resource/light-probe;onlyrepeat11999 null gets one unique upstream-error readmission;main has no run and continues normally;177 original scores preserved")
        with (destination / (arm + "-plan.json")).open("xb") as stream:
            stream.write(encoded(plan))
    original = event.resume34.verify_config(read(event.R34 / "hy4-resume.json"))
    paths = [FOLDER / name for name in ("prepare.py", "qualify.py", "qualification.json", "prepared.json", "prepare_hy4.py", "resume_hy4.py", "accepted-unknown35.proposed.json")]
    paths += [OLD / "continuation.py", OLD / "continuation-qualification.json", OLD / "qualify_continuation.py", OLD / "execution-review.json",
        event.R34 / "hy4-resume.json", event.R34 / "hy4-resume-review.json", event.R34 / "resume_hy4.py",
        BASE / "resume_verified_hy4.py", BASE / "recover_hy4_quota.py", ROOT / "work/check_codebuddy_free_models.py",
        BASE / "run_ready_queues_light_probe.py", BASE / "ready_coordinator_light_probe.py", BASE / "prepare_reuse_ablation.py",
        BASE / "run_reuse_ablation.py", BASE / "run_fixed_free_trials.py", ROOT / original["fifth_plan"]]
    paths += [destination / name for name in ("main-plan.json", "repeat-plan.json", "tasks.json", "checks.json", "scopes.json")]
    paths += [ROOT / name for name in plans["main"]["image_preparation_sha256"]]
    sources = {str(path.relative_to(ROOT)): sha(path) for path in paths}
    sources[str((FOLDER / "accepted-unknown35.json").relative_to(ROOT))] = sha(FOLDER / "accepted-unknown35.proposed.json")
    config = {"accepted_unknown_count": 35, "accepted_evidence": str((FOLDER / "accepted-unknown35.json").relative_to(ROOT)),
        "recovery_folder": str(FOLDER.relative_to(ROOT)), "accepted_stop_sha256": sha(FOLDER / "stop-after-parent-acceptance.proposed.json"),
        "recovery_config_sha256": sha(event.R34 / "hy4-resume.json"), "source_sha256": sources,
        "main_plan": str((destination / "main-plan.json").relative_to(ROOT)), "repeat_plan": str((destination / "repeat-plan.json").relative_to(ROOT)),
        "fifth_plan": original["fifth_plan"], "old_actors": [], "recovery_ancestry_sources": 82,
        "scope": "No old actor may remain. Parent accepts exact35,prepares formal config and approves before run. Fresh cloud metadata/1200-second proof and locked exact hold release;reuse reviewed proxy continuation original225 then3 then2,including image prewarming. Completed ReLU revision not repeated. Future STOP always blocks;no auxiliary retries."}
    event.create("hy4-resume.pending-acceptance.json", encoded(config))
    event.create("hy4-plans-prepared.json", encoded({"status": "prospective_only_not_accepted_or_started",
        "plan_sha256": {arm: sha(destination / (arm + "-plan.json")) for arm in plans},
        "pending_config_sha256": sha(FOLDER / "hy4-resume.pending-acceptance.json"), "new_readmission": str(replacement),
        "retained_originals": 177, "own_zero_interruption_cost": 7, "unknown_cost": None,
        "main11999_has_no_run": True, "new_model_calls": 0, "stop_modified": False}))
    print(json.dumps(read(FOLDER / "hy4-plans-prepared.json")))


if __name__ == "__main__":
    main()
