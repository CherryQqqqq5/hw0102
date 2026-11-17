import argparse
import hashlib
import json
import math
from collections import Counter
from pathlib import Path

from course_eval.codebuddy_free import verify_free_response
from course_eval.confirmation_summary import merge_usage
from course_eval.export_revision import LOG_NAMES
from course_eval.summarize import read_runs, run_metrics
from course_eval.verify_scores import verify


def evidence_files(directory):
    ignored = {"starter", "grader-input", "_python", "_deps", "solution", "tests"}
    return {path.relative_to(directory) for path in directory.rglob("*")
            if path.is_file() and not path.is_symlink()
            and not ignored.intersection(path.relative_to(directory).parts)
            and (path.name in LOG_NAMES or {"candidate", "candidates"}.intersection(path.relative_to(directory).parts))}


def compare_files(first, second):
    files = evidence_files(first)
    assert files == evidence_files(second), (first, second, "evidence file set differs")
    for relative in files:
        assert (first / relative).read_bytes() == (second / relative).read_bytes(), (first, second, relative)
    return len(files)


def same_usage(first, second):
    assert first.keys() == second.keys()
    for key in first:
        if isinstance(first[key], float):
            assert math.isclose(first[key], second[key], rel_tol=1e-12, abs_tol=1e-9), (key, first[key], second[key])
        else:
            assert first[key] == second[key], (key, first[key], second[key])


def audit_free_billing(directory, *, require_runtime_acceptance=True):
    requests = responses = accepted = native_usage = local_errors = recovered = 0
    largest_output = 0
    for log in directory.rglob("model.jsonl"):
        events = [json.loads(line) for line in log.read_text().splitlines()]
        sent = {event["request_id"]: event for event in events if event["event"] == "request"}
        returned = {event["request_id"]: event for event in events if event["event"] == "response"}
        verified = {event["request_id"]: event for event in events if event["event"] == "billing_verified"}
        assert len(sent) == sum(event["event"] == "request" for event in events), log
        assert len(returned) == sum(event["event"] == "response" for event in events), log
        assert returned.keys() <= sent.keys(), log
        for request in sent.values():
            assert request["model"] == "hy4flash-free", log
            if require_runtime_acceptance:
                assert request["configured_max_output_tokens"] == 4096, log
        for request_id, response in returned.items():
            proof = verify_free_response(response["payload"])
            native_usage += proof["usage_records"]
            local_errors += len(proof["local_cli_errors"])
            if require_runtime_acceptance:
                for item in response["payload"]:
                    usage = item.get("providerData", {}).get("rawUsage")
                    if usage is not None:
                        output = usage["completion_tokens"]
                        assert isinstance(output, int) and not isinstance(output, bool) and 0 <= output <= 4096, (log, request_id, output)
                        largest_output = max(largest_output, output)
            if require_runtime_acceptance:
                assert request_id in verified, (log, request_id, "missing runtime acceptance")
                assert {key: verified[request_id][key] for key in proof} == proof, (log, request_id)
        if require_runtime_acceptance:
            assert sent.keys() == returned.keys() == verified.keys(), log
            assert not any(event["event"] in {"request_error", "billing_error"} for event in events), log
        requests += len(sent)
        responses += len(returned)
        accepted += len(verified)
        recovered += sum(event["event"] == "truncation_recovered" for event in events)
    return {"requests": requests, "responses": responses, "runtime_accepted_responses": accepted,
            "offline_verified_zero_credit_responses": responses, "actual_model_usage_records": native_usage,
            "local_cli_errors_with_own_usage_proof": local_errors, "recovered_actions": recovered,
            "largest_model_output_tokens": largest_output if require_runtime_acceptance else None,
            "reported_credit_for_returned_responses": 0, "missing_responses": requests - responses,
            "missing_response_credit": None if requests != responses else 0,
            "scope": "Actual per-message provider identity and credit; CLI total_cost_usd is not billing evidence"}


