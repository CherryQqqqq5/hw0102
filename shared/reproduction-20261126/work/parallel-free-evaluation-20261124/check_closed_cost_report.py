import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
BASE = Path(__file__).resolve().parent
PROOF = BASE / "closed-cost-report-qualification-20261126"
sys.path.insert(0, str(ROOT))


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--record-red", action="store_true")
    parser.add_argument("--renderer-only", action="store_true")
    args = parser.parse_args()
    if args.renderer_only:
        qualify_renderer()
        return
    def no_external(event, args):
        if event == "subprocess.Popen":
            command = args[1]
            allowed = [sys.executable, "-B", str(BASE / "export_nvidia_history.py"), "closed-verify", "--out"]
            if len(command) == 6 and list(command[:5]) == allowed and Path(command[5]).resolve().is_relative_to(ROOT / "work"):
                return
            raise PermissionError("Only the exact zero-model portable verifier CLI may execute")
        if event in {"socket.connect", "os.system"}:
            raise PermissionError("This report qualification cannot call models,network or subprocesses")
    sys.addaudithook(no_external)
    reports = load("closed_report_consumer", BASE / "prepare_report_data.py")
    if not args.record_red:
        qualify_consumer(reports)
        return
    PROOF.mkdir(exist_ok=False)
    try:
        reports.nvidia_report_sources(BASE / "nvidia-v33-consumer-qualification/summary.json", ROOT, {},
            closed_supplement=BASE / "closed-cost-supplement-20261125")
    except TypeError as exc:
        if "closed_supplement" not in str(exc):
            raise
        value = {"status": "RED_EXPECTED", "actual_error": str(exc),
            "consumer_sha256": reports.digest(BASE / "prepare_report_data.py"),
            "new_model_calls": 0, "new_original_grader_calls": 0}
        (PROOF / "red-result.json").write_text(json.dumps(value, indent=2) + "\n")
        print(json.dumps(value))
    else:
        raise AssertionError("The old public API unexpectedly accepted the new typed supplement")


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def qualify_consumer(reports):
    snapshot = BASE / "nvidia-v33-consumer-qualification/summary.json"
    package = BASE / "closed-cost-supplement-20261125"
    plan = reports.read(ROOT / reports.read(snapshot)["plan_path"])
    tasks = {task["id"]: task for task in reports.read(ROOT / plan["manifest"])["selected"]}
    integrated = reports.nvidia_report_sources(snapshot, ROOT, tasks, closed_supplement=package)
    strict = {key: value for key, value in integrated.items() if key != "closed_cost_supplement"}
    assert sum(g["completed"] for g in strict["groups"].values()) == 7
    assert sum(g["passed"] for g in strict["groups"].values()) == 5
    assert sum(g["requests"] for g in strict["groups"].values()) == 135
    assert integrated["comparison"] == strict["comparison"] and integrated["repeat"] == strict["repeat"]
    closed = integrated["closed_cost_supplement"]
    assert closed["latest_step5_originals"]["scored"] == 9
    assert closed["latest_step5_originals"]["passed"] == 5
    assert closed["latest_step5_originals"]["strict_record_validated"] == 8
    assert closed["combined_retained_costs"]["physical_requests"] == 324
    assert closed["combined_retained_costs"]["complete_native_policy_proofs"] == 315
    fixture = BASE / "closed-cost-supplement-qualification-20261125/portable-closed-supplement"
    assert digest(fixture / "index.json") == digest(package / "index.json")
    blocked = []
    def no_original_reads(event, args):
        if event == "open" and isinstance(args[0], (str, bytes)):
            name = args[0].decode() if isinstance(args[0], bytes) else args[0]
            if Path(name).absolute().is_relative_to(ROOT / "work/vmshare"):
                blocked.append(name)
                raise PermissionError("Closed report integration must consume its portable proof")
    sys.addaudithook(no_original_reads)
    negatives = []
    def reject(label, operation):
        try:
            operation()
        except (ValueError, KeyError) as exc:
            negatives.append({"name": label, "rejected": True, "reason": str(exc)})
        else:
            raise AssertionError("Report accepted corrupted actual provenance: " + label)
    bad = copy.deepcopy(strict)
    bad["cross_service_retained_costs"]["closed_physical_requests"] = 319
    reject("wrong_prior_cost_view", lambda: reports.nvidia_closed_cost_sources(bad, ROOT, package))
    bad = copy.deepcopy(strict)
    bad["reported_monetary_cost_usd"] = 0
    reject("unknown_prior_money_filled_zero", lambda: reports.nvidia_closed_cost_sources(bad, ROOT, package))
    invalid = BASE / "nvidia-closed-2321-20261125/summary.json"
    reject("normal_consumer_still_rejects_invalid_snapshot", lambda: reports.nvidia_report_sources(invalid, ROOT, tasks))
    bad = copy.deepcopy(strict)
    bad["source"] = str(invalid.relative_to(ROOT))
    bad["source_sha256"] = digest(invalid)
    reject("latest_scheduler_snapshot_would_double_count_delta", lambda: reports.nvidia_closed_cost_sources(bad, ROOT, package))
    index_path = fixture / "index.json"
    original_index = index_path.read_bytes()
    original_files = {p: digest(p) for p in fixture.rglob("*") if p.is_file()}
    def bad_package(label, index_change=None, relative=None, transform=None):
        index = json.loads(original_index)
        saved = None
        if index_change:
            index_change(index)
        if relative:
            path = fixture / relative
            saved = path.read_bytes()
            write(path, transform(json.loads(saved)))
            member, = [row for row in index["files"] if row["path"] == relative]
            member.update(export_sha256=digest(path), export_bytes=path.stat().st_size, byte_identical=False)
        write(index_path, index)
        try:
            reject(label, lambda: reports.nvidia_closed_cost_sources(strict, ROOT, fixture))
        finally:
            if relative:
                path.write_bytes(saved)
            index_path.write_bytes(original_index)
    def changed(value, **fields):
        value.update(fields)
        return value
    bad_package("unknown33_amount_filled_zero", relative="accepted-unknown33.json", transform=lambda v: changed(v, actual_amount=0))
    bad_package("raw_original_false_promoted_true", relative="runs/main/result.json", transform=lambda v: changed(v, passed=True))
    bad_package("technical_qualification_promoted_grade", index_change=lambda v: v["qualifications"][0].update(is_task_position=True, original_score=True))
    bad_package("reused_native_identity", index_change=lambda v: v["qualifications"][1].update(generation_id=v["qualifications"][0]["generation_id"]))
    assert not blocked and all(digest(path) == expected for path, expected in original_files.items())
    assert reports.nvidia_closed_cost_sources(strict, ROOT, package) == integrated
    write(PROOF / "nvidia-fragment.json", integrated)
    value = {"status": "PASS_CONSUMER_FRAGMENT_NOT_FINAL_REPORT", "strict_original_scored": 7,
        "strict_original_passed": 5, "strict_matrix_requests": 135,
        "latest_step5": closed["latest_step5_originals"], "combined_costs": closed["combined_retained_costs"],
        "strict_pairing_unchanged": True, "negative_cases": negatives, "closed_integration_original_vmshare_reads": blocked,
        "source_sha256": {str(path.relative_to(ROOT)): digest(path) for path in (
            BASE / "prepare_report_data.py", ROOT / "work/render_hy4_final_reports.py", BASE / "export_nvidia_history.py", Path(__file__))},
        "fragment_sha256": digest(PROOF / "nvidia-fragment.json"),
        "new_model_calls": 0, "new_original_grader_calls": 0, "vm_commands": 0,
        "full_report_data_generated": False, "pdf_generated": False}
    write(PROOF / "consumer-result.json", value)
    print(json.dumps({key: value[key] for key in ("status", "strict_original_scored", "latest_step5", "negative_cases")}, ensure_ascii=False))


