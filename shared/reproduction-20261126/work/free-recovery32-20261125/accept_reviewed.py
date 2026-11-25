import argparse
import fcntl
import hashlib
import importlib.util
import json
from pathlib import Path


FOLDER = Path(__file__).resolve().parent
ROOT = Path.cwd().resolve()
STOP = ROOT / "work/performance-stop-20261122.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_bytes())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-prepared-sha", required=True)
    args = parser.parse_args()
    prepared = read(FOLDER / "prepared.json")
    qualification = read(FOLDER / "qualification.json")
    if (sha(FOLDER / "prepared.json") != args.expected_prepared_sha
            or qualification["status"] != "passed"
            or qualification["prepared_sha256"] != args.expected_prepared_sha
            or sha(FOLDER / "prepare.py") != prepared["writer_sha256"]):
        raise ValueError("The explicitly reviewed preparation and qualification changed")
    spec = importlib.util.spec_from_file_location("reviewed_unknown32_source", FOLDER / "prepare.py")
    checker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checker)
    accepted = FOLDER / "accepted-unknown32.json"
    temporary = STOP.with_suffix(".accept32-writing")
    if accepted.exists() or temporary.exists():
        raise FileExistsError("Inspect the retained acceptance state instead of overwriting it")
    with STOP.with_suffix(".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        stop, _, _, _, _, _, registry, _, sources, _, _ = checker.inspect()
        proposal = FOLDER / "accepted-unknown32.proposed.json"
        future = FOLDER / "stop-after-parent-acceptance.proposed.json"
        evidence, updated = read(proposal), read(future)
        if (sha(proposal) != prepared["proposal_sha256"]
                or evidence["source_sha256"] != sources
                or registry != (FOLDER / "generation-registry-at-prepare32.json").read_bytes()
                or sha(future) != prepared["expected_accepted_stop_sha256"]
                or sha(STOP) != prepared["expected_stop_sha256"]
                or sha(FOLDER / "stop-before-accepting-32.json") != sha(STOP)):
            raise ValueError("The actual stopped attempt or proposed bytes changed")
        changed = {key for key in stop.keys() | updated.keys() if stop.get(key) != updated.get(key)}
        if (changed != {"historical_unknown_calls", "accepted_total_unknown_calls", "pending_unverified_calls",
                "unverified_requests", "unresolved_fee_stops", "accepted_unknown_evidence", "previous_pending_stop", "reason"}
                or updated["historical_unknown_calls"] != 32 or updated["accepted_total_unknown_calls"] != 32
                or updated["active"] is not True or updated["pending_unverified_calls"] != 0
                or updated["unresolved_fee_stops"] or updated["unverified_requests"]
                or any(evidence[key] is not None for key in
                    ("complete_actual_model_identity", "actual_generation_id", "actual_usage", "actual_amount"))):
            raise ValueError("Only this exact historical unknown may change; preserve the quota-only pause")
        with accepted.open("xb") as stream:
            stream.write(proposal.read_bytes())
        with temporary.open("xb") as stream:
            stream.write(future.read_bytes())
        temporary.replace(STOP)
    print(json.dumps({"accepted_unknown": 32, "pending": 0, "quota_pause_retained": True,
        "stop_sha256": sha(STOP), "unknown_amount": None, "unknown_usage": None,
        "new_model_calls": 0, "wait_started": False}))


if __name__ == "__main__":
    main()
