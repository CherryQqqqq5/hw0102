import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path('[server-project]')
if Path(__file__).resolve().parent != ROOT or os.getuid() == 0:
    raise RuntimeError('Run this copied script as the existing non-root user in the isolated project')
os.umask(0o077)
for name in ('logs', 'cache', 'packages', 'sysroot', 'apt/lists/partial', 'apt/cache', 'guest', 'python', 'bin', 'config'):
    (ROOT / name).mkdir(parents=True, exist_ok=True)
ENV = os.environ | {'TMPDIR': str(ROOT / 'cache'), 'PIP_CACHE_DIR': str(ROOT / 'cache/pip'),
    'PIP_INDEX_URL': 'https://pypi.org/simple', 'UV_CACHE_DIR': str(ROOT / 'cache/uv'),
    'UV_PYTHON_INSTALL_DIR': str(ROOT / 'python'), 'UV_PYTHON_BIN_DIR': str(ROOT / 'bin'),
    'UV_DEFAULT_INDEX': 'https://pypi.org/simple', 'UV_NO_CONFIG': '1',
    'PIP_CONFIG_FILE': '/dev/null', 'XDG_CACHE_HOME': str(ROOT / 'cache'),
    'MSWEA_GLOBAL_CONFIG_DIR': str(ROOT / 'config'), 'MSWEA_SILENT_STARTUP': '1',
    'PYTHONDONTWRITEBYTECODE': '1'}
ENV.pop('PIP_EXTRA_INDEX_URL', None)
STATE = ROOT / 'host-preparation.json'
state = json.loads(STATE.read_text()) if STATE.exists() else {'stage': 'preparing', 'new_model_calls': 0}


def record(stage, **values):
    state.update(stage=stage, **values)
    STATE.write_text(json.dumps(state, indent=2) + '\n')
    print(json.dumps({'stage': stage, **values}), flush=True)


def run(args, label, *, cwd=ROOT, timeout=1200, env=ENV):
    with (ROOT / 'logs' / (label + '.log')).open('a') as log:
        result = subprocess.run([str(x) for x in args], cwd=cwd, env=env,
            stdout=log, stderr=subprocess.STDOUT, timeout=timeout)
    if result.returncode:
        raise RuntimeError(f'{label}: exit {result.returncode}; see project log')


def checksum(path):
    value = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


apt_sources = ROOT / 'apt/sources.list'
apt_sources.write_text('deb [arch=amd64] https://archive.ubuntu.com/ubuntu jammy main\n'
    'deb [arch=amd64] https://archive.ubuntu.com/ubuntu jammy-updates main\n'
    'deb [arch=amd64] https://security.ubuntu.com/ubuntu jammy-security main\n')
APT = ['-o', f'Dir::State::Lists={ROOT}/apt/lists', '-o', f'Dir::Cache={ROOT}/apt/cache',
    '-o', f'Dir::Etc::sourcelist={apt_sources}', '-o', 'Dir::Etc::sourceparts=-',
    '-o', 'Debug::NoLocking=true', '-o', 'Acquire::Languages=none']
run(['apt-get', *APT, 'update'], 'apt-project-update', timeout=600)
record('signed_apt_metadata_in_project')
packages = {}


def package(name):
    if name in packages:
        return
    run(['apt-get', *APT, 'download', name], 'download-' + name, cwd=ROOT / 'packages')
    for path in (ROOT / 'packages').glob('*.deb'):
        if path.name in packages.values():
            continue
        actual = subprocess.check_output(['dpkg-deb', '-f', str(path), 'Package'], text=True).strip()
        if actual != name:
            continue
        run(['dpkg-deb', '-x', path, ROOT / 'sysroot'], 'extract-' + name)
        packages[name] = path.name
        return
    raise RuntimeError('Downloaded package not found: ' + name)


for name in ('qemu-system-x86', 'qemu-system-common', 'qemu-system-data', 'qemu-utils', 'seabios', 'ipxe-qemu'):
    package(name)
libdirs = [ROOT / 'sysroot/usr/lib/x86_64-linux-gnu', ROOT / 'sysroot/lib/x86_64-linux-gnu']
QENV = ENV | {'LD_LIBRARY_PATH': ':'.join(map(str, libdirs)),
    'QEMU_MODULE_DIR': str(ROOT / 'sysroot/usr/lib/x86_64-linux-gnu/qemu')}
