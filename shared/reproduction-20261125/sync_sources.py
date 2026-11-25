import argparse
import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys


DESTINATION = Path(__file__).resolve().parent
BASE = "work/parallel-free-evaluation-20261124/"
CODE = [BASE + name for name in (
    "run_ready_queues.py", "ready_coordinator.py", "run_hy4_trial.py", "resource_trial.py",
    "resource_warm_trial.py", "image_copy_http1.py", "image_copy_proxy_cdn.py", "run_fixed_free_trials.py",
    "prepare_reuse_ablation.py", "run_reuse_ablation.py", "resume_verified_hy4.py", "recover_hy4_quota.py",
    "analyze_hy4.py", "join_scoped_revisions.py", "prepare_report_data.py", "analyze_nvidia_v28.py",
    "export_joined_evidence.py", "export_nvidia_v28.py", "export_nvidia_history.py",
    "snapshot_execution_environment.py", "qualify_offline_environment.py")]
CODE += ["scripts/" + name for name in (
    "export_performance_evidence.py", "summarize_performance_comparison.py", "run_performance_queue.py",
    "run_performance_trial.py", "run_performance_matrix.py", "run_pinned_image_copy.py",
    "import_pinned_image_copy.py", "prepare_registry_export_tool.py", "harbor_artifact_capture.py",
    "check_dsh_runtime.py", "check_dsh_harbor_transport.py", "check_reusable_runtime.py")]
CODE += ["work/" + name for name in (
    "render_hy4_final_reports.py", "render_course_phase_reports.py", "render_delivery_pdf_qa.py",
    "scan_staged_delivery.py", "package_final_submission.py", "check_codebuddy_free_models.py")]
CODE += ["work/nvidia75-parallel-dispatch-v32-20261125/" + name for name in (
    "prepare.py", "run_lane.py", "benchmarks_entry.py")]
CODE += ["work/nvidia75-transport-v28-20261125/" + name for name in ("run_lane.py", "external_runtimes.py")]
CODE += ["work/nvidia75-v27-20261125/" + name for name in ("analyze.py", "export.py")]
CODE += ["work/nvidia75-idle-alignment-v31-20261125/prepare.py",
    "work/nvidia75-small-actions-v30-20261125/prepare.py",
    "work/hy4-free-readiness-20261124/codebuddy-guard.sh",
    "work/hy4-free-readiness-20261124/request_guard.py",
    "work/hw0102-publish/shared/scripts/render_hw0102_final.py"]
CODE += ["work/json-in-semantics-20261125/" + name for name in (
    "public_json_types_probe.py", "expanded/public_contract_probe.py", "oracle-bool/public_oracle_bool_probe.py",
    "oracle-bool/ascii-transport/prepare_repair.py", "oracle-bool/ascii-transport/qualify_transport.py")]
CODE += ["work/feal-linear-helper-20261125/" + name for name in (
    "prepare_readmission.py", "prepare_readmission_inputs.py", "prepare_repair.py", "qualify_controller.py",
    "qualify_generated.py", "qualify_linux.py", "qualify_delivery.py")]
CODE += ["work/xarray-2905-semantics-20261125/" + name for name in (
    "public_object_probe.py", "prepare_repair.py", "qualify_public_contract.py", "separate-public-reference.patch",
    "public-sources/original-variable.py", "public-sources/current-variable.py")]
CODE += ["work/pytest-7205-semantics-20261125/" + name for name in (
    "public_setup_repr_probe.py", "prepare_repair.py", "qualify_public_contract.py", "separate-public-reference.patch",
    "public-sources/original-setuponly.py", "public-sources/mature-setuponly.py", "public-sources/original-test_setuponly.py")]
CODE += ["work/pytest-5631-preservation-20261125/" + name for name in ("prepare_and_run.py", "qualify_preservation.py")]
RUNTIMES = (
    "frozen-performance-free-v27", "frozen-performance-dsh-parallel-guard-20261124",
    "frozen-performance-hy4-feal-linear-v19", "frozen-performance-hy4-sql-layout-v18-guidance-off",
    "frozen-performance-hy4-sql-layout-v18", "frozen-performance-free-v31",
)
PLANS = [BASE + "final-sql75-quota-recovered/" + name for name in ("main-plan.json", "repeat-plan.json")]
PLANS += ["work/nvidia75-" + name + "/plan.json" for name in (
    "parallel-dispatch-v32-20261125", "idle-alignment-v31-20261125", "small-actions-v30-20261125", "v27-20261125")]
