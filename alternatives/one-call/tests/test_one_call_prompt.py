"""Offline checks of the fixed instructions, the turn input and the reply schema.

No network and no model call. The flow is built the way advisor-first's
persona runner builds it, with a transport that refuses to be used. Every
person and every catalog entry below is fictional.
"""
import copy
from datetime import date
import hashlib
import json
from pathlib import Path
import re
import socket
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1])); import _paths

from chat import ResponsesClient
from natural_flow import NaturalConversation
from pilot_knowledge import PilotKnowledge, approval_digest
import conversation_records
import enrollment_flow

import one_call_prompt as prompt

ADVISOR = _paths.ADVISOR
PLAYBOOK_DIR = Path(__file__).resolve().parents[1] / 'prompt' / 'playbooks'

# A fictional field catalog in the contract's shape, so these tests do not
# depend on one_call_tools.
CATALOG = [
    {'id': 'X01', 'label': 'Fictional first field', 'purpose': 'Shows the catalog is rendered.',
     'choices': [{'id': 'one', 'label': 'One'}, {'id': 'two', 'label': 'Two'}], 'fields': ['choice']},
    {'fields': ['text'], 'choices': [], 'purpose': 'Shows key order is fixed.',
     'label': 'Fictional second field', 'id': 'X02'},
]

GOOD_REPLY = {
    'detail_step': 'requested_work',
    'reply_blocks': [{'text': 'A fictional reply block.', 'fact_ids': ['basics']},
                     {'text': 'A second fictional block.', 'fact_ids': []}],
    'question': {'target': 'X01', 'text': 'A fictional question?'},
    'pause': False,
    'concerns': {'why_now': 'A fictional reason.', 'worries': ['A fictional worry.'], 'tried': []},
}


def _refuse(payload):
    raise AssertionError('No model call is allowed in these tests.')


def make_flow():
    return NaturalConversation(None, None,
        json.loads((ADVISOR / 'web/guide-contract.json').read_text()),
        json.loads((ADVISOR / 'web/teaching-facts.json').read_text()),
        json.loads((ADVISOR / 'web/readiness-content.json').read_text()),
        ResponsesClient(key='synthetic', model='gpt-5.4', transport=_refuse),
        True, None, fixture=False)


def _structural_errors(schema, value, path='reply'):
    """A minimal check of the schema features REPLY_SCHEMA uses."""
    kinds = schema['type'] if isinstance(schema['type'], list) else [schema['type']]
    names = {'object': dict, 'array': list, 'string': str, 'boolean': bool, 'null': type(None)}
    if not any(isinstance(value, names[kind]) for kind in kinds):
        return [path + ': wrong type']
    errors = []
    if isinstance(value, dict):
        errors += [path + ': missing ' + key for key in schema.get('required', []) if key not in value]
        if schema.get('additionalProperties') is False:
            errors += [path + ': extra ' + key for key in value if key not in schema['properties']]
        for key, item in value.items():
            if key in schema.get('properties', {}):
                errors += _structural_errors(schema['properties'][key], item, path + '.' + key)
    elif isinstance(value, list):
        if len(value) < schema.get('minItems', 0) or len(value) > schema.get('maxItems', len(value)):
            errors.append(path + ': wrong length')
        for index, item in enumerate(value):
            errors += _structural_errors(schema['items'], item, '%s[%d]' % (path, index))
    return errors


def schema_errors(value):
    try:
        import jsonschema
    except ImportError:
        return _structural_errors(prompt.REPLY_SCHEMA, value)
    validator = jsonschema.Draft202012Validator(prompt.REPLY_SCHEMA)
    return [error.message for error in validator.iter_errors(value)]


class OfflineCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.net = [patch.object(socket, 'create_connection', side_effect=AssertionError('Network forbidden')),
                   patch.object(socket.socket, 'connect', side_effect=AssertionError('Network forbidden'))]
        for item in cls.net:
            item.start()
        cls.flow = make_flow()

    @classmethod
    def tearDownClass(cls):
        for item in cls.net:
            item.stop()


