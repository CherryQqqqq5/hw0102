import argparse
import json
from pathlib import Path

from export_joined_evidence import read, verify, verify_run
from scripts.export_performance_evidence import digest, export_captured_artifacts, inspect_run, scrub
from scripts.summarize_performance_comparison import control_artifact_metrics


parser = argparse.ArgumentParser()
parser.add_argument("--plan", type=Path, default=Path("work/parallel-free-evaluation-20261124/final-reuse-ablation/plan.json"))
parser.add_argument("--out", type=Path, default=Path("work/parallel-free-evaluation-20261124/final-guidance-evidence-20261126"))
parser.add_argument("--verify-only", action="store_true")
args = parser.parse_args()
args.plan = args.plan.resolve()
root, output = Path.cwd().resolve(), args.out.resolve()
if not output.is_relative_to(root / "work") or any(p.is_symlink() for p in (args.out, *args.out.parents)):
    raise ValueError("Only the declared project work export is allowed")
if args.verify_only:
    print(json.dumps(verify(output), ensure_ascii=False))
    raise SystemExit(0)
if not output.is_dir() or (output / "index.json").exists():
    raise ValueError("First run the existing sanitizer into a new ablation export; preserve an existing index")
plan = read(args.plan)
if digest(args.plan) != "a61385dd661d8b9074e154896b74e37bf073176d5e2e25e0961fa750a0d00e2e":
    raise ValueError("Use the three actual prespecified guidance ablations")
for name, expected in plan["all_files_sha256"].items():
    if digest(root / name) != expected:
        raise ValueError("An actual frozen ablation source changed: " + name)
queue = root / plan["queue"]
state = read(queue / "state.json")
if (state["stage"] != "complete" or state["required"] != state["completed"] or state["completed"] != 3
        or state["plan_sha256"] != digest(args.plan)
        or [row["task"] for row in state["rows"]] != plan["task_ids"]):
    raise ValueError("All three original ablation scores must be complete and source bound")
records = []
for row in state["rows"]:
    source = root / row["run_dir"]
    if source != queue / (row["task"] + "-C0-reuse-guidance-off-r1"):
        raise ValueError("An ablation row changed its declared physical run")
    actual = inspect_run(source, "mini-swe")
    if (digest(source / "result.json") != row["original_score_sha256"]
            or any(actual[key] != row[key] for key in ("passed", "actual_requests", "input_tokens", "output_tokens", "wall_seconds"))):
        raise ValueError("The actual original score or individual usage differs from the completed state")
    destination = output / source.name
    protocol = source.with_suffix(".protocol.json")
    exported_protocol = destination.with_suffix(".protocol.json")
    exported_protocol.write_text(scrub(protocol.read_text(), root))
    task = read(source / "trial.json")["task"]
    capture = export_captured_artifacts(source, destination, root, task["candidate_scope"]["artifacts"])
    files = []
    for path in sorted(p for p in destination.rglob("*") if p.is_file()) + [exported_protocol]:
        original = protocol if path == exported_protocol else source / path.relative_to(destination)
        files.append({"path": str(path.relative_to(output)), "source_sha256": digest(original), "export_sha256": digest(path)})
    record = {"source_relative": str(source.relative_to(root)), "path": source.name, "task": row["task"],
        "framework": "mini-swe", "metrics": actual, "files": files, "artifact_capture": capture,
        "control": control_artifact_metrics(source, "mini-swe", "C0")}
    verify_run(output, record)
    records.append(record)
snapshots = {}
for name, source in {"plan": args.plan, "state": queue / "state.json", "tasks": root / plan["manifest"],
        "checks": root / plan["checks"], "artifact-capture-policy": root / plan["artifact_capture_policy"]}.items():
    path = output / (name + ".json")
    path.write_text(scrub(source.read_text(), root))
    snapshots[name] = {"path": path.name, "source_relative": str(source.relative_to(root)),
        "source_sha256": digest(source), "export_sha256": digest(path)}
index = {"format": "completed_guidance_ablation_filtered_evidence_v1", "stage": "complete_three_guidance_ablations",
    "runs": records, "snapshots": snapshots, "views": {"guidance_off": [r["source_relative"] for r in records]},
    "all_current_positions_exported": True, "expected_current_unique_runs": 3,
    "finalizer_sha256": digest(Path(__file__)), "new_model_calls": 0,
    "scope": "Three fixed guidance-off original scores, separate from the225 core and16 scoped revisions. Original v18 full-guidance references remain source-bound in the plan; later ReLU revisions are not substituted."}
(output / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n")
print(json.dumps(verify(output), ensure_ascii=False))
