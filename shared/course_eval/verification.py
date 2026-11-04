import shlex
from dataclasses import dataclass
from pathlib import PurePosixPath


@dataclass(frozen=True)
class PublicCheck:
    check_id: str
    source_quote: str
    command: str
    dependencies: tuple[str, ...]

    def validate(self, instruction: str) -> None:
        if not self.source_quote or self.source_quote not in instruction:
            raise ValueError(f"Missing task-visible source for {self.check_id}")
        if not self.command or not self.dependencies:
            raise ValueError(f"Missing command or dependencies for {self.check_id}")
        for name in self.dependencies:
            path = PurePosixPath(name)
            if path.is_absolute() or ".." in path.parts or not path.name:
                raise ValueError(f"Unsafe check dependency: {name}")


@dataclass(frozen=True)
class Evidence:
    state: str
    returncode: int | None = None
    snapshot: str | None = None


class VerificationState:
    def __init__(self, checks: tuple[PublicCheck, ...], *, invalidate: bool):
        self.checks = {check.check_id: check for check in checks}
        self.commands = {check.command: check for check in checks}
        if len(self.checks) != len(checks) or len(self.commands) != len(checks):
            raise ValueError("Public check ids and commands must be distinct")
        self.invalidate = invalidate
        self.evidence = {check_id: Evidence("pending") for check_id in self.checks}

    @staticmethod
    def snapshot(check: PublicCheck, target, timeout: int) -> str | None:
        paths = shlex.join(check.dependencies)
        output = target.exec(f"/usr/bin/sha256sum -- {paths}", timeout=timeout)
        return output["stdout"] if output["returncode"] == 0 else None

    def observe(self, check: PublicCheck, before: str | None, after: str | None, returncode: int) -> Evidence:
        if returncode != 0:
            result = Evidence("failed", returncode)
        elif self.invalidate and (before is None or after is None):
            result = Evidence("unknown", returncode)
        elif self.invalidate and before != after:
            result = Evidence("stale", returncode, before)
        else:
            result = Evidence("passed", returncode, after)
        self.evidence[check.check_id] = result
        return result

    def inspect(self, target, timeout: int) -> dict[str, Evidence]:
        if self.invalidate:
            for key, check in self.checks.items():
                previous = self.evidence[key]
                if previous.state == "passed" and self.snapshot(check, target, timeout) != previous.snapshot:
                    self.evidence[key] = Evidence("stale", previous.returncode, previous.snapshot)
        return self.evidence.copy()
