import argparse
import base64
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from course_eval.export_revision import LOG_NAMES, SECRET, sanitize_model
from scripts.export_performance_evidence import inspect_run, scrub
from run_study import FOLDER, ROOT, digest, hashes, read, save


RETAINED_LOG_NAMES = LOG_NAMES | {"regrade-result.json", "eval.sh", "patch.diff", "session.v4.jsonl",
    "dsh-review.jsonl", "dsh-transport.jsonl", "dsh-input.json", "dsh-responses.jsonl",
    "dsh-stderr.log", "shared-environment.json", "submission-review-candidate.json"}


def portable(text, source=None):
    if source is not None and source.name == "export_revision.py" and source.parent.name == "course_eval":
        original = FOLDER / "runtime/course_eval/export_revision.py"
        expected = read(FOLDER / "study-plan.json")["source_hashes"][str(original.relative_to(ROOT))]
        if digest(source) != expected or SECRET.search(text):
            raise ValueError("The reviewed redaction-rule source changed or contains a credential")
        # 脱敏规则中的路径模式属于代码；保留已冻结原件，仍拒绝真实凭据。
        return text
    return scrub(text.replace(str(ROOT), "[project]").replace(str(ROOT.parent), "[server-project]"), ROOT)


def export_file(source, destination):
    text = source.read_text()
    if source.name == "model.jsonl":
        text = sanitize_model(text)
    elif source.name == "agent.json":
        info = json.loads(text)["info"]
        text = json.dumps({"info": {key: info[key] for key in
            ("exit_status", "submission", "model_stats") if key in info}}, ensure_ascii=False, indent=2)
    if "candidates" in source.parts or source.name == "submission-review-candidate.json":
        for entry in json.loads(text)["files"].values():
            decoded = base64.b64decode(entry.get("data", ""), validate=True).decode("utf-8", errors="replace")
            if SECRET.search(decoded):
                raise ValueError("A saved candidate contains a credential: " + str(source))
            portable(decoded)
    text = portable(text, source)
    if source.suffix == ".json":
        json.loads(text)
    elif source.suffix == ".jsonl":
        for line in text.splitlines():
            json.loads(line)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(text)
    return {"source_sha256": digest(source), "export_sha256": digest(destination),
        "export_bytes": destination.stat().st_size}


def export_run(source, destination):
    framework = "dsh" if source.name == "dsh" else "mini-swe"
    before = inspect_run(source, framework)
    files = []
    for path in sorted(source.rglob("*")):
        relative = path.relative_to(source)
        if not path.is_file() or path.is_symlink():
            continue
        if {"starter", "grader-input", "_python", "_deps", "solution", "tests"}.intersection(relative.parts):
            continue
        if (path.name not in RETAINED_LOG_NAMES
                and not {"candidate", "candidates", "tool-output"}.intersection(relative.parts)):
            continue
        proof = export_file(path, destination / relative)
        files.append({"path": str(relative), **proof})
    if inspect_run(destination, framework) != before:
        raise ValueError("Export changed actual scoring, usage or individual zero-credit receipts")
    protocol = source.with_suffix(".protocol.json")
    proof = export_file(protocol, destination.with_suffix(".protocol.json"))
    files.append({"path": "../" + destination.name + ".protocol.json", **proof})
    return {"metrics": before, "files": files}


def verify_export(directory):
    directory = directory.resolve()
    index = read(directory / "index.json")
    checked = 0
    for entry in index["files"]:
        path = (directory / entry["path"]).resolve()
        if not path.is_relative_to(directory) or digest(path) != entry["export_sha256"]:
            raise ValueError("An exported source or result file changed")
        checked += 1
    requests, tokens, passed = 0, 0, 0
    for run in index["runs"]:
        target = (directory / run["path"]).resolve()
        if not target.is_relative_to(directory):
            raise ValueError("An exported run is outside the evidence directory")
        for entry in run["files"]:
            path = (target / entry["path"]).resolve()
            if not path.is_relative_to(directory) or digest(path) != entry["export_sha256"]:
                raise ValueError("An exported trajectory or scoring artifact changed")
            checked += 1
        framework = "dsh" if target.name == "dsh" else "mini-swe"
        actual = inspect_run(target, framework)
        if actual != run["metrics"]:
            raise ValueError("Original scoring, usage or individual zero-credit receipts differ")
        requests += actual["actual_requests"]
        tokens += actual["input_tokens"] + actual["output_tokens"]
        passed += actual["passed"]
    return {"verified_positions": len(index["runs"]), "original_passed": passed,
        "actual_requests_with_zero_credit_receipts": requests, "total_tokens": tokens,
        "verified_files": checked, "new_model_calls": 0}


