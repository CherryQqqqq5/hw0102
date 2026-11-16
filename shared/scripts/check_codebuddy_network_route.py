import json
import subprocess
from pathlib import Path

from course_eval.agent import CodeBuddyModel, RunLimits


model = CodeBuddyModel(Path("work"), RunLimits(), "{{output}}")
fixed_environment = model.process_environment()
old_environment = {key: value for key, value in fixed_environment.items()
                   if key.lower() not in {"http_proxy", "https_proxy", "all_proxy"}}
command = ["curl", "--head", "--silent", "--show-error", "--connect-timeout", "3", "--max-time", "6",
           "--output", "/dev/null", "--write-out",
           '{"http_code":"%{http_code}","peer":"%{remote_ip}","lookup_seconds":%{time_namelookup},"total_seconds":%{time_total}}',
           "https://wb.tencentbuddy.com"]
records = []
for repeat in range(1, 6):
    for name, environment in (("old_proxy_removed", old_environment), ("fixed_proxy_preserved", fixed_environment)):
        process = subprocess.run(command, env=environment, capture_output=True, text=True, timeout=8, check=False)
        records.append({"repeat": repeat, "environment": name, "returncode": process.returncode,
                        "result": json.loads(process.stdout), "error": process.stderr.strip()})
result = {"destination": "https://wb.tencentbuddy.com", "method": "HEAD", "authenticated": False,
          "model_requests": 0, "records": records,
          "scope": "Real HTTP connectivity under old and fixed child environments; no inference or billing claim"}
Path("work/codebuddy-network-route-check.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
print(json.dumps(result, ensure_ascii=False))
fixed = [row for row in records if row["environment"] == "fixed_proxy_preserved"]
assert all(row["returncode"] == 0 and row["result"]["peer"] == "127.0.0.1"
           and row["result"]["http_code"] == "404" for row in fixed)
