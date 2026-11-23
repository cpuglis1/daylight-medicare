"""Shared pieces for the one-call integration tests.

Offline only: a scripted transport stands in for the model, the budget ledger
is a temporary file, sockets are forbidden and every person is fictional.
These tests check what software does with a scripted model's output. They say
nothing about how a live model reads a message or writes a reply.
"""
import copy
from datetime import date, datetime, timezone
import json
from pathlib import Path
import socket
import sys
import tempfile
from unittest.mock import patch
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import _paths  # noqa: E402

from ai_budget import DailyBudget  # noqa: E402
from chat import ResponsesClient  # noqa: E402
from natural_flow import CONTEXT_POLICY  # noqa: E402
import conversation_planner  # noqa: E402
import conversation_records  # noqa: E402
import ux_flow  # noqa: E402

from one_call_flow import OneCallConversation  # noqa: E402
import one_call_prompt  # noqa: E402

ADVISOR = _paths.ADVISOR
TODAY = date(2026, 11, 21)
EXTRACTION = 'daylight_guide_commands'
COMPOSITION = 'daylight_resolved_conversation'
UI_KEYS = ('conversationNext', 'questionProgress', 'profileProgress', 'whatsLeft', 'planReadiness',
           'enrollment', 'cmsChecklist')


def contract_available():
    """advisor-first's plan views read a sealed profile contract whose sources may be absent in a checkout."""
    try:
        import comparison_profile
        comparison_profile._load_contract()
        return True
    except Exception:
        return False


READY = contract_available()
NOT_READY = 'advisor-first profile contract sources are not present in this checkout (tools/prepare_advisor.py)'


def _forbidden(*args, **kwargs):
    raise AssertionError('Network is forbidden in the one-call tests')


def offline(test):
    """The same four patches as advisor-first's persona_runner.offline_network()."""
    for owner, name in ((socket, 'create_connection'), (socket, 'getaddrinfo'),
                        (socket.socket, 'connect'), (socket.socket, 'connect_ex')):
        guard = patch.object(owner, name, _forbidden)
        guard.start()
        test.addCleanup(guard.stop)


def pin_today(test, day=TODAY):
    for module in (conversation_records, ux_flow):
        guard = patch.object(module, 'TODAY', day)
        guard.start()
        test.addCleanup(guard.stop)


# -- scripted model output ---------------------------------------------------------

def completed(output):
    return {'status': 'completed', 'model': 'gpt-5.4', 'service_tier': 'default',
            'usage': {'input_tokens': 300, 'output_tokens': 70, 'total_tokens': 370,
                      'input_tokens_details': {'cached_tokens': 0}},
            'output': output}


def message(value):
    return {'type': 'message', 'id': 'msg_1', 'role': 'assistant',
            'content': [{'type': 'output_text', 'text': value if isinstance(value, str) else json.dumps(value)}]}


def call(call_id, name, arguments):
    return {'type': 'function_call', 'id': 'fc_' + call_id, 'call_id': call_id, 'name': name,
            'arguments': json.dumps(arguments)}


def reply(*blocks, question=None, target=None, pause=False, concerns=None, detail_step='talk'):
    """A final reply in the one-call format. ``question`` is its text; ``target`` its catalog id."""
    return {'reply_blocks': [block if isinstance(block, dict) else {'text': block, 'fact_ids': []} for block in blocks],
            'question': None if question is None else {'target': target, 'text': question},
            'pause': pause, 'detail_step': detail_step,
            'concerns': concerns or {'why_now': None, 'worries': [], 'tried': []}}


def update(identifier, fields, quote, **extra):
    return {'id': identifier, 'entity': None,
            'fields': [{'key': key, 'value': value} for key, value in fields.items()],
            'quote': quote, 'subject': 'beneficiary', 'scope': 'current',
            'uncertain': False, 'correction': False, **extra}


def save(*updates, call_id='c1'):
    return call(call_id, 'save_profile_fields', {'updates': list(updates)})


def extraction(updates=(), **extra):
    """What advisor-first's extraction stage returns for a records-enabled conversation."""
    return {'updates': list(updates), 'requests': [], 'fact_ids': [],
            'agenda': {'concerns': [], 'priorityReason': {'topic': '', 'reason': '', 'quote': '',
                                                          'subject': 'unclear', 'scope': 'unknown'}},
            'situation_proposals': [], 'goal_quote': '',
            'education_request': {'kind': 'none', 'concept_ids': [], 'quote': ''},
            'discussion': conversation_planner.empty_proposal(), 'next_target': {'ids': [], 'reason': 'goal'},
            'coverage_reports': [], 'pending_disposition': 'none', **extra}


