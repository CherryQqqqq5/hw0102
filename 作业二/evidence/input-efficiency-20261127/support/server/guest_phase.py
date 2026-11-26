import argparse
import hashlib
import json
import os
import shlex
import shutil
import socket
import stat
import subprocess
import time

import docker
import guest_vm


def proxy_content(proxy_port):
    proxy = f'http://10.0.2.2:{proxy_port}'
    return ('[Service]\nEnvironment="HTTP_PROXY=' + proxy + '"\n'
        'Environment="HTTPS_PROXY=' + proxy + '"\n'
        'Environment="NO_PROXY=localhost,127.0.0.1,::1"\n')


def preparation(state, proxy_port):
    if state['stage'] != 'qualified_tcg_guest_small_container_only' or not state['restricted']:
        raise RuntimeError('Switch only from the actually qualified restricted guest')
    with socket.create_connection(('127.0.0.1', proxy_port), timeout=3):
        pass
    content = proxy_content(proxy_port)
    program = ('from pathlib import Path; p=Path("/etc/systemd/system/docker.service.d/20-project-proxy.conf"); '
        'p.parent.mkdir(parents=True,exist_ok=True); p.write_text(' + repr(content) + ')')
    guest_vm.ssh(state, 'python3 -c ' + shlex.quote(program))
    old_tunnel = state['docker_tunnel_pid']
    guest_vm.ssh(state, 'sync; poweroff', check=False)
    deadline = time.monotonic() + 180
    while guest_vm.alive(state['qemu_pid']) and time.monotonic() < deadline:
        time.sleep(2)
    if guest_vm.alive(state['qemu_pid']) or guest_vm.alive(old_tunnel):
        raise RuntimeError('The previous guest/tunnel has not naturally closed')
    api = guest_vm.GUEST / 'docker.sock'
    if not stat.S_ISSOCK(api.stat().st_mode):
        raise RuntimeError('The old API path is not the owned socket')
    api.unlink()
    guest_vm.start(state, restricted=False)
    finish_preparation(state, proxy_port)


def finish_preparation(state, proxy_port, existing_tunnel_pid=None):
    api = guest_vm.GUEST / 'docker.sock'
    if api.exists():
        if not existing_tunnel_pid or not guest_vm.alive(existing_tunnel_pid):
            raise RuntimeError('An existing socket requires its exact live tunnel PID')
        actual_args = (guest_vm.Path(f'/proc/{existing_tunnel_pid}/cmdline').read_bytes().decode().split('\0'))
        if (f'{api}:127.0.0.1:2375' not in actual_args
                or str(guest_vm.GUEST / 'id_ed25519') not in actual_args or '-N' not in actual_args):
            raise RuntimeError('The existing process is not the exact project Docker tunnel')
        tunnel_pid = existing_tunnel_pid
    else:
        with (guest_vm.GUEST / 'docker-tunnel.log').open('a') as log:
            process = subprocess.Popen(guest_vm.ssh_base(state) + ['-N', '-o', 'ExitOnForwardFailure=yes',
                '-o', 'StreamLocalBindMask=0177', '-L', f'{api}:127.0.0.1:2375', 'root@127.0.0.1'],
                env=guest_vm.ENV, stdout=log, stderr=log, stdin=subprocess.DEVNULL, start_new_session=True)
        tunnel_pid = process.pid
        state['preparation_tunnel_pid'] = tunnel_pid
        guest_vm.save(state)
        for _ in range(50):
            if api.exists():
                break
            if process.poll() is not None:
                raise RuntimeError('The preparation API tunnel failed')
            time.sleep(.1)
    client = docker.DockerClient(base_url=state['docker_host'], timeout=60)
    try:
        assert client.ping() is True
        info = client.info()
    finally:
        client.close()
    assert info['NCPU'] == 4 and info['MemTotal'] > 7 * 1024**3
    assert api.stat().st_mode & 0o777 == 0o600
    actual = guest_vm.ssh(state, 'cat /etc/systemd/system/docker.service.d/20-project-proxy.conf').stdout
    assert actual == proxy_content(proxy_port)
    proxy = f'http://10.0.2.2:{proxy_port}'
    state.update(stage='trusted_image_preparation_only', docker_tunnel_pid=tunnel_pid,
        task_execution_allowed=False, preparation_proxy=proxy,
        proxy_dropin_sha256=hashlib.sha256(actual.encode()).hexdigest(),
        guest_cpus_actual=info['NCPU'], guest_memory_bytes_actual=info['MemTotal'])
    guest_vm.save(state)
    print(json.dumps({'stage': state['stage'], 'docker_host': state['docker_host'],
        'task_execution_allowed': False, 'restricted': False, 'proxy': proxy,
        'new_model_calls': 0}), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('phase', choices=('preparation', 'resume-preparation', 'tasks'))
    parser.add_argument('--proxy-port', type=int)
    parser.add_argument('--existing-tunnel-pid', type=int)
    args = parser.parse_args()
    state = json.loads(guest_vm.STATE.read_text())
    if (state['cpus'], state['memory_mib']) != (4, 8192):
        raise RuntimeError('The fixed 4CPU/8GiB guest is required')
    if args.phase == 'resume-preparation':
        if (state['stage'] != 'trusted_guest_bootstrap_only' or state['restricted']
                or not guest_vm.alive(state['qemu_pid'])):
            raise RuntimeError('Resume only the existing live, unscored preparation guest')
        guest_vm.wait_for_ssh(state)
    if guest_vm.ssh(state, 'docker ps -q').stdout.strip():
        raise RuntimeError('Active containers prevent a guest phase transition')
    if args.phase != 'tasks' and not (args.proxy_port and 1 <= args.proxy_port <= 65535):
        parser.error('Preparation requires the explicit project-owned loopback proxy port')
    archive = guest_vm.GUEST / ('before-' + args.phase + '-' + str(time.time_ns()))
    archive.mkdir()
    shutil.copy2(guest_vm.STATE, archive / 'state.json')
    for name in ('qualification.json', 'client-qualification.json', 'ENVIRONMENT.md'):
        shutil.copy2(guest_vm.ROOT / name, archive / name)
    if args.phase == 'preparation':
        preparation(state, args.proxy_port)
    elif args.phase == 'resume-preparation':
        finish_preparation(state, args.proxy_port, args.existing_tunnel_pid)
    else:
        if state['stage'] != 'trusted_image_preparation_only' or state['restricted']:
            raise RuntimeError('Task qualification must follow the explicit trusted preparation phase')
        state['stage'] = 'trusted_bootstrap_complete'
        guest_vm.save(state)
        guest_vm.restrict_and_qualify()


if __name__ == '__main__':
    main()
