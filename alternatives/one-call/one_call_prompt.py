"""The fixed instructions, the per-turn input and the reply schema of the one-call loop.

The instructions are the same bytes on every turn for the same accepted
sources: the core rules (`prompt/core.md`), the playbooks
(`prompt/playbooks/*.md`), the field catalog and the fact library.

This module writes no Medicare fact. The fact library is rendered from the
sources advisor-first already loads, through its own loaders and acceptance
filters:

- `flow.facts`: the retained lessons, the two evidence lessons (already
  stripped of their editorial sentences) and the rule files whose
  `review_state` starts with `owner_accepted`;
- `flow.pilot_knowledge`: catalog facts that pass `PilotKnowledge._eligible`
  on an allowed surface (nothing when the catalog is absent).

advisor-first's `enrollment-content.json` is not a source. That file is awaiting
the owner's sign-off as a whole and is marked for :8895 only, and advisor-first
exposes no owner-accepted loader for it that covers another surface. None of
its statements or evidence entries enter the library.

Nothing here logs, calls a model or touches the network.
"""
from datetime import date, datetime
from functools import lru_cache
import json
from pathlib import Path

import _paths  # noqa: F401  (puts advisor-first on sys.path and registers the pinned engine)

import conversation_records
import education as education_catalog

HERE = Path(__file__).resolve().parent
PROMPT = HERE / 'prompt'
CORE = PROMPT / 'core.md'
PLAYBOOK_DIR = PROMPT / 'playbooks'
PLAYBOOKS = (
    'discovery', 'past-experience', 'helping-someone-else', 'teaching-basics',
    'teaching-detail', 'working-past-65', 'fall-review', 'comparing-plans',
    'presenting-the-result', 'concerns', 'closing-and-handoff', 'boundaries', 'repair',
)

REPLY_SCHEMA_NAME = 'daylight_one_call_reply'
REPLY_SCHEMA = {
    'type': 'object',
    'additionalProperties': False,
    'required': ['reply_blocks', 'question', 'pause', 'concerns', 'detail_step'],
    'properties': {
        'reply_blocks': {
            'type': 'array', 'minItems': 1, 'maxItems': 4,
            'items': {
                'type': 'object',
                'additionalProperties': False,
                'required': ['text', 'fact_ids'],
                'properties': {
                    'text': {'type': 'string'},
                    'fact_ids': {'type': 'array', 'items': {'type': 'string'}},
                },
            },
        },
        'question': {
            'type': ['object', 'null'],
            'additionalProperties': False,
            'required': ['target', 'text'],
            'properties': {
                'target': {'type': ['string', 'null']},
                'text': {'type': 'string'},
            },
        },
        'pause': {'type': 'boolean'},
        'detail_step': {'type': 'string', 'enum': ['talk', 'invite', 'agree', 'later', 'requested_work']},
        'concerns': {
            'type': 'object',
            'additionalProperties': False,
            'required': ['why_now', 'worries', 'tried'],
            'properties': {
                'why_now': {'type': ['string', 'null']},
                'worries': {'type': 'array', 'items': {'type': 'string'}},
                'tried': {'type': 'array', 'items': {'type': 'string'}},
            },
        },
    },
}

# Where a library entry came from. Used for grouping and for counts only.
SOURCES = ('lesson', 'evidence', 'rule', 'pilot_knowledge')
_OTHER = 'other_reviewed_facts'


# ---------------------------------------------------------------------------
# The fact library
# ---------------------------------------------------------------------------

def _one_line(value):
    return ' '.join(value.split()) if isinstance(value, str) else ''


def _flow_facts(flow):
    """Lessons, evidence lessons and accepted rules, exactly as the flow loaded them."""
    facts = getattr(flow, 'facts', None) or {}
    rules = getattr(flow, 'rule_facts', None) or {}
    lessons = getattr(flow, 'progress_fact_ids', None) or frozenset()
    for identifier in sorted(facts):
        source = 'rule' if identifier in rules else 'lesson' if identifier in lessons else 'evidence'
        yield {'id': identifier, 'text': _one_line(facts[identifier].get('text')), 'source': source, 'scope': ''}


