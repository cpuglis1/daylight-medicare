"""Offline checks for live grading isolation from authored labels and mock evidence."""
import unittest

from score_observations import score_trial


class LiveScoringTests(unittest.TestCase):
    """Check the boundary between generated observations and saved calibration examples."""

    def test_only_real_output_reaches_grader(self):
        """Send the generated follow-up and actual tool result, hiding the saved answer key."""
        case = dict(context="Existing visit", user_prompt="Pause", expected_behavior="Honor pause",
                    evidence=[], reference_label="SECRET", sample_reply="SECRET", tool_trace=["SECRET"])
        row = dict(reply="Okay", nextQuestion={"question":"Why?"}, rawLineHash="1", status="observed",
                   trace={"message":"Pause", "toolCalls":["ACTUAL"]})
        def grader(payload):
            """Capture the exact answer and return a deliberately failing grade."""
            self.assertNotIn("SECRET", str(payload))
            self.assertIn("Why?", payload["sample_reply"])
            self.assertEqual(["ACTUAL"], payload["tool_trace"]["observedToolCalls"])
            return dict(verdict="fail", reason="Asked why", model="offline", confidence=1)
        self.assertEqual("fail", score_trial(row, case, "1", grader)["verdict"])

    def test_stale_fixture_is_unscored(self):
        """A different hash must never reach the subscription model."""
        self.assertEqual("unscored", score_trial({"rawLineHash":"old"}, {}, "new")["verdict"])
