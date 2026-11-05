import json
import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, "/opt/public-checker")
from public_semantics import execute_readonly, file_digest


database = Path("/app/oewn.sqlite")
before = file_digest(database)
started = time.perf_counter()
report = {"kind": "one_original_reference_execution_in_real_task_container",
          "sqlite_version": sqlite3.sqlite_version, "python_version": sys.version,
          "timeout_seconds": 120, "database_before": before}
try:
    columns, rows, elapsed = execute_readonly(database, Path("/app/my-sql-query.sql").read_text(), 120)
    report.update({"reference_completed": True, "columns": columns, "rows": rows,
                   "elapsed_seconds": elapsed})
except sqlite3.Error as error:
    report.update({"reference_completed": None, "status": "unknown",
                   "error_type": type(error).__name__, "error": str(error),
                   "elapsed_seconds": time.perf_counter() - started})
report["database_after"] = file_digest(database)
report["database_unchanged"] = report["database_after"] == before
print(json.dumps(report))
