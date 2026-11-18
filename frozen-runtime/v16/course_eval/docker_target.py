import json
import os
import subprocess
from pathlib import Path


class DockerTarget:
    def __init__(self, image: str, cwd: str | None, *, platform: str, memory_mb: int, cpus: int,
                 read_only_empty_dirs: tuple[str, ...] = (), read_only_mounts: tuple[tuple[str, str], ...] = (),
                 environment: dict[str, str] | None = None):
        host = os.environ["DOCKER_HOST"]
        if not host.startswith("unix://"):
            raise ValueError("The local runner requires an explicit Docker Unix socket")
        self.binary = os.environ["COURSE_DOCKER_BIN"]
        self.cwd = cwd or self.image_workdir(image)
        self.image = self.docker("image", "inspect", "--format", "{{.Id}}", image).stdout.strip()
        mounts = []
        for directory in read_only_empty_dirs:
            mounts.extend(("--tmpfs", f"{directory}:ro,noexec,nosuid,size=1m"))
        for source, destination in read_only_mounts:
            mounts.extend(("--mount", f"type=bind,source={source},target={destination},readonly"))
        for key, value in (environment or {}).items():
            mounts.extend(("--env", key + "=" + value))
        self.container = self.docker(
            "run", "-d", "--pull=never", "--platform", platform, "--network", "none",
            "--cpus", str(cpus), "--memory", f"{memory_mb}m", "--pids-limit", "512",
            "--security-opt", "no-new-privileges", *mounts, "--entrypoint", "/bin/sleep", "-w", self.cwd,
            self.image, "infinity",
        ).stdout.strip()
        try:
            result = self.exec("uname -s; uname -r; uname -v; uname -m", timeout=10)
            fields = result["stdout"].splitlines()
            if result["returncode"] or len(fields) != 4:
                raise RuntimeError(f"Failed to read the container environment: {result}")
            self.system_info = dict(zip(("system", "release", "version", "machine"), fields, strict=True))
            self.system_info.update(image=self.image, cwd=self.cwd, cpus=cpus, memory_mb=memory_mb,
                                    read_only_empty_dirs=list(read_only_empty_dirs),
                                    read_only_mounts=list(read_only_mounts), environment=environment or {})
        except BaseException:
            self.docker("rm", "-f", self.container)
            raise

    def docker(self, *args: str, timeout: int = 90, check: bool = True) -> subprocess.CompletedProcess:
        return subprocess.run([self.binary, *args], text=True, encoding="utf-8", errors="replace",
                              capture_output=True, timeout=timeout, check=check)

    def image_workdir(self, image: str) -> str:
        result = self.docker("image", "inspect", "--format", "{{json .Config.WorkingDir}}", image)
        return json.loads(result.stdout) or "/"

    def exec(self, command: str, *, cwd: str = "", timeout: int) -> dict:
        process = self.docker(
            "exec", "-w", cwd or self.cwd, "-e", "PAGER=cat", "-e", "PIP_PROGRESS_BAR=off",
            self.container, "timeout", "--kill-after=2s", f"{timeout}s", "bash", "-c", command,
            timeout=timeout + 12, check=False,
        )
        return {"stdout": process.stdout, "stderr": process.stderr, "returncode": process.returncode}

    def upload_tree(self, source: Path) -> None:
        self.docker("cp", str(source) + "/.", f"{self.container}:{self.cwd}")

    def upload_file(self, source: Path, destination: str, *, timeout: int = 20) -> None:
        self.docker("cp", str(source), f"{self.container}:{destination}", timeout=timeout)

    def download_file(self, name: str, destination: Path) -> bool:
        path = Path(name)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError(f"Unsafe artifact path: {name}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        result = self.docker("cp", f"{self.container}:{self.cwd}/{name}", str(destination), check=False)
        if result.returncode and "Could not find the file" in result.stderr:
            return False
        result.check_returncode()
        if destination.is_symlink() or not destination.is_file():
            raise ValueError(f"Artifact is not a regular file: {name}")
        return True

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        result = self.docker("rm", "-f", self.container, check=False)
        if result.returncode and exc_type is None:
            result.check_returncode()
