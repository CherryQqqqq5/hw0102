import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile


MODES = ("--setup-show", "--setup-only", "--setup-plan")
SCENARIOS = (
    ("default_ascii_bytes", b"north-star", None, None),
    ("default_non_ascii_bytes", b"\x03\x9e\xff", None, None),
    ("default_string", "public-alpha", None, None),
    ("default_integer", 23, None, None),
    ("explicit_id", 17, "['visible-token']", "visible-token"),
    ("callable_id", 11, "lambda value: 'mapped-%d' % (value * 3)", "mapped-33"),
)
TRANSCRIPT = Path("/course-public-setup-repr-processes.json")


def source(value, ids):
    if ids is None:
        return ("import pytest\n\n@pytest.mark.parametrize('public_param', [" + repr(value)
                + "])\ndef test_safe(public_param):\n    pass\n")
    return ("import pytest\n\n@pytest.fixture(params=[" + repr(value) + "], ids=" + ids
            + ")\ndef public_param(request):\n    return request.param\n\n"
            + "def test_safe(public_param):\n    pass\n")


rows, processes = [], []
with tempfile.TemporaryDirectory(prefix="course-public-repr-", dir="/") as workspace:
    for name, value, ids, label in SCENARIOS:
        expected = repr(value if ids is None else label)
        for mode in MODES:
            folder = Path(workspace) / (name + mode)
            folder.mkdir()
            test = folder / "test_public_safe_repr.py"
            test.write_text(source(value, ids), encoding="utf-8")
            command = [sys.executable, "-bb", "-m", "pytest", str(test), mode,
                       "-q", "--color=no", "--basetemp", str(folder / "pytest-basetemp")]
            environment = os.environ.copy()
            environment["PYTHONPATH"] = "/testbed/src" + os.pathsep + environment.get("PYTHONPATH", "")
            environment["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
            environment["PYTEST_ADDOPTS"] = ""
            try:
                result = subprocess.run(command, cwd=str(folder), env=environment,
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                        universal_newlines=True, timeout=20)
                stdout, stderr, returncode = result.stdout, result.stderr, result.returncode
                rendered = {}
                for line in stdout.splitlines():
                    match = re.match(r"^\s*(SETUP|TEARDOWN)\s+F\s+public_param(\[.*\])\s*$", line)
                    if match:
                        rendered.setdefault(match.group(1), []).append(match.group(2))
                token = "[" + expected + "]"
                passed = (returncode == 0 and rendered.get("SETUP") == [token]
                          and rendered.get("TEARDOWN") == [token]
                          and "BytesWarning" not in stdout + stderr)
                row = {"scenario": name, "mode": mode, "expected": token,
                       "rendered": rendered, "returncode": returncode, "passed": passed,
                       "stdout_sha256": hashlib.sha256(stdout.encode()).hexdigest(),
                       "stderr_sha256": hashlib.sha256(stderr.encode()).hexdigest()}
                process = {"scenario": name, "mode": mode, "command": command,
                           "cwd": str(folder), "returncode": returncode,
                           "stdout": stdout, "stderr": stderr}
            except subprocess.TimeoutExpired as error:
                row = {"scenario": name, "mode": mode, "expected": "[" + expected + "]",
                       "passed": False, "error_type": "TimeoutExpired"}
                process = {"scenario": name, "mode": mode, "command": command,
                           "cwd": str(folder), "error_type": "TimeoutExpired", "detail": str(error)}
            rows.append(row)
            processes.append(process)

TRANSCRIPT.write_text(json.dumps({"actual_processes": processes}, ensure_ascii=True, indent=2) + "\n")
passed = len(rows) == 18 and all(row["passed"] for row in rows)
print(json.dumps({"passed": passed, "total": len(rows), "cases": rows,
    "actual_cli_transcript": str(TRANSCRIPT),
    "scope": "Self-chosen values under actual Python -bb CLI in three setup modes. Default bytes/string/integer and explicit/callable fixture ids use one safe repr display contract. Builtin pytest plugins are used; third-party plugin autoload is disabled only for these isolated public cases. No hidden fixtures or expected production patch."}))
raise SystemExit(0 if passed else 1)
