import copy
import importlib.machinery
import importlib.util
import json
from pathlib import Path

from export_hy4_interruptions import costs
from scripts.export_performance_evidence import digest


def main():
    root, folder = Path.cwd(), Path(__file__).parent
    output = folder / "hy4-interruption-identity-qualification-20261126"
    output.mkdir(exist_ok=False)
    artifact = folder / "hy4-unscored-interruption-evidence-20261126"
    index = json.loads((artifact / "index.json").read_text())
    actual = []
    for run in index["runs"]:
        source, exported = root / run["source_relative"], artifact / run["path"]
        assert costs(source) == costs(exported) == run["actual_recomputed_costs"]
        for member in run["files"]:
            path = artifact / member["path"]
            original = source.with_suffix(".protocol.json") if path == exported.with_suffix(".protocol.json") else source / path.relative_to(exported)
            assert digest(path) == member["export_sha256"] and digest(original) == member["source_sha256"]
        actual.append({"source": run["source_relative"], "costs": costs(source), "unchanged_export_members": len(run["files"])})
    fixture_source = root / next(run["source_relative"] for run in index["runs"] if run["source_relative"].endswith("python-grep-C0-r1"))
    events = [json.loads(line) for line in next(fixture_source.rglob("model.jsonl")).read_text().splitlines()]
    first_bill = next(i for i, event in enumerate(events) if event["event"] == "billing_verified")
    first_response = next(i for i, event in enumerate(events) if event["event"] == "response")
    before_path = folder / "export-hy4-interruptions-before-identity-binding-20261126.py.txt"
    loader = importlib.machinery.SourceFileLoader("interruption_before_identity_binding", str(before_path))
    before = importlib.util.module_from_spec(importlib.util.spec_from_loader(loader.name, loader))
    loader.exec_module(before)
    negatives = []
    for name in ("wrong_receipt_identity", "nonzero_reported_credit", "receipt_before_response",
            "missing_individual_proof", "duplicate_proof", "no_native_usage", "backdated_proof", "advance_after_unknown"):
        altered = copy.deepcopy(events)
        if name == "wrong_receipt_identity":
            altered[first_bill]["fresh_model_message_ids"] = ["not-the-returned-native-identity"]
        elif name == "nonzero_reported_credit":
            altered[first_bill]["credit"] = 1
        elif name == "receipt_before_response":
            altered[first_bill], altered[first_response] = altered[first_response], altered[first_bill]
        elif name == "missing_individual_proof":
            altered.pop(first_bill)
        elif name == "duplicate_proof":
            altered.insert(first_bill + 1, copy.deepcopy(altered[first_bill]))
        elif name == "no_native_usage":
            for item in altered[first_response]["payload"]:
                item.get("providerData", {}).pop("rawUsage", None)
        elif name == "backdated_proof":
            altered[first_bill]["time"] = 0
        else:
            extra = copy.deepcopy(next(e for e in reversed(altered) if e["event"] == "request"))
            extra["request_id"] += 1
            altered.append(extra)
        directory = output / name
        directory.mkdir()
        (directory / "model.jsonl").write_text("".join(json.dumps(event, ensure_ascii=False) + "\n" for event in altered))
        if name == "wrong_receipt_identity":
            assert before.costs(directory)["own_verified_receipts"] == 2
        try:
            costs(directory)
        except (ValueError, RuntimeError) as error:
            negatives.append({"name": name, "rejected": True, "error_type": type(error).__name__})
        else:
            raise AssertionError("An invalid retrospective cost trace was accepted: " + name)
    result = {"new_model_calls": 0, "original_export_index_sha256": digest(artifact / "index.json"),
        "strict_reader_sha256": digest(folder / "export_hy4_interruptions.py"),
        "original_export_producer_sha256": digest(before_path), "actual_runs": actual,
        "negative_controls": negatives, "old_wrong_identity_acceptance_reproduced": True,
        "scope": "Reconsumes the unchanged five real exports and original traces. Eight explicitly mutated local traces are validation fixtures, not model calls, scores or provider receipts. Three historical missing receipts stay unknown."}
    (output / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"actual_runs": len(actual), "negative_controls": len(negatives), "all_passed": True,
        "new_model_calls": 0, "result_sha256": digest(output / "result.json")}))


if __name__ == "__main__":
    main()
