from copy import deepcopy
import importlib.util
import json
from pathlib import Path


FOLDER = Path(__file__).resolve().parent
ROOT = Path.cwd().resolve()


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    writer = load("actual_unknown33_writer", FOLDER / "prepare.py")
    resume = load("actual_unknown33_resume", FOLDER / "resume_hy4.py")
    prepared = writer.read(FOLDER / "prepared.json")
    actual = writer.inspect()
    raw_stop = writer.STOP.read_bytes()
    writer.require(prepared["writer_sha256"] == writer.sha(FOLDER / "prepare.py")
        and prepared["expected_stop_sha256"] == writer.sha(writer.STOP)
        and writer.read(FOLDER / "accepted-unknown33.proposed.json")["source_sha256"] == actual["sources"]
        and (FOLDER / "generation-registry-at-prepare33.json").read_bytes() == actual["registry_bytes"], "Prepared actual sources/registry no longer match")
    negatives = {}
    def rejects(name, call):
        try:
            call()
        except (ValueError, KeyError):
            negatives[name] = "rejected"
        else:
            raise AssertionError("Expected rejection: " + name)
    run = Path(actual["stop"]["run_dir"])
    for name, change in (("extra_pending", lambda v: v.update(pending_unverified_calls=2)),
            ("future_accepted_count", lambda v: v.update(accepted_total_unknown_calls=33)),
            ("wrong_request", lambda v: v["unresolved_fee_stops"][0].update(unverified_requests=[9])),
            ("fabricated_quota", lambda v: v.update(quota_pause={"resume_not_before": "2026-11-26T00:00:00+08:00"})),
            ("released_original_stop", lambda v: v.update(active=False))):
        value = deepcopy(actual["stop"])
        change(value)
        rejects(name, lambda value=value: writer.validate_stop(value, run))
    for name, change in (("new_complete_response", lambda v: v.append({"event": "response"})),
            ("wrong_model", lambda v: v[0]["payload"].update(model="another-model")),
            ("wrong_endpoint", lambda v: v[0].update(endpoint="https://example.invalid")),
            ("verified_unknown", lambda v: v[-1].update(response_identity_and_usage_verified=True))):
        value = deepcopy(actual["unknown"])
        change(value)
        rejects(name, lambda value=value: writer.validate_unknown(value))
    altered = deepcopy(actual["first"])
    next(e for e in altered if e["event"] == "response")["payload"]["usage"]["cost"] = 1
    contract = ROOT / writer.read(writer.PLAN)["lanes"]["main"]["contract"]
    rejects("nonzero_response", lambda: writer.audit_nvidia_events(altered, contract, writer.MODEL, 64000))
    private = FOLDER / "private-noquota-gate"
    private.mkdir()
    fixture_stop = private / "stop.json"
    future = (FOLDER / "stop-after-parent-acceptance.proposed.json").read_bytes()
    fixture_stop.write_bytes(future)
    config = writer.read(FOLDER / "hy4-resume.pending-acceptance.json")
    resume.STOP = fixture_stop
    resume.exact_accepted_hold(config, json.loads(future))
    fixture_stop.write_bytes(future + b"\n")
    rejects("new_stop_bytes", lambda: resume.exact_accepted_hold(config, json.loads(future)))
    fixture_stop.write_bytes(future)
    changed = json.loads(future)
    changed["pending_unverified_calls"] = 1
    rejects("pending_after_acceptance", lambda: resume.exact_accepted_hold(config, changed))
    changed = json.loads(future)
    changed["quota_pause"] = {"resume_not_before": "2026-11-26T00:00:00+08:00"}
    rejects("quota_after_acceptance", lambda: resume.exact_accepted_hold(config, changed))
    fixture_stop.unlink()
    private.rmdir()
    writer.require(writer.STOP.read_bytes() == raw_stop and not (FOLDER / "accepted-unknown33.json").exists()
        and not (FOLDER / "hy4-resume.json").exists(), "Qualification changed real financial or execution state")
    result = {"status": "passed", "prepared_sha256": writer.sha(FOLDER / "prepared.json"), "writer_sha256": writer.sha(FOLDER / "prepare.py"),
        "qualifier_sha256": writer.sha(Path(__file__)), "resume_source_sha256": writer.sha(FOLDER / "resume_hy4.py"), "source_sha256": actual["sources"],
        "negative_cases": negatives, "actual_closed_positions": actual["positions"], "new_complete_step5_proofs": 20,
        "retained_selected_step5_proofs": 115, "retained_actual_minimax_qualifications": actual["minimax"],
        "registry_claims_preserved": len(json.loads(actual["registry_bytes"])["generations"]),
        "unknown_model_identity": None, "unknown_generation_id": None, "unknown_usage": None, "unknown_amount": None,
        "official_status_followup_http": 410, "real_stop_bytes_unchanged": True, "new_model_calls": 0, "new_original_grader_calls": 0,
        "VM_calls": 0, "process_signals": 0, "wait_started": False, "financial_acceptance_executed": False,
        "scope": "Actual closed source/protocol/reward and individual policy proofs plus exact registry claims. In-memory malformed cases and private real-file STOP drift only. No model/grader/VM run or end-to-end recovery success claimed; original1134 source admission reused without bulk rehash."}
    writer.create("qualification.json", writer.encoded(result))
    print(json.dumps({"status": "passed", "prepared_sha256": result["prepared_sha256"], "qualification_sha256": writer.sha(FOLDER / "qualification.json"),
        "negative_cases": len(negatives), "new_step5_proofs": 20, "minimax_qualifications": 2, "stop_unchanged": True}))


if __name__ == "__main__":
    main()
