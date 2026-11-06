import argparse
import json
import os
import re
import shlex
import shutil
import subprocess
import time
from contextlib import closing
from dataclasses import asdict
from pathlib import Path

from course_eval.agent import RunLimits, run_baseline
from course_eval.aider_runtime import prepare_aider_runtime
from course_eval.docker_target import DockerTarget
from course_eval.inventory import REVISIONS
from course_eval.terminal_setup import prepare_offline_verifier
from course_eval.verification import PublicCheck


AIDER_TESTS = {
    "python": "python -m pytest",
    "rust": "cargo test --offline -- --include-ignored",
    "go": "GOPROXY=off go test ./...",
    "javascript": "/aider/benchmark/npm-test.sh",
    "cpp": "/aider/benchmark/cpp-test.sh",
    "java": "gradle --no-daemon --offline test",
}
SWE_HIDDEN_CACHES = ("/opt/miniconda3/pkgs", "/root/.cache/pip")


def swe_public_dependencies(task):
    directories = {"django__django-12193": "django-12193", "pytest-dev__pytest-5631": "pytest-5631-py39"}
    if task["id"] not in directories:
        return {}
    root = Path(os.environ.get("COURSE_PUBLIC_DEPS_ROOT", "work/vmshare/confirmation-public-deps"))
    source = (root / directories[task["id"]]).resolve(strict=True)
    return {"read_only_mounts": ((str(source), "/opt/course-public-deps"),),
            "environment": {"PYTHONPATH": "/opt/course-public-deps"}}


def write_json(path: Path, value: dict) -> None:
    staged = path.with_name(f".{path.name}.writing")
    staged.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    staged.replace(path)


def require_tool(output: dict) -> str:
    if output["returncode"]:
        raise RuntimeError(f"Environment command failed: {output}")
    return output["stdout"]


def aider_source(task: dict, sources: Path) -> Path:
    language, slug = task["id"].split("/", 1)
    return sources / f"polyglot-benchmark-{REVISIONS['aider']}" / language / "exercises/practice" / slug


def aider_cwd(task: dict) -> str:
    # Exercism 的 CMakeLists 通过当前目录名定位原题的测试源文件。
    return "/exercise/" + task["id"].split("/", 1)[1] if task["stratum"] == "cpp" else "/exercise"


def prepare_aider(task: dict, original: Path, destination: Path) -> tuple[str, list[str]]:
    config = json.loads((original / ".meta/config.json").read_text())["files"]
    sources = [name for name in config["solution"] if name not in {"CMakeLists.txt", "Cargo.toml"}]
    ignore_paths = set(config.get("example", []))

    def ignored(directory: str, entries: list[str]) -> set[str]:
        relative = Path(directory).relative_to(original)
        return {entry for entry in entries if entry in {".meta", ".docs", ".git"}
                or (relative / entry).as_posix() in ignore_paths}

    shutil.copytree(original, destination, ignore=ignored)
    docs = original / ".docs"
    instruction = "\n\n".join((docs / name).read_text() for name in (
        "introduction.md", "instructions.md", "instructions.append.md",
    ) if (docs / name).is_file())
    command = AIDER_TESTS[task["stratum"]]
    instruction += (f"\n\nEdit only these solution files: {', '.join(sources)}. "
                    f"Original tests are available. Run them using `{command}`. "
                    "The grader restores its own original test and build files.")
    return instruction, sources


def score_aider(task: dict, initial: Path, candidate: Path, directory: Path, image: str) -> dict:
    started = time.monotonic()
    language = task["stratum"]
    stage = directory / "grader-input"
    shutil.copytree(initial, stage)
    for file in candidate.rglob("*"):
        if file.is_file():
            relative = file.relative_to(candidate)
            shutil.copy2(file, stage / relative)
    if language == "java":
        for name in task["test_files"]:
            file = stage / name
            # Aider 的正式测试启用原测试中的 @Disabled 用例。
            file.write_text(re.sub(r"@Disabled\([^)]*\)\s*\n", "", file.read_text()))
    with DockerTarget(image, aider_cwd(task), platform="linux/arm64", memory_mb=2048, cpus=1) as target:
        target.upload_tree(stage)
        # 评分容器的冷启动编译时间独立于模型的交互时限。
        output = target.exec(AIDER_TESTS[language], timeout=600)
    write_json(directory / "grader.json", output)
    scoreable = output["returncode"] not in {124, 125, 126, 127, 137}
    return {"scoreable": scoreable, "passed": output["returncode"] == 0 if scoreable else None,
            "grader_exit_code": output["returncode"], "grader_seconds": time.monotonic() - started}


