import hashlib
import json
import subprocess
import sys
from pathlib import Path

from scripts import run_pinned_image_copy as frozen_copy

original_environment = frozen_copy.registry_tool_environment


def actual_client_environment(root):
    return original_environment(root) | {"GODEBUG": "http2client=0"}


frozen_copy.registry_tool_environment = actual_client_environment


if __name__ == "__main__":
    if sys.argv[1:] == ["--qualify-environment"]:
        root = Path.cwd()
        before, after = original_environment(root), frozen_copy.registry_tool_environment(root)
        changed = sorted(key for key in before.keys() | after.keys() if before.get(key) != after.get(key))
        if changed != ["GODEBUG"] or after["GODEBUG"] != "http2client=0":
            raise ValueError("The actual client environment changed outside the declared HTTP compatibility setting")
        binary = root / "work/vendor/bin/regctl"
        tool = json.loads((root / "work/registry-tools/tool.json").read_text())
        if hashlib.sha256(binary.read_bytes()).hexdigest() != tool["sha256"]:
            raise ValueError("The actual public registry client changed")
        subprocess.run([str(binary), "version"], env=frozen_copy.registry_tool_environment(root), check=True, capture_output=True)
        print(json.dumps({"actual_child_environment_changes": changed, "GODEBUG": after["GODEBUG"],
            "original_environment_other_fields_preserved": True, "actual_verified_regctl_startup": True,
            "new_model_calls": 0, "public_image_transfers_during_qualification": 0,
            "transport_completion_not_claimed": True}), flush=True)
    else:
        frozen_copy.main()
