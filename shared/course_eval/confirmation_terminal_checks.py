import ast
import csv
import datetime
import json
import math
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
from collections import Counter, defaultdict
from pathlib import Path


CHECK_DEADLINE = None


def condition(name, passed, actual, required):
    return {"id": name, "passed": bool(passed), "actual": actual, "required": required}


def log_summary():
    today = datetime.date(2025, 8, 12)
    wanted = Counter()
    levels = ("ERROR", "WARNING", "INFO")
    periods = ("today", "last_7_days", "last_30_days", "month_to_date", "total")
    for path in Path("/app/logs").glob("*.log"):
        date = datetime.date.fromisoformat(path.name.split("_", 1)[0])
        age = (today - date).days
        included = {"today": age == 0, "last_7_days": 0 <= age < 7,
                    "last_30_days": 0 <= age < 30,
                    "month_to_date": date.replace(day=1) == today.replace(day=1) and date <= today, "total": True}
        for line in path.read_text().splitlines():
            match = re.match(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} \[(\w+)\]", line)
            if match and match.group(1) in levels:
                for period, include in included.items():
                    if include:
                        wanted[(period, match.group(1))] += 1
    with Path("/app/summary.csv").open(newline="") as handle:
        reader = csv.DictReader(handle)
        columns = reader.fieldnames
        rows = list(reader)
    expected = [{"period": period, "severity": level, "count": str(wanted[(period, level)])}
                for period in periods for level in levels]
    differences = [{"row": index, "actual": actual, "required": required}
                   for index, (actual, required) in enumerate(zip(rows, expected)) if actual != required]
    return [condition("csv_header", columns == ["period", "severity", "count"], columns, ["period", "severity", "count"]),
            condition("all_period_counts", rows == expected, {"rows": len(rows), "differences": differences},
                      {"rows": 15, "all_counts": "counts from bracketed severity field, not message text"})]


def distribution():
    import numpy as np
    values = np.load("/app/dist.npy", allow_pickle=False)
    valid = (values.shape == (150000,) and np.issubdtype(values.dtype, np.floating)
             and np.isfinite(values).all() and (values > 0).all())
    conditions = [condition("distribution_shape_positive", valid, {"shape": list(values.shape)}, "150000 finite positive values")]
    if valid:
        total = math.fsum(float(value) for value in values)
        forward = float(np.sum(values * np.log(values * values.size)))
        backward = float(np.mean(-np.log(values * values.size)))
        tolerance = max(1e-12, 4 * float(np.finfo(values.dtype).eps))
        conditions.extend([condition("normalization", abs(total - 1) <= tolerance, total,
                                     {"sum": 1, "floating_point_tolerance": tolerance}),
                           condition("forward_KL", abs(forward - 10) <= .001, forward, "10 ± 0.001"),
                           condition("backward_KL", abs(backward - 10) <= .001, backward, "10 ± 0.001")])
    return conditions


def recovered_db():
    rows = json.loads(Path("/app/recovered.json").read_text())
    valid = isinstance(rows, list) and all(isinstance(row, dict) for row in rows)
    ids = [row.get("id") for row in rows] if valid else None
    conditions = [condition("eleven_ordered_records", valid and ids == list(range(1, 12)), ids, list(range(1, 12))),
                  condition("record_fields", valid and all(set(row) == {"id", "name", "value"}
                            and type(row["id"]) is int and isinstance(row["name"], str)
                            and type(row["value"]) is int for row in rows),
                            "record structure", "integer id/value and string name, from the visible SQLite schema")]
    # SQLite 可能创建或清理 WAL/SHM；在副本中读取，避免检查改变候选。
    with scratch_directory("wal-") as directory:
        copied = Path(directory) / "main.db"
        shutil.copyfile("/app/main.db", copied)
        wal = Path("/app/main.db-wal")
        if wal.exists():
            shutil.copyfile(wal, str(copied) + "-wal")
        connection = sqlite3.connect(copied.as_uri() + "?mode=ro", uri=True)
        try:
            recovered = [dict(zip(("id", "name", "value"), row))
                         for row in connection.execute("SELECT id, name, value FROM items ORDER BY id")]
        finally:
            connection.close()
    conditions.append(condition("readable_repaired_database", valid and rows == recovered and len(recovered) == 11,
                                {"sqlite_rows": len(recovered), "json_matches_database": rows == recovered},
                                "SQLite reads all 11 rows from the repaired database/WAL and JSON matches them"))
    return conditions


