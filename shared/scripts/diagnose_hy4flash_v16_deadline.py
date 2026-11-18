import json
import os
import socket
import subprocess
from pathlib import Path
from statistics import median, quantiles
from urllib.parse import urlsplit


root = Path("work/vmshare/confirmation-hy4flash-free-v15")
latencies = []
for path in root.rglob("model.jsonl"):
    events = [json.loads(line) for line in path.read_text().splitlines()]
    requests = {event["request_id"]: event for event in events if event["event"] == "request"}
    for event in events:
        if event["event"] == "response":
            latencies.append(event["time"] - requests[event["request_id"]]["time"])
diagnostic = json.loads(Path("work/codebuddy-first-response-v15/diagnostic.json").read_text())
proxy = []
for name in ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy", "ALL_PROXY", "all_proxy"):
    if os.environ.get(name):
        value = urlsplit(os.environ[name])
        proxy.append({"variable": name, "scheme": value.scheme, "host": value.hostname, "port": value.port,
                      "credentials_present": bool(value.username or value.password)})
host = "wb.tencentbuddy.com"
addresses = sorted({record[4][0] for record in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)})
curl = subprocess.run(["curl", "--silent", "--show-error", "--max-time", "20", "--output", os.devnull,
                       "--write-out", "%{json}", "https://" + host], capture_output=True, text=True, check=True)
timing = json.loads(curl.stdout)
percentiles = quantiles(latencies, n=100)
result = {
    "phase": "DEBUG", "model_requests": 0, "previous_original_scores": 260,
    "completed_cli_responses": len(latencies), "latency_median_seconds": median(latencies),
    "latency_p95_seconds": percentiles[94], "latency_p99_seconds": percentiles[98],
    "latency_max_seconds": max(latencies), "responses_over_60_seconds": sum(value > 60 for value in latencies),
    "responses_over_150_seconds": sum(value > 150 for value in latencies),
    "prior_admission_floor_seconds": 60, "failed_call_available_seconds": diagnostic["effective_request_timeout_seconds"],
    "sdk_first_token_timeout_ms": 1200000, "outer_execution_limit_seconds": 600,
    "proxy_environment": proxy, "dns_addresses": addresses,
    "unauthenticated_http_read": {key: timing[key] for key in (
        "http_code", "time_namelookup", "time_connect", "time_appconnect", "time_starttransfer", "time_total")},
    "network_check_scope": "Current unauthenticated reachability only; no inference, credentials or historical root-cause claim",
    "confirmed_local_cause": "The adapter admitted a late request with only 73 seconds left while the SDK first-token deadline was 1200 seconds; outer timeout killed a still-waiting client before any response or billing",
    "unresolved_upstream_cause": "Client records cannot distinguish upstream queueing from historical network latency",
}
directory = Path("work/codebuddy-deadline-v16")
directory.mkdir(exist_ok=True)
(directory / "diagnostic.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
print(json.dumps(result, ensure_ascii=False))