def qualify_renderer():
    sys.path.insert(0, str(ROOT / "work"))
    renderer = load("closed_cost_report_renderer", ROOT / "work/render_hy4_final_reports.py")
    data = json.loads((PROOF / "nvidia-fragment.json").read_bytes())
    renderer.verify_nvidia_closed_source(data)
    items = renderer.nvidia_validation_items(data)
    def texts(value):
        if hasattr(value, "getPlainText"):
            return [value.getPlainText()]
        if hasattr(value, "_cellvalues"):
            return texts(value._cellvalues)
        if isinstance(value, (list, tuple)):
            return [text for part in value for text in texts(part)]
        return [str(value)]
    text = "\n".join(texts(items))
    for expected in ("冻结已评分7/225", "最新Step5原分为5/9", "8条", "qualified计数为5", "其余218个计划位置", "324次请求", "315个完整身份", "64000表示请求上限被接受"):
        assert expected in text, expected
    assert "其余74题在各组共同采用v28" not in text
    assert "reasoning_effort参数" in text and "low" not in text
    assert "原生DSH" in text and "无原分" in text and "MiniMax" in text
    result = json.loads((PROOF / "consumer-result.json").read_bytes())
    assert digest(PROOF / "nvidia-fragment.json") == result["fragment_sha256"]
    assert all(digest(ROOT / path) == expected for path, expected in result["source_sha256"].items())
    result.update(status="PASS_NVIDIA_REPORT_FRAGMENT_NOT_FINAL_DELIVERY", renderer_flowables=len(items),
        renderer_actual_text_sha256=hashlib.sha256(text.encode()).hexdigest(),
        renderer_scope="Actual ReportLab paragraph/table objects;no PDF/layout/full-report qualification",
        ablation_plan_exists=(BASE / "final-reuse-ablation/plan.json").exists(),
        preservation_completed_review_exists=(ROOT / "work/pytest-5631-preservation-20261125/completed-review.json").exists())
    write(PROOF / "result.json", result)
    print(json.dumps({key: result[key] for key in ("status", "renderer_flowables", "pdf_generated", "ablation_plan_exists", "preservation_completed_review_exists")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
