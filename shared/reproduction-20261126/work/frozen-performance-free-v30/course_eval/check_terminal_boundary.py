import argparse
import asyncio
import json
import os
import time
from pathlib import Path

from harbor.agents.base import BaseAgent
from minisweagent.exceptions import TimeExceeded

from course_eval.agent import RunLimits
from course_eval.benchmarks import prepare_terminal_task, terminal_trial
from course_eval.confirmation_terminal_materials import terminal_check
from course_eval.controller import BoundedTarget, Budget
from course_eval.docker_target import DockerTarget
from course_eval.harbor_agent import HarborTarget
from course_eval.inventory import REVISIONS


class DeadlineProbeAgent(BaseAgent):
    @staticmethod
    def name():
        return "course-deadline-regression"

    def version(self):
        return "1"

    async def setup(self, environment):
        pass

    async def run(self, instruction, environment, context):
        limits = RunLimits.model_validate_json(os.environ["COURSE_RUN_LIMITS"])
        budget = Budget(limits.wall_seconds)
        target = HarborTarget(environment, asyncio.get_running_loop(), "/app", {})
        result = await asyncio.to_thread(BoundedTarget(target, budget).exec, "sleep 10", timeout=10)
        assert result["returncode"] == 124, result
        while budget.remaining():
            await asyncio.sleep(min(0.05, budget.remaining()))
        try:
            budget.require_time()
        except TimeExceeded:
            reached = time.monotonic() - budget.started
        else:
            raise AssertionError("The actual internal deadline did not stop execution")
        # 模拟实际日志序列化收尾；期间不再执行模型请求或容器动作。
        await asyncio.sleep(0.25)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        (self.logs_dir / "execution-budget.json").write_text(json.dumps({
            "limit_seconds": limits.wall_seconds, "elapsed_seconds": reached,
            "cleanup_seconds": 0.25, "model_requests": 0, "post_deadline_actions": 0,
        }, indent=2) + "\n")


def public_probe(args):
    task = next(task for task in json.loads(args.manifest.read_text())["selected"]
                if task["id"] == "modernize-scientific-stack")
    original = args.sources / f"terminal-bench-2-1-{REVISIONS['terminal']}" / "tasks" / task["id"]
    current = terminal_check(task, (original / "instruction.md").read_text())
    old = json.loads(args.previous_checks.read_text())[task["id"]][0]["command"]
    records = []
    with DockerTarget(task["image"], "/app", platform="linux/amd64", memory_mb=2048, cpus=1) as target:
        target.upload_file(Path(__file__).with_name("fixtures") / "climate_cli.py", "/app/analyze_climate_modern.py")
        requirements = args.out / "requirements.txt"
        requirements.write_text("numpy>=1\npandas>=1\nscipy>=1\n")
        target.upload_file(requirements, "/app/requirements.txt")
        for name, command, expected in (
            ("old_argparse", old, False),
            ("new_argparse", current.command, True),
            ("old_system_exit_zero", "CLIMATE_SKIP_ARGPARSE=1 " + old, False),
            ("new_system_exit_zero", "CLIMATE_SKIP_ARGPARSE=1 " + current.command, True),
            ("new_nonzero_exit", "CLIMATE_PROBE_EXIT=7 " + current.command, False),
        ):
            execution = target.exec(command, timeout=60)
            judgment = json.loads(execution["stdout"])
            assert judgment["passed"] is expected, (name, execution)
            if name == "new_nonzero_exit":
                execution_condition = next(item for item in judgment["conditions"]
                                           if item["id"] == "modern_python_execution")
                assert execution_condition["actual"]["returncode"] == 7, judgment
            record = {"case": name, "execution": execution, "judgment": judgment}
            (args.out / (name + ".json")).write_text(json.dumps(record, indent=2) + "\n")
            records.append({"case": name, "expected_passed": expected, "observed_passed": judgment["passed"]})
    return records


def deadline_probe(args):
    task = {"id": "openssl-selfsigned-cert"}
    records = []
    for name, grace in (("old_outer_deadline", 0), ("new_cleanup_grace", 30)):
        directory = (args.out / name).resolve()
        directory.mkdir()
        path = prepare_terminal_task(task, args.sources.resolve(), directory)
        limits = RunLimits(model_calls=1, wall_seconds=5, command_seconds=10, strict_wall=True)
        outcome = terminal_trial(path, directory, "course_eval.check_terminal_boundary:DeadlineProbeAgent",
                                 os.environ | {"COURSE_RUN_LIMITS": limits.model_dump_json()},
                                 agent_timeout_seconds=limits.wall_seconds + grace)
        details = json.loads((directory / outcome["harbor_result"]).read_text())
        if grace == 0:
            assert outcome["scoreable"] is False, outcome
            assert details["exception_info"]["exception_type"] == "AgentTimeoutError", details
        else:
            assert outcome["scoreable"] is True and outcome["passed"] is False, outcome
            assert details["exception_info"] is None, details
            budget = json.loads((directory / outcome["harbor_result"]).parent.joinpath("agent/execution-budget.json").read_text())
            assert 5 <= budget["elapsed_seconds"] < 5.5, budget
            assert budget["model_requests"] == budget["post_deadline_actions"] == 0, budget
        records.append({"case": name, "outcome": outcome, "original_reward": details["verifier_result"]["rewards"]["reward"]})
    return records


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--previous-checks", type=Path, required=True)
    parser.add_argument("--sources", type=Path, default=Path("work/datasets"))
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    result = {"formal_benchmark_trial": False, "model_requests": 0,
              "data": "synthetic command-line candidate with real public climate CSV; actual Harbor deadline and original OpenSSL grader",
              "public_probe_cases": public_probe(args), "deadline_cases": deadline_probe(args)}
    (args.out / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
