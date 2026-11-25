import copy
import hashlib
import json
from pathlib import Path
import subprocess

from submission_readme import build_submission_readme


root = Path.cwd()
repo = root / "work/hw0102-publish"
commit = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip()
snapshot = root / "work/parallel-free-evaluation-20261124/joint-snapshot-0232-20261126/summary.json"
data = json.loads(snapshot.read_text())
pdfs = []
for assignment in ("一", "二"):
    name = f"作业{assignment}/231880296_邱昱宁_作业{assignment}.pdf"
    content = (repo / name).read_bytes()
    tracked = subprocess.check_output(["git", "-C", str(repo), "show", commit + ":" + name])
    assert tracked == content
    pdfs.append({"file": name, "bytes": len(content), "sha256": hashlib.sha256(content).hexdigest(),
        "github_byte_equal": True})
note = build_submission_readme(commit, data, pdfs)
assert commit in note and "136份" in note and "14份" in note
assert f"{data['historical_unknown_calls_preserved']}笔历史未知" in note
assert "61/75" in note and "60/75" in note
assert "e0231e09cdbe23f589635f8b762292267e5e0b8b" not in note
assert "分别为6页和15页" not in note and "历史13笔" not in note
negatives = []
for name, wrong_commit, wrong_pdfs in (
        ("incomplete_commit", commit[:7], pdfs),
        ("one_missing_pdf", commit, pdfs[:1]),
        ("unmatched_remote_pdf", commit, [pdfs[0], pdfs[1] | {"github_byte_equal": False}])):
    try:
        build_submission_readme(wrong_commit, copy.deepcopy(data), wrong_pdfs)
    except ValueError:
        negatives.append(name)
    else:
        raise AssertionError("Invalid package metadata was accepted:" + name)
result = {"status": "PASS_ACTUAL_PARTIAL_COUNTS_AND_OLD_NOTE_DRIFT_REJECTION", "local_git_commit": commit,
    "data_snapshot_sha256": hashlib.sha256(snapshot.read_bytes()).hexdigest(),
    "new_unknown_count_used": data["historical_unknown_calls_preserved"], "negative_cases_rejected": negatives,
    "old_note_preserved_sha256": hashlib.sha256((root / "work/FINAL_SUBMISSION_README.md").read_bytes()).hexdigest(),
    "source_sha256": {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in (Path(__file__), root / "work/submission_readme.py", root / "work/package_final_submission.py")},
    "scope": "Real partial experiment counts and local Git-object PDF equality. The builder's remote-match flag is an explicit metadata fixture;no new remote PDF verification or final package is claimed. The final packager must perform its actual remote byte checks and full experiment/review gates.",
    "new_model_calls": 0, "new_original_grader_calls": 0}
output = root / "work/submission-note-qualification-20261126.json"
with output.open("x") as stream:
    stream.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
print(json.dumps({"status": result["status"], "negative_cases_rejected": len(negatives), "new_model_calls": 0}))
