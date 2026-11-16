import argparse
import base64
import json
import re
from pathlib import Path


HOME_PATH = re.compile(r"/Users/cherry[^\s\"'`<>\\]*")
PRIVATE_PEM = re.compile(r"-----BEGIN ([A-Z ]*PRIVATE KEY)-----.*?-----END \1-----", re.DOTALL)
SECRET = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----|\b(?:gh[pousr]_|github_pat_|sk-(?:proj-)?)[A-Za-z0-9_-]{30,}|\b(?:AKIA|ASIA)[A-Z0-9]{16}\b|\bAKID[A-Za-z0-9]{28,}")
PRIVATE = re.compile(r"@smail\.nju\.edu\.cn|huawei-modelarts|/sfs/yuning", re.IGNORECASE)
LOG_NAMES = {"trial.json", "result.json", "instruction.txt", "model.jsonl", "tools.jsonl", "verification.jsonl",
             "agent.json", "artifact.json", "candidate.patch", "grader.json", "report.json", "test_output.txt",
             "run_instance.log", "trial.log", "test-stdout.txt", "reward.txt", "checkout.json", "run-plan.json",
             "controller.jsonl", "final-verification.json", "execution-budget.json", "public-runtime.json", "recovery.json"}
MODEL_FIELDS = {"event", "time", "request_id", "attempt", "model", "system", "history", "schema", "error_type",
                "timeout_seconds", "returncode", "http_status", "protocol_commit", "transport",
                "provider_diagnostics", "call_id", "ok", "timeout", "response_body", "retry_after", "seconds",
                "request_model", "provider_model", "credit", "usage_records", "detail",
                "configured_max_output_tokens", "local_cli_errors"}
RESULT_FIELDS = {"type", "subtype", "is_error", "num_turns", "total_cost_usd", "usage", "result",
                 "structured_output", "duration_ms", "duration_api_ms"}


def sanitize_model(content):
    records = []
    for line in content.splitlines():
        original = json.loads(line)
        record = {key: value for key, value in original.items() if key in MODEL_FIELDS}
        if original["event"] == "response":
            payload = original["payload"]
            if isinstance(payload, list):
                safe = []
                for item in payload:
                    if item.get("type") == "result":
                        safe.append({key: value for key, value in item.items() if key in RESULT_FIELDS})
                    elif (item.get("type") in {"reasoning", "function_call", "model-usage"}
                          or (item.get("type") == "message" and item.get("role") == "assistant")
                          or any(key in item.get("providerData", {}) for key in ("model", "requestModelId", "rawUsage"))):
                        provider = item.get("providerData", {})
                        kept = {"type": item["type"], "role": item.get("role"), "status": item.get("status"),
                                     "providerData": {key: provider[key] for key in (
                                         "requestModelId", "requestModelName", "model", "messageId", "rawUsage",
                                         "conversationRequestId", "agent", "skipRun", "error") if key in provider}}
                        if item.get("type") == "function_call" and item.get("name") == "StructuredOutput":
                            kept.update({"name": item["name"], "arguments": item.get("arguments")})
                        safe.append(kept)
                record["payload"] = safe
            else:
                record["payload"] = payload
        elif original["event"] == "request" and "payload" in original:
            record["payload"] = original["payload"]
        elif original["event"] == "request_error" and "getaddrinfo ENOTFOUND wb.tencentbuddy.com" in original.get("stderr", ""):
            record["diagnostic"] = {"category": "name_resolution", "message": "getaddrinfo ENOTFOUND wb.tencentbuddy.com"}
        elif original["event"] == "request_error" and "429 额度已用尽" in original.get("stderr", ""):
            record["diagnostic"] = {"category": "quota_exhausted", "message": "429 额度已用尽"}
        records.append(json.dumps(record, ensure_ascii=False))
    return "\n".join(records) + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    files = 0
    for file in sorted(args.runs.rglob("*")):
        relative = file.relative_to(args.runs)
        if not file.is_file() or file.is_symlink():
            continue
        if {"starter", "grader-input", "_python", "_deps", "solution", "tests"}.intersection(relative.parts):
            continue
        if file.name not in LOG_NAMES and not {"candidate", "candidates"}.intersection(relative.parts):
            continue
        content = file.read_text(encoding="utf-8")
        if "candidates" in relative.parts:
            for name, record in json.loads(content)["files"].items():
                decoded = base64.b64decode(record.get("data", ""), validate=True).decode("utf-8", errors="replace")
                if SECRET.search(decoded) or PRIVATE.search(decoded) or HOME_PATH.search(decoded):
                    raise ValueError(f"Sensitive candidate requires review: {relative}: {name}")
        content = PRIVATE_PEM.sub("[REDACTED BENCHMARK PRIVATE KEY]", content)
        content = re.sub(r"-----BEGIN [A-Z ]*PRIVATE KEY-----", "[REDACTED PRIVATE KEY HEADER]", content)
        if file.name == "model.jsonl":
            content = sanitize_model(content)
        elif file.name == "agent.json":
            info = json.loads(content)["info"]
            content = json.dumps({"info": {key: info[key] for key in ("exit_status", "submission", "model_stats")
                                           if key in info}}, ensure_ascii=False, indent=2) + "\n"
        content = HOME_PATH.sub("[本机路径]", content)
        if SECRET.search(content) or PRIVATE.search(content):
            raise ValueError(f"Sensitive marker requires review: {relative}")
        if file.suffix == ".json":
            json.loads(content)
        elif file.suffix == ".jsonl":
            for line in content.splitlines():
                json.loads(line)
        destination = args.out / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(content, encoding="utf-8")
        files += 1
    print(json.dumps({"exported_files": files, "output": str(args.out)}))


if __name__ == "__main__":
    main()