class InstructionTests(OfflineCase):
    def test_instructions_are_byte_identical_and_complete(self):
        first = prompt.static_instructions(self.flow, catalog=CATALOG)
        second = prompt.static_instructions(self.flow, catalog=copy.deepcopy(CATALOG))
        self.assertEqual(first.encode(), second.encode())
        other_flow = prompt.static_instructions(make_flow(), catalog=CATALOG)
        self.assertEqual(first.encode(), other_flow.encode())
        for name in prompt.PLAYBOOKS:
            self.assertIn('## Playbook: ' + name + '\n', first)
        texts = prompt.fact_texts(self.flow)
        self.assertTrue(texts)
        for identifier, text in texts.items():
            self.assertRegex(first, r'(?m)^- %s \([^)]*\): %s$' % (re.escape(identifier), re.escape(text)))
        # Every library line is a fact from fact_texts: nothing is rendered beside it.
        library = first.split('# Fact library', 1)[1]
        rendered = re.findall(r'(?m)^- (\S+) \(', library)
        self.assertEqual(sorted(rendered), sorted(texts))
        self.assertEqual(len(rendered), len(set(rendered)))
        counts = prompt.library_counts(self.flow)
        print('\none-call instructions: %d characters (%d with no field catalog); %d facts: %s' % (
            len(first), len(prompt.static_instructions(self.flow, catalog=[])), len(texts),
            ', '.join('%s %d' % (source, counts[source]) for source in prompt.SOURCES)))

    def test_field_catalog_is_rendered_in_a_fixed_key_order(self):
        text = prompt.static_instructions(self.flow, catalog=CATALOG)
        self.assertIn('- {"id":"X01","label":"Fictional first field"', text)
        self.assertIn('- {"id":"X02","label":"Fictional second field","purpose":"Shows key order is fixed.",'
                      '"choices":[],"fields":["text"]}', text)
        self.assertLess(text.index('"id":"X01"'), text.index('"id":"X02"'))

    def test_core_rules_come_first_and_name_every_tool_and_input(self):
        text = prompt.static_instructions(self.flow, catalog=CATALOG)
        self.assertTrue(text.startswith('# Daylight'))
        order = [text.index(mark) for mark in ('# Playbooks', '# Profile fields you may save', '# Fact library')]
        self.assertEqual(order, sorted(order))
        for name in ('save_profile_fields', 'get_signup_dates', 'check_doctor', 'check_medicine',
                     'get_plan_status', 'offer_plans', 'show_card', '`transcript`', '`profile`', '`open_items`',
                     '`readiness`', '`education`', '`concerns`', '`today`', '`pending_note`',
                     '`reply_blocks`', '`question`', '`pause`', '`fact_ids`'):
            self.assertIn(name, text)

    def test_library_holds_only_accepted_sources(self):
        texts = prompt.fact_texts(self.flow)
        self.assertEqual(set(self.flow.facts) - set(texts), set())
        for path in sorted(ADVISOR.glob('pilot-rules*.json')):
            document = json.loads(path.read_text())
            accepted = str(document.get('review_state', '')).startswith('owner_accepted')
            for fact in document['facts']:
                if accepted:
                    self.assertIn(fact['id'], texts)
                elif fact['id'] not in self.flow.facts:
                    self.assertNotIn(fact['id'], texts)
        # enrollment-content.json awaits the owner's sign-off as a whole and is marked for :8895 only:
        # none of its statements or evidence entries is in the library, whatever state each carries.
        content = enrollment_flow.content()
        self.assertEqual(content['review_state'], 'awaiting_owner_sign_off')
        text = prompt.static_instructions(self.flow, catalog=CATALOG)
        own = set(self.flow.facts)
        for identifier, item in [*content['statements'].items(), *(content.get('evidence') or {}).items()]:
            if identifier not in own:
                self.assertNotIn(identifier, texts)
                self.assertNotIn(' '.join(item['text'].split()), text)
        self.assertEqual(set(texts), own)
        self.assertEqual(prompt.SOURCES, ('lesson', 'evidence', 'rule', 'pilot_knowledge'))
        self.assertNotIn('card heading', text)
        # The retained evidence lessons carry no editorial instruction.
        self.assertNotIn('Do not turn this general explanation', texts['enrollment_intro'])

    def test_facts_are_grouped_by_concept_with_the_core_fact_first(self):
        entries = prompt.fact_library(self.flow)
        concepts = [entry['concept'] for entry in entries]
        known = [*conversation_records.CONCEPTS, 'other_reviewed_facts']
        self.assertEqual(concepts, sorted(concepts, key=known.index))
        for entry in entries:
            expected = conversation_records.FACT_CONCEPT.get(entry['id'])
            if expected:
                self.assertEqual((entry['concept'], entry['role']), expected)
        by_concept = {}
        for entry in entries:
            by_concept.setdefault(entry['concept'], []).append(entry['role'])
        for roles in by_concept.values():
            self.assertNotIn('core', roles[1:])
        text = prompt.static_instructions(self.flow, catalog=CATALOG)
        self.assertIn('## original_medicare: Original Medicare\n', text)

    def test_absent_knowledge_catalog_renders_the_rest(self):
        self.assertFalse((self.flow.pilot_knowledge.root / 'catalog.json').exists()
                         and self.flow.pilot_knowledge.surface)
        counts = prompt.library_counts(self.flow)
        self.assertEqual(counts['pilot_knowledge'], 0)
        self.assertGreater(counts['lesson'], 0)
        self.assertGreater(counts['rule'], 0)
        self.assertEqual(sum(counts.values()), counts['lesson'] + counts['evidence'] + counts['rule'])


