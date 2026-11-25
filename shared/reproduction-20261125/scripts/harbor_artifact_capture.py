import hashlib
import json
import os
from pathlib import Path, PurePosixPath


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare_args(argv, *, root=None, policy_file=None):
    root = Path(root or Path(__file__).resolve().parents[1])
    policy_file = Path(policy_file or os.environ.get("COURSE_HARBOR_CAPTURE_POLICY")
        or root / "work/harbor-artifact-capture/policy.json")
    if argv[1:3] != ["trials", "start"] or not policy_file.exists():
        return argv
    policy = json.loads(policy_file.read_text())
    if not policy["active"] or os.environ.get("COURSE_MODEL_BACKEND") not in policy.get("backends", ["nvidia-free"]):
        return argv

    def option(name):
        if argv.count(name) != 1:
            raise ValueError(f"Artifact capture requires exactly one {name}")
        return Path(argv[argv.index(name) + 1]).resolve(strict=True)

    directory, task_path = option("--trials-dir"), option("--path")
    queues = [(root / path).resolve() for path in policy["queues"]]
    if not any(directory.parent == queue for queue in queues):
        return argv
    if digest(Path(__file__)) != policy["capture_code_sha256"]:
        raise ValueError("The registered artifact capture code changed")
    if digest(root / "work/.venv/bin/harbor") != policy["launcher_sha256"]:
        raise ValueError("The registered Harbor launcher changed")
    if task_path.parent != directory or any(x in argv for x in ("--config", "-c")):
        raise ValueError("Artifact capture received an unexpected trial layout or existing config")
    scope = json.loads(os.environ.get("COURSE_CANDIDATE_SCOPE", "null"))
    artifacts = scope.get("artifacts", []) if scope else []
    expected = policy["task_artifacts"].get(task_path.name)
    if artifacts != expected:
        raise ValueError("The actual artifact scope differs from the registered task")
    if not artifacts:
        return argv
    for name in artifacts:
        path = PurePosixPath(name)
        if not path.is_absolute() or ".." in path.parts or path.parts[1] not in {"app", "workspace"}:
            raise ValueError("Artifact collection is restricted to declared task outputs")
    config = {"task": {"path": str(task_path)}, "artifacts": artifacts}
    config_path = directory / "artifact-capture-config.json"
    with config_path.open("x") as stream:
        json.dump(config, stream, indent=2)
        stream.write("\n")
    effective = argv[:3] + ["--config", str(config_path)] + argv[3:]
    # 只给 Harbor 增加结束后下载项，不改任务、提示、工具、评分或费用证明。
    record = {"kind": "native_harbor_post_agent_artifact_collection", "original_argv": argv,
              "effective_argv": effective, "policy_sha256": digest(policy_file),
              "capture_code_sha256": digest(Path(__file__)), "launcher_sha256": policy["launcher_sha256"],
              "config_sha256": digest(config_path), "sources": artifacts,
              "framework": os.environ.get("COURSE_AGENT_FRAMEWORK"),
              "model_requests_made_by_instrumentation": 0}
    with (directory / "artifact-capture.json").open("x") as stream:
        json.dump(record, stream, indent=2)
        stream.write("\n")
    return effective
