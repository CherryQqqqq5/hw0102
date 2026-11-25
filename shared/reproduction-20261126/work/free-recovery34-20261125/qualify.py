import ast
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys


ROOT = Path.cwd().resolve()
FOLDER = Path(__file__).resolve().parent


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    writer = load("actual_unknown34_writer", FOLDER / "prepare.py")
    actual = writer.inspect()
    prepared = writer.read(FOLDER / "prepared.json")
    raw_stop = writer.STOP.read_bytes()
    writer.require(prepared["writer_sha256"] == writer.sha(FOLDER / "prepare.py")
        and writer.read(FOLDER / "accepted-unknown34.proposed.json")["source_sha256"] == actual["sources"]
        and (FOLDER / "generation-registry-at-prepare34.json").read_bytes() == actual["registry_bytes"], "The exact prepared event or registry changed")
    negatives = {}
    def rejects(name, call):
        try:
            call()
        except (ValueError, KeyError, RuntimeError):
            negatives[name] = "rejected"
        else:
            raise AssertionError(name)
    for name, change in (("extra_pending", lambda v: v.update(pending_unverified_calls=2)),
            ("wrong_previous_count", lambda v: v.update(accepted_total_unknown_calls=34)),
            ("wrong_pending_request", lambda v: v["unresolved_fee_stops"][0].update(unverified_requests=[3])),
            ("fabricated_quota", lambda v: v.update(quota_pause={"resume_not_before": "2026-11-26T00:00:00+08:00"}))):
        value = deepcopy(actual["stop"])
        change(value)
        rejects(name, lambda value=value: writer.validate_stop(value))
    for name, change in (("returned_unknown_receipt", lambda v: v.append({"event": "response"})),
            ("wrong_model", lambda v: v[0]["payload"].update(model="another-model")),
            ("wrong_endpoint", lambda v: v[0].update(endpoint="https://example.invalid")),
            ("different_service_error", lambda v: v[1].update(http_status=429))):
        value = deepcopy(actual["unknown"])
        change(value)
        rejects(name, lambda value=value: writer.validate_unknown(value))
    changed = deepcopy(actual["first"])
    next(e for e in changed if e["event"] == "response")["payload"]["usage"]["cost"] = 1
    rejects("nonzero_response", lambda: writer.old.audit_nvidia_events(changed, ROOT / actual["plan"]["lanes"]["main"]["contract"], writer.MODEL, 64000))
    old_source = (writer.OLD_PLANS.parent / "ready_coordinator_light_probe.py").read_text()
    new_source = (FOLDER / "ready_coordinator.py").read_text()
    writer.require(old_source.replace('result["error"] != recovery["original_error"]', 'result.get("error") != recovery["original_error"]') == new_source,
        "The isolated coordinator changed more than the approved optional-error lookup")
    sys.path.insert(0, str(ROOT))
    coordinator = load("actual_optional_error_coordinator", FOLDER / "ready_coordinator.py")
    plans = {arm: writer.read(FOLDER / "hy4-plans" / (arm + "-plan.json")) for arm in ("main", "repeat")}
    main_plan = plans["main"]
    recovery = main_plan["mechanical_policy_recoveries"]["llm-inference-batching-scheduler"]
    selected = coordinator.policy_directory("llm-inference-batching-scheduler", "C0", ROOT / main_plan["queue"], main_plan)
    writer.require(selected == Path(recovery["replacement_run"]) and not selected.exists(), "The actual original null must select exactly one unused readmission")
    altered = deepcopy(main_plan)
    altered["mechanical_policy_recoveries"]["llm-inference-batching-scheduler"]["original_result_sha256"] = "0" * 64
    rejects("wrong_original_null_sha", lambda: coordinator.policy_directory("llm-inference-batching-scheduler", "C0", ROOT / main_plan["queue"], altered))
    private = FOLDER / "private-gates"
    private.mkdir()
    fixture = private / "semantic-false"
    fixture.mkdir()
    (fixture / "result.json").write_text(json.dumps({"scoreable": True, "passed": False}))
    altered = deepcopy(main_plan)
    altered["mechanical_policy_recoveries"]["llm-inference-batching-scheduler"].update(original_run=str(fixture), original_result_sha256=writer.sha(fixture / "result.json"))
    rejects("semantic_false_readmission", lambda: coordinator.policy_directory("llm-inference-batching-scheduler", "C0", ROOT / main_plan["queue"], altered))
    resume = load("actual_noquota34_resume", FOLDER / "resume_hy4.py")
    config = writer.read(FOLDER / "hy4-resume.pending-acceptance.json")
    gate_stop = private / "stop.json"
    future = (FOLDER / "stop-after-parent-acceptance.proposed.json").read_bytes()
    gate_stop.write_bytes(future)
    resume.STOP = gate_stop
    resume.exact_accepted_hold(config, json.loads(future))
    gate_stop.write_bytes(future + b"\n")
    rejects("new_stop_bytes", lambda: resume.exact_accepted_hold(config, json.loads(future)))
    tree = ast.parse((FOLDER / "resume_hy4.py").read_text())
    gate, = [node for node in ast.walk(tree) if isinstance(node, ast.If) and any(isinstance(n, ast.Constant) and isinstance(n.value, str)
        and n.value.startswith("Retain the two actual ReLU outcomes") for n in ast.walk(node))]
    gate_code = compile(ast.Module(body=[gate], type_ignores=[]), "actual_pre_core_gate", "exec")
    synthetic = {"plan_sha256": config["pre_core_revision"]["plan_sha256"], "stage": "complete", "required": 2, "completed": 2,
        "passed": 2, "qualified_passed": 2, "rows": [{"passed": True, "qualified_passed": True} for _ in range(2)]}
    exec(gate_code, {"scored": synthetic, "revision": config["pre_core_revision"]})
    for name, change in (("relu_raw_false", lambda v: v.update(passed=1)), ("relu_qualified_false", lambda v: v["rows"][0].update(qualified_passed=False)),
            ("relu_partial", lambda v: v.update(completed=1))):
        value = deepcopy(synthetic)
        change(value)
        rejects(name, lambda value=value: exec(gate_code, {"scored": value, "revision": config["pre_core_revision"]}))
    (fixture / "result.json").unlink()
    fixture.rmdir()
    gate_stop.unlink()
    private.rmdir()
    validation = {}
    for arm, plan in plans.items():
        command = [sys.executable, str(FOLDER / "ready_coordinator.py"), "--plan", str(FOLDER / "hy4-plans" / (arm + "-plan.json")),
            "--queue-dir", str(ROOT / plan["queue"]), "--validate-only"]
        completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=True)
        validation[arm] = json.loads(completed.stdout.strip().splitlines()[-1])
    writer.require(writer.STOP.read_bytes() == raw_stop and not (FOLDER / "accepted-unknown34.json").exists(), "Qualification changed actual STOP")
    output = {"status": "passed", "prepared_sha256": writer.sha(FOLDER / "prepared.json"), "writer_sha256": writer.sha(FOLDER / "prepare.py"),
        "qualifier_sha256": writer.sha(Path(__file__)), "source_sha256": actual["sources"], "negative_cases": negatives,
        "actual_minimax_complete_prefix": actual["proofs"], "hy4_interruption": actual["hy4_interruption"], "coordinator_validation": validation,
        "pending_config_sha256": writer.sha(FOLDER / "hy4-resume.pending-acceptance.json"), "same75_inputs_order_and_limits": True,
        "pre_core_gate_scope": "Actual source predicate with explicitly synthetic metadata positive/negative cases;not real ReLU scores or model behavior",
        "unknown_amount": None, "unknown_usage": None, "unknown_model_identity": None,
        "new_model_calls": 0, "new_original_grader_calls": 0, "VM_calls": 0, "signals": 0, "stop_modified": False,
        "accepted": False, "wait_started": False, "scope": "Real closed responses/own proofs/registry and existing coordinator validate-only;exact-null recovery and private malformed-input gates. No financial acceptance,model,original grader,VM or MiniMax retry."}
    writer.create("qualification.json", writer.encoded(output))
    print(json.dumps({"status": "passed", "prepared_sha256": output["prepared_sha256"], "qualification_sha256": writer.sha(FOLDER / "qualification.json"), "negative_cases": len(negatives), "coordinator_validation": validation}))


if __name__ == "__main__":
    main()
