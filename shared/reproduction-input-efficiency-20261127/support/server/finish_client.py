import hashlib
import json
import os
import shlex
import subprocess
import time
from pathlib import Path

import docker
import guest_vm


state = json.loads(guest_vm.STATE.read_text())
if state['stage'] != 'qualified_tcg_guest_small_container_only' or not state['restricted']:
    raise RuntimeError('The actual restricted small-container qualification is required')
root = guest_vm.ROOT
environment = dict(guest_vm.ENV, HOME=str(root / 'course-home'),
    DOCKER_CONFIG=str(root / 'config/docker'), DOCKER_HOST=state['docker_host'])
for name in ('course-home', 'config/docker', 'bin'):
    (root / name).mkdir(parents=True, exist_ok=True)
cli = root / 'bin/docker'
if cli.exists():
    actual_sha = guest_vm.ssh(state, 'sha256sum /usr/bin/docker').stdout.split()[0]
    if hashlib.sha256(cli.read_bytes()).hexdigest() != actual_sha:
        raise RuntimeError('Do not replace a differing project Docker CLI')
else:
    base = guest_vm.ssh_base(state)
    copy = ['scp'] + base[1:]
    copy[copy.index('-p')] = '-P'
    subprocess.run(copy + ['root@127.0.0.1:/usr/bin/docker', str(cli)],
        env=environment, capture_output=True, text=True, timeout=180, check=True)
cli.chmod(0o755)
started = time.monotonic()
client = docker.DockerClient(base_url=state['docker_host'], timeout=30)
assert client.ping() is True
info = client.info()
server = client.version()
client.close()
api_seconds = time.monotonic() - started
cli_result = subprocess.run([str(cli), 'info', '--format', '{{json .}}'],
    env=environment, capture_output=True, text=True, timeout=60, check=True)
cli_info = json.loads(cli_result.stdout)
assert cli_info['ID'] == info['ID'] and info['OSType'] == 'linux'
compose = subprocess.run([str(cli), 'compose', 'version'], env=environment,
    capture_output=True, text=True, timeout=30)
cpu = ('import time,json,subprocess; t=time.monotonic(); '
    'v=sum(i*i%1000003 for i in range(1000000)); a=time.monotonic()-t; '
    't=time.monotonic(); '
    '[subprocess.run(["/bin/true"],check=True) for _ in range(10)]; '
    'print(json.dumps(dict(value=v,arithmetic_seconds=a,ten_process_seconds=time.monotonic()-t)))')
host = json.loads(subprocess.run(['/usr/bin/python3', '-B', '-c', cpu],
    env=environment, capture_output=True, text=True, timeout=60, check=True).stdout)
guest = json.loads(guest_vm.ssh(state, 'python3 -B -c ' + shlex.quote(cpu)).stdout)
assert host['value'] == guest['value']
receipt = dict(status='actual_project_docker_api_and_cli_passed',
    docker_host=state['docker_host'], socket_mode=oct(Path(state['docker_host'][7:]).stat().st_mode & 0o777),
    sdk_version=docker.__version__, api_seconds=api_seconds,
    server_version=server['Version'], api_version=server['ApiVersion'],
    operating_system=info['OperatingSystem'], architecture=info['Architecture'],
    guest_cpus=info['NCPU'], guest_memory_bytes=info['MemTotal'],
    docker_cli_sha256=hashlib.sha256(cli.read_bytes()).hexdigest(),
    cli_matches_actual_sdk_info=True,
    compose_available=compose.returncode == 0,
    compose_stdout=compose.stdout.strip(), compose_stderr=compose.stderr.strip(),
    idle_microbenchmark=dict(host=host, guest=guest,
        arithmetic_ratio=guest['arithmetic_seconds']/host['arithmetic_seconds'],
        process_ratio=guest['ten_process_seconds']/host['ten_process_seconds']),
    source_sha256={name:hashlib.sha256((root/name).read_bytes()).hexdigest()
        for name in ('guest_vm.py', 'prepare_small_image.py', 'finish_client.py',
            'qualification.json', 'small-image.json')},
    new_model_calls=0, new_original_grader_calls=0,
    original_course_image_or_grader_qualified=False)
(root / 'client-qualification.json').write_text(json.dumps(receipt, indent=2) + '\n')
(root / 'docker-env.sh').write_text(
    'export DOCKER_HOST=' + shlex.quote(state['docker_host']) + '\n'
    'export DOCKER_CONFIG=' + shlex.quote(environment['DOCKER_CONFIG']) + '\n'
    'export MSWEA_GLOBAL_CONFIG_DIR=' + shlex.quote(str(root/'config')) + '\n'
    'export MSWEA_SILENT_STARTUP=1\n'
    'export PATH=' + shlex.quote(str(root/'bin')) + ':"$PATH"\n')
print(json.dumps(receipt), flush=True)
