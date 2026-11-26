import hashlib
import json
import re
import shlex
import time
from pathlib import Path


LOG_ROOT = "/course-tool-output"
KEY_LINE = re.compile(r"^\s*(?:def |class |export |function |(?:PASS|FAIL|ERROR|OK|FAILED)\b|"
    r"Ran \d+|Tests?:|Test Suites:|\S+?:\d+:)")


def digest_output(text, path):
    middle = []
    used = 0
    for line in text[1200:-1200].splitlines():
        if KEY_LINE.match(line) and used + len(line) + 1 <= 1200:
            middle.append(line)
            used += len(line) + 1
    return (f"Full original output: {path} ({len(text)} characters). "
        "Read selected lines with sed or grep; the original command need not be rerun.\n"
        + text[:1200] + "\n[... selected lines ...]\n" + "\n".join(middle)
        + "\n[... output tail ...]\n" + text[-1200:])


class ToolOutput:
    def __init__(self, directory, target, policy):
        if policy not in {"archive", "digest"}:
            raise ValueError("Unknown tool output policy")
        self.directory, self.target, self.policy = Path(directory), target, policy
        self.counter = 0
        self.ready = False

    def project(self, message, outputs):
        actions = message["extra"]["actions"]
        result = []
        for action, output in zip(actions, outputs, strict=True):
            command = action.get("command")
            text = output["output"]
            if (not command or len(text) <= 6000 or LOG_ROOT in command
                    or "<MSWEA_MULTIMODAL_CONTENT>" in text):
                result.append(output)
                continue
            started = time.monotonic()
            if not self.ready:
                initialized = self.target.exec("mkdir -p " + shlex.quote(LOG_ROOT), timeout=10)
                if initialized["returncode"]:
                    raise RuntimeError("Cannot prepare the task's tool-output directory")
                self.directory.mkdir(exist_ok=True)
                self.ready = True
            self.counter += 1
            name = f"output-{self.counter:04d}.txt"
            local = self.directory / name
            local.write_text(text)
            remote = LOG_ROOT + "/" + name
            self.target.upload_file(local, remote, timeout=20)
            compact = self.policy == "digest" and output["returncode"] == 0
            shown = digest_output(text, remote) if compact else text + "\nFull original output: " + remote
            record = {"call_id": action.get("tool_call_id"), "policy": self.policy,
                "returncode": output["returncode"], "original_characters": len(text),
                "presented_characters": len(shown), "projection_applied": compact,
                "log_path": remote, "sha256": hashlib.sha256(local.read_bytes()).hexdigest(),
                "archive_seconds": time.monotonic()-started}
            with (self.directory / "index.jsonl").open("a") as handle:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            result.append(output | {"output": shown})
        return result


def environment_context(target, directory, scope):
    python = (scope or {}).get("python", "python3")
    source = ("import json,os,sys; print(json.dumps({'cwd':os.getcwd(),'python':sys.executable,"
        "'version':sys.version.split()[0],'test_entry':"
        "'tests/runtests.py' if os.path.isfile('tests/runtests.py') else "
        "'/aider/benchmark/npm-test.sh' if os.path.isfile('/aider/benchmark/npm-test.sh') else "
        "'python -m pytest' if os.path.isdir('testing') else 'see task and visible project files'}))")
    probe = target.exec(shlex.quote(python) + " -c " + shlex.quote(source), timeout=15)
    if probe["returncode"]:
        raise RuntimeError("The declared task interpreter is unavailable")
    facts = json.loads(probe["stdout"])
    if facts["cwd"] != target.cwd or not facts["python"].startswith("/"):
        raise RuntimeError("The actual task environment differs from its declared location")
    Path(directory, "shared-environment.json").write_text(json.dumps(facts, indent=2) + "\n")
    return (f"\nVerified task environment: cwd={facts['cwd']}; Python={facts['python']} "
        f"({facts['version']}); visible test entry={facts['test_entry']}. "
        "Use this interpreter for repository tests. Start with tests related to the changed behavior; "
        "expand testing when a specific coverage gap remains.\n")
