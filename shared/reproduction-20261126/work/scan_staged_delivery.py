import subprocess
from pathlib import Path
from zipfile import ZipFile

import pdfplumber

from course_eval.export_revision import HOME_PATH, PRIVATE, SECRET


def decode_for_scan(data):
    return data.decode("utf-8", errors="replace")


root = Path("work/hw0102-publish")
names = subprocess.check_output(["git", "-C", str(root), "diff", "--cached", "--name-only", "-z"]).decode().split("\0")
files = [root / name for name in names if name]
exceptions = 0
pdf_files = 0
for path in files:
    if path.suffix.lower() == ".pdf":
        with pdfplumber.open(path) as document:
            pages = [page.extract_text() for page in document.pages]
            if not pages or any(not page for page in pages):
                raise ValueError("PDF has a page without extractable text: " + str(path))
            content = "\n".join(pages) + "\n" + repr(document.metadata)
        pdf_files += 1
    elif path.suffix.lower() == ".whl":
        with ZipFile(path) as wheel:
            if wheel.testzip() is not None:
                raise ValueError("A staged wheel failed its archive integrity check: " + str(path))
            content = "\n".join(decode_for_scan(wheel.read(name)) for name in wheel.namelist() if not name.endswith("/"))
    elif path.suffix.lower() == ".zip":
        with ZipFile(path) as archive:
            if archive.testzip() is not None:
                raise ValueError("A staged evidence ZIP failed its archive integrity check: " + str(path))
            for member in archive.infolist():
                if member.is_dir():
                    continue
                with archive.open(member) as stream:
                    tail = ""
                    while data := stream.read(1024 * 1024):
                        chunk = tail + decode_for_scan(data)
                        if any(pattern.search(chunk) for pattern in (SECRET, PRIVATE, HOME_PATH)):
                            raise ValueError("Sensitive archive member requires review: " + str(path) + ":" + member.filename)
                        tail = chunk[-4096:]
        continue
    else:
        content = decode_for_scan(path.read_bytes())
    if path in {root / "shared/course_eval/export_revision.py",
            root / "shared/runtime-snapshots/nvidia-v30/course_eval/export_revision.py",
            root / "shared/runtime-snapshots/nvidia-v31/course_eval/export_revision.py",
            root / "shared/runtime-snapshots/hy4-v18/course_eval/export_revision.py",
            root / "shared/runtime-snapshots/hy4-v20/course_eval/export_revision.py",
            root / "shared/reproduction-20261125/course_eval/export_revision.py",
            root / "shared/reproduction-20261125/work/frozen-performance-dsh-parallel-guard-20261124/course_eval/export_revision.py",
            root / "shared/reproduction-20261125/work/frozen-performance-free-v27/course_eval/export_revision.py",
            root / "shared/reproduction-20261125/work/frozen-performance-free-v31/course_eval/export_revision.py",
            root / "shared/reproduction-20261125/work/frozen-performance-hy4-feal-linear-v19/course_eval/export_revision.py",
            root / "shared/reproduction-20261125/work/frozen-performance-hy4-sql-layout-v18/course_eval/export_revision.py",
            root / "shared/reproduction-20261125/work/frozen-performance-hy4-sql-layout-v18-guidance-off/course_eval/export_revision.py",
            root / "shared/reproduction-20261126/course_eval/export_revision.py",
            root / "shared/reproduction-20261126/work/frozen-performance-dsh-parallel-guard-20261124/course_eval/export_revision.py",
            root / "shared/reproduction-20261126/work/frozen-performance-free-v27/course_eval/export_revision.py",
            root / "shared/reproduction-20261126/work/frozen-performance-free-v28/course_eval/export_revision.py",
            root / "shared/reproduction-20261126/work/frozen-performance-free-v30/course_eval/export_revision.py",
            root / "shared/reproduction-20261126/work/frozen-performance-free-v31/course_eval/export_revision.py",
            root / "shared/reproduction-20261126/work/frozen-performance-hy4-feal-linear-v19/course_eval/export_revision.py",
            root / "shared/reproduction-20261126/work/frozen-performance-hy4-sql-layout-v18/course_eval/export_revision.py",
            root / "shared/reproduction-20261126/work/frozen-performance-hy4-sql-layout-v18-guidance-off/course_eval/export_revision.py",
            root / "shared/reproduction-20261126/work/frozen-performance-hy4-submit-boundary-v20/course_eval/export_revision.py"}:
        # 检测器本身包含拒绝规则，只排除规则定义，保留其余源码扫描。
        lines = content.splitlines(keepends=True)
        definitions = [line for line in lines if line.startswith(("PRIVATE = re.compile(", "HOME_PATH = re.compile("))]
        if len(definitions) != 2:
            raise ValueError("Unexpected detector definition")
        content = "".join(line for line in lines if line not in definitions)
        exceptions += len(definitions)
    if any(pattern.search(content) for pattern in (SECRET, PRIVATE, HOME_PATH)):
        raise ValueError("Sensitive marker requires review: " + str(path))
print({"staged_files": len(files), "sensitive_artifact_hits": 0,
       "pdf_files": pdf_files, "detector_definition_exceptions": exceptions,
       "largest_bytes": max((path.stat().st_size for path in files), default=0)})
