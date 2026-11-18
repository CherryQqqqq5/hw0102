import argparse
import json
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo


parser = argparse.ArgumentParser()
parser.add_argument("--recovery", type=int, choices=(1, 2, 3, 4, 5, 6, 7, 8, 9), default=1)
args = parser.parse_args()
root = Path("work/hw0102-publish")
label = {1: "恢复补充证据", 2: "接电续跑停止证据", 3: "_v8首轮停止证据", 4: "_v9截断修复停止证据", 5: "_v10原题验证停止证据", 6: "_v11序列化修复停止证据", 7: "_v12评分与输出修复停止证据", 8: "_v13评分与空流修复停止证据", 9: "_v15_260条评分与停止证据"}[args.recovery]
date = "20261118" if args.recovery in (8, 9) else "20261117"
output = Path(f"outputs/作业一二_hy4flash{label}_{date}.zip")
staged = output.with_suffix(".zip.part")
tracked = [os.fsdecode(name) for name in subprocess.check_output(
    ["git", "-C", str(root), "ls-files", "-z"]).split(b"\0") if name]
names = [name for name in tracked if name == "README.md"
         or name.startswith(("shared/", "作业二/configs/", "作业二/evidence/confirmation-hy4flash-free-v",
                             "作业二/evidence/hy4flash-v7-recovery", "作业二/evidence/hy4flash-recovery",
                             "作业二/evidence/hy4flash-v8-"))
         or name in {"作业二/README.md", "作业一/README.md",
                     "作业一/231880296_邱昱宁_作业一.pdf", "作业二/231880296_邱昱宁_作业二.pdf",
                     "作业二/evidence/hy4flash-v7-recovery1-stopped-summary.json",
                     "作业二/evidence/hy4flash-v7-recovery1-20261117.md",
                     "作业二/evidence/hy4flash-recovery1-sleep-events.txt"}]
commit = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
if args.recovery == 4:
    names = [name for name in tracked if name == "README.md"
        or name.startswith(("shared/", "作业二/configs/", "作业二/evidence/hy4flash-v9-repair",
                            "作业二/evidence/codebuddy-single-turn-probe-v9/"))
        or name in {"作业一/README.md", "作业二/README.md",
                    "作业一/231880296_邱昱宁_作业一.pdf", "作业二/231880296_邱昱宁_作业二.pdf"}]
    historical = Path("outputs/作业一二_hy4flash_v8首轮停止证据_20261117.zip")
if args.recovery == 5:
    names = [name for name in tracked if name == "README.md"
        or name.startswith(("shared/", "作业二/configs/", "作业二/evidence/hy4flash-v10-",
                            "作业二/evidence/confirmation-hy4flash-free-v10",
                            "作业二/evidence/hy4flash-recovery-probe-v10/",
                            "作业二/evidence/hy4flash-recovery-replay-v10/"))
        or name in {"作业一/README.md", "作业二/README.md",
                    "作业二/evidence/hy4flash-recovery-validation-v10.json",
                    "作业一/231880296_邱昱宁_作业一.pdf", "作业二/231880296_邱昱宁_作业二.pdf"}]
    historical = Path("outputs/作业一二_hy4flash_v9截断修复停止证据_20261117.zip")
if args.recovery == 6:
    names = [name for name in tracked if name == "README.md"
        or name.startswith(("shared/", "作业二/configs/", "作业二/evidence/hy4flash-v11-",
                            "作业二/evidence/codebuddy-single-turn-probe-v11/"))
        or name in {"作业一/README.md", "作业二/README.md",
                    "作业一/231880296_邱昱宁_作业一.pdf", "作业二/231880296_邱昱宁_作业二.pdf"}]
    historical = Path("outputs/作业一二_hy4flash_v10原题验证停止证据_20261117.zip")
if args.recovery == 7:
    names = [name for name in tracked if name == "README.md"
        or name.startswith(("shared/", "frozen-runtime/v12/", "作业二/configs/",
                            "作业二/evidence/hy4flash-v12-", "作业二/evidence/confirmation-hy4flash-free-v12",
                            "作业二/evidence/codebuddy-single-turn-probe-v12/"))
        or name in {"作业一/README.md", "作业二/README.md",
                    "作业二/evidence/free-api-options-20261117.md",
                    "作业一/231880296_邱昱宁_作业一.pdf", "作业二/231880296_邱昱宁_作业二.pdf"}]
    historical = Path("outputs/作业一二_hy4flash_v11序列化修复停止证据_20261117.zip")


def load_file(name):
    path = root / name
    if path.is_symlink():
        raise ValueError("Review a tracked symbolic link before packaging: " + name)
    return ZipInfo.from_file(path, name), path.read_bytes()


if args.recovery == 8:
    names = [name for name in tracked if name == "README.md"
        or name.startswith(("shared/", "frozen-runtime/v13/", "作业二/configs/",
                            "作业二/evidence/hy4flash-v13-", "作业二/evidence/confirmation-hy4flash-free-v13",
                            "作业二/evidence/codebuddy-stdout-probe-v13/"))
        or name in {"作业一/README.md", "作业二/README.md", "作业二/evidence/free-channel-setup-20261118.md",
                    "作业一/231880296_邱昱宁_作业一.pdf", "作业二/231880296_邱昱宁_作业二.pdf"}]
    historical = Path("outputs/作业一二_hy4flash_v12评分与输出修复停止证据_20261117.zip")
if args.recovery == 9:
    names = [name for name in tracked if name == "README.md"
        or name.startswith(("shared/", "frozen-runtime/v14/", "frozen-runtime/v15/", "作业二/configs/",
                            "作业二/evidence/hy4flash-v14-", "作业二/evidence/hy4flash-v15-",
                            "作业二/evidence/confirmation-hy4flash-free-v15", "作业二/evidence/preparation-free/"))
        or name in {"作业一/README.md", "作业二/README.md", "作业二/evidence/free-channel-setup-20261118.md",
                    "作业一/231880296_邱昱宁_作业一.pdf", "作业二/231880296_邱昱宁_作业二.pdf"}]
    historical = Path("outputs/作业一二_hy4flash_v13评分与空流修复停止证据_20261118.zip")


with ZipFile(staged, "w") as archive:
    archive.comment = f"Free evaluation recovery evidence; published commit {commit}; incomplete 270-position matrix".encode()
    with ThreadPoolExecutor(max_workers=8) as executor:
        for info, payload in executor.map(load_file, names):
            archive.writestr(info, payload, compress_type=ZIP_DEFLATED, compresslevel=6)
    if args.recovery in (4, 5, 6, 7, 8, 9):
        archive.write(historical, "history/" + historical.name)
with ZipFile(staged) as archive:
    assert archive.testzip() is None
staged.replace(output)
print(json.dumps({"archive": str(output), "files": len(names) + (args.recovery in (4, 5, 6, 7, 8, 9)), "bytes": output.stat().st_size,
                  "published_commit": commit,
                  "scope": "Shared code, configurations, all free-batch sources and recovery evidence; earlier full historical package remains separate"}, ensure_ascii=False))
