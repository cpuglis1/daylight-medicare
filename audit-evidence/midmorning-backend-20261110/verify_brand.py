"""Offline brand boundaries: scripted model transport and an isolated fixture service."""
from pathlib import Path
import copy
import json
import socket
import sys
import tempfile
import uuid
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT/'alternatives/advisor-first/tests'), str(ROOT/'alternatives/advisor-first')]
from test_natural_agent import NaturalAgentTests
from natural_agent import COMPOSE_INSTRUCTIONS
from server import build, verify_engine
from identifier_guard import IDENTIFIER_MESSAGE
from plans_context import REFERENCE_MARKER, REFERENCE_NOTICE

verify_engine()
case = NaturalAgentTests()
case.setUp()
message = 'Fictional note: Daylight is the name I typed, and I want to learn about Medicare.'
def forbidden(*args, **kwargs):
    raise AssertionError('Network forbidden: scripted verification only')
with patch.object(socket.socket, 'connect', forbidden), patch.object(socket, 'create_connection', forbidden):
    case.answer = case.extraction([])
    with case.agent.reserve_turn() as reservation:
        case.agent.extract('fictional-owner', message, case.g, {}, str(uuid.uuid4()), reservation)
    extractor = case.calls[-1]
    assert extractor['instructions'].startswith("You are MidMorning's report interpreter")
    assert message in json.dumps(extractor['input'])
    assert extractor['text']['format']['name'] == 'daylight_guide_commands'
    case.answer = case.composition()
    case.context['current_message'] = message
    case.compose()
    composer = case.calls[-1]
    assert composer['instructions'].startswith('You are MidMorning, a Medicare advisor')
    assert 'Daylight' not in composer['instructions']
    assert message in json.dumps(composer['input'])
    assert composer['text']['format']['name'] == 'daylight_resolved_conversation'
assert 'MidMorning' in IDENTIFIER_MESSAGE
assert 'MidMorning' in REFERENCE_MARKER and 'MidMorning' in REFERENCE_NOTICE
checks = []
with tempfile.TemporaryDirectory() as temp:
    service = build(0, fixture=True, database=Path(temp)/'fictional.sqlite3')
    try:
        cls = next(cls for cls in service.RequestHandlerClass.__mro__ if cls.__name__ == 'BrandedResponseHandler')
        parent = cls.__bases__[0]
        instance = object.__new__(service.RequestHandlerClass)
        seen = []
        def capture(self, code, value, mime, cookie):
            seen.append((code, value, mime, cookie))
        with patch.object(parent, 'respond', capture):
            for text in ['Daylight is busy. Your message and reports are preserved.',
                         'Daylight is busy. You can see plans now.',
                         'Daylight is busy. Your reports are unchanged.',
                         'Daylight is busy. Your guide is unchanged; retry shortly.']:
                original = {'error': text, 'reply': message, 'reports': {'note': message}}
                saved = copy.deepcopy(original)
                cls.respond(instance, 429, original, cookie='daylight_advisor_fixture=fictional')
                result = seen[-1]
                assert result[1]['error'] == text.replace('Daylight', 'MidMorning')
                assert result[1]['reply'] == message and result[1]['reports'] == saved['reports']
                assert original == saved
                assert result[3] == 'daylight_advisor_fixture=fictional'
            for code, text in [(429, 'Daylight is a word the person typed.'),
                               (200, 'Daylight is busy. Your reports are unchanged.')]:
                value = {'error': text, 'reply': message}
                cls.respond(instance, code, value)
                assert seen[-1][1] == value
        checks.append('four exact busy errors renamed; arbitrary text, other statuses and input data preserved')
        loaded = set(service.adaptive.rule_facts)
        r2 = json.loads((ROOT/'alternatives/advisor-first/pilot-rules-r2.json').read_text())
        assert not r2['review_state'].startswith('owner_accepted')
        assert not loaded.intersection(f['id'] for f in r2['facts'])
        checks.append('unaccepted rule drafts remain unloaded')
    finally:
        service.server_close()
print(json.dumps({'scripted_model_requests':len(case.calls),'paid_model_calls':0,
    'composer_name':'MidMorning','interpreter_name':'MidMorning','schema_names_unchanged':True,
    'verbatim_user_text_preserved':True,'pinned_engine_verified':True,'checks':checks},indent=2))
