import argparse
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

from scripts.export_performance_evidence import digest, export_captured_artifacts, inspect_run, scrub
from scripts.summarize_performance_comparison import control_artifact_metrics


def read(path):
    return json.loads(path.read_text())


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def contained(root, name):
    path = root / name
    if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
        raise ValueError("An evidence member escapes its declared directory")
    return path


def verify_run(output, record):
    for member in record["files"]:
        if digest(contained(output, member["path"])) != member["export_sha256"]:
            raise ValueError("An exported evidence member changed")
    directory = contained(output, record["path"])
    if inspect_run(directory, record["framework"]) != record["metrics"]:
        raise ValueError("Export changed original scores, own fresh zero-fee receipts or usage")
    protocol = read(directory.with_suffix(".protocol.json"))
    control = control_artifact_metrics(directory, record["framework"], protocol["configuration"])
    if {key: value for key, value in control.items() if key != "final_verification_sha256"} != {
            key: value for key, value in record["control"].items() if key != "final_verification_sha256"}:
        raise ValueError("Export changed the actual final public or protected result")
    return record["metrics"]["passed"]


def verify_source(root, output, record, row):
    source = contained(root, record["source_relative"])
    destination = contained(output, record["path"])
    if source != contained(root, row["run_dir"]) or inspect_run(source, record["framework"]) != record["metrics"]:
        raise ValueError("The current source no longer matches the cached scored export")
    protocol = source.with_suffix(".protocol.json")
    configuration = read(protocol)["configuration"]
    if control_artifact_metrics(source, record["framework"], configuration) != record["control"]:
        raise ValueError("The current source control evidence differs from the cached export")
    for member in record["files"]:
        exported = contained(output, member["path"])
        original = protocol if exported == destination.with_suffix(".protocol.json") else source / exported.relative_to(destination)
        if digest(original) != member["source_sha256"]:
            raise ValueError("A current source member differs from the earlier exported source SHA")


