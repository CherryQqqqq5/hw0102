import argparse
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BASE = Path(__file__).resolve().parent
EXPERIMENT = ROOT / "work/nvidia75-transport-v28-20261125"
V28_SHA = "86ffe1672729bdf1a68aacc0884a471cd9777162b3a048881a41335823884a92"
V27_SHA = "13166798b21d7069d9194363cd4d1a3b2ec8d9c9c5f129ca44ebb4fa620e970f"
V29_SHA = "d2d8e1f1daf9ec0dc25f824a6a4e7168696eb3b92f37f433048690a461a6483e"
V30_SHA = "c0fe4961f310f979bec7da1101e75f0b86db240cb5b40364ccd76f4e2b528f18"
V31_SHA = "0995b63b9b2d06cef8a4348872a7757941c13c8fc1419a2da5b5c133e0dd4da3"
V32_SHA = "f5971565bd5b18374b065f0b2aeb7659727310beef85a0e375b9fd18c9f7dae2"
V33_SHA = "18cef63f6033106e9f1ea8c019a0d9ad2ac178127cdbcc4c0cafa29419686d9e"
BINDING_COUNTS = {V28_SHA: 427, V29_SHA: 541, V30_SHA: 729, V31_SHA: 969, V32_SHA: 1100, V33_SHA: 1134}


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def load(name, path, expected):
    if digest(path) != expected:
        raise ValueError("The previously verified offline dependency changed: " + str(path))
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


exporter_path = ROOT / "work/nvidia75-v27-20261125/export.py"
legacy = load("verified_v27_exporter", exporter_path,
    "5e9c72e888281b9810adfceb51921c85800210f84e5dd91002ad59f795c81997")
consumer_path = BASE / "analyze_nvidia_v28.py"
consumer = load("verified_v28_consumer", consumer_path,
    "2d57f7137af10c990c563d02f585f886df53516466d0857779f15b0b2b8e95e6")
read, contained, write = legacy.read, legacy.contained, legacy.write


