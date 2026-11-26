import hashlib
import json
import shlex
from pathlib import Path

import guest_vm


state = json.loads(guest_vm.STATE.read_text())
if state['stage'] != 'trusted_guest_bootstrap_only' or state['restricted']:
    raise RuntimeError('Only this unscored guest bootstrap may prepare the small image')
failure = guest_vm.ssh(state, 'tail -n 14 /var/log/cloud-init-output.log').stdout
if 'registry-1.docker.io' not in failure or 'i/o timeout' not in failure:
    raise RuntimeError('Preserve and inspect the actual image-pull failure first')
archive = guest_vm.ROOT / 'guest' / 'docker-hub-pull-failure.txt'
if archive.exists() and archive.read_text() != failure:
    raise RuntimeError('Do not replace the original bootstrap failure')
archive.write_text(failure)
program = '''import hashlib,io,json,os,subprocess,tarfile
from pathlib import Path
folder=Path('/var/lib/course-small-image')
folder.mkdir(exist_ok=True)
os.chdir(folder)
def run(args):
    return subprocess.run(args,check=True,capture_output=True,text=True,timeout=180)
run(['apt-get','download','busybox-static'])
packages=list(folder.glob('busybox-static_*.deb'))
assert len(packages)==1
package=packages[0]
run(['dpkg-deb','-x',str(package),str(folder/'root')])
binary=folder/'root/bin/busybox'
assert binary.is_file()
tarpath=folder/'rootfs.tar'
with tarfile.open(tarpath,'w') as output:
    output.add(binary,arcname='bin/busybox')
    for name in ('sh','ls','wget','uname','head','sha256sum'):
        item=tarfile.TarInfo('bin/'+name)
        item.type=tarfile.SYMTYPE
        item.linkname='busybox'
        item.mode=0o777
        output.addfile(item)
reference='course-qualification-busybox-static:jammy'
image=run(['docker','import',str(tarpath),reference]).stdout.strip()
print(json.dumps(dict(image=reference,image_id=image,
    package=package.name,package_sha256=hashlib.sha256(package.read_bytes()).hexdigest(),
    package_bytes=package.stat().st_size,binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),
    purpose='Project-owned engine qualification rootfs; not an official benchmark image',
    new_model_calls=0,new_original_grader_calls=0)))
'''
result = guest_vm.ssh(state, 'python3 -c ' + shlex.quote(program), timeout=300)
receipt = json.loads(result.stdout)
receipt['docker_hub_failure_sha256'] = hashlib.sha256(archive.read_bytes()).hexdigest()
path = guest_vm.ROOT / 'small-image.json'
if path.exists():
    raise RuntimeError('The small-image receipt already exists')
path.write_text(json.dumps(receipt, indent=2) + '\n')
guest_vm.ssh(state, 'docker version > /var/lib/course-docker-version.txt; touch /var/lib/course-bootstrap-ready')
print(json.dumps(receipt), flush=True)