def verify(output):
    index = read(output / "index.json")
    expected = [run["source_relative"] for run in index["runs"]]
    if len(expected) != len(set(expected)):
        raise ValueError("Shared original and effective views duplicate a physical scored run")
    for name, member in index["snapshots"].items():
        if digest(contained(output, member["path"])) != member["export_sha256"]:
            raise ValueError("An exported analysis snapshot changed: " + name)
    passed = sum(verify_run(output, record) for record in index["runs"])
    for view, members in index["views"].items():
        if len(members) != len(set(members)) or set(members) - set(expected):
            raise ValueError("A declared evidence view duplicates or lacks a scored run: " + view)
    return {"stage": index["stage"], "unique_original_scored_runs": len(expected), "raw_passed": passed,
        "actual_requests": sum(record["metrics"]["actual_requests"] for record in index["runs"]),
        "all_core_and_revision_positions_exported": index["all_current_positions_exported"], "new_model_calls": 0}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary", type=Path, default=Path("work/parallel-free-evaluation-20261124/joint-policy-summary/summary.json"))
    parser.add_argument("--out", type=Path, default=Path("work/parallel-free-evaluation-20261124/final-evidence"))
    parser.add_argument("--max-new-runs", type=int)
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument("--require-complete", action="store_true")
    args = parser.parse_args()
    args.summary = args.summary.resolve()
    root, output = Path.cwd(), args.out.resolve()
    if args.verify_only:
        print(json.dumps(verify(output)), flush=True)
        return
    if args.max_new_runs is not None and args.max_new_runs <= 0:
        raise ValueError("A limited qualification export must include at least one actual run")
    if output == root or not output.is_relative_to(root / "work"):
        raise ValueError("The staged evidence must remain under the project work directory")
    summary = read(args.summary)
    folder = Path(__file__).parent.resolve()
    spec = importlib.util.spec_from_file_location("export_report_sources", folder / "prepare_report_data.py")
    consumer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(consumer)
    acceptance = consumer.incremental_sources(summary, root, folder)
    if acceptance is None:
        raise ValueError("The joint exporter requires source-verified incremental acceptance")
    if args.require_complete and not summary["complete_all225"]:
        raise ValueError("A final export requires all original225 and all fixed final revisions")
    groups = {"original_core": acceptance["original_core_rows"], "effective_policy_and_dsh": summary["rows"],
        "final_task_revisions": acceptance["new_revision_rows"],
        "earlier_json_development": acceptance["previous_json_development_rows"]}
    rows = {row["run_dir"]: row for group in groups.values() for row in group}
    if args.out.absolute().is_symlink() or any(parent.is_symlink() for parent in args.out.absolute().parents):
        raise ValueError("The export directory must not traverse symbolic links")
    for source_name in rows:
        source = contained(root, source_name)
        if source.is_relative_to(output) or output.is_relative_to(source):
            raise ValueError("The export directory overlaps an actual original scored run")
    output.mkdir(parents=True, exist_ok=True)
    existing_path = contained(output, "index.json")
    existing = read(existing_path) if existing_path.exists() else {"runs": []}
    prior = {record["source_relative"]: record for record in existing["runs"]}
    if set(prior) - set(rows):
        raise ValueError("A new source snapshot drops an already exported original scored position")
    records, newly_exported = [], 0
    for source_name, row in rows.items():
        if source_name in prior:
            record = prior[source_name]
            verify_source(root, output, record, row)
            verify_run(output, record)
            records.append(record)
            continue
        if args.max_new_runs is not None and newly_exported >= args.max_new_runs:
            continue
        source = contained(root, source_name)
        framework = "dsh" if row["arm"] == "dsh" else "mini-swe"
        metrics = inspect_run(source, framework)
        for key in ("task", "passed", "wall_seconds", "actual_requests", "verified_zero_credit_requests", "input_tokens", "output_tokens"):
            if metrics[key] != row[key]:
                raise ValueError("The source row no longer describes its actual independent score or billing")
        relative = Path("runs") / source.parent.name / source.name
        destination = contained(output, str(relative))
        if destination.exists():
            checkpoint = destination / "export-record.json"
            if not checkpoint.exists():
                raise FileExistsError("An unfinished filtered export requires diagnosis: " + str(destination))
            record = read(checkpoint)
            if record["source_relative"] != source_name or record["metrics"] != metrics:
                raise ValueError("An interrupted export checkpoint differs from the actual source")
            verify_source(root, output, record, row)
            verify_run(output, record)
            records.append(record)
            continue
        subprocess.run([sys.executable, "-m", "course_eval.export_revision", "--runs", str(source),
            "--out", str(destination)], check=True, capture_output=True, text=True)
        task = read(source / "trial.json")["task"]
        capture = export_captured_artifacts(source, destination, root, (task.get("candidate_scope") or {}).get("artifacts", []))
        protocol = source.with_suffix(".protocol.json")
        protocol_out = contained(output, str(relative.with_suffix(".protocol.json")))
        protocol_out.write_text(scrub(protocol.read_text(), root))
        files = []
        for exported in [path for path in destination.rglob("*") if path.is_file()] + [protocol_out]:
            original = protocol if exported == protocol_out else source / exported.relative_to(destination)
            files.append({"path": str(exported.relative_to(output)), "source_sha256": digest(original),
                "export_sha256": digest(exported)})
        configuration = read(protocol)["configuration"]
        record = {"source_relative": source_name, "path": str(relative), "task": row["task"],
            "framework": framework, "metrics": metrics,
            "control": control_artifact_metrics(source, framework, configuration),
            "artifact_capture": capture, "files": files}
        verify_run(output, record)
        write(contained(output, str(relative / "export-record.json")), record)
        records.append(record)
        newly_exported += 1
        print(json.dumps({"exported": source_name, "files": len(files), "passed": metrics["passed"]}), flush=True)
    snapshots = {}
    snapshot_sources = {"effective_summary": args.summary,
        "intact_original_summary": root / acceptance["core_summary"],
        "effective_tasks": root / summary["source_manifest_path"]}
    for name, source in snapshot_sources.items():
        path = contained(output, name + ".json")
        path.write_text(scrub(source.read_text(), root))
        snapshots[name] = {"path": path.name, "source_relative": str(source.relative_to(root)),
            "source_sha256": digest(source), "export_sha256": digest(path)}
    included = {record["source_relative"] for record in records}
    all_exported = included == set(rows)
    index = {"format": "source_verified_joined_original_and_task_revision_evidence_v1",
        "stage": "complete_core_and_revision_evidence" if all_exported and summary["complete_all225"] else "partial_internal_evidence",
        "exporter_sha256": digest(Path(__file__)), "sanitizer_sha256": digest(root / "course_eval/export_revision.py"),
        "all_current_positions_exported": all_exported, "original_core_complete225": summary["complete_all225"],
        "expected_current_unique_runs": len(rows), "runs": records, "snapshots": snapshots,
        "views": {name: [row["run_dir"] for row in group if row["run_dir"] in included] for name, group in groups.items()},
        "new_model_calls": 0,
        "scope": "Each physical scored run is exported once. Views reference shared evidence; no score selection or best-of replacement. Earlier semantic failures and all five scored JSON development positions remain. This index alone is not the final submission: ablations, unscored/unknown billing records, code/dependencies, independent review and final PDFs are separate required members.",
        "filtering": "Reuses the existing course_eval.export_revision sanitizer. Structured model actions, request history, tools, control, own billing identities and original scores retained; response reasoning/text may be filtered. Source and exported SHA-256 are separate; no claim of byte-identical unfiltered full reasoning. No hidden tests/solutions, credentials, VM disks or rebuildable caches."}
    write(contained(output, "index.json"), index)
    print(json.dumps(verify(output)), flush=True)


if __name__ == "__main__":
    main()