def run_aider(task: dict, sources: Path, directory: Path, limits: RunLimits,
              configuration: str, checks: tuple[PublicCheck, ...]) -> dict:
    initial = directory / "starter"
    instruction, files = prepare_aider(task, aider_source(task, sources), initial)
    language = task["stratum"]
    image = f"nju-course-aider:{language}"
    candidate = directory / "candidate"
    candidate.mkdir()
    original = aider_source(task, sources)
    meta = json.loads((original / ".meta/config.json").read_text())["files"]
    deps = tuple(dict.fromkeys(files + meta["test"] + meta.get("invalidator", [])))
    checks = checks or (PublicCheck("public-suite", "Original tests are available.", AIDER_TESTS[language], deps),)
    with DockerTarget(image, aider_cwd(task), platform="linux/arm64", memory_mb=2048, cpus=1) as target:
        target.upload_tree(initial)
        if limits.strict_wall:
            runtime = prepare_aider_runtime(target, language)
            if runtime:
                write_json(directory / "public-runtime.json", runtime)
        scope = {"kind": "files", "artifacts": files,
                 "protected": [str(path.relative_to(initial)) for path in initial.rglob("*")
                               if path.is_file() and str(path.relative_to(initial)) not in files]}
        try:
            outcome = run_baseline(instruction, target, directory, limits, configuration=configuration,
                                   checks=checks, scope=scope)
        finally:
            missing = [file for file in files if not target.download_file(file, candidate / file)]
            write_json(directory / "artifact.json", {"missing_required_sources": missing})
    if missing:
        return outcome | {"scoreable": True, "passed": False, "missing_required_sources": missing}
    grade = score_aider(task, initial, candidate, directory, image)
    return outcome | grade


def grade_swe(row: dict, patch: str, directory: Path) -> dict:
    import docker
    from docker.models.containers import ContainerCollection
    from swebench.harness import run_evaluation
    from swebench.harness.utils import make_test_spec

    class OfflineContainers(ContainerCollection):
        def create(self, image, command=None, **kwargs):
            # 官方评分器直接运行候选补丁。容器在创建时关闭网络。
            return super().create(image, command, **(kwargs | {"network_mode": "none"}))

    class OfflineDockerClient(docker.DockerClient):
        @property
        def containers(self):
            return OfflineContainers(client=self)

    if not shutil.which("docker"):
        raise RuntimeError("The official SWE-bench harness requires docker on PATH for cleanup")
    started = time.monotonic()
    run_evaluation.RUN_EVALUATION_LOG_DIR = directory / "swe-official"
    pred = {"instance_id": row["instance_id"], "model_name_or_path": "course-mini-swe-agent",
            "model_patch": patch}
    with closing(OfflineDockerClient.from_env(timeout=240)) as client:
        result = run_evaluation.run_instance(make_test_spec(row), pred, client, directory.name,
                                             timeout=600, skip_patch=not patch.strip())
    if result is None:
        return {"scoreable": False, "passed": None, "grader_error": "See the official run log",
                "grader_seconds": time.monotonic() - started}
    instance, report = result
    judgment = report[instance]
    scoreable = not judgment.get("infra_failure", False)
    return {"scoreable": scoreable, "passed": judgment["resolved"] if scoreable else None,
            "grader_seconds": time.monotonic() - started}


