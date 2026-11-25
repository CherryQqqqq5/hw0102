import hashlib
import json
from pathlib import Path

from scripts.export_performance_evidence import scrub


root = Path.cwd().resolve()
here = root / "work/report-tools-overlay-20261126"
selection = json.loads((here / "SELECTION.json").read_bytes())
output = root / "work/hw0102-publish/shared/reproduction-report-tools-20261126"
if output.exists() or any(path.is_symlink() for path in (output, *output.parents)):
    raise ValueError("Use the new declared overlay directory; do not overwrite a snapshot")


def sha(data):
    return hashlib.sha256(data).hexdigest()


for name, expected in (
        ("work/render_hy4_final_reports.py", selection["expected_renderer_sha256"]),
        ("work/parallel-free-evaluation-20261124/prepare_report_data.py", selection["expected_consumer_sha256"])):
    if sha((root / name).read_bytes()) != expected:
        raise ValueError("The selected current source changed: " + name)

entries = [(name, "source_code") for name in selection["code"]]
entries += [(name, "execution_record") for name in selection["records"]]
entries += [(str((here / name).relative_to(root)), "source_code" if name.endswith(".py") else "delivery_metadata")
    for name in ("SELECTION.json", "README.md", "copy_overlay.py")]
prepared = {}
for name, kind in entries:
    source = root / name
    if (Path(name).is_absolute() or ".." in Path(name).parts or source.is_symlink()
            or not source.resolve().is_relative_to(root) or name in prepared):
        raise ValueError("Invalid or repeated selected source: " + name)
    raw = source.read_bytes()
    if source.suffix == ".py" or source.name.endswith(".py.txt"):
        compile(raw, name, "exec")
    if source.suffix == ".json":
        json.loads(raw)
    data = scrub(raw.decode(), root).encode() if kind == "execution_record" else raw
    if source.suffix == ".json":
        json.loads(data)
    destination = source.name if source.parent == here else name
    prepared[name] = (data, {"path": destination, "kind": kind, "source_sha256": sha(raw),
        "source_bytes": len(raw), "export_sha256": sha(data), "export_bytes": len(data),
        "byte_identical": data == raw})
if sum(len(data) for data, _ in prepared.values()) > 2 * 1024 * 1024:
    raise ValueError("The selected small report-tool overlay exceeds2MiB")

manifest = {"kind": selection["kind"], "base_snapshot": selection["base"],
    "base_manifest_sha256": sha((output.parent / "reproduction-20261126/SOURCE_MANIFEST.json").read_bytes()),
    "files": {name: row for name, (_, row) in prepared.items()},
    "new_model_calls": 0, "base_snapshot_modified": False}
output.mkdir()
for name, (data, row) in prepared.items():
    if sha((root / name).read_bytes()) != row["source_sha256"]:
        raise ValueError("A source changed before copying: " + name)
    target = output / row["path"]
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
manifest_path = output / "SOURCE_MANIFEST.json"
manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
checksums = {row["path"]: row["export_sha256"] for _, row in prepared.values()}
checksums[manifest_path.name] = sha(manifest_path.read_bytes())
(output / "SHA256SUMS").write_text("".join(f"{value}  {name}\n" for name, value in sorted(checksums.items())))
for name, expected in checksums.items():
    if sha((output / name).read_bytes()) != expected:
        raise ValueError("The copied artifact differs: " + name)
print(json.dumps({"output": str(output.relative_to(root)), "files": len(prepared) + 2,
    "source_files": len(selection["code"]), "execution_records": len(selection["records"]),
    "bytes": sum(path.stat().st_size for path in output.rglob("*") if path.is_file()),
    "all_exports_byte_checked": True, "new_model_calls": 0}, ensure_ascii=False))
