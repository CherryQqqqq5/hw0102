import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import unittest
from zipfile import ZipFile


ROOT = Path.cwd().resolve()
FOLDER = Path(__file__).resolve().parent
RUNTIME = ROOT / "work/frozen-performance-hy4-submit-boundary-v20"
os.environ.setdefault("MSWEA_GLOBAL_CONFIG_DIR", str(ROOT / "work/miniswe-config"))
os.environ.setdefault("MSWEA_SILENT_STARTUP", "1")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(RUNTIME))
from minisweagent.exceptions import Submitted
from course_eval.agent import RunLimits
from course_eval.controller import Budget, ControlledEnvironment
from course_eval.verification import PublicCheck


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def old_action(lane, request):
    repeat = 1 if lane == "main" else 2
    run = ROOT / f"work/vmshare/performance75-hy4-sql-layout-v18-{lane}-20261125/model-extraction-relu-logits-C0-r{repeat}"
    trace, = run.rglob("model.jsonl")
    for line in trace.open():
        event = json.loads(line)
        if event["event"] == "response" and event["request_id"] == request:
            return next(row["structured_output"] for row in reversed(event["payload"]) if row.get("type") == "result")
    raise ValueError("The actual old structured action was not found")


class LocalTarget:
    def __init__(self, folder):
        self.cwd = str(folder)
        self.payload = folder / ".course-controller-input.json"
        self.system_info = {"system": "Darwin", "cwd": self.cwd, "fixture": "actual local subprocess,not a container"}
        self.commands = []

    def upload_file(self, source, destination, *, timeout=20):
        if destination != "/.course-controller-input.json":
            raise ValueError("Only the real CandidateStore transport input is mapped locally")
        shutil.copyfile(source, self.payload)

    def exec(self, command, *, cwd="", timeout):
        self.commands.append(command)
        mapped = command.replace("/.course-controller-input.json", shlex.quote(str(self.payload)))
        mapped = mapped.replace("/usr/bin/sha256sum", "/sbin/sha256sum")
        result = subprocess.run(["/bin/bash", "-c", mapped], cwd=cwd or self.cwd,
            env=os.environ | {"PYTHONDONTWRITEBYTECODE": "1"}, capture_output=True, text=True, timeout=timeout)
        return {"stdout": result.stdout, "stderr": result.stderr, "returncode": result.returncode}


