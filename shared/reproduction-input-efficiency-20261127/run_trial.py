import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path

os.environ.setdefault("MSWEA_GLOBAL_CONFIG_DIR", str(Path.cwd() / "work/miniswe-config"))
os.environ.setdefault("MSWEA_SILENT_STARTUP", "1")

from course_eval.agent import RunLimits
from course_eval.financial_stop import preserve_free_stop


parser = argparse.ArgumentParser()
parser.add_argument("--task", required=True)
parser.add_argument("--manifest", type=Path, required=True)
parser.add_argument("--configuration", choices=("B0", "C0", "C1"), default="B0")
parser.add_argument("--checks", type=Path)
parser.add_argument("--run-dir", type=Path, required=True)
parser.add_argument("--max-output-tokens", type=int, default=64000)
parser.add_argument("--backend", choices=("codebuddy", "openrouter-free", "nvidia-free"), default="codebuddy")
parser.add_argument("--model", default="hy4flash-free")
parser.add_argument("--runtime-root", type=Path)
parser.add_argument("--persistent-session", action="store_true")
parser.add_argument("--nvidia-contract", type=Path)
parser.add_argument("--nvidia-qualification", type=Path)
parser.add_argument("--framework", choices=("mini-swe", "dsh"), default="mini-swe")
parser.add_argument("--readonly-swe-tests", action="store_true")
args = parser.parse_args()
root = Path.cwd()
execution = json.loads((Path(__file__).parent / "execution.json").read_text())
phase = json.loads(Path(execution["guest_state_path"]).read_text())
if phase["restricted"] is not True or phase["stage"] != "qualified_tcg_guest_small_container_only":
    raise RuntimeError("The ModelArts guest has not returned to its qualified isolated task phase")
if args.persistent_session and args.backend != "codebuddy":
    raise ValueError("Native CLI session persistence applies only to the CodeBuddy backend")
stop_path = root / "work/performance-stop-20261122.json"
historical_unknown = 13
if stop_path.exists():
    stop = json.loads(stop_path.read_text())
    if stop["active"]:
        raise RuntimeError(f"Model calls remain stopped for an unresolved billing receipt: {stop_path}")
    historical_unknown = stop["accepted_total_unknown_calls"]
runtime = args.runtime_root.resolve() if args.runtime_root else root
if args.readonly_swe_tests and not (runtime / "course_eval/repository_readonly.py").is_file():
    raise ValueError("The requested frozen runtime does not implement read-only SWE repository protection")
if args.backend == "codebuddy":
    if args.model != "hy4flash-free":
        raise ValueError("Only the actually verified CodeBuddy zero-credit route is admitted")
    metadata = json.loads(Path("work/input-efficiency-20261126/free-model-metadata/cloud-model-metadata.json").read_text())
    selected = next(row for row in metadata["available_models"] if row["id"] == args.model)
    if selected["credits"] != "x0.00 credits" or args.max_output_tokens > selected["maxOutputTokens"]:
        raise RuntimeError("The selected model does not advertise this free output allowance")
elif args.backend == "nvidia-free":
    from course_eval.nvidia_free import NvidiaFeeError, NvidiaFreeModel, admit_nvidia_channel, nvidia_queue_snapshot, preserve_nvidia_fee_stop

    if args.nvidia_contract is None or args.nvidia_qualification is None:
        raise ValueError("The NVIDIA backend requires an approved contract and an actual successful qualification")
    try:
        contract, qualification = admit_nvidia_channel(args.nvidia_contract, args.nvidia_qualification, args.max_output_tokens)
        if args.model != contract["model"]:
            raise NvidiaFeeError("The requested model differs from its qualified free NVIDIA route")
    except NvidiaFeeError:
        preserve_nvidia_fee_stop(stop_path, reason="The NVIDIA free channel failed its real qualification binding")
        raise
    queue_snapshot = nvidia_queue_snapshot(contract)
    if not queue_snapshot["ready"]:
        raise RuntimeError("The fixed NVIDIA model is busy; wait outside the task budget without creating a model request")
