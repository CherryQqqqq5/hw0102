import base64
import fnmatch
import hashlib
import json
import os
import stat
import subprocess
import sys
from pathlib import Path


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def read_file(name):
    path = Path(name)
    if not path.exists() and not path.is_symlink():
        return {"missing": True}
    if path.is_symlink() or not path.is_file():
        raise ValueError("Only regular candidate files are supported: " + name)
    if path.stat().st_size > 8 * 1024 * 1024:
        raise ValueError("Candidate file exceeds 8 MiB: " + name)
    return {"data": base64.b64encode(path.read_bytes()).decode(), "mode": stat.S_IMODE(path.stat().st_mode)}


def file_identity(name):
    path = Path(name)
    if not path.exists() and not path.is_symlink():
        return {"missing": True}
    if path.is_symlink() or not path.is_file():
        raise ValueError("Protected dependency is not a regular file: " + name)
    checksum = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            checksum.update(chunk)
    return {"sha256": checksum.hexdigest(), "mode": stat.S_IMODE(path.stat().st_mode)}


def git(*args):
    return subprocess.check_output(["git", "--no-pager", *args], universal_newlines=True)


def protected_path(name):
    path = Path(name)
    return (any(part in {"tests", "testing", "test"} for part in path.parts)
            or path.name.startswith("test_") or path.name in {
                "tox.ini", "pytest.ini", "conftest.py", "pyproject.toml", "setup.cfg", "setup.py"})


def test_configuration(name):
    return Path(name).name in {"conftest.py", "pytest.ini", "tox.ini", "pyproject.toml", "setup.cfg", "setup.py"}


def names_for(scope):
    if scope["kind"] == "repository":
        head = git("rev-parse", "HEAD").strip()
        if scope.get("head") and head != scope["head"]:
            raise ValueError("Repository HEAD changed during the trial")
        tracked = git("ls-tree", "-r", "--name-only", "-z", scope.get("head", "HEAD")).split("\0")
        changed = git("diff", "--no-ext-diff", "--no-textconv", "--name-only", "-z", "HEAD").split("\0")
        untracked = git("ls-files", "--others", "--exclude-standard", "-z").split("\0")
        # 新建复现文件也是候选；缓存和构建结果不进入版本存储。
        ignored = ("*.pyc", "*.pyo", "*.so", "*.o", "*.log", "*.jsonl", "*.tar*", "*.png", "*.pdf")
        protected = sorted(name for name in tracked if name and protected_path(name))
        source_changes = [name for name in changed if name and name not in protected and not test_configuration(name)]
        new_sources = [name for name in untracked if name and not test_configuration(name)
                       and not name.startswith(".course-public-check/")]
        artifacts = sorted({name for name in source_changes + new_sources if name
                            and not any(fnmatch.fnmatch(name, pattern) for pattern in ignored)})
        modified_protected = sorted({name for name in changed if name in protected}
                                    | {name for name in changed + untracked if name and test_configuration(name)})
        return artifacts, protected, {"head": head, "modified_protected": modified_protected}
    artifacts = list(scope["artifacts"])
    protected = set(scope.get("protected", []))
    permitted = {Path(name).resolve() for name in artifacts}
    protected.update(str(path) for path in Path(".").rglob("*") if path.is_file()
                     and test_configuration(str(path)) and path.resolve() not in permitted)
    return artifacts, sorted(protected), {}


def capture(scope, known):
    artifacts, protected, extra = names_for(scope)
    version_paths = list(artifacts)
    if scope["kind"] == "repository":
        # 只传输相对初始版本的改动；恢复时用宿主保存的初始字节覆盖已撤销的改动。
        artifacts = sorted(set(artifacts) | set(known))
    files = {name: read_file(name) for name in artifacts}
    if sum(len(item.get("data", "")) for item in files.values()) > 24 * 1024 * 1024:
        raise ValueError("Candidate exceeds 18 MiB")
    if scope["kind"] == "repository":
        protected_digest = digest(extra["modified_protected"])
    else:
        protected_digest = digest({name: file_identity(name) for name in protected})
    version = {name: files[name] for name in version_paths}
    return {"files": files, "artifact_digest": digest(version), "protected_digest": protected_digest, **extra}


def initial(scope):
    artifacts, protected, extra = names_for(scope)
    if scope["kind"] == "repository":
        if artifacts or extra["modified_protected"]:
            raise ValueError("Candidate repository must start clean")
        files = {}
    else:
        files = {name: read_file(name) for name in artifacts}
    return {"files": files, "artifact_digest": digest(files),
            "protected_digest": digest(extra["modified_protected"]) if scope["kind"] == "repository"
            else digest({name: file_identity(name) for name in protected}), **extra}


def original(scope, names):
    if scope["kind"] != "repository":
        raise ValueError("Original repository bytes require repository scope")
    records = {}
    tracked_names = set(git("ls-tree", "-r", "--name-only", "-z", scope["head"]).split("\0"))
    for name in names:
        if name in tracked_names:
            data = subprocess.check_output(["git", "show", scope["head"] + ":" + name])
            mode = git("ls-tree", scope["head"], "--", name).split()[0]
            records[name] = {"data": base64.b64encode(data).decode(), "mode": int(mode, 8) & 0o777}
        else:
            records[name] = {"missing": True}
    return records


def restore(scope, files):
    tracked_names = (set(git("ls-tree", "-r", "--name-only", "-z", scope["head"]).split("\0"))
                     if scope["kind"] == "repository" else set())
    for name, record in files.items():
        path = Path(name)
        if ".." in path.parts or path.is_symlink() or any(parent.is_symlink() for parent in path.parents):
            raise ValueError("Unsafe candidate path: " + name)
        if scope["kind"] == "repository" and (path.is_absolute() or test_configuration(name)
                                               or name in tracked_names and protected_path(name)):
            raise ValueError("Candidate restore cannot modify protected paths: " + name)
        if scope["kind"] == "files" and name not in scope["artifacts"]:
            raise ValueError("Candidate restore is outside explicit artifact paths: " + name)
    for name, record in files.items():
        path = Path(name)
        if record.get("missing"):
            if path.exists():
                path.unlink()
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            staged = path.with_name(path.name + ".course-writing")
            staged.write_bytes(base64.b64decode(record["data"], validate=True))
            os.chmod(staged, record["mode"])
            staged.replace(path)
    return {"restored": sorted(files)}


def main():
    request = json.loads(Path(sys.argv[1]).read_text())
    os.chdir(request["cwd"])
    scope = request["scope"]
    operation = request["operation"]
    if operation == "initial":
        result = initial(scope)
    elif operation == "capture":
        result = capture(scope, request.get("known", []))
    elif operation == "original":
        result = original(scope, request["names"])
    elif operation == "restore":
        result = restore(scope, request["files"])
    else:
        raise ValueError("Unknown candidate operation")
    print(json.dumps(result, separators=(",", ":")))


if __name__ == "__main__":
    main()
