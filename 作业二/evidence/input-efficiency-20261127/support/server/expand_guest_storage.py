import json
import socket
import time

import guest_vm


state = json.loads(guest_vm.STATE.read_text())
if state["stage"] != "qualified_tcg_guest_small_container_only" or not state["restricted"]:
    raise RuntimeError("Only the qualified project guest may be expanded")
if guest_vm.ssh(state, "docker ps -q").stdout.strip():
    raise RuntimeError("An active task prevents disk maintenance")
folder = guest_vm.ROOT / "diagnostics" / ("disk-capacity-" + str(time.time_ns()))
folder.mkdir()
target_bytes = 48 * 1024**3


with socket.socket(socket.AF_UNIX) as connection:
    connection.settimeout(30)
    connection.connect(str(guest_vm.GUEST / "qmp.sock"))
    stream = connection.makefile("rwb")
    greeting = json.loads(stream.readline())
    if "QMP" not in greeting:
        raise RuntimeError("The owned socket is not a QMP endpoint")

    def command(name, arguments=None):
        request = {"execute": name}
        if arguments is not None:
            request["arguments"] = arguments
        stream.write((json.dumps(request) + "\n").encode())
        stream.flush()
        while line := stream.readline():
            response = json.loads(line)
            if "error" in response:
                raise RuntimeError(str(response["error"]))
            if "return" in response:
                return response["return"]
        raise RuntimeError("The project QMP connection closed without a response")

    command("qmp_capabilities")
    before = command("query-block")
    disk, = [entry["inserted"] for entry in before if entry.get("inserted", {}).get("file")
        == str(guest_vm.GUEST / "disk.qcow2")]
    old_bytes = disk["image"]["virtual-size"]
    if old_bytes != 16 * 1024**3:
        raise RuntimeError("The existing disk differs from its observed 16 GiB capacity")
    (folder / "before.json").write_text(json.dumps(before, indent=2) + "\n")
    command("block_resize", {"node-name": disk["node-name"], "size": target_bytes})
    after = command("query-block")

if guest_vm.ssh(state, "findmnt -no SOURCE /").stdout.strip() != "/dev/vda1":
    raise RuntimeError("The guest root partition differs from the verified device")
deadline = time.monotonic() + 30
while int(guest_vm.ssh(state, "blockdev --getsize64 /dev/vda").stdout) != target_bytes:
    if time.monotonic() > deadline:
        raise RuntimeError("The guest did not observe the enlarged virtual disk")
    time.sleep(1)
grown = guest_vm.ssh(state,
    "mkdir -p /var/lib/course-maintenance && TMPDIR=/var/lib/course-maintenance growpart /dev/vda 1",
    check=False)
partition_bytes = int(guest_vm.ssh(state, "blockdev --getsize64 /dev/vda1").stdout)
if partition_bytes < target_bytes - 256 * 1024**2:
    raise RuntimeError("Root partition expansion failed: " + grown.stdout + grown.stderr)
resized = guest_vm.ssh(state, "resize2fs /dev/vda1")
filesystem = guest_vm.ssh(state, "df -B1 --output=source,size,used,avail,pcent /").stdout
if int(filesystem.splitlines()[1].split()[1]) < 40 * 1024**3:
    raise RuntimeError("The root filesystem did not gain its required capacity")
result = {"status": "PASS", "before_virtual_bytes": old_bytes, "after_virtual_bytes": target_bytes,
    "qemu_pid": state["qemu_pid"], "same_process_cpu_memory_and_disk_path": True,
    "growpart": grown.stdout + grown.stderr, "resize2fs": resized.stdout + resized.stderr,
    "filesystem": filesystem, "after_qmp": after, "new_model_calls": 0}
(folder / "result.json").write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps({key: value for key, value in result.items() if key != "after_qmp"}), flush=True)
