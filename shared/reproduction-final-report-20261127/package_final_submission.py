import argparse
import base64
import hashlib
import json
import posixpath
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from course_eval.export_revision import HOME_PATH, PRIVATE, SECRET
from submission_readme import build_submission_readme
from interruption_cost import load as load_interruption_cost


parser = argparse.ArgumentParser()
parser.add_argument("--commit", required=True)
parser.add_argument("--output", type=Path, required=True)
parser.add_argument("--report-data", type=Path, required=True)
parser.add_argument("--final-review", type=Path, required=True)
parser.add_argument("--note", type=Path)
parser.add_argument("--focused", action="store_true")
parser.add_argument("--repo", type=Path, required=True)
parser.add_argument("--pdf-dir", type=Path, required=True)
parser.add_argument("--github-verification", type=Path, required=True)
parser.add_argument("--efficiency", type=Path, required=True)
parser.add_argument("--interruption-cost", type=Path, required=True)
args = parser.parse_args()
root = args.repo
expected_commit, output = args.commit, args.output
note = args.note or output.with_suffix(".README.md")
if len(expected_commit) != 40 or any(c not in "0123456789abcdef" for c in expected_commit):
    raise ValueError("Use the exact reviewed40-character Git commit")
if output.exists() or output.with_suffix(".zip.part").exists():
    raise FileExistsError("Keep each completed or interrupted package distinct")
report_data = json.loads(args.report_data.read_text())
review = json.loads(args.final_review.read_text())
github = json.loads(args.github_verification.read_text())
github_receipt_sha256 = hashlib.sha256(args.github_verification.read_bytes()).hexdigest()
if github["repository"] != "CherryQqqqq5/hw0102" or github["commit"] != expected_commit:
    raise ValueError("The actual GitHub PDF receipt belongs to another repository or commit")
efficiency = {name: json.loads((args.efficiency / filename).read_text()) for name, filename in (
    ("study", "study-results.json"), ("repeat", "repeat-results.json"), ("review", "final-study-review.json"))}
interruption_cost = load_interruption_cost(args.interruption_cost)
if (efficiency["study"]["stage"] != "complete" or efficiency["repeat"]["stage"] not in {"complete", "not_started"}
        or efficiency["review"]["blocking_findings_remaining"] != 0):
    raise ValueError("The registered efficiency study or its independent review is incomplete")
for filename, key in (("study-results.json", "source_summary_sha256"), ("repeat-results.json", "source_repeat_sha256")):
    if hashlib.sha256((args.efficiency / filename).read_bytes()).hexdigest() != efficiency["review"][key]:
        raise ValueError("An efficiency result changed after independent review")
if (not report_data["complete_required_experiments"] or not report_data["main_and_repeat_all75_qualified_pass"]
        or any(report_data["groups"][arm]["completed"] != 75 for arm in ("main", "dsh", "repeat"))
        or review["source_summary_sha256"] != report_data["summary_sha256"]
        or review["blocking_findings_remaining"] != 0
        or review["positions_reviewed"] != {"main": 75, "dsh": 75, "repeat": 75}):
    raise ValueError("Final packaging requires the completed real cohort and its exact final independent review")


def git(*args):
    return subprocess.check_output(["git", "-C", str(root), *args])


assert git("rev-parse", "HEAD").decode().strip() == expected_commit
subprocess.run(["git", "-C", str(root), "diff", "--quiet", "HEAD", "--"], check=True)
tracked = sorted(git("ls-files", "-z").decode().split("\0")[:-1])
all_tracked_count = len(tracked)
if args.focused:
    required_roots = (
        "shared/", "作业一/evidence/formal/", "作业一/evidence/preflights/", "作业二/configs/",
        "作业二/evidence/performance75-final-20261126/",
        "作业二/evidence/confirmation-hy4flash-free-v16/",
        "作业二/evidence/confirmation-hy4flash-free-v16-summary/",
        "作业二/evidence/performance75-cost-history-20261126/hy4-interruptions/",
        "作业二/evidence/input-efficiency-20261127/",
        "作业二/evidence/input-efficiency-cost-history-20261127/",
    )
    required_files = {"README.md", "作业一/README.md", "作业一/231880296_邱昱宁_作业一.pdf",
        "作业一/evidence/task-records.csv", "作业一/evidence/task-records.json",
        "作业一/evidence/task-observations.json", "作业一/evidence/formal-trials.csv",
        "作业一/evidence/formal-coverage.json", "作业一/evidence/diagnosis-notes.md",
        "作业一/evidence/preflight-status.json",
        "作业二/README.md", "作业二/231880296_邱昱宁_作业二.pdf",
        "作业二/evidence/course-grading-tables-20261118.md",
        "作业二/evidence/confirmation-hy4flash-free-v16-source-audit.json",
        "作业二/evidence/confirmation-hy4flash-free-v16-analysis.json",
        "作业二/evidence/input-efficiency-20261127.zip",
        "作业二/evidence/input-efficiency-cost-history-20261127/billing-ledger.json",
        "作业二/evidence/input-efficiency-cost-history-20261127/interruption-review.json"}
    required_files.update(f"作业二/evidence/performance75-final-20261126-part{n}.zip" for n in (1, 2, 3))
    tracked = [name for name in tracked if name in required_files or name.startswith(required_roots)]
    if not required_files.issubset(tracked):
        raise ValueError("The focused submission is missing a required report or evidence archive")
tracked_set = set(tracked)