def flag():
    content = Path("/app/results.txt").read_text().strip()
    okay = re.fullmatch(r"FLAG\{[^{}\r\n]+\}", content) is not None
    return [condition("flag_output_format", okay, {"characters": len(content)}, "one FLAG{...}; actual secret identity remains unverified")]


def plaintexts():
    inputs = Path("/app/ciphertexts.txt").read_text().splitlines()
    output = Path("/app/plaintexts.txt").read_text()
    # 题面只要求将答案保存到文件，没有规定独占行或禁止诊断文字。
    numbers = [int(value) for value in re.findall(r"(?<![\w.-])\d+(?![\w.])", output)]
    representable = [value for value in numbers if 0 <= value < 2**64]
    return [condition("plaintext_payload_present", len(representable) >= len(inputs),
                      {"uint64_tokens": len(representable), "ciphertext_count": len(inputs)},
                      "enough decimal uint64 tokens for the public decrypt.c output; actual plaintext identity, ordering and diagnostic disambiguation remain unverified")]


CLIMATE_PROBE = """import codecs,json,runpy,sys
from pathlib import Path
import pandas as pd
import pandas.io.parsers as parsers
import pandas.io.parsers.readers as readers
observed=[]
original=pd.read_csv
def read_csv(*args,**kwargs):
    value=original(*args,**kwargs)
    source=args[0] if args else kwargs.get('filepath_or_buffer')
    encoding=kwargs.get('encoding') or getattr(source,'encoding',None) or 'utf-8'
    path=source if isinstance(source,(str,Path)) else getattr(source,'name',source)
    observed.append({'path':str(Path(path).resolve()),
                     'encoding':codecs.lookup(encoding).name})
    return value
pd.read_csv=read_csv
parsers.read_csv=read_csv
readers.read_csv=read_csv
metadata=Path(sys.argv[1])
sys.argv=['/app/analyze_climate_modern.py']
try:
    runpy.run_path(sys.argv[0],run_name='__main__')
except SystemExit as error:
    if error.code not in (None,0):
        raise
finally:
    metadata.write_text(json.dumps(observed))
"""


def climate_dependencies():
    import tomllib
    from packaging.requirements import Requirement
    from packaging.utils import canonicalize_name
    results = []
    for path in (Path("/app/requirements.txt"), Path("/app/pyproject.toml")):
        if not path.is_file():
            continue
        try:
            if path.suffix == ".txt":
                requirements = [Requirement(line.split("#", 1)[0].strip())
                                for line in path.read_text().splitlines()
                                if line.strip() and not line.lstrip().startswith("#")]
            else:
                content = tomllib.loads(path.read_text())
                strings = list(content.get("project", {}).get("dependencies", []))
                for name, version in content.get("tool", {}).get("poetry", {}).get("dependencies", {}).items():
                    if name.lower() == "python":
                        continue
                    version = version.get("version", "") if isinstance(version, dict) else version
                    strings.append(name + version)
                requirements = [Requirement(value) for value in strings]
            constrained = {canonicalize_name(item.name) for item in requirements
                           if any(spec.operator in {">=", "==", "~="} for spec in item.specifier)}
            valid = {"numpy", "pandas"}.issubset(constrained) and bool(constrained & {"matplotlib", "scipy"})
            results.append({"file": str(path), "valid": valid, "constrained_packages": sorted(constrained)})
        except (OSError, ValueError, TypeError) as error:
            results.append({"file": str(path), "valid": False, "error": str(error)})
    return condition("dependency_file", any(item["valid"] for item in results), results,
                     "requirements.txt OR pyproject.toml specifies numpy, pandas and matplotlib or scipy with >=, == or ~= constraints")


