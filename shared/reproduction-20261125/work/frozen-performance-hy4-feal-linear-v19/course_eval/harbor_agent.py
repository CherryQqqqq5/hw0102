import asyncio
import json
import os
import re
import shlex
from concurrent.futures import TimeoutError

from harbor.agents.base import BaseAgent
from harbor.environments.base import BaseEnvironment
from harbor.environments.docker.docker import DockerEnvironment
from harbor.models.agent.context import AgentContext
from minisweagent import __version__

from course_eval.agent import RunLimits, run_baseline
from course_eval.docker_target import DockerTarget
from course_eval.verification import PublicCheck
from course_eval.terminal_runtime import prepare_public_runtime
from course_eval.sandbox_command import CONTAINER_COMMAND


class HarborTarget:
    def __init__(self, environment: BaseEnvironment, loop, cwd: str, system_info: dict, *, container=None):
        self.environment = environment
        self.loop = loop
        self.cwd = cwd
        self.system_info = system_info | {"cwd": cwd}
        if container is not None:
            if re.fullmatch(r"[0-9a-f]{64}", container) is None:
                raise ValueError("The exact Harbor task container ID is invalid")
            self.container = container
            self.binary = os.environ["COURSE_DOCKER_BIN"]

    docker = DockerTarget.docker

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


async def make_harbor_target(environment, *, native_dsh=False):
    identity = await environment.exec("pwd; uname -s; uname -r; uname -v; uname -m", timeout_sec=20)
    fields = (identity.stdout or "").splitlines()
    if identity.return_code or len(fields) != 5:
        raise RuntimeError("Cannot identify the benchmark container")
    info = dict(zip(("system", "release", "version", "machine"), fields[1:], strict=True))
    container = None
    if native_dsh:
        if not isinstance(environment, DockerEnvironment):
            raise ValueError("The verified DSH transport requires Harbor's Docker environment")
        selected = await environment._run_docker_compose_command(["ps", "--quiet", "main"], timeout_sec=20)
        container = (selected.stdout or "").strip()
        if selected.return_code or re.fullmatch(r"[0-9a-f]{64}", container) is None:
            raise RuntimeError("Cannot resolve exactly one original Harbor main container")
    target = HarborTarget(environment, asyncio.get_running_loop(), fields[0], info, container=container)
    if native_dsh:
        inspected, = json.loads((await asyncio.to_thread(target.docker, "inspect", container)).stdout)
        if (inspected["Id"] != container or inspected["HostConfig"]["NetworkMode"] != "none"
                or inspected["Config"]["Labels"].get("com.docker.compose.service") != "main"):
            raise RuntimeError("The resolved container is outside the original offline Harbor main service")
        target.system_info.update(image=inspected["Image"], container_id=container)
    return target


class CourseMiniSweAgent(BaseAgent):
    @staticmethod
    def name() -> str:
        return "course-mini-swe-agent"

    def version(self) -> str:
        return "dsh-sdk-0.2.2rc2" if os.environ.get("COURSE_AGENT_FRAMEWORK") == "dsh" else __version__

    async def setup(self, environment: BaseEnvironment) -> None:
        result = await environment.exec("ls /sys/class/net", timeout_sec=20)
        if result.return_code != 0 or (result.stdout or "").strip() != "lo":
            raise RuntimeError("The terminal sandbox has a non-loopback network interface")

    async def run(self, instruction: str, environment: BaseEnvironment, context: AgentContext) -> None:
        target = await make_harbor_target(environment, native_dsh=os.environ.get("COURSE_AGENT_FRAMEWORK") == "dsh")
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
