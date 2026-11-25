import argparse
import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil


HERE = Path(__file__).resolve().parent
LIMIT = 32 * 1024 * 1024
TEXT = {".py", ".mjs", ".cjs", ".sh", ".c", ".java", ".yaml", ".yml", ".json", ".txt", ".md", ".patch", ".Dockerfile"}


def read(path):
    return json.loads(path.read_bytes())


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode()


def budget(selected_bytes, reserve_bytes):
    if selected_bytes + reserve_bytes > LIMIT:
        raise ValueError("The explicit source snapshot exceeds32MiB before any copy")
    return selected_bytes + reserve_bytes


def local(root, name):
    path = root / name
    if Path(name).is_absolute() or ".." in Path(name).parts or not path.resolve().is_relative_to(root):
        raise ValueError("An explicit source escaped its root: " + name)
    current = path
    while current != root:
        if current.is_symlink():
            raise ValueError("A source/output path contains a symbolic link: " + name)
        current = current.parent
    return path


def legacy_owner(root, selection):
    adjacent = HERE.parent / "reproduction-20261125"
    folder = adjacent if adjacent.is_dir() else root / "work/hw0102-publish/shared/reproduction-20261125"
    if sha(folder / "sync_sources.py") != selection["legacy_sync_sha256"] or sha(folder / "SOURCE_MANIFEST.json") != selection["legacy_manifest_sha256"]:
        raise ValueError("The separately retained601-source producer changed")
    spec = importlib.util.spec_from_file_location("retained_source_sync_20261125", folder / "sync_sources.py")
    owner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(owner)
    return owner, folder, read(folder / "SOURCE_MANIFEST.json")


def static_sources(root, initial):
    pending, seen = list(initial), set()
    while pending:
        name = pending.pop()
        if name in seen:
            continue
        seen.add(name)
        path = local(root, name)
        if path.suffix != ".py":
            continue
        parts = Path(name).parts
        mount = root / Path(*parts[:2]) if len(parts) > 2 and parts[0] == "work" and parts[1].startswith("frozen-") else root
        for node in ast.walk(ast.parse(path.read_text())):
            modules = [item.name for item in node.names] if isinstance(node, ast.Import) else []
            bases = [path.parent, mount]
            if isinstance(node, ast.ImportFrom):
                if node.level:
                    base = path.parent
                    for _ in range(node.level - 1):
                        base = base.parent
                    bases = [base]
                modules = ([node.module] if node.module else []) + [".".join(filter(None, (node.module, item.name))) for item in node.names if item.name != "*"]
            for module in modules:
                for base in bases:
                    candidate = base / Path(*module.split("."))
                    candidates = [candidate.with_suffix(".py"), candidate / "__init__.py"]
                    for source in candidates:
                        if source.is_file() and source.resolve().is_relative_to(root):
                            relative = str(source.relative_to(root))
                            if relative not in seen:
                                pending.append(relative)
    return sorted(seen)


def selected_sources(root, selection, old_manifest):
    code = {name for name, row in old_manifest["files"].items() if row["kind"] == "source_code"}
    metadata = {name for name, row in old_manifest["files"].items() if row["kind"] == "configuration_record"}
    code.update(selection["code_additions"])
    code.update(row["archive"] for row in selection["source_versions"])
    for entry in selection["dynamic_load_allowlist"]:
        if entry["owner"] != "launchers/harbor_entry.py":
            code.add(entry["owner"])
        code.update(entry["targets"])
    metadata.update(selection["configuration_additions"])
    for name in sorted(metadata):
        if Path(name).name not in {"plan.json", "main-plan.json", "repeat-plan.json"}:
            continue
        plan = read(local(root, name))
        for key in ("manifest", "checks", "artifact_capture_policy", "external_runtime_manifest"):
            if key in plan:
                value = Path(plan[key])
                metadata.add(str((value if value.is_absolute() else root / value).resolve().relative_to(root)))
    runtimes = sorted(set(old_manifest["runtime_inventory"]) | set(selection["additional_runtimes"]))
    files = {name: "source_code" for name in static_sources(root, code)}
    public_wheels = []
    for runtime in runtimes:
        directory = root / "work" / runtime
        for path in sorted(directory.rglob("*")):
            if not path.is_file() or "__pycache__" in path.parts:
                continue
            name = str(path.relative_to(root))
            if path.suffix == ".whl":
                public_wheels.append({"source": name, "sha256": sha(path), "bytes": path.stat().st_size})
            elif path.suffix in TEXT:
                files[name] = "frozen_source_code"
            else:
                raise ValueError("Unreviewed runtime binary is outside the code snapshot: " + name)
    files.update({name: "configuration_record" for name in metadata})
    for name in files:
        if ("node_modules" in Path(name).parts or any(part in {".venv", ".codebuddy", ".git"} for part in Path(name).parts)
                or Path(name).name in {"model.jsonl", "tools.jsonl", "controller.jsonl", "result.json", "final-verification.json"}
                or Path(name).name.startswith(("accepted-unknown", "stop-", "released-stop"))):
            raise ValueError("Private execution evidence cannot enter the code allowlist: " + name)
        if "work/vmshare/" in name and name not in {"work/vmshare/performance75-dsh-hy4-v10/" + item for item in ("protocol.json", "tasks.json", "environment-pins.json")}:
            raise ValueError("Only three prior public task/pin/protocol descriptors may come from VMshare")
    return files, runtimes, public_wheels


