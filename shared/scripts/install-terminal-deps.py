import concurrent.futures
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from course_eval.terminal_setup import dependency_key, offline_spec


root = Path("work")
tasks = next((root / "datasets").glob("terminal-bench-2-1-*")) / "tasks"
manifest = json.loads(Path(sys.argv[1]).read_text())
sets = set()
for task in manifest["selected"]:
    if task["benchmark"] != "terminal":
        continue
    try:
        interpreter, deps, _ = offline_spec((tasks / task["id"] / "tests/test.sh").read_text())
    except ValueError as exc:
        print(f"Needs original bootstrap: {task['id']}: {exc}", flush=True)
        continue
    sets.add((interpreter, deps))


def install(spec: tuple[str, tuple[str, ...]]) -> None:
    interpreter, deps = spec
    version = "3.12" if interpreter.endswith("3.12") else "3.13"
    target = root / "terminal-runtime/deps" / dependency_key(interpreter, deps)
    if target.with_name(target.name + ".tar.gz").is_file():
        return
    if not all((target / f"{name.replace('-', '_')}-{version}.dist-info").is_dir()
               for name, version in (dep.split("==", 1) for dep in deps)):
        env = os.environ | {"UV_CACHE_DIR": str((root / "uv-cache").resolve()), "UV_HTTP_TIMEOUT": "150"}
        subprocess.run([
            "uv", "pip", "install", "--target", str(target), "--index-url",
            "https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple", "--python-version", version,
            "--python-platform", "x86_64-manylinux_2_28", "--only-binary", ":all:", *deps,
        ], env=env, check=True)
    archive = shutil.make_archive(str(target) + ".building", "gztar", root_dir=target)
    Path(archive).rename(target.with_name(target.name + ".tar.gz"))


with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
    for _ in executor.map(install, sorted(sets)):
        pass
