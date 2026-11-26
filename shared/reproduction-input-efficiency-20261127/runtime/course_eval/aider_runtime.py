import hashlib
import os
import time
from pathlib import Path


PYTHON_SHA256 = {"linux/arm64": "31c6e61eed48ca4e156d0e473025a792338641109e8277a63518ded438390c96",
    "linux/amd64": "ad178e36a84de3f845885d0ace5ca6f87fa9502d1f0cf53ba3dd42194277d42e"}


def prepare_aider_runtime(target, language):
    if language != "javascript":
        return None
    archive = Path(os.environ["COURSE_AIDER_PUBLIC_PYTHON"])
    expected = PYTHON_SHA256[os.environ.get("COURSE_AIDER_PLATFORM", "linux/arm64")]
    if hashlib.sha256(archive.read_bytes()).hexdigest() != expected:
        raise ValueError("Aider public Python differs from the pinned upstream release")
    started = time.monotonic()
    target.upload_file(archive, "/course-public-python.tar.gz", timeout=60)
    output = target.exec(
        "mkdir -p /opt/course-runtime && tar -xzf /course-public-python.tar.gz "
        "-C /opt/course-runtime --strip-components=1 && /opt/course-runtime/bin/python3 --version "
        "&& test ! -e /usr/local/bin/python3 && ln -s /opt/course-runtime/bin/python3 /usr/local/bin/python3",
        timeout=90)
    if output["returncode"]:
        raise RuntimeError("Aider public Python setup failed: " + output["stderr"])
    # 原公开脚本会启用xtest并建立依赖链接，须在保护测试内容之前完成。
    initialized = target.exec("/aider/benchmark/npm-test.sh", timeout=60)
    if initialized["returncode"] not in (0, 1):
        raise RuntimeError("Aider public test preparation failed: " + initialized["stderr"])
    return {"source": archive.name, "sha256": expected, "python": output["stdout"].strip(),
            "seconds": time.monotonic() - started, "all_configurations": True,
            "public_helper_initialized_before_snapshot": True, "starter_test_returncode": initialized["returncode"]}
