import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

from prepare_image import DOCKER, FOLDER, ROOT, checked_body, verify
from course_eval.resource_pool import ResourceLease


PROJECT = ROOT.parent
REGCTL = PROJECT / "bin/regctl"
tool = json.loads((PROJECT / "bin/regctl.json").read_text())
if hashlib.sha256(REGCTL.read_bytes()).hexdigest() != tool["sha256"]:
    raise RuntimeError("The actual native registry tool differs from its official pinned release")
environment = os.environ | {"HTTP_PROXY": "http://127.0.0.1:46671", "HTTPS_PROXY": "http://127.0.0.1:46671",
    "REGCTL_CONFIG": str(PROJECT / "preparation/regctl.json"), "DOCKER_CONFIG": str(ROOT / "work/docker-config"),
    "DOCKER_HOST": "unix://" + str(PROJECT / "guest/docker.sock")}
cache = Path(os.environ.get("COURSE_PREPARATION_CACHE", str(FOLDER / "oci-cache")))
tasks = json.loads((FOLDER / "candidate-tasks.json").read_text())["selected"]
for task in tasks:
    if task["benchmark"] != "swe":
        continue
    folder = FOLDER / "preparation" / task["id"]
    record = json.loads((folder / "record.json").read_text())
    if record["status"] == "ready":
        continue
    destination = "ocidir://" + str(cache) + ":" + task["id"]
    print(json.dumps({"task": task["id"], "stage": "native_copy", "new_model_calls": 0}), flush=True)
    with (folder / "native-copy.log").open("ab") as log:
        subprocess.run([str(REGCTL), "image", "copy", record["source"], destination], env=environment,
            stdout=log, stderr=subprocess.STDOUT, timeout=7200, check=True)
    manifest = checked_body((folder / "manifest.json").read_bytes(), record["manifest_digest"])
    checked_body((folder / "config.json").read_bytes(), manifest["config"]["digest"])
    index = json.loads((cache / "index.json").read_text())
    if record["manifest_digest"] not in {entry["digest"] for entry in index["manifests"]}:
        raise RuntimeError("The native OCI export does not contain the pinned original manifest")
    for blob in (cache / "blobs/sha256").iterdir():
        with blob.open("rb") as handle:
            actual = hashlib.file_digest(handle, "sha256").hexdigest()
        if actual != blob.name:
            raise RuntimeError("An original OCI blob differs from its content address")
    print(json.dumps({"task": task["id"], "stage": "verified_native_export_import"}), flush=True)
    with ResourceLease(FOLDER / "resources", exclusive=True, label="image-import-" + task["id"]), \
            (folder / "native-export.log").open("ab") as error, (folder / "native-load.log").open("ab") as log:
        producer = subprocess.Popen([str(REGCTL), "image", "export", destination, "--name", record["tag"]],
            env=environment, stdout=subprocess.PIPE, stderr=error)
        try:
            subprocess.run([str(DOCKER), "load"], env=environment, stdin=producer.stdout, stdout=log,
                stderr=subprocess.STDOUT, timeout=1800, check=True)
            producer.stdout.close()
            if producer.wait(timeout=30):
                raise RuntimeError("The verified native OCI export failed")
        finally:
            if producer.poll() is None:
                producer.kill()
                producer.wait(timeout=15)
        verified = verify(folder, environment, imported=True)
    print(json.dumps({"task": task["id"], "stage": "ready", "image_id": verified["image_id"]}), flush=True)
if cache.exists():
    shutil.rmtree(cache)
print(json.dumps({"stage": "all_swe_images_ready", "native_cache_removed": True, "new_model_calls": 0}), flush=True)
