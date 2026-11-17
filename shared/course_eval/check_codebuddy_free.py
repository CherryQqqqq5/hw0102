import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from minisweagent.exceptions import FormatError, TimeExceeded

from course_eval.agent import CodeBuddyModel, RunLimits
from course_eval.codebuddy_free import verify_free_response
from course_eval.controller import Budget
from course_eval.export_revision import sanitize_model


class FreeResponseChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path("work/codebuddy-quota-probe")
        cls.free = json.loads((cls.root / "hy4flash-free-smoke-exactroute.stdout.json").read_text())
        cls.paid = json.loads((cls.root / "hy4free-smoke-bundledca.stdout.json").read_text())
        cls.truncated = json.loads((cls.root / "hy4flash-output-cap-4096-v1/events.json").read_text())
        paths = list(Path("work/vmshare/confirmation-hy4flash-free-v3").rglob("model.jsonl"))
        path, = paths
        events = [json.loads(line) for line in path.read_text().splitlines()]
        cls.recovered, = [event["payload"] for event in events
                         if event["event"] == "response" and event["request_id"] == 2]
        path, = Path("work/vmshare/confirmation-hy4flash-free-v4").rglob("model.jsonl")
        events = [json.loads(line) for line in path.read_text().splitlines()]
        cls.tool_recovered, = [event["payload"] for event in events
                              if event["event"] == "response" and event["request_id"] == 6]
        path = Path("work/vmshare/confirmation-hy4flash-free-v6/C-swe-django__django-11999-B0-r1/model.jsonl")
        events = [json.loads(line) for line in path.read_text().splitlines()]
        cls.spaced_tool_recovered, = [event["payload"] for event in events
                                     if event["event"] == "response" and event["request_id"] == 14]

    def model(self):
        directory = Path(tempfile.mkdtemp(prefix="response-replay-", dir=self.root))
        return CodeBuddyModel(directory, RunLimits(), "{{output}}")

    def test_cli_child_preserves_existing_proxy_and_free_route(self):
        model = self.model()
        environment = model.process_environment()
        proxy_keys = [key for key in os.environ if key.lower() in {"http_proxy", "https_proxy", "all_proxy", "no_proxy"}]
        self.assertTrue(proxy_keys)
        for key in proxy_keys:
            self.assertEqual(environment[key], os.environ[key])
        self.assertEqual(environment["CODEBUDDY_DISABLE_PROXY_CONFIG_FILE"], "1")
        self.assertNotIn("WORKBUDDY_PROXY_SOURCE", environment)
        for key in ("CODEBUDDY_MODEL", "CODEBUDDY_SMALL_FAST_MODEL", "CODEBUDDY_BIG_SLOW_MODEL"):
            self.assertEqual(environment[key], "hy4flash-free")
        self.assertEqual(environment["CODEBUDDY_CODE_MAX_OUTPUT_TOKENS"], "4096")
        self.assertNotIn("CODEBUDDY_FALLBACK_MODEL", environment)
        child = subprocess.run(["node", "-e", "process.stdout.write(JSON.stringify({proxy:!!process.env.HTTPS_PROXY,source:process.env.WORKBUDDY_PROXY_SOURCE??null,configDisabled:process.env.CODEBUDDY_DISABLE_PROXY_CONFIG_FILE}))"],
                               env=environment, capture_output=True, text=True, check=True)
        self.assertEqual(json.loads(child.stdout), {"proxy": True, "source": None, "configDisabled": "1"})

    def test_real_zero_exit_dns_failure_keeps_billing_unknown(self):
        path, = Path("work/vmshare/confirmation-hy4flash-free-v5/C-swe-django__django-11999-B0-r1").rglob("model.jsonl")
        events = [json.loads(line) for line in path.read_text().splitlines()]
        error, = [event for event in events if event["event"] == "request_error"]
        process = subprocess.CompletedProcess(["codebuddy"], error["returncode"], error["stdout"], error["stderr"])
        model = self.model()
        model.request_id = error["request_id"]
        with self.assertRaisesRegex(RuntimeError, "DNS.*unknown"):
            model.process_completed_process(process, 1)
        replay = [json.loads(line) for line in model.trace.read_text().splitlines()]
        self.assertEqual([event["event"] for event in replay], ["request_error"])
        self.assertEqual(replay[0]["failure_category"], "dns_resolution")
        self.assertEqual(replay[0]["billing_status"], "unknown")
        exported = json.loads(sanitize_model(model.trace.read_text()))
        self.assertEqual(exported["billing_status"], "unknown")
        self.assertEqual(exported["diagnostic"]["category"], "name_resolution")

    def test_real_recovered_response_and_action(self):
        proof = verify_free_response(self.recovered)
        self.assertEqual(proof["credit"], 0)
        self.assertEqual(proof["usage_records"], 2)
        self.assertEqual(len(proof["local_cli_errors"]), 1)
        result = self.model().process_response(self.recovered)
        final, = [item for item in self.recovered if item.get("type") == "result"]
        action, = result["extra"]["actions"]
        self.assertEqual(action["command"], final["structured_output"]["command"])

    def test_real_truncation_without_action_is_format_error(self):
        proof = verify_free_response(self.truncated)
        self.assertEqual(proof["usage_records"], 3)
        with self.assertRaises(FormatError):
            self.model().process_response(self.truncated)

    def test_real_local_tool_error_recovers_after_model_billing(self):
        for payload in (self.tool_recovered, json.loads(sanitize_model(json.dumps({"event": "response", "payload": self.tool_recovered})))["payload"]):
            proof = verify_free_response(payload)
            self.assertEqual(proof["credit"], 0)
            self.assertEqual(proof["usage_records"], 3)
            self.assertEqual(len(proof["local_cli_errors"]), 2)
            self.model().process_response(payload)

    def test_tool_error_cannot_cover_nonzero_or_unknown_model_billing(self):
        for change in ("credit", "missing", "network", "message"):
            modified = copy.deepcopy(self.tool_recovered)
            billed = next(item for item in modified if "rawUsage" in item.get("providerData", {}))
            local = next(item for item in modified if item.get("providerData", {}).get("error", {}).get("isRetryable"))
            if change == "credit":
                billed["providerData"]["rawUsage"]["credit"] = 1.0
            elif change == "missing":
                del billed["providerData"]["rawUsage"]
            elif change == "network":
                local["providerData"]["error"]["isNetworkError"] = True
            else:
                local["providerData"]["error"]["message"] = "Unrecognized provider failure"
            with self.subTest(change=change), self.assertRaises(ValueError):
                verify_free_response(modified)

    def test_real_spaced_tool_name_keeps_independent_billing(self):
        for payload in (self.spaced_tool_recovered, json.loads(sanitize_model(json.dumps({
                "event": "response", "payload": self.spaced_tool_recovered})))["payload"]):
            proof = verify_free_response(payload)
            self.assertEqual(proof["usage_records"], 3)
            self.assertEqual(len(proof["local_cli_errors"]), 2)
            self.assertEqual(len({error["model_message_id"] for error in proof["local_cli_errors"]}), 2)
            self.model().process_response(payload)

    def test_spaced_tool_name_cannot_weaken_model_receipts(self):
        for change in ("credit", "missing", "message", "model", "network"):
            modified = copy.deepcopy(self.spaced_tool_recovered)
            billed = [item for item in modified if "rawUsage" in item.get("providerData", {})][-1]
            if change == "credit":
                billed["providerData"]["rawUsage"]["credit"] = 0.1
            elif change == "missing":
                del billed["providerData"]["rawUsage"]
            elif change == "message":
                billed["providerData"]["messageId"] = "unrelated-message"
            elif change == "model":
                billed["providerData"]["model"] = "hy4-flash"
            else:
                local = [item for item in modified if item.get("providerData", {}).get("skipRun")][-1]
                local["providerData"]["error"]["isNetworkError"] = True
            with self.subTest(change=change), self.assertRaises(ValueError):
                verify_free_response(modified)

    def test_each_local_error_requires_its_own_prior_usage(self):
        modified = copy.deepcopy(self.tool_recovered)
        index = next(index for index, item in enumerate(modified)
                     if item.get("providerData", {}).get("error", {}).get("isRetryable"))
        self.assertEqual(modified[index - 1]["type"], "model-usage")
        del modified[index - 1]
        for payload in (modified, json.loads(sanitize_model(json.dumps({"event": "response", "payload": modified})))["payload"]):
            with self.assertRaises(ValueError):
                verify_free_response(payload)

    def test_insufficient_remaining_request_window_makes_no_call(self):
        model = self.model()
        model.budget = Budget(5)
        with self.assertRaises(TimeExceeded):
            model.query([{"role": "system", "content": "Unused"}, {"role": "user", "content": "Unused"}])
        self.assertFalse(model.trace.exists())

    def test_paid_and_missing_billing_still_stop(self):
        with self.assertRaises(ValueError):
            verify_free_response(self.paid)
        modified = copy.deepcopy(self.recovered)
        billed = next(item for item in modified if "rawUsage" in item.get("providerData", {}))
        del billed["providerData"]["rawUsage"]
        with self.assertRaises(ValueError):
            verify_free_response(modified)
        with self.assertRaises(ValueError):
            verify_free_response([])

    def test_local_error_cannot_hide_real_billing(self):
        for field, value in (("credit", 0.1), ("credit", False)):
            modified = copy.deepcopy(self.recovered)
            billed = next(item for item in modified if "rawUsage" in item.get("providerData", {}))
            billed["providerData"]["rawUsage"][field] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                verify_free_response(modified)

    def test_unbilled_usage_event_is_preserved_and_rejected(self):
        modified = copy.deepcopy(self.recovered)
        usage = next(item for item in modified if item.get("type") == "model-usage")
        usage["providerData"] = {}
        for payload in (modified, json.loads(sanitize_model(json.dumps({"event": "response", "payload": modified})))["payload"]):
            with self.assertRaises(ValueError):
                verify_free_response(payload)
        modified = copy.deepcopy(self.recovered)
        usage = next(item for item in modified if item.get("type") == "model-usage")
        del usage["providerData"]["rawUsage"]
        with self.assertRaises(ValueError):
            verify_free_response(modified)

    def test_unknown_or_unrelated_local_error_stops(self):
        for change in ("network", "context", "model", "status"):
            modified = copy.deepcopy(self.recovered)
            local = next(item for item in modified if item.get("providerData", {}).get("skipRun"))
            if change == "network":
                local["providerData"]["error"]["isNetworkError"] = True
            elif change == "context":
                local["providerData"]["conversationRequestId"] = "unrelated-request"
            elif change == "model":
                local["providerData"]["model"] = "hy4"
            else:
                local["status"] = "completed"
            with self.subTest(change=change), self.assertRaises(ValueError):
                verify_free_response(modified)

    def test_recovery_rejects_mismatched_structured_action(self):
        modified = copy.deepcopy(self.recovered)
        final, = [item for item in modified if item.get("type") == "result"]
        final["structured_output"] = {"command": "printf mismatched"}
        with self.assertRaises(FormatError):
            self.model().process_response(modified)

    def test_export_preserves_real_provider_and_local_events(self):
        for payload in (self.recovered, self.truncated):
            original = verify_free_response(payload)
            exported = json.loads(sanitize_model(json.dumps({"event": "response", "payload": payload})))["payload"]
            self.assertEqual(verify_free_response(exported), original)
        exported = json.loads(sanitize_model(json.dumps({"event": "response", "payload": self.recovered})))["payload"]
        self.model().process_response(exported)

    def test_timeout_log_keeps_processes_and_billing_separate(self):
        path = Path("evals/regression_cases/codebuddy-timeout-before-first-chunk.log")
        failed = CodeBuddyModel.inspect_cli_log(path, 92775)
        self.assertEqual(failed["stage"], "awaiting_first_stream_chunk")
        self.assertEqual(failed["model_requests_sent"], 1)
        self.assertEqual(failed["first_raw_chunks"], 0)
        self.assertEqual(failed["event_loop_ticks"], 1)
        completed = CodeBuddyModel.inspect_cli_log(path, 92565)
        self.assertEqual(completed["stage"], "model_stream_completed_before_cli_exit")
        for record in (failed, completed):
            self.assertEqual(record["billing_status"], "unknown")
            self.assertNotIn("credit", record)

    def test_pending_later_native_request_is_not_hidden_by_earlier_completion(self):
        model = self.model()
        source = Path("evals/regression_cases/codebuddy-timeout-before-first-chunk.log").read_text()
        # 真实日志的受控PID变体，覆盖同一CLI内前次完成、后次等待的情况。
        path = model.run_dir / "multiple-native.log"
        path.write_text(source.replace("pid=92775", "pid=92565"))
        record = model.inspect_cli_log(path, 92565)
        self.assertEqual(record["model_requests_sent"], 2)
        self.assertEqual(record["completed_streams"], 1)
        self.assertEqual(record["stage"], "awaiting_first_stream_chunk")

    def test_timeout_never_accepts_even_a_complete_recorded_zero_credit_payload(self):
        model = self.model()
        model.request_id = 1
        payload = (self.root / "hy4flash-free-smoke-exactroute.stdout.json").resolve()
        command = [sys.executable, "-c",
                   "import pathlib,sys,time; sys.stdin.read(); print(pathlib.Path(sys.argv[1]).read_text(),flush=True); time.sleep(2)",
                   str(payload)]
        with self.assertRaisesRegex(RuntimeError, "before billing could be verified"):
            model.request_with_timeout_recovery(
                lambda: model.run_cli(command, "recorded-payload transport regression", model.process_environment(), 0.5),
                {"model": "hy4flash-free"}, subprocess.TimeoutExpired, 0.5)
        events = [json.loads(line) for line in model.trace.read_text().splitlines()]
        self.assertEqual([item["event"] for item in events], ["request", "cli_process_started", "request_error"])
        error = events[-1]
        self.assertEqual(json.loads(error["stdout"]), self.free)
        self.assertEqual(error["provider_diagnostics"]["billing_status"], "unknown")
        exported = json.loads(sanitize_model(json.dumps(error)))
        self.assertEqual(exported["provider_diagnostics"], error["provider_diagnostics"])


if __name__ == "__main__":
    unittest.main()
