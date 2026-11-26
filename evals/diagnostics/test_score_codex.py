"""Offline checks for Codex verdict handling and exact live receipt provenance."""

import io
import json
import unittest

from score_codex import MODEL, canonical_hash, load_receipts, parse_verdict, verify_receipts


class CodexScoreTests(unittest.TestCase):
    """Exercise fail-closed behavior along the live score artifact path."""

    def test_tool_event_invalidates_valid_verdict(self):
        """Reject a tool event even when the otherwise valid structured verdict passes."""
        message = {"type": "item.completed", "item": {
            "type": "agent_message",
            "text": '{"pass":true,"confidence":1,"reason":"The reply confirms the pause."}',
        }}
        end = {"type": "turn.completed"}
        self.assertEqual("pass", parse_verdict("\n".join(map(json.dumps, (message, end))))["verdict"])
        command = {"type": "item.completed", "item": {"type": "command_execution"}}
        with self.assertRaises(ValueError):
            parse_verdict("\n".join(map(json.dumps, (command, message, end))))

    def test_resume_discards_only_interrupted_receipt_line(self):
        """Preserve complete receipt lines and remove an unfinished final write."""
        receipt = {"stamp": "1", "rowHash": "a", "score": {"caseId": "a-1", "trial": 1}}
        complete = json.dumps(receipt).encode() + b"\n"
        handle = io.BytesIO(complete + b'{"stamp"')
        self.assertEqual({("a-1", 1): receipt}, load_receipts(handle, "1"))
        self.assertEqual(complete, handle.getvalue())
        with self.assertRaises(ValueError):
            load_receipts(handle, "changed")

    def test_changed_final_observation_cannot_keep_pass(self):
        """Bind the verdict to the exact observed reply, case hash and authorized trial."""
        row = {"caseId": "a-1", "trial": 1, "rawLineHash": "case-version", "status": "observed",
               "reply": "Okay, let's stop."}
        score = {"caseId": "a-1", "trial": 1, "suite": "question_timing", "split": "heldout",
                 "verdict": "pass", "model": MODEL, "confidence": 1}
        receipts = {("a-1", 1): {"score": score, "rowHash": canonical_hash(row)}}
        expected = [("a-1", 1)]
        cases = {"a-1": ({"judge": "question_timing", "split": "heldout"}, "case-version")}
        self.assertEqual([score], verify_receipts([row], receipts, expected, cases))
        with self.assertRaises(ValueError):
            verify_receipts([{**row, "reply": "Why do you want to stop?"}], receipts, expected, cases)
        with self.assertRaises(ValueError):
            verify_receipts([row], receipts, [], cases)


if __name__ == "__main__":
    unittest.main()
