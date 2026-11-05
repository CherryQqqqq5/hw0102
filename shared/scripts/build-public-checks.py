import argparse
import json
import shlex
from dataclasses import asdict
from pathlib import Path

from course_eval.inventory import REVISIONS
from course_eval.verification import PublicCheck


parser = argparse.ArgumentParser()
parser.add_argument("--sources", type=Path, default=Path("work/datasets"))
parser.add_argument("--manifest", type=Path, default=Path("work/frozen.json"))
parser.add_argument("--out", type=Path, default=Path("work/public-checks.draft.json"))
parser.add_argument("--repair-json-lines", action="store_true")
args = parser.parse_args()
root = args.sources
manifest = json.loads(args.manifest.read_text())
issues = {row["instance_id"]: row["problem_statement"] for row in json.loads((root / "swe-grader.json").read_text())}
terminal = root / f"terminal-bench-2-1-{REVISIONS['terminal']}" / "tasks"
python = "/opt/miniconda3/envs/testbed/bin/python"

swe_specs = {
    "django__django-15987": ("tests/runtests.py fixtures --parallel=1", "django/core/management/commands/loaddata.py tests/fixtures/tests.py"),
    "django__django-13346": ("tests/runtests.py model_fields.test_jsonfield --parallel=1", "django/db/models/fields/json.py tests/model_fields/test_jsonfield.py"),
    "django__django-16082": ("tests/runtests.py expressions --parallel=1", "django/db/models/expressions.py tests/expressions/tests.py"),
    "django__django-15554": ("tests/runtests.py filtered_relation --parallel=1", "django/db/models/sql/query.py tests/filtered_relation/tests.py"),
    "django__django-12050": ("tests/runtests.py lookup --parallel=1", "django/db/models/sql/query.py tests/lookup/tests.py"),
    "pydata__xarray-6599": ("-m pytest -q xarray/tests/test_computation.py -k polyval", "xarray/core/computation.py xarray/tests/test_computation.py"),
    "pydata__xarray-3305": ("-m pytest -q xarray/tests/test_dataarray.py xarray/tests/test_dataset.py -k quantile", "xarray/core/dataarray.py xarray/core/dataset.py xarray/core/variable.py xarray/tests/test_dataarray.py xarray/tests/test_dataset.py"),
    "pydata__xarray-2905": ("-m pytest -q xarray/tests/test_variable.py -k setitem", "xarray/core/variable.py xarray/tests/test_variable.py"),
    "pydata__xarray-4695": ("-m pytest -q xarray/tests/test_dataarray.py -k 'loc and not dask'", "xarray/core/dataarray.py xarray/core/dataset.py xarray/core/indexing.py xarray/tests/test_dataarray.py"),
    "scikit-learn__scikit-learn-13496": ("-m pytest -q sklearn/ensemble/tests/test_iforest.py", "sklearn/ensemble/iforest.py sklearn/ensemble/tests/test_iforest.py"),
    "scikit-learn__scikit-learn-14496": ("-m pytest -q sklearn/cluster/tests/test_optics.py", "sklearn/cluster/optics_.py sklearn/cluster/tests/test_optics.py"),
    "scikit-learn__scikit-learn-10908": ("-m pytest -q sklearn/feature_extraction/tests/test_text.py -k vocab", "sklearn/feature_extraction/text.py sklearn/feature_extraction/tests/test_text.py"),
    "pytest-dev__pytest-7205": ("-m pytest -q testing/test_setuponly.py", "src/_pytest/setuponly.py testing/test_setuponly.py"),
    "pytest-dev__pytest-8399": ("-m pytest -q testing/test_unittest.py", "src/_pytest/unittest.py testing/test_unittest.py"),
    "pytest-dev__pytest-7571": ("-m pytest -q testing/logging/test_fixture.py", "src/_pytest/logging.py testing/logging/test_fixture.py"),
}


def artifact(quote: str, paths: str, check: str = "") -> PublicCheck:
    deps = tuple(paths.split())
    present = " && ".join("test -s " + shlex.quote(name) for name in deps)
    return PublicCheck("public-artifact", quote, present + (" && " + check if check else ""), deps, deps)


