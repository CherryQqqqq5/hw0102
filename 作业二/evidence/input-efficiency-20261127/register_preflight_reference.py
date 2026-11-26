import ast
import json
import time

from run_study import FOLDER, ROOT, digest, hashes, read, save


archive = FOLDER / "preflight-reference-amendment-20261127"
if (archive / "amendment.json").exists():
    raise FileExistsError("The reference-mapping amendment is already registered")
old = read(archive / "study-plan-v3.json")
current = hashes()
changed = {name for name in old["source_hashes"] | current
    if old["source_hashes"].get(name) != current.get(name)}
name = str((FOLDER / "runtime/course_eval/preflight.py").relative_to(ROOT))
if changed != {name}:
    raise RuntimeError("Unexpected source changes beyond upstream-reference preparation")
before = ast.parse((archive / "preflight-v3.py").read_text())
after = ast.parse((FOLDER / "runtime/course_eval/preflight.py").read_text())
unchanged = lambda tree: [ast.dump(node) for node in tree.body
    if not isinstance(node, ast.FunctionDef) or node.name != "aider_preflight"]
if unchanged(before) != unchanged(after):
    raise RuntimeError("The patch changes behavior outside Aider reference-file mapping")
task = "cpp/binary-search-tree"
controls = read(FOLDER / "preflight" / task / "preflight.json")
if (controls["original_starter"]["passed"] is not False
        or controls["upstream_reference"]["passed"] is not True
        or not all(controls[key]["scoreable"] for key in ("original_starter", "upstream_reference"))):
    raise RuntimeError("The actual starter and declared upstream reference have not qualified")
if list((FOLDER / "trials" / task).rglob("model.jsonl")):
    raise RuntimeError("The affected task already dispatched a model request")
if read(ROOT / "work/performance-stop-20261122.json")["active"]:
    raise RuntimeError("An unresolved fee prevents continuation")
requests = 0
for path in (FOLDER / "trials").rglob("model.jsonl"):
    events = [json.loads(line) for line in path.read_text().splitlines()]
    sent = {row["request_id"] for row in events if row["event"] == "request"}
    verified = {row["request_id"] for row in events
        if row["event"] == "billing_verified" and row["credit"] == 0}
    if sent != verified or any(row["event"] in {"request_error", "billing_error"} for row in events):
        raise RuntimeError("An existing model position lacks its own complete zero-credit receipts")
    requests += len(sent)
original = ROOT / "work/datasets/polyglot-benchmark-7e0611e77b54e2dea774cdc0aa00cf9f7ed6144f/cpp/exercises/practice/binary-search-tree"
positive = FOLDER / "preflight" / task / "positive"
if (digest(original / ".meta/example.h") != digest(positive / "reference/binary_search_tree.h")
        or digest(original / "binary_search_tree.cpp") != digest(positive / "grader-input/binary_search_tree.cpp")):
    raise RuntimeError("The declared upstream header or untouched source stub changed")
record = {"stage": "registered_before_affected_task_first_generation", "registered_unix": time.time(),
    "reason": "The declared C++ upstream example is header-only; preserve unmatched original stubs while mapping every declared reference once",
    "source_changes": {name: {"before": old["source_hashes"][name], "after": current[name]}},
    "original_plan_sha256": digest(archive / "study-plan-v3.json"),
    "controls": controls, "existing_zero_credit_requests": requests,
    "completed_positions": len(list((FOLDER / "trials").rglob("*.audited.json"))),
    "affected_task_model_requests": 0, "new_model_calls_by_repair": 0,
    "model_prompt_task_grader_limits_fee_selection_repeat_rules_unchanged": True,
    "upstream_header_sha256": digest(original / ".meta/example.h"),
    "untouched_source_stub_sha256": digest(original / "binary_search_tree.cpp")}
save(archive / "amendment.json", record)
save(FOLDER / "study-plan.json", old | {"stage": "frozen_after_preflight_reference_mapping_repair",
    "source_hashes": current, "preflight_reference_amendment": record})
print(json.dumps(record))
