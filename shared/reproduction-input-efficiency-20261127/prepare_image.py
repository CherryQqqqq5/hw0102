import argparse
import hashlib
import json
import os
import subprocess
import time
from pathlib import Path

from scripts.prepare_registry_export_tool import registry_tool_environment


ROOT = Path.cwd()
FOLDER = Path(__file__).parent.resolve()
DOCKER = ROOT / "work/vendor/docker/docker"


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def checked_body(body, digest):
    if "sha256:" + hashlib.sha256(body).hexdigest() != digest:
        raise RuntimeError("The retained registry object differs from its pinned digest")
    return json.loads(body)


def pin(task, folder):
    regctl = Path(os.environ.get("COURSE_REGCTL_BIN", str(ROOT / "work/vendor/bin/regctl")))
    tool_path = Path(os.environ.get("COURSE_REGCTL_RECORD", str(ROOT / "work/registry-tools/tool.json")))
    tool = json.loads(tool_path.read_text())
    if hashlib.sha256(regctl.read_bytes()).hexdigest() != tool["sha256"]:
        raise RuntimeError("The pinned registry tool changed")
    environment = registry_tool_environment(ROOT)
    if os.environ.get("COURSE_REGISTRY_HTTP_PROXY"):
        environment.update(HTTP_PROXY=os.environ["COURSE_REGISTRY_HTTP_PROXY"],
            HTTPS_PROXY=os.environ["COURSE_REGISTRY_HTTP_PROXY"])
    reference = "docker.io/" + task["image"]
    body = subprocess.check_output([str(regctl), "manifest", "get", reference,
        "--platform", "linux/amd64", "--format", "raw-body"], env=environment, timeout=120)
    manifest = json.loads(body)
    digest = "sha256:" + hashlib.sha256(body).hexdigest()
    config_body = subprocess.check_output([str(regctl), "blob", "get", reference,
        manifest["config"]["digest"]], env=environment, timeout=120)
    config = checked_body(config_body, manifest["config"]["digest"])
    if config["architecture"] != "amd64" or config["os"] != "linux":
        raise RuntimeError("The original scorer image must be Linux amd64")
    folder.mkdir(parents=True, exist_ok=False)
    (folder / "manifest.json").write_bytes(body)
    (folder / "config.json").write_bytes(config_body)
    record = {"task": task["id"], "tag": task["image"], "status": "pinned",
        "source": reference.rsplit(":", 1)[0] + "@" + digest, "manifest_digest": digest,
        "config_digest": manifest["config"]["digest"], "new_model_calls": 0,
        "compressed_layer_bytes": sum(row["size"] for row in manifest["layers"])}
    save(folder / "record.json", record)
    return record


def verify(folder, environment, *, imported=False):
    record = json.loads((folder / "record.json").read_text())
    manifest = checked_body((folder / "manifest.json").read_bytes(), record["manifest_digest"])
    config = checked_body((folder / "config.json").read_bytes(), manifest["config"]["digest"])
    reference = record["tag"] if imported else record["source"]
    inspected, = json.loads(subprocess.check_output([str(DOCKER), "image", "inspect", reference],
        env=environment, text=True, timeout=60))
    manifest_identity = (inspected["Id"] == record["manifest_digest"]
        and inspected.get("Descriptor", {}).get("digest") == record["manifest_digest"])
    config_identity = (inspected["Id"] == record["config_digest"]
        and (imported or record["source"].removeprefix("docker.io/") in
        [name.removeprefix("docker.io/") for name in inspected.get("RepoDigests", [])]))
    if (not (manifest_identity or config_identity)
            or inspected["RootFS"]["Layers"] != config["rootfs"]["diff_ids"]
            or inspected["Architecture"] != "amd64" or inspected["Os"] != "linux"):
        save(folder / "imported-image-inspect.json", inspected)
        raise RuntimeError("The actual Docker image differs from its original pinned manifest/config/layers")
    subprocess.run([str(DOCKER), "image", "tag", inspected["Id"], record["tag"]],
        env=environment, check=True, timeout=60)
    record.update(status="ready", image_id=inspected["Id"], actual_image_id=inspected["Id"],
        docker_endpoint=environment["DOCKER_HOST"],
        image_identity_rule="Pinned manifest, config and all uncompressed layer digests; actual Docker identity verified",
        preparation_route="Verified native-host OCI export/import" if imported else "Pinned daemon pull")
    save(folder / "record.json", record)
    return record


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", required=True)
    parser.add_argument("--pin-only", action="store_true")
    parser.add_argument("--verify-daemon", action="store_true")
    args = parser.parse_args()
    task, = [row for row in json.loads((FOLDER / "candidate-tasks.json").read_text())["selected"]
        if row["id"] == args.task and row["benchmark"] == "swe"]
    folder = FOLDER / "preparation" / task["id"]
    record = json.loads((folder / "record.json").read_text()) if folder.exists() else pin(task, folder)
    if args.pin_only:
        print(json.dumps(record), flush=True)
        return
    environment = os.environ | {"DOCKER_HOST": os.environ["COURSE_STUDY_DOCKER_HOST"],
        "DOCKER_CONFIG": str(ROOT / "work/docker-config")}
    started = time.monotonic()
    if not args.verify_daemon:
        with (folder / "pull.log").open("a") as log:
            subprocess.run([str(DOCKER), "pull", "--platform", "linux/amd64", record["source"]],
                env=environment, stdout=log, stderr=subprocess.STDOUT, timeout=3600, check=True)
    record = verify(folder, environment)
    print(json.dumps({"task": args.task, "status": record["status"], "image_id": record["image_id"],
        "elapsed_seconds": time.monotonic() - started}), flush=True)


if __name__ == "__main__":
    main()