elif not args.model.endswith(":free"):
    raise ValueError("Only fixed OpenRouter :free models are admitted")
limits = RunLimits(model_calls=500, wall_seconds=1800, command_seconds=120,
                   max_output_tokens=args.max_output_tokens, timeout_retries=0, strict_wall=True)
if args.run_dir.exists():
    raise FileExistsError(args.run_dir)
args.run_dir.parent.mkdir(parents=True, exist_ok=True)
environment = os.environ | {
    "PATH": str(root / "work/vendor/docker") + os.pathsep + os.environ["PATH"],
    "PYTHONPATH": str(runtime), "TMPDIR": str(root / "work/process-tmp"),
    "DOCKER_HOST": os.environ["COURSE_STUDY_DOCKER_HOST"],
    "DOCKER_CONFIG": str(root / "work/docker-config"),
    "COURSE_DOCKER_BIN": str(root / "work/vendor/docker/docker"),
    "COURSE_HARBOR_BIN": str(root / "work/.venv/bin/harbor"),
    "COURSE_TERMINAL_DEPS": str(root / "work/terminal-runtime/deps"),
    "COURSE_TERMINAL_PYTHON": str(root / "work/terminal-runtime/python-3.13.12-linux-x86_64.tar.gz"),
    "COURSE_TERMINAL_PYTHON_312": str(root / "work/terminal-runtime/python-3.12.13-linux-x86_64.tar.gz"),
    "COURSE_AIDER_PUBLIC_PYTHON": str(root / "work/terminal-runtime/python-3.13.12-linux-x86_64.tar.gz"),
    "COURSE_AIDER_PLATFORM": "linux/amd64",
    "COURSE_PUBLIC_DEPS_ROOT": str(root / "work/vmshare/confirmation-public-deps"),
    "COURSE_CODEBUDDY_BIN": os.environ.get("COURSE_CODEBUDDY_GUARDED_BIN", str(root / "work/codebuddy/node_modules/.bin/codebuddy")),
    "COURSE_MODEL_BACKEND": args.backend, "COURSE_MODEL_ID": args.model,
    "COURSE_AGENT_FRAMEWORK": args.framework,
    "COURSE_REPOSITORY_READONLY": "1" if args.readonly_swe_tests else "0",
    "COURSE_REPOSITORY_READONLY_CACHE": str(root / "work/vmshare/repository-readonly-v1"),
    "COURSE_DSH_RUNTIME": str(root / "work/vmshare/dsh-linux-runtime"),
    "COURSE_DSH_RUNTIME_ARM64": str(root / "work/vmshare/dsh-linux-arm64"),
    "COURSE_CODEBUDDY_PERSIST_SESSION": "1" if args.persistent_session else "0",
    "COURSE_FREE_MODEL_METADATA": str(root / "work/free-channel-metadata-20261122/openrouter-metadata.json"),
    "COURSE_RUN_LIMITS": limits.model_dump_json(),
    "MSWEA_GLOBAL_CONFIG_DIR": str(root / "work/miniswe-config"), "MSWEA_SILENT_STARTUP": "1",
}
environment.pop("CODEBUDDY_FALLBACK_MODEL", None)
environment.pop("COURSE_PROTOCOL_COMMIT", None)
if args.backend == "nvidia-free":
    environment.update(COURSE_NVIDIA_FREE_CONTRACT=str(args.nvidia_contract.resolve()),
        COURSE_NVIDIA_FREE_QUALIFICATION=str(args.nvidia_qualification.resolve()),
        COURSE_FREE_STOP_PATH=str(stop_path))
command = [str(root / "work/.venv/bin/python"), "-m", "course_eval.benchmarks",
    "--manifest", str(args.manifest.resolve()), "--sources", str(root / "work/datasets"),
    "--id", args.task, "--configuration", args.configuration, "--run-dir", str(args.run_dir.resolve())]
