import argparse
import json
from pathlib import Path

from course_eval.agent import CourseModel, ProviderTimeout, RunLimits
from course_eval.controller import Budget
from course_eval.summarize import run_metrics


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    limits = RunLimits(model_calls=1, wall_seconds=5, max_output_tokens=32768, timeout_retries=0)
    model = CourseModel(args.out, limits, "{{output.output}}")
    model.budget = Budget(4.15)
    try:
        model.query([{"role": "system", "content": "Use one bash tool call."},
                     {"role": "user", "content": "Run exactly: printf ready"}])
    except ProviderTimeout:
        usage = run_metrics(args.out)
        assert usage["model_calls"] == 1 and usage["model_request_timeouts"] == 1, usage
        assert usage["model_request_retries"] == 0 and usage["model_responses"] == 0, usage
        assert usage["usage_unreturned_requests"] == 1, usage
        result = {"engineering_check": "pass", "formal_benchmark_trial": False,
                  "actual_short_deadline_request": True, "timeout_propagated": True,
                  "execution_seconds": 4.15 - model.budget.remaining(), "usage": usage,
                  "unreturned_usage": "unknown"}
        (args.out / "result.json").write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result, indent=2))
        return
    raise AssertionError("The short-deadline request unexpectedly completed; timeout path was not exercised")


if __name__ == "__main__":
    main()