def climate():
    source = Path("/app/analyze_climate_modern.py").read_text()
    tree = ast.parse(source)
    path_aliases, module_aliases = set(), set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "pathlib":
            path_aliases.update(item.asname or item.name for item in node.names if item.name == "Path")
        elif isinstance(node, ast.Import):
            module_aliases.update(item.asname or item.name for item in node.names if item.name == "pathlib")
    uses_path = any(isinstance(node, ast.Call) and (
        isinstance(node.func, ast.Name) and node.func.id in path_aliases
        or isinstance(node.func, ast.Attribute) and node.func.attr == "Path"
        and isinstance(node.func.value, ast.Name) and node.func.value.id in module_aliases)
        for node in ast.walk(tree))
    temperatures = defaultdict(list)
    csv_path = Path("/app/climate_analyzer/sample_data/climate_data.csv")
    with csv_path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            temperatures[int(row["station_id"])].append(float(row["temperature"]))
    expected = {station: f"Station {station} mean temperature: {math.fsum(values)/len(values):.1f}°C"
                for station, values in temperatures.items() if station in {101, 102}}
    with scratch_directory("climate-") as directory:
        metadata = Path(directory) / "read_csv.json"
        execution = command_result([sys.executable, "-W", "error::DeprecationWarning", "-W", "error::FutureWarning",
                                    "-c", CLIMATE_PROBE, str(metadata)], cwd="/app", seconds=25)
        observed = json.loads(metadata.read_text()) if execution["returncode"] == 0 else []
    reads_input = any(Path(item["path"]).resolve() == csv_path
                      and isinstance(item["encoding"], str)
                      and item["encoding"] in {"utf-8", "utf-8-sig"}
                      for item in observed)
    lines = execution["stdout"].splitlines()
    matching = [line for line in lines if re.fullmatch(r"Station (101|102) mean temperature: -?\d+\.\d°C", line)]
    return [condition("modern_python_execution", execution["returncode"] == 0, execution,
                      "runs under current Python without deprecated-API warnings"),
            condition("pathlib_paths", uses_path, uses_path, "calls pathlib.Path using its imported name or alias"),
            condition("pandas_utf8_input", reads_input, observed, "reads the original CSV with pandas using UTF-8, including its UTF-8 default"),
            condition("both_station_means", set(expected) == {101, 102} and sorted(matching) == sorted(expected.values()),
                      matching, list(expected.values())), climate_dependencies()]


def merged_users():
    import pandas as pd
    mapping = {"user_id": "user_id", "id": "user_id", "userId": "user_id", "email": "email",
               "email_address": "email", "full_name": "name", "name": "name", "userName": "name",
               "registration_date": "created_date", "created_at": "created_date", "joined": "created_date",
               "status": "status"}
    source_rows = [json.loads(Path("/data/source_a/users.json").read_text()),
                   pd.read_csv("/data/source_b/users.csv").to_dict("records"),
                   pd.read_parquet("/data/source_c/users.parquet").to_dict("records")]
    values = defaultdict(lambda: defaultdict(dict))
    for source, rows in zip(("source_a", "source_b", "source_c"), source_rows):
        for row in rows:
            normalized = {mapping[key]: value for key, value in row.items() if key in mapping and pd.notna(value)}
            identifier = int(normalized.pop("user_id"))
            for key, value in normalized.items():
                values[identifier][key][source] = str(value)
    expected = {identifier: {field: next(iter(items.values())) for field, items in fields.items()}
                for identifier, fields in values.items()}
    expected_conflicts = {(identifier, field): items for identifier, fields in values.items()
                          for field, items in fields.items() if len(set(items.values())) > 1}
    output = pd.read_parquet("/app/merged_users.parquet")
    required_columns = {"user_id", "name", "email", "created_date"}
    valid_columns = required_columns.issubset(output.columns) and set(output.columns).issubset(required_columns | {"status"})
    ids = output["user_id"].tolist()
    differences = []
    if len(ids) == len(set(ids)) and set(ids) == set(expected):
        for row in output.to_dict("records"):
            for field, value in expected[int(row["user_id"])].items():
                if field == "status" and "status" not in output.columns:
                    continue
                if str(row.get(field)) != value:
                    differences.append({"user_id": int(row["user_id"]), "field": field,
                                        "actual": str(row.get(field)), "required": value})
    else:
        differences.append({"ids": ids, "required_ids": sorted(expected)})
    report = json.loads(Path("/app/conflicts.json").read_text())
    conflicts = report["conflicts"]
    found = {(int(item["user_id"]), item["field"]): item for item in conflicts}
    exact = (type(report["total_conflicts"]) is int and len(found) == len(conflicts) == report["total_conflicts"]
             and set(found) == set(expected_conflicts))
    if exact:
        for key, items in expected_conflicts.items():
            actual = found[key]
            exact = exact and actual["values"] == items and actual["selected"] == next(iter(items.values()))
    valid_types = (pd.api.types.is_integer_dtype(output["user_id"].dtype)
                   and all(isinstance(value, str) for name in ("name", "email") for value in output[name]))
    dates = output["created_date"].tolist()
    dates_ok = all(isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value)
                   and datetime.date.fromisoformat(value).isoformat() == value for value in dates)
    if "status" in output.columns:
        valid_types = valid_types and all(pd.isna(value) or isinstance(value, str) for value in output["status"])
    return [condition("parquet_columns", valid_columns, list(output.columns), sorted(required_columns) + ["optional: status"]),
            condition("priority_merge", not differences, differences, "all users and mapped fields follow A>B>C priority"),
            condition("conflict_report", exact, {"count": len(conflicts), "declared": report["total_conflicts"]},
                      {"count": len(expected_conflicts), "values": "all differing source values and selected priority value"}),
            condition("parquet_types", valid_types and dates_ok, {"id_dtype": str(output["user_id"].dtype), "dates": dates},
                      "integer user_id; YYYY-MM-DD date strings")]


