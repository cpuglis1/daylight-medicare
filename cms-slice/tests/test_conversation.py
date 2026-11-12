"""Discovery continuity and model boundaries, without external services."""

import json
from pathlib import Path
import sys
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import cms_slice as cms
from chat import Chat, ResponsesClient
from conversation import Conversation
from research_http import make_research_test_server as make_server

PROFILE = {"recipient": "self", "zip": "34102", "medicare": "yes", "drugs": "yes", "hearing": "no", "vision": "yes", "dental": "unsure"}


class Sources:
    research_mode = True
    version = "test-snapshot"

    def coordination(self, messages):
        return {"coordination_flags": [], "coordination_facts": []}

    def education(self, topic):
        return {"facts": [{"id": topic, "text": "Immutable source text for " + topic, "evidence": []}]}


def model_response(value):
    return {"status": "completed", "output": [{"type": "message", "content": [{"type": "output_text", "text": json.dumps(value)}]}]}


class ConversationTests(unittest.TestCase):
    def setUp(self):
        self.chat = Chat(Sources(), ResponsesClient(key="", model=""))
        self.conversation = Conversation(self.chat)

    def test_first_turn_automatically_opens_with_paths_and_a_question(self):
        result = self.conversation.answer(PROFILE)
        self.assertEqual(result["topic"], "priorities")
        self.assertEqual([p["title"] for p in result["starter_options"]], ["Original Medicare", "Medicare Advantage"])
        self.assertEqual(result["starter_options"][0]["text"], "Immutable source text for basics")
        self.assertFalse(result["personal_recommendation"])
        self.assertEqual(result["conversation_mode"], "guided")

    def test_doctor_priority_changes_the_next_question_and_does_not_repeat_it(self):
        history = [{"role": "assistant", "content": "What matters to you?", "topic": "priorities"}]
        result = self.conversation.answer(PROFILE, history, "Keeping my doctors")
        self.assertEqual(result["topic"], "doctors")
        history += [{"role": "user", "content": "Keeping my doctors"}, {"role": "assistant", "content": result["question"], "topic": "doctors"}]
        result = self.conversation.answer(PROFILE, history, "No particular doctor")
        self.assertNotIn(result["topic"], {"priorities", "doctors"})

    def test_a_factual_question_does_not_count_as_an_intake_answer(self):
        history = [{"role": "assistant", "content": "What matters to you?", "topic": "priorities"}]
        result = self.conversation.answer(PROFILE, history, "Explain Medicare Advantage?")
        self.assertEqual(result["topic"], "priorities")
        self.assertEqual(result["facts"][0]["text"], "Immutable source text for advantage")

    def test_no_prescription_branch_skips_medicines_and_pharmacy(self):
        profile = {**PROFILE, "drugs": "no", "medicare": "no", "timing": "soon"}
        history = [{"role": "assistant", "content": "Question", "topic": t} for t in []]
        for topic in ["priorities", "doctors"]:
            history.extend([{"role": "assistant", "content": "Question", "topic": topic}, {"role": "user", "content": "Let’s come back to this"}])
        result = self.conversation.answer(profile, history, "I’m ready")
        self.assertEqual(result["topic"], "budget")

    def test_caregiver_question_refers_to_the_person_receiving_coverage(self):
        result = self.conversation.answer({**PROFILE, "recipient": "someone"})
        self.assertIn("to them", result["question"])

    def test_connected_router_receives_history_without_storage_or_fact_authoring(self):
        payloads = []
        def transport(payload):
            payloads.append(payload)
            return model_response({"next_topic": "budget", "answered_topics": ["priorities"], "research": False})
        conversation = Conversation(Chat(Sources(), ResponsesClient(key="test-key", model="test-model", transport=transport)))
        history = [{"role": "assistant", "content": "What matters?", "topic": "priorities"}]
        result = conversation.answer(PROFILE, history, "Monthly cost")
        self.assertEqual(result["topic"], "budget")
        self.assertEqual(result["conversation_mode"], "connected")
        self.assertFalse(payloads[0]["store"])
        self.assertEqual(payloads[0]["tools"], [])
        self.assertEqual(json.loads(payloads[0]["input"][0]["content"])["history"], history)
        self.assertNotIn("test-key", json.dumps(result))

    def test_model_prose_or_invalid_output_falls_back_without_becoming_coverage_advice(self):
        for value in [{"next_topic": "doctors", "answered_topics": [], "research": False, "text": "Invented advice"}, ["invalid"], {"next_topic": [], "answered_topics": [], "research": False}]:
            conversation = Conversation(Chat(Sources(), ResponsesClient(key="test", model="test", transport=lambda payload: model_response(value))))
            result = conversation.answer(PROFILE)
            self.assertEqual(result["conversation_mode"], "guided")
            self.assertTrue(result["notice"])
            self.assertNotIn("Invented advice", json.dumps(result))

    def test_incomplete_profiles_unbounded_history_and_unconfirmed_selections_rejected(self):
        cases = [({}, [], ""), ({**PROFILE, "zip": "12"}, [], ""), ({**PROFILE, "medicare": "no"}, [], ""), (PROFILE, [{"role": "assistant", "content": "x", "topic": []}], "hello"), (PROFILE, [{"role": "user", "content": "x"}] * 17, "hello")]
        for profile, history, message in cases:
            with self.assertRaises(cms.SourceError):
                self.conversation.answer(profile, history, message)
        with self.assertRaises(cms.SourceError):
            self.conversation.answer(PROFILE, selections={"rxcui": "guessed-product"})

    def test_http_discovery_and_cross_origin_guards(self):
        server = make_server(self.chat, 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        url = f"http://127.0.0.1:{server.server_port}/api/conversation"
        try:
            request = Request(url, data=json.dumps({"profile": PROFILE, "message": ""}).encode(), headers={"Content-Type": "application/json"})
            with urlopen(request) as response:
                self.assertEqual(response.status, 200)
                self.assertEqual(json.load(response)["topic"], "priorities")
            request.add_header("Origin", "https://untrusted.example")
            with self.assertRaises(HTTPError) as caught:
                urlopen(request)
            self.assertEqual(caught.exception.code, 403)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


if __name__ == "__main__":
    unittest.main()
