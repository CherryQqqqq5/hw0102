import argparse
import hashlib
import json
from pathlib import Path

from course_eval.codebuddy_free import FreeProviderResponse


def load(directory):
    directory = Path(directory)
    index = json.loads((directory / "index.json").read_text())
    files = {item["path"]: item for item in index["files"]}
    for name, record in files.items():
        if hashlib.sha256((directory / name).read_bytes()).hexdigest() != record["export_sha256"]:
            raise ValueError("A published interruption record changed")
    ledger = json.loads((directory / "billing-ledger.json").read_text())
    review = json.loads((directory / "interruption-review.json").read_text())
    if (review["status"] != "interrupted_preserved" or ledger["status"] != "interrupted_cost_ledger"
            or ledger["source_interruption_review_sha256"] != files["interruption-review.json"]["source_sha256"]
            or ledger["source_model_log_sha256"] not in review["source_sha256"].values()
            or ledger["original_grade"] is not None or ledger["scoreable"] is not False
            or ledger["fee_hold_active"] is not True or review["fee_stop_still_active"] is not True):
        raise ValueError("The interrupted attempt or its unresolved fee changed")
    known, unknown = [], []
    for entry in ledger["entries"]:
        if entry["status"] == "own_zero_credit_receipt":
            models = [FreeProviderResponse.model_validate(row["providerData"])
                for row in entry["fresh_provider_records"]]
            if not models or {row.messageId for row in models} != set(
                    entry["actual_billing_verified_event"]["fresh_model_message_ids"]):
                raise ValueError("A known request lacks its own actual native zero-credit receipt")
            known.append(entry["request_id"])
        elif (entry["status"] == "unknown_no_response_or_own_receipt" and entry["credit"] is None
                and entry["actual_billing_verified_event"] is None and not entry["fresh_provider_records"]):
            unknown.append(entry["request_id"])
        else:
            raise ValueError("An interruption entry has an unsupported financial status")
    if (len(known) != ledger["own_zero_credit_receipts"] or unknown != ledger["new_pending_unknown_requests"]
            or len(known) + len(unknown) != ledger["physical_request_attempts"]
            or len(set(known + unknown)) != len(known) + len(unknown)
            or ledger["conditional_repeat_started"] is not False):
        raise ValueError("The actual known and unknown request counts changed")
    return {"known_zero": len(known), "unknown": unknown,
        "historical_unknown": ledger["historical_unknown_requests_preserved"], "fee_stop_active": True}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    print(json.dumps(load(args.directory) | {"new_model_calls": 0}))