PLANS += ["work/" + name + "/plan.json" for name in (
    "json-in-semantics-20261125/oracle-bool/ascii-transport/frozen",
    "feal-linear-helper-20261125/readmission", "xarray-2905-semantics-20261125/frozen",
    "pytest-7205-semantics-20261125/frozen", "pytest-5631-preservation-20261125/frozen",
    "json-in-semantics-20261125/frozen", "json-in-semantics-20261125/expanded/frozen",
    "json-in-semantics-20261125/oracle-bool/frozen")]
METADATA = [BASE + "final-sql75-quota-recovered/" + name for name in ("tasks.json", "checks.json", "scopes.json")]
METADATA += [BASE + name for name in ("requirements-execution-20261125.txt", "execution-environment-20261125.json")]
METADATA += ["work/vmshare/performance75-dsh-hy4-v10/" + name for name in (
    "protocol.json", "tasks.json", "environment-pins.json")]
TEXT_SUFFIXES = {".py", ".mjs", ".cjs", ".sh", ".c", ".java", ".yaml", ".yml", ".json", ".txt", ".md", ".patch", ".Dockerfile"}


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read(path):
    return json.loads(path.read_bytes())


def contained(root, name):
    path = root / name
    if Path(name).is_absolute() or ".." in Path(name).parts or path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
        raise ValueError("A source or output escaped the explicit reproduction tree: " + str(name))
    return path


