import argparse
import json
from pathlib import Path
import subprocess
import sys

from course_eval.codebuddy_free import verify_free_response
from course_eval.summarize import run_metrics
from scripts.export_performance_evidence import digest, scrub


def read(path):
    return json.loads(path.read_text())


def costs(directory):
    logs = list(directory.rglob("model.jsonl"))
    if len(logs) > 1:
        raise ValueError("An interrupted run has multiple model traces")
    events = [json.loads(line) for line in logs[0].read_text().splitlines()] if logs else []
    requested, returned, verified, seen = set(), set(), set(), {}
    pending, response_seen, fresh_ids, last_time = None, False, set(), None
    for event in events:
        kind, identity = event["event"], event.get("request_id")
        if kind == "request":
            if pending is not None or identity in requested or (last_time is not None and event["time"] < last_time):
                raise ValueError("An interrupted run advances before its previous individual receipt")
            requested.add(identity)
            pending, response_seen = (identity, event["native_session_id"]), False
            last_time = event["time"]
        elif kind == "response":
            if pending is None or identity != pending[0] or identity in returned or event["time"] < last_time:
                raise ValueError("An interrupted response has no unique actual request")
            verify_free_response(event["payload"])
            fresh_ids = set()
            for item in event["payload"]:
                provider = item.get("providerData", {})
                if "rawUsage" not in provider:
                    continue
                key = pending[1], provider["messageId"]
                if key in seen:
                    if seen[key] != provider["rawUsage"]:
                        raise ValueError("A cumulative interrupted usage record changed")
                else:
                    seen[key] = provider["rawUsage"]
                    fresh_ids.add(provider["messageId"])
            if len(fresh_ids) != 1:
                raise ValueError("An interrupted returned generation lacks exactly one fresh native identity")
            returned.add(identity)
            response_seen, last_time = True, event["time"]
        elif kind == "billing_verified":
            if (pending is None or identity != pending[0] or not response_seen
                    or identity not in returned or identity in verified or event["credit"] != 0
                    or event["fresh_usage_records"] != 1 or len(event["fresh_model_message_ids"]) != 1
                    or set(event["fresh_model_message_ids"]) != fresh_ids or event["time"] < last_time):
                raise ValueError("An interrupted known response lacks its own new zero-credit receipt")
            verified.add(identity)
            pending, last_time = None, event["time"]
    if returned != verified:
        raise ValueError("Returned usage and individual financial verification differ")
    usage = run_metrics(directory)
    return {"model_request_events": len(requested), "own_verified_receipts": len(verified),
        "unverified_request_ids": sorted(requested - verified),
        "known_returned_input_tokens": None if usage["usage_missing_input_responses"] else usage["input_tokens"],
        "known_returned_output_tokens": None if usage["usage_missing_output_responses"] else usage["output_tokens"]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    root, output = Path.cwd(), args.out.resolve()
    if not output.is_relative_to(root / "work") or output.is_symlink():
        raise ValueError("The interruption export must remain inside project work")
    summary = read(args.summary)
    rows = summary["mechanical_interruption_costs"]
    if len({row["run_dir"] for row in rows}) != len(rows):
        raise ValueError("An interrupted physical run is duplicated")
    records = []
    for row in rows:
        source = (root / row["run_dir"]).resolve(strict=True)
        if not source.is_relative_to(root / "work/vmshare") or source.is_relative_to(output) or output.is_relative_to(source):
            raise ValueError("An interruption source is outside the archived run scope")
        result = read(source / "result.json")
        logs = list(source.rglob("model.jsonl"))
        if (result["scoreable"] is not False or result["passed"] is not None
                or digest(source / "result.json") != row["result_sha256"]
                or (digest(logs[0]) if len(logs) == 1 else None) != row["trace_sha256"]
                or row["actual_unverified_amount"] is not None or row["actual_unverified_usage"] is not None):
            raise ValueError("An interrupted outcome, original trace or unknown amount changed")
        actual = costs(source)
        if any(row[key] != value for key, value in actual.items()):
            raise ValueError("Actual interrupted request/receipt/usage counts differ from the source summary")
        relative = Path("runs") / source.parent.name / source.name
        destination = output / relative
        if any(path.is_symlink() for path in (output, destination, *destination.parents)):
            raise ValueError("The interruption export traverses a symbolic link")
        if destination.exists():
            raise FileExistsError("Keep an interrupted or completed export distinct; do not overwrite its members")
        subprocess.run([sys.executable, "-m", "course_eval.export_revision", "--runs", str(source),
            "--out", str(destination)], check=True, capture_output=True, text=True)
        if costs(destination) != actual or read(destination / "result.json")["passed"] is not None:
            raise ValueError("Export changed an actual zero receipt, missing receipt or null outcome")
        members = [{"path": str(path.relative_to(output)), "source_sha256": digest(source / path.relative_to(destination)),
            "export_sha256": digest(path)} for path in destination.rglob("*") if path.is_file()]
        protocol = source.with_suffix(".protocol.json")
        if protocol.exists():
            exported = destination.with_suffix(".protocol.json")
            exported.write_text(scrub(protocol.read_text(), root))
            members.append({"path": str(exported.relative_to(output)), "source_sha256": digest(protocol),
                "export_sha256": digest(exported)})
        records.append({"source_relative": row["run_dir"], "path": str(relative), "original_cost_record": row,
            "actual_recomputed_costs": actual, "files": members})
    index = {"format": "source_verified_unscored_hy4_interruption_evidence_v1",
        "source_summary": str(args.summary.resolve().relative_to(root)), "source_summary_sha256": digest(args.summary),
        "producer_sha256": digest(Path(__file__)), "sanitizer_sha256": digest(root / "course_eval/export_revision.py"),
        "runs": records, "new_model_calls": 0, "new_grader_calls": 0,
        "scope": "Only ended source-recorded mechanical attempts. Original passed=null and missing actual amount/usage remain null. Known prefixes are individually verified own-zero receipts; these attempts are excluded from scored success rates. Other historical unknowns remain in their separate ledger."}
    output.mkdir(parents=True, exist_ok=True)
    (output / "index.json").write_text(scrub(json.dumps(index, ensure_ascii=False, indent=2) + "\n", root))
    print(json.dumps({"physical_unscored_runs": len(records), "request_events": sum(r["actual_recomputed_costs"]["model_request_events"] for r in records),
        "own_zero_receipts": sum(r["actual_recomputed_costs"]["own_verified_receipts"] for r in records),
        "missing_receipts_retained": sum(len(r["actual_recomputed_costs"]["unverified_request_ids"]) for r in records), "new_model_calls": 0}))


if __name__ == "__main__":
    main()