def positions(plan, parent, tasks, plan_sha=V28_SHA, plan_member="plan-v28.json"):
    if (plan_sha not in BINDING_COUNTS or len(plan["all_files_sha256"]) != BINDING_COUNTS[plan_sha] or len(parent["all_files_sha256"]) != 218
            or len(tasks) != 75 or plan["limits"] != parent["limits"]
            or Counter(task["benchmark"] for task in tasks.values()) != {"aider": 25, "swe": 25, "terminal": 25}):
        raise ValueError("The frozen427/218 sources, original75 union or budgets changed")
    expected_lanes = {"main": ("mini-swe", "C0", 1), "dsh": ("dsh", "B0", 1), "repeat": ("mini-swe", "C0", 2)}
    if set(plan["lanes"]) != set(expected_lanes) or set(parent["lanes"]) != set(expected_lanes):
        raise ValueError("The three comparison lanes changed")
    result = []
    for name, lane in plan["lanes"].items():
        original = parent["lanes"][name]
        remaining = [task for task in original["tasks"] if task != "extract-elf"]
        if plan_sha in {V29_SHA, V30_SHA, V31_SHA, V32_SHA, V33_SHA}:
            remaining = remaining[1:] + remaining[:1]
        if plan_sha in {V32_SHA, V33_SHA} or plan_sha == V31_SHA and name != "dsh":
            remaining = [task for task in remaining if task != "model-extraction-relu-logits"]
        if plan_sha == V33_SHA:
            remaining = [task for task in remaining if not (name == "main" and task == "pydata__xarray-4687")]
            order = {task: index for index, task in enumerate(tasks)}
            remaining.sort(key=lambda task: (2 if task == "video-processing" else
                int(tasks[task]["benchmark"] == "swe" or task in {"query-optimize", "tune-mjcf"}), order[task]))
        if ((lane["framework"], lane["configuration"], lane["repetition"]) != expected_lanes[name]
                or lane["backend"] != "nvidia-free" or lane["model"] != "stepfun-ai/step-5-preview"
                or len(original["tasks"]) != 75 or set(original["tasks"]) != set(tasks)
                or lane["tasks"] != remaining
                or {key: value for key, value in lane.items() if key != "tasks"} != {
                    key: value for key, value in original.items() if key != "tasks"}):
            raise ValueError("An arm changed task order, model, framework or repetition")
        for task in original["tasks"]:
            if task == "extract-elf":
                source = plan["inherited_completed_positions"][name]["run_dir"]
                source_plan, source_sha, stratum = "plan-v27.json", V27_SHA, "v27_inherited_elf"
            elif plan_sha in {V31_SHA, V32_SHA, V33_SHA} and name != "dsh" and task == "model-extraction-relu-logits":
                source = plan["additional_inherited_v30_relu_positions"][name]["run_dir"]
                source_plan, source_sha, stratum = "plan-v30.json", V30_SHA, "v30_inherited_scored_relu"
            elif plan_sha in {V32_SHA, V33_SHA} and name == "dsh" and task == "model-extraction-relu-logits":
                source = plan["additional_inherited_v31_dsh_relu_position"]["run_dir"]
                source_plan, source_sha, stratum = "plan-v31.json", V31_SHA, "v31_inherited_scored_dsh_relu"
            elif plan_sha == V33_SHA and name == "main" and task == "pydata__xarray-4687":
                source = plan["additional_inherited_v32_main_xarray_position"]["run_dir"]
                source_plan, source_sha, stratum = "plan-v32.json", V32_SHA, "v32_inherited_scored_main_xarray"
            else:
                suffix = task.replace("/", "-") + "-" + lane["configuration"] + "-r" + str(lane["repetition"])
                source = str(Path(plan["queue"]) / name / suffix)
                source_plan, source_sha, stratum = plan_member, plan_sha, (
                    "v31_runtime_v33_light_first_remaining218" if plan_sha == V33_SHA else
                    "v31_runtime_v32_parallel_remaining219" if plan_sha == V32_SHA else
                    "v31_sdk_idle_alignment_remaining220" if plan_sha == V31_SHA else
                    "v30_common_guidance_remaining74" if plan_sha == V30_SHA else "v28_remaining74")
            result.append({"lane": name, "task": task, "source_relative": source,
                "actual_source_plan": source_plan, "actual_source_plan_sha256": source_sha, "transport_stratum": stratum})
    if len(result) != 225 or len({row["source_relative"] for row in result}) != 225:
        raise ValueError("The physical225 source positions are not unique")
    return result


def verify_original_reward(directory, result):
    if result.get("harbor_result") and result["scoreable"] is True:
        native = contained(directory, result["harbor_result"])
        reward_path = contained(directory, str(native.parent.relative_to(directory) / "verifier/reward.txt"))
        reward = Decimal(reward_path.read_text().strip())
        actual = read(native)
        reported = actual["verifier_result"]["rewards"]["reward"]
        if reward not in (Decimal(0), Decimal(1)) or reward != Decimal(str(reported)) or (reward == 1) is not result["passed"]:
            raise ValueError("The raw original reward file contradicts the Harbor result or saved original score")


def verify_member_source(member):
    if member["byte_identical"] is True and (member["source_sha256"] != member["export_sha256"]
            or member["source_bytes"] != member["export_bytes"]):
        raise ValueError("A declared byte-identical copy differs from its bound original bytes")


def verify_run_source_members(hashes, members):
    for source, expected in hashes.items():
        matches = [member for member in members.values() if member["source_relative"] == source]
        if len(matches) != 1 or matches[0]["source_sha256"] != expected:
            raise ValueError("An exported run member lost its bound original source checksum")


