import copy
import hashlib
import json
from pathlib import Path

import pdfplumber

import render_hy4_final_reports as renderer


root = Path.cwd()
folder = root / "work/sklearn-25232-semantics-20261126/report-feedback-preview"
source = folder / "observations.json"
observations = json.loads(source.read_text())
summary_path = root / observations["summary"]
summary = json.loads(summary_path.read_text())
for name, expected in observations["sources"]["files_sha256"].items():
    assert renderer.digest(root / name) == expected
review_entry = observations["supplementary"]["sklearn_completed_review"]
assert renderer.digest(root / review_entry["path"]) == review_entry["sha256"]
data = {"case_observations": {"scikit-learn__scikit-learn-25232": observations["facts"]},
    "supplementary": observations["supplementary"]}
indexed = {arm: {row["task"]: row for row in summary["rows"] if row["arm"] == arm}
    for arm in ("main", "repeat", "dsh")}
items = renderer.nan_contract_items(data, indexed)
pdf = folder / "preview_real_two_sessions_and_feedback.pdf"
if pdf.exists():
    raise FileExistsError("Preserve the existing rendered evidence")
renderer.build(str(pdf), "内部检查：两次真实评分与反馈修复", items,
    subtitle="两位置均完成原评分；完整75题仍在运行；非最终报告", footer="实际原评分、公开检查与反馈来源核验")
with pdfplumber.open(pdf) as document:
    text = "\n".join(page.extract_text() for page in document.pages)
    outside = [(number, char["text"]) for number, page in enumerate(document.pages, 1) for char in page.chars
        if char["x0"] < -0.5 or char["x1"] > page.width + 0.5 or char["top"] < -0.5 or char["bottom"] > page.height + 0.5]
    pages = len(document.pages)
for phrase in ("第24步", "11/12", "第27步", "第28步", "第33步", "45 / 879.9", "34 / 802.1"):
    assert phrase in text, phrase
assert "待评分" not in text and not outside
wrong = copy.deepcopy(data)
wrong["supplementary"]["sklearn_completed_review"]["sha256"] = "0" * 64
try:
    renderer.nan_contract_items(wrong, indexed)
except ValueError:
    rejected = True
else:
    raise AssertionError("The report accepted a different reviewed feedback source")
result = {"status": "PASS_REAL_SCORED_NAN_AND_REVIEWED_FEEDBACK_REPORT_BRANCH", "pages": pages,
    "page_bounds_violations": len(outside), "changed_review_hash_rejected": rejected,
    "actual_case_sources": len(observations["sources"]["files_sha256"]),
    "actual_model_original_passed": 2, "actual_model_public12_passed": 2,
    "new_model_calls_by_check": 0, "new_original_grader_calls_by_check": 0,
    "source_sha256": {str(path.relative_to(root)): renderer.digest(path)
        for path in (source, summary_path, root / review_entry["path"], Path(renderer.__file__), Path(__file__))},
    "pdf_sha256": hashlib.sha256(pdf.read_bytes()).hexdigest(),
    "limit": "Actual two-session report section only;does not close the full75 comparison,full PDFs,GitHub PDFs or final submission. Visual review is separate."}
with (folder / "result.json").open("x") as stream:
    stream.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
print(json.dumps({key: result[key] for key in ("status", "pages", "page_bounds_violations")}))
