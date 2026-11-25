import argparse
import json
from pathlib import Path

from jsonschema import Draft202012Validator
from pydantic import ValidationError

from course_eval.controller import ControlAction


def accepted(action):
    try:
        ControlAction.model_validate(action)
    except ValidationError:
        return False
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows = json.loads((args.evidence_root / "confirmation-hy4flash-free-v16-summary/trials.json").read_text())
    validator = Draft202012Validator(ControlAction.model_json_schema())
    Draft202012Validator.check_schema(validator.schema)
    counts = {"real_actions": 0, "valid_actions": 0, "invalid_actions": 0}
    conflicts = []
    for row in rows:
        directory = args.evidence_root / "confirmation-hy4flash-free-v16" / row["run_id"]
        source, = directory.rglob("model.jsonl")
        for line in source.read_text().splitlines():
            response = json.loads(line)
            if response["event"] != "response" or row["arm"] == "B0":
                continue
            for event in response["payload"]:
                action = event.get("structured_output") if event.get("type") == "result" else None
                if not isinstance(action, dict):
                    continue
                counts["real_actions"] += 1
                valid = accepted(action)
                counts["valid_actions" if valid else "invalid_actions"] += 1
                if validator.is_valid(action) != valid:
                    conflicts.append({"run_id": row["run_id"], "request_id": response["request_id"], "action": action})
    boundary_cases = 0
    for operation, field in ControlAction.required_fields.items():
        action = {"operation": operation, **({field: "valid"} if field else {})}
        assert accepted(action) and validator.is_valid(action)
        for name in ("command", "check_id", "candidate_id", "note", "unknown"):
            for value in (None, "", "value", 0, True, []):
                candidate = action | {name: value}
                assert validator.is_valid(candidate) == accepted(candidate), candidate
                boundary_cases += 1
        if field:
            assert not accepted({"operation": operation})
            assert not validator.is_valid({"operation": operation})
    for operation in ("unknown", None, 1):
        assert not validator.is_valid({"operation": operation}) and not accepted({"operation": operation})
    assert not validator.is_valid({"operation": "bash", "command": "x" * 65537})
    assert not accepted({"operation": "bash", "command": "x" * 65537})
    result = {**counts, "schema_local_conflicts": conflicts, "boundary_cases": boundary_cases, "new_model_requests": 0,
              "validation_scope": "Archived real actions; no model or benchmark execution"}
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    assert not conflicts, f"Sent schema and local validator disagree on {len(conflicts)} real actions"
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