def inspect(directory, plan, plan_sha, lane, task, contract):
    trial, protocol = read(directory / "trial.json"), read(directory.with_suffix(".protocol.json"))
    legacy.consumer.validate_protocol(plan, plan_sha, lane, task, trial, protocol)
    metrics = legacy.inspect_nvidia_run(directory, lane["framework"], contract)
    if metrics["task"] != task["id"] or not 0 < metrics["actual_requests"] <= plan["limits"]["model_calls"] or metrics["model_request_retries"]:
        raise ValueError("The actual scored position changed task, call budget or retry policy")
    result = read(directory / "result.json")
    verify_original_reward(directory, result)
    grade_seconds = legacy.consumer.original_grade(task, directory, result, legacy.LocalSnapshot(directory))
    trace, = directory.rglob("model.jsonl")
    claims, proposals = [], Counter()
    for line in trace.open():
        event = json.loads(line)
        if event["event"] == "billing_verified":
            claims.append({"generation_id": event["generation_id"], "request_id": event["request_id"],
                "model": event["provider_model"], "trace_relative_to_run": str(trace.relative_to(directory))})
        elif event["event"] == "response":
            for choice in event["payload"].get("choices", []):
                for call in (choice.get("message") or {}).get("tool_calls") or []:
                    proposals[(call.get("function") or {}).get("name", "<missing_function_name>")] += 1
    identities = [claim["generation_id"] for claim in claims]
    if len(identities) != len(set(identities)) or len(identities) != metrics["actual_requests"]:
        raise ValueError("A scored position lacks unique per-request native proof identities")
    metrics.pop("final_verification_sha256", None)
    return {"metrics": metrics, "grader_seconds": grade_seconds, "generation_claims": claims,
        "native_proposed_function_calls_by_name": dict(proposals)}


