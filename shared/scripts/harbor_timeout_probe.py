import asyncio
import json
import os
from pathlib import Path

from course_eval.benchmarks import prepare_terminal_task, terminal_trial, write_json
from course_eval.harbor_agent import CourseMiniSweAgent, HarborTarget


class TimeoutProbe(CourseMiniSweAgent):
    @staticmethod
    def name() -> str:
        return "course-command-timeout-probe"

    async def run(self, instruction, environment, context) -> None:
        target = HarborTarget(environment, asyncio.get_running_loop(), "/app", {})
        expired = await asyncio.to_thread(target.exec, "sleep 3; touch /app/late-proof", timeout=1)
        await asyncio.sleep(3)
        recovery = await asyncio.to_thread(target.exec, "test ! -e /app/late-proof && printf 'ready\n'", timeout=5)
        write_json(self.logs_dir / "command-timeout.json", {"expired_command": expired, "next_command": recovery})
        if expired["returncode"] != 124 or recovery["returncode"] or recovery["stdout"].strip() != "ready":
            raise RuntimeError("The timed-out command did not terminate cleanly inside the container")


if __name__ == "__main__":
    manifest = json.loads(Path("work/frozen.json").read_text())
    task = next(task for task in manifest["selected"] if task["id"] == "openssl-selfsigned-cert")
    directory = Path("work/vmshare/terminal-command-timeout-regression").resolve()
    directory.mkdir(exist_ok=False)
    task_path = prepare_terminal_task(task, Path("work/datasets").resolve(), directory)
    result = terminal_trial(task_path, directory, "work.harbor_timeout_probe:TimeoutProbe", os.environ)
    write_json(directory / "result.json", result)
    if not result["scoreable"]:
        raise RuntimeError("Harbor did not complete the timeout probe and original scoring")
