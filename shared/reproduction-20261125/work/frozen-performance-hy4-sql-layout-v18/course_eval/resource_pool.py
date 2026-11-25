import fcntl
import json
import os
import subprocess
import time
from pathlib import Path


class ResourceLease:
    def __init__(self, pool, *, exclusive, label):
        self.pool, self.exclusive, self.label = Path(pool), exclusive, label
        self.main = None
        self.slot = None
        self.marker = None

    def __enter__(self):
        self.pool.mkdir(parents=True, exist_ok=True)
        waiters = self.pool / "exclusive-waiters"
        waiters.mkdir(exist_ok=True)
        if self.exclusive:
            self.marker = waiters / (str(os.getpid()) + ".json")
            self.marker.write_text(json.dumps({"pid": os.getpid(), "label": self.label}) + "\n")
        self.main = (self.pool / "whole-vm.lock").open("a")
        mode = fcntl.LOCK_EX if self.exclusive else fcntl.LOCK_SH
        while True:
            for marker in waiters.glob("[0-9]*.json"):
                try:
                    os.kill(int(marker.stem), 0)
                except ProcessLookupError:
                    marker.unlink(missing_ok=True)
            if not self.exclusive and any(waiters.glob("[0-9]*.json")):
                time.sleep(1)
                continue
            try:
                fcntl.flock(self.main, mode | fcntl.LOCK_NB)
            except BlockingIOError:
                time.sleep(1)
                continue
            if self.exclusive:
                return self
            for index in range(2):
                handle = (self.pool / ("light-slot-" + str(index) + ".lock")).open("a")
                try:
                    fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    self.slot = handle
                    return self
                except BlockingIOError:
                    handle.close()
            fcntl.flock(self.main, fcntl.LOCK_UN)
            time.sleep(1)

    def __exit__(self, exc_type, exc, traceback):
        if self.slot is not None:
            self.slot.close()
        if self.main is not None:
            self.main.close()
        if self.marker is not None:
            self.marker.unlink(missing_ok=True)


def task_requires_exclusive(task):
    return task["benchmark"] == "swe" or task["id"] in {"query-optimize", "tune-mjcf"}


def image_cleanup_needed(root, environment):
    output = subprocess.check_output([str(root / "work/vendor/bin/limactl"), "shell", "c", "df", "-Pk", "/"],
        env=environment | {"LIMA_HOME": str(root / ".v")}, text=True)
    return int(output.splitlines()[-1].split()[3]) * 1024 < 12 * 1024**3
