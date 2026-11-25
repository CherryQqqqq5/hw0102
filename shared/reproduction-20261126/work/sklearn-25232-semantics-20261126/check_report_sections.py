import copy
import hashlib
import json
from pathlib import Path

import pdfplumber

import render_hy4_final_reports as renderer


root = Path.cwd()
folder = root / "work/sklearn-25232-semantics-20261126"
output = folder / "report-preview"
output.mkdir(exist_ok=False)
source = folder / "consumption-qualification/joint-seven/summary.json"
observations_path = folder / "consumption-qualification/nan-contract-observations.json"
summary = json.loads(source.read_text())
observations = json.loads(observations_path.read_text())
data = {"incremental_acceptance": summary["incremental_acceptance"],
    "case_observations": {"scikit-learn__scikit-learn-25232": observations["facts"]}}
indexed = {arm: {row["task"]: row for row in summary["rows"] if row["arm"] == arm}
    for arm in ("main", "repeat", "dsh")}
items = renderer.revision_accounting(data) + renderer.nan_contract_items(data, indexed)
pdf = output / "preview_nan_contract_and_accounting.pdf"
renderer.build(str(pdf), "内部检查：局部修订与缺失值合同", items,
    subtitle="固定177快照；两模型位置仍待原评分；非最终报告", footer="内部排版与来源核验")
with pdfplumber.open(pdf) as document:
    text = "\n".join(page.extract_text() for page in document.pages)
    outside = [(number, char["text"]) for number, page in enumerate(document.pages, 1) for char in page.chars
        if char["x0"] < -0.5 or char["x1"] > page.width + 0.5 or char["top"] < -0.5 or char["bottom"] > page.height + 0.5]
    pages = len(document.pages)
assert "136份原记录与14份新记录" in text
assert "7处修订新会话（计划14）" in text
assert "8/12" in text and "9/12" in text and "12/12" in text
assert text.count("待评分") == 2 and "215个回归目标" not in text
assert "214个回归目标" in text and not outside
wrong = copy.deepcopy(data)
wrong["incremental_acceptance"]["required_new_positions"] = 12
try:
    renderer.revision_accounting(wrong)
except ValueError:
    rejected = True
else:
    raise AssertionError("The report accepted an incomplete150-position accounting")
result = {"status": "PASS_ACTUAL_REPORTLAB_PENDING_SECTION_AND_PAGE_BOUNDS", "pages": pages,
    "model_scores_in_preview": "Two fixed pending positions only;no invented successes",
    "malformed_accounting_rejected": rejected, "page_bounds_violations": len(outside),
    "pdf_sha256": hashlib.sha256(pdf.read_bytes()).hexdigest(),
    "source_sha256": {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in (source, observations_path, Path(renderer.__file__), Path(__file__))},
    "new_model_calls": 0, "new_original_grader_calls": 0,
    "limit": "Actual existing section renderer with closed177 observations;full report load and new scored-session rendering await real closure. Visual inspection is separate."}
(output / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
print(json.dumps({key: result[key] for key in ("status", "pages", "page_bounds_violations")}))