def check_index(directory, filename, include_runs=False):
    index = json.loads((root / directory / filename).read_text())
    records = [(directory + "/" + row["path"], row) for row in index["files"]]
    if include_runs:
        records.extend((directory + "/" + run["path"] + "/" + row["path"], row)
                       for run in index["runs"] for row in run["files"])
    for name, row in records:
        name = posixpath.normpath(name)
        if not name.startswith(directory + "/"):
            raise ValueError("An evidence index points outside its directory")
        if name not in tracked_set:
            raise ValueError("The submission is missing an indexed evidence file: " + name)
        data = (root / name).read_bytes()
        if len(data) != row["export_bytes"] or hashlib.sha256(data).hexdigest() != row["export_sha256"]:
            raise ValueError("An indexed evidence file changed: " + name)


check_index("作业二/evidence/input-efficiency-20261127", "index.json", include_runs=True)
check_index("shared/reproduction-input-efficiency-20261127", "SOURCE_MANIFEST.json")
check_index("作业二/evidence/input-efficiency-cost-history-20261127", "index.json")
historical_files = set()
supplement = []
historical_roots = () if args.focused else ("codebuddy-v3-cases.json", "codebuddy-v3-stopped-summary.json",
                                          "confirmation-boyue-v4", "confirmation-v3")
for name in historical_roots:
    source = root / "作业二/evidence" / name
    files = [source] if source.is_file() else sorted(p for p in source.rglob("*") if p.is_file())
    assert files, source
    historical_files.update(str(path.relative_to(root)) for path in files)
    supplement.extend(str(path.relative_to(root)) for path in files if str(path.relative_to(root)) not in tracked_set)
if supplement:
    raise ValueError("Commit the authorized historical evidence to the same GitHub version before final packaging")
names = sorted(tracked + supplement)
assert len(names) == len(set(names))

# 历史补充使用已有脱敏导出，不读取原运行目录或凭据。
def inspect_file(name):
    path = root / name
    assert path.is_file() and not path.is_symlink(), name
    assert not ({".git", ".env", ".venv", "__pycache__"} & set(path.parts)), name
    content = path.read_bytes().decode("utf-8", errors="replace")
    if SECRET.search(content):
        return name
    if name in historical_files and (PRIVATE.search(content) or HOME_PATH.search(content)):
        return name
    return None


hits = []
with ThreadPoolExecutor(max_workers=8) as executor:
    for index, hit in enumerate(executor.map(inspect_file, names), 1):
        if hit is not None:
            hits.append(hit)
        if index % 4000 == 0:
            print(json.dumps({"files_read": index, "total": len(names)}), flush=True)
assert not hits, sorted(set(hits))
print(json.dumps({"files_read": len(names), "sensitive_matches": 0}), flush=True)

pdfs = []
for assignment in ("一", "二"):
    name = f"作业{assignment}/231880296_邱昱宁_作业{assignment}.pdf"
    remote = github["pdfs"][name]
    assert remote["encoding"] == "base64"
    assert git("rev-parse", expected_commit + ":" + name).decode().strip() == remote["sha"]
    data = base64.b64decode(remote["content"], validate=False)
    assert data == (root / name).read_bytes() == (args.pdf_dir / Path(name).name).read_bytes(), name
    pdfs.append({"file": name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(), "github_byte_equal": True})

note_bytes = build_submission_readme(expected_commit, report_data, pdfs, focused=args.focused,
    efficiency=efficiency, interruption_cost=interruption_cost).encode("utf-8")
if note.exists():
    if note.read_bytes() != note_bytes:
        raise FileExistsError("Keep the old package note;select a fresh --note output for this exact commit and results")
else:
    with note.open("xb") as stream:
        stream.write(note_bytes)

staged = output.with_suffix(".zip.part")
print("Writing complete archive", flush=True)
with ZipFile(staged, "w", compression=ZIP_DEFLATED, compresslevel=6) as archive:
    archive.comment = ("Complete course submission; GitHub commit " + expected_commit).encode()
    archive.write(note, "提交包说明.md")
    for name in names:
        archive.write(root / name, name)
with ZipFile(staged) as archive:
    assert archive.testzip() is None
    assert set(archive.namelist()) == set(names) | {"提交包说明.md"}
    for name in names:
        assert archive.read(name) == (root / name).read_bytes(), name
    assert archive.read("提交包说明.md") == note.read_bytes()
assert hashlib.sha256(args.github_verification.read_bytes()).hexdigest() == github_receipt_sha256
subprocess.run(["git", "-C", str(root), "diff", "--quiet", "HEAD", "--"], check=True)
staged.replace(output)
result = {"archive": str(output), "bytes": output.stat().st_size,
          "github_pdf_receipt_sha256": github_receipt_sha256,
          "commit": expected_commit, "tracked_files": len(tracked),
          "focused_submission": args.focused, "repository_tracked_files": all_tracked_count,
          "supplementary_historical_files": len(supplement), "members": len(names) + 1,
          "included_historical_files": len(historical_files),
          "supplementary_roots": ["作业二/evidence/" + name for name in historical_roots],
          "pdfs": pdfs, "all_members_byte_equal": True, "zip_integrity": "pass",
          "sensitive_matches": 0, "new_model_requests": 0, "new_grader_executions": 0}
output.with_suffix(".verification.json").write_text(
    json.dumps(result, ensure_ascii=False, indent=2) + "\n")
print(json.dumps(result, ensure_ascii=False, indent=2))
