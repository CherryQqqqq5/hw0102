import hashlib
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path


ROOT = Path('[server-project]')
if Path(__file__).resolve().parent != ROOT or os.getuid() == 0:
    raise RuntimeError('Only the new non-root project is allowed')
guest = ROOT / 'guest'
state = json.loads((guest / 'state.json').read_text())
if not state.get('ssh_ready_seconds'):
    raise RuntimeError('Guest SSH is not ready')
program = ('import time,json,subprocess,sys; t=time.monotonic(); '
    'v=sum(i*i%1000003 for i in range(1000000)); arithmetic=time.monotonic()-t; '
    't=time.monotonic(); [subprocess.run(["/bin/true"],check=True)for _ in range(10)]; '
    'print(json.dumps(dict(value=v,arithmetic_seconds=arithmetic,ten_subprocess_seconds=time.monotonic()-t,python=sys.version.split()[0])))')
host = json.loads(subprocess.check_output([sys.executable, '-B', '-c', program], text=True))
command = ['ssh', '-F', '/dev/null', '-i', str(guest / 'id_ed25519'), '-p', str(state['ssh_port']),
    '-o', 'BatchMode=yes', '-o', 'IdentitiesOnly=yes', '-o', 'IdentityAgent=none',
    '-o', 'StrictHostKeyChecking=yes', '-o', f'UserKnownHostsFile={guest}/known_hosts',
    '-o', 'GlobalKnownHostsFile=/dev/null', 'root@127.0.0.1', 'python3 -B -c ' + shlex.quote(program)]
actual = json.loads(subprocess.check_output(command, text=True, timeout=60))
assert host['value'] == actual['value']
result = {'stage': 'provisional_during_trusted_guest_package_bootstrap', 'host': host, 'guest': actual,
    'arithmetic_ratio': actual['arithmetic_seconds'] / host['arithmetic_seconds'],
    'program_sha256': hashlib.sha256(program.encode()).hexdigest(),
    'new_model_calls': 0, 'original_grader_calls': 0, 'interpretation': 'TCG microbenchmark only; guest apt may run concurrently'}
(ROOT / 'cpu-bootstrap.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result))
