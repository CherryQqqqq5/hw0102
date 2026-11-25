import argparse
import json
import os
import selectors
import subprocess
import time
from pathlib import Path
from datetime import datetime, timezone


parser = argparse.ArgumentParser()
parser.add_argument("--cloud-only", action="store_true")
parser.add_argument("--output", type=Path)
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
output = args.output or root / "work/codebuddy-quota-probe"
output.mkdir(exist_ok=True)
environment = os.environ.copy()
environment["TMPDIR"] = str(root / "work/process-tmp")
environment["CODEBUDDY_DISABLE_COMPILE_CACHE"] = "1"
if args.cloud_only:
    environment["CODEBUDDY_DISABLE_BUILTIN_MODELS"] = "1"
command = [
    str(root / "work/codebuddy/node_modules/.bin/codebuddy"),
    "--print", "--input-format", "stream-json", "--output-format", "stream-json",
    "--tools", "", "--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}',
    "--setting-sources", "", "--settings", '{"disableAllHooks":true}',
    "--no-session-persistence",
]
request = {
    "type": "control_request",
    "request_id": "free-model-metadata-only",
    "request": {"subtype": "get_available_models"},
}
process = subprocess.Popen(
    command, cwd=output, env=environment, stdin=subprocess.PIPE,
    stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
)
started = time.monotonic()
try:
    if args.cloud_only:
        time.sleep(8)
    process.stdin.write(json.dumps(request) + "\n")
    process.stdin.flush()
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ)
    response = None
    while time.monotonic() - started < 45:
        if process.poll() is not None:
            raise RuntimeError(f"CodeBuddy metadata process exited: {process.returncode}")
        if not selector.select(timeout=1):
            continue
        line = process.stdout.readline()
        if not line:
            raise RuntimeError("CodeBuddy closed stdout before metadata response")
        event = json.loads(line)
        if event.get("type") != "control_response":
            raise RuntimeError(f"Unexpected metadata event type: {event.get('type')}")
        envelope = event["response"]
        if envelope.get("request_id") != request["request_id"]:
            raise RuntimeError("Metadata response request_id mismatch")
        if envelope.get("subtype") != "success":
            raise RuntimeError(f"Metadata control request failed: {envelope.get('subtype')}")
        response = envelope["response"]
        break
    if response is None:
        raise TimeoutError("CodeBuddy model metadata did not return within 45 seconds")
    models = response["rawModels"]
    if not isinstance(models, list):
        raise TypeError("rawModels must be a list")
    allowed = {
        "id", "name", "description", "descriptionEn", "descriptionZh", "labels",
        "credits", "credit", "price", "pricing",
        "free", "isFree", "freeQuota", "freeQuotaRemaining", "quota",
        "available", "disabled", "aliases", "relatedModels",
        "reasoning", "supportsReasoning", "onlyReasoning", "maxOutputTokens",
        "maxInputTokens", "supportsImages", "disabledMultimodal", "maxAllowedSize", "supportsToolCall",
    }
    selected = [
        {key: value for key, value in model.items() if key in allowed}
        | {"metadata_keys": sorted(model)}
        for model in models
        if "hy4" in str(model.get("id", "")).lower()
        or "hy4" in str(model.get("name", "")).lower()
    ]
    result = {
        "stage": "metadata_only", "model_generation_requests": 0,
        "observed_utc": datetime.now(timezone.utc).isoformat(),
        "builtins_disabled": args.cloud_only,
        "cli_version": "2.179.3", "models_count": len(models),
        "model_ids": [model["id"] for model in models],
        "available_models": [{key: value for key, value in model.items() if key in allowed} for model in models],
        "hy4_models": selected,
        "elapsed_seconds": round(time.monotonic() - started, 3),
    }
    filename = "cloud-model-metadata.json" if args.cloud_only else "model-metadata.json"
    (output / filename).write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    )
    print(json.dumps(result, ensure_ascii=False))
finally:
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
