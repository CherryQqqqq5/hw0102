import argparse
import json
import shlex
from pathlib import Path

from course_eval.docker_target import DockerTarget


parser = argparse.ArgumentParser()
parser.add_argument("--out", type=Path, required=True)
args = parser.parse_args()
args.out.mkdir(parents=True, exist_ok=False)
image = "alexgshaw/llm-inference-batching-scheduler:20251031"
path = "/app/course-jsonlines-probe.jsonl"
old = f"python3 -m json.tool --json-lines {path} >/dev/null"
code = "import json,sys; from pathlib import Path; [json.loads(line) for name in sys.argv[1:] for line in Path(name).read_text().splitlines()]"
repaired = "python3 -c " + shlex.quote(code) + " " + path
records = []
with DockerTarget(image, "/app", platform="linux/amd64", memory_mb=1024, cpus=1) as target:
    for name, command in (
        ("runtime", "python3 --version"),
        ("write-valid", "printf '%s' " + shlex.quote('{"x":1}\n{"x":2}\n') + " > " + path),
        ("old-valid", old),
        ("repaired-valid", repaired),
        ("write-invalid", "printf '%s' " + shlex.quote('{"x":1}\nnot-json\n') + " > " + path),
        ("repaired-invalid", repaired),
    ):
        result = target.exec(command, timeout=10)
        records.append({"name": name, "command": command, **result})
        if name in {"runtime", "write-valid", "write-invalid"}:
            assert result["returncode"] == 0, result
    observed = {record["name"]: record for record in records}
    assert observed["old-valid"]["returncode"] == 1
    assert "closed file" in observed["old-valid"]["stderr"]
    assert observed["repaired-valid"]["returncode"] == 0
    assert observed["repaired-invalid"]["returncode"] == 1
    output = {"engineering_check": "pass", "formal_benchmark_trial": False, "model_requests": 0,
              "fixture": "two synthetic JSON Lines records, then one invalid record", "image": image,
              "records": records}
(args.out / "result.json").write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n")
print(json.dumps({"engineering_check": "pass", "runtime": observed["runtime"]["stdout"].strip(),
                  "exit_codes": [observed[name]["returncode"] for name in ("old-valid", "repaired-valid", "repaired-invalid")]}))
