import json
import pathlib
import shutil
import sqlite3

from course_eval.public_semantics import capture_baseline, check_query, execute_readonly, sql_comments
from validate import DOCKER, OUT, ROOT, checks, condition, copy_checker, require, run, save


def real_container_once():
    container = "course-public-query-reference-once"
    run(DOCKER, "run", "-d", "--platform", "linux/amd64", "--network", "none", "--name", container,
        "--entrypoint", "sleep", "alexgshaw/query-optimize:20251031", "infinity")
    try:
        copy_checker(container)
        run(DOCKER, "cp", ROOT / "work/terminal-runtime/python-3.13.12-linux-x86_64.tar.gz",
            f"{container}:/opt/python-runtime.tar.gz")
        run(DOCKER, "exec", container, "tar", "xzf", "/opt/python-runtime.tar.gz", "-C", "/opt")
        run(DOCKER, "cp", OUT / "container_reference_once.py", f"{container}:/opt/public-checker/reference_once.py")
        print("query: one bounded original SQL execution in real task container", flush=True)
        output = run(DOCKER, "exec", container, "/opt/python/bin/python3", "/opt/public-checker/reference_once.py", timeout=150)
        report = json.loads(output.stdout)
        save(OUT / "query/container-reference-once.json", report)
        require("real query container: database preserved", report["database_unchanged"])
        print(json.dumps({key: report.get(key) for key in ("reference_completed", "status", "elapsed_seconds", "sqlite_version")}), flush=True)
    finally:
        run(DOCKER, "rm", "-f", container)


def synthetic_checks():
    directory = OUT / "query-synthetic"
    directory.mkdir(exist_ok=True)
    database = directory / "oewn.sqlite"
    if database.exists():
        raise FileExistsError("Preserve previous synthetic fixture evidence before re-running")
    connection = sqlite3.connect(database)
    connection.executescript("CREATE TABLE words(wordid INTEGER PRIMARY KEY, word TEXT); CREATE TABLE senses(wordid INTEGER, synsetid INTEGER); CREATE TABLE synsets(synsetid INTEGER, domainid INTEGER, posid INTEGER);")
    connection.executemany("INSERT INTO words VALUES(?,?)", [(index, f"synthetic-word-{index}") for index in range(150)])
    connection.executemany("INSERT INTO synsets VALUES(?,?,?)", [(10, 1, 1), (20, 2, 1), (30, 3, 2)])
    connection.executemany("INSERT INTO senses VALUES(?,?)", [(index, synset) for index in range(150) for synset in (10, 20, 20, 30, 30, 30)])
    connection.commit()
    connection.close()
    shutil.copyfile(OUT / "query/my-sql-query.sql", directory / "my-sql-query.sql")
    candidate = (OUT / "query/sol.sql").read_text()
    (directory / "sol.sql").write_text(candidate)
    baseline = capture_baseline("query", directory)
    save(directory / "baseline.json", baseline)
    report = check_query(directory, baseline, repeats=2, timeout_seconds=5)
    save(directory / "public-check.json", report)
    require("synthetic query: exact ordered output verified", condition(report, "query.exact_public_output")["passed"])
    require("synthetic query: alternating timing pairs", [pair["order"] for pair in report["metrics"]["timing_pairs"]] == [["original", "candidate"], ["candidate", "original"]])
    require("synthetic query: original database preserved", condition(report, "query.database_unchanged_after_check")["passed"])
    require("synthetic query: no hidden time threshold", report["metrics"]["public_numeric_runtime_threshold"] is None)
    for name, sql, expected_id in (
        ("multiple statements", "SELECT 1; SELECT 2;", "query.single_readonly_sqlite_query"),
        ("write attempt", "DELETE FROM words;", "query.single_readonly_sqlite_query"),
        ("line comment", "SELECT 1; -- comment", "query.no_comments"),
        ("block comment", "SELECT /* comment */ 1;", "query.no_comments"),
        ("missing semicolon", "SELECT 1", "query.semicolon_terminated"),
        ("different output", "SELECT 1;", "query.exact_public_output"),
    ):
        (directory / "sol.sql").write_text(sql)
        rejected = check_query(directory, baseline, repeats=2, timeout_seconds=5)
        require("synthetic query: " + name + " rejected", condition(rejected, expected_id)["passed"] is False)
    require("synthetic query: quoted comment delimiters accepted", not sql_comments("SELECT '--', '/*', \"--\", `/*`, [--];"))
    incomplete = dict(baseline)
    incomplete["original_sql"] = "WITH RECURSIVE t(x) AS (VALUES(1) UNION ALL SELECT x+1 FROM t) SELECT sum(x) FROM t;"
    save(directory / "timeout-baseline.json", incomplete)
    timeout_report = check_query(directory, incomplete, repeats=2, timeout_seconds=0.01)
    save(directory / "timeout-check.json", timeout_report)
    require("synthetic query: reference timeout is unknown", timeout_report["passed"] is None and condition(timeout_report, "query.reference_completed")["status"] == "unknown")
    invocation = run(ROOT / "work/.venv/bin/python", ROOT / "course_eval/check_public_semantics.py", "query", "--root", directory,
                     "--baseline", directory / "timeout-baseline.json", "--repeats", "2", "--timeout-seconds", "0.01", success=False)
    require("synthetic query: unknown exits 2", invocation.returncode == 2 and json.loads(invocation.stdout)["passed"] is None)
    (directory / "sol.sql").write_text(candidate)
    connection = sqlite3.connect(database)
    connection.execute("INSERT INTO words VALUES(99999,'changed')")
    connection.commit()
    connection.close()
    changed = check_query(directory, baseline, repeats=2)
    require("synthetic query: database mutation rejected", not condition(changed, "query.database_pristine")["passed"])
    save(directory / "provenance.json", {"kind": "synthetic_engineering_fixture", "word_count": 150, "sense_count": 900,
                                         "query": "original public SQL", "candidate": "manually authored fixture", "real_task_success": False})


if __name__ == "__main__":
    real_container_once()
    synthetic_checks()
    save(OUT / "query-validation.json", {"engineering_checks_passed": True, "checks": checks, "model_calls": 0,
                                          "real_query_equivalence": "unverified unless reference completed; see container-reference-once.json"})
    print(json.dumps({"engineering_checks_passed": True, "count": len(checks), "model_calls": 0}))