class KnowledgeCatalogTests(OfflineCase):
    """The knowledge path, proved with a synthetic catalog that states nothing about Medicare."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name) / 'data'
        root.mkdir()
        raw, text = b'SYNTHETIC RAW', 'SYNTHETIC SOURCE TEXT FOR TESTS ONLY'
        (root / 'raw.bin').write_bytes(raw)
        (root / 'text.txt').write_text(text)
        source = {'id': 's1', 'status': 'captured', 'raw_path': 'raw.bin', 'text_path': 'text.txt',
                  'sha256': hashlib.sha256(raw).hexdigest(),
                  'text_sha256': hashlib.sha256(text.encode()).hexdigest(),
                  'url': 'https://example.invalid/', 'authority': 'Synthetic', 'title': 'Synthetic'}
        quote = text[:9]

        def fact(identifier, holds=()):
            return {'id': identifier, 'title': 'Synthetic', 'text': 'Synthetic  statement\n' + identifier + '.',
                    'conditions': ['Synthetic condition.'], 'jurisdiction': 'ZZ', 'coverage_years': [2026],
                    'review_by': '2027-01-31', 'holds': list(holds), 'aliases': [], 'source_ids': ['s1'],
                    'support': [{'source_id': 's1', 'start': 0, 'end': 9, 'quote': quote,
                                 'sha256': hashlib.sha256(quote.encode()).hexdigest()}]}

        facts = [fact('zz_synthetic_b'), fact('zz_synthetic_a'), fact('zz_synthetic_held', ['hold']),
                 fact('zz_synthetic_unapproved')]
        (root / 'catalog.json').write_text(json.dumps(
            {'schema_version': 1, 'revision': 'synthetic-r1', 'sources': [source], 'facts': facts}))
        receipt = lambda item: {'digest': approval_digest(item, {'s1': source}), 'accepted_on': '2026-11-12',
                                'reviewer': 'SYNTHETIC TEST ONLY', 'accepted_by': 'SYNTHETIC TEST ONLY'}
        controls = Path(self.temp.name) / 'review.json'
        controls.write_text(json.dumps({
            'purpose': 'general_education', 'revision': 'synthetic-r1', 'allowed_surfaces': ['synthetic-surface'],
            'approved_facts': {item['id']: receipt(item) for item in facts[:3]},
            'blocked_facts': [], 'blocked_sources': []}))
        self.flow = make_flow()
        self.flow.pilot_knowledge = PilotKnowledge(root, controls, surface='synthetic-surface')
        pinned = patch.object(conversation_records, 'TODAY', date(2026, 11, 21))
        pinned.start(); self.addCleanup(pinned.stop)

    def test_only_eligible_catalog_facts_are_rendered(self):
        texts = prompt.fact_texts(self.flow)
        self.assertEqual(sorted(key for key in texts if key.startswith('zz_')), ['zz_synthetic_a', 'zz_synthetic_b'])
        self.assertEqual(texts['zz_synthetic_a'], 'Synthetic statement zz_synthetic_a. Conditions: Synthetic condition.')
        text = prompt.static_instructions(self.flow, catalog=CATALOG)
        self.assertIn('- zz_synthetic_a (statement; jurisdiction ZZ; coverage years 2026): Synthetic statement', text)
        self.assertLess(text.index('- zz_synthetic_a '), text.index('- zz_synthetic_b '))
        self.assertEqual(prompt.library_counts(self.flow)['pilot_knowledge'], 2)

    def test_the_held_claim_instruction_travels_only_on_a_hold_surface(self):
        self.assertNotIn('## Held claims', prompt.static_instructions(self.flow, catalog=CATALOG))
        self.flow.pilot_knowledge.surface = 'hosted-demo'
        text = prompt.static_instructions(self.flow, catalog=CATALOG)
        held = self.flow.pilot_knowledge.response_limits()['instruction']
        self.assertIn('## Held claims\n' + ' '.join(held.split()), text)

    def test_a_surface_outside_the_acceptance_renders_none(self):
        self.flow.pilot_knowledge.surface = 'another-surface'
        self.assertFalse([key for key in prompt.fact_texts(self.flow) if key.startswith('zz_')])

    def test_an_expired_or_altered_fact_is_withdrawn(self):
        with patch.object(conversation_records, 'TODAY', date(2027, 2, 1)):
            self.assertFalse([key for key in prompt.fact_texts(self.flow) if key.startswith('zz_')])
        (self.flow.pilot_knowledge.root / 'text.txt').write_text('ALTERED')
        self.assertFalse([key for key in prompt.fact_texts(self.flow) if key.startswith('zz_')])


class PlaybookTests(unittest.TestCase):
    def test_thirteen_playbooks_with_front_matter_and_three_sections(self):
        files = sorted(path.stem for path in PLAYBOOK_DIR.glob('*.md'))
        self.assertEqual(files, sorted(prompt.PLAYBOOKS))
        self.assertEqual(len(files), 13)
        for name in prompt.PLAYBOOKS:
            path = PLAYBOOK_DIR / (name + '.md')
            meta, body = prompt._front_matter(path.read_text(encoding='utf-8'), path)
            self.assertEqual(meta['name'], name)
            self.assertTrue(meta['description'].startswith('Use '))
            headings = re.findall(r'(?m)^## (.+)$', body)
            self.assertEqual(headings, ['When it applies', 'What to do', 'What never to do'])
            words = len(body.split())
            self.assertTrue(100 <= words <= 240, '%s has %d words' % (name, words))

    def test_no_fact_markers_in_any_playbook(self):
        for path in sorted(PLAYBOOK_DIR.glob('*.md')):
            text = path.read_text(encoding='utf-8')
            self.assertNotIn('$', text, path.name)
            self.assertNotIn('%', text, path.name)
            self.assertIsNone(re.search(r'(?<!\d)\d{4}(?!\d)', text), path.name)
            self.assertNotIn('"', text, path.name)   # no sentence offered for copying


class TurnInputTests(unittest.TestCase):
    def build(self, **changes):
        values = {
            'transcript': [{'role': 'daylight', 'text': 'A fictional greeting.'},
                           {'role': 'person', 'text': 'A fictional message from Pat Example.'}],
            'profile': {'who': 'self', 'coverage': ['none']},
            'open_items': [{'id': 'X01', 'label': 'Fictional first field'}],
            'readiness': {'plans': {'ready': False, 'needs': ['X01']}},
            'education': {'concepts': {}, 'delivered_facts': []},
            'concerns': {'why_now': None, 'worries': [], 'tried': []},
            'today': '2026-11-21',
        }
        values.update(changes)
        return prompt.turn_input(**values)

    def test_same_values_give_the_same_string_whatever_the_key_order(self):
        first = self.build()
        second = self.build(
            transcript=[{'text': 'A fictional greeting.', 'role': 'daylight', 'request_id': 'ignored'},
                        {'text': 'A fictional message from Pat Example.', 'role': 'person'}],
            profile={'coverage': ['none'], 'who': 'self'},
            readiness={'plans': {'needs': ['X01'], 'ready': False}},
            today=date(2026, 11, 21), pending_note=None)
        self.assertEqual(first, second)
        value = json.loads(first)
        self.assertEqual(list(value), ['today', 'profile', 'open_items', 'readiness', 'education',
                                       'concerns', 'stage', 'pending_note', 'transcript'])
        self.assertIsNone(value['pending_note'])
        self.assertEqual(value['transcript'][-1], {'role': 'person', 'text': 'A fictional message from Pat Example.'})

    def test_sets_are_ordered_and_a_bad_transcript_role_is_refused(self):
        first = self.build(open_items={'ids': {'X02', 'X01'}}, pending_note={'missed': ['X02']})
        second = self.build(open_items={'ids': {'X01', 'X02'}}, pending_note={'missed': ['X02']})
        self.assertEqual(first, second)
        self.assertEqual(json.loads(first)['open_items'], {'ids': ['X01', 'X02']})
        with self.assertRaises(ValueError):
            self.build(transcript=[{'role': 'system', 'text': 'A fictional entry.'}])


class ReplySchemaTests(unittest.TestCase):
    def test_schema_name(self):
        self.assertEqual(prompt.REPLY_SCHEMA_NAME, 'daylight_one_call_reply')

    def test_good_replies_validate(self):
        self.assertEqual(schema_errors(GOOD_REPLY), [])
        paused = {**copy.deepcopy(GOOD_REPLY), 'question': None, 'pause': True}
        paused['concerns']['why_now'] = None
        self.assertEqual(schema_errors(paused), [])
        untargeted = copy.deepcopy(GOOD_REPLY)
        untargeted['question']['target'] = None
        self.assertEqual(schema_errors(untargeted), [])

    def test_missing_extra_and_out_of_range_are_rejected(self):
        for key in GOOD_REPLY:
            self.assertTrue(schema_errors({k: v for k, v in GOOD_REPLY.items() if k != key}), key)
        for path in (('reply_blocks', 0, 'fact_ids'), ('question', 'target'), ('concerns', 'tried')):
            broken = copy.deepcopy(GOOD_REPLY)
            holder = broken
            for step in path[:-1]:
                holder = holder[step]
            del holder[path[-1]]
            self.assertTrue(schema_errors(broken), path)
        self.assertTrue(schema_errors({**GOOD_REPLY, 'extra': 1}))
        self.assertTrue(schema_errors({**GOOD_REPLY, 'reply_blocks': []}))
        self.assertTrue(schema_errors({**GOOD_REPLY, 'reply_blocks': GOOD_REPLY['reply_blocks'][:1] * 5}))
        self.assertTrue(schema_errors({**GOOD_REPLY, 'pause': None}))
        # The fallback check agrees with the validator on the same cases.
        self.assertEqual(_structural_errors(prompt.REPLY_SCHEMA, GOOD_REPLY), [])
        self.assertTrue(_structural_errors(prompt.REPLY_SCHEMA, {k: v for k, v in GOOD_REPLY.items() if k != 'pause'}))

    def test_schema_is_strict_throughout(self):
        def walk(schema):
            kinds = schema['type'] if isinstance(schema['type'], list) else [schema['type']]
            if 'object' in kinds:
                self.assertIs(schema['additionalProperties'], False)
                self.assertEqual(sorted(schema['required']), sorted(schema['properties']))
                for item in schema['properties'].values():
                    walk(item)
            if 'array' in kinds:
                walk(schema['items'])
        walk(prompt.REPLY_SCHEMA)


if __name__ == '__main__':
    unittest.main()
