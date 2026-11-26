import argparse
import hashlib
import json
import os
import re
import subprocess
import time
import urllib.request
from pathlib import Path


ROOT = Path('[server-project]')
VERSION = 'v0.30.1'
ASSET = 'buildx-' + VERSION + '.linux-amd64'
API = 'https://api.github.com/repos/docker/buildx/releases/tags/' + VERSION
FOLDER = ROOT / 'bootstrap-buildx'
if Path(__file__).resolve().parent != ROOT or os.getuid() == 0:
    raise RuntimeError('Use only the isolated, non-root project')
os.umask(0o077)


def opener():
    return urllib.request.build_opener(urllib.request.ProxyHandler({
        'http': 'http://127.0.0.1:46671', 'https': 'http://127.0.0.1:46671'}))


def request(url):
    return urllib.request.Request(url, headers={
        'User-Agent': 'course-project-buildx-bootstrap', 'Accept': 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28'})


def metadata():
    path = FOLDER / ('release-' + VERSION + '.json')
    if not path.exists():
        with opener().open(request(API), timeout=60) as response:
            data = response.read(2 * 1024**2 + 1)
        if len(data) > 2 * 1024**2:
            raise RuntimeError('Unexpected release metadata size')
        path.write_bytes(data)
    release = json.loads(path.read_bytes())
    if release['tag_name'] != VERSION or release['draft'] or release['prerelease']:
        raise RuntimeError('The requested official stable release is unavailable')
    asset, = [item for item in release['assets'] if item['name'] == ASSET]
    if (not re.fullmatch(r'sha256:[0-9a-f]{64}', asset['digest'] or '')
            or not 0 < asset['size'] <= 200 * 1024**2
            or asset['browser_download_url'] != 'https://github.com/docker/buildx/releases/download/' + VERSION + '/' + ASSET):
        raise RuntimeError('The official asset has no valid size/digest/URL binding')
    return asset, path


def install(asset, path):
    directory = ROOT / 'run/work/docker-config/cli-plugins'
    if not directory.parent.is_dir() or not directory.parent.resolve().is_relative_to(ROOT):
        raise RuntimeError('The existing project Docker configuration is required')
    directory.mkdir(exist_ok=True)
    target = directory / 'docker-buildx'
    if target.exists() or target.is_symlink():
        raise FileExistsError('Do not overwrite an existing plugin: ' + str(target))
    temporary = FOLDER / (ASSET + '.downloading')
    checksum = hashlib.sha256()
    count = 0
    started = time.monotonic()
    with opener().open(request(asset['browser_download_url']), timeout=120) as response, temporary.open('xb') as output:
        while chunk := response.read(1024**2):
            if time.monotonic() - started > 600 or count + len(chunk) > asset['size']:
                raise RuntimeError('The official asset exceeded its size or total download deadline')
            output.write(chunk)
            checksum.update(chunk)
            count += len(chunk)
        output.flush()
        os.fsync(output.fileno())
    if count != asset['size'] or 'sha256:' + checksum.hexdigest() != asset['digest']:
        raise RuntimeError('Actual downloaded bytes differ from the official release digest/size')
    with temporary.open('rb') as handle:
        header = handle.read(64)
    if header[:6] != b'\x7fELF\x02\x01' or header[18:20] != b'\x3e\x00':
        raise RuntimeError('The verified asset is not a Linux x86_64 ELF executable')
    temporary.chmod(0o755)
    os.link(temporary, target)
    temporary.unlink()
    environment = {'PATH': '/usr/bin:/bin', 'HOME': str(ROOT / 'course-home'), 'LC_ALL': 'C.UTF-8',
        'DOCKER_CONFIG': str(directory.parent), 'TMPDIR': str(ROOT / 'cache')}
    result = subprocess.run([str(ROOT / 'bin/docker'), 'buildx', 'version'], env=environment,
        check=True, capture_output=True, text=True, timeout=30)
    if not re.match(r'^github\.com/docker/buildx v0\.30\.1(?:\s|$)', result.stdout):
        raise RuntimeError('The Docker CLI did not resolve the installed official plugin')
    receipt = {'status': 'PASS', 'release_api_url': API, 'release_metadata_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
        'asset_name': asset['name'], 'asset_url': asset['browser_download_url'], 'asset_id': asset['id'],
        'official_digest': asset['digest'], 'official_size_bytes': asset['size'],
        'installed_path': str(target), 'installed_sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
        'installed_bytes': target.stat().st_size, 'installed_mode': oct(target.stat().st_mode & 0o777),
        'docker_cli_sha256': hashlib.sha256((ROOT / 'bin/docker').read_bytes()).hexdigest(),
        'source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'docker_config': str(directory.parent), 'version_stdout': result.stdout.strip(),
        'download_seconds': time.monotonic() - started, 'builds_started': 0, 'new_model_calls': 0,
        'guest_or_qemu_modified': False, 'compose_installed': False}
    with (FOLDER / 'installation.json').open('x') as handle:
        handle.write(json.dumps(receipt, indent=2) + '\n')
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('phase', choices=('metadata', 'install'))
    args = parser.parse_args()
    FOLDER.mkdir(exist_ok=True)
    selected, source = metadata()
    result = ({'release': VERSION, 'name': selected['name'], 'bytes': selected['size'], 'digest': selected['digest']}
        if args.phase == 'metadata' else install(selected, source))
    print(json.dumps(result), flush=True)