def scratch_directory(prefix):
    root = Path.cwd() / ".course-public-check"
    root.mkdir(exist_ok=True)
    return tempfile.TemporaryDirectory(prefix=prefix, dir=root)


def command_result(arguments, *, cwd, seconds=25, input_text=None):
    if CHECK_DEADLINE is not None:
        remaining = CHECK_DEADLINE - time.monotonic()
        if remaining <= 0:
            raise subprocess.TimeoutExpired(arguments, 55)
        seconds = min(seconds, remaining)
    completed = subprocess.run(arguments, cwd=cwd, input=input_text, capture_output=True,
                               text=True, timeout=seconds, check=False)
    return {"returncode": completed.returncode, "stdout": completed.stdout[-12000:],
            "stderr": completed.stderr[-12000:]}


def coq_proof():
    source = Path("/workspace/plus_comm.v")
    compiled = Path("/workspace/plus_comm.vo")
    conditions = [condition("compiled_proof_present", compiled.is_file() and compiled.stat().st_size > 0,
                            compiled.exists(), "nonempty /workspace/plus_comm.vo")]
    with scratch_directory("coq-") as directory:
        root = Path(directory)
        # 编译副本以免 .aux/.glob 等编译副产物改变交付文件。
        shutil.copyfile(source, root / "plus_comm.v")
        compilation = command_result(["coqc", "-q", "-noglob", "plus_comm.v"], cwd=root)
        conditions.append(condition("source_compiles", compilation["returncode"] == 0, compilation,
                                    "coqc accepts the completed source proof"))
        if compilation["returncode"] == 0:
            probe = ("Require Import plus_comm.\n"
                     "Definition course_public_theorem : forall n m : nat, n + m = m + n := plus_comm.plus_comm.\n"
                     "Print Assumptions course_public_theorem.\n")
            source_probe = command_result(["coqtop", "-q", "-quiet"], cwd=root, input_text=probe)
            source_closed = (source_probe["returncode"] == 0 and "Error:" not in source_probe["stderr"]
                             and "Closed under the global context" in source_probe["stdout"])
            conditions.append(condition("source_theorem_closed", source_closed, source_probe,
                                        "the required forall n m theorem has no unproven assumptions"))
            if compiled.is_file():
                shutil.copyfile(compiled, root / "plus_comm.vo")
                object_probe = command_result(["coqtop", "-q", "-quiet"], cwd=root, input_text=probe)
                object_closed = (object_probe["returncode"] == 0 and "Error:" not in object_probe["stderr"]
                                 and "Closed under the global context" in object_probe["stdout"])
                conditions.append(condition("compiled_theorem_closed", object_closed, object_probe,
                                            "delivered plus_comm.vo contains the required theorem without unproven assumptions"))
    return conditions


