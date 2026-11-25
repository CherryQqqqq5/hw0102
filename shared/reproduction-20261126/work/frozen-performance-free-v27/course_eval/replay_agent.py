import asyncio
import json
import os
import time
from pathlib import Path

from course_eval.agent import BashArguments
from course_eval.harbor_agent import CourseMiniSweAgent, HarborTarget


def replay_completed_actions(target, source: Path, log_path: Path, *, wall_seconds: int = 600) -> int:
    rows = [json.loads(line) for line in (source / "tools.jsonl").read_text().splitlines()]
    commands = [(index, BashArguments.model_validate({"command": row["command"]}).command)
                for index, row in enumerate(rows) if row["event"] == "bash"]
    if not commands:
        raise ValueError("No completed real model actions are available to recover")
    started = time.monotonic()
    with log_path.open("x") as log:
        for index, command in commands:
            remaining = wall_seconds - (time.monotonic() - started)
            if remaining < 1:
                raise TimeoutError(f"Recorded-action recovery exceeded {wall_seconds} seconds")
            output = target.exec(command, timeout=min(120, int(remaining)))
            log.write(json.dumps({"source_action_index": index, "command": command, **output},
                                 ensure_ascii=False) + "\n")
            log.flush()
    return len(commands)


class RecordedActionReplayAgent(CourseMiniSweAgent):
    @staticmethod
    def name() -> str:
        return "course-recorded-candidate-recovery"

    async def run(self, instruction, environment, context):
        source = Path(os.environ["COURSE_REPLAY_SOURCE"])
        if (source / "instruction.txt").read_text() != instruction:
            raise ValueError("The recovery task differs from the original model-visible instruction")
        identity = await environment.exec("pwd; uname -s; uname -r; uname -v; uname -m", timeout_sec=20)
        fields = (identity.stdout or "").splitlines()
        if identity.return_code or len(fields) != 5:
            raise RuntimeError("Cannot identify the recovery sandbox")
        info = dict(zip(("system", "release", "version", "machine"), fields[1:], strict=True))
        target = HarborTarget(environment, asyncio.get_running_loop(), fields[0], info)
        self.logs_dir.mkdir(parents=True, exist_ok=True)

        count = await asyncio.to_thread(replay_completed_actions, target, source,
                                        self.logs_dir / "replayed-tools.jsonl")
        (self.logs_dir / "recovery.json").write_text(json.dumps({
            "source_agent_directory": str(source), "completed_model_actions_reexecuted": count,
            "new_model_calls": 0, "scope": "Recover the original partial candidate for its original scorer; not an independent model run",
        }, ensure_ascii=False, indent=2) + "\n")
        context.n_input_tokens = 0
        context.n_output_tokens = 0
        context.cost_usd = 0
