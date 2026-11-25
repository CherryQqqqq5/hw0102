import hashlib
import json
from pathlib import Path

from scripts.export_performance_evidence import digest, scrub


root = Path.cwd().resolve()
folder = root / "work/parallel-free-evaluation-20261124"
output = root / "work/hw0102-publish/作业二/evidence/performance75-final-20261126"
data_path = folder / "report-data-final75-20261126.json"
review_path = folder / "final-source-and-trace-review-20261126.json"
data, review = json.loads(data_path.read_bytes()), json.loads(review_path.read_bytes())
if (not data["complete_required_experiments"] or not data["main_and_repeat_all75_qualified_pass"]
        or review["source_summary_sha256"] != data["summary_sha256"]
        or review["positions_reviewed"] != {"main": 75, "dsh": 75, "repeat": 75}
        or review["blocking_findings_remaining"] != 0):
    raise ValueError("Only completed actual scores and their exact independent review may enter final metadata")
sources = {
    "joint-summary.json": root / data["summary"],
    "joint-trials.csv": folder / "joint-final75-20261126/trials.csv",
    "tasks.json": root / data["tasks_path"],
    "original225-summary.json": folder / "hy4-original225-final-20261126/summary.json",
    "original225-trials.csv": folder / "hy4-original225-final-20261126/trials.csv",
    "report-data.json": data_path,
    "final-source-and-trace-review.json": review_path,
    "guidance-ablation-review.json": folder / "independent-guidance-ablation-completed-20261126.json",
}
records = {item["path"] for item in data["supplementary"].values()}
records.update(name for item in data["case_sources"].values() for name in item.get("files_sha256", {}))
records.update(str(path.relative_to(root)) for path in (
    folder / "independent-closed177-review-20261126.json",
    folder / "independent-core-after177-incremental-20261126.json",
    folder / "independent-core-after187-incremental-20261126.json",
    folder / "independent-core-after201-incremental-20261126.json",
    folder / "independent-core-after210-incremental-20261126.json",
    folder / "independent-core-after219-incremental-20261126.json",
    root / "work/performance-stop-20261122.json",
    root / "work/free-recovery35-20261126/accepted-unknown35.json",
    root / "work/free-recovery35-20261126/continuation-state.json"))
for path in (folder / "final-reuse-ablation").glob("*.json"):
    records.add(str(path.relative_to(root)))
already_published, already_archived = [], []
for name in sorted(records):
    if name.startswith("work/hw0102-publish/"):
        already_published.append(name.removeprefix("work/hw0102-publish/"))
    elif name.startswith("work/vmshare/"):
        already_archived.append(name)
    else:
        sources["sources/" + name] = root / name
for path in (folder / "finalize_guidance_export.py", root / "work/package_completed_performance_evidence.py", Path(__file__).resolve()):
    sources["tools/" + path.name] = path

provenance, prepared = {}, {}
for name, source in sources.items():
    if (source.is_symlink() or not source.resolve(strict=True).is_relative_to(root)
            or Path(name).is_absolute() or ".." in Path(name).parts):
        raise ValueError("A metadata source/output escapes its scope")
    raw = source.read_bytes()
    code = source.suffix == ".py"
    payload = raw if code else scrub(raw.decode(), root).encode()
    if source.suffix == ".json":
        json.loads(payload)
    if code:
        compile(payload, str(source), "exec")
    target = output / name
    if target.exists():
        raise FileExistsError("Keep each exact metadata version distinct: " + name)
    prepared[name] = payload
    provenance[name] = {"source": str(source.relative_to(root)), "source_sha256": digest(source),
        "export_sha256": hashlib.sha256(payload).hexdigest(), "source_bytes": len(raw), "export_bytes": len(payload),
        "byte_identical": raw == payload, "transformation": "none" if code else "existing exporter.scrub"}
for name, payload in prepared.items():
    target = output / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload)
    if target.read_bytes() != payload:
        raise ValueError("A metadata copy differs")
result = {"format": "final_performance_metadata_provenance_v1", "files": provenance,
    "already_published_references": already_published, "case_members_already_in_scored_archives": already_archived,
    "raw_joined_summary_sha256": data["summary_sha256"], "raw_report_data_sha256": digest(data_path),
    "new_model_calls": 0, "new_original_grader_calls": 0,
    "scope": "Source and export hashes remain separate. Redacted metadata is not falsely accepted as the raw source by full original-engineering regeneration; scored archived records support their independent offline verifier."}
(output / "PROVENANCE.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
print(json.dumps({"copied_files": len(provenance), "already_published": len(already_published),
    "case_sources_already_archived": len(already_archived), "bytes": sum(row["export_bytes"] for row in provenance.values()),
    "all_exports_byte_equal": True, "new_model_calls": 0}, ensure_ascii=False))
