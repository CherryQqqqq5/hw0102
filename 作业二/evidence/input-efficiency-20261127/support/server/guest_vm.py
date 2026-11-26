import argparse
import base64
import hashlib
import io
import json
import os
import shutil
import socket
import subprocess
import time
from pathlib import Path

ROOT = Path('[server-project]')
if Path(__file__).resolve().parent != ROOT or os.getuid() == 0:
    raise RuntimeError('Use the isolated non-root project')
os.umask(0o077)
GUEST = ROOT / 'guest'
STATE = GUEST / 'state.json'
QEMU = ROOT / 'sysroot/usr/bin/qemu-system-x86_64'
QIMG = ROOT / 'sysroot/usr/bin/qemu-img'
ENV = {'PATH': '/usr/bin:/bin', 'LC_ALL': 'C.UTF-8',
    'LD_LIBRARY_PATH': f'{ROOT}/sysroot/usr/lib/x86_64-linux-gnu:{ROOT}/sysroot/lib/x86_64-linux-gnu',
    'QEMU_MODULE_DIR': str(ROOT / 'sysroot/usr/lib/x86_64-linux-gnu/qemu'),
    'TMPDIR': str(ROOT / 'cache'), 'PYTHONDONTWRITEBYTECODE': '1'}


def run(args, *, timeout=120, check=True):
    result = subprocess.run(list(map(str, args)), env=ENV, capture_output=True, text=True, timeout=timeout)
    if check and result.returncode:
        raise RuntimeError(f'Command exit {result.returncode}: {result.stderr[-1500:]}')
    return result


def save(value):
    STATE.write_text(json.dumps(value, indent=2) + '\n')


def ssh(state, command, *, timeout=120, check=True):
    args = ssh_base(state) + ['root@127.0.0.1', command]
    return run(args, timeout=timeout, check=check)


def ssh_base(state):
    return ['ssh', '-F', '/dev/null', '-i', str(GUEST / 'id_ed25519'), '-p', str(state['ssh_port']),
        '-o', 'BatchMode=yes', '-o', 'IdentitiesOnly=yes', '-o', 'IdentityAgent=none',
        '-o', 'StrictHostKeyChecking=accept-new', '-o', f'UserKnownHostsFile={GUEST}/known_hosts',
        '-o', 'GlobalKnownHostsFile=/dev/null', '-o', 'ConnectTimeout=5']


def write_seed():
    import pycdlib

    public = (GUEST / 'id_ed25519.pub').read_text().strip()
    config = {'disable_root': False, 'ssh_pwauth': False,
        'users': [{'name': 'root', 'lock_passwd': True, 'ssh_authorized_keys': [public]}],
        'package_update': True, 'packages': ['docker.io', 'ca-certificates', 'curl', 'python3-minimal'],
        'write_files': [{'path': '/etc/ssh/sshd_config.d/01-course.conf', 'permissions': '0644',
            'content': 'PasswordAuthentication no\nPermitRootLogin prohibit-password\n'},
            {'path': '/etc/systemd/system/docker.service.d/override.conf', 'permissions': '0644',
             'content': '[Service]\nExecStart=\nExecStart=/usr/bin/dockerd -H unix:///var/run/docker.sock -H tcp://127.0.0.1:2375 --tls=false --containerd=/run/containerd/containerd.sock\n'}],
        'runcmd': [['bash', '-ec', 'systemctl daemon-reload; systemctl enable containerd docker; '
            'systemctl restart containerd docker; docker pull busybox:1.36.1; '
            'docker version > /var/lib/course-docker-version.txt; touch /var/lib/course-bootstrap-ready']]}
    iso = pycdlib.PyCdlib()
    iso.new(interchange_level=3, joliet=3, rock_ridge='1.09', vol_ident='CIDATA')
    data = {'user-data': '#cloud-config\n' + json.dumps(config),
        'meta-data': 'instance-id: course-input-efficiency-20261126-virtio\nlocal-hostname: course-input-guest\n',
        'network-config': json.dumps({'version': 2, 'ethernets': {'course': {
            'match': {'macaddress': '52:54:00:12:34:56'}, 'set-name': 'eth0', 'dhcp4': True}}})}
    for index, (name, value) in enumerate(data.items()):
        content = value.encode()
        iso.add_fp(io.BytesIO(content), len(content), iso_path=f'/DATA{index}.;1',
            rr_name=name, joliet_path='/' + name)
    iso.write(str(GUEST / 'seed.iso'))
    iso.close()