def check_swe_checkout(task: dict, target: DockerTarget, directory: Path) -> str:
    base = task["base_commit"]
    base_tree_expr = shlex.quote(base + "^{tree}")
    head, head_tree, base_tree = require_tool(target.exec(
        "git rev-parse HEAD 'HEAD^{tree}' " + base_tree_expr, timeout=10,
    )).splitlines()
    status = require_tool(target.exec("git status --porcelain", timeout=20))
    paths = require_tool(target.exec("git diff --raw --no-renames --no-abbrev " + shlex.quote(base) + " HEAD",
                                    timeout=20)).splitlines() if head_tree != base_tree else []
    mode_changes = 0
    # 官方构建可能统一设置可执行位。路径、对象类型和文件内容仍须与数据集一致。
    for line in paths:
        old_mode, new_mode, old_blob, new_blob, kind = line.split("\t", 1)[0].split()
        if {old_mode.removeprefix(":"), new_mode} == {"100644", "100755"} and old_blob == new_blob and kind == "M":
            mode_changes += 1
    write_json(directory / "checkout.json", {"base_commit": base, "image_commit": head,
                                             "base_tree": base_tree, "image_tree": head_tree, "status": status,
                                             "changed_paths": len(paths), "executable_bit_changes": mode_changes})
    if len(paths) != mode_changes or status:
        raise RuntimeError(f"SWE-bench checkout differs from the original source files: {head} vs {base}")
    caches = shlex.join(SWE_HIDDEN_CACHES)
    files = require_tool(target.exec(f"find {caches} -mindepth 1 -maxdepth 1 -print -quit", timeout=10))
    if files:
        raise RuntimeError("The SWE-bench agent can read package-cache files outside the original repository")
    return head


def run_swe(task: dict, sources: Path, directory: Path, limits: RunLimits,
            configuration: str, checks: tuple[PublicCheck, ...]) -> dict:
    rows = json.loads((sources / "swe-grader.json").read_text())
    row = next(row for row in rows if row["instance_id"] == task["id"])
    with DockerTarget(task["image"], "/testbed", platform="linux/amd64", memory_mb=3072, cpus=2,
                      read_only_empty_dirs=SWE_HIDDEN_CACHES, **swe_public_dependencies(task)) as target:
        head = check_swe_checkout(task, target, directory)
        instruction = row["problem_statement"] + "\n\nFix production code. Preserve existing tests and test configuration."
        try:
            outcome = run_baseline(instruction, target, directory, limits, configuration=configuration, checks=checks,
                                   scope={"kind": "repository", "python": "/opt/miniconda3/envs/testbed/bin/python"})
        finally:
            patch = require_tool(target.exec("git add -N -A && git diff --binary " + shlex.quote(head), timeout=30))
            (directory / "candidate.patch").write_text(patch, encoding="utf-8")
    return outcome | grade_swe(row, patch, directory)


def prepare_terminal_task(task: dict, sources: Path, directory: Path, *, oracle: bool = False) -> Path:
    original = sources / f"terminal-bench-2-1-{REVISIONS['terminal']}" / "tasks" / task["id"]
    path = directory / task["id"]
    shutil.copytree(original, path, ignore=None if oracle else shutil.ignore_patterns("solution"))
    # 评分依赖随原题测试一起注入。Docker Compose 在容器创建时禁用网络。
    prepare_offline_verifier(path)
    return path


def terminal_trial(path: Path, directory: Path, agent: str, env: dict[str, str],
                   *, agent_timeout_seconds: float | None = None) -> dict:
    cli = os.environ["COURSE_HARBOR_BIN"]
    command = [
        cli, "trials", "start", "--path", str(path), "--agent", agent,
        "--env", "docker", "--trials-dir", str(directory),
        "--extra-docker-compose", str(Path(__file__).with_name("terminal-no-network.yaml").resolve()),
    ]
    if agent_timeout_seconds is not None:
        command.extend(("--agent-timeout", str(agent_timeout_seconds)))
    process = subprocess.run(command, env=env, text=True, capture_output=True, timeout=2700, check=False)
    (directory / "harbor.stdout").write_text(process.stdout, encoding="utf-8")
    (directory / "harbor.stderr").write_text(process.stderr, encoding="utf-8")
    process.check_returncode()
    result_path, = directory.glob("*/result.json")
    result = json.loads(result_path.read_text())
    verification = result.get("verifier_result")
    reward = (verification.get("rewards") or {}).get("reward") if verification else None
    scoreable = reward in {0, 1} and not result.get("exception_info")
    return {"scoreable": scoreable, "passed": reward == 1 if scoreable else None,
            "harbor_result": str(result_path.relative_to(directory))}


