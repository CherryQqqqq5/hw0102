import os
import re
from pathlib import Path


PYTEST_COMMAND = re.compile(r"^\s*(?:uv run )?pytest (--ctrf /logs/verifier/ctrf\.json /tests/test_outputs\.py (?:-v )?-rA)$",
                            re.MULTILINE)
PINNED_DEPENDENCY = r"[a-zA-Z0-9_-]+==[0-9.]+"
COMMON = ("pytest==8.4.1", "pytest-json-ctrf==0.3.5")
BOOTSTRAP = {
    "apt-get update", "apt-get install -y curl", "apt-get install -y curl gcc",
    "apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y expect curl",
    "curl -LsSf https://astral.sh/uv/0.9.5/install.sh | sh",
    "source $HOME/.local/bin/env",
    'if [ "$PWD" = "/" ]; then',
    'echo "Error: No working directory set. Please set a WORKDIR in your Dockerfile before running this script."',
    "exit 1", "fi",
}
REWARD = 'if [ $? -eq 0 ]; then\n  echo 1 > /logs/verifier/reward.txt\nelse\n  echo 0 > /logs/verifier/reward.txt\nfi\n'


def offline_spec(script: str) -> tuple[str, tuple[str, ...], str]:
    test_command = PYTEST_COMMAND.search(script)
    if not script.endswith(REWARD) or test_command is None:
        raise ValueError("The original verifier is outside the supported pytest bootstrap pattern")
    prefix, suffix = script[:test_command.start()], script[test_command.end():]
    if suffix.strip() != REWARD.strip():
        raise ValueError("The original verifier contains additional grading actions")
    requirements = []
    interpreter = "python"
    for line in prefix.splitlines():
        line = line.strip().removesuffix("\\").strip()
        if not line or line.startswith("#") or line in BOOTSTRAP or line == "uvx":
            continue
        if line == "-p 3.13":
            interpreter = "/tests/_python/bin/python3.13"
        elif line == "uv venv -p 3.12 .tb":
            interpreter = "/tests/_python/bin/python3.12"
        elif line == "source .tb/bin/activate" and interpreter.endswith("3.12"):
            continue
        elif re.fullmatch(r"-w " + PINNED_DEPENDENCY, line):
            requirements.append(line.removeprefix("-w "))
        elif interpreter.endswith("3.12") and re.fullmatch(r"uv pip install(?: " + PINNED_DEPENDENCY + r")+", line):
            requirements.extend(line.removeprefix("uv pip install ").split())
        elif line == "pip install " + " ".join(COMMON):
            requirements.extend(COMMON)
        else:
            raise ValueError(f"The verifier contains a task-specific bootstrap step: {line}")
    if not set(COMMON).issubset(requirements):
        raise ValueError("The original verifier does not request the standard pytest dependencies")
    return interpreter, tuple(sorted(requirements)), test_command.group(1)


def dependency_key(interpreter: str, requirements: tuple[str, ...]) -> str:
    prefix = "python3.12+" if interpreter.endswith("3.12") else ""
    return prefix + "+".join(requirements)


def prepare_offline_verifier(task: Path) -> None:
    test = task / "tests/test.sh"
    script = test.read_text()
    interpreter, requirements, pytest_args = offline_spec(script)
    deps_root = Path(os.environ["COURSE_TERMINAL_DEPS"])
    dependencies = deps_root / (dependency_key(interpreter, requirements) + ".tar.gz")
    os.link(dependencies, test.parent / "_deps.tar.gz")
    unpack = 'mkdir -p /tests/_deps && tar -xzf /tests/_deps.tar.gz -C /tests/_deps || exit 2\n'
    if interpreter != "python":
        archive_variable = "COURSE_TERMINAL_PYTHON_312" if interpreter.endswith("3.12") else "COURSE_TERMINAL_PYTHON"
        os.link(Path(os.environ[archive_variable]), test.parent / "_python.tar.gz")
        unpack += ('mkdir -p /tests/_python && '
                   'tar -xzf /tests/_python.tar.gz -C /tests/_python --strip-components=1 || exit 2\n')
    precheck = 'if [ "$PWD" = "/" ]; then exit 2; fi\n' if 'if [ "$PWD" = "/" ]; then' in script else ""
    # 安装步骤移到宿主侧。测试文件、pytest 参数和奖励判定来自原题。
    test.write_text("#!/bin/bash\n" + precheck + 'test "$(ls /sys/class/net)" = lo || exit 2\n' + unpack
                    + 'export PYTHONPATH="/tests/_deps${PYTHONPATH:+:$PYTHONPATH}"\n'
                    + f'{interpreter} -m pytest {pytest_args}\n\n' + REWARD)
