import argparse
import base64
import copy
import json
from pathlib import Path
import subprocess
import sys

from benchmark_key_export import APPROVED_RUNS, candidate_projection, prepare_filtered_source
from course_eval.export_revision import HOME_PATH, PRIVATE, PRIVATE_PEM, SECRET
from export_joined_evidence import verify_run, verify_source
from scripts.export_performance_evidence import digest, export_captured_artifacts, inspect_run, scrub
from scripts.summarize_performance_comparison import control_artifact_metrics


ROOT = Path.cwd()
FOLDER = Path(__file__).parent
DEFAULT_OUT = FOLDER / "benchmark-key-export-qualification-20261126"


def rejected(name, callback):
    try:
        callback()
    except (ValueError, UnicodeDecodeError) as error:
        return {"name": name, "rejected": True, "error_type": type(error).__name__}
    raise AssertionError("An invalid private export was accepted: " + name)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    output = parser.parse_args().out.resolve()
    if not output.is_relative_to(ROOT / "work"):
        raise ValueError("A private qualification must remain inside project work")
    output.mkdir(exist_ok=False)
    rows = json.loads((FOLDER / "joint-after-loc-0432-20261126/summary.json").read_text())["rows"]
    rows = [row for row in rows if row["task"] == "openssl-selfsigned-cert"]
    actual, negatives, source_bindings = [], [], {}
    for row in rows:
        source = ROOT / row["run_dir"]
        framework = "dsh" if row["arm"] == "dsh" else "mini-swe"
        relative = Path("runs") / source.parent.name / source.name
        destination = output / relative
        original_hashes = {str(path.relative_to(source)): digest(path) for path in source.rglob("*") if path.is_file()}
        stage, redactions = source, []
        if framework == "mini-swe":
            stage = output / "stages" / source.parent.name / source.name
            redactions = prepare_filtered_source(source, stage)
        subprocess.run([sys.executable, "-m", "course_eval.export_revision", "--runs", str(stage),
            "--out", str(destination)], check=True, capture_output=True, text=True)
        scope = json.loads((source / "trial.json").read_text())["task"].get("candidate_scope") or {}
        capture = export_captured_artifacts(source, destination, ROOT, scope.get("artifacts", []))
        protocol = source.with_suffix(".protocol.json")
        protocol_out = destination.with_suffix(".protocol.json")
        protocol_out.write_text(scrub(protocol.read_text(), ROOT))
        files = []
        for exported in [path for path in destination.rglob("*") if path.is_file()] + [protocol_out]:
            original = protocol if exported == protocol_out else source / exported.relative_to(destination)
            files.append({"path": str(exported.relative_to(output)), "source_sha256": digest(original),
                "export_sha256": digest(exported)})
        record = {"source_relative": row["run_dir"], "path": str(relative), "framework": framework,
            "metrics": inspect_run(source, framework), "control": control_artifact_metrics(source, framework,
                json.loads(protocol.read_text())["configuration"]), "files": files,
            "benchmark_private_key_redactions": redactions, "artifact_capture": capture}
        assert verify_run(output, record) is True
        verify_source(ROOT, output, record, row)
        for original in source.rglob("candidate-*.json"):
            before = json.loads(original.read_text())
            after = json.loads((destination / original.relative_to(source)).read_text())
            assert {k: v for k, v in before.items() if k != "files"} == {
                k: v for k, v in after.items() if k not in {"files", "export_redactions"}}
            assert set(before["files"]) == set(after["files"])
            for name, item in after["files"].items():
                assert {k: v for k, v in before["files"][name].items() if k != "data"} == {
                    k: v for k, v in item.items() if k != "data"}
                decoded = base64.b64decode(item["data"], validate=True).decode("utf-8")
                assert not any(pattern.search(decoded) for pattern in (SECRET, PRIVATE, HOME_PATH, PRIVATE_PEM))
                if name.endswith(".crt"):
                    assert item == before["files"][name]
        for exported in destination.rglob("*"):
            if exported.is_file():
                assert not PRIVATE_PEM.search(exported.read_text())
        assert original_hashes == {str(path.relative_to(source)): digest(path) for path in source.rglob("*") if path.is_file()}
        original_result = (destination / "result.json").read_bytes()
        (destination / "result.json").write_bytes(original_result + b"\n")
        negatives.append(rejected("export_byte_tamper_" + row["arm"], lambda: verify_run(output, record)))
        (destination / "result.json").write_bytes(original_result)
        source_bindings.update({str(source / name): value for name, value in original_hashes.items()})
        actual.append({"arm": row["arm"], "original_and_export_passed": True,
            "metrics_and_control_identical": True, "source_unchanged": True,
            "candidate_snapshots_redacted": len(redactions), "redacted_candidate_artifacts": sum(len(r["files"]) for r in redactions),
            "actual_requests": record["metrics"]["actual_requests"], "redactions": redactions,
            "native_capture": capture})
    source = ROOT / next(iter(APPROVED_RUNS))
    original = next(source.rglob("candidate-*.json"))
    base = json.loads(original.read_text())
    key = "/app/ssl/server.key"
    for name, mutation in (
        ("wrong_internal_path", lambda d: d["files"].update({"/app/other.key": d["files"].pop(key)})),
        ("invalid_base64", lambda d: d["files"][key].update(data="%%%")),
        ("incomplete_private_pem", lambda d: d["files"][key].update(data=base64.b64encode(b"-----BEGIN " + b"RSA PRIVATE KEY-----\nunfinished").decode())),
        ("unrelated_secret_after_pem", lambda d: d["files"][key].update(data=base64.b64encode(base64.b64decode(d["files"][key]["data"]) + b"\nsk-" + b"z" * 40).decode())),
        ("unrelated_home_after_pem", lambda d: d["files"][key].update(data=base64.b64encode(base64.b64decode(d["files"][key]["data"]) + b"\n" + (HOME_PATH.pattern.split("[", 1)[0] + "/private").encode()).decode())),
    ):
        altered = copy.deepcopy(base)
        mutation(altered)
        negatives.append(rejected(name, lambda value=altered: candidate_projection(json.dumps(value).encode())))
    negatives.append(rejected("unreviewed_run", lambda: prepare_filtered_source(output / "unreviewed", output / "bad-stage")))
    result = {"format": "real_openssl_filtered_export_qualification_v1", "new_model_calls": 0,
        "actual_original_runs": actual, "negative_controls": negatives, "original_sources_sha256": source_bindings,
        "exporter_sha256": digest(FOLDER / "export_joined_evidence.py"),
        "filter_sha256": digest(FOLDER / "benchmark_key_export.py"),
        "qualification_driver_sha256": digest(Path(__file__)),
        "frozen_sanitizer_sha256": digest(ROOT / "course_eval/export_revision.py"),
        "scope": "Real archived runs are exported and consumed without models or grading. Private candidate payloads cannot restore their original keys; original scores/digests/modes/eligibility are source records. Negative payloads are explicit local mutations, not experiment results."}
    (output / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"actual_runs": len(actual), "negative_controls": len(negatives), "all_passed": True,
        "new_model_calls": 0, "result_sha256": digest(output / "result.json")}))


if __name__ == "__main__":
    main()