def _pilot_knowledge_facts(flow, today):
    """Catalog facts that pass advisor-first's own receipt, digest, date and surface checks.

    An absent or unreadable catalog yields nothing, as it does in `PilotKnowledge.select`.
    """
    index = getattr(flow, 'pilot_knowledge', None)
    if index is None:
        return []
    found = []
    try:
        catalog, control, sources = index._read()
        if not index._active(control):
            return []
        for fact in sorted(catalog['facts'], key=lambda item: item['id']):
            if not index._eligible(fact, control, sources, today):
                continue
            text = _one_line(fact['text'])
            conditions = [_one_line(item) for item in fact.get('conditions') or [] if _one_line(item)]
            if conditions:
                text += ' Conditions: ' + '; '.join(conditions)
            years = ', '.join(str(year) for year in sorted(fact.get('coverage_years') or []))
            scope = '; '.join(part for part in (
                'jurisdiction ' + str(fact['jurisdiction']) if fact.get('jurisdiction') else '',
                'coverage years ' + years if years else '') if part)
            found.append({'id': fact['id'], 'text': text, 'source': 'pilot_knowledge', 'scope': scope})
    except (OSError, ValueError, KeyError, TypeError):
        return []
    return found


def fact_library(flow, *, today=None):
    """Every rendered library entry, in rendering order.

    Each entry is {'id', 'text', 'source', 'scope', 'concept', 'role'}. An id
    is rendered once; the first source in SOURCES order keeps it.
    """
    today = today or conversation_records._today()
    entries, seen = [], set()
    for entry in [*_flow_facts(flow), *_pilot_knowledge_facts(flow, today)]:
        if not entry['text'] or not isinstance(entry['id'], str) or entry['id'] in seen:
            continue
        seen.add(entry['id'])
        concept, role = conversation_records.FACT_CONCEPT.get(entry['id'], (None, None))
        if concept is None:
            concept = _OTHER
            role = 'statement'
        entries.append({**entry, 'concept': concept, 'role': role})
    order = {concept: index for index, concept in enumerate([*conversation_records.CONCEPTS, _OTHER])}
    position = {}
    for concept, (_title, core, details) in conversation_records.CONCEPTS.items():
        for index, identifier in enumerate([core, *details]):
            position.setdefault(identifier, index)
    entries.sort(key=lambda entry: (order[entry['concept']], position.get(entry['id'], len(position)), entry['id']))
    return entries


def fact_texts(flow):
    """Fact id -> text, exactly the pairs `static_instructions` renders."""
    return {entry['id']: entry['text'] for entry in fact_library(flow)}


def library_counts(flow):
    """How many entries each source contributed. Counts only; no content."""
    counts = dict.fromkeys(SOURCES, 0)
    for entry in fact_library(flow):
        counts[entry['source']] += 1
    return counts


def _render_library(flow):
    entries = fact_library(flow)
    outcomes = {item['concept_id']: item['learning_outcome'] for item in education_catalog.CONCEPTS}
    titles = {concept: title for concept, (title, _core, _details) in conversation_records.CONCEPTS.items()}
    titles[_OTHER] = 'Other reviewed facts'
    lines = ['# Fact library', '',
             'Each line is one reviewed fact: its id, its role in the concept, then its text. '
             'Cite the id in fact_ids when a reply block states the fact. '
             'A scope shown in the brackets limits where the fact applies.']
    current = None
    for entry in entries:
        if entry['concept'] != current:
            current = entry['concept']
            lines += ['', '## %s: %s' % (current, titles[current])]
            if current in outcomes:
                lines.append('Useful understanding: ' + outcomes[current])
        label = entry['role'] + ('; ' + entry['scope'] if entry['scope'] else '')
        lines.append('- %s (%s): %s' % (entry['id'], label, entry['text']))
    index = getattr(flow, 'pilot_knowledge', None)
    limits = index.response_limits() if index is not None else {}
    if isinstance(limits, dict) and limits.get('instruction'):
        lines += ['', '## Held claims', _one_line(limits['instruction'])]
    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# Core rules, playbooks and the field catalog
