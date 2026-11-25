import argparse
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
from types import ModuleType, SimpleNamespace


ROOT = Path.cwd().resolve()
FOLDER = Path(__file__).resolve().parent
BASE = ROOT / "work/parallel-free-evaluation-20261124"


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write(path, data):
    with path.open("x") as stream:
        stream.write(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def prepare():
    consumer = load(BASE / "prepare_report_data.py", "qualified_loader_case_consumer")
    summary_path = FOLDER / "consumer-qualification/joint-eight/summary.json"
    summary = consumer.read(summary_path)
    acceptance = consumer.incremental_sources(summary, ROOT, BASE)
    sources, facts = {}, {}
    for task, method in (("pydata__xarray-4695", consumer.loc_preservation_case_observations),
            ("scikit-learn__scikit-learn-25232", consumer.nan_contract_case_observations)):
        facts[task], sources[task] = method(ROOT, acceptance)
    nvidia_path = BASE / "closed-cost-report-qualification-20261126/nvidia-fragment.json"
    data = {"summary": str(summary_path.relative_to(ROOT)), "summary_sha256": consumer.digest(summary_path),
        "producer_sha256": consumer.digest(BASE / "prepare_report_data.py"),
        "tasks_path": summary["source_manifest_path"], "tasks_sha256": summary["source_manifest_sha256"],
        "supplementary": {}, "case_sources": sources, "case_observations": facts, "sources": {},
        "nvidia_auxiliary": consumer.read(nvidia_path), "groups": summary["groups"],
        "complete_required_experiments": False, "main_and_repeat_all75_qualified_pass": False,
        "qualification_scope": "Loader-only input assembled from actual source-bound partial summary/case consumers and the previously qualified NVIDIA fragment. Not full prepare_report_data output or final report data. No required final review is asserted."}
    write(FOLDER / "consumer-qualification/loader-preview-data.json", data)


def check():
    renderer = load(ROOT / "work/render_hy4_final_reports.py", "actual_public_case_loader")
    original_path = FOLDER / "consumer-qualification/renderer-before-loc-load-fix.py.txt"
    previous = ModuleType("actual_archived_loader_before_loc_fix")
    previous.__file__ = str(original_path)
    exec(compile(original_path.read_bytes(), str(original_path), "exec"), previous.__dict__)
    path = FOLDER / "consumer-qualification/loader-preview-data.json"
    original = renderer.read(path)
    args = SimpleNamespace(data=path, preview=True, out_dir=FOLDER / "loader-preview", final_review=None)
    try:
        previous.load(args)
    except ValueError as error:
        assert "multi-source public NaN case" in str(error)
        red = str(error)
    else:
        raise AssertionError("The actual archived loader did not reproduce its observed P1")
    data, tasks, indexed = renderer.load(args)
    assert data == original and len(tasks) == 75
    assert {arm: len(rows) for arm, rows in indexed.items()} == {"main": 64, "repeat": 66, "dsh": 67}
    negatives = {}

    def rejects(name, value, preview=True):
        fixture = FOLDER / "consumer-qualification" / ("loader-negative-" + name + ".json")
        write(fixture, value)
        try:
            renderer.load(SimpleNamespace(data=fixture, preview=preview, out_dir=args.out_dir, final_review=None))
        except ValueError as error:
            negatives[name] = str(error)
        else:
            raise AssertionError("The real loader accepted invalid input:" + name)
        finally:
            fixture.unlink()

    wrong_name = deepcopy(original)
    wrong_name["case_sources"]["unregistered_case"] = wrong_name["case_sources"].pop("pydata__xarray-4695")
    rejects("unregistered_multi_source_case", wrong_name)
    wrong_hash = deepcopy(original)
    evidence = wrong_hash["case_sources"]["pydata__xarray-4695"]["files_sha256"]
    evidence[next(iter(evidence))] = "0" * 64
    rejects("changed_loc_source_hash", wrong_hash)
    empty = deepcopy(original)
    empty["case_sources"]["pydata__xarray-4695"]["files_sha256"] = {}
    rejects("empty_loc_source_contract", empty)
    rejects("partial_source_cannot_generate_final_pdf", original, preview=False)
    write(FOLDER / "consumer-qualification/loader-result.json", {
        "status": "PASS_ACTUAL_RENDERER_LOAD_WITH_REAL_LOC_AND_NAN_SOURCES",
        "actual_archived_P1": red, "negative_cases": negatives,
        "real_task_union": 75, "source_case_counts": {key: len(value["files_sha256"]) for key, value in original["case_sources"].items()},
        "source_sha256": {str(path.relative_to(ROOT)): renderer.digest(path) for path in
            (Path(__file__), original_path, ROOT / "work/render_hy4_final_reports.py", args.data)},
        "scope": original["qualification_scope"], "new_model_calls": 0, "new_original_grader_calls": 0})
    print(json.dumps({"status": "PASS_ACTUAL_RENDERER_LOAD_WITH_REAL_LOC_AND_NAN_SOURCES", "negative_cases": len(negatives)}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("prepare", "check"))
    args = parser.parse_args()
    prepare() if args.action == "prepare" else check()
