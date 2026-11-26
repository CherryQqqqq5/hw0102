import argparse
import hashlib
import json
import os
import subprocess
from contextlib import closing
from pathlib import Path

import docker


ROOT = Path.cwd()
FOLDER = Path(__file__).parent.resolve()
PROJECT = ROOT.parent
ENDPOINT = "unix://" + str(PROJECT / "guest/docker.sock")
ENV = os.environ | {"DOCKER_HOST": ENDPOINT, "DOCKER_CONFIG": str(ROOT / "work/docker-config")}
DOCKER = ROOT / "work/vendor/docker/docker"
parser = argparse.ArgumentParser()
parser.add_argument("--language", choices=("javascript", "python", "cpp", "all"), default="javascript")
args = parser.parse_args()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def digest(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


with closing(docker.DockerClient(base_url=ENDPOINT, timeout=240)) as client:
    info = client.info()
    if info["NCPU"] != 4 or info["MemTotal"] < 7 * 1024**3:
        raise RuntimeError("The actual guest differs from the registered resources")
    source = ROOT / "work/vmshare/dsh-linux-runtime"
    try:
        volume = client.volumes.get("course-dsh-runtime-20261126")
    except docker.errors.NotFound:
        volume = client.volumes.create(name="course-dsh-runtime-20261126",
            labels={"course_project": str(PROJECT)})
        volume.reload()
    if volume.attrs["Labels"]["course_project"] != str(PROJECT):
        raise RuntimeError("The DSH volume belongs to another project")
    record_path = FOLDER / "dsh-runtime.json"
    if not record_path.exists():
        qualification = json.loads((PROJECT / "qualification.json").read_text())
        container = client.containers.create(qualification["qualification_image_id"],
            entrypoint="/bin/busybox", command=["sleep", "1800"], network_mode="none",
            volumes={volume.name: {"bind": "/opt/course-harness", "mode": "rw"}},
            mem_limit="512m", nano_cpus=10**9, labels={"course_project": str(PROJECT)})
        try:
            container.start()
            with (FOLDER / "dsh-stage.log").open("ab") as log:
                subprocess.run([str(DOCKER), "cp", str(source) + "/.",
                    container.id + ":/opt/course-harness"], env=ENV, stdout=log,
                    stderr=subprocess.STDOUT, timeout=900, check=True)
        finally:
            container.remove(force=True)
        save(record_path, {"stage": "copied_not_yet_import_qualified", "volume": volume.name,
            "guest_path": volume.attrs["Mountpoint"], "source": str(source), "new_model_calls": 0})
    record = json.loads(record_path.read_text())
    if record["guest_path"] != volume.attrs["Mountpoint"]:
        raise RuntimeError("The actual DSH runtime mount changed")
    candidate = json.loads((FOLDER / "candidate-tasks.json").read_text())
    for task in candidate["selected"]:
        if task["benchmark"] != "aider" or (args.language != "all" and task["stratum"] != args.language):
            continue
        image = client.images.get("nju-course-aider:" + task["stratum"])
        if image.attrs["Architecture"] != "amd64" or image.attrs["Os"] != "linux":
            raise RuntimeError("An Aider image uses a different platform")
        save(FOLDER / "preparation" / task["id"] / "record.json", {"status": "ready",
            "task": task["id"], "image_id": image.id, "architecture": "amd64",
            "dockerfile_sha256": digest(FOLDER / "cpp-image/Dockerfile" if task["stratum"] == "cpp"
                else ROOT / "work/vmshare/aider/aider.Dockerfile"),
            "docker_id": info["ID"], "new_model_calls": 0})
    image = client.images.get("nju-course-aider:javascript")
    command = "timeout 90 /opt/course-harness/python/bin/python3 -c 'import sys,deepseek_harness; print(sys.version); print(deepseek_harness.__file__)'"
    checked = client.containers.run(image.id, ["bash", "-lc", command],
        network_mode="none", environment={"PYTHONPATH": "/opt/course-harness/lib"},
        volumes={volume.name: {"bind": "/opt/course-harness", "mode": "ro"}}, remove=True,
        mem_limit="1g", nano_cpus=10**9)
    record.update(stage="actual_python_sdk_import_passed", import_stdout=checked.decode(),
        core_sha256={str(path.relative_to(source)): digest(path) for path in
            (source / "python/bin/python3.13", source / "lib/deepseek_harness/__init__.py")})
    save(record_path, record)
print(json.dumps({"status": "PASS", "dsh_runtime": record["guest_path"], "new_model_calls": 0}), flush=True)
