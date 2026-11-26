import hashlib
import json
from pathlib import Path
import re

import pdfplumber


root = Path.cwd()
folder = root / "work/parallel-free-evaluation-20261124"
data = json.loads((folder / "report-data-final75-20261126.json").read_bytes())
review = json.loads((folder / "final-source-and-trace-review-20261126.json").read_bytes())
if (not data["complete_required_experiments"] or not data["main_and_repeat_all75_qualified_pass"]
        or review["source_summary_sha256"] != data["summary_sha256"] or review["blocking_findings_remaining"]):
    raise ValueError("Final PDF checks require the qualified actual final results")
tasks = json.loads((root / data["tasks_path"]).read_bytes())["selected"]
output = root / "work/report-structure-review-20261126/pdf-qa"
output.mkdir(parents=True, exist_ok=True)
results = []
for numeral in ("一", "二"):
    path = root / "outputs" / f"231880296_邱昱宁_作业{numeral}.pdf"
    pages, links, fonts = [], set(), set()
    with pdfplumber.open(path) as document:
        for number, page in enumerate(document.pages, 1):
            text = page.extract_text() or ""
            if len(text) < 100 or "�" in text or "内部预览，实验未齐" in text:
                raise ValueError(f"Incomplete or invalid PDF text: {path.name}:{number}")
            for char in page.chars:
                if char["text"].strip():
                    fonts.add(char["fontname"])
                    if "STHeitiSC" not in char["fontname"]:
                        raise ValueError(f"A character does not use Heiti: {path.name}:{number}:{char['fontname']}")
                if not (-0.1 <= char["x0"] <= char["x1"] <= page.width + 0.1
                        and -0.1 <= char["top"] <= char["bottom"] <= page.height + 0.1):
                    raise ValueError(f"A PDF character lies outside its page: {path.name}:{number}")
            if f"智能推理与规划 · 邱昱宁" not in text or not text.rstrip().endswith(str(number)):
                raise ValueError(f"A page footer or sequence differs: {path.name}:{number}")
            pages.append(text)
            links.update(link["uri"] for link in page.hyperlinks if link.get("uri"))
    full = "\n\n".join(pages)
    compact = re.sub(r"\s+", "", full)
    required = ["231880296", "邱昱宁", "hy4flash-free"]
    if numeral == "一":
        required += ["26/30", "30/30", "4/4", "27/30"]
        required += ["extract-elf", "llm-inference-batching-scheduler", "query-optimize", "video-processing"]
    else:
        required += ["75/75", "69/75", "8.0", "134", "16", "1270", "1200", "1209",
            "34,626,096", "27,159,037", "29,615,186", "18,267.7", "20,731.3", "18,700.0",
            "3题消融", "5.8%", "11/12", "12/12", "84.8%", "95.2%"]
        if "附录" in compact:
            raise ValueError("Assignment two must not include the removed per-task appendix")
    if "预期行为" in compact or "任务目标与预期" in compact:
        raise ValueError("The removed expected-behavior column is still present")
    headings = ["一、实验目的", "二、实验原理与" + ("方法" if numeral == "一" else "改进方法"),
        "三、实验环境与设置", "四、实验步骤", "五、实验结果", "六、结果分析与" + ("改进验证" if numeral == "一" else "讨论"),
        "七、实验结论", "参考文献"]
    positions = [compact.find(heading) for heading in headings]
    if min(positions) < 0 or positions != sorted(positions):
        raise ValueError(f"Experiment-report chapters are missing or out of order: {path.name}")
    if not any("Light" in font for font in fonts) or not any("Medium" in font for font in fonts):
        raise ValueError("Both regular and emphasized Heiti must be present")
    missing = [value for value in required if re.sub(r"\s+", "", value) not in compact]
    repository = "https://github.com/CherryQqqqq5/hw0102"
    if missing or not any(uri == repository or uri.startswith(repository + "/") for uri in links):
        raise ValueError(f"Final PDF is missing actual metrics, task rows or source links: {path.name}:{missing}")
    (output / f"assignment-{numeral}-text.txt").write_text(full)
    results.append({"path": str(path), "pages": len(pages), "bytes": path.stat().st_size,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "characters_per_page": list(map(len, pages)),
        "links": sorted(links), "fonts": sorted(fonts), "chapter_order": headings,
        "all_characters_use_Heiti": True, "all_characters_within_pages": True,
        "all_required_actual_values_present": True})
result = {"report_data_sha256": hashlib.sha256((folder / "report-data-final75-20261126.json").read_bytes()).hexdigest(),
    "source_summary_sha256": data["summary_sha256"], "final_science_review_sha256": hashlib.sha256((folder / "final-source-and-trace-review-20261126.json").read_bytes()).hexdigest(),
    "renderer_sha256": hashlib.sha256((root / "work/render_hy4_final_reports.py").read_bytes()).hexdigest(),
    "checker_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), "pdfs": results,
    "visual_inspection_is_separate": True, "new_model_calls": 0}
(output / "structural-and-values-check.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
print(json.dumps({"pdfs": [{"pages": row["pages"], "sha256": row["sha256"]} for row in results],
    "actual_values_and_page_bounds_passed": True, "new_model_calls": 0}, ensure_ascii=False))