def dependency_sources(root, initial):
    pending, seen = [root / name for name in initial if name.endswith(".py")], set()
    discovered = set()
    while pending:
        path = pending.pop()
        if path in seen:
            continue
        seen.add(path)
        for node in ast.walk(ast.parse(path.read_text())):
            names = []
            if isinstance(node, ast.Import):
                names = [item.name for item in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = ([node.module + "." + item.name for item in node.names]
                    if node.module in {"course_eval", "scripts"} else [node.module])
            for name in names:
                if name.startswith(("course_eval.", "scripts.")):
                    source = root / Path(*name.split(".")).with_suffix(".py")
                    if source.is_file() and source not in seen:
                        pending.append(source)
                        discovered.add(str(source.relative_to(root)))
    discovered.add("course_eval/dsh_sandbox.py")
    return sorted(discovered)


def existing_helpers(root):
    sys.path.insert(0, str(root))
    spec = importlib.util.spec_from_file_location("source_sync_existing_exporter", root / "scripts/export_performance_evidence.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def source_sync(root):
    root = root.resolve(strict=True)
    if root == DESTINATION or DESTINATION.is_relative_to(root / "work/vmshare"):
        raise ValueError("Select the author source project,never a live run")
    helpers = existing_helpers(root)
    records, runtime_inventory, external = {}, {}, []
    code = sorted(set(CODE + dependency_sources(root, CODE)))

    def copy(name, kind):
        source = contained(root, name)
        if not source.is_file():
            raise FileNotFoundError("An allowlisted source is missing: " + name)
        original = source.read_bytes()
        data = helpers.scrub(original.decode("utf-8"), root).encode("utf-8") if kind == "configuration_record" else original
        destination = contained(DESTINATION, name)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            if destination.read_bytes() != data:
                raise ValueError("Never replace a previously synchronized source silently: " + name)
        else:
            with destination.open("xb") as stream:
                stream.write(data)
        records[name] = {"source": name, "source_sha256": hashlib.sha256(original).hexdigest(),
            "source_bytes": len(original), "export_sha256": sha(destination), "export_bytes": len(data),
            "byte_identical": original == data, "kind": kind,
            "transformation": "existing exporter.scrub only; provenance,not a new executable admission" if kind == "configuration_record" else "none"}

    for name in code:
        copy(name, "source_code")
    for runtime in RUNTIMES:
        directory = root / "work" / runtime
        files = {}
        for path in sorted(directory.rglob("*")):
            if not path.is_file() or "__pycache__" in path.parts:
                continue
            name = str(path.relative_to(root))
            files[str(path.relative_to(directory))] = {"sha256": sha(path), "bytes": path.stat().st_size}
            if path.suffix == ".whl":
                matches = [candidate for candidate in (DESTINATION.parent / "runtime-snapshots").glob("*/course_eval/sqlparse.whl")
                    if sha(candidate) == sha(path)]
                if not matches:
                    raise ValueError("The omitted public resource has no already published exact source")
                external.append({"source": name, "sha256": sha(path), "bytes": path.stat().st_size,
                    "published_copy_relative_to_reproduction": os.path.relpath(matches[0], DESTINATION),
                    "included_in_this_directory": False, "scope": "Already published public sqlparse wheel; no duplicate binary resource is copied"})
            elif path.suffix in TEXT_SUFFIXES:
                copy(name, "frozen_source_code")
            else:
                raise ValueError("An unreviewed binary/resource entered the source snapshot: " + name)
        runtime_inventory[runtime] = {"files": files, "scope": "Complete original resource inventory; public wheel bytes are referenced separately,not bundled again"}
    metadata = set(METADATA + PLANS)
    for name in PLANS:
        plan = read(contained(root, name))
        for key in ("manifest", "checks", "artifact_capture_policy", "external_runtime_manifest"):
            if key in plan:
                path = Path(plan[key])
                metadata.add(str((path if path.is_absolute() else root / path).resolve().relative_to(root)))
    for name in sorted(metadata):
        copy(name, "configuration_record")
    original_launcher = root / "work/.venv/bin/harbor"
    launcher = DESTINATION / "launchers/harbor_entry.py"
    if not launcher.is_file():
        raise FileNotFoundError("The explicit portable Harbor entry is required")
    records["launchers/harbor_entry.py"] = {"source": "work/.venv/bin/harbor", "source_sha256": sha(original_launcher),
        "source_bytes": original_launcher.stat().st_size, "export_sha256": sha(launcher), "export_bytes": launcher.stat().st_size,
        "byte_identical": False, "kind": "portable_launcher",
        "transformation": "Remove machine shebang and locate the nearest reproduction scripts directory; preserve the real prepare_args->Harbor app entry. New model execution requires its own newly qualified launcher/policy digest."}
    generated = {name: {"sha256": sha(DESTINATION / name), "bytes": (DESTINATION / name).stat().st_size}
        for name in ("README.md", "sync_sources.py")}
    manifest = {"schema": "course_reproduction_source_manifest_v1", "stage": "code_and_provenance_only_not_final_submission",
        "files": records, "generated_files": generated, "runtime_inventory": runtime_inventory,
        "external_public_resources": external, "new_model_calls": 0, "new_original_grader_calls": 0,
        "excluded": ["All model/run traces,candidates,hidden graders/gold,caches,images,SDK payloads,credentials,STOP and account metadata"],
        "scope": "Explicit source and public-input allowlist plus static local import closure. Never follow all_files_sha256 into raw/private evidence. Sanitized plans preserve original source hashes but are provenance records,not ready-to-run admissions."}
    output = DESTINATION / "SOURCE_MANIFEST.json"
    data = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode()
    if output.exists() and output.read_bytes() != data:
        raise FileExistsError("The source manifest already exists; review any new source version separately")
    if not output.exists():
        output.write_bytes(data)
    return verify_sources()


def verify_sources():
    manifest = read(DESTINATION / "SOURCE_MANIFEST.json")
    for name, row in manifest["files"].items():
        path = contained(DESTINATION, name)
        if sha(path) != row["export_sha256"] or path.stat().st_size != row["export_bytes"]:
            raise ValueError("A synchronized exported source changed: " + name)
        if row["byte_identical"] and (row["source_sha256"] != row["export_sha256"] or row["source_bytes"] != row["export_bytes"]):
            raise ValueError("A claimed exact source is not byte identical: " + name)
        if path.suffix == ".py":
            compile(path.read_text(), str(path), "exec")
        elif path.suffix == ".json":
            read(path)
    for name, row in manifest["generated_files"].items():
        if sha(DESTINATION / name) != row["sha256"]:
            raise ValueError("A source-manifest helper or explanation changed")
    for row in manifest["external_public_resources"]:
        path = (DESTINATION / row["published_copy_relative_to_reproduction"]).resolve(strict=True)
        if not path.is_relative_to(DESTINATION.parent / "runtime-snapshots") or sha(path) != row["sha256"]:
            raise ValueError("An already published exact public dependency changed")
    expected = set(manifest["files"]) | set(manifest["generated_files"]) | {"SOURCE_MANIFEST.json", "VALIDATION.json"}
    extra = [str(path.relative_to(DESTINATION)) for path in DESTINATION.rglob("*")
        if path.is_file() and str(path.relative_to(DESTINATION)) not in expected
        and not (path.suffix == ".pyc" and "__pycache__" in path.relative_to(DESTINATION).parts[:-1])]
    if extra:
        raise ValueError("Unexpected files entered the code-only directory: " + repr(extra))
    return {"status": "verified", "source_files": len(manifest["files"]),
        "source_bytes": sum(row["export_bytes"] for row in manifest["files"].values()),
        "frozen_runtime_versions": len(manifest["runtime_inventory"]),
        "public_resources_referenced_not_copied": len(manifest["external_public_resources"]),
        "new_model_calls": 0, "new_original_grader_calls": 0, "final_results_complete": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("sync", "verify"))
    parser.add_argument("--source-root", type=Path)
    args = parser.parse_args()
    if args.action == "sync" and args.source_root is None:
        parser.error("sync requires the explicit author project source root")
    print(json.dumps(source_sync(args.source_root) if args.action == "sync" else verify_sources()))