terminal_specs = {
    "openssl-selfsigned-cert": artifact("Save it as `/app/ssl/server.crt`", "/app/ssl/server.crt /app/ssl/server.key",
                                        "openssl x509 -in /app/ssl/server.crt -noout"),
    "query-optimize": artifact("Please save your solution in the file /app/sol.sql", "/app/sol.sql",
                               "{ printf 'EXPLAIN QUERY PLAN '; cat /app/sol.sql; } | sqlite3 -readonly /app/oewn.sqlite >/dev/null"),
    "sqlite-db-truncate": artifact("create a JSON file in /app/recover.json", "/app/recover.json",
                                    "python3 -m json.tool /app/recover.json >/dev/null"),
    "regex-log": artifact("Save your regex in /app/regex.txt", "/app/regex.txt",
                          "python3 -c 'import re; from pathlib import Path; re.compile(Path(\"/app/regex.txt\").read_text().strip(), re.M)'"),
    "video-processing": artifact("store it in `/app/output.toml`", "/app/jump_analyzer.py /app/output.toml",
                                 "python3 -m py_compile /app/jump_analyzer.py && python3 -c 'import tomllib; "
                                 'd=tomllib.load(open("/app/output.toml", "rb")); '
                                 'a=d["jump_takeoff_frame_number"]; b=d["jump_land_frame_number"]; '
                                 'assert type(a) is int and type(b) is int and 0 <= a < b\''),
    "llm-inference-batching-scheduler": artifact("/app/task_file/output_data/plan_b1.jsonl",
                                                 "/app/task_file/output_data/plan_b1.jsonl /app/task_file/output_data/plan_b2.jsonl",
                                                 "python3 -m json.tool --json-lines /app/task_file/output_data/plan_b1.jsonl >/dev/null"
                                                 " && python3 -m json.tool --json-lines /app/task_file/output_data/plan_b2.jsonl >/dev/null"),
    "mailman": PublicCheck("public-config", "save mailman configuration file in /etc/mailman3/mailman.cfg",
                           "test -s /etc/mailman3/mailman.cfg", ("/etc/mailman3/mailman.cfg",)),
    "sparql-university": artifact("Save your query in `/app/solution.sparql`", "/app/solution.sparql"),
    "extract-elf": artifact("Write me a program extract.js", "extract.js", "node --check extract.js"),
    "fix-git": PublicCheck("public-branch", "merge them into master", "git rev-parse --verify 'master^{commit}' >/dev/null",
                           (".git/HEAD", ".git/refs/heads/master")),
    "model-extraction-relu-logits": artifact("save this matrix to `/app/stolen_A1.npy`", "/app/steal.py /app/stolen_A1.npy",
                                              "python3 -m py_compile /app/steal.py"),
    "constraints-scheduling": artifact("Create `/app/meeting_scheduled.ics`", "/app/meeting_scheduled.ics",
                                        "grep -q BEGIN:VEVENT /app/meeting_scheduled.ics"),
    "tune-mjcf": artifact("Tuned mjcf should be saved as /app/model.xml", "/app/model.xml",
                          "python3 -c 'import xml.etree.ElementTree as ET; ET.parse(\"/app/model.xml\")'"),
    "password-recovery": artifact("Write each matching password you find", "/app/recovered_passwords.txt"),
    "custom-memory-heap-crash": PublicCheck("public-release", "Release: g++ -std=c++17",
                                            "g++ -std=c++17 -o /app/release /app/main.cpp /app/user.cpp -O2 -DNDEBUG "
                                            "-L/usr/local/gcc-custom-release/lib64 -Wl,-Bstatic -lstdc++ -Wl,-Bdynamic -lm",
                                            ("/app/user.cpp", "/app/main.cpp")),
}

if args.repair_json_lines:
    decoder = "import json,sys; from pathlib import Path; [json.loads(line) for name in sys.argv[1:] for line in Path(name).read_text().splitlines()]"
    terminal_specs["llm-inference-batching-scheduler"] = artifact(
        "/app/task_file/output_data/plan_b1.jsonl",
        "/app/task_file/output_data/plan_b1.jsonl /app/task_file/output_data/plan_b2.jsonl",
        "python3 -c " + shlex.quote(decoder)
        + " /app/task_file/output_data/plan_b1.jsonl /app/task_file/output_data/plan_b2.jsonl",
    )

plans = {}
for task in manifest["selected"]:
    task_id = task["id"]
    if task["benchmark"] == "aider":
        continue
    if task["benchmark"] == "terminal":
        instruction = (terminal / task_id / "instruction.md").read_text()
        check = terminal_specs[task_id]
    else:
        instruction = issues[task_id]
        test, dependencies = swe_specs[task_id]
        quote = next(line.strip() for line in instruction.splitlines() if line.strip())
        check = PublicCheck("public-regression", quote, f"{python} {test}", tuple(dependencies.split()))
    check.validate(instruction)
    plans[task_id] = [asdict(check)]

args.out.parent.mkdir(parents=True, exist_ok=True)
args.out.write_text(json.dumps(plans, ensure_ascii=False, indent=2) + "\n")