def verify(output, require_complete=False):
    contained(output, ".")
    index = read(contained(output, "index.json"))
    if (index["format"] != "nvidia75_v28_stratified_sanitized_evidence_v1"
            or index["stage"] not in {"partial_internal_evidence", "complete_original225_evidence"}):
        raise ValueError("This is not a completed v28 export snapshot")
    members = {member["path"]: member for member in index["files"]}
    if len(members) != len(index["files"]):
        raise ValueError("The file inventory repeats a physical member")
    for name, member in members.items():
        verify_member_source(member)
        path = contained(output, name)
        if digest(path) != member["export_sha256"] or path.stat().st_size != member["export_bytes"]:
            raise ValueError("An exported member changed: " + name)
        legacy.private_scan(path)
    if {str(path.relative_to(output)) for path in output.rglob("*") if path.is_file()} != set(members) | {"index.json"}:
        raise ValueError("The export has missing or unregistered files")
    legacy.private_scan(output / "index.json")
    plan_sha = index["source_plan_sha256"]
    if plan_sha not in BINDING_COUNTS:
        raise ValueError("An unrelated orchestration cannot replace the admitted comparison")
    plan_member = index.get("source_plan_member", "plan-v28.json")
    if plan_member != {V28_SHA: "plan-v28.json", V29_SHA: "plan-v29.json", V30_SHA: "plan-v30.json", V31_SHA: "plan-v31.json", V32_SHA: "plan-v32.json", V33_SHA: "plan-v33.json"}[plan_sha]:
        raise ValueError("The actual source plan name does not match its admitted version")
    plans = {name: read(output / name) for name in ("plan-v27.json", plan_member)}
    if plan_sha in {V31_SHA, V32_SHA, V33_SHA}:
        plans["plan-v30.json"] = read(contained(output, "plan-v30.json"))
        if members["plan-v30.json"]["source_sha256"] != V30_SHA:
            raise ValueError("The inherited scored ReLU positions lost their actual v30 plan")
        inherited_plan = plans["plan-v30.json"]
        if members["capture-policy-v30.json"]["source_sha256"] != inherited_plan["all_files_sha256"][inherited_plan["artifact_capture_policy"]]:
            raise ValueError("The inherited ReLU capture scope lost its actual v30 binding")
    if plan_sha in {V32_SHA, V33_SHA}:
        plans["plan-v31.json"] = read(contained(output, "plan-v31.json"))
        if members["plan-v31.json"]["source_sha256"] != V31_SHA:
            raise ValueError("The inherited DSH ReLU lost its actual v31 plan")
        inherited_plan = plans["plan-v31.json"]
        if members["capture-policy-v31.json"]["source_sha256"] != inherited_plan["all_files_sha256"][inherited_plan["artifact_capture_policy"]]:
            raise ValueError("The inherited DSH capture scope lost its actual v31 binding")
    if plan_sha == V33_SHA:
        plans["plan-v32.json"] = read(contained(output, "plan-v32.json"))
        if members["plan-v32.json"]["source_sha256"] != V32_SHA:
            raise ValueError("The inherited main xarray lost its actual v32 plan")
        inherited_plan = plans["plan-v32.json"]
        if members["capture-policy-v32.json"]["source_sha256"] != inherited_plan["all_files_sha256"][inherited_plan["artifact_capture_policy"]]:
            raise ValueError("The inherited xarray capture scope lost its actual v32 binding")
    plan, parent = plans[plan_member], plans["plan-v27.json"]
    if members[plan_member]["source_sha256"] != plan_sha or members["plan-v27.json"]["source_sha256"] != V27_SHA:
        raise ValueError("The export lacks the actual admitted v28/v27 plans")
    tasks = {task["id"]: task for task in read(output / "tasks.json")["selected"]}
    expected = positions(plan, parent, tasks, plan_sha, plan_member)
    binding = read(output / "source-validation.json")
    if binding["plan_sha256"] != plan_sha or binding["matched_all_files_sha256"] != plan["all_files_sha256"] or binding["matched_count"] != BINDING_COUNTS[plan_sha]:
        raise ValueError("The427-source export-time validation is missing")
    for target, key in (("tasks.json", "manifest"), ("checks.json", "checks"),
            ("capture-policy-v28.json", "artifact_capture_policy")):
        if members[target]["source_sha256"] != plan["all_files_sha256"][plan[key]]:
            raise ValueError("An actual v28 task/check/capture binding changed")
    if (members["tasks.json"]["source_sha256"] != parent["all_files_sha256"][parent["manifest"]]
            or members["checks.json"]["source_sha256"] != parent["all_files_sha256"][parent["checks"]]
            or members["capture-policy-v27.json"]["source_sha256"] != parent["all_files_sha256"][parent["artifact_capture_policy"]]):
        raise ValueError("The inherited v27 input scope changed")
    snapshot = read(output / "analysis-summary.json")
    rows = [json.loads(line) for line in (output / "analysis-trials.jsonl").read_text().splitlines()]
    if (snapshot["schema"] != "nvidia75_v28_stratified_offline_summary_v1" or snapshot["plan_sha256"] != plan_sha
            or snapshot["stage"] not in {"partial", "complete_original225"}
            or snapshot["unexpected_position_directories"] or snapshot["bound_source_count"] != BINDING_COUNTS[plan_sha]
            or snapshot["trials_sha256"] != members["analysis-trials.jsonl"]["source_sha256"]
            or binding["analysis_rows_sha256"] != members["analysis-trials.jsonl"]["source_sha256"]
            or binding["analysis_summary_sha256"] != members["analysis-summary.json"]["source_sha256"]
            or snapshot["identity_audit"]["errors"] or snapshot["historical_ledger_errors"]):
        raise ValueError("The exact verified analysis snapshot or its identity audit changed")
    for row, wanted in zip(rows, expected, strict=True):
        if any(row[key] != wanted[key] for key in ("lane", "task", "transport_stratum", "actual_source_plan_sha256")) or row["run_dir"] != wanted["source_relative"]:
            raise ValueError("A225-row position lost its actual source plan or transport stratum")
    closed = [row for row in rows if row.get("scoreable") is True]
    if any(not row["record_validated"] or row["validation_errors"] for row in closed):
        raise ValueError("An original-scored source failed its strict consumer")
    wanted_by_position = {(row["lane"], row["task"]): row for row in expected}
    if [(record["lane"], record["task"]) for record in index["runs"]] != [(row["lane"], row["task"]) for row in closed[:len(index["runs"])]]:
        raise ValueError("The scored prefix omitted, repeated or selected a task by outcome")
    seed = read(output / "generation-seed.json")
    registry = read(output / "prior-generation-registry-snapshot.json")
    if (members["generation-seed.json"]["source_sha256"] != plan["all_files_sha256"][plan["generation_seed"]]
            or registry["seed_sha256"] != members["generation-seed.json"]["source_sha256"]
            or members["prior-generation-registry-snapshot.json"]["source_sha256"] != plan["all_files_sha256"][
                str(Path(plan["admission"]).parent / "prior-generation-registry-snapshot.json")]):
        raise ValueError("The frozen historical identity seed or registry changed")
    contract = output / "nvidia-free-contract.json"
    if not members[contract.name]["byte_identical"] or digest(contract) != members[contract.name]["source_sha256"]:
        raise ValueError("The original raw proof-contract bytes changed")
    seen, sources = set(), set()
    groups = {name: {"original_scored": 0, "raw_passed": 0, "qualified_passed": 0} for name in plan["lanes"]}
    requests = proofs = monetary = artifact_count = 0
    inherited_claims = Counter()
    for record, analyzed in zip(index["runs"], closed, strict=False):
        verify_run_source_members(record["source_member_sha256"], members)
        wanted = wanted_by_position[record["lane"], record["task"]]
        if any(record[key] != value for key, value in wanted.items()) or record["source_relative"] in sources:
            raise ValueError("A physical run or its actual original source plan was substituted")
        sources.add(record["source_relative"])
        actual_plan = plans[record["actual_source_plan"]]
        lane = actual_plan["lanes"][record["lane"]]
        if members[contract.name]["source_sha256"] != actual_plan["all_files_sha256"][lane["contract"]]:
            raise ValueError("A lane's actual proof contract differs from its raw copy")
        directory = contained(output, record["path"])
        actual = inspect(directory, actual_plan, record["actual_source_plan_sha256"], lane, tasks[record["task"]], contract)
        if actual != record["portable_evidence"]:
            raise ValueError("Exported raw score,strict proof,usage,control,candidate or tool metrics changed")
        metrics = actual["metrics"]
        if metrics["passed"] is not analyzed["passed"] or [claim["generation_id"] for claim in actual["generation_claims"]] != analyzed["generation_ids"]:
            raise ValueError("The portable original score or native IDs differ from the verified source rows")
        for key in ("actual_requests", "verified_nonbilled_service_calls", "actual_monetary_receipt_calls", "reported_monetary_cost"):
            if metrics[key] != analyzed["billing"][key]:
                raise ValueError("The portable financial proof differs from its actual source")
        for claim in actual["generation_claims"]:
            identity = claim["generation_id"]
            if identity in seen or identity in seed["generation_ids"]:
                raise ValueError("A portable native identity repeats a run or immutable historical generation")
            seen.add(identity)
            prior = registry["generations"].get(identity)
            if prior is not None:
                expected_claim = {"trace": str(Path("[project]") / record["source_relative"] / claim["trace_relative_to_run"]),
                    "request_id": claim["request_id"], "model": claim["model"]}
                if record["transport_stratum"] not in {"v27_inherited_elf", "v30_inherited_scored_relu", "v31_inherited_scored_dsh_relu", "v32_inherited_scored_main_xarray"} or prior != expected_claim:
                    raise ValueError("A new matrix generation reuses a prior registered call")
                inherited_claims[record["transport_stratum"]] += 1
        group = groups[record["lane"]]
        group["original_scored"] += 1
        group["raw_passed"] += metrics["passed"] is True
        group["qualified_passed"] += metrics["passed"] is True and (not metrics["final_control_applicable"] or
            metrics["final_protected_unchanged"] is True and metrics["final_valid_verification"] is True)
        requests += metrics["actual_requests"]
        proofs += metrics["verified_nonbilled_service_calls"]
        monetary += metrics["actual_monetary_receipt_calls"]
        for artifact in record["artifact_capture"]["outputs"]:
            if artifact["status"] == "ok":
                artifact_count += 1
                if digest(contained(directory, artifact["path"])) != artifact["export_sha256"]:
                    raise ValueError("A native captured output changed")
    complete = len(sources) == 225 and all(group["original_scored"] == 75 for group in groups.values())
    if complete and snapshot["all_original225_validated"] is not True:
        raise ValueError("The source consumer did not validate complete225 despite the copied position count")
    if index["complete_original225"] is not complete or index["stage"] != ("complete_original225_evidence" if complete else "partial_internal_evidence"):
        raise ValueError("The export falsely declares original225 completion")
    if index["complete_delivery_evidence_bundle"] is not False or index["retained_cost_scope"]["full_run_logs_exported"] is not False:
        raise ValueError("Historical metadata was mislabeled as a complete retained-cost export")
    if require_complete and not complete:
        raise ValueError("--require-complete requires all three75-task original-scored lanes")
    return {"status": "verified", "stage": index["stage"], "groups": groups,
        "unique_physical_runs": len(sources), "actual_requests": requests,
        "verified_nonbilled_service_calls": proofs, "distinct_generation_ids": len(seen),
        "allowed_exact_inherited_elf_self_bindings": inherited_claims["v27_inherited_elf"],
        "allowed_exact_inherited_v30_relu_self_bindings": inherited_claims["v30_inherited_scored_relu"],
        "allowed_exact_inherited_v31_dsh_relu_self_bindings": inherited_claims["v31_inherited_scored_dsh_relu"],
        "actual_monetary_receipt_calls": monetary, "reported_monetary_cost_usd": 0 if requests and requests == monetary else None,
        "native_artifacts": artifact_count, "inventory_files": len(members),
        "export_bytes": sum(member["export_bytes"] for member in members.values()) + (output / "index.json").stat().st_size,
        "sensitive_marker_findings": 0, "verify_reads_original_run_paths": False,
        "complete_delivery_evidence_bundle": False, "retained_cost_full_run_logs_exported": False,
        "scope": "Portable scored-position proof validation only. Historical pilots/interruptions remain source-bound metadata,not their full run exports. Runtime/SDK trees are not bundled. NVIDIA partial status does not alter the separate Hy4 report gate.",
        "new_model_calls": 0, "new_original_grader_calls": 0, "vm_commands": 0, "stop_modified": False}


