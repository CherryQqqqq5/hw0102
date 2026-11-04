import argparse
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
        nested = await asyncio.to_thread(target.exec, "timeout 12s bash -c 'sleep 3; touch /app/nested-late-proof'; :", timeout=1)
        await asyncio.sleep(3)
        command = "test ! -e /app/late-proof && test ! -e /app/nested-late-proof && printf 'ready\n'"
        recovery = await asyncio.to_thread(target.exec, command, timeout=5)
        write_json(self.logs_dir / "command-timeout.json", {"expired_command": expired, "nested_timeout": nested,
                                                             "next_command": recovery})
        if any(result["returncode"] != 124 for result in (expired, nested)) or recovery["returncode"] or recovery["stdout"].strip() != "ready":
            raise RuntimeError("The timed-out command did not terminate cleanly inside the container")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, default=Path("work/frozen.json"))
    parser.add_argument("--sources", type=Path, default=Path("work/datasets"))
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    task = next(task for task in manifest["selected"] if task["id"] == "openssl-selfsigned-cert")
    directory = args.out.resolve()
    directory.mkdir(exist_ok=False)
    task_path = prepare_terminal_task(task, args.sources.resolve(), directory)
    module = __spec__.name if __spec__ else f"{Path(__file__).parent.name}.harbor_timeout_probe"
    result = terminal_trial(task_path, directory, f"{module}:TimeoutProbe", os.environ)
    write_json(directory / "result.json", result)
    if not result["scoreable"]:
        raise RuntimeError("Harbor did not complete the timeout probe and original scoring")
