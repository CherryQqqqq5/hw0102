import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile


ROOT = Path.cwd().resolve()
HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("current_source_preparation_only", HERE / "sync_sources.py")
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)


def rejected(function):
    try:
        function()
    except (ValueError, FileNotFoundError) as error:
        return type(error).__name__ + ": " + str(error)
    raise AssertionError("A deliberately invalid code-snapshot input was accepted")


def main():
    plan = HERE / "SYNC_PLAN.json"
    selection = HERE / "SELECTION.json"
    source, _, _ = helper.verify_plan(ROOT, selection, plan)
    output = ROOT / "work/hw0102-publish/shared/reproduction-20261126"
    if output.exists():
        raise ValueError("This preparation-only qualification expects no copied new snapshot")
    checks = {}
    with tempfile.TemporaryDirectory(prefix="private-source-qualification-", dir=HERE) as temporary:
        fixture = Path(temporary)
        bad = copy.deepcopy(source)
        first = next(iter(bad["files"]))
        bad["files"][first]["source_sha256"] = "0" * 64
        wrong = fixture / "wrong-plan.json"
        wrong.write_bytes(helper.encoded(bad))
        checks["changed_prepared_source_expectation"] = rejected(lambda: helper.verify_plan(ROOT, selection, wrong))
        checks["budget_over32MiB"] = rejected(lambda: helper.budget(helper.LIMIT, 1))
        assert helper.budget(source["selected_export_bytes"], source["reserved_manifest_and_helpers_bytes"]) == source["maximum_prepared_snapshot_bytes"]
        (fixture / "real.py").write_text("value = 1\n")
        (fixture / "alias.py").symlink_to(fixture / "real.py")
        checks["source_symlink"] = rejected(lambda: helper.local(fixture, "alias.py"))
        checks["source_parent_escape"] = rejected(lambda: helper.local(fixture, "../outside.py"))
        package = fixture / "package"
        package.mkdir()
        (package / "entry.py").write_text("from .child import value\n")
        (package / "child.py").write_text("value = 1\n")
        closure = helper.static_sources(fixture, ["package/entry.py"])
        assert set(closure) == {"package/entry.py", "package/child.py"}
        empty = {"files": {}, "runtime_inventory": {}}
        forbidden = {"code_additions": [], "source_versions": [], "dynamic_load_allowlist": [],
            "configuration_additions": ["work/vmshare/private-run/model.jsonl"], "additional_runtimes": []}
        checks["raw_model_trace_never_read"] = rejected(lambda: helper.selected_sources(fixture, forbidden, empty))
    help_result = subprocess.run([sys.executable, "-B", str(HERE / "sync_sources.py"), "--help"], capture_output=True, text=True, check=True)
    assert "verify-plan" in help_result.stdout and "--approved-plan-sha256" in help_result.stdout
    assert not output.exists()
    dynamic = source["dynamic_load_allowlist"]
    assert all(target in source["files"] for row in dynamic for target in row["targets"])
    assert all(row["owner"] in source["files"] or row["owner"] == "launchers/harbor_entry.py" for row in dynamic)
    result = {"status": "PASS_PREPARATION_ONLY_NO_SOURCE_TREE_COPY", "plan_sha256": helper.sha(plan),
        "selection_sha256": helper.sha(selection), "source_files": len(source["files"]),
        "selected_export_bytes": source["selected_export_bytes"], "maximum_prepared_snapshot_bytes": source["maximum_prepared_snapshot_bytes"],
        "frozen_runtime_versions": len(source["runtimes"]), "historical_source_version_entries": len(source["source_versions"]),
        "explicit_dynamic_owners": len(dynamic), "negative_cases_rejected": checks,
        "relative_static_import_fixture": closure, "actual_cli_help_exit_code": help_result.returncode,
        "source_sha256": {str(path.relative_to(ROOT)): helper.sha(path) for path in (Path(__file__), HERE / "sync_sources.py", selection, HERE / "README.md")},
        "new_model_calls": 0, "new_original_grader_calls": 0, "VM_or_container_executions": 0,
        "publication_clone_modified": False, "full_tree_synchronized": False,
        "limitations": ["Current allowlisted source/export hashes were read and compiled; the entire new tree was not copied.",
            "Actual sync, new portable snapshot verify, three existing entry helps and final sensitive scan remain for parent-approved synchronization.",
            "No SDK payload tree, original model/session/STOP/account metadata or whole plan all_files source list was traversed."]}
    with (HERE / "qualification.json").open("xb") as stream:
        stream.write(helper.encoded(result))
    print(json.dumps({key: result[key] for key in ("status", "plan_sha256", "source_files", "selected_export_bytes", "maximum_prepared_snapshot_bytes")}))


if __name__ == "__main__":
    main()

