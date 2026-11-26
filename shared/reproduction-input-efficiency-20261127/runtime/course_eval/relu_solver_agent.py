import asyncio
import hashlib
import json
from pathlib import Path

from course_eval.harbor_agent import CourseMiniSweAgent, make_harbor_target


class ReluSolverAgent(CourseMiniSweAgent):
    @staticmethod
    def name():
        return "course-deterministic-relu-directions"

    def version(self):
        return "query-only-helper-v1"

    async def run(self, instruction, environment, context):
        required = ("The input dimension is 10", "forward(x)", "/app/steal.py", "/app/stolen_A1.npy")
        if not all(text in instruction for text in required):
            raise ValueError("This component validation is restricted to the stated public ReLU task")
        target = await make_harbor_target(environment)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        source = Path(__file__).with_name("relu_recovery.py")
        program = self.logs_dir / "steal.py"
        program.write_text(source.read_text() + '\n\nif __name__ == "__main__":\n'
            '    import json\n'
            '    from forward import forward\n'
            '    rows, diagnostics = recover_relu_directions(forward, 10)\n'
            '    np.save("/app/stolen_A1.npy", rows, allow_pickle=False)\n'
            '    print(json.dumps(diagnostics))\n')
        original = await asyncio.to_thread(target.exec, "sha256sum /app/forward.py", timeout=10)
        if original["returncode"]:
            raise RuntimeError("The public oracle module is unavailable")
        await asyncio.to_thread(target.upload_file, program.resolve(), "/app/steal.py")
        output = await asyncio.to_thread(target.exec, "python3 /app/steal.py", timeout=120)
        unchanged = await asyncio.to_thread(target.exec, "sha256sum /app/forward.py", timeout=10)
        if original != unchanged:
            raise RuntimeError("The public oracle module changed during numerical recovery")
        record = {"new_model_calls": 0, "independent_model_repeat": False,
            "scope": "Deterministic query-only component on the original task; not an agent success",
            "library_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            "delivered_script_sha256": hashlib.sha256(program.read_bytes()).hexdigest(),
            "oracle_module_unchanged": True, "input_dimension_source": "Original public task statement",
            "unknown_width_or_weights_supplied": False, "execution": output}
        (self.logs_dir / "component.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n")
        if output["returncode"]:
            raise RuntimeError("The numerical helper failed; preserve its actual output")
        context.n_input_tokens = 0
        context.n_output_tokens = 0
        context.cost_usd = 0