def main():
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--out", type=Path)
    mode.add_argument("--verify", type=Path)
    args = parser.parse_args()
    if args.verify:
        print(json.dumps(verify_export(args.verify)))
        return
    study, repeat = read(FOLDER / "study-results.json"), read(FOLDER / "repeat-results.json")
    if study["stage"] != "complete" or repeat["stage"] not in {"complete", "not_started"}:
        raise RuntimeError("Finish the registered comparison and repeat decision before export")
    if hashes() != read(FOLDER / "study-plan.json")["source_hashes"]:
        raise RuntimeError("The frozen source changed")
    output = args.out.resolve()
    output.mkdir(parents=True, exist_ok=False)
    inventory = {"source_plan_sha256": digest(FOLDER / "study-plan.json"), "runs": [], "files": []}
    for row in study["rows"] + repeat.get("rows", []):
        source = Path(row["run_dir"])
        if not source.resolve().is_relative_to(FOLDER):
            raise ValueError("A registered run is outside the study")
        relative = source.relative_to(FOLDER)
        record = export_run(source, output / relative)
        inventory["runs"].append({"path": str(relative), **record})
    sources = [path for path in FOLDER.glob("*.py") if path.name != "ops_snapshot.py"]
    sources += list(FOLDER.glob("*.sh"))
    sources += [path for path in (FOLDER / "cpp-image").iterdir() if path.is_file()]
    sources += [FOLDER / name for name in ("README.md", "candidate-tasks.json", "study-plan.json", "study-results.json",
        "repeat-results.json", "joint-trials.csv", "execution.json", "free-model-metadata/cloud-model-metadata.json",
        "remote-output-qualification/result.json", "requirements.txt", "pytest-trace-review.json",
        "final-study-review.json", "aider-python-requirements.txt")]
    if (FOLDER / "repeat-plan.json").exists():
        sources.append(FOLDER / "repeat-plan.json")
    for directory in ("runtime", "inputs", "scoring-amendment-20261127", "baseline-amendment-20261127",
            "preflight-reference-amendment-20261127"):
        sources += [path for path in (FOLDER / directory).rglob("*")
            if path.is_file() and path.suffix in {".py", ".json"} and "__pycache__" not in path.parts]
    for directory, pattern in (("preflight", "*/preflight.json"), ("preparation", "*/manifest.json"),
            ("preparation", "*/config.json"), ("preparation", "*/record.json")):
        sources += sorted((FOLDER / directory).glob(pattern))
    for source in sorted(set(sources)):
        relative = source.relative_to(FOLDER)
        proof = export_file(source, output / relative)
        inventory["files"].append({"path": str(relative), **proof})
    for name in ("export_performance_evidence.py", "run_performance_queue.py", "summarize_performance_comparison.py"):
        source = ROOT / "scripts" / name
        relative = Path("support/scripts") / name
        proof = export_file(source, output / relative)
        inventory["files"].append({"path": str(relative), **proof})
    for source in sorted((ROOT / "work/vmshare/aider").iterdir()):
        if source.is_file():
            relative = Path("support") / source.relative_to(ROOT)
            proof = export_file(source, output / relative)
            inventory["files"].append({"path": str(relative), **proof})
    for name in ("guest_vm.py", "guest_phase.py", "prepare_host.py", "finish_client.py", "measure_guest_cpu.py",
            "install_buildx.py", "prepare_small_image.py", "expand_guest_storage.py", "ENVIRONMENT.md",
            "docker-env.sh", "qualification.json", "host-preparation.json", "cpu-bootstrap.json",
            "client-qualification.json", "small-image.json"):
        source = ROOT.parent / name
        relative = Path("support/server") / name
        proof = export_file(source, output / relative)
        inventory["files"].append({"path": str(relative), **proof})
    inventory["positions"] = len(inventory["runs"])
    save(output / "index.json", inventory)
    verification = verify_export(output)
    save(output / "verification.json", verification)
    archive_path = output.with_suffix(".zip")
    if archive_path.exists():
        raise FileExistsError(archive_path)
    with ZipFile(archive_path, "w", ZIP_DEFLATED, compresslevel=6) as archive:
        for path in sorted(output.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(output))
    with ZipFile(archive_path) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("Evidence archive integrity check failed")
        if any(archive.read(name) != (output / name).read_bytes() for name in archive.namelist()):
            raise RuntimeError("Evidence archive differs from its verified files")
    print(json.dumps({"archive": str(archive_path), "positions": inventory["positions"],
        "bytes": archive_path.stat().st_size, "sha256": digest(archive_path), "new_model_calls": 0}))


if __name__ == "__main__":
    main()
