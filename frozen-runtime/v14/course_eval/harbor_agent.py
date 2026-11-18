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
from course_eval.terminal_runtime import prepare_public_runtime


# 嵌套 timeout 会建立独立进程组。到达时限时按进程树终止，避免子进程持有输出管道。
CONTAINER_COMMAND = """
terminate_tree() {
    local pid=$1 children_file children child
    kill -STOP "$pid" 2>/dev/null || return 0
    for children_file in /proc/"$pid"/task/*/children; do
        children=$(<"$children_file") 2>/dev/null || continue
        for child in $children; do
            terminate_tree "$child"
        done
    done
    kill -KILL "$pid" 2>/dev/null || :
}
expire() {
    terminate_tree "$command_pid"
    wait "$command_pid" 2>/dev/null
    exit 124
}
trap expire USR1
bash -c "$1" &
command_pid=$!
wait "$command_pid"
"""


class HarborTarget:
    def __init__(self, environment: BaseEnvironment, loop, cwd: str, system_info: dict):
        self.environment = environment
        self.loop = loop
        self.cwd = cwd
        self.system_info = system_info | {"cwd": cwd}

    def upload_file(self, source, destination: str, *, timeout: int = 20) -> None:
        task = asyncio.run_coroutine_threadsafe(self.environment.upload_file(source, destination), self.loop)
        try:
            task.result(timeout=timeout)
        except TimeoutError:
            task.cancel()
            raise

    def exec(self, command: str, *, cwd: str = "", timeout: int) -> dict:
        # 先在容器内终止超时命令，保留退出码供智能体判断。外层时限用于传输故障。
        bounded = shlex.join(("timeout", "--foreground", "--signal=USR1", "--kill-after=3s", f"{timeout}s",
                              "bash", "-c", CONTAINER_COMMAND, "course-command", command))
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
        scope = json.loads(os.environ.get("COURSE_CANDIDATE_SCOPE", "null"))
        runtime = await asyncio.to_thread(prepare_public_runtime, target, scope)
        if runtime:
            (self.logs_dir / "public-runtime.json").write_text(json.dumps(runtime, indent=2) + "\n")
        await asyncio.to_thread(run_baseline, instruction, target, self.logs_dir, limits,
                                configuration=configuration, checks=checks,
                                scope=scope)