def composition(text='Thank you.', target=None, question=''):
    """What advisor-first's composer returns for a tapped answer. No question unless one is named."""
    return {'question_target': target, 'reply': text, 'question': question if target else '', 'report_refs': [],
            'evidence_refs': [], 'education': {'purpose': 'advance', 'updates': [], 'visual': 'none'},
            'agenda_update': {'current_concern': '', 'pause': False}}


def extraction_update(identifier, fields, quote, **extra):
    """An update as the extraction stage writes one (entity 'profile', fields as pairs)."""
    return {'id': identifier, 'entity': 'profile', 'fields': [{'key': key, 'value': value} for key, value in fields.items()],
            'quote': quote, 'subject': 'beneficiary', 'scope': 'current', 'uncertain': False, 'correction': False, **extra}


class Script:
    """The scripted transport.

    A one-call request takes the next entry of ``steps`` (a list of output items,
    or an exception to raise). An extraction request, which only the background
    record pass makes here, takes the next entry of ``extractions`` or an empty
    extraction. Every payload is kept for inspection.
    """

    def __init__(self):
        self.steps, self.extractions, self.compositions = [], [], []
        self.sent, self.extraction_sent, self.composition_sent = [], [], []

    def __call__(self, payload):
        name = payload['text']['format']['name']
        if name == EXTRACTION:
            self.extraction_sent.append(copy.deepcopy(payload))
            value = self.extractions.pop(0) if self.extractions else extraction()
            if isinstance(value, BaseException):
                raise value
            return completed([message(value)])
        if name == COMPOSITION:
            # advisor-first's own one-request reply to a tapped answer sent with AI permission.
            self.composition_sent.append(copy.deepcopy(payload))
            value = self.compositions.pop(0) if self.compositions else composition()
            if isinstance(value, BaseException):
                raise value
            return completed([message(value)])
        if name != one_call_prompt.REPLY_SCHEMA_NAME:
            raise AssertionError('An unexpected model stage was called: ' + name)
        self.sent.append(copy.deepcopy(payload))
        if not self.steps:
            raise AssertionError('The scripted model has no step left for this request')
        step = self.steps.pop(0)
        if isinstance(step, BaseException):
            raise step
        return completed(step)

    def add(self, *steps):
        self.steps.extend(steps)

    def inputs(self):
        """The turn input of every one-call request, parsed."""
        return [json.loads(payload['input'][0]['content']) for payload in self.sent]


def temporary_ledger(test, agent):
    """A fresh budget ledger in a temporary folder, with rates valid on its fixed clock."""
    folder = tempfile.TemporaryDirectory()
    test.addCleanup(folder.cleanup)
    path = Path(folder.name)
    path.chmod(0o700)
    rates = json.loads((_paths.REPO / 'alternatives/chat-first/cms-slice/config/ai-pricing.json').read_text())
    rates['verified_at'] = '2026-10-30T00:00:00Z'
    rates['valid_until'] = '2026-11-04T00:00:00Z'
    pricing = path / 'pricing.json'
    pricing.write_text(json.dumps(rates))
    agent.budget = DailyBudget(path / 'usage.sqlite3', pricing_path=pricing,
                               clock=lambda: datetime(2026, 10, 30, 16, tzinfo=timezone.utc).timestamp())
    agent.count_tokens = lambda client, payload: 300
    return agent.budget


def charge_rows(budget):
    with budget.db() as db:
        return sorted(row[0] for row in db.execute('SELECT status FROM ai_charges'))


def make_flow(script, *, reconcile=False, inline=True):
    """The real conversation class over the scripted transport, constructed as advisor-first's server does."""
    flow = OneCallConversation(None, None,
                               json.loads((ADVISOR / 'web/guide-contract.json').read_text()),
                               json.loads((ADVISOR / 'web/teaching-facts.json').read_text()),
                               json.loads((ADVISOR / 'web/readiness-content.json').read_text()),
                               ResponsesClient(key='synthetic-offline-only', model='gpt-5.4', transport=script),
                               True, None, fixture=False)
    flow.guided_close = True
    flow.reconciler.enabled = reconcile
    if inline:
        flow.reconciler.executor = lambda work: work()
    return flow


