import asyncio
import json
import os
import shlex
from concurrent.futures import TimeoutError

from harbor.agents.base import BaseAgent
from harbor.environments.base import BaseEnvironment
from harbor.models.agent.context import AgentContext
from minisweagent import __version__

from course_eval.agent import RunLimits, run_baseline
from course_eval.verification import PublicCheck


class HarborTarget:
    def __init__(self, environment: BaseEnvironment, loop, cwd: str, system_info: dict):
        self.environment = environment
        self.loop = loop
        self.cwd = cwd
        self.system_info = system_info | {"cwd": cwd}

    def exec(self, command: str, *, cwd: str = "", timeout: int) -> dict:
        # 先在容器内终止超时命令，保留退出码供智能体判断。外层时限用于传输故障。
        bounded = f"timeout --kill-after=2s {timeout}s bash -c {shlex.quote(command)}"
        task = asyncio.run_coroutine_threadsafe(
            self.environment.exec(bounded, cwd=cwd or self.cwd, timeout_sec=timeout + 5), self.loop,
        )
        try:
            result = task.result(timeout=timeout + 15)
        except TimeoutError:
            task.cancel()
            raise
        return {"stdout": result.stdout or "", "stderr": result.stderr or "", "returncode": result.return_code}


class CourseMiniSweAgent(BaseAgent):
    @staticmethod
    def name() -> str:
        return "course-mini-swe-agent"

    def version(self) -> str:
        return __version__

    async def setup(self, environment: BaseEnvironment) -> None:
        result = await environment.exec("ls /sys/class/net", timeout_sec=20)
        if result.return_code != 0 or (result.stdout or "").strip() != "lo":
            raise RuntimeError("The terminal sandbox has a non-loopback network interface")

    async def run(self, instruction: str, environment: BaseEnvironment, context: AgentContext) -> None:
        identity = await environment.exec("pwd; uname -s; uname -r; uname -v; uname -m", timeout_sec=20)
        fields = (identity.stdout or "").splitlines()
        if identity.return_code or len(fields) != 5:
            raise RuntimeError("Cannot identify the benchmark container")
        info = dict(zip(("system", "release", "version", "machine"), fields[1:], strict=True))
        target = HarborTarget(environment, asyncio.get_running_loop(), fields[0], info)
        limits = RunLimits.model_validate_json(os.environ.get("COURSE_RUN_LIMITS", "{}"))
        checks = tuple(PublicCheck(**(item | {"dependencies": tuple(item["dependencies"])}))
                       for item in json.loads(os.environ.get("COURSE_PUBLIC_CHECKS", "[]")))
        configuration = os.environ.get("COURSE_CONFIGURATION", "B0")
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(run_baseline, instruction, target, self.logs_dir, limits,
                                configuration=configuration, checks=checks)
