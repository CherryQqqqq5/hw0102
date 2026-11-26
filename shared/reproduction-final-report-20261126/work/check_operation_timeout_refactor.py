import ast
import json
from pathlib import Path
import shutil
import subprocess
from types import SimpleNamespace

from minisweagent.exceptions import TimeExceeded


root = Path.cwd()
output = root / "work/report-prose-review-20261126/timeout-replay"
output.mkdir(parents=True, exist_ok=True)
before = root / "work/report-prose-review-20261126/controller-before.py.txt"
after = root / "work/hw0102-publish/shared/course_eval/controller.py"


def bounded_class(path):
    tree = ast.parse(path.read_text())
    node = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "BoundedTarget")
    scope = {"TimeExceeded": TimeExceeded}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), "exec"), scope)
    return scope["BoundedTarget"]


class LocalTarget:
    def __init__(self):
        self.calls = []

    def exec(self, command, *, cwd, timeout):
        self.calls.append(["exec", command, cwd, timeout])
        result = subprocess.run(command, shell=True, cwd=cwd, timeout=timeout,
                                capture_output=True, text=True, check=True)
        return result.stdout.strip()

    def upload_file(self, source, destination, *, timeout):
        self.calls.append(["upload", str(source), str(destination), timeout])
        shutil.copyfile(source, destination)
        return Path(destination).read_text()


source, destination = output / "source.txt", output / "destination.txt"
source.write_text("actual local copy\n")
results = []
for remaining, requested in ((20, 5), (4, 5), (3.99, 5), (50, 20)):
    for operation in ("exec", "upload"):
        observed = []
        for path in (before, after):
            target = LocalTarget()
            budget = SimpleNamespace(remaining=lambda: remaining)
            bounded = bounded_class(path)(target, budget)
            try:
                if operation == "exec":
                    value = bounded.exec("pwd", cwd=str(output), timeout=requested)
                elif requested == 20:
                    value = bounded.upload_file(source, destination)
                else:
                    value = bounded.upload_file(source, destination, timeout=requested)
                observed.append({"value": value, "calls": target.calls})
            except TimeExceeded as error:
                observed.append({"error": error.args, "calls": target.calls})
        assert observed[0] == observed[1], (operation, remaining, observed)
        if remaining < 4:
            assert not observed[1]["calls"] and "error" in observed[1]
        else:
            assert observed[1]["calls"][0][-1] == min(requested, int(remaining - 3))
        results.append({"operation": operation, "remaining": remaining,
                        "requested": requested, "same_behavior": True, "observed": observed[1]})

record = {"cases": results, "actual_local_subprocess_and_file_copy": True,
          "new_model_calls": 0, "vm_started": False}
(output.parent / "timeout-refactor-validation.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n")
print(json.dumps({"cases": len(results), "all_equal": True, "new_model_calls": 0}))