class Visit:
    """One fictional person's visit, driven through ``flow.turn`` the way the browser drives it.

    Every response is checked for the delivery contract and the keys the
    interface reads, and its continuation is the one sent with the next turn.
    """

    def __init__(self, test, flow, script):
        self.test, self.flow, self.script = test, flow, script
        self.owner = uuid.uuid4().hex
        self.guide, self.record = flow.initial()
        self.continuation = None
        self.outs = []

    def payload(self, action, *, consent=True, policy=CONTEXT_POLICY):
        value = {'guide': copy.deepcopy(self.guide), 'record': copy.deepcopy(self.record), 'action': action,
                 'requestId': str(uuid.uuid4()), 'aiConsent': consent, 'contextPolicy': policy}
        if self.continuation:
            value['continuation'] = self.continuation
        return value

    def send(self, action, *, consent=True, policy=CONTEXT_POLICY):
        out = self.flow.turn(self.owner, self.payload(action, consent=consent, policy=policy))
        self.test.assertTrue(conversation_planner.valid_delivered_next(out), out.get('conversationNext'))
        for key in UI_KEYS:
            if key != 'cmsChecklist' or policy == CONTEXT_POLICY:
                self.test.assertIn(key, out)
        self.test.assertRegex(out['continuation'], r'^[a-f0-9]{32}\.[a-f0-9]{64}$')
        self.guide, self.record, self.continuation = out['guide'], out['record'], out['continuation']
        self.outs.append(out)
        return out

    def start(self):
        return self.send({'type': 'start'}, consent=False, policy=None)

    def say(self, text, *steps):
        """Type a message; ``steps`` are the scripted model's requests for this turn."""
        self.script.add(*steps)
        return self.send({'type': 'message', 'message': text})

    def tap(self, action, *, consent=False):
        """A button or form answer. By default a free on-screen control with no AI permission;
        ``consent=True`` sends it as the live interface does, and advisor-first composes a reply."""
        return self.send(action, consent=consent, policy=CONTEXT_POLICY if consent else None)

    @property
    def chain(self):
        return self.flow.current_chain[self.owner]

    def given_profile_permission(self):
        """Start this routing fixture at the point after the person has agreed to detail questions."""
        self.flow.one_call_visits.add(self.owner, self.chain, CONTEXT_POLICY, detail_permission='granted')

    def transcript(self):
        return self.flow.one_call_visits.read(self.owner, self.chain, CONTEXT_POLICY)['transcript']

    def value(self, path):
        return self.flow.value(self.guide, path)

    def report(self, identifier):
        return self.flow.report(self.record, identifier)


# -- advisor-first's offline doctor and medicine fixtures ---------------------------------

def check_services():
    """advisor-first's fictional doctor and drug services (tests/behavioral_offline_server.py).

    Those fixtures import the data package, whose modules import the PostgreSQL driver at
    load time. The fixtures never open a connection, so when the driver is not installed an
    empty stand-in module lets the pure-Python code load. Returns ``(Doctors, Drugs,
    ConversationChecks)``, or None when the fixtures still cannot be loaded.
    """
    import importlib.util
    import types
    try:
        missing = 'psycopg' not in sys.modules and importlib.util.find_spec('psycopg') is None
    except (ImportError, ValueError):
        missing = False
    if missing:
        nothing = lambda *args, **kwargs: None
        for name, attributes in (('psycopg', {'connect': nothing, 'Connection': object}),
                                 ('psycopg.sql', {'SQL': nothing, 'Identifier': nothing, 'Literal': nothing,
                                                  'Composed': object}),
                                 ('psycopg.rows', {'dict_row': None}),
                                 ('psycopg.conninfo', {'conninfo_to_dict': nothing}),
                                 ('psycopg.types', {}), ('psycopg.types.json', {'Jsonb': nothing}),
                                 ('psycopg_pool', {'ConnectionPool': None})):
            module = types.ModuleType(name)
            module.__dict__.update(attributes)
            module.__path__ = []
            sys.modules[name] = module
        sys.modules['psycopg'].sql = sys.modules['psycopg.sql']
    for path in (str(ADVISOR / 'tests'), str(_paths.REPO / 'infrastructure/daylight-data/src')):
        if path not in sys.path:
            sys.path.append(path)
    try:
        from behavioral_offline_server import Doctors, Drugs
        from conversation_checks import ConversationChecks
    except Exception:
        return None
    return Doctors, Drugs, ConversationChecks


def attach_fictional_checks(flow):
    """Attach advisor-first's check controller over its fictional services. Returns whether it could."""
    loaded = check_services()
    if loaded is None:
        return False
    Doctors, Drugs, ConversationChecks = loaded
    plans = [{'offering_id': '2026:H9999:00%d:000' % number, 'name': 'Fictional Plan %d' % number} for number in range(3)]
    flow.conversation_checks = ConversationChecks(flow, Doctors(plans), Drugs(), lambda: [])
    return True
