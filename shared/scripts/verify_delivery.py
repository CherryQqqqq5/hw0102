import argparse
import json
import os
import zipfile
from pathlib import Path

import pdfplumber


parser = argparse.ArgumentParser()
parser.add_argument("--archive", type=Path)
args = parser.parse_args()
root = Path("work/hw0102-publish")
batch = os.environ.get("COURSE_REPORT_BATCH", "confirmation-hy4flash-free-v13")
plan = json.loads((root / ("作业二/configs/" + batch.replace("confirmation-", "confirmation-plan-", 1) + ".json")).read_text())
protocol = os.environ.get("COURSE_REPORT_PROTOCOL", "abad82197a3b7833478261a0360f2eae873efdaa")
summary = json.loads((root / f"作业二/evidence/{batch}-summary/summary.json").read_text())
trials = json.loads((root / f"作业二/evidence/{batch}-summary/trials.json").read_text())
audit = json.loads((root / f"作业二/evidence/{batch}-source-audit.json").read_text())
stopped = json.loads((root / "作业二/evidence/codebuddy-v3-stopped-summary.json").read_text())
assert len(trials) == 270 and all(row["scoreable"] for row in trials)
assert summary["previous_attempt_count"] == len(plan["preserved_previous_attempts"]) and summary["previous_scored_count"] == 0
assert stopped["all_attempts"] == 281 and stopped["all_scored"] == 279
assert audit["batch"] == batch and audit["primary_positions"] == 270
assert audit["protocol_commit"] == protocol and audit["reused_positions"] == plan["reused_positions"]
assert audit["new_positions"] == plan["new_positions"]
assert audit["free_billing"]["missing_responses"] == 0
assert audit["free_billing"]["reported_credit_for_returned_responses"] == 0
assert sum(item["missing_responses"] for item in audit["previous_free_billing"]) == plan["historical_unknown_cli_requests"]["formal"]
assert audit["free_preparation"]["missing_responses"] == plan["historical_unknown_cli_requests"]["preparation"]
assert (audit["mechanical_free_billing"]["missing_responses"]
        + sum(item["missing_responses"] for item in audit["previous_free_billing"])
        == audit["all_attempt_usage"]["usage_unreturned_requests"])
assert summary["transport_sensitivity"]["tasks"] == 29
results = []
for assignment in ("一", "二"):
    filename = f"231880296_邱昱宁_作业{assignment}.pdf"
    source = Path("outputs") / filename
    target = root / f"作业{assignment}" / filename
    assert source.read_bytes() == target.read_bytes(), filename
    page_text = []
    with pdfplumber.open(source) as pdf:
        for index, page in enumerate(pdf.pages, 1):
            content = page.extract_text() or ""
            assert len(content) > 100, (filename, index, "nearly empty page")
            assert "阶段稿" not in content and "�" not in content, (filename, index)
            for char in page.chars:
                assert -0.1 <= char["x0"] <= char["x1"] <= page.width + 0.1, (filename, index, "horizontal bounds")
                assert -0.1 <= char["top"] <= char["bottom"] <= page.height + 0.1, (filename, index, "vertical bounds")
            page_text.append(content)
    assert "231880296" in page_text[0] and "邱昱宁" in page_text[0], filename
    if assignment == "一":
        assert "86.7%" in "\n".join(page_text), filename
        assert "免费模型重复基线复测" in "\n".join(page_text), filename
        assert "hy4flash-free" in "\n".join(page_text), filename
    else:
        for required in ("免费模型固定任务复测协议", "任务成功率与机制消融", "代表性轨迹", "方法形成与历史结果",
                         "hy4flash-free", "hy4-flash-free", "4096", "270", protocol[:7], "CodeBuddy", "29题",
                         "未返回响应", "缺失输入/输出用量", "rawUsage.credit=0", "0.55积分", "真实费用未知",
                         "mini-swe-agent", "Terminus 2"):
            assert required in "\n".join(page_text), required
    Path(f"work/final-assignment-{assignment}-text.txt").write_text("\n\n".join(page_text))
    results.append({"file": str(source), "pages": len(page_text), "characters_per_page": list(map(len, page_text))})
if args.archive:
    with zipfile.ZipFile(args.archive) as archive:
        assert archive.testzip() is None
        for assignment in ("一", "二"):
            name = f"作业{assignment}/231880296_邱昱宁_作业{assignment}.pdf"
            assert archive.read(name) == (root / name).read_bytes(), name
        assert all(not name.startswith("work/") and "/.env" not in name for name in archive.namelist())
        results.append({"archive": str(args.archive), "members": len(archive.namelist()), "integrity": "pass"})
print(json.dumps(results, ensure_ascii=False, indent=2))