def prepare():
    if STATE.exists():
        raise RuntimeError('Existing guest state: inspect it rather than replacing this VM')
    host = json.loads((ROOT / 'host-preparation.json').read_text())
    if host['stage'] != 'host_tools_and_base_image_ready':
        raise RuntimeError('The project tool/image bootstrap has not completed')
    key = GUEST / 'id_ed25519'
    run(['ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-C', 'course-project-guest', '-f', key])
    write_seed()
    run([QIMG, 'create', '-f', 'qcow2', '-F', 'qcow2', '-b', GUEST / 'ubuntu-jammy-base.qcow2', GUEST / 'disk.qcow2', '16G'])
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        port = probe.getsockname()[1]
    state = {'stage': 'prepared', 'ssh_port': port, 'accelerator': 'tcg', 'cpus': 2, 'memory_mib': 4096,
        'host_shared_directories': [], 'provider_credentials_copied': False}
    save(state)
    return state


def alive(pid):
    stat = Path(f'/proc/{pid}/stat')
    return stat.exists() and stat.read_text().split()[2] != 'Z'


def start(state, restricted):
    if state.get('qemu_pid') and alive(state['qemu_pid']):
        raise RuntimeError('This project guest is already running')
    qmp = GUEST / 'qmp.sock'
    if qmp.exists():
        qmp.unlink()
    network = f'user,id=n0,hostfwd=tcp:127.0.0.1:{state["ssh_port"]}-:22'
    if restricted:
        network += ',restrict=on'
    argv = [str(QEMU), '-no-user-config', '-nodefaults', '-display', 'none', '-monitor', 'none',
        '-machine', 'q35,vmport=off,dump-guest-core=off', '-accel', 'tcg,thread=multi',
        '-cpu', 'max', '-smp', str(state['cpus']), '-m', str(state['memory_mib']),
        '-L', str(ROOT / 'sysroot/usr/share/qemu'), '-bios', str(ROOT / 'sysroot/usr/share/seabios/bios-256k.bin'),
        '-drive', f'file={GUEST}/disk.qcow2,format=qcow2,if=virtio,cache=writeback',
        '-drive', f'file={GUEST}/seed.iso,format=raw,if=virtio,readonly=on',
        '-smbios', 'type=1,serial=ds=nocloud',
        '-netdev', network, '-device', 'virtio-net-pci,netdev=n0,romfile=,mac=52:54:00:12:34:56',
        '-serial', f'file:{GUEST}/serial-{int(restricted)}.log',
        '-qmp', f'unix:{qmp},server=on,wait=off',
        '-sandbox', 'on,obsolete=deny,elevateprivileges=deny,spawn=deny,resourcecontrol=deny']
    with (GUEST / 'qemu.log').open('a') as log:
        process = subprocess.Popen(argv, env=ENV, stdin=subprocess.DEVNULL,
            stdout=log, stderr=log, start_new_session=True)
    state.update(qemu_pid=process.pid, qemu_argv=argv, restricted=restricted,
        stage='restricted_guest_started' if restricted else 'trusted_guest_bootstrap_only',
        boot_started_timestamp=time.time())
    state.pop('ssh_ready_seconds', None)
    save(state)
    wait_for_ssh(state)


def wait_for_ssh(state, timeout=900):
    started = time.monotonic()
    while time.monotonic() - started < timeout:
        if not alive(state['qemu_pid']):
            raise RuntimeError('QEMU exited; see guest/qemu.log')
        try:
            result = ssh(state, 'true', timeout=10, check=False)
        except subprocess.TimeoutExpired as exc:
            state.setdefault('boot_probe_timeouts', []).append({
                'time': time.time(), 'timeout_seconds': exc.timeout,
                'qemu_pid': state['qemu_pid'], 'event': 'ssh_probe_timeout'})
            save(state)
            time.sleep(5)
            continue
        if result.returncode == 0:
            state['ssh_ready_seconds'] = time.monotonic() - started
            save(state)
            return
        time.sleep(5)
    raise TimeoutError(f'No guest SSH within {timeout} seconds; original files/logs retained')


