import argparse
import base64
import json
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import quote
from zipfile import ZIP_DEFLATED, ZipFile

from course_eval.export_revision import HOME_PATH, PRIVATE, SECRET


parser = argparse.ArgumentParser()
parser.add_argument("--commit", required=True)
parser.add_argument("--output", type=Path, required=True)
parser.add_argument("--report-data", type=Path, required=True)
parser.add_argument("--final-review", type=Path, required=True)
parser.add_argument("--note", type=Path, default=Path("work/FINAL_SUBMISSION_README.md"))
args = parser.parse_args()
root = Path("work/hw0102-publish")
expected_commit, output, note = args.commit, args.output, args.note
if len(expected_commit) != 40 or any(c not in "0123456789abcdef" for c in expected_commit):
    raise ValueError("Use the exact reviewed40-character Git commit")
if output.exists() or output.with_suffix(".zip.part").exists():
    raise FileExistsError("Keep each completed or interrupted package distinct")
report_data = json.loads(args.report_data.read_text())
review = json.loads(args.final_review.read_text())
if (not report_data["complete_required_experiments"] or not report_data["main_and_repeat_all75_qualified_pass"]
        or any(report_data["groups"][arm]["completed"] != 75 for arm in ("main", "dsh", "repeat"))
        or review["source_summary_sha256"] != report_data["summary_sha256"]
        or review["blocking_findings_remaining"] != 0
        or review["positions_reviewed"] != {"main": 75, "dsh": 75, "repeat": 75}):
    raise ValueError("Final packaging requires the completed real cohort and its exact final independent review")


def git(*args):
    return subprocess.check_output(["git", "-C", str(root), *args])


def remote_commit():
    return subprocess.check_output(
        ["gh", "api", "repos/CherryQqqqq5/hw0102/git/ref/heads/main", "--jq", ".object.sha"],
        text=True,
    ).strip()


assert git("rev-parse", "HEAD").decode().strip() == expected_commit
assert remote_commit() == expected_commit
subprocess.run(["git", "-C", str(root), "diff", "--quiet", "HEAD", "--"], check=True)
tracked = sorted(git("ls-files", "-z").decode().split("\0")[:-1])
tracked_set = set(tracked)
historical_files = set()
supplement = []
for name in ("codebuddy-v3-cases.json", "codebuddy-v3-stopped-summary.json",
             "confirmation-boyue-v4", "confirmation-v3"):
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
    endpoint = "repos/CherryQqqqq5/hw0102/contents/" + quote(name, safe="/") + "?ref=" + expected_commit
    remote = json.loads(subprocess.check_output(["gh", "api", endpoint]))
    data = base64.b64decode(remote["content"], validate=False)
    assert data == (root / name).read_bytes() == (Path("outputs") / Path(name).name).read_bytes(), name
    pdfs.append({"file": name, "bytes": len(data), "github_byte_equal": True})

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
assert remote_commit() == expected_commit
subprocess.run(["git", "-C", str(root), "diff", "--quiet", "HEAD", "--"], check=True)
staged.replace(output)
result = {"archive": str(output), "bytes": output.stat().st_size,
          "commit": expected_commit, "tracked_files": len(tracked),
          "supplementary_historical_files": len(supplement), "members": len(names) + 1,
          "included_historical_files": len(historical_files),
          "supplementary_roots": ["作业二/evidence/" + name for name in
              ("codebuddy-v3-cases.json", "codebuddy-v3-stopped-summary.json",
               "confirmation-boyue-v4", "confirmation-v3")],
          "pdfs": pdfs, "all_members_byte_equal": True, "zip_integrity": "pass",
          "sensitive_matches": 0, "new_model_requests": 0, "new_grader_executions": 0}
output.with_suffix(".verification.json").write_text(
    json.dumps(result, ensure_ascii=False, indent=2) + "\n")
print(json.dumps(result, ensure_ascii=False, indent=2))