def bottle():
    rows = [json.loads(line) for line in Path("/app/report.jsonl").read_text().splitlines()]
    report_valid = bool(rows) and all(isinstance(row, dict)
        and row.get("file_path") == "/app/bottle.py" and isinstance(row.get("cwe_id"), list)
        and bool(row["cwe_id"]) and all(isinstance(value, str) and re.fullmatch(r"cwe-\d+", value, re.IGNORECASE)
                                       for value in row["cwe_id"]) for row in rows)
    suite = command_result([sys.executable, "-m", "pytest", "-rA"], cwd="/app", seconds=50)
    return [condition("vulnerability_report", report_valid, {"records": len(rows)},
                      "JSON Lines records with /app/bottle.py and nonempty cwe-N lists; exact CWE identity remains unverified"),
            condition("visible_repository_tests", suite["returncode"] == 0, suite,
                      "the original task-visible pytest -rA suite passes")]


def polyglot():
    source = Path("/app/polyglot/main.rs")
    conditions = []
    with scratch_directory("polyglot-") as directory:
        root = Path(directory)
        for language, command, executable in (
            ("rust", ["rustc", str(source), "-o", str(root / "main")], root / "main"),
            ("cpp", ["g++", "-x", "c++", str(source), "-o", str(root / "cmain")], root / "cmain"),
        ):
            compilation = command_result(command, cwd=root, seconds=20)
            conditions.append(condition(language + "_compiles", compilation["returncode"] == 0, compilation,
                                        "compile the same main.rs with the public compiler command"))
            if compilation["returncode"]:
                continue
            differences = []
            for number in tuple(range(11)) + (20, 30, 40):
                left, right = 1, 1
                for _ in range(number):
                    left, right = right, left + right
                actual = command_result([str(executable), str(number)], cwd=root, seconds=2)
                if actual["returncode"] or actual["stdout"].strip() != str(left):
                    differences.append({"n": number, "required": left, **actual})
            conditions.append(condition(language + "_fibonacci", not differences, differences,
                                        "f(0)=f(1)=1 and recurrence for n=0..10,20,30,40; untested n remain unverified"))
    return conditions


CHECKS = {"log-summary-date-ranges": log_summary, "distribution-search": distribution,
          "db-wal-recovery": recovered_db, "vulnerable-secret": flag,
          "feal-linear-cryptanalysis": plaintexts, "modernize-scientific-stack": climate,
          "multi-source-data-merger": merged_users, "prove-plus-comm": coq_proof,
          "fix-code-vulnerability": bottle, "polyglot-rust-c": polyglot}

LIMITATIONS = {
    "vulnerable-secret": "Only the public FLAG output format is checked; secret identity is unverified.",
    "feal-linear-cryptanalysis": "Only readable numeric payload capacity is checked; the task does not prohibit diagnostic text. Key, plaintext truth, ordering and diagnostic disambiguation remain unverified.",
    "distribution-search": "The specified dist.npy is checked; the unspecified Python script and its provenance are outside the fixed artifact scope.",
    "db-wal-recovery": "JSON is compared to the repaired SQLite state; the original encrypted WAL truth remains for independent grading.",
    "fix-code-vulnerability": "The report format and original visible tests are checked; exact CWE identity and hidden security cases are unverified.",
    "polyglot-rust-c": "Both compilers and the listed finite Fibonacci cases are checked; arbitrary larger inputs are unverified.",
}


def main():
    global CHECK_DEADLINE
    CHECK_DEADLINE = time.monotonic() + 55
    try:
        conditions = CHECKS[sys.argv[1]]()
    except subprocess.TimeoutExpired as exc:
        print(json.dumps({"passed": None, "conditions": [{"id": "public_check_completed", "passed": None,
                          "actual": {"timeout_seconds": exc.timeout}, "required": "public check completes"}],
                          "status": "unknown"}))
        raise SystemExit(2) from None
    except (OSError, ValueError, KeyError, TypeError, SyntaxError, sqlite3.Error) as exc:
        conditions = [condition("required_artifact", False, {"error": type(exc).__name__, "detail": str(exc)},
                                "readable artifact satisfying the public format")]
    passed = all(item["passed"] for item in conditions)
    print(json.dumps({"passed": passed, "conditions": conditions,
                      "coverage_limit": LIMITATIONS.get(sys.argv[1])}, ensure_ascii=True, allow_nan=False))
    raise SystemExit(0 if passed else 1)


if __name__ == "__main__":
    main()
