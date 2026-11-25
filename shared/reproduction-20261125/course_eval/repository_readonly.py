import hashlib
import json
import os
import stat
import subprocess
from pathlib import Path, PurePosixPath

from course_eval.candidate_io import protected_path
from course_eval.docker_target import DockerTarget


def content_manifest(directory):
    records = {}
    for path in sorted(directory.rglob("*")):
        relative = str(path.relative_to(directory))
        mode = path.lstat().st_mode
        if stat.S_ISLNK(mode):
            records[relative] = {"type": "symlink", "target": os.readlink(path)}
        elif stat.S_ISDIR(mode):
            records[relative] = {"type": "directory", "mode": stat.S_IMODE(mode)}
        elif stat.S_ISREG(mode):
            records[relative] = {"type": "file", "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                                 "mode": stat.S_IMODE(mode)}
        else:
            raise ValueError("A protected repository export contains a special file")
    return records


def mount_roots(tracked):
    roots = set()
    for name in tracked:
        path = PurePosixPath(name)
        if path.is_absolute() or ".." in path.parts or "," in name:
            raise ValueError("The original repository has an unsupported mount path")
        if not protected_path(name):
            continue
        prefix = next((i for i, part in enumerate(path.parts[:-1]) if part in {"tests", "testing", "test"}), None)
        roots.add(str(PurePosixPath(*path.parts[:prefix + 1])) if prefix is not None else name)
    selected = []
    for name in sorted(roots, key=lambda value: (len(PurePosixPath(value).parts), value)):
        if not any(PurePosixPath(name).is_relative_to(parent) for parent in selected):
            selected.append(name)
    return sorted(selected)


def repository_readonly_mounts(image, cwd, cache_root, *, hidden_dirs=()):
    if not PurePosixPath(cwd).is_absolute():
        raise ValueError("A repository guard requires its exact absolute checkout path")
    binary = os.environ["COURSE_DOCKER_BIN"]
    inspected = subprocess.run([binary, "image", "inspect", "--format", "{{.Id}}", image],
                               capture_output=True, text=True, check=True, timeout=30)
    identity = inspected.stdout.strip()
    if not identity.startswith("sha256:") or len(identity) != 71:
        raise ValueError("The original repository image lacks its exact content identity")
    key = identity.removeprefix("sha256:") + "-" + hashlib.sha256(cwd.encode()).hexdigest()[:12]
    directory = Path(cache_root) / key
    manifest_path = directory / "manifest.json"
    payload = directory / "payload"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
        if (manifest["image"] != identity or manifest["cwd"] != cwd
                or manifest["files"] != content_manifest(payload)):
            raise ValueError("The cached original protected repository bytes changed")
    else:
        directory.mkdir(parents=True, exist_ok=False)
        payload.mkdir()
        with DockerTarget(identity, cwd, platform="linux/amd64", memory_mb=3072, cpus=2,
                          read_only_empty_dirs=tuple(hidden_dirs)) as original:
            tree = original.exec("git ls-tree -r --name-only -z HEAD", timeout=30)
            head = original.exec("git rev-parse HEAD", timeout=10)
            if tree["returncode"] or head["returncode"]:
                raise ValueError("Cannot identify the original repository's tracked public files")
            tracked = [name for name in tree["stdout"].split("\0") if name]
            roots = mount_roots(tracked)
            if not roots:
                raise ValueError("The original repository has no declared protected test or configuration paths")
            for name in roots:
                destination = payload / name
                destination.parent.mkdir(parents=True, exist_ok=True)
                original.docker("cp", f"{original.container}:{cwd.rstrip('/')}/{name}", str(destination))
                if destination.is_symlink():
                    raise ValueError("A protected mount root must not be a symbolic link")
            manifest = {"image": identity, "cwd": cwd, "head": head["stdout"].strip(),
                        "roots": roots, "files": content_manifest(payload),
                        "model_requests_in_preparation": 0,
                        "policy": "same protected_path rule as the course candidate store; complete original directories are mounted read-only"}
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    mounts = []
    for name in manifest["roots"]:
        relative = PurePosixPath(name)
        source = payload / name
        if (relative.is_absolute() or ".." in relative.parts or "," in name or name not in manifest["files"]
                or source.is_symlink() or not source.resolve(strict=True).is_relative_to(payload.resolve())):
            raise ValueError("A cached protected mount is outside its original public payload")
        mounts.append((str(source), cwd.rstrip("/") + "/" + name))
    return tuple(mounts)
