import hashlib
import json
import os
from pathlib import Path

from course_eval.agent import CodeBuddyModel, RunLimits
from course_eval.docker_target import DockerTarget
from course_eval.tool_output import ToolOutput, environment_context


ROOT = Path(__file__).resolve().parents[2]
FOLDER = Path(__file__).parent.resolve()


def main():
    os.environ.update(COURSE_MODEL_ID="hy4flash-free", COURSE_CODEBUDDY_PERSIST_SESSION="1")
    os.environ.setdefault("COURSE_CODEBUDDY_BIN", str(ROOT / "work/codebuddy/node_modules/.bin/codebuddy"))
    source = Path(os.environ.get("COURSE_OUTPUT_REPLAY_LOG", str(ROOT / "work/vmshare/performance75-hy4-sql-layout-v18-main-20261125/javascript-book-store-C0-r1/tools.jsonl")))
    archived = [json.loads(line) for line in source.read_text().splitlines()]
    sample = max(archived, key=lambda row: len(row["stdout"] + row["stderr"]))
    folder = FOLDER / os.environ.get("COURSE_OUTPUT_QUALIFICATION", "output-qualification")
    folder.mkdir(exist_ok=False)
    results = []
    platform = os.environ.get("COURSE_AIDER_PLATFORM", "linux/arm64")
    with DockerTarget("nju-course-aider:javascript", "/exercise", platform=platform, memory_mb=1024, cpus=1) as target:
        target.upload_tree(source.parent / "starter")
        prepared = target.exec("command -v python3", timeout=10)
        if prepared["returncode"]:
            from course_eval.aider_runtime import prepare_aider_runtime

            prepare_aider_runtime(target, "javascript")
        context = environment_context(target, folder, {"python": "python3"})
        assert "/exercise" in context
        for policy in ("archive", "digest"):
            directory = folder / policy
            directory.mkdir()
            store = ToolOutput(directory / "tool-output", target, policy)
            original = sample["stdout"] + sample["stderr"]
            message = {"extra": {"actions": [{"command": sample["command"], "tool_call_id": "archived-book-store"}]}}
            output = {"output": original, "returncode": sample["returncode"], "exception_info": ""}
            projected, = store.project(message, [output])
            model = CodeBuddyModel(directory, RunLimits(), "{{ output | tojson }}")
            formatted, = model.format_observation_messages(message, [projected])
            decoded = json.loads(formatted["content"])
            assert decoded["returncode"] == output["returncode"]
            recovered = target.exec("cat /course-tool-output/output-0001.txt", timeout=10)
            assert recovered["returncode"] == 0 and recovered["stdout"] == original
            if policy == "digest":
                assert len(decoded["output"]) < len(original)
                assert original[:200] in decoded["output"] and original[-200:] in decoded["output"]
            results.append({"policy": policy, "original_characters": len(original),
                "presented_characters": len(decoded["output"]), "recalled_exact": True})
        failed = target.exec("python3 -c 'import sys; print(\"failed assertion context\\n\"*400); sys.exit(1)'", timeout=10)
        store = ToolOutput(folder / "negative-output", target, "digest")
        output = {"output": failed["stdout"] + failed["stderr"], "returncode": failed["returncode"], "exception_info": ""}
        shown, = store.project({"extra": {"actions": [{"command": "actual failing subprocess"}]}}, [output])
        assert shown["returncode"] == 1 and output["output"] in shown["output"]
        recalled, = store.project({"extra": {"actions": [{"command": "cat /course-tool-output/output-0001.txt"}]}}, [output])
        assert recalled == output
        short = output | {"output": "short observation", "returncode": 0}
        assert store.project(message, [short]) == [short]
    result = {"status": "PASS", "type": "actual archived-output replay and real container IO; not model validation",
        "source_tool_log_sha256": hashlib.sha256(source.read_bytes()).hexdigest(), "replay": results,
        "real_failed_subprocess_preserved": True, "recall_not_recompressed": True,
        "short_unchanged": True, "actual_environment_probe": True, "new_model_calls": 0,
        "docker_endpoint": os.environ["DOCKER_HOST"], "platform": platform}
    (folder / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
