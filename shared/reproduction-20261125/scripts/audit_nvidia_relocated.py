import argparse
import hashlib
import json
import sys
import types
from pathlib import Path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit_bundle(bundle, origin, runtime, index, trace_name, contract_name, policy_name, model):
    bundle, origin = bundle.resolve(), origin.resolve()
    if bundle == origin:
        raise ValueError("The portable audit must use a distinct copied artifact root")
    def member(name):
        path = (bundle / name).resolve()
        if not path.is_relative_to(bundle):
            raise ValueError("An evidence member escapes the downloaded artifact")
        return path

    inventory = json.loads(member(index).read_text())
    for name, expected in inventory["files_sha256"].items():
        indexed = member(name)
        if digest(indexed) != expected:
            raise ValueError("An exact original artifact member is missing or changed: " + name)
    runtime = (bundle / runtime).resolve()
    if not runtime.is_relative_to(bundle):
        raise ValueError("The audited runtime must be inside the downloaded artifact")
    sys.path.insert(0, str(runtime))
    from course_eval import nvidia_evidence, nvidia_free, nvidia_http_recovery

    for module in (nvidia_evidence, nvidia_free, nvidia_http_recovery):
        module_path = Path(module.__file__).resolve()
        relative = str(module_path.relative_to(bundle))
        if (not module_path.is_relative_to(runtime) or relative not in inventory["files_sha256"]
                or digest(module_path) != inventory["files_sha256"][relative]):
            raise ValueError("A financial validator came from an unbound or ambient installation")
    mapped = []
    def relocated_path(*parts):
        selected = Path(*parts)
        if not selected.is_absolute():
            selected = bundle / selected
        if selected.is_relative_to(bundle):
            destination = selected
        elif selected.is_relative_to(origin):
            destination = bundle / selected.relative_to(origin)
            mapped.append(str(destination.relative_to(bundle)))
        else:
            raise ValueError("An original evidence pointer escapes the declared artifact origin")
        destination = member(destination)
        if destination.is_file() and str(destination.relative_to(bundle)) not in inventory["files_sha256"]:
            raise ValueError("An original evidence pointer targets an unindexed file")
        return destination

    original = nvidia_http_recovery.validate_accepted_errors
    relocated = types.FunctionType(original.__code__, original.__globals__ | {"Path": relocated_path},
        original.__name__, original.__defaults__, original.__closure__)
    original_audit = nvidia_evidence.audit_recoverable_events
    auditor = types.FunctionType(original_audit.__code__,
        original_audit.__globals__ | {"validate_accepted_errors": relocated}, original_audit.__name__,
        original_audit.__defaults__, original_audit.__closure__)
    trace, contract, policy = (member(name) for name in (trace_name, contract_name, policy_name))
    required = [trace, contract, policy]
    ledger = trace.parent / nvidia_http_recovery.LEDGER
    if ledger.exists():
        required.append(member(ledger))
    if any(str(path.relative_to(bundle)) not in inventory["files_sha256"] for path in required):
        raise ValueError("The model trace, contract, recovery policy or unknown ledger is not indexed")
    events = [json.loads(line) for line in trace.read_text().splitlines()]
    financial = auditor(events, trace, contract, model, 64000, policy)
    return financial | {"manifest_files_checked": len(inventory["files_sha256"]),
        "portable_path_relocation_only": True, "original_validator_function_code_unchanged": True,
        "relocated_original_pointers": len(mapped), "new_model_calls": 0, "new_original_grader_calls": 0}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle-root", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--runtime-root", required=True)
    parser.add_argument("--index", default="index.json")
    parser.add_argument("--trace", required=True)
    parser.add_argument("--contract", required=True)
    parser.add_argument("--policy", required=True)
    parser.add_argument("--model", required=True)
    args = parser.parse_args()
    print(json.dumps(audit_bundle(args.bundle_root, args.source_root, args.runtime_root, args.index,
        args.trace, args.contract, args.policy, args.model), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