# ---------------------------------------------------------------------------

def _front_matter(text, path):
    """A playbook's `name` and `description` plus its body. Plain `key: value` lines only."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != '---':
        raise ValueError('Playbook has no front matter: %s' % path.name)
    try:
        end = lines.index('---', 1)
    except ValueError:
        raise ValueError('Playbook front matter is not closed: %s' % path.name) from None
    meta = {}
    for line in lines[1:end]:
        key, separator, value = line.partition(':')
        if separator:
            meta[key.strip()] = value.strip()
    if meta.get('name') != path.stem or not meta.get('description'):
        raise ValueError('Playbook needs a matching name and a description: %s' % path.name)
    return meta, '\n'.join(lines[end + 1:]).strip()


def _demote(body):
    """A playbook's own headings sit one level below its title in the instructions."""
    return '\n'.join('#' + line if line.startswith('## ') else line for line in body.splitlines())


@lru_cache(maxsize=1)
def _fixed_text():
    """The hand-written part: core rules, then every playbook in a fixed order."""
    parts = [CORE.read_text(encoding='utf-8').strip(), '', '# Playbooks', '',
             'Each playbook is guidance for one kind of moment. Several can apply in the same turn. '
             'The rules above always take priority.']
    for name in PLAYBOOKS:
        path = PLAYBOOK_DIR / (name + '.md')
        meta, body = _front_matter(path.read_text(encoding='utf-8'), path)
        parts += ['', '## Playbook: ' + meta['name'], meta['description'], '', _demote(body)]
    return '\n'.join(parts)


def _dumps(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), default=_plain)


def _plain(value):
    if isinstance(value, (set, frozenset)):
        return sorted(value, key=str)
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    raise TypeError('Unsupported value in the turn input.')


def _ordered(item, first):
    """One JSON object with the named keys first and the rest sorted."""
    keys = [key for key in first if key in item] + sorted(key for key in item if key not in first)
    return '{' + ','.join(json.dumps(key) + ':' + _dumps(item[key]) for key in keys) + '}'


def _render_catalog(catalog):
    lines = ['# Profile fields you may save', '',
             'One line per meaning, in the shape save_profile_fields expects: its id, what it records, '
             'why it is asked, the choices it allows and its fields.']
    for item in catalog:
        lines.append('- ' + _ordered(item, ('id', 'label', 'purpose', 'choices', 'fields')))
    return '\n'.join(lines)


def static_instructions(flow, *, catalog=None):
    """The whole fixed instruction text for this flow's accepted sources.

    `catalog` is the field catalog; when omitted it comes from
    `one_call_tools.field_catalog(flow)`.
    """
    if catalog is None:
        import one_call_tools
        catalog = one_call_tools.field_catalog(flow)
    return '\n\n'.join([_fixed_text(), _render_catalog(catalog), _render_library(flow)]) + '\n'


# ---------------------------------------------------------------------------
# The per-turn input
# ---------------------------------------------------------------------------

_ROLES = ('person', 'daylight')


def turn_input(*, transcript, profile, open_items, readiness, education, concerns, today, pending_note=None,
               stage=None):
    """One JSON string with a fixed key order; the transcript comes last.

    The same values always give the same string, whatever order the caller
    built its dictionaries in.
    """
    turns = []
    for turn in transcript:
        if turn.get('role') not in _ROLES or not isinstance(turn.get('text'), str):
            raise ValueError('A transcript entry needs a role of person or daylight and a text.')
        turns.append({'role': turn['role'], 'text': turn['text']})
    value = {
        'today': today.isoformat() if isinstance(today, (date, datetime)) else today,
        'profile': profile,
        'open_items': open_items,
        'readiness': readiness,
        'education': education,
        'concerns': concerns,
        'stage': stage if stage is not None else {
            'now': 'understand_the_person', 'still_to_learn': ['why_now', 'worries', 'tried'], 'detail_permission': 'open'},
        'pending_note': pending_note,
        'transcript': turns,
    }
    return _ordered(value, tuple(value))
