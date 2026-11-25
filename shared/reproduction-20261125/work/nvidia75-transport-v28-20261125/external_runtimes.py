import hashlib
import os
from pathlib import Path


def fingerprint(root, paths):
    files, links = {}, {}
    for relative in paths:
        directory = root / relative
        for path in sorted(directory.rglob("*")):
            name = str(path.relative_to(root))
            if path.is_symlink():
                target = path.resolve(strict=True)
                if not target.is_relative_to(directory.resolve()):
                    raise ValueError("An external SDK link leaves its declared runtime: " + name)
                links[name] = os.readlink(path)
            if path.is_file():
                with path.open("rb") as stream:
                    files[name] = hashlib.file_digest(stream, "sha256").hexdigest()
    return {"roots": paths, "file_sha256": files, "symlinks": links}


def verify_runtime(root, manifest):
    current = fingerprint(root, manifest["roots"])
    if current != {key: manifest[key] for key in ("roots", "file_sha256", "symlinks")}:
        raise ValueError("The actual mounted DSH SDK/Python bytes or inventory changed")
