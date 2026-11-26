import argparse
import ast
import hashlib
import json
from pathlib import Path

from run_study import FOLDER, ROOT, RUNTIME, digest, hashes, read, save
from course_eval.resource_pool import ResourceLease


ARCHIVE = FOLDER / "scoring-amendment-20261127"
DIRECTORY = FOLDER / "trials/django__django-14855/environment"
EXPECTED_PATCH = "47442bacef9306ee9c7fac6b219dee9db2b2f895adc99b7c5f0efee6c225bd64"


def model_evidence():
    path = DIRECTORY / "model.jsonl"
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    requests = {row["request_id"] for row in rows if row["event"] == "request"}
    verified = {row["request_id"] for row in rows if row["event"] == "billing_verified" and row["credit"] == 0}
    if (len(requests) != 31 or requests != verified
            or any(row["event"] in {"request_error", "billing_error"} for row in rows)):
        raise RuntimeError("The existing model calls differ from their closed zero-credit evidence")
    return {"sha256": digest(path), "actual_requests": len(requests), "verified_zero_credit_requests": len(verified)}


def register():
    if (ARCHIVE / "amendment.json").exists():
        raise FileExistsError("The scoring amendment is already registered")
    old = read(ARCHIVE / "study-plan-v1.json")
    current = hashes()
    changed = {name for name in old["source_hashes"] | current
        if old["source_hashes"].get(name) != current.get(name)}
    expected = {str((FOLDER / name).relative_to(ROOT)) for name in
        ("runtime/course_eval/benchmarks.py", "run_registered.py")}
    if changed != expected:
        raise RuntimeError("Unexpected source changes beyond scorer timeout and freeze resumption")
    previous = ast.parse((ARCHIVE / "benchmarks-v1.py").read_text())
    edits = 0
    for node in ast.walk(previous):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "run_instance":
            for keyword in node.keywords:
                if keyword.arg == "timeout" and isinstance(keyword.value, ast.Constant) and keyword.value.value == 600:
                    keyword.value.value = 1800
                    edits += 1
    if edits != 1 or ast.dump(previous) != ast.dump(ast.parse((RUNTIME / "course_eval/benchmarks.py").read_text())):
        raise RuntimeError("The benchmark runner contains a behavior change beyond the original grader timeout")
    if digest(DIRECTORY / "candidate.patch") != EXPECTED_PATCH:
        raise RuntimeError("The submitted candidate differs from the actual original scoring attempt")
    scripts = list((FOLDER / "preflight/django__django-14855").rglob("eval.sh"))
    scripts += list((DIRECTORY / "swe-official").rglob("eval.sh"))
    if len(scripts) != 3 or {digest(path) for path in scripts} != {
            "8dd32f1d6c28d0281d43ddd42e4398b42f1f3892a53ee42d08e6ab2c69e11e37"}:
        raise RuntimeError("The original test commands differ")
    import swebench.harness.run_evaluation as official

    record = {"stage": "registered_before_any_further_generation", "original_test_timeout_seconds": 600,
        "uniform_swe_test_timeout_seconds": 1800, "reason": "Actual official test timeout; installed official CLI default is 1800",
        "testset_and_candidate_unchanged": True, "model_and_agent_limits_unchanged": True,
        "source_changes": {name: {"before": old["source_hashes"][name], "after": current[name]} for name in sorted(changed)},
        "original_plan_sha256": digest(ARCHIVE / "study-plan-v1.json"),
        "original_result_sha256": digest(ARCHIVE / "result-grader600.json"),
        "official_runner_sha256": digest(Path(official.__file__)), "candidate_sha256": EXPECTED_PATCH,
        "original_eval_script_sha256": digest(scripts[0]), "model_before": model_evidence(),
        "regrading_rule": "One original 1800-second scoring attempt on the saved candidate; no model resampling; stop if unscoreable",
        "disk_maintenance": "The same live QEMU process, CPU, memory, Docker identity and disk path; virtual capacity expanded 16 to 48 GiB after actual import ENOSPC",
        "new_model_calls": 0}
    save(ARCHIVE / "amendment.json", record)
    save(FOLDER / "study-plan.json", old | {"stage": "frozen_after_scoring_amendment_before_next_generation",
        "source_hashes": current, "scoring_amendment": record})
    print(json.dumps(record), flush=True)


def regrade():
    from course_eval.benchmarks import grade_swe

    amendment = read(ARCHIVE / "amendment.json")
    if hashes() != read(FOLDER / "study-plan.json")["source_hashes"]:
        raise RuntimeError("The amended runtime changed")
    if model_evidence() != amendment["model_before"] or digest(DIRECTORY / "candidate.patch") != EXPECTED_PATCH:
        raise RuntimeError("The saved candidate or model evidence changed")
    if read(ROOT / "work/performance-stop-20261122.json")["active"]:
        raise RuntimeError("An unresolved fee prevents any continuation")
    destination = DIRECTORY / "grader-recovery-1800"
    destination.mkdir(exist_ok=False)
    row, = [row for row in read(ROOT / "work/datasets/swe-grader.json") if row["instance_id"] == "django__django-14855"]
    with ResourceLease(FOLDER / "resources", exclusive=True, label="saved-candidate-official-regrade-1800"):
        result = grade_swe(row, (DIRECTORY / "candidate.patch").read_text(), destination)
    if model_evidence() != amendment["model_before"]:
        raise RuntimeError("A model event appeared during score-only recovery")
    save(destination / "regrade-result.json", result | {"new_model_calls": 0,
        "candidate_sha256": EXPECTED_PATCH, "test_timeout_seconds": 1800})
    if not result["scoreable"]:
        raise RuntimeError("The single 1800-second original scoring attempt remains unscoreable")
    original = read(ARCHIVE / "result-grader600.json")
    combined = original | result | {"wall_seconds": original["wall_seconds"] + result["grader_seconds"],
        "grader_seconds_total": original["grader_seconds"] + result["grader_seconds"],
        "original_grading_attempts": [{"timeout_seconds": 600, "scoreable": False,
            "result": str((ARCHIVE / "result-grader600.json").relative_to(ROOT))},
            {"timeout_seconds": 1800, "scoreable": True,
            "result": str((destination / "regrade-result.json").relative_to(ROOT))}]}
    combined.pop("grader_error", None)
    save(DIRECTORY / "result.json", combined)
    print(json.dumps(combined), flush=True)


parser = argparse.ArgumentParser()
parser.add_argument("action", choices=("register", "regrade"))
args = parser.parse_args()
{"register": register, "regrade": regrade}[args.action]()
