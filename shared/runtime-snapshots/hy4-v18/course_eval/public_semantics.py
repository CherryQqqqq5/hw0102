from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sqlite3
import statistics
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


SCHEDULER_LIMITS = {
    1: {"cost": 3.0e11, "pad_ratio": 0.055, "p95_latency_ms": 2.1e6,
        "sequential_timecost": 2.7e8},
    2: {"cost": 4.8e10, "pad_ratio": 0.15, "p95_latency_ms": 2.1e5,
        "sequential_timecost": 3.2e7},
}
SCHEMA_VERSION = 1
SQL_LEXICAL_REGIONS = re.compile(
    r"'(?:''|[^'])*'|\"(?:\"\"|[^\"])*\"|`(?:``|[^`])*`|\[[^\]]*\]"
    r"|--[^\r\n]*|/\*[\s\S]*?(?:\*/|$)"
)


def file_digest(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def input_files(root: Path) -> dict[str, str]:
    directory = root / "input_data"
    if not directory.is_dir():
        raise FileNotFoundError(directory)
    return {str(path.relative_to(root)): file_digest(path)
            for path in sorted(directory.rglob("*")) if path.is_file()}


def capture_baseline(task: str, root: Path) -> dict[str, Any]:
    if task == "scheduler":
        files = input_files(root)
        for bucket in (1, 2):
            if f"input_data/requests_bucket_{bucket}.jsonl" not in files:
                raise ValueError(f"Missing public input bucket {bucket}")
        return {"schema_version": SCHEMA_VERSION, "task": task, "files": files}
    if task == "query":
        sql = (root / "my-sql-query.sql").read_text(encoding="utf-8")
        return {"schema_version": SCHEMA_VERSION, "task": task,
                "files": {"oewn.sqlite": file_digest(root / "oewn.sqlite")},
                "original_sql": sql}
    raise ValueError(f"Unsupported public task: {task}")


def result() -> dict[str, Any]:
    return {"conditions": [], "metrics": {}, "passed": False}


def condition(report: dict[str, Any], name: str, passed: bool | None,
              actual: Any, required: Any) -> None:
    report["conditions"].append({"id": name, "passed": passed,
                                 "status": "unknown" if passed is None else "pass" if passed else "fail",
                                 "actual": actual, "required": required})


def finish(report: dict[str, Any]) -> dict[str, Any]:
    values = [item["passed"] for item in report["conditions"]]
    report["passed"] = (False if not values or False in values else
                        None if None in values else True)
    return report


def validate_baseline(baseline: dict[str, Any], task: str) -> None:
    if baseline.get("schema_version") != SCHEMA_VERSION or baseline.get("task") != task:
        raise ValueError("Baseline schema version or task does not match")
    files = baseline.get("files")
    if not isinstance(files, dict) or not files or not all(
        isinstance(name, str) and isinstance(value, str)
        and re.fullmatch(r"[0-9a-f]{64}", value) for name, value in files.items()
    ):
        raise ValueError("Baseline must contain the pristine public file digests")
    required = ({"oewn.sqlite"} if task == "query" else
                {f"input_data/requests_bucket_{bucket}.jsonl" for bucket in (1, 2)})
    if not required.issubset(files):
        raise ValueError("Baseline lacks required public input files")
    if task == "query" and not isinstance(baseline.get("original_sql"), str):
        raise ValueError("Query baseline lacks the original public SQL")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open(encoding="utf-8") as handle:
        for number, line in enumerate(handle, 1):
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{number}: expected a JSON object")
            rows.append(value)
    return rows


def scheduler_metrics(requests: dict[str, dict[str, Any]],
                      plan: list[dict[str, Any]]) -> dict[str, Any]:
    # 公式逐项来自公开 cost_model.py；候选目录中的 Python 文件不会被执行。
    batches: dict[str, list[dict[str, Any]]] = defaultdict(list)
    shapes = {}
    for row in plan:
        batches[row["batch_id"]].append(requests[row["request_id"]])
        shape = row["shape"]
        shapes[row["batch_id"]] = tuple(shape[key] for key in
                                       ("seq_align", "heads_align", "hidden_align"))
    cost = 0.0
    pad_tokens = real_tokens = 0
    latencies = {}
    for batch, rows in batches.items():
        aligned = [((row["prompt_len"] + 63) // 64) * 64 for row in rows]
        seq = max(aligned)
        generation = max(row["gen_len"] for row in rows)
        square_sum = (generation * seq * seq + seq * generation * (generation - 1)
                      + generation * (generation - 1) * (2 * generation - 1) // 6)
        linear_sum = generation * seq + generation * (generation - 1) / 2
        cost += sum(2.0 * seq_i ** 2 + seq_i * 4096 for seq_i in aligned)
        cost += len(rows) * (square_sum + 0.5 * 4096 * linear_sum)
        latencies[batch] = [0.002 * seq_i ** 2 + 0.0015 * seq_i * 4096
                            + 0.0012 * square_sum + 0.0006 * 4096 * linear_sum + 8.0
                            for seq_i in aligned]
        pad_tokens += sum(seq_i - row["prompt_len"] + generation - row["gen_len"]
                          for seq_i, row in zip(aligned, rows))
        real_tokens += sum(row["prompt_len"] + row["gen_len"] for row in rows)
    for shape in set(shapes.values()):
        seq = shape[0]
        cost += 500.0 * seq ** 2 + 2.0 * seq * 4096
        first = min(batch for batch, value in shapes.items() if value == shape)
        latencies[first][0] += 1500.0
    cost += 10_000_000.0 * len(batches)
    ordered = sorted(value for values in latencies.values() for value in values)
    return {"cost": cost, "pad_tokens": pad_tokens, "real_tokens": real_tokens,
            "pad_ratio": pad_tokens / max(1, real_tokens),
            "p95_latency_ms": ordered[math.ceil(0.95 * len(ordered)) - 1] if ordered else 0.0,
            "sequential_timecost": sum(max(latencies[batch]) for batch in sorted(latencies)),
            "request_count": len(plan), "batch_count": len(batches),
            "unique_shape_count": len(set(shapes.values()))}


def check_scheduler(root: Path, baseline: dict[str, Any]) -> dict[str, Any]:
    validate_baseline(baseline, "scheduler")
    report = result()
    current = input_files(root)
    changed = sorted(name for name in set(current) | set(baseline["files"])
                     if current.get(name) != baseline["files"].get(name))
    condition(report, "scheduler.input_data_unchanged", not changed,
              {"changed_files": changed}, "identical pristine input_data file set and bytes")
    all_shapes = set()
    for bucket, limits in SCHEDULER_LIMITS.items():
        prefix = f"scheduler.bucket_{bucket}"
        try:
            rows = read_jsonl(root / "input_data" / f"requests_bucket_{bucket}.jsonl")
            plan = read_jsonl(root / "output_data" / f"plan_b{bucket}.jsonl")
            if not rows or not all(isinstance(row.get("request_id"), str)
                                   and type(row.get("prompt_len")) is int
                                   and row["prompt_len"] >= 0
                                   and type(row.get("gen_len")) is int
                                   and row["gen_len"] >= 0 for row in rows):
                raise ValueError("Public request data is empty or has invalid fields")
            requests = {row["request_id"]: row for row in rows}
            if len(requests) != len(rows):
                raise ValueError("Public request data contains duplicate request_id")
            for row in plan:
                shape = row.get("shape")
                if not (isinstance(row.get("request_id"), str)
                        and isinstance(row.get("batch_id"), str)
                        and isinstance(shape, dict)
                        and all(type(shape.get(key)) is int for key in
                                ("seq_align", "heads_align", "hidden_align"))):
                    raise ValueError("Plan requires string request_id/batch_id and integer shape dimensions")
        except (OSError, ValueError) as error:
            condition(report, prefix + ".jsonl_schema", False, str(error),
                      "two readable JSON Lines files with valid request and plan records")
            continue
        condition(report, prefix + ".jsonl_schema", True, len(plan),
                  "one JSON object per line with typed required fields")
        counts = Counter(row["request_id"] for row in plan)
        missing = sorted(set(requests) - counts.keys())
        extra = sorted(counts.keys() - set(requests))
        duplicates = sorted(key for key, value in counts.items() if value != 1)
        coverage = not (missing or extra or duplicates)
        condition(report, prefix + ".request_coverage", coverage,
                  {"missing": missing, "extra": extra, "duplicates": duplicates},
                  "each public request_id appears exactly once in its bucket")
        bad_dimensions, bad_alignment, insufficient = [], [], []
        per_batch: dict[str, set[tuple[int, int, int]]] = defaultdict(set)
        for row in plan:
            shape = row["shape"]
            dimensions = tuple(shape[key] for key in
                               ("seq_align", "heads_align", "hidden_align"))
            all_shapes.add(dimensions)
            per_batch[row["batch_id"]].add(dimensions)
            if shape["heads_align"] != 32 or shape["hidden_align"] != 4096:
                bad_dimensions.append(row["request_id"])
            if shape["seq_align"] % 64:
                bad_alignment.append(row["request_id"])
            request = requests.get(row["request_id"])
            if request is not None and shape["seq_align"] < ((request["prompt_len"] + 63) // 64) * 64:
                insufficient.append(row["request_id"])
        mixed = sorted(batch for batch, values in per_batch.items() if len(values) != 1)
        condition(report, prefix + ".fixed_dimensions", not bad_dimensions,
                  bad_dimensions, {"heads_align": 32, "hidden_align": 4096})
        condition(report, prefix + ".seq_alignment", not bad_alignment,
                  bad_alignment, "seq_align is an integer multiple of 64")
        condition(report, prefix + ".prompt_coverage", not insufficient,
                  insufficient, "seq_align >= ceil(prompt_len / 64) * 64")
        condition(report, prefix + ".batch_shape_consistency", not mixed,
                  mixed, "identical shape within each bucket-local batch_id")
        if coverage and not (bad_dimensions or bad_alignment or insufficient or mixed):
            try:
                measured = scheduler_metrics(requests, plan)
                if not all(math.isfinite(measured[name]) for name in limits):
                    raise ArithmeticError("Public metrics exceed finite numeric range")
            except ArithmeticError as error:
                condition(report, prefix + ".performance_measurable", False,
                          str(error), "finite public metrics below the published limits")
                continue
            report["metrics"][f"bucket_{bucket}"] = measured
            for metric, limit in limits.items():
                condition(report, prefix + "." + metric, measured[metric] < limit,
                          measured[metric], {"operator": "<", "value": limit})
        else:
            condition(report, prefix + ".performance_measurable", False,
                      "invalid plan structure", "valid complete plan before cost measurement")
    report["metrics"]["global_unique_shapes"] = [list(shape) for shape in sorted(all_shapes)]
    condition(report, "scheduler.global_shape_cap", len(all_shapes) <= 8,
              len(all_shapes), {"operator": "<=", "value": 8, "scope": "both buckets"})
    return finish(report)


def sql_comments(sql: str) -> list[str]:
    # 这里只定位引号外的注释；语法和单语句约束交给 SQLite 自身解析。
    return [match.group(0) for match in SQL_LEXICAL_REGIONS.finditer(sql)
            if match.group(0).startswith(("--", "/*"))]


def execute_readonly(database: Path, sql: str, timeout_seconds: float) -> tuple[list, list, float]:
    connection = sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True)
    try:
        connection.execute("PRAGMA query_only=ON")
        connection.execute("PRAGMA temp_store=MEMORY")
        allowed = {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ,
                   sqlite3.SQLITE_FUNCTION, sqlite3.SQLITE_RECURSIVE}
        connection.set_authorizer(lambda action, *_: sqlite3.SQLITE_OK
                                  if action in allowed else sqlite3.SQLITE_DENY)
        deadline = time.perf_counter() + timeout_seconds
        connection.set_progress_handler(lambda: int(time.perf_counter() >= deadline), 1000)
        started = time.perf_counter()
        cursor = connection.execute(sql)
        if cursor.description is None:
            raise ValueError("Expected a result-producing SQLite query")
        columns = [column[0] for column in cursor.description]
        rows = cursor.fetchall()
        return columns, rows, time.perf_counter() - started
    finally:
        connection.close()


def check_query(root: Path, baseline: dict[str, Any], repeats: int = 4,
                timeout_seconds: float = 120.0) -> dict[str, Any]:
    validate_baseline(baseline, "query")
    if repeats < 2 or repeats % 2 or not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
        raise ValueError("Timing requires an even repeat count >= 2 and a positive query timeout")
    report = result()
    database = root / "oewn.sqlite"
    before = file_digest(database)
    unchanged = before == baseline["files"]["oewn.sqlite"]
    condition(report, "query.database_pristine", unchanged, before,
              baseline["files"]["oewn.sqlite"])
    sql = (root / "sol.sql").read_text(encoding="utf-8")
    comments = sql_comments(sql)
    condition(report, "query.no_comments", not comments, len(comments), 0)
    terminated = sql.rstrip().endswith(";") and sqlite3.complete_statement(sql)
    condition(report, "query.semicolon_terminated", terminated, terminated,
              "one complete SQLite query terminated by a semicolon")
    # 数据库已变化时，不把新数据库上的等价结果当作原任务证据。
    if not unchanged or comments or not terminated:
        return finish(report)
    timings: list[dict[str, Any]] = []
    equivalent = True
    phase = "candidate_warmup"
    try:
        original = baseline["original_sql"]
        candidate_columns, candidate, candidate_warmup = execute_readonly(database, sql, timeout_seconds)
        condition(report, "query.single_readonly_sqlite_query", True, True,
                  "SQLite accepts one result-producing candidate query with writes denied")
        report["metrics"]["candidate_warmup_seconds"] = candidate_warmup
        phase = "reference_warmup"
        columns, expected, reference_warmup = execute_readonly(database, original, timeout_seconds)
        condition(report, "query.reference_completed", True, reference_warmup,
                  f"original public SQL completes within {timeout_seconds} seconds")
        report["metrics"]["reference_warmup_seconds"] = reference_warmup
        equivalent = columns == candidate_columns and expected == candidate
        report["metrics"]["reference_row_count"] = len(expected)
        report["metrics"]["candidate_row_count"] = len(candidate)
        report["metrics"]["column_names_equal"] = columns == candidate_columns
        for index in range(repeats):
            order = ("original", "candidate") if index % 2 == 0 else ("candidate", "original")
            pair: dict[str, Any] = {"round": index + 1, "order": list(order)}
            for name in order:
                phase = f"{name}_timing_round_{index + 1}"
                measured_columns, measured_rows, elapsed = execute_readonly(
                    database, original if name == "original" else sql, timeout_seconds)
                equivalent = equivalent and measured_columns == columns and measured_rows == expected
                pair[name + "_seconds"] = elapsed
            timings.append(pair)
        condition(report, "query.exact_public_output", equivalent,
                  {"ordered_rows_equal": equivalent, "reference_rows": len(expected),
                   "candidate_rows": len(candidate), "column_names_equal": columns == candidate_columns},
                  "same column names, values, multiplicities and row order on every measured execution")
        differences = [pair["original_seconds"] - pair["candidate_seconds"] for pair in timings]
        median_difference = statistics.median(differences)
        report["metrics"].update({"timing_pairs": timings,
                                  "median_paired_seconds_saved": median_difference,
                                  "original_median_seconds": statistics.median(pair["original_seconds"] for pair in timings),
                                  "candidate_median_seconds": statistics.median(pair["candidate_seconds"] for pair in timings),
                                  "timing_protocol": "one warmup each; alternating order; fresh read-only connection per execution",
                                  "public_numeric_runtime_threshold": None})
        condition(report, "query.measured_improvement", median_difference > 0,
                  median_difference, {"operator": ">", "value": 0,
                                      "meaning": "positive median paired seconds saved versus original public SQL"})
    except (sqlite3.Error, ValueError) as error:
        report["metrics"]["timing_pairs"] = timings
        condition_id = ("query.single_readonly_sqlite_query" if phase == "candidate_warmup"
                        else "query.reference_completed" if phase == "reference_warmup"
                        else "query.timing_completed")
        incomplete = phase != "candidate_warmup" or (
            isinstance(error, sqlite3.OperationalError) and "interrupted" in str(error))
        condition(report, condition_id, None if incomplete else False,
                  {"phase": phase, "error_type": type(error).__name__, "message": str(error)},
                  f"each read-only execution completes within {timeout_seconds} seconds")
    after = file_digest(database)
    condition(report, "query.database_unchanged_after_check", after == before, after, before)
    return finish(report)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check only published Terminal-Bench task conditions")
    commands = parser.add_subparsers(dest="command", required=True)
    capture = commands.add_parser("capture")
    capture.add_argument("task", choices=("scheduler", "query"))
    capture.add_argument("--root", type=Path, required=True)
    for name, default in (("scheduler", "/app/task_file"), ("query", "/app")):
        check = commands.add_parser(name)
        check.add_argument("--root", type=Path, default=Path(default))
        check.add_argument("--baseline", type=Path, required=True)
        if name == "query":
            check.add_argument("--repeats", type=int, default=4)
            check.add_argument("--timeout-seconds", type=float, default=120.0)
    arguments = parser.parse_args(argv)
    try:
        if arguments.command == "capture":
            print(json.dumps(capture_baseline(arguments.task, arguments.root), sort_keys=True))
            return 0
        baseline = json.loads(arguments.baseline.read_text(encoding="utf-8"))
        if not isinstance(baseline, dict):
            raise ValueError("Baseline must be a JSON object")
        report = (check_scheduler(arguments.root, baseline) if arguments.command == "scheduler"
                  else check_query(arguments.root, baseline, arguments.repeats, arguments.timeout_seconds))
    except (OSError, ValueError, TypeError, KeyError) as error:
        report = result()
        condition(report, "checker.inputs_readable", False,
                  {"error_type": type(error).__name__, "message": str(error)},
                  "valid baseline, public inputs and candidate deliverables")
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, allow_nan=False))
    return 0 if report["passed"] is True else 2 if report["passed"] is None else 1


if __name__ == "__main__":
    sys.exit(main())