def run_terminal(task: dict, sources: Path, directory: Path, limits: RunLimits,
                 configuration: str, checks: tuple[PublicCheck, ...]) -> dict:
    path = prepare_terminal_task(task, sources, directory)
    env = os.environ | {"COURSE_RUN_LIMITS": limits.model_dump_json(), "COURSE_CONFIGURATION": configuration,
                        "COURSE_PUBLIC_CHECKS": json.dumps([asdict(check) for check in checks]),
                        "COURSE_CANDIDATE_SCOPE": json.dumps(task.get("candidate_scope"))}
    # 内部预算终止模型和工具；外层额外覆盖环境识别与日志收尾，避免抢先取消线程。
    timeout = limits.wall_seconds + 30 if limits.strict_wall else None
    outcome = terminal_trial(path, directory, "course_eval.harbor_agent:CourseMiniSweAgent", env,
                             agent_timeout_seconds=timeout)
    return outcome | {"command_supervisor": "descendant_tree_v2"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--sources", required=True, type=Path)
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--id", required=True)
    parser.add_argument("--configuration", choices=("B0", "BP", "A", "F", "R", "RP", "C0", "C1"), default="B0")
    parser.add_argument("--checks", type=Path, help="Task-visible check plans for repository and terminal tasks")
    parser.add_argument("--pilot", action="store_true")
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    if manifest["stage"] != "frozen" and not args.pilot:
        parser.error("Formal evaluation requires an environment-verified frozen manifest")
    task = next((row for row in manifest["selected"] if row["id"] == args.id), None)
    if task is None and args.pilot:
        task = next((row for row in manifest["inventory"] if row["id"] == args.id and not row["exclude"]), None)
    if task is None or (args.pilot and task.get("split") == "H"):
        parser.error("The requested task is unavailable for this phase")
    plans = json.loads(args.checks.read_text()) if args.checks else {}
    checks = tuple(PublicCheck(**(check | {"dependencies": tuple(check["dependencies"])}))
                   for check in plans.get(task["id"], []))
    if task["benchmark"] != "aider" and args.configuration != "B0" and not checks:
        parser.error("This treatment requires a frozen task-visible check plan")
    args.run_dir.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    limits = RunLimits.model_validate_json(os.environ.get("COURSE_RUN_LIMITS", "{}"))
    write_json(args.run_dir / "trial.json", {"task": task, "phase": "pilot" if args.pilot else "formal",
                                           "configuration": args.configuration, "status": "started",
                                           "model": os.environ["COURSE_MODEL_ID"],
                                           "backend": os.environ["COURSE_MODEL_BACKEND"],
                                           "protocol_commit": os.environ.get("COURSE_PROTOCOL_COMMIT"),
                                           "limits": limits.model_dump()})
    run = {"aider": run_aider, "swe": run_swe, "terminal": run_terminal}[task["benchmark"]]
    try:
        outcome = run(task, args.sources.resolve(), args.run_dir.resolve(), limits, args.configuration, checks)
    except Exception as exc:
        write_json(args.run_dir / "result.json", {"task": task["id"], "wall_seconds": time.monotonic() - started,
                                                 "scoreable": False, "passed": None,
                                                 "error_type": type(exc).__name__, "error": str(exc)})
        raise
    write_json(args.run_dir / "result.json", {"task": task["id"], "wall_seconds": time.monotonic() - started, **outcome})


if __name__ == "__main__":
    main()
