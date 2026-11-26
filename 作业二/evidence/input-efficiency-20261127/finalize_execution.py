import hashlib
import json
import socket
from contextlib import closing
from pathlib import Path

import docker


ROOT = Path.cwd()
FOLDER = Path(__file__).parent.resolve()
PROJECT = ROOT.parent
phase_path = PROJECT / "guest/state.json"
phase = json.loads(phase_path.read_text())
if (phase["restricted"] is not True or phase["stage"] != "qualified_tcg_guest_small_container_only"
        or phase["task_execution_allowed"] is not True):
    raise RuntimeError("The actual guest must pass its final isolated task qualification first")
qualification = PROJECT / "qualification.json"
transport = json.loads(qualification.read_text())
if transport["qemu_pid"] != phase["qemu_pid"] or transport["restricted"] is not True:
    raise RuntimeError("The saved qualification belongs to a different guest process")
dsh = json.loads((FOLDER / "dsh-runtime.json").read_text())
if dsh["stage"] != "actual_python_sdk_import_passed":
    raise RuntimeError("The actual DSH runtime has not passed Python and SDK import")
endpoint = "unix://" + str(PROJECT / "guest/docker.sock")
with closing(docker.DockerClient(base_url=endpoint, timeout=60)) as client:
    info = client.info()
if info["NCPU"] != 4 or info["MemTotal"] < 7 * 1024**3:
    raise RuntimeError("The actual daemon resources differ from the registered environment")
free_socket = PROJECT / "hy4-relay.sock"
with socket.socket(socket.AF_UNIX) as connection:
    connection.settimeout(20)
    connection.connect(str(free_socket))
    connection.sendall(b'{"event":"info"}\n')
    free = json.loads(connection.makefile().readline())
expected = "bfc167075d229f101878a378e6c5f9a8c2b64463545dd5ffb3881d6417040915"
if free["client_version"] != "2.179.3" or free["client_sha256"] != expected or free["new_model_calls"] != 0:
    raise RuntimeError("The actual authenticated free client differs from the qualified fixed client")
record = {"status": "PASS", "scope": "actual isolated Docker transport, DSH import and authenticated client identity; task original graders admitted separately",
    "docker_id": info["ID"], "docker_endpoint": endpoint, "task_network": "none",
    "cpus": info["NCPU"], "memory_bytes": info["MemTotal"], "guest_state_path": str(phase_path),
    "qualification_sha256": hashlib.sha256(qualification.read_bytes()).hexdigest(),
    "dsh_runtime_guest_path": dsh["guest_path"], "free_client_socket": str(free_socket),
    "free_client_entry": str(FOLDER / "runtime/course_eval/remote_codebuddy.py"),
    "free_client_sha256": free["client_sha256"], "free_client_version": free["client_version"],
    "fee_rule": "Actual fresh zero-credit receipt for each generation; stop on unknown or nonzero", "new_model_calls": 0}
path = FOLDER / "execution.json"
if path.exists() and json.loads(path.read_text()) != record:
    raise RuntimeError("A different execution environment is already registered")
path.write_text(json.dumps(record, indent=2) + "\n")
print(json.dumps(record), flush=True)
