import os
import time
from pathlib import Path


def prepare_public_runtime(target, scope):
    if not scope or not scope.get("python", "").startswith("/opt/course-runtime/"):
        return None
    started = time.monotonic()
    archive = Path(os.environ["COURSE_TERMINAL_PYTHON"])
    target.upload_file(archive, "/course-public-python.tar.gz", timeout=60)
    result = target.exec("mkdir -p /opt/course-runtime && tar -xzf /course-public-python.tar.gz -C /opt/course-runtime --strip-components=1 && /opt/course-runtime/bin/python3 --version && test ! -e /usr/local/bin/python3 && ln -s /opt/course-runtime/bin/python3 /usr/local/bin/python3", timeout=90)
    if result["returncode"]:
        raise RuntimeError("Public Python runtime setup failed: " + result["stderr"])
    return {"source": archive.name, "python": result["stdout"].strip(), "seconds": time.monotonic() - started,
            "all_configurations": True}
