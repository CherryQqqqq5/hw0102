import argparse
import json
import subprocess
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


root = Path("work/hw0102-publish")
parser = argparse.ArgumentParser()
parser.add_argument("--live-grading", action="store_true")
args = parser.parse_args()
output = Path("outputs/作业一二_真实评分标准与失效分析_20261118.zip" if args.live_grading
              else "outputs/作业一二_课程要求核查与报告补充_20261118.zip")
names = ["README.md", "作业一/231880296_邱昱宁_作业一.pdf", "作业二/231880296_邱昱宁_作业二.pdf",
         "作业一/README.md", "作业一/evidence/task-records.json", "作业一/evidence/task-records.csv",
         "作业二/README.md", "作业二/evidence/course-rubric-audit-20261118.md",
         "作业二/evidence/course-rubric-pdf-structure-20261118.json",
         "作业二/evidence/course-rubric-validation-20261118.json",
         "作业二/evidence/confirmation-hy4flash-free-v16-analysis.json",
         "shared/scripts/build_course_task_records.py", "shared/scripts/render_hw0102_final.py",
         "shared/scripts/render_confirmation_report.py", "shared/scripts/render_delivery_pdf_qa.py",
         "shared/CONFIRMATION.md"]
if args.live_grading:
    names = [name for name in names if name not in (
        "作业二/evidence/course-rubric-pdf-structure-20261118.json", "作业二/evidence/course-rubric-validation-20261118.json")]
    names.extend(["作业二/evidence/course-grading-tables-20261118.md",
                  "作业二/evidence/course-live-grading-pdf-structure-20261118.json",
                  "作业二/evidence/course-live-grading-validation-20261118.json",
                  "作业二/evidence/course-execution-failure-analysis-20261118.json",
                  "shared/scripts/analyze_course_execution_failures.py"])
commit = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
staged = output.with_suffix(".zip.part")
with ZipFile(staged, "w", compression=ZIP_DEFLATED) as archive:
    archive.comment = ("Report supplement to the preserved complete v16 evidence package; commit " + commit).encode()
    for name in names:
        archive.write(root / name, name)
with ZipFile(staged) as archive:
    assert archive.testzip() is None and archive.namelist() == names
    for name in names:
        assert archive.read(name) == (root / name).read_bytes()
staged.replace(output)
print(json.dumps({"archive": str(output), "members": len(names), "bytes": output.stat().st_size,
                  "commit": commit, "all_members_match_published_files": True}, ensure_ascii=False))