def export(args):
    summary_path, rows_path = args.analysis / "summary.json", args.analysis / "trials.jsonl"
    summary_sha, rows_sha = digest(summary_path), digest(rows_path)
    snapshot = read(summary_path)
    plan_sha = snapshot["plan_sha256"]
    if plan_sha not in BINDING_COUNTS:
        raise ValueError("The selected source plan was not admitted")
    experiment = {V28_SHA: EXPERIMENT, V29_SHA: ROOT / "work/nvidia75-resume-v29-20261125",
        V30_SHA: ROOT / "work/nvidia75-small-actions-v30-20261125",
        V31_SHA: ROOT / "work/nvidia75-idle-alignment-v31-20261125",
        V32_SHA: ROOT / "work/nvidia75-parallel-dispatch-v32-20261125",
        V33_SHA: ROOT / "work/nvidia75-light-first-v33-20261125"}[plan_sha]
    plan_member = {V28_SHA: "plan-v28.json", V29_SHA: "plan-v29.json", V30_SHA: "plan-v30.json", V31_SHA: "plan-v31.json", V32_SHA: "plan-v32.json", V33_SHA: "plan-v33.json"}[plan_sha]
    plan_path, parent_path = experiment / "plan.json", ROOT / "work/nvidia75-v27-20261125/plan.json"
    plan, parent = read(plan_path), read(parent_path)
    if digest(plan_path) != plan_sha or digest(parent_path) != V27_SHA:
        raise ValueError("The actual admitted v28/v27 plans changed")
    consumer.verify_hashes(plan["all_files_sha256"])
    if (snapshot["trials_sha256"] != rows_sha
            or snapshot["stage"] not in {"partial", "complete_original225"}
            or snapshot["unexpected_position_directories"] or snapshot["identity_audit"]["errors"]
            or snapshot["historical_ledger_errors"]):
        raise ValueError("The analyzed snapshot lost its original plan or row hash")
    consumer.verify_hashes(snapshot["source_sha256"])
    tasks = {task["id"]: task for task in read(ROOT / plan["manifest"])["selected"]}
    expected = positions(plan, parent, tasks, plan_sha, plan_member)
    rows = [json.loads(line) for line in rows_path.read_text().splitlines()]
    for row, wanted in zip(rows, expected, strict=True):
        if (row["run_dir"] != wanted["source_relative"] or any(row[key] != wanted[key]
                for key in ("lane", "task", "actual_source_plan_sha256", "transport_stratum"))):
            raise ValueError("The225 analyzed rows changed actual source positions")
    closed = [row for row in rows if row.get("scoreable") is True]
    if any(not row["record_validated"] or row["validation_errors"] for row in closed):
        raise ValueError("An actual scored source failed strict validation")
    selected = closed[:args.limit] if args.limit is not None else closed
    if not selected or args.require_complete and len(selected) != 225:
        raise ValueError("No eligible scored rows,or --require-complete lacks all225 positions")
    output = args.out.absolute()
    contained(output, ".")
    if not output.resolve().is_relative_to(BASE) or output.resolve() == BASE:
        raise ValueError("Use a separate new offline output child under BASE,outside original VM-share")
    output.mkdir(parents=True, exist_ok=False)
    files = []
    metadata = [(plan_member, plan_path), ("plan-v27.json", parent_path),
        ("tasks.json", ROOT / plan["manifest"]), ("checks.json", ROOT / plan["checks"]),
        ("capture-policy-v28.json", ROOT / plan["artifact_capture_policy"]),
        ("capture-policy-v27.json", ROOT / parent["artifact_capture_policy"]),
        ("generation-seed.json", ROOT / plan["generation_seed"]),
        ("prior-generation-registry-snapshot.json", experiment / "prior-generation-registry-snapshot.json"),
        ("analysis-summary.json", summary_path), ("analysis-trials.jsonl", rows_path)]
    actual_plans = {plan_member: plan, "plan-v27.json": parent}
    if plan_sha in {V31_SHA, V32_SHA, V33_SHA}:
        inherited_path = ROOT / "work/nvidia75-small-actions-v30-20261125/plan.json"
        if digest(inherited_path) != V30_SHA:
            raise ValueError("The inherited scored ReLU protocol changed")
        actual_plans["plan-v30.json"] = read(inherited_path)
        metadata += [("plan-v30.json", inherited_path),
            ("capture-policy-v30.json", ROOT / actual_plans["plan-v30.json"]["artifact_capture_policy"])]
    if plan_sha in {V32_SHA, V33_SHA}:
        inherited_path = ROOT / "work/nvidia75-idle-alignment-v31-20261125/plan.json"
        if digest(inherited_path) != V31_SHA:
            raise ValueError("The inherited DSH ReLU protocol changed")
        actual_plans["plan-v31.json"] = read(inherited_path)
        metadata += [("plan-v31.json", inherited_path),
            ("capture-policy-v31.json", ROOT / actual_plans["plan-v31.json"]["artifact_capture_policy"])]
    if plan_sha == V33_SHA:
        inherited_path = ROOT / "work/nvidia75-parallel-dispatch-v32-20261125/plan.json"
        if digest(inherited_path) != V32_SHA:
            raise ValueError("The inherited main xarray protocol changed")
        actual_plans["plan-v32.json"] = read(inherited_path)
        metadata += [("plan-v32.json", inherited_path),
            ("capture-policy-v32.json", ROOT / actual_plans["plan-v32.json"]["artifact_capture_policy"])]
    contracts = {lane["contract"] for lane in plan["lanes"].values()}
    if len(contracts) != 1:
        raise ValueError("The actual three lanes do not share one fixed proof contract")
    contract, = contracts
    for target, source in metadata:
        files.append(legacy.copy_text(output, source, target))
    files.append(legacy.copy_text(output, ROOT / contract, "nvidia-free-contract.json", exact=True))
    binding = {"plan_sha256": plan_sha, "matched_count": BINDING_COUNTS[plan_sha],
        "matched_all_files_sha256": plan["all_files_sha256"], "analysis_summary_sha256": summary_sha,
        "analysis_rows_sha256": rows_sha, "observed_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "Actual" + str(BINDING_COUNTS[plan_sha]) + " source SHA equality before and after export. Metadata attestation is not a copy or execution of the full SDK/runtime tree."}
    binding_path = contained(output, "source-validation.json")
    write(binding_path, binding)
    legacy.private_scan(binding_path)
    files.append({"path": binding_path.name, "source_relative": None, "source_sha256": None,
        "export_sha256": digest(binding_path), "source_bytes": None,
        "export_bytes": binding_path.stat().st_size, "byte_identical": None})
    index = {"format": "nvidia75_v28_stratified_sanitized_evidence_v1", "stage": "exporting",
        "source_plan_sha256": plan_sha, "source_plan_member": plan_member, "complete_original225": False, "complete_delivery_evidence_bundle": False,
        "exporter_sha256": digest(Path(__file__)), "reused_v27_exporter_sha256": digest(exporter_path),
        "consumer_sha256": digest(consumer_path), "sanitizer_sha256": digest(Path(legacy.sanitizer.__file__)),
        "existing_exporter_sha256": digest(ROOT / "scripts/export_performance_evidence.py"),
        "files": files, "runs": [], "selection": "Validated scored prefix in fixed lane/task order; includes true and false,never filters by passed.",
        "metric_definitions": {"portable_evidence.metrics.tool_calls": "Unmodified existing inspect_nvidia_run metric:mini-swe tools.jsonl records,DSH native session tool/call count; these framework-specific counts are not a shared count of every native function execution.",
            "native_proposed_function_calls_by_name": "Actual provider tool/function proposals,not proof of execution. Original SDK and controller logs remain in the export."},
        "retained_cost_scope": {"full_run_logs_exported": False,
            "metadata": "analysis-summary.json retains separate old pilots,unscored v25/v27/v28/v29/v30/v32 attempts and the OR30/31route probes,including complete proofs and explicit unknowns. Their run logs use the separate historical-cost export.",
            "originals": "Original historical run trees remain unchanged at their declared source paths.",
            "remaining_delivery_work": "A separate retained-cost record type must later export full known-prefix proof and unknown/error evidence; these unscored runs are not sent through the scored-position verifier."},
        "new_model_calls": 0, "new_original_grader_calls": 0, "vm_commands": 0, "stop_modified": False}
    by_position = {(row["lane"], row["task"]): row for row in expected}
    for row in selected:
        consumer.verify_hashes(row["source_sha256"])
        wanted = by_position[row["lane"], row["task"]]
        source = ROOT / wanted["source_relative"]
        actual_plan = actual_plans[wanted["actual_source_plan"]]
        lane = actual_plan["lanes"][row["lane"]]
        before = inspect(source, actual_plan, wanted["actual_source_plan_sha256"], lane, tasks[row["task"]], ROOT / contract)
        destination = contained(output, str(Path("runs") / row["lane"] / source.name))
        copied, capture, omitted, source_shas = legacy.copy_run(output, source, destination, tasks[row["task"]])
        files.extend(copied)
        after = inspect(destination, actual_plan, wanted["actual_source_plan_sha256"], lane, tasks[row["task"]], output / "nvidia-free-contract.json")
        if before != after:
            raise ValueError("Sanitization changed raw score,proof,usage,control or tool metrics")
        consumer.verify_hashes(source_shas)
        index["runs"].append(wanted | {"path": str(destination.relative_to(output)), "portable_evidence": before,
            "artifact_capture": capture, "omitted_file_reasons": omitted, "source_member_sha256": source_shas})
        print(json.dumps({"lane": row["lane"], "task": row["task"], "actual_source_plan": wanted["actual_source_plan"],
            "passed": before["metrics"]["passed"], "files": len(copied)}), flush=True)
    consumer.verify_hashes(plan["all_files_sha256"])
    consumer.verify_hashes(snapshot["source_sha256"])
    if digest(summary_path) != summary_sha or digest(rows_path) != rows_sha:
        raise ValueError("The analyzed snapshot changed while being exported")
    index["complete_original225"] = len(selected) == 225
    index["stage"] = "complete_original225_evidence" if index["complete_original225"] else "partial_internal_evidence"
    write(contained(output, "index.json"), index)
    return verify(output, args.require_complete)


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="action", required=True)
    for action in ("export", "verify"):
        child = sub.add_parser(action)
        child.add_argument("--out", type=Path, required=True)
        child.add_argument("--require-complete", action="store_true")
        if action == "export":
            child.add_argument("--analysis", type=Path, default=BASE / "final-nvidia-v32-summary")
            child.add_argument("--limit", type=int)
    args = parser.parse_args()
    if args.action == "export":
        args.analysis = args.analysis.absolute()
    if args.action == "export" and args.limit is not None and args.limit < 1:
        raise ValueError("The optional scored prefix must have positive length")
    result = export(args) if args.action == "export" else verify(args.out.absolute(), args.require_complete)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