class LocalChecks(unittest.TestCase):
    def setUp(self):
        self.folder = PHASE / self._testMethodName
        self.folder.mkdir()
        fixture, logs = self.folder / "fixture", self.folder / "logs"
        fixture.mkdir()
        logs.mkdir()
        (fixture / "artifact.txt").write_text("ready")
        (fixture / "forward.py").write_text("# Self-authored local fixture; no original model weights.\n")
        self.target = LocalTarget(fixture)
        checker = shlex.join((sys.executable, "-c", "from pathlib import Path; assert Path('artifact.txt').read_text() == 'ready'; print('actual-file-check-passed')"))
        self.check = PublicCheck("public-query-directions", "local public file contract", checker,
            ("artifact.txt", "forward.py"))
        self.scope = {"kind": "files", "artifacts": ["artifact.txt"], "protected": ["forward.py"], "python": sys.executable}
        self.logs = logs

    def environment(self, *, enabled=False, scope=None):
        return ControlledEnvironment(self.target, self.logs, RunLimits(wall_seconds=90, command_seconds=20),
            (self.check,), scope or self.scope, Budget(90), enabled)

    def test_actual_main_submit_requires_registered_current_check(self):
        env = self.environment()
        try:
            reply = env.execute(old_action("main", 10))
        except Submitted:
            self.fail("Actual main step10 incorrectly finalized while the registered check is pending")
        self.assertIn('"submission_rejected": true', reply["output"])
        self.assertIn("public-query-directions", reply["output"])
        self.assertIsNone(env.final_report)
        self.assertFalse((self.logs / "final-verification.json").exists())

    def test_rejected_main_can_continue_with_actual_repeat_verify_save(self):
        env = self.environment()
        env.execute(old_action("main", 10))
        self.assertEqual(env.before_decision(100), "")
        checked = env.execute(old_action("repeat", 4))
        self.assertIn('"state": "passed"', checked["output"])
        saved = env.execute(old_action("repeat", 5))
        self.assertIn('"eligible": true', saved["output"])
        with self.assertRaises(Submitted):
            env.execute(old_action("repeat", 7))
        self.assertTrue(env.final_report["valid_verification"])
        events = [json.loads(line) for line in (self.logs / "controller.jsonl").read_text().splitlines()]
        checks = [e for e in events if e["event"] == "verification"]
        self.assertEqual([e["reason"] for e in checks], ["requested"])

    def test_failed_stale_and_protected_checks_reject_submission(self):
        env = self.environment()
        artifact = Path(self.target.cwd) / "artifact.txt"
        artifact.write_text("broken")
        self.assertEqual(env.verify(self.check.check_id, "requested")["state"], "failed")
        self.assertIn('"state": "failed"', env.execute(old_action("main", 10))["output"])
        artifact.write_text("ready")
        env.verify(self.check.check_id, "requested")
        artifact.write_text("changed after verify")
        self.assertIn('"state": "stale"', env.execute(old_action("main", 10))["output"])
        artifact.write_text("ready")
        env.verify(self.check.check_id, "requested")
        (Path(self.target.cwd) / "forward.py").write_text("# protected dependency changed\n")
        self.assertIn("protected_dependency_changed", env.execute(old_action("main", 10))["output"])
        self.assertIsNone(env.final_report)

    def test_C1_retains_automatic_verification_and_recovery(self):
        env = self.environment(enabled=True)
        self.assertEqual(env.verify(self.check.check_id, "requested")["state"], "passed")
        (Path(self.target.cwd) / "artifact.txt").write_text("broken after feasible version")
        with self.assertRaises(Submitted):
            env.execute(old_action("main", 10))
        self.assertTrue(env.final_report["valid_verification"])
        self.assertEqual(env.final_report["restored_candidate"], "candidate-001")
        self.assertEqual((Path(self.target.cwd) / "artifact.txt").read_text(), "ready")

    def test_actual_oracle_read_is_rejected_before_local_process(self):
        env = self.environment(scope=self.scope | {"reusable_helper": "relu_directions"})
        before = len(self.target.commands)
        reply = env.execute(old_action("main", 2))
        self.assertIn("oracle_access_rejected", reply["output"])
        self.assertEqual(len(self.target.commands), before)

    def test_nearby_oracle_reads_are_blocked_and_repeat_commands_remain_allowed(self):
        from course_eval.oracle_access import rejection_reason

        env = self.environment(scope=self.scope | {"reusable_helper": "relu_directions"})
        blocked = ["sed -n '1,80p' /app/forward.py", "head forward.py", "cat *.py",
            "python -c \"from pathlib import Path;print(Path('forward.py').read_text())\"",
            "python -c \"import forward as f;print(f.A1)\"",
            "python -c \"import forward;print(getattr(forward, 'A1'))\"",
            "python -c \"import inspect;from forward import forward;print(inspect.getsource(forward))\"",
            "python -c \"import forward;print(vars(forward))\"",
            "python -c \"from forward import forward;print(forward.__globals__)\""]
        before = len(self.target.commands)
        for command in blocked:
            reply = env.execute({"operation": "bash", "command": command})
            self.assertIn("oracle_access_rejected", reply["output"], command)
        self.assertEqual(len(self.target.commands), before)
        for step in (1, 2, 3, 6, 7):
            self.assertIsNone(rejection_reason(old_action("repeat", step)["command"]))
        self.assertIsNone(rejection_reason("python3 /opt/course-tools/relu_export.py --dimension 10 --oracle-module forward --oracle-function forward --output /app/steal.py"))

    def test_non_relu_read_and_verified_submit_match_original_v18(self):
        import importlib.util

        env = self.environment()
        reply = env.execute(old_action("main", 2))
        self.assertEqual(reply["returncode"], 0)
        self.assertIn("Self-authored local fixture", reply["output"])
        spec = importlib.util.spec_from_file_location("unchanged_v18_controller", ROOT / "work/frozen-performance-hy4-sql-layout-v18/course_eval/controller.py")
        original = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(original)
        versions = []
        for label, kind in (("v18", original.ControlledEnvironment), ("v20", ControlledEnvironment)):
            logs = self.folder / label
            logs.mkdir()
            active = kind(self.target, logs, RunLimits(wall_seconds=90, command_seconds=20),
                (self.check,), self.scope, Budget(90), False)
            active.execute(old_action("repeat", 4))
            active.execute(old_action("repeat", 5))
            with self.assertRaises(Submitted):
                active.execute(old_action("main", 10))
            versions.append({key: value for key, value in active.final_report.items() if key != "elapsed_seconds"})
        self.assertEqual(versions[0], versions[1])

    def test_public_helper_exports_and_runs_without_course_tools(self):
        fixture = Path(self.target.cwd)
        (fixture / "forward.py").write_text(
            "import numpy as np\nrng = np.random.default_rng(7341)\n"
            "weights = rng.normal(size=(3, 10))\nbias = rng.normal(size=3) * 0.1\n"
            "coefficients = np.array([0.5, -0.7, 1.3])\n"
            "def forward(x):\n    return float(coefficients @ np.maximum(0, weights @ np.asarray(x) + bias) + 0.12)\n")
        output = fixture / "steal.py"
        exported = subprocess.run([sys.executable, str(RUNTIME / "course_eval/relu_export.py"),
            "--dimension", "10", "--oracle-module", "forward", "--oracle-function", "forward",
            "--output", str(output)], capture_output=True, text=True, timeout=20)
        self.assertEqual(exported.returncode, 0, exported.stderr)
        helper = RUNTIME / "course_eval/relu_recovery.py"
        self.assertTrue(output.read_bytes().startswith(helper.read_bytes()))
        self.assertNotIn("/opt/course-tools", output.read_text())
        executed = subprocess.run([sys.executable, str(output)], cwd=self.folder,
            capture_output=True, text=True, timeout=40)
        self.assertEqual(executed.returncode, 0, executed.stderr)
        import importlib.util
        import numpy as np

        spec = importlib.util.spec_from_file_location("fresh_synthetic_relu", fixture / "forward.py")
        oracle = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(oracle)
        from course_eval.relu_recovery import validate_saved_directions

        matrix = np.load(fixture / "stolen_A1.npy", allow_pickle=False)
        report = validate_saved_directions(oracle.forward, 10, matrix)
        self.assertTrue(report["passed"], report)
        self.assertEqual(report["actual_shape"], [3, 10])
        (self.folder / "synthetic-query-report.json").write_text(json.dumps(report, indent=2) + "\n")
        from course_eval.terminal_runtime import relu_check_command

        command = relu_check_command().replace("/app", str(fixture)).replace(
            "/opt/course-tools", str(RUNTIME / "course_eval")).replace("python3", shlex.quote(sys.executable))
        self.check = PublicCheck("public-query-directions", "self-authored local numerical oracle", command,
            ("steal.py", "stolen_A1.npy", "forward.py"))
        self.scope = {"kind": "files", "artifacts": ["steal.py", "stolen_A1.npy"],
            "protected": ["forward.py"], "python": sys.executable, "reusable_helper": "relu_directions"}
        env = self.environment()
        self.assertIn('"submission_rejected": true', env.execute(old_action("main", 10))["output"])
        checked = env.execute(old_action("repeat", 4))
        self.assertIn('"state": "passed"', checked["output"])
        env.execute(old_action("repeat", 5))
        with self.assertRaises(Submitted):
            env.execute(old_action("main", 10))
        self.assertTrue(env.final_report["valid_verification"])
        self.assertTrue(env.final_report["protected_unchanged"])

    def test_export_refuses_changed_public_helper(self):
        copied = Path(self.target.cwd)
        shutil.copyfile(RUNTIME / "course_eval/relu_export.py", copied / "relu_export.py")
        (copied / "relu_recovery.py").write_bytes((RUNTIME / "course_eval/relu_recovery.py").read_bytes() + b"\n# changed source\n")
        output = copied / "steal.py"
        result = subprocess.run([sys.executable, str(copied / "relu_export.py"), "--dimension", "10",
            "--oracle-module", "forward", "--oracle-function", "forward", "--output", str(output)],
            capture_output=True, text=True, timeout=10)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("immutable public numerical helper changed", result.stderr)
        self.assertFalse(output.exists())


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", required=True)
    parser.add_argument("--case")
    args = parser.parse_args()
    PHASE = FOLDER / args.phase
    PHASE.mkdir(exist_ok=False)
    with ZipFile(PHASE / "source.zip", "w") as archive:
        archive.write(Path(__file__), "qualify_local.py")
        for name in ("controller.py", "terminal_runtime.py", "oracle_access.py", "relu_export.py"):
            source = RUNTIME / "course_eval" / name
            if source.exists():
                archive.write(source, name)
    suite = (unittest.defaultTestLoader.loadTestsFromName("LocalChecks." + args.case, sys.modules[__name__])
        if args.case else unittest.defaultTestLoader.loadTestsFromTestCase(LocalChecks))
    with (PHASE / "test.log").open("w") as stream:
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    record = {"unit_checks_passed": result.wasSuccessful(), "unit_tests_run": result.testsRun,
        "failures": len(result.failures), "errors": len(result.errors), "driver_sha256": sha(Path(__file__)),
        "source_zip_sha256": sha(PHASE / "source.zip"), "log_sha256": sha(PHASE / "test.log"),
        "scope": "Real local Python/bash/CandidateStore/VerificationState operations;no Docker or original grader and no mocked successful output.",
        "new_model_calls": 0, "new_original_grader_calls": 0, "new_VM_calls": 0}
    (PHASE / "result.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(record))
    raise SystemExit(0 if result.wasSuccessful() else 1)
