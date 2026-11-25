import hashlib
import os
import time
from pathlib import Path


RELU_HELPER_PATH = "/opt/course-tools/relu_recovery.py"


def reusable_helper_instructions(scope):
    name = scope.get("reusable_helper") if scope else None
    if name is None:
        return ""
    if name != "relu_directions":
        raise ValueError("Unknown reusable numerical helper: " + str(name))
    return ("\nOptional reusable numerical source is available at " + RELU_HELPER_PATH
            + ". It provides recover_relu_directions(oracle, dimension), returning (rows, diagnostics). "
            "It queries a scalar one-hidden-layer ReLU oracle and estimates input-weight row directions "
            "without receiving the unknown width or weights. Inspect its source and limitations before use: "
            "finite grids may miss close or weak kinks; signs and scales are ambiguous, and completeness "
            "is not certified. Keep a delivered solution self-contained when it must run in a fresh environment.\n")


def prepare_public_runtime(target, scope):
    helper = {}
    if reusable_helper_instructions(scope):
        source = Path(__file__).with_name("relu_recovery.py")
        prepared = target.exec("mkdir -p /opt/course-tools && test ! -e " + RELU_HELPER_PATH, timeout=10)
        if prepared["returncode"]:
            raise RuntimeError("Reusable numerical helper destination is not fresh: " + prepared["stderr"])
        target.upload_file(source, RELU_HELPER_PATH)
        checksum = hashlib.sha256(source.read_bytes()).hexdigest()
        verified = target.exec("chmod 444 " + RELU_HELPER_PATH + " && sha256sum " + RELU_HELPER_PATH, timeout=10)
        if verified["returncode"] or verified["stdout"].split() != [checksum, RELU_HELPER_PATH]:
            raise RuntimeError("Reusable numerical helper transfer failed its source digest check")
        helper = {"reusable_helper": {"name": "relu_directions", "path": RELU_HELPER_PATH,
                                      "sha256": checksum, "all_configurations": True}}
    if not scope or not scope.get("python", "").startswith("/opt/course-runtime/"):
        return helper or None
    started = time.monotonic()
    archive = Path(os.environ["COURSE_TERMINAL_PYTHON"])
    target.upload_file(archive, "/course-public-python.tar.gz", timeout=60)
    result = target.exec("mkdir -p /opt/course-runtime && tar -xzf /course-public-python.tar.gz -C /opt/course-runtime --strip-components=1 && /opt/course-runtime/bin/python3 --version && test ! -e /usr/local/bin/python3 && ln -s /opt/course-runtime/bin/python3 /usr/local/bin/python3", timeout=90)
    if result["returncode"]:
        raise RuntimeError("Public Python runtime setup failed: " + result["stderr"])
    return {"source": archive.name, "python": result["stdout"].strip(), "seconds": time.monotonic() - started,
            "all_configurations": True, **helper}
