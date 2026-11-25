import copy
import json
import unittest
from pathlib import Path

from pydantic import ValidationError

from course_eval.openrouter_free import available_free_requests, recorded_free_requests, verify_free_receipt


class ActualOpenRouterReceiptChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path("work/vmshare/performance-native-free-v2/extract-elf-Ling-B0-r1")
        events = [json.loads(line) for line in next(root.rglob("model.jsonl")).read_text().splitlines()]
        cls.actual = next(event["payload"] for event in events if event["event"] == "response")
        cls.rejected = json.loads(next(event["body"] for event in events if event["event"] == "request_error"))
        cls.model = "inclusionai/ling-3.2-flash:free"
        cls.account = json.loads(Path("work/openrouter-receipt-followup-20261122.json").read_text())["account_totals"]

    def test_actual_account_quota(self):
        self.assertEqual(available_free_requests(self.account), 49)

    def test_zero_quota_boundary(self):
        value = copy.deepcopy(self.account)
        value["free_model_daily_requests"]["remaining"] = 0
        self.assertEqual(available_free_requests(value), 0)

    def test_lagging_remote_quota_uses_actual_local_count(self):
        self.assertEqual(available_free_requests(self.account, 50), 0)
        self.assertEqual(available_free_requests(self.account, 49), 1)

    def test_actual_saved_daily_requests_include_unknowns(self):
        count = recorded_free_requests(Path("work/vmshare"), "2026-11-22")
        self.assertEqual(count, 56)
        self.assertEqual(available_free_requests(self.account, count), 0)

    def test_unknown_quota_rejected(self):
        value = copy.deepcopy(self.account)
        del value["free_model_daily_requests"]["remaining"]
        with self.assertRaises(ValidationError):
            available_free_requests(value)

    def test_actual_zero_receipt(self):
        self.assertEqual(verify_free_receipt(self.actual, self.model, 64000).usage.cost, 0)

    def test_actual_429_is_not_zero_cost_evidence(self):
        with self.assertRaises(ValidationError):
            verify_free_receipt(self.rejected, self.model, 64000)

    def test_missing_cost_rejected(self):
        value = copy.deepcopy(self.actual)
        del value["usage"]["cost"]
        with self.assertRaises(ValidationError):
            verify_free_receipt(value, self.model, 64000)

    def test_nonzero_cost_rejected(self):
        value = copy.deepcopy(self.actual)
        value["usage"]["cost"] = 0.001
        with self.assertRaises(ValidationError):
            verify_free_receipt(value, self.model, 64000)

    def test_boolean_cost_rejected(self):
        value = copy.deepcopy(self.actual)
        value["usage"]["cost"] = False
        with self.assertRaises(ValidationError):
            verify_free_receipt(value, self.model, 64000)

    def test_different_model_rejected(self):
        with self.assertRaises(ValueError):
            verify_free_receipt(self.actual, "nvidia/nemotron-3-ultra-550b-a55b:free", 64000)


if __name__ == "__main__":
    unittest.main()
