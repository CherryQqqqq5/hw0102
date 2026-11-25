import copy
import hashlib
import json
from pathlib import Path

import pdfplumber

import render_hy4_final_reports as renderer


root = Path.cwd()
folder = root / "work/xarray-4695-preservation-20261126"
qualification = folder / "consumer-qualification/result.json"
summary_path = folder / "consumer-qualification/joint-eight/summary.json"
observations = json.loads(qualification.read_text())
summary = json.loads(summary_path.read_text())
for name, expected in observations["source_sha256"].items():
    assert hashlib.sha256((root / name).read_bytes()).hexdigest() == expected
for name, expected in observations["loc_case_source_sha256"].items():
    assert hashlib.sha256((root / name).read_bytes()).hexdigest() == expected
data = {"incremental_acceptance": summary["incremental_acceptance"],
    "case_observations": {"pydata__xarray-4695": observations["loc_case_observations"]}}
indexed = {arm: {row["task"]: row for row in summary["rows"] if row["arm"] == arm}
    for arm in ("main", "repeat", "dsh")}
output = folder / "report-preview"
output.mkdir(exist_ok=False)
pdf = output / "preview_preservation_and_accounting.pdf"
renderer.build(str(pdf), "内部检查：测试保护与局部修订", renderer.revision_accounting(data)
    + renderer.loc_preservation_items(data, indexed), subtitle="固定201原记录；两个新增位置待评分；非最终报告", footer="内部排版与来源核验")
with pdfplumber.open(pdf) as document:
    text = "\n".join(page.extract_text() for page in document.pages)
    outside = [(number, char["text"]) for number, page in enumerate(document.pages, 1) for char in page.chars
        if char["x0"] < -0.5 or char["x1"] > page.width + 0.5 or char["top"] < -0.5 or char["bottom"] > page.height + 0.5]
    pages = len(document.pages)
assert "134份原记录与16份新记录" in text and "8处修订新会话（计划16）" in text
assert "ReLU与xarray4695" in text and "原题示例" in text
assert "原重复完整候选" in text and "重复候选仅恢复测试" in text
assert "第14步" in text and "第21步" in text and "坏候选即使pytest返回0仍被拒绝" in text
assert text.count("待评分") == 3 and not outside
wrong = copy.deepcopy(data)
wrong["incremental_acceptance"]["required_new_positions"] = 14
try:
    renderer.revision_accounting(wrong)
except ValueError:
    rejected = True
else:
    raise AssertionError("The report accepted only148 main/repeat positions")
result = {"status": "PASS_ACTUAL_EIGHT_SCOPE_REPORT_SECTION_AND_PAGE_BOUNDS", "pages": pages,
    "model_scores_in_preview": "Both new fixed loc positions remain pending in the real frozen snapshot;engineering replays are separate",
    "malformed_accounting_rejected": rejected, "page_bounds_violations": len(outside),
    "pdf_sha256": hashlib.sha256(pdf.read_bytes()).hexdigest(),
    "source_sha256": {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in (qualification, summary_path, Path(renderer.__file__), Path(__file__))},
    "new_model_calls": 0, "new_original_grader_calls": 0,
    "limit": "Actual existing section renderer;not the final two reports. Visual inspection is separate."}
(output / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
print(json.dumps({key: result[key] for key in ("status", "pages", "page_bounds_violations")}))
