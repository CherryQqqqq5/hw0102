import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

from ready_coordinator import digest, prepare_missing_image, read_json
from scripts.export_performance_evidence import inspect_run
from scripts.summarize_performance_comparison import control_artifact_metrics


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    root, plan = Path.cwd(), read_json(args.plan)

    def validate():
        for name, expected in plan["all_files_sha256"].items():
            if digest(root / name) != expected:
                raise ValueError("A fixed prospective experiment source changed: " + name)
        if read_json(root / "work/performance-stop-20261122.json")["active"]:
            raise RuntimeError("The actual financial stop prevents every new generation")

    validate()
    task, = read_json(root / plan["manifest"])["selected"]
    labels = plan["prospective_trials"]
    if task["id"] != plan["task"] or len(labels) != 2 or len(set(labels)) != 2 or plan["model"] != "hy4flash-free":
        raise ValueError("Only two uniquely prespecified sessions on the verified free model are admitted")
    if args.validate_only:
        print(json.dumps({"status": "validated", "prospective_sessions": 2, "new_model_calls": 0}), flush=True)
        return
    queue = root / plan["queue"]
    queue.mkdir(exist_ok=True)
    environment = os.environ | {"PYTHONPATH": str(root), "DOCKER_HOST": "unix://" + str(root / "work/v/c/sock/docker.sock"),
        "DOCKER_CONFIG": str(root / "work/docker-config"), "LIMA_HOME": str(root / ".v"),
        "COURSE_DOCKER_BIN": str(root / "work/vendor/docker/docker"), "COURSE_CODEBUDDY_IMAGES": "1",
        "COURSE_CODEBUDDY_IMAGE_METADATA": str(root / "work/free-channel-capabilities-20261122/cloud-model-metadata.json"),
        "COURSE_ELF_PUBLIC_WHEEL": str(root / "work/vmshare/elf-public-check-deps/pyelftools-0.33-py3-none-any.whl"),
        "COURSE_CODEBUDDY_GUARDED_BIN": str(root / "work/hy4-free-readiness-20261124/codebuddy-guard.sh"),
        "COURSE_FREE_STOP_PATH": str(root / "work/performance-stop-20261122.json"),
        "COURSE_PINNED_IMAGE_COPY_DRIVER": str(root / plan["image_copy_driver"]),
        "COURSE_HARBOR_CAPTURE_POLICY": str(root / plan["artifact_capture_policy"])}
    rows, identities = [], set()
    for label in labels:
        validate()
        directory = queue / (task["id"] + "-C0-" + label)
        if not (directory / "result.json").exists():
            if directory.exists():
                raise RuntimeError("An unfinished real session requires diagnosis; do not overwrite or resample")
            prepare_missing_image(task, environment)
            validate()
            command = [sys.executable, str(root / plan["resource_driver"]), "--task", task["id"],
                "--benchmark", task["benchmark"], "--image", task["image"], "--expected-image-id", plan["pin"],
                "--record", str(directory.with_suffix(".resources.json")), "--", sys.executable,
                str(root / plan["driver"]), "--task", task["id"], "--manifest", str(root / plan["manifest"]),
                "--configuration", "C0", "--persistent-session", "--framework", "mini-swe",
                "--runtime-root", str(root / plan["runtime_root"]), "--run-dir", str(directory),
                "--checks", str(root / plan["checks"])]
            with directory.with_suffix(".dispatch.log").open("x") as stream:
                subprocess.run(command, env=environment, stdout=stream, stderr=subprocess.STDOUT, check=True)
        metrics = inspect_run(directory, "mini-swe")
        protocol = read_json(directory.with_suffix(".protocol.json"))
        normalized = {key: value for key, value in protocol.items() if key != "historical_unknown_calls_preserved"}
        if normalized != plan["expected_protocol"] or read_json(directory / "trial.json")["task"] != task:
            raise ValueError("The actual input, model or execution protocol differs from the prospective plan")
        events = [json.loads(line) for trace in directory.rglob("model.jsonl") for line in trace.read_text().splitlines()]
        fresh = {message for event in events if event["event"] == "billing_verified" for message in event["fresh_model_message_ids"]}
        if not fresh or identities.intersection(fresh):
            raise ValueError("The two independent sessions lack unique actual generations")
        identities.update(fresh)
        control = control_artifact_metrics(directory, "mini-swe", "C0")
        rows.append({"label": label, "run_dir": str(directory.relative_to(root)),
            "original_score_sha256": digest(directory / "result.json"), **metrics, **control,
            "qualified_passed": metrics["passed"] and control["final_valid_verification"] is True
                and control["final_protected_unchanged"] is True})
        state = {"stage": "complete" if len(rows) == 2 else "running", "plan_sha256": digest(args.plan),
            "required": 2, "completed": len(rows), "passed": sum(row["passed"] for row in rows),
            "qualified_passed": sum(row["qualified_passed"] for row in rows), "rows": rows,
            "all_core_scores_and_revision_attempts_preserved": True, "incremental_acceptance_join_not_performed": True}
        (queue / "state.json").write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n")
        print(json.dumps({"task": task["id"], "label": label, "passed": metrics["passed"],
            "qualified_passed": rows[-1]["qualified_passed"], "actual_requests": metrics["actual_requests"]}), flush=True)


if __name__ == "__main__":
    main()
