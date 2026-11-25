import argparse
from email.parser import Parser
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from urllib.request import urlopen
import zipfile


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    root, folder = Path.cwd(), Path(__file__).parent.resolve()
    output = args.out.resolve()
    if not output.is_relative_to(folder) or output == folder:
        raise ValueError("The fresh qualification must have its own new work directory")
    output.mkdir()
    extra = folder / "offline-extra-wheels"
    extra.mkdir(exist_ok=True)
    observed = json.loads((folder / "execution-environment-20261125.json").read_text())["installed_distributions"]
    canonical = lambda name: re.sub(r"[-_.]+", "-", name).lower()
    previous = json.loads((root / "work/analysis-wheelhouse-validation.json").read_text())
    requirements = {}
    for line in (root / "work/hw0102-publish/shared/requirements-analysis.txt").read_text().splitlines():
        if line.strip() and not line.startswith("#"):
            name, version = line.split("==", 1)
            requirements[canonical(name)] = (name, version)
    rebuilt = {canonical(item.split("==", 1)[0]) for item in previous["cached_distributions_repacked_with_wheel"]}
    official_names = set(previous["official_release_hash_verified"])
    candidates = {}
    for directory in (root / "work/official-analysis-wheelhouse", root / "work/cached-analysis-wheelhouse"):
        for path in directory.glob("*.whl"):
            with zipfile.ZipFile(path) as archive:
                member, = [name for name in archive.namelist() if name.endswith(".dist-info/METADATA")]
                metadata = Parser().parsestr(archive.read(member).decode())
            candidates.setdefault((canonical(metadata["Name"]), metadata["Version"]), []).append(path)
    local, artifacts = [], []
    for normalized, (name, version) in requirements.items():
        matches = candidates.get((normalized, version), [])
        if normalized in rebuilt:
            path, = [path for path in matches if path.parent.name == "cached-analysis-wheelhouse"]
            expected = sha(path)
            origin = "retained installed distribution previously repacked with wheel; not an official release hash"
        else:
            path, = [path for path in matches if path.parent.name == "official-analysis-wheelhouse" and path.name in official_names]
            metadata = json.loads((root / "work/analysis-package-metadata" / (name + "-" + version + ".json")).read_text())
            published, = [item for item in metadata["urls"] if item["filename"] == path.name]
            expected = published["digests"]["sha256"]
            if sha(path) != expected:
                raise ValueError("A retained official wheel differs from its publisher digest")
            origin = "cached publisher metadata and exact official release SHA256"
        local.append(name + " @ " + path.as_uri() + " --hash=sha256:" + expected)
        artifacts.append({"path": str(path.relative_to(root)), "sha256": expected,
            "origin": origin, "name": name, "version": version})
    if len(local) != 82 or len(rebuilt) != 11:
        raise ValueError("Preserve the exact previous71 official plus11 reconstructed package scope")
    for name in ("keyring", "jaraco-classes", "jaraco-context", "jaraco-functools", "more-itertools"):
        version = observed[name]
        metadata_url = "https://pypi.org/pypi/" + name + "/" + version + "/json"
        with urlopen(metadata_url, timeout=25) as response:
            metadata = json.load(response)
        if metadata["info"]["version"] != version:
            raise ValueError("The public package metadata returned another installed version")
        wheels = [entry for entry in metadata["urls"] if not entry.get("yanked")
            and entry["packagetype"] == "bdist_wheel" and entry["filename"].endswith("-py3-none-any.whl")]
        item, = wheels
        if Path(item["filename"]).name != item["filename"]:
            raise ValueError("A public wheel filename is not a plain package member")
        path = extra / item["filename"]
        if not path.exists():
            with urlopen(item["url"], timeout=25) as response:
                path.write_bytes(response.read())
        expected = item["digests"]["sha256"]
        if sha(path) != expected:
            raise ValueError("A public extra wheel differs from the publisher digest")
        write(extra / (name + "-" + version + ".json"), metadata)
        local.append(name + " @ " + path.as_uri() + " --hash=sha256:" + expected)
        artifacts.append({"path": str(path.relative_to(root)), "sha256": expected,
            "origin": metadata_url, "name": name, "version": version})
        print(json.dumps({"official_extra_wheel_verified": name, "version": version}), flush=True)
    requirements = output / "local-wheels.txt"
    requirements.write_text("\n".join(local) + "\n")
    record = {"phase": "fresh_offline_analysis_environment_prepared", "new_model_calls": 0,
        "new_original_grader_calls": 0, "driver_sha256": sha(Path(__file__)), "artifacts": artifacts,
        "artifact_count": len(artifacts), "commands": [], "cleanup_complete": False,
        "scope": "Fresh87-package macOS analysis environment: previous82 exact packages plus five observed required keyring dependencies. Current complete136-package execution environment is recorded separately. This does not rerun models, Docker graders or claim clean installation of all136 optional execution packages."}
    proof = output / "result.json"
    write(proof, record)
    uv = shutil.which("uv")
    if uv is None:
        raise RuntimeError("Use the existing package installer; do not install a new global tool")
    environment = os.environ | {"UV_CACHE_DIR": str(output / "cache"), "TMPDIR": str(output / "process-tmp"),
        "MSWEA_GLOBAL_CONFIG_DIR": str(output / "miniswe-config"), "MSWEA_SILENT_STARTUP": "1", "PYTHONPATH": str(root)}
    Path(environment["TMPDIR"]).mkdir()
    venv = output / "venv"
    commands = [[uv, "venv", "--python", str(root / "work/.venv/bin/python"), str(venv)],
        [uv, "pip", "install", "--python", str(venv / "bin/python"), "--offline", "--no-deps", "--require-hashes", "-r", str(requirements)],
        [uv, "pip", "check", "--python", str(venv / "bin/python")],
        [str(venv / "bin/python"), str(folder / "export_joined_evidence.py"), "--verify-only", "--out", str(folder / "final-evidence")]]
    for index, command in enumerate(commands):
        result = subprocess.run(command, cwd=root, env=environment, capture_output=True, text=True)
        log = output / (str(index) + ".log")
        log.write_text(result.stdout + "\n" + result.stderr)
        record["commands"].append({"arguments": command, "returncode": result.returncode,
            "log": str(log.relative_to(root)), "log_sha256": sha(log)})
        record["phase"] = "offline_command_returned"
        write(proof, record)
        print(json.dumps({"command_index": index, "returncode": result.returncode}), flush=True)
        result.check_returncode()
    versions = subprocess.run([str(venv / "bin/python"), "-c",
        "import importlib.metadata,json,sys;print(json.dumps({'python':sys.version,'prefix':sys.prefix,'packages':{d.metadata['Name']:d.version for d in importlib.metadata.distributions()}}))"],
        cwd=root, env=environment, capture_output=True, text=True, check=True)
    record["isolated_environment"] = json.loads(versions.stdout)
    actual = {re.sub(r"[-_.]+", "-", name).lower(): version for name, version in record["isolated_environment"]["packages"].items()}
    if len(actual) != 87 or any(version != observed[name] for name, version in actual.items()):
        raise ValueError("The actual isolated package versions differ from the frozen observed dependencies")
    index_path = folder / "final-evidence/index.json"
    record.update(phase="actual_fresh_offline_artifact_verification_passed", evidence_index_sha256=sha(index_path),
        evidence_snapshot_stage=json.loads(index_path.read_text())["stage"])
    for path in (venv, output / "cache", output / "process-tmp", output / "miniswe-config"):
        if path.exists():
            shutil.rmtree(path)
    record["cleanup_complete"] = not venv.exists() and not (output / "cache").exists()
    write(proof, record)
    print(json.dumps({"phase": record["phase"], "installed_packages": len(actual),
        "new_model_calls": 0, "temporary_environment_removed": record["cleanup_complete"]}), flush=True)


if __name__ == "__main__":
    main()