def inspect(root, selection_path):
    selection = read(selection_path)
    owner, legacy, old = legacy_owner(root, selection)
    helpers = owner.existing_helpers(root)
    files, runtimes, wheels = selected_sources(root, selection, old)
    rows = {}
    for name, kind in sorted(files.items()):
        source = local(root, name)
        data = source.read_bytes()
        if source.suffix == ".py" or source.name.endswith(".py.txt"):
            compile(data, str(source), "exec")
        if source.suffix == ".json":
            json.loads(data)
        exported = helpers.scrub(data.decode(), root).encode() if kind == "configuration_record" else data
        rows[name] = {"kind": kind, "source_sha256": hashlib.sha256(data).hexdigest(), "source_bytes": len(data),
            "export_sha256": hashlib.sha256(exported).hexdigest(), "export_bytes": len(exported), "byte_identical": data == exported}
    renderer = "work/render_hy4_final_reports.py"
    if rows[renderer]["source_sha256"] != selection["expected_current_renderer_sha256"]:
        raise ValueError("The parent-confirmed renderer version changed; prepare a new explicit selection")
    versions = [{"logical_source": name, "source_sha256": row["source_sha256"], "export_sha256": row["export_sha256"],
        "already_published_relative_to_shared": "reproduction-20261125/" + name, "copied_again": False}
        for name, row in old["files"].items() if row["kind"] in {"source_code", "frozen_source_code"}
        and name in rows and row["source_sha256"] != rows[name]["source_sha256"]]
    versions += [{"logical_source": row["logical_source"], "archive": row["archive"],
        "source_sha256": rows[row["archive"]]["source_sha256"], "export_sha256": rows[row["archive"]]["export_sha256"],
        "copied_exact_archive": True, "scope": row["scope"]} for row in selection["source_versions"]]
    shared = legacy.parent
    for version in versions:
        if "already_published_relative_to_shared" in version and sha(local(shared, version["already_published_relative_to_shared"])) != version["export_sha256"]:
            raise ValueError("An explicitly retained historical source changed")
    patch = selection["external_codebuddy_patch"]
    if sha(shared / patch["relative_to_shared"]) != patch["sha256"]:
        raise ValueError("The existing published client patch changed")
    for wheel in wheels:
        published = shared / "runtime-snapshots/hy4-v18/course_eval/sqlparse.whl"
        if sha(published) != wheel["sha256"]:
            raise ValueError("The omitted wheel has no byte-identical published reference")
        wheel["already_published_relative_to_shared"] = str(published.relative_to(shared))
    launcher = root / "work/.venv/bin/harbor"
    result = {"schema": "course_source_sync_preparation_v2", "stage": "prepared_code_allowlist_only_not_synchronized",
        "legacy_manifest_sha256": selection["legacy_manifest_sha256"], "legacy_sync_sha256": selection["legacy_sync_sha256"],
        "selection_sha256": sha(selection_path), "files": rows, "runtimes": runtimes, "source_versions": versions,
        "preparation_helper_sha256": sha(Path(__file__)), "preparation_readme_sha256": sha(HERE / "README.md"),
        "external_public_wheels": wheels, "external_codebuddy_patch": patch, "external_sdk": selection["external_sdk"],
        "launcher_original": {"source": "work/.venv/bin/harbor", "sha256": sha(launcher), "bytes": launcher.stat().st_size},
        "portable_launcher_sha256": sha(legacy / "launchers/harbor_entry.py"),
        "dynamic_load_allowlist": selection["dynamic_load_allowlist"], "new_model_calls": 0, "new_original_grader_calls": 0,
        "not_included": selection["excluded"], "snapshot_limit_bytes": LIMIT}
    result["selected_export_bytes"] = sum(row["export_bytes"] for row in rows.values())
    result["reserved_manifest_and_helpers_bytes"] = 2 * len(encoded(result)) + 256 * 1024
    result["maximum_prepared_snapshot_bytes"] = budget(result["selected_export_bytes"], result["reserved_manifest_and_helpers_bytes"])
    return result, owner, legacy


def verify_plan(root, selection_path, plan_path):
    actual, owner, legacy = inspect(root, selection_path)
    if actual != read(plan_path):
        raise ValueError("A prepared source/version/export hash changed; never silently refresh its plan")
    return actual, owner, legacy


