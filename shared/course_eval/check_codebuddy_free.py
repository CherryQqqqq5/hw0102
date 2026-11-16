import copy
import json
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

    def model(self):
        directory = Path(tempfile.mkdtemp(prefix="response-replay-", dir=self.root))
        return CodeBuddyModel(directory, RunLimits(), "{{output}}")

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


if __name__ == "__main__":
    unittest.main()