def audit_free_preparation(probe_root, interface_root):
    usage = run_metrics(interface_root)
    proof = audit_free_billing(interface_root, require_runtime_acceptance=False)
    assert usage["model_calls"] == usage["model_responses"] == 2
    native_usage = proof["actual_model_usage_records"]
    for name in ("hy4flash-free-smoke-exactroute.stdout.json", "hy4flash-output-cap-4096-v1/events.json"):
        events = json.loads((probe_root / name).read_text())
        native_usage += verify_free_response(events)["usage_records"]
        result, = [event for event in events if event["type"] == "result"]
        usage["model_calls"] += 1
        usage["model_responses"] += 1
        usage["provider_turns"] += result["num_turns"]
        for target, source in (("input_tokens", "input_tokens"), ("output_tokens", "output_tokens"),
                               ("cached_input_tokens", "cache_read_input_tokens")):
            usage[target] += result["usage"][source]
    return {"usage": usage, "limited_preparation_calls": 3, "initial_connectivity_calls": 1,
            "actual_model_usage_records": native_usage, "reported_credit_for_returned_responses": 0,
            "scope": "Two interface calls, one 4096 cap probe and one initial exact-route connectivity call; excludes paid alias mistake"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-root", type=Path, default=Path("work/vmshare"))
    parser.add_argument("--plan", type=Path, default=Path("work/confirmation-plan-hy4flash-free-v7.json"))
    parser.add_argument("--runtime", type=Path, default=Path("course_eval"))
    parser.add_argument("--probe-root", type=Path, default=Path("work/codebuddy-quota-probe"))
    parser.add_argument("--summary", type=Path, default=Path("work/confirmation-hy4flash-free-v7-summary/summary.json"))
    parser.add_argument("--out", type=Path, default=Path("work/confirmation-hy4flash-free-v7-source-audit.json"))
    parser.add_argument("--protocol-commit", default="8430f57529f77271ab12dcaf443061b7ce8b1185")
    args = parser.parse_args()
    plan = json.loads(args.plan.read_text())
    summary = json.loads(args.summary.read_text())
    root = args.evidence_root
    current = root / "confirmation-hy4flash-free-v7"
    stopped, earlier = root / "confirmation-v3", root / "confirmation-v2"
    rows = read_runs(current)
    slots = {slot["run_id"]: slot for slot in plan["slots"]}
    assert len(slots) == len(rows) == 270 and all(row["scoreable"] for row in rows)
    assert {row["run_id"] for row in rows} == slots.keys()
    assert Counter((row["benchmark"], row["arm"]) for row in rows) == {
        (benchmark, arm): 30 for benchmark in ("aider", "swe", "terminal") for arm in ("B0", "C0", "C1")}
    assert plan["backend"] == "codebuddy" and plan["model"] == "hy4flash-free"
    assert plan["limits"]["max_output_tokens"] == 4096 and plan["limits"]["timeout_retries"] == 0
    free_reused = {slot["run_id"] for slot in slots.values() if slot.get("source_protocol_commit")}
    assert len(free_reused) == plan["reused_positions"] == 7
    free_compared_files = 0
    for row in rows:
        slot = slots[row["run_id"]]
        trial = json.loads((current / row["run_id"] / "trial.json").read_text())
        expected = slot.get("source_protocol_commit", args.protocol_commit)
        if row["run_id"] in free_reused:
            assert slot["source_batch"] == "confirmation-hy4flash-free-v5"
            assert expected == "32b5ef17552b0a64a94511c5ff0e24834308d7b4"
            free_compared_files += compare_files(current / row["run_id"], root / slot["source_batch"] / row["run_id"])
        assert trial["protocol_commit"] == expected, row["run_id"]
        assert trial["task"]["id"] == slot["task"] and trial["configuration"] == slot["arm"]
        assert all(trial[key] == plan[key] for key in ("model", "backend", "limits"))
        for log in (current / row["run_id"]).rglob("model.jsonl"):
            for line in log.read_text().splitlines():
                event = json.loads(line)
                assert event["protocol_commit"] == expected, (row["run_id"], event["event"])
                if event["event"] == "request":
                    assert event["model"] == plan["model"]
                    assert event["configured_max_output_tokens"] == 4096
                    assert "api_key" not in event
                    if row["run_id"] not in free_reused:
                        assert event["proxy_environment_configured"] is True
                        assert event["proxy_config_file_disabled"] is True
    for name, expected in plan["runtime_sha256"].items():
        assert hashlib.sha256((args.runtime / name).read_bytes()).hexdigest() == expected, name
    boyue_source = root / "confirmation-boyue-v4"
    boyue_stopped = root / "confirmation-boyue-v5"
    boyue_previous = root / "confirmation-boyue-v5-previous"
    boyue_rows = read_runs(boyue_stopped)
    assert len(boyue_rows) == 179 and sum(row["scoreable"] for row in boyue_rows) == 178
    boyue_reused = {row["run_id"] for row in boyue_rows
                    if json.loads((boyue_stopped / row["run_id"] / "trial.json").read_text())["protocol_commit"] == "a59144b"}
    assert len(boyue_reused) == 33
    boyue_before = read_runs(boyue_source)
    assert len(boyue_before) == 36 and sum(row["scoreable"] for row in boyue_before) == 35
    boyue_previous_rows = read_runs(boyue_previous)
    assert len(boyue_previous_rows) == 3 and sum(row["scoreable"] for row in boyue_previous_rows) == 2
    assert all(row["task"] == "modernize-scientific-stack" and row["run_id"].endswith("-r1")
               for row in boyue_previous_rows)
    assert {row["run_id"] for row in boyue_before if row["task"] != "modernize-scientific-stack"} == boyue_reused
    boyue_compared_files = sum(compare_files(boyue_stopped / run_id, boyue_source / run_id) for run_id in boyue_reused)
    boyue_compared_files += sum(compare_files(boyue_previous / row["run_id"], boyue_source / row["run_id"])
                                for row in boyue_previous_rows)
    previous = root / "confirmation-v3-previous"
    stopped_rows = read_runs(stopped)
    assert len(stopped_rows) == 266 and sum(row["scoreable"] for row in stopped_rows) == 265
    reused = {row["run_id"] for row in stopped_rows
              if json.loads((stopped / row["run_id"] / "trial.json").read_text())["protocol_commit"] ==
              "d3e51828421535d077365177395d8a3c84b3684a"}
    assert len(reused) == 80 and sum(not row["passed"] for row in stopped_rows if row["run_id"] in reused) == 7
    compared_files = sum(compare_files(stopped / run_id, earlier / run_id) for run_id in reused)
    replaced = {row["run_id"] for row in read_runs(earlier)} - reused
    assert len(replaced) == 6
    assert all("javascript__" in run_id and run_id.endswith("-r1") for run_id in replaced)
    compared_files += sum(compare_files(previous / run_id, earlier / run_id) for run_id in replaced)
    interrupted, = (root / "confirmation-v2-attempts").glob("*/trial.json")
    compared_files += compare_files(previous / interrupted.parent.name, interrupted.parent)
    prior_rows = read_runs(root / "confirmation-v1") + read_runs(previous)
    assert len(prior_rows) == 15 and sum(row["scoreable"] for row in prior_rows) == 14
    mechanical = current.with_name(current.name + "-attempts")
    # 两种来源划分必须得到相同消耗，防止把80条复用记录再次计费。
    old_selected_usage = merge_usage([run_metrics(stopped), run_metrics(previous), run_metrics(root / "confirmation-v1")])
    old_original_usage = merge_usage([run_metrics(earlier), run_metrics(root / "confirmation-v2-attempts"),
        run_metrics(root / "confirmation-v1"),
        *[run_metrics(stopped / row["run_id"]) for row in stopped_rows if row["run_id"] not in reused]])
    same_usage(old_selected_usage, old_original_usage)
    boyue_mechanical = boyue_stopped.with_name(boyue_stopped.name + "-attempts")
    boyue_usage = merge_usage([run_metrics(boyue_stopped), run_metrics(boyue_mechanical), run_metrics(boyue_previous)])
    original_boyue_usage = merge_usage([run_metrics(boyue_source), run_metrics(boyue_mechanical),
        *[run_metrics(boyue_stopped / row["run_id"]) for row in boyue_rows if row["run_id"] not in boyue_reused]])
    same_usage(boyue_usage, original_boyue_usage)
    free_previous = [root / "confirmation-hy4flash-free-v7-previous"]
    free_previous_rows = [row for directory in free_previous for row in read_runs(directory)]
    assert len(free_previous_rows) == 6 and not any(row["scoreable"] for row in free_previous_rows)
    for item in plan["preserved_previous_attempts"]:
        free_compared_files += compare_files(root / item["source_batch"] / item["source_run_id"],
                                             free_previous[0] / item["preserved_run_id"])
    selected_usage = merge_usage([run_metrics(current), run_metrics(mechanical), *map(run_metrics, free_previous)])
    original_free_usage = merge_usage([run_metrics(root / "confirmation-hy4flash-free-v5"),
                                      *[run_metrics(root / item["source_batch"] / item["source_run_id"])
                                        for item in plan["preserved_previous_attempts"]
                                        if item["source_batch"] != "confirmation-hy4flash-free-v5"],
                                      run_metrics(mechanical),
                                      *[run_metrics(current / row["run_id"]) for row in rows if row["run_id"] not in free_reused]])
    same_usage(selected_usage, original_free_usage)
    same_usage(selected_usage, summary["all_attempt_usage"])
    assert summary["previous_attempt_count"] == 6 and summary["previous_scored_count"] == 0
    free_billing = audit_free_billing(current)
    # 恢复前缺失回执继续未知，主矩阵仍逐回复严格验证零费用。
    mechanical_billing = audit_free_billing(mechanical, require_runtime_acceptance=False)
    previous_billing = [audit_free_billing(directory, require_runtime_acceptance=False) for directory in free_previous]
    assert sum(item["missing_responses"] for item in previous_billing) == 3
    assert (free_billing["missing_responses"] + mechanical_billing["missing_responses"]
            + sum(item["missing_responses"] for item in previous_billing)
            == selected_usage["usage_unreturned_requests"])
    preparation_usage = merge_usage([run_metrics(root / name) for name in
        ("boyue-interface-v1", "boyue-agent-v1", "boyue-timeout-v1")])
    assert preparation_usage["model_calls"] == 18 and preparation_usage["model_responses"] == 17
    assert preparation_usage["usage_unreturned_requests"] == 1
    totals = {arm: sum(row["passed"] for row in rows if row["arm"] == arm) for arm in ("B0", "C0", "C1")}
    for comparison in summary["comparisons"]:
        expected = 100 * (totals[comparison["treatment"]] - totals[comparison["reference"]]) / 90
        assert math.isclose(comparison["delta_percentage_points"], expected, abs_tol=1e-12)
    original_scores = [verify(current), verify(boyue_stopped, allow_unscored=True),
                       verify(boyue_source, allow_unscored=True), verify(boyue_previous, allow_unscored=True),
                       verify(stopped, allow_unscored=True), verify(root / "confirmation-v1"),
                       verify(previous, allow_unscored=True),
                       *[verify(directory, allow_unscored=True) for directory in free_previous]]
    archived_trials = list(mechanical.glob("*/trial.json"))
    assert all(json.loads((path.parent / "result.json").read_text())["scoreable"] is False for path in archived_trials)
    result = {"batch": current.name, "protocol_commit": args.protocol_commit,
              "primary_positions": len(rows), "reused_positions": len(free_reused), "new_positions": len(rows) - len(free_reused),
              "free_previous_attempts": 6, "free_previous_scored": 0,
              "free_billing": free_billing, "mechanical_free_billing": mechanical_billing,
              "previous_free_billing": previous_billing,
              "boyue_main_scored_preserved": sum(row["scoreable"] for row in boyue_rows),
              "boyue_previous_attempts": len(boyue_previous_rows), "boyue_previous_scored": 2,
              "codebuddy_scored_records_preserved": 265 + 14,
              "codebuddy_attempts_preserved": len(stopped_rows) + len(prior_rows),
              "mechanical_attempts": len(archived_trials),
              "evidence_files_compared": compared_files + boyue_compared_files + free_compared_files,
              "runtime_matches_frozen_plan": True, "original_score_checks_by_batch": original_scores,
              "all_attempt_usage": selected_usage, "codebuddy_attempt_usage": old_selected_usage,
              "boyue_attempt_usage": boyue_usage,
              "boyue_preparation_usage": preparation_usage,
              "free_preparation": audit_free_preparation(args.probe_root, root / "hy4flash-interface-v1"),
              "scope": "Complete independent free matrix and actual zero-credit receipts; preserved separate historical providers and nonduplicating source partitions; no model or grader rerun"}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