def bootstrap():
    if STATE.exists():
        state = json.loads(STATE.read_text())
        if state['stage'] != 'trusted_guest_bootstrap_only' or alive(state['qemu_pid']) or state.get('ssh_ready_seconds'):
            raise RuntimeError('Only a pre-SSH mechanical launch failure may reuse this initial guest')
        write_seed()
    else:
        state = prepare()
    start(state, restricted=False)
    started = time.monotonic()
    while time.monotonic() - started < 1800:
        if ssh(state, 'test -f /var/lib/course-bootstrap-ready', check=False).returncode == 0:
            state.update(stage='trusted_bootstrap_complete', bootstrap_wait_seconds=time.monotonic() - started)
            save(state)
            print(json.dumps(state), flush=True)
            return
        time.sleep(10)
    raise TimeoutError('Guest package bootstrap deadline; no model or original grader executed')


def restrict_and_qualify():
    state = json.loads(STATE.read_text())
    if state['stage'] != 'trusted_bootstrap_complete':
        raise RuntimeError('The completed trusted bootstrap is required')
    small_image = json.loads((ROOT / 'small-image.json').read_text())
    if small_image['purpose'] != 'Project-owned engine qualification rootfs; not an official benchmark image':
        raise RuntimeError('The explicit small-image provenance is required')
    image_reference = small_image['image']
    ssh(state, 'sync; poweroff', check=False)
    deadline = time.monotonic() + 180
    while alive(state['qemu_pid']) and time.monotonic() < deadline:
        time.sleep(2)
    if alive(state['qemu_pid']):
        raise RuntimeError('Own new guest has not shut down; no unrelated process will be signalled')
    start(state, restricted=True)
    (ROOT / 'host-only-sentinel').write_text('not mounted into the guest\n')
    result = ssh(state, 'set -e; test ! -e [server-project]/host-only-sentinel; '
        'docker version; ss -ltn | grep "127.0.0.1:2375"', check=True)
    (GUEST / 'docker-version.txt').write_text(result.stdout)
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        listener.listen()
        port = listener.getsockname()[1]
        probe = 'import socket; s=socket.socket(); s.settimeout(3); code=s.connect_ex(("10.0.2.2",' + str(port) + ')); assert code!=0, "guest can contact host"; print(code)'
        blocked = ssh(state, 'python3 -c ' + __import__('shlex').quote(probe))
    cpu = 'import time,json; t=time.monotonic(); v=sum(i*i%1000003 for i in range(1000000)); print(json.dumps(dict(value=v,seconds=time.monotonic()-t)))'
    host_cpu = json.loads(run(['python3', '-B', '-c', cpu]).stdout)
    guest_cpu = json.loads(ssh(state, 'python3 -B -c ' + __import__('shlex').quote(cpu)).stdout)
    if host_cpu['value'] != guest_cpu['value']:
        raise RuntimeError('CPU qualification result mismatch')
    container = ('docker run --name course-qualification --network none --memory 128m --cpus 1 '
        '--read-only --cap-drop ALL --security-opt no-new-privileges ' + __import__('shlex').quote(image_reference) + ' /bin/sh -ec ')
    command = ('test "$(ls /sys/class/net)" = lo; '
        'test ! -e [server-project]/host-only-sentinel; '
        'command -v wget >/dev/null; '
        'for host in 127.0.0.1 10.0.2.15 172.17.0.1; do '
        'if wget -q -T 2 -O - "http://$host:2375/_ping"; then exit 88; fi; done; '
        'echo network-none-api-probes-blocked; uname -m; head -c 16777216 /dev/zero | sha256sum')
    started = time.monotonic()
    output = ssh(state, container + __import__('shlex').quote(command))
    inspect = json.loads(ssh(state, 'docker inspect course-qualification').stdout)[0]
    image = json.loads(ssh(state, 'docker image inspect ' + __import__('shlex').quote(image_reference)).stdout)[0]
    if image['Id'] != small_image['image_id']:
        raise RuntimeError('The actual qualification image differs from its receipt')
    assert inspect['HostConfig']['NetworkMode'] == 'none' and inspect['HostConfig']['Memory'] == 134217728
    assert inspect['HostConfig']['NanoCpus'] == 1000000000 and inspect['State']['ExitCode'] == 0
    assert not inspect['Mounts']
    ssh(state, 'docker rm course-qualification')
    api = GUEST / 'docker.sock'
    if api.exists():
        if not state.get('docker_tunnel_pid') or alive(state['docker_tunnel_pid']):
            raise RuntimeError('Do not replace an existing live API socket')
        if not __import__('stat').S_ISSOCK(api.stat().st_mode):
            raise RuntimeError('The old API path is not a socket')
        api.unlink()
    with (GUEST / 'docker-tunnel.log').open('a') as log:
        process = subprocess.Popen(ssh_base(state) + ['-N', '-o', 'ExitOnForwardFailure=yes',
            '-o', 'StreamLocalBindMask=0177', '-L', f'{api}:127.0.0.1:2375', 'root@127.0.0.1'],
            stdout=log, stderr=log, stdin=subprocess.DEVNULL, start_new_session=True)
    for _ in range(50):
        if api.exists():
            break
        if process.poll() is not None:
            raise RuntimeError('Project-local Docker tunnel failed')
        time.sleep(0.1)
    with socket.socket(socket.AF_UNIX) as client:
        client.connect(str(api))
        client.sendall(b'GET /_ping HTTP/1.0\r\nHost: localhost\r\n\r\n')
        ping = client.recv(4096).decode()
    assert '200 OK' in ping
    assert api.stat().st_mode & 0o777 == 0o600
    state.update(stage='qualified_tcg_guest_small_container_only', docker_tunnel_pid=process.pid,
        task_execution_allowed=True,
        docker_host='unix://' + str(api), docker_api_guest='127.0.0.1:2375',
        api_socket_mode=oct(api.stat().st_mode & 0o777), network_restrict_host_probe_errno=blocked.stdout.strip(),
        cpu_host=host_cpu, cpu_guest=guest_cpu, cpu_emulation_ratio=guest_cpu['seconds'] / host_cpu['seconds'],
        container_stdout=output.stdout, container_qualification_seconds=time.monotonic() - started,
        container_inspected_limits={k:inspect['HostConfig'][k] for k in ('NetworkMode', 'Memory', 'NanoCpus', 'ReadonlyRootfs')},
        qualification_image_id=image['Id'], qualification_image_repo_digests=image['RepoDigests'],
        new_model_calls=0, original_pinned_benchmark_grader_verified=False)
    save(state)
    (ROOT / 'qualification.json').write_text(json.dumps(state, indent=2) + '\n')
    (ROOT / 'ENVIRONMENT.md').write_text('# ModelArts isolated course environment\n\n'
        'Host Ubuntu22.04, non-root project-only packages; KVM device unavailable.\n'
        f'QEMU TCG guest: {state["cpus"]}vCPU/{state["memory_mib"]}MiB, UbuntuMinimal22.04, private qcow2 disk.\n'
        'No host shared directories or provider credentials. Restricted SLIRP networking; only SSH forwarded to host127.0.0.1.\n'
        'Docker API listens only on guest127.0.0.1:2375, authenticated SSH transports it to a mode600 project Unix socket.\n\n'
        f'DOCKER_HOST={state["docker_host"]}\n\n'
        f'CPU fixed arithmetic qualification TCG/host ratio: {state["cpu_emulation_ratio"]:.3f}.\n'
        'This is an environment microbenchmark, not native performance or a new original task score.\n'
        'Small Docker network-none container qualified; no SWE/Aider original image or original grader qualification yet.\n'
        'Runtime/public dependencies can be sent by docker cp; do not mount hostSFS paths.\n')
    print(json.dumps(state), flush=True)


def resize():
    state = json.loads(STATE.read_text())
    if state['stage'] != 'qualified_tcg_guest_small_container_only' or (state['cpus'], state['memory_mib']) != (2, 4096):
        raise RuntimeError('Only the qualified initial 2CPU/4GiB bootstrap may be resized')
    if ssh(state, 'docker ps -q').stdout.strip():
        raise RuntimeError('A task container is active; do not resize')
    archive = GUEST / 'qualification-2cpu-4g'
    archive.mkdir(exist_ok=False)
    for name in ('qualification.json', 'client-qualification.json', 'ENVIRONMENT.md'):
        shutil.copy2(ROOT / name, archive / name)
    shutil.copy2(STATE, archive / 'state.json')
    state.update(cpus=4, memory_mib=8192, stage='trusted_bootstrap_complete',
        resized_from='guest/qualification-2cpu-4g', resize_reason='Authorized before any original benchmark execution')
    save(state)
    restrict_and_qualify()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('phase', choices=('bootstrap', 'qualify', 'resize'))
    args = parser.parse_args()
    {'bootstrap': bootstrap, 'qualify': restrict_and_qualify, 'resize': resize}[args.phase]()
