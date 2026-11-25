import hashlib
import json
from pathlib import Path
import subprocess
import sys

from scripts import run_pinned_image_copy as frozen_copy
from scripts.prepare_registry_export_tool import registry_tool_environment


def client_environment(root):
    return registry_tool_environment(root) | {"GODEBUG": "http2client=0", "NO_PROXY": "localhost,127.0.0.1,::1"}


def qualify(root):
    before, after = registry_tool_environment(root), client_environment(root)
    changed = sorted(key for key in before.keys() | after.keys() if before.get(key) != after.get(key))
    if changed != ["GODEBUG", "NO_PROXY"] or after["GODEBUG"] != "http2client=0":
        raise ValueError("Only the declared child HTTP compatibility and CDN route may change")
    binary = root / "work/vendor/bin/regctl"
    expected = json.loads((root / "work/registry-tools/tool.json").read_text())["sha256"]
    with binary.open("rb") as stream:
        if hashlib.file_digest(stream, "sha256").hexdigest() != expected:
            raise ValueError("The already verified registry client changed")
    subprocess.run([str(binary), "version"], env=after, capture_output=True, check=True, timeout=15)
    return {"actual_child_environment_changes": changed, "regctl_sha256": expected,
        "new_model_calls": 0, "global_proxy_or_daemon_modified": False,
        "note": "Caller owns the original per-image preparation lock;this driver does not take a second lock"}


def main():
    root = Path.cwd()
    qualified = qualify(root)
    if sys.argv[1:] == ["--qualify-environment"]:
        print(json.dumps(qualified), flush=True)
        return
    if len(sys.argv) != 5 or sys.argv[1] != "--task" or sys.argv[3] != "--attempt":
        raise ValueError("Use --task TASK --attempt N")
    task, attempt = sys.argv[2], int(sys.argv[4])
    if attempt < 0:
        raise ValueError("A public preparation attempt must be nonnegative")
    stem = "django11999" if task == "django__django-11999" else task.replace("/", "-")
    if ".." in stem or not stem:
        raise ValueError("Invalid original task identity")
    stem += "-preparation-r" + str(attempt) if attempt else ""
    record = root / ("work/registry-tools/copy-" + stem + ".json")
    if record.exists():
        raise FileExistsError("Preserve the original preparation record")
    frozen_copy.registry_tool_environment = client_environment
    try:
        frozen_copy.main()
    finally:
        if record.exists():
            actual = json.loads(record.read_text())
            actual["blob_cdn_route"] = "This registry child uses the existing local proxy for public metadata and CDN blobs;no global settings changed"
            actual["route_qualification"] = qualified
            record.write_text(json.dumps(actual, indent=2) + "\n")


if __name__ == "__main__":
    main()