def verify_snapshot(owner):
    result = owner.verify_sources()
    output = owner.DESTINATION
    manifest = read(output / "SOURCE_MANIFEST.json")
    for version in manifest["source_versions"]:
        if "already_published_relative_to_shared" in version:
            name = version["already_published_relative_to_shared"]
            if not name.startswith("reproduction-20261125/") or sha(local(output.parent, name)) != version["export_sha256"]:
                raise ValueError("A retained historical601-source version changed")
    patch = manifest["external_codebuddy_patch"]
    if sha(local(output.parent, patch["relative_to_shared"])) != patch["sha256"]:
        raise ValueError("The separately published client patch changed")
    return result


def synchronize(root, selection_path, plan_path, output, approved_sha):
    if sha(plan_path) != approved_sha:
        raise ValueError("sync requires the exact reviewed preparation-plan SHA")
    plan, owner, legacy = verify_plan(root, selection_path, plan_path)
    output = output.absolute()
    if output != legacy.parent / "reproduction-20261126" or output.exists() or any(p.is_symlink() for p in (output, *output.parents)):
        raise ValueError("Only a new separate shared/reproduction-20261126 destination is permitted")
    output.mkdir()
    for name in ("sync_sources.py", "README.md"):
        shutil.copyfile(HERE / name, output / name)
    (output / "launchers").mkdir()
    shutil.copyfile(legacy / "launchers/harbor_entry.py", output / "launchers/harbor_entry.py")
    owner.DESTINATION = output
    owner.CODE = [name for name, row in plan["files"].items() if row["kind"] == "source_code"]
    owner.METADATA = [name for name, row in plan["files"].items() if row["kind"] == "configuration_record"]
    owner.PLANS, owner.RUNTIMES = [], plan["runtimes"]
    owner.source_sync(root)
    manifest = read(output / "SOURCE_MANIFEST.json")
    if set(manifest["files"]) != set(plan["files"]) | {"launchers/harbor_entry.py"}:
        raise ValueError("The mature sync owner produced an unexpected source set")
    for name, expected in plan["files"].items():
        if any(manifest["files"][name][key] != expected[key] for key in ("source_sha256", "source_bytes", "export_sha256", "export_bytes", "byte_identical")):
            raise ValueError("Source/export bytes differ from the reviewed allowlist: " + name)
    for name, source in (("SELECTION.json", selection_path), ("SYNC_PLAN.json", plan_path)):
        shutil.copyfile(source, output / name)
        manifest["generated_files"][name] = {"sha256": sha(output / name), "bytes": (output / name).stat().st_size}
    manifest["source_versions"] = plan["source_versions"]
    manifest["external_codebuddy_patch"] = plan["external_codebuddy_patch"]
    manifest["external_sdk"] = plan["external_sdk"]
    (output / "SOURCE_MANIFEST.json").write_bytes(encoded(manifest))
    actual_bytes = sum(p.stat().st_size for p in output.rglob("*") if p.is_file())
    if actual_bytes > LIMIT:
        raise ValueError("The completed code-only snapshot exceeded the preflight32MiB ceiling")
    return verify_snapshot(owner) | {"actual_snapshot_bytes": actual_bytes}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("plan", "verify-plan", "sync", "verify"))
    parser.add_argument("--source-root", type=Path, default=Path.cwd())
    parser.add_argument("--selection", type=Path, default=HERE / "SELECTION.json")
    parser.add_argument("--plan", type=Path, default=HERE / "SYNC_PLAN.json")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--approved-plan-sha256")
    args = parser.parse_args()
    root = args.source_root.resolve(strict=True)
    if args.action == "plan":
        value, _, _ = inspect(root, args.selection)
        with args.plan.open("xb") as stream:
            stream.write(encoded(value))
        result = {"status": value["stage"], "source_files": len(value["files"]), "selected_export_bytes": value["selected_export_bytes"],
            "maximum_prepared_snapshot_bytes": value["maximum_prepared_snapshot_bytes"], "plan_sha256": sha(args.plan)}
    elif args.action == "verify-plan":
        value, _, _ = verify_plan(root, args.selection, args.plan)
        result = {"status": "verified_prepared_sources_without_copy", "source_files": len(value["files"]), "plan_sha256": sha(args.plan)}
    elif args.action == "sync":
        if args.output is None or args.approved_plan_sha256 is None:
            parser.error("sync needs a new --output and exact --approved-plan-sha256")
        result = synchronize(root, args.selection, args.plan, args.output, args.approved_plan_sha256)
    else:
        selection = read(args.selection)
        owner, legacy, _ = legacy_owner(root, selection)
        owner.DESTINATION = args.output.absolute() if args.output else HERE
        result = verify_snapshot(owner)
    print(json.dumps(result, ensure_ascii=False))

