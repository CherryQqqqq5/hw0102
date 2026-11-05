import argparse
import json
from collections import Counter
from pathlib import Path


def verify(root: Path) -> dict:
    counts = Counter()
    positions = set()
    for path in sorted(root.glob("*/trial.json")):
        trial = json.loads(path.read_text())
        result = json.loads((path.parent / "result.json").read_text())
        task = trial["task"]
        assert result["scoreable"] is True, path.parent
        assert isinstance(result["passed"], bool), path.parent
        if task["benchmark"] == "swe":
            report, = path.parent.rglob("report.json")
            judgment = json.loads(report.read_text())[task["id"]]
            assert judgment.get("infra_failure", False) is False, report
            passed = judgment["resolved"]
        elif task["benchmark"] == "terminal":
            report = path.parent / result["harbor_result"]
            judgment = json.loads(report.read_text())
            assert judgment["exception_info"] is None, report
            reward = judgment["verifier_result"]["rewards"]["reward"]
            assert reward in (0, 1), report
            passed = reward == 1
            reward_file = next(report.parent.rglob("reward.txt"))
            assert float(reward_file.read_text().strip()) == reward, reward_file
        elif task["benchmark"] == "aider":
            if result.get("missing_required_sources"):
                passed = False
            else:
                report = path.parent / "grader.json"
                judgment = json.loads(report.read_text())
                assert judgment["returncode"] not in (124, 125, 126, 127, 137), report
                assert judgment["returncode"] == result["grader_exit_code"], report
                passed = judgment["returncode"] == 0
        else:
            raise ValueError(task["benchmark"])
        assert passed == result["passed"], path.parent
        position = (task["id"], trial["configuration"], int(path.parent.name.rsplit("-r", 1)[1]))
        assert position not in positions, position
        positions.add(position)
        counts[task["benchmark"]] += 1
    plan_path = root / "run-plan.json"
    if plan_path.exists():
        plan = json.loads(plan_path.read_text())
        expected = {(slot["task"], slot["arm"], slot["repeat"]) for slot in plan["slots"]}
        assert positions == expected, {"missing": sorted(expected - positions), "unexpected": sorted(positions - expected)}
        for path in root.glob("*/trial.json"):
            trial = json.loads(path.read_text())
            assert all(trial[key] == plan[key] for key in ("model", "backend", "limits")), path
    return {"runs": str(root), "score_records_verified": sum(counts.values()), "by_benchmark": dict(counts),
            "check": "saved original grader decisions agree with result.json; graders were not re-executed"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=Path, nargs="+", required=True)
    args = parser.parse_args()
    print(json.dumps([verify(root) for root in args.runs], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
