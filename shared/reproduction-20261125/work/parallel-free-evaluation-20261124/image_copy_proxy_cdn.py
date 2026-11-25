import fcntl
import hashlib
import json
import subprocess
import sys
from pathlib import Path

from image_copy_http1 import actual_client_environment, frozen_copy


def proxy_environment(root):
    return actual_client_environment(root) | {"NO_PROXY": "localhost,127.0.0.1,::1"}


def qualify(root):
    before, after = actual_client_environment(root), proxy_environment(root)
    changed = sorted(key for key in before.keys() | after.keys() if before.get(key) != after.get(key))
    if changed != ["NO_PROXY"] or after["GODEBUG"] != "http2client=0":
        raise ValueError("Only the public CDN subprocess route may change")
    binary = root / "work/vendor/bin/regctl"
    expected = json.loads((root / "work/registry-tools/tool.json").read_text())["sha256"]
    if hashlib.sha256(binary.read_bytes()).hexdigest() != expected:
        raise ValueError("The verified registry client changed")
    subprocess.run([str(binary), "version"], env=after, capture_output=True, check=True, timeout=15)
    return {"actual_child_environment_changes": changed, "GODEBUG": after["GODEBUG"],
        "verified_regctl_sha256": expected, "global_proxy_or_daemon_changed": False,
        "new_model_calls": 0, "user_registry_credentials_used": False}


def main():
    root = Path.cwd()
    qualified = qualify(root)
    if sys.argv[1:] == ["--qualify-environment"]:
        print(json.dumps(qualified), flush=True)
        return
    if len(sys.argv) != 5 or sys.argv[1] != "--task" or sys.argv[3] != "--attempt":
        raise ValueError("Use --task TASK --attempt N; no model or queue controls are accepted")
    task, attempt = sys.argv[2], int(sys.argv[4])
    base = "django11999" if task == "django__django-11999" else task.replace("/", "-")
    if attempt <= 0 or "/" in base or ".." in base:
        raise ValueError("An explicit positive preparation attempt is required")
    pool = root / "work/parallel-free-evaluation-20261124/resources"
    record = root / f"work/registry-tools/copy-{base}-preparation-r{attempt}.json"
    with (pool / f"image-{base}.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if record.exists():
            raise FileExistsError(record)
        frozen_copy.registry_tool_environment = proxy_environment
        try:
            frozen_copy.main()
        finally:
            if record.exists():
                result = json.loads(record.read_text())
                result["blob_cdn_route"] = "This registry subprocess uses the existing local proxy for metadata and public CDN blobs; no global settings changed"
                result["route_qualification"] = qualified
                record.write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
