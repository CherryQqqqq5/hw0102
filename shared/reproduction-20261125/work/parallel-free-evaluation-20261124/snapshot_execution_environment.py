import importlib.metadata
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys


def main():
    root, folder = Path.cwd(), Path(__file__).parent.resolve()
    packages = {}
    for distribution in importlib.metadata.distributions():
        name = re.sub(r"[-_.]+", "-", distribution.metadata["Name"]).lower()
        if name in packages and packages[name] != distribution.version:
            raise ValueError("Multiple installed versions of a distribution: " + name)
        packages[name] = distribution.version
    recorded = {}
    old = root / "work/hw0102-publish/shared/requirements-analysis.txt"
    for line in old.read_text().splitlines():
        if line.strip() and not line.startswith("#"):
            name, version = line.split("==", 1)
            recorded[re.sub(r"[-_.]+", "-", name).lower()] = version
    binary = root / "work/vendor/docker/docker"
    env = os.environ | {"DOCKER_HOST": "unix://" + str(root / "work/v/c/sock/docker.sock"),
        "DOCKER_CONFIG": str(root / "work/docker-config")}
    docker = subprocess.run([str(binary), "info", "--format",
        '{"cpu_count":{{json .NCPU}},"memory_bytes":{{json .MemTotal}},"architecture":{{json .Architecture}},"os_type":{{json .OSType}}}'],
        capture_output=True, text=True, check=True, env=env)
    node_package = root / "work/codebuddy/node_modules/@tencent-ai/codebuddy-code/package.json"
    client = json.loads(node_package.read_text())
    requirements = folder / "requirements-execution-20261125.txt"
    with requirements.open("x") as stream:
        stream.write("\n".join(name + "==" + packages[name] for name in sorted(packages)) + "\n")
    record = {"phase": "actual_current_execution_environment_snapshot", "new_model_calls": 0,
        "new_original_grader_calls": 0, "python": sys.version, "host_system": platform.system(),
        "host_release": platform.release(), "host_architecture": platform.machine(),
        "docker_vm": json.loads(docker.stdout), "task_container_platform": "linux/amd64",
        "model_compute": "Remote authenticated verified-free hy4flash-free; no local model inference or GPU claim",
        "client": {"name": client["name"], "version": client["version"]},
        "installed_distributions": packages, "installed_distribution_count": len(packages),
        "older_analysis_lock": str(old.relative_to(root)), "older_analysis_distribution_count": len(recorded),
        "additional_current_distributions": sorted(set(packages) - set(recorded)),
        "older_lock_version_differences": {name: {"old": version, "current": packages.get(name)}
            for name, version in recorded.items() if packages.get(name) != version},
        "scope": "Observed whole execution environment, including optional and unused packages. This is not a fresh clean installation or a claim that every package is required. The earlier82-package clean analysis evidence describes its own older scope; current performance scripts import additional dependencies, so its success is not reused as current full environment validation."}
    path = folder / "execution-environment-20261125.json"
    with path.open("x") as stream:
        stream.write(json.dumps(record, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"installed_packages": len(packages), "old_analysis_packages": len(recorded),
        "additional": len(record["additional_current_distributions"]),
        "old_version_differences": record["older_lock_version_differences"], "docker_vm": record["docker_vm"],
        "new_model_calls": 0}), flush=True)


if __name__ == "__main__":
    main()
