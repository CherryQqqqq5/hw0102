import shlex
from pathlib import Path, PurePosixPath

from course_eval.verification import PublicCheck


TERMINAL_TASKS = {
    "vulnerable-secret": {
        "artifacts": ("/app/results.txt",), "inputs": ("/app/vulnerable",),
        "coverage": ("FLAG{...} output format; actual secret identity is unverified",),
    },
    "log-summary-date-ranges": {
        "artifacts": ("/app/summary.csv",), "inputs": (),
        "coverage": ("all 15 counts and required row order from visible logs, using public reference date 2025-08-12",),
    },
    "feal-linear-cryptanalysis": {
        "artifacts": ("/app/plaintexts.txt",),
        "inputs": ("/app/feal.c", "/app/decrypt.c", "/app/pairs.txt", "/app/ciphertexts.txt"),
        "coverage": ("readable output with enough decimal uint64 tokens for the visible decrypt.c output; diagnostic text is allowed; key, plaintext identity and ordering are unverified",),
    },
    "prove-plus-comm": {
        "cwd": "/workspace", "python": "/usr/bin/python3",
        "artifacts": ("/workspace/plus_comm.v", "/workspace/plus_comm.vo"), "inputs": (),
        "coverage": ("coqc accepts source; source and delivered object expose the required addition-commutativity theorem without unproven assumptions",),
    },
    "modernize-scientific-stack": {
        "artifacts": ("/app/analyze_climate_modern.py", "/app/requirements.txt", "/app/pyproject.toml"),
        "deliverables": ("/app/analyze_climate_modern.py",),
        "inputs": ("/app/climate_analyzer/analyze_climate.py", "/app/climate_analyzer/sample_data/climate_data.csv",
                   "/app/climate_analyzer/config.ini"),
        "coverage": ("current-Python execution, pathlib.Path use, real pandas UTF-8 CSV read, exact station 101/102 mean output",
                     "requirements.txt OR pyproject.toml contains the specified constrained dependencies"),
    },
    "distribution-search": {
        "artifacts": ("/app/dist.npy",), "inputs": (),
        "coverage": ("150000 finite positive probabilities, numerical normalization, forward and backward KL within public 0.001 tolerance of 10",
                     "the unspecified Python script and its provenance are not covered by the fixed output scope"),
    },
    "db-wal-recovery": {
        "python": "/usr/bin/python3",
        "artifacts": ("/app/recovered.json", "/app/main.db", "/app/main.db-wal", "/app/main.db-shm"),
        "deliverables": ("/app/recovered.json", "/app/main.db"), "inputs": (),
        "coverage": ("eleven ordered typed JSON records equal the repaired database as read by SQLite on a scratch copy",
                     "original encrypted WAL truth remains for independent grading"),
    },
    "fix-code-vulnerability": {
        "artifacts": ("/app/bottle.py", "/app/report.jsonl"), "inputs": (),
        "coverage": ("report contains bottle.py and nonempty CWE lists; original visible pytest -rA suite passes",
                     "exact CWE identity and hidden security cases remain unverified"),
    },
    "multi-source-data-merger": {
        "artifacts": ("/app/merged_users.parquet", "/app/conflicts.json"),
        "inputs": ("/data/source_a/users.json", "/data/source_b/users.csv", "/data/source_c/users.parquet"),
        "coverage": ("all users, public field mappings, A>B>C field priority, complete conflict values and selected values, output schema and dates",),
    },
    "polyglot-rust-c": {
        "python": "/opt/course-runtime/bin/python3",
        "artifacts": ("/app/polyglot/main.rs",), "inputs": (),
        "coverage": ("same source compiles as Rust and C++; f(0)=f(1)=1 checked at n=0..10,20,30,40",
                     "larger untested inputs remain unverified"),
    },
}


def specification(task):
    task_id = task if isinstance(task, str) else task["id"]
    return task_id, TERMINAL_TASKS[task_id]


def terminal_check(task, instruction):
    task_id, spec = specification(task)
    source = Path(__file__).with_name("confirmation_terminal_checks.py").read_text()
    interpreter = task.get("public_python", spec.get("python", "/usr/local/bin/python3")) if isinstance(task, dict) else spec.get("python", "/usr/local/bin/python3")
    cwd = PurePosixPath(spec.get("cwd", "/app"))
    deliverables = spec.get("deliverables", spec["artifacts"])
    paths = tuple(dict.fromkeys((*deliverables, *spec["inputs"])))
    # 未在题面写出绝对路径的环境文件，使用工作目录内的相对文件名。
    dependencies = tuple(name if name in instruction else str(PurePosixPath(name).relative_to(cwd))
                         for name in paths)
    delivery_paths = tuple(name if name in instruction else str(PurePosixPath(name).relative_to(cwd))
                           for name in deliverables)
    quote = next(line.strip() for line in instruction.splitlines() if line.strip())
    command = shlex.join((interpreter, "-c", source, task_id))
    check = PublicCheck("public-task", quote, command, dependencies, deliverables=delivery_paths,
                        coverage=spec["coverage"], timeout_seconds=60, inconclusive_exit_codes=(2, 124))
    check.validate(instruction)
    return check


def terminal_scope(task, environment_listing):
    task_id, spec = specification(task)
    cwd = PurePosixPath(spec.get("cwd", "/app"))
    lines = environment_listing.splitlines() if isinstance(environment_listing, str) else environment_listing
    protected = set(spec["inputs"])
    artifacts = set(spec["artifacts"])
    for name in lines:
        path = PurePosixPath(name)
        if ".." in path.parts:
            raise ValueError("Unsafe environment listing path: " + name)
        path = path if path.is_absolute() else cwd / path
        if any(part in {".git", "__pycache__", ".pytest_cache", ".course-public-check"} for part in path.parts):
            continue
        if path.suffix in {".pyc", ".pyo"}:
            continue
        if str(path) not in artifacts:
            protected.add(str(path))
    if task_id == "log-summary-date-ranges" and not any(name.startswith("/app/logs/") for name in protected):
        raise ValueError("The pristine log file listing is required to protect all public inputs")
    interpreter = task.get("public_python", spec.get("python", "/usr/local/bin/python3")) if isinstance(task, dict) else spec.get("python", "/usr/local/bin/python3")
    return {"kind": "files", "artifacts": list(spec["artifacts"]),
            "protected": sorted(protected), "python": interpreter}
