import argparse
import hashlib
import json
import shutil
import subprocess
import time
from pathlib import Path

from scripts.prepare_registry_export_tool import registry_tool_environment


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", default="django__django-11999")
    parser.add_argument("--attempt", type=int, default=0)
    args = parser.parse_args()
    if args.attempt < 0:
        raise ValueError("The preparation attempt must be nonnegative")
    root = Path.cwd()
    queue = root / "work/vmshare/performance75-dsh-hy4-v10"
    task, = [row for row in json.loads((queue / "tasks.json").read_text())["selected"]
             if row["id"] == args.task]
    stem = "django11999" if args.task == "django__django-11999" else args.task.replace("/", "-")
    if args.attempt:
        stem += "-preparation-r" + str(args.attempt)
    pinned = json.loads((queue / "environment-pins.json").read_text())["pins"][task["id"]]
    reference = "docker.io/" + task["image"].rsplit(":", 1)[0] + "@" + pinned
    destination = "ocidir://work/registry-tools/" + stem + ":baseline"
    binary = root / "work/vendor/bin/regctl"
    tool = json.loads((root / "work/registry-tools/tool.json").read_text())
    if hashlib.sha256(binary.read_bytes()).hexdigest() != tool["sha256"]:
        raise ValueError("The official download tool changed after verification")
    record_path = root / ("work/registry-tools/copy-" + stem + ".json")
    if record_path.exists():
        raise FileExistsError(record_path)
    manifest_body = subprocess.check_output([str(binary), "manifest", "get", reference, "--format", "raw-body"],
        env=registry_tool_environment(root), timeout=120)
    if "sha256:" + hashlib.sha256(manifest_body).hexdigest() != pinned:
        raise ValueError("The public registry manifest differs from the frozen digest")
    manifest = json.loads(manifest_body)
    layers = {row["digest"]: row["size"] for row in manifest.get("layers", [])}
    for child in manifest.get("manifests", []):
        body = subprocess.check_output([str(binary), "manifest", "get", reference.rsplit("@", 1)[0] + "@" + child["digest"],
            "--format", "raw-body"], env=registry_tool_environment(root), timeout=120)
        if "sha256:" + hashlib.sha256(body).hexdigest() != child["digest"]:
            raise ValueError("A public index child differs from its content digest")
        for layer in json.loads(body).get("layers", []):
            layers[layer["digest"]] = layer["size"]
    if not layers:
        raise ValueError("The pinned public image has no bounded layer inventory")
    expected_bytes = sum(layers.values())
    if shutil.disk_usage(root).free < expected_bytes + 8 * 1024**3:
        raise RuntimeError("Insufficient local workspace for one bounded verified image copy")
    record = {"status": "downloading", "source": reference, "destination": destination,
        "blob_cdn_route": "Only public Docker CDN hosts bypass the local proxy for this process; registry metadata remains proxied",
        "task": task["id"], "expected_image_id": pinned, "expected_compressed_bytes": expected_bytes,
        "tool_sha256": tool["sha256"], "new_model_calls": 0,
        "docker_daemon_or_proxy_reconfigured": False, "user_credentials_used": False}
    record_path.write_text(json.dumps(record, indent=2) + "\n")
    started = time.monotonic()
    try:
        with (root / ("work/registry-tools/copy-" + stem + ".log")).open("x") as log:
            copied = subprocess.run([str(binary), "image", "copy", reference, destination], cwd=root,
                env=registry_tool_environment(root), stdout=log, stderr=subprocess.STDOUT,
                check=True, timeout=10800)
        image = subprocess.check_output([str(binary), "image", "digest", destination], cwd=root,
            env=registry_tool_environment(root), text=True, timeout=30).strip()
        if image != pinned:
            raise ValueError("The downloaded OCI manifest differs from the frozen original identity")
        blobs = list((root / "work/registry-tools" / stem / "blobs/sha256").glob("*"))
        for blob in blobs:
            checksum = hashlib.sha256()
            with blob.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    checksum.update(chunk)
            if checksum.hexdigest() != blob.name:
                raise ValueError("A copied OCI blob differs from its content digest")
        record.update(status="ready_for_import", returncode=copied.returncode, manifest_digest=image,
                      verified_blobs=len(blobs), copied_bytes=sum(path.stat().st_size for path in blobs))
    except (subprocess.SubprocessError, ValueError, OSError) as exc:
        record.update(status="failed", error_type=type(exc).__name__, detail=str(exc))
        raise
    finally:
        record["wall_seconds"] = time.monotonic() - started
        record_path.write_text(json.dumps(record, indent=2) + "\n")
        print(json.dumps(record), flush=True)


if __name__ == "__main__":
    main()
