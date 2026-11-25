import hashlib
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


root = Path.cwd().resolve()
folder = root / "work/parallel-free-evaluation-20261124"
publish = root / "work/hw0102-publish/作业二/evidence"
sources = {"core": folder / "final-evidence", "guidance": folder / "final-guidance-evidence-20261126"}
stem = "performance75-final-20261126"
if list(publish.glob(stem + "-part*.zip*")) or (publish / stem / "ARCHIVE_MANIFEST.json").exists():
    raise ValueError("Preserve existing completed or interrupted archive parts")
indices = {name: json.loads((path / "index.json").read_bytes()) for name, path in sources.items()}
if (indices["core"]["stage"] != "complete_core_and_revision_evidence"
        or not indices["core"]["all_current_positions_exported"]
        or len(indices["core"]["runs"]) != 246
        or indices["guidance"]["stage"] != "complete_three_guidance_ablations"
        or len(indices["guidance"]["runs"]) != 3):
    raise ValueError("Use the full246 core/development positions and three separate fixed ablations")
run_sources = [row["source_relative"] for index in indices.values() for row in index["runs"]]
if len(set(run_sources)) != 249:
    raise ValueError("The source views duplicate a physical scored run")


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


members = {}
for label, source in sources.items():
    for path in source.rglob("*"):
        if path.is_symlink():
            raise ValueError("Archive sources must not contain symbolic links")
        if path.is_file():
            name = str(Path(label) / path.relative_to(source))
            members[name] = {"source": path, "bytes": path.stat().st_size, "sha256": sha(path)}

parts, archive, active, covered = [], None, [], set()
temporary = None
soft_limit, hard_limit = 70 * 1024 * 1024, 90 * 1024 * 1024


def close_part():
    global archive, active, temporary
    if archive is None:
        return
    archive.close()
    if temporary.stat().st_size >= hard_limit:
        raise ValueError("An archive part exceeds the explicit90MiB Git file limit")
    with ZipFile(temporary) as incoming:
        if incoming.namelist() != active:
            raise ValueError("Archive paths differ from the written member list")
        for name in active:
            with incoming.open(name) as stream:
                actual = hashlib.file_digest(stream, "sha256").hexdigest()
            if actual != members[name]["sha256"] or name in covered:
                raise ValueError("An archive member differs or repeats: " + name)
            covered.add(name)
    complete = temporary.with_suffix("")
    temporary.rename(complete)
    parts.append({"file": complete.name, "bytes": complete.stat().st_size,
        "sha256": sha(complete), "members": list(active), "all_member_bytes_equal": True,
        "CRC_checked_while_reading_all_members": True})
    print(json.dumps({"part": complete.name, "bytes": complete.stat().st_size, "members": len(active)}), flush=True)
    archive, active, temporary = None, [], None


for name, record in sorted(members.items()):
    # 写入前按未压缩大小预留；单个大文件独占分包，完成后仍检查实际硬上限。
    reserve = record["bytes"] + record["bytes"] // 1000 + 4096
    if archive is not None and archive.fp.tell() + reserve > soft_limit:
        close_part()
    if archive is None:
        temporary = publish / (stem + f"-part{len(parts) + 1}.zip.part")
        archive = ZipFile(temporary, "x", compression=ZIP_DEFLATED, compresslevel=6)
        archive.comment = b"Full246scoredcore/development plus3guidance;filtered evidence;2026-11-26"
    if sha(record["source"]) != record["sha256"]:
        raise ValueError("A source changed after its inventory: " + name)
    archive.write(record["source"], name)
    active.append(name)
    if archive.fp.tell() >= soft_limit:
        close_part()
close_part()
if covered != set(members):
    raise ValueError("The archive parts omit an exported evidence member")
destination = publish / stem
destination.mkdir(exist_ok=True)
manifest = {"format": "complete_performance_evidence_archives_v1", "scored_physical_runs": 249,
    "core_and_development_runs": 246, "separate_guidance_runs": 3,
    "raw_passed": sum(row["metrics"]["passed"] for index in indices.values() for row in index["runs"]),
    "actual_own_zero_requests": sum(row["metrics"]["actual_requests"] for index in indices.values() for row in index["runs"]),
    "parts_extract_into_one_directory": True, "parts": parts,
    "files": {name: {key: value for key, value in item.items() if key != "source"} for name, item in members.items()},
    "index_source_sha256": {name: sha(source / "index.json") for name, source in sources.items()},
    "packager_source_sha256": sha(Path(__file__)), "all_source_and_archived_bytes_equal": True,
    "new_model_calls": 0, "new_original_grader_calls": 0,
    "scope": "All unique scored core and development positions plus three prespecified guidance ablations. Historical unknown/unscored attempts, source versions, final report data/review and PDFs remain separate required submission members. Original failures retained; no claim that all249 passed."}
(destination / "ARCHIVE_MANIFEST.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
print(json.dumps({"parts": len(parts), "members": len(members), "physical_scored_runs": 249,
    "raw_passed": manifest["raw_passed"], "own_zero_requests": manifest["actual_own_zero_requests"],
    "all_archived_bytes_equal": True}, ensure_ascii=False), flush=True)
