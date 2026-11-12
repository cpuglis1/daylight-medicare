import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from chat import ResponsesClient
from usage_metrics import CURRENT, TurnUsage


class UsageTests(unittest.TestCase):
    def test_multiple_calls_charge_cached_input_once_and_reasoning_as_output(self):
        response = {"usage": {"input_tokens": 1000, "input_tokens_details": {"cached_tokens": 800},
                              "output_tokens": 100, "output_tokens_details": {"reasoning_tokens": 20}}}
        client = ResponsesClient(key="test", model="gpt-5.4", transport=lambda payload: response)
        with TurnUsage(client.model) as usage:
            client.create([])
            client.create([])
            with self.assertLogs("milkman.usage") as captured:
                result = usage.finish({"tool_calls": ["education"], "_retry_count": 1})
        self.assertEqual(result["model_calls"], 2)
        self.assertEqual(result["cached_input_tokens"], 1600)
        self.assertEqual(result["reasoning_tokens"], 40)
        self.assertAlmostEqual(result["estimated_cost_usd"], .0044)
        self.assertEqual(result["retry_count"], 1)
        self.assertNotIn("test", json.dumps(result))
        self.assertEqual(len(captured.output), 1)
        self.assertIsNone(CURRENT.get())

    def test_request_contexts_do_not_mix(self):
        with TurnUsage("gpt-5.4") as first:
            with TurnUsage("gpt-5.4-mini") as second:
                self.assertIs(CURRENT.get(), second)
            self.assertIs(CURRENT.get(), first)

    def test_unknown_rates_do_not_invent_free_usage(self):
        with TurnUsage("unknown") as usage:
            self.assertIsNone(usage.value["estimated_cost_usd"])


if __name__ == "__main__":
    unittest.main()