if args.checks:
    command += ["--checks", str(args.checks.resolve())]
protocol = {"task": args.task, "model": args.model, "backend": args.backend, "configuration": args.configuration,
    "environment_context": environment.get("COURSE_ENVIRONMENT_CONTEXT") == "1",
    "tool_output_policy": environment.get("COURSE_TOOL_OUTPUT_POLICY"),
    "execution_environment": "ModelArts project Linux guest; original container scoring",
    "docker_endpoint": environment["DOCKER_HOST"], "aider_platform": environment["COURSE_AIDER_PLATFORM"],
    "compact_success_feedback": environment.get("COURSE_COMPACT_SUCCESS_FEEDBACK") == "1",
    "common_instruction_sha256": hashlib.sha256(environment.get("COURSE_COMMON_TASK_INSTRUCTION", "").encode()).hexdigest(),
    "framework": args.framework,
    "readonly_swe_repository": args.readonly_swe_tests,
    "persistent_native_session": args.persistent_session,
    "limits": limits.model_dump(), "runtime_root": str(runtime.relative_to(root)),
    "billing": "Actual per-call model identity and zero-cost receipt; no request retry or paid fallback",
    "historical_unknown_calls_preserved": historical_unknown, "benchmark_grader": "unchanged original task scorer"}
if args.backend == "nvidia-free":
    protocol.update(billing="Authorized official non-billed NVIDIA endpoint; individual actual model/request/usage verified; missing money remains null; no retry or paid fallback",
        nvidia_contract=str(args.nvidia_contract), nvidia_qualification=str(args.nvidia_qualification),
        qualification_generation_id=qualification["generation_id"], reasoning_effort=NvidiaFreeModel.reasoning_effort,
        admission_queue=queue_snapshot)
args.run_dir.with_suffix(".protocol.json").write_text(json.dumps(protocol, ensure_ascii=False, indent=2) + "\n")
log = args.run_dir.with_suffix(".log")
with log.open("x") as stream:
    completed = subprocess.run(command, cwd=runtime, env=environment, stdout=stream, stderr=subprocess.STDOUT)
print(json.dumps({"run_dir": str(args.run_dir), "returncode": completed.returncode, "log": str(log)}, ensure_ascii=False))
traces = []
for path in args.run_dir.rglob("model.jsonl"):
    traces.extend(json.loads(line) for line in path.read_text().splitlines())
requests_seen = {event["request_id"] for event in traces if event["event"] == "request"}
verified = {event["request_id"] for event in traces if event["event"] == "billing_verified"}
if args.backend == "nvidia-free":
    from course_eval.nvidia_free import audit_nvidia_events

    try:
        audit = audit_nvidia_events(traces, args.nvidia_contract, args.model, args.max_output_tokens)
    except NvidiaFeeError:
        preserve_nvidia_fee_stop(stop_path, run_dir=str(args.run_dir),
                                reason="The NVIDIA post-run actual free-service evidence failed verification")
        raise
    (args.run_dir / "nvidia-free-evidence.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n")
    if audit["unverified_requests"] or any(event["event"] in {"billing_error", "request_error"} for event in traces):
        raise RuntimeError("The NVIDIA trial contains incomplete response evidence; preserve it and stop the trial")
elif requests_seen != verified or any(event["event"] in {"billing_error", "request_error"} for event in traces):
    preserve_free_stop(stop_path, run_dir=str(args.run_dir),
        unverified_requests=sorted(requests_seen - verified), reason="Actual per-request fee is missing or invalid")
    raise RuntimeError("At least one actual model call lacks its own verified zero-cost receipt; stop")
if completed.returncode:
    raise RuntimeError("Trial stopped; inspect its actual result and billing before any further model call")
result = json.loads((args.run_dir / "result.json").read_text())
print(json.dumps(result, ensure_ascii=False, indent=2))
if not result["scoreable"]:
    raise RuntimeError("The original task score is missing; repair the recorded mechanical failure before continuing")
