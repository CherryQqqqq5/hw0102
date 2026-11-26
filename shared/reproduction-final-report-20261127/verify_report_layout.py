import argparse
import hashlib
import json
from pathlib import Path

import fitz


parser = argparse.ArgumentParser()
parser.add_argument("--pdf-dir", type=Path, required=True)
parser.add_argument("--out-dir", type=Path, required=True)
args = parser.parse_args()
args.out_dir.mkdir(parents=True, exist_ok=False)
reports = []
for path in sorted(args.pdf_dir.glob("*.pdf")):
    document = fitz.open(path)
    texts, pages, problems = [], [], []
    for number, page in enumerate(document, 1):
        text = page.get_text()
        texts.append(text)
        fonts, bold = set(), 0
        for block in page.get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                for span in line["spans"]:
                    if not span["text"].strip():
                        continue
                    fonts.add(span["font"])
                    bold += "Medium" in span["font"]
                    box = fitz.Rect(span["bbox"])
                    if not page.rect.contains(box):
                        problems.append({"page": number, "outside_page": span["text"]})
                    if "STHeiti" not in span["font"]:
                        problems.append({"page": number, "unexpected_font": span["font"]})
        image = args.out_dir / f"{path.stem}-page-{number:02d}.png"
        page.get_pixmap(matrix=fitz.Matrix(1.4, 1.4), alpha=False).save(image)
        pages.append({"page": number, "text_characters": len(text), "fonts": sorted(fonts),
            "bold_spans": bold, "image": image.name})
    text = "\n".join(texts)
    for phrase in ("一、实验目的", "二、实验原理", "三、实验环境", "四、实验步骤",
            "五、实验结果", "六、结果分析", "七、实验结论"):
        if phrase not in text:
            problems.append({"missing_section": phrase})
    for phrase in ("参考文献", "附录", "内部预览", "尚无记录", "尚无原评分"):
        if phrase in text:
            problems.append({"unexpected_text": phrase})
    links = [link.get("uri") for page in document for link in page.get_links() if link.get("uri")]
    if links != ["https://github.com/CherryQqqqq5/hw0102"]:
        problems.append({"unexpected_links": links})
    (args.out_dir / (path.stem + ".txt")).write_text(text)
    reports.append({"file": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "page_count": len(document), "pages": pages, "links": links, "problems": problems})
result = {"reports": reports, "status": "PASS" if len(reports) == 2
    and all(not report["problems"] for report in reports) else "FAIL", "new_model_calls": 0}
(args.out_dir / "layout-verification.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
print(json.dumps(result, ensure_ascii=False))
if result["status"] != "PASS":
    raise SystemExit(1)
