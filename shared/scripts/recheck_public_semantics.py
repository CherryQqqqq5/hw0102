import argparse
import importlib.util
import json
import math
import sys
from pathlib import Path

from course_eval.public_semantics import check_scheduler, read_jsonl, scheduler_metrics


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path, default=Path("../作业二/evidence/public-semantics-v1"))
    args = parser.parse_args()
    root = args.evidence.resolve()
    results = []
    for arm, expected_shapes, expected_pass in (("B0", 13, False), ("RP", 7, True)):
        directory = root / arm
        candidate = directory / "task_file"
        baseline = json.loads((directory / "baseline.json").read_text())
        report = check_scheduler(candidate, baseline)
        saved = json.loads((directory / "public-check-current.json").read_text())
        assert report == saved, f"Recomputed conditions differ: {arm}"
        shapes = next(item["actual"] for item in report["conditions"] if item["id"] == "scheduler.global_shape_cap")
        assert shapes == expected_shapes and report["passed"] is expected_pass, arm
        provenance = json.loads((directory / "provenance.json").read_text())
        source = Path(provenance["source"]).relative_to("work/vmshare")
        events = read_jsonl(root.parent / source)
        event = next(item for item in events if item["tool_call_id"] == provenance["event_id"])
        assert (directory / "original-command.sh").read_text().rstrip("\n") == event["command"].rstrip("\n")
        assert event["stdout"] == provenance["logged_stdout"]
        # 原公开成本模型独立计算，避免只复算本检查器自身的公式。
        spec = importlib.util.spec_from_file_location("public_cost_" + arm, candidate / "scripts/cost_model.py")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        for bucket in (1, 2):
            requests = {row["request_id"]: row for row in read_jsonl(candidate / f"input_data/requests_bucket_{bucket}.jsonl")}
            plan = read_jsonl(candidate / f"output_data/plan_b{bucket}.jsonl")
            expected = module.CostModel(64).plan_metrics(requests, plan)
            actual = scheduler_metrics(requests, plan)
            assert all(math.isclose(actual[key], expected[key], rel_tol=1e-12, abs_tol=1e-8)
                       for key in ("cost", "pad_ratio", "p95_latency_ms", "sequential_timecost", "pad_tokens", "real_tokens"))
        results.append({"arm": arm, "global_shapes": shapes, "public_passed": report["passed"],
                        "historical_command_matched": True, "public_formula_matched": True})
    reference = json.loads((root / "query/container-reference-once.json").read_text())
    assert reference["status"] == "unknown" and reference["reference_completed"] is None
    assert reference["database_unchanged"] and reference["database_before"] == reference["database_after"]
    print(json.dumps({"scheduler_recomputed": results, "query_record_verified": "original reference timed out; no new query executed",
                      "model_calls": 0}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