owners = {'libaio.so.1': 'libaio1', 'libfdt.so.1': 'libfdt1', 'libfuse3.so.3': 'libfuse3-3',
    'libpixman-1.so.0': 'libpixman-1-0', 'libslirp.so.0': 'libslirp0', 'liburing.so.2': 'liburing2',
    'libpmem.so.1': 'libpmem1', 'libdaxctl.so.1': 'libdaxctl1', 'libndctl.so.6': 'libndctl6',
    'libibverbs.so.1': 'libibverbs1', 'librdmacm.so.1': 'librdmacm1', 'libnuma.so.1': 'libnuma1',
    'libsasl2.so.2': 'libsasl2-2', 'libcap-ng.so.0': 'libcap-ng0', 'libattr.so.1': 'libattr1',
    'libnl-3.so.200': 'libnl-3-200', 'libnl-route-3.so.200': 'libnl-route-3-200',
    'libjpeg.so.8': 'libjpeg-turbo8', 'libgthread-2.0.so.0': 'libglib2.0-0',
    'libgmodule-2.0.so.0': 'libglib2.0-0', 'libglib-2.0.so.0': 'libglib2.0-0'}
for attempt in range(6):
    missing = set()
    for binary in ('qemu-system-x86_64', 'qemu-img'):
        result = subprocess.run(['ldd', str(ROOT / 'sysroot/usr/bin' / binary)], env=QENV,
            capture_output=True, text=True, check=True)
        missing.update(re.findall(r'(\S+) => not found', result.stdout))
    if not missing:
        break
    if missing - owners.keys():
        raise RuntimeError('Unmapped missing Ubuntu libraries: ' + ','.join(sorted(missing)))
    for name in sorted({owners[x] for x in missing}):
        package(name)
else:
    raise RuntimeError('QEMU dependencies did not close within six rounds')
run([ROOT / 'sysroot/usr/bin/qemu-system-x86_64', '--version'], 'qemu-version', env=QENV)
record('qemu_project_tools_ready', packages={name: {'file': filename,
    'sha256': checksum(ROOT / 'packages' / filename)} for name, filename in packages.items()})

venv = ROOT / '.venv'
if not (venv / 'bin/python').exists():
    run([sys.executable, '-m', 'venv', venv], 'create-bootstrap-venv')
run([venv / 'bin/python', '-m', 'pip', 'install', 'pexpect==4.9.0', 'pycdlib==1.14.0', 'uv'], 'bootstrap-dependencies')
record('bootstrap_venv_ready')
run([venv / 'bin/uv', 'python', 'install', '3.13'], 'managed-python313')
if not (ROOT / '.venv-course/bin/python').exists():
    run([venv / 'bin/uv', 'venv', '--python', '3.13', ROOT / '.venv-course'], 'create-course-venv')
run([venv / 'bin/uv', 'pip', 'install', '--python', ROOT / '.venv-course/bin/python',
    'mini-swe-agent==2.4.6', 'swebench==5.0.2', 'harbor==0.25.0', 'docker==7.1.0'], 'course-dependencies')
record('course_python_dependencies_ready')

base = 'https://cloud-images.ubuntu.com/minimal/releases/jammy/release/'
for remote, local in (('SHA256SUMS', 'SHA256SUMS'),
        ('ubuntu-22.04-minimal-cloudimg-amd64.img', 'ubuntu-jammy-base.qcow2')):
    path = ROOT / 'guest' / local
    if not path.exists():
        part = path.with_suffix(path.suffix + '.part')
        run(['curl', '-q', '--fail', '--location', '--retry', '2', '--connect-timeout', '20',
            '--max-time', '1800', '--continue-at', '-', '--output', part, base + remote],
            'download-' + local, timeout=1850)
        part.rename(path)
expected = next(line.split()[0] for line in (ROOT / 'guest/SHA256SUMS').read_text().splitlines()
    if line.endswith('ubuntu-22.04-minimal-cloudimg-amd64.img'))
actual = checksum(ROOT / 'guest/ubuntu-jammy-base.qcow2')
if expected != actual:
    raise RuntimeError('Official Ubuntu image SHA256 mismatch')
record('host_tools_and_base_image_ready', guest_base_sha256=actual,
    guest_base_bytes=(ROOT / 'guest/ubuntu-jammy-base.qcow2').stat().st_size,
    guest_started=False, pinned_benchmark_images_downloaded=0)
