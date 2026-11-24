"""Offline regression checks for verdict isolation, escalation and failed judge calls."""

import os
import unittest
from unittest.mock import patch

from calibrate_turns import grade, subscription_available


class CalibrationTests(unittest.TestCase):
    """Verify the exact input boundary used for the real subscription grader."""

    def setUp(self):
        """Prepare one fully fictional answered example with private reference metadata."""
        self.case = dict(context="No prior report", user_prompt="Can you check?",
                         expected_behavior="Ask which plan", sample_reply="Which plan?",
                         evidence=[], tool_trace=[], reference_label="SECRET-LABEL",
                         reference_reason="SECRET-REASON")

    def test_grade_excludes_reference_and_escalates(self):
        """A low-confidence first vote must escalate without exposing the answer key."""
        def respond(prompt, schema, model):
            """Return opposite votes from the two model tiers."""
            self.assertNotIn("SECRET", prompt)
            return {"pass": model == "sonnet", "confidence": 0.9 if model == "sonnet" else 0.3,
                    "reason": "Fixture verdict"}
        result = grade(self.case, respond)
        self.assertEqual(("pass", "sonnet"), (result["verdict"], result["model"]))
        self.assertEqual(2, len(result["trace"]["judgeCalls"]))

    def test_alternate_credentials_are_blocked(self):
        """An API key or provider override cannot authorize a subscription calibration run."""
        for key in ("ANTHROPIC_API_KEY", "CLAUDE_CODE_USE_BEDROCK", "ANTHROPIC_BASE_URL"):
            with patch.dict(os.environ, {key: "fictional"}, clear=True):
                self.assertFalse(subscription_available())

    def test_invalid_results_fail_closed(self):
        """String booleans from a malformed grader must never become passing verdicts."""
        result = grade(self.case, lambda *_: {"pass": "false", "confidence": 1, "reason": "x"})
        self.assertEqual("error", result["verdict"])


if __name__ == "__main__":
    unittest.main()
