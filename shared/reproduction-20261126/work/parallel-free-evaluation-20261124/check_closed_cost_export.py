import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
from types import SimpleNamespace


BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[1]
OWNER = BASE / "export_nvidia_history.py"
PROOF = BASE / "closed-cost-supplement-qualification-20261125"


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--record-red", action="store_true")
    parser.add_argument("--verify-existing", action="store_true")
    args = parser.parse_args()
    if args.record_red:
        PROOF.mkdir(exist_ok=False)
        before = PROOF / "exporter-before-change.py.txt"
        before.write_bytes(OWNER.read_bytes())
        result = subprocess.run([sys.executable, "-B", str(OWNER), "closed-verify", "--out", str(PROOF / "absent")],
            cwd=ROOT, capture_output=True, text=True, check=False)
        if result.returncode != 2 or "invalid choice" not in result.stderr:
            raise AssertionError("The initial public CLI must expose the actual missing operation")
        value = {"status": "RED_EXPECTED", "owner_sha256": digest(before), "returncode": result.returncode,
            "actual_error": result.stderr, "new_model_calls": 0, "new_original_grader_calls": 0}
        write(PROOF / "red-result.json", value)
        print(json.dumps(value))
        return
    qualify(args.verify_existing)


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def qualify(verify_existing=False):
    spec = importlib.util.spec_from_file_location("qualified_closed_history_owner", OWNER)
    owner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(owner)
    package = BASE / "closed-cost-supplement-20261125"
    if package.exists() and not verify_existing:
        initial = owner.read(package / "index.json")
        if "authoring_source_versions" in initial:
            raise RuntimeError("Do not overwrite an existing final current-version export")
        for member in initial["files"]:
            if digest(owner.contained(package, member["path"])) != member["export_sha256"]:
                raise ValueError("The first69-member qualification changed")
        (PROOF / "first-export-before-source-version-binding-index.json").write_bytes((package / "index.json").read_bytes())
        write(PROOF / "first-export-before-source-version-binding.json", {"status": "selected_sources_only_not_final140_qualification",
            "index_sha256": digest(package / "index.json"), "members": len(initial["files"]),
            "exporter_sha256": initial["exporter_sha256"], "bytes": sum(m["export_bytes"] for m in initial["files"]),
            "scope": "Own unsubmitted generated preview removed after retaining exact inventory;no original run removed."})
        expected = {m["path"] for m in initial["files"]} | {"index.json"}
        if {str(p.relative_to(package)) for p in package.rglob("*") if p.is_file()} != expected:
            raise ValueError("Do not remove an output containing unexpected files")
        shutil.rmtree(package)
    result = owner.verify_closed(package) if verify_existing else owner.export_closed(SimpleNamespace(out=package))
    portable = PROOF / "portable-closed-supplement"
    if verify_existing:
        if digest(package / "index.json") != digest(portable / "index.json"):
            raise ValueError("Only the exact unchanged final package may be reverified")
        previous = PROOF / "result.json"
        backup = PROOF / "result-before-native-payload-negative.json"
        if previous.exists() and not backup.exists():
            backup.write_bytes(previous.read_bytes())
    else:
        shutil.copytree(package, portable)
    review = owner.read(package / "closed-review.json")
    for name, expected in review["source_sha256"].items():
        if digest(ROOT / owner.CLOSED_AUTHORING_VERSIONS.get(name, name)) != expected:
            raise ValueError("A reviewed source/version changed before qualification")
    blocked = []
    vmshare = ROOT / "work/vmshare"
    def guard(event, args):
        if event == "open" and isinstance(args[0], (str, bytes)):
            value = args[0].decode() if isinstance(args[0], bytes) else args[0]
            if Path(value).absolute().is_relative_to(vmshare):
                blocked.append(value)
                raise PermissionError("Original VMshare reads are forbidden for portable qualification")
    sys.addaudithook(guard)
    portable_result = owner.verify_closed(portable)
    index_path = portable / "index.json"
    original_index = index_path.read_bytes()
    originals = {p: digest(p) for p in portable.rglob("*") if p.is_file()}
    negatives = []
    def reject(name, index_change=None, member_change=None):
        index = json.loads(original_index)
        saved = {}
        if index_change:
            index_change(index)
        if member_change:
            relative, transform, lines = member_change
            path = owner.contained(portable, relative)
            saved[path] = path.read_bytes()
            value = [json.loads(x) for x in path.read_text().splitlines()] if lines else owner.read(path)
            value = transform(value)
            path.write_text("".join(json.dumps(x) + "\n" for x in value) if lines else json.dumps(value))
            member, = [m for m in index["files"] if m["path"] == relative]
            member.update(export_sha256=digest(path), export_bytes=path.stat().st_size, byte_identical=False)
        write(index_path, index)
        try:
            owner.verify_closed(portable)
        except (ValueError, KeyError) as exc:
            negatives.append({"name": name, "rejected": True, "reason": str(exc)})
        else:
            raise AssertionError("A real evidence mutation was accepted: " + name)
        finally:
            for path, content in saved.items():
                path.write_bytes(content)
            index_path.write_bytes(original_index)
    index = json.loads(original_index)
    main = index["runs"][0]["path"]
    trace = next(m["path"] for m in index["files"] if m["path"].startswith(main + "/") and m["path"].endswith("/model.jsonl"))
    def changed(value, **fields):
        value.update(fields)
        return value
    reject("original_false_changed_to_true", member_change=(main + "/result.json", lambda v: changed(v, passed=True), False))
    reject("unknown33_amount_filled_zero", member_change=("accepted-unknown33.json", lambda v: changed(v, actual_amount=0), False))
    reject("unknown34_usage_filled_zero", member_change=("accepted-unknown34.json", lambda v: changed(v, actual_usage={"total_tokens": 0}), False))
    reject("physical_unknown_request8_removed", member_change=(trace, lambda rows: [r for r in rows if r.get("request_id") != 8], True))
    reject("qualification_promoted_to_original_score", index_change=lambda v: v["qualifications"][0].update(is_task_position=True, original_score=True))
    reject("repeated_qualification_generation_id", index_change=lambda v: v["qualifications"][1].update(generation_id=v["qualifications"][0]["generation_id"]))
    duplicate = index["runs"][0]["portable_evidence"]["generation_ids"][0]
    def repeat_actual_native_identity(rows):
        for row in rows:
            if row["event"] == "response":
                row["payload"]["id"] = duplicate
            elif row["event"] == "billing_verified":
                row["generation_id"] = duplicate
        return rows
    reject("actual_native_response_and_proof_id_reused", member_change=("runs/minimax_main/model.jsonl", repeat_actual_native_identity, True))
    def change_actual_failure_header(rows):
        for row in rows:
            if row["event"] == "response_headers" and row["request_id"] == 2:
                row["http_status"] = 200
        return rows
    reject("actual503_header_changed_to200", member_change=("runs/minimax_main/model.jsonl", change_actual_failure_header, True))
    reject("extra_unreviewed_source_path", index_change=lambda v: v["files"][0].update(source_relative="work/unreviewed-private-source.json"))
    reject("archive_exception_extended_to_data", index_change=lambda v: v["authoring_source_versions"].update({"work/unreviewed-data.json": {}}))
    final = owner.verify_closed(portable)
    if blocked or any(digest(p) != h for p, h in originals.items()):
        raise AssertionError("Portable verification read original VMshare or left a mutation")
    old = owner.verify(BASE / "nvidia-retained-history-through30-20261125")
    branches = {}
    for label, path in (("v32", BASE / "final-nvidia-v32-summary/summary.json"),
            ("v33", BASE / "nvidia-v33-consumer-qualification/summary.json")):
        branches[label] = len(owner.rows_from(owner.read(path)))
    value = {"status": "PASS", "owner_sha256": digest(OWNER), "driver_sha256": digest(Path(__file__)),
        "review_sha256": owner.CLOSED_REVIEW_SHA, "authoring_archives": owner.closed_source_versions(owner.read(package / "closed-review.json")),
        "authoring_archive_acquisition": {"exporter": "Actual byte copy made before editing;exact prior review SHA matched",
            "report_consumer": "Parent reconstructed an independent archive from current source by manually reversing this turn's sole trial-validation patch;exact historical review SHA matched;active source was not overwritten"},
        "source_versions_checked": {"current_original_sources": 138, "explicit_authoring_archives": 2},
        "export": result, "portable_verify": portable_result, "portable_restored_verify": final,
        "negative_cases": negatives, "original_vmshare_open_attempts": blocked,
        "old_historical_package_verify": old, "old_actual_snapshot_rows_from_counts": branches,
        "old_v32_v33_portable_limit": "No existing v32/v33 history package was found;their exact rows_from branches were exercised with real saved snapshots,not presented as full new portable exports.",
        "package_index_sha256": digest(package / "index.json"), "portable_index_sha256": digest(portable / "index.json"),
        "package_bytes": sum(p.stat().st_size for p in package.rglob("*") if p.is_file()),
        "new_model_calls": 0, "new_original_grader_calls": 0, "vm_commands": 0, "stop_modified": False}
    write(PROOF / "result.json", value)
    print(json.dumps(value, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
