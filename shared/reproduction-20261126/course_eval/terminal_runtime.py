import hashlib
import os
import shlex
import time
from pathlib import Path


RELU_HELPER_PATH = "/opt/course-tools/relu_recovery.py"
VIDEO_HELPER_PATH = "/opt/course-tools/video_events.py"


def elf_check_command(binary="/app/a.out", program="/app/extract.js"):
    launcher = ("import sys,runpy;sys.path.insert(0,'/opt/course-tools/pyelftools.whl');"
                "runpy.run_path('/opt/course-tools/elf_memory_check.py',run_name='__main__')")
    return shlex.join(("python3", "-c", launcher, binary, program))


def reusable_helper_instructions(scope):
    name = scope.get("reusable_helper") if scope else None
    if name is None:
        return ""
    if name == "video_events":
        return ("\nA reusable fixed-camera, single-runner video baseline is available at " + VIDEO_HELPER_PATH
            + ". It provides analyze_video(path), returning takeoff_frame, landing_frame and diagnostics. "
            "It estimates a temporal background, keeps planted-foot components, follows the runner's traversal "
            "and brackets sustained flight by observed ground contact. It receives only video pixels, not event labels. "
            "Inspect and run this baseline on the task-visible example before developing a replacement. "
            "Revise it only after finding a concrete failure or unmet public requirement. Its fixed-scene masks "
            "are heuristic; missing observable contact boundaries raise an error instead of supplying guessed indices. "
            "Keep the delivered script self-contained by embedding the necessary method source, with the required "
            "command-line input and TOML output. Do not depend on /opt/course-tools in the delivery environment.\n")
    if name == "elf_memory_check":
        return ("\nA public ELF memory coverage checker is available at /opt/course-tools/elf_memory_check.py, "
            "with the pyelftools wheel at /opt/course-tools/pyelftools.whl. The registered public check "
            "compares unsigned 32-bit words at PT_LOAD virtual addresses of the provided binary. "
            "This is an independent public diagnostic, not the hidden reference scorer. "
            "Use it to detect incomplete extraction and inconsistent values. The delivered extract.js "
            "must run in the original environment without these added verification files. "
            "Run the checker with: " + elf_check_command() + "\n")
    if name != "relu_directions":
        raise ValueError("Unknown reusable numerical helper: " + str(name))
    return ("\nReusable numerical baseline source is available at " + RELU_HELPER_PATH
            + ". It provides recover_relu_directions(oracle, dimension), returning (rows, diagnostics). "
            "It queries a scalar one-hidden-layer ReLU oracle and estimates input-weight row directions "
            "without receiving the unknown width or weights. Inspect and run this baseline on the callable oracle "
            "before developing a replacement. Record its diagnostics, and revise the method only after identifying "
            "a concrete numerical failure or an unmet task requirement. Its limitations are explicit: "
            "finite grids may miss close or weak kinks; signs and scales are ambiguous, and completeness "
            "is not certified. Preserve the critical-witness precision refinement when embedding this method; "
            "coarse directional similarity and a small output-fit RMSE do not verify recovered weights. "
            "The registered numerical check compares the saved rows with fresh query-derived directions, "
            "up to permutation and scaling; it remains a finite-query consistency check. "
            "Query only the public callable oracle; do not inspect its implementation, "
            "globals or private weight artifacts. Infer unknown width from queries. "
            "Keep a delivered solution self-contained when it must run in a fresh environment.\n")


def relu_check_command():
    return ("test -s /app/steal.py && test -s /app/stolen_A1.npy && python3 -m py_compile /app/steal.py"
            " && cd /app && python3 -c 'import json,sys,numpy as np; "
            "sys.path.insert(0,\"/opt/course-tools\"); "
            "from relu_recovery import validate_saved_directions; from forward import forward; "
            "report=validate_saved_directions(forward,10,np.load(\"/app/stolen_A1.npy\",allow_pickle=False)); "
            "print(json.dumps(report)); assert report[\"passed\"],\"Saved directions disagree with fresh oracle queries\"'")


def prepare_public_runtime(target, scope):
    helper = {}
    instructions = reusable_helper_instructions(scope)
    if instructions and scope["reusable_helper"] == "elf_memory_check":
        wheel = Path(os.environ["COURSE_ELF_PUBLIC_WHEEL"])
        expected = "f215ad5f47d3f1373a21496a6c9e0707c622840d0622f23ff7ce08678b020036"
        if hashlib.sha256(wheel.read_bytes()).hexdigest() != expected:
            raise ValueError("The public ELF parser wheel differs from its pinned official release")
        files = []
        for source, destination in ((Path(__file__).with_name("elf_memory_check.py"),
                                    "/opt/course-tools/elf_memory_check.py"),
                                   (wheel, "/opt/course-tools/pyelftools.whl")):
            prepared = target.exec("mkdir -p /opt/course-tools && test ! -e " + destination, timeout=10)
            if prepared["returncode"]:
                raise RuntimeError("The isolated ELF checker destination is not fresh")
            target.upload_file(source, destination)
            checksum = hashlib.sha256(source.read_bytes()).hexdigest()
            verified = target.exec("chmod 444 " + destination + " && sha256sum " + destination, timeout=10)
            if verified["returncode"] or verified["stdout"].split() != [checksum, destination]:
                raise RuntimeError("The isolated ELF checker transfer differs from its source")
            files.append({"path": destination, "sha256": checksum})
        helper = {"reusable_helper": {"name": "elf_memory_check", "files": files, "all_configurations": True}}
    elif instructions:
        name = scope["reusable_helper"]
        destination = VIDEO_HELPER_PATH if name == "video_events" else RELU_HELPER_PATH
        source = Path(__file__).with_name("video_events.py" if name == "video_events" else "relu_recovery.py")
        prepared = target.exec("mkdir -p /opt/course-tools && test ! -e " + destination, timeout=10)
        if prepared["returncode"]:
            raise RuntimeError("Reusable helper destination is not fresh: " + prepared["stderr"])
        target.upload_file(source, destination)
        checksum = hashlib.sha256(source.read_bytes()).hexdigest()
        verified = target.exec("chmod 444 " + destination + " && sha256sum " + destination, timeout=10)
        if verified["returncode"] or verified["stdout"].split() != [checksum, destination]:
            raise RuntimeError("Reusable helper transfer failed its source digest check")
        helper = {"reusable_helper": {"name": name, "path": destination,
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
