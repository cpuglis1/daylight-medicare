"""Small, local pilot fact index; no network, embeddings or user storage.

The catalog is review material. Only exact facts with an explicit receipt for
general education can enter a conversation. It never decides applicability.
"""
from datetime import date
import hashlib
import json
import os
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2] / 'docs/data/pilot-knowledge-2026-11-12-r2'
CONTROLS = Path(__file__).with_name('pilot-knowledge-review-8895-r2.json')
# Retrieval hints (no wording): which approved fact a person's own phrasing is about. Exact alias
# phrases alone missed "is there any limit on what I could end up paying for drugs in a year?"
# and five other questions in the 15-profile run of November 13, 2026.
CONCEPTS = Path(__file__).with_name('pilot-knowledge-concepts.json')
HELD_MA_DEADLINE = 'ma_initial_deadline_after_late_part_b'


def _late_part_b(text):
    text = words(text or '')
    return bool(re.search(r'\b(?:new to|delay\w*)\s+part b\b', text)
                or re.search(r'\bpart b\b.{0,30}\b(?:later|late|delay\w*|after part a)\b', text)
                or (re.search(r'\b(?:already.{0,20}part a|part a only|part a first)\b', text)
                    and re.search(r'\b(?:add(?:ing|ed)?|start(?:ing|ed)?)\s+part b\b', text)))


def held_deadline_claim(text, limits):
    """Bounded rejection for the explicitly unresolved MA enrollment clock.

    Raw source prose never enters context. This also rejects a clock echoed from
    the user's question; ordinary literal grounding alone cannot do that.
    It is a conservative language guard, not general semantic entailment.
    """
    if HELD_MA_DEADLINE not in limits.get('held_claim_ids', []):
        return False
    normalized = words(text or '')
    scoped = limits.get('late_part_b_context') or (
        (_late_part_b(text) or re.search(r'\bafter part b (?:starts?|begins?)\b', normalized))
        and re.search(r'\b(?:medicare advantage|ma|part c)\b', normalized))
    if not scoped:
        return False
    timing = re.compile(
        r'\b(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|'
        r'first|second|third|fourth|fifth|sixth|last)\s+(?:(?:full|calendar|consecutive)\s+)?(?:days?|weeks?|months?)\b|'
        r'\b(?:january|february|march|april|june|july|august|september|october|november|december)\b|'
        r'\bmay\s+\d|\b(?:by|until|through|in|on|before|after|is|ends?) may\b|'
        r'\b\d{4}[-/]\d{1,2}(?:[-/]\d{1,2})?\b|\b\d{1,2}/\d{1,2}(?:/\d{2,4})?\b|'
        r'\b(?:end of|same|next|following) (?:the )?month\b|\bmonth (?:after|before)\b', re.I)
    for clause in re.split(r'[.!?;\n]+', text or ''):
        # Hyphenated durations and number words are equivalent for this hold.
        normalized_clause = re.sub(r'[-–—]', ' ', clause).lower()
        if not (timing.search(normalized_clause) or timing.search(clause)):
            continue
        # A supported coverage effective date is not an enrollment deadline.
        clock = re.search(r'\b(?:deadline|window|period|close[sd]?|lasts?|until|through|by|within|'
                          r'to (?:join|enroll)|chance to)\b', normalized_clause)
        effective = re.search(r'\b(?:coverage|plan) (?:generally |will |can )?(?:start|begin)|'
                              r'\b(?:take[sn]? effect|effective date)\b', normalized_clause)
        if effective and not clock:
            continue
        # These separately named clocks remain teachable in a mixed answer.
        other_clock = re.search(r'\bmedigap\b|\bpart b.{0,35}\bspecial enrollment\b|'
                                r'\bgeneral enrollment period\b|\bannual (?:open )?enrollment\b', normalized_clause)
        if other_clock and not re.search(r'\b(?:medicare advantage|ma|part c)\b', normalized_clause):
            continue
        return True
    return False


def _concepts():
    try:
        loaded = json.loads(CONCEPTS.read_text(encoding='utf-8'))
        return {key: value for key, value in loaded.items() if isinstance(value, list)}
    except (OSError, ValueError):
        return {}


def _concept_match(identifier, query):
    groups = _concepts().get(identifier)
    try:
        return bool(groups) and all(any(re.search(r'(?<![a-z0-9])(?:%s)' % pattern, query) for pattern in group) for group in groups)
    except re.error:
        return False


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(',', ':')).encode()).hexdigest()


def approval_digest(fact, sources):
    return digest({'fact': fact, 'sources': [sources[s] for s in fact['source_ids']]})


def words(text):
    return ' '.join(re.findall(r'[a-z0-9]+', text.lower()))


class PilotKnowledge:
    def __init__(self, root=ROOT, controls=CONTROLS, *, surface=None):
        self.root, self.controls = Path(root), Path(controls)
        self.surface = surface

    def _active(self, control):
        return (self.surface in control.get('allowed_surfaces', [])
                and not os.environ.get('DAYLIGHT_DISABLE_PILOT_KNOWLEDGE'))

    def response_limits(self, message='', facts=()):
        # D163: this hold persists on :8895 even if index use is disabled or a
        # receipt expires. It does not depend on quoting the held source.
        if self.surface != 'unified-8895':
            return {}
        return {'held_claim_ids': [HELD_MA_DEADLINE],
                'late_part_b_context': (_late_part_b(message) or any(
                    f.get('id') == 'pk_new_part_b_plan_window' for f in facts)),
                'instruction': 'The exact Medicare Advantage initial enrollment opening/closing date '
                    'and window duration when Part B is added after Part A are unresolved. Do not '
                    'state, calculate, guess or confirm that deadline, including a date/duration '
                    'suggested by the user. Explain supported prerequisites and coverage starts '
                    'and continue with the approved question. Other enrollment clocks remain separate.'}

    def _read(self):
        catalog = json.loads((self.root / 'catalog.json').read_text())
        control = json.loads(self.controls.read_text())
        if (catalog['schema_version'] != 1 or control['purpose'] != 'general_education'
                or control['revision'] != catalog['revision']):
            raise ValueError('Unsupported knowledge revision or purpose')
        sources = {s['id']: s for s in catalog['sources']}
        return catalog, control, sources

    def _eligible(self, fact, control, sources, today):
        receipt = control.get('approved_facts', {}).get(fact['id'], {})
        if (fact['holds'] or fact['id'] in control.get('blocked_facts', [])
                or not receipt.get('reviewer') or not receipt.get('accepted_by')
                or receipt.get('digest') != approval_digest(fact, sources)
                or not (date.fromisoformat(receipt['accepted_on']) <= today
                        <= date.fromisoformat(fact['review_by']))):
            return False
        if not fact['source_ids'] or not fact['support']:
            return False
        for sid in fact['source_ids']:
            s = sources[sid]
            if s['status'] != 'captured' or sid in control.get('blocked_sources', []):
                return False
            for field, hash_field in [('raw_path', 'sha256'), ('text_path', 'text_sha256')]:
                path = (self.root / s[field]).resolve()
                if not path.is_relative_to(self.root.resolve()):
                    return False
                if hashlib.sha256(path.read_bytes()).hexdigest() != s[hash_field]:
                    return False
        for passage in fact['support']:
            if passage['source_id'] not in fact['source_ids']:
                return False
            s = sources[passage['source_id']]
            text = (self.root / s['text_path']).read_text()
            quote = text[passage['start']:passage['end']]
            if quote != passage['quote'] or hashlib.sha256(quote.encode()).hexdigest() != passage['sha256']:
                return False
        return True

    def select(self, message, *, state=None, year=2026, today=None, limit=3):
        """Match explanation topics, never infer a report, right or eligibility.

        Florida questions can receive an explicitly Florida-scoped explanation
        without recording that the speaker lives there. No semantic follow-up
        guess: an unmatched turn simply uses the existing reviewed evidence.
        """
        today = today or date.today()
        try:
            year = int(year)
            catalog, control, sources = self._read()
            if not self._active(control):
                return []
            query = ' ' + words(message or '') + ' '
            requested_years = {int(y) for y in re.findall(r'\b20\d{2}\b', message or '')}
            if requested_years and requested_years != {year}:
                return []
            ranked = []
            for fact in catalog['facts']:
                if year not in fact['coverage_years']:
                    continue
                if fact['jurisdiction'] == 'FL' and state != 'FL' and ' florida ' not in query:
                    continue
                matches = [a for a in fact['aliases'] if ' ' + words(a) + ' ' in query]
                if matches:
                    ranked.append((sum(len(words(a).split()) for a in matches), fact))
                elif _concept_match(fact['id'], query):
                    ranked.append((2, fact))
            ranked.sort(key=lambda item: (-item[0], item[1]['id']))
            selected = []
            for _, fact in ranked:
                if not self._eligible(fact, control, sources, today):
                    continue
                selected.append({'id': fact['id'], 'title': fact['title'],
                    'text': fact['text'], 'summary': fact['text'],
                    'conditions': fact['conditions'], 'jurisdiction': fact['jurisdiction'],
                    'coverage_years': fact['coverage_years'], 'review_by': fact['review_by'],
                    'kind': 'reviewed_general_education',
                    'sources': [{'url': sources[s]['url'], 'label': sources[s]['authority'] + ': ' + sources[s]['title']}
                                for s in fact['source_ids']],
                    'knowledge_digest': approval_digest(fact, sources)})
                if len(selected) >= min(max(limit, 1), 3):
                    break
            return selected
        except (OSError, ValueError, KeyError, TypeError):
            return []

    def current(self, receipts, *, today=None):
        """Recheck revocation/expiry after composition and on replay, without AI."""
        if not receipts:
            return True
        today = today or date.today()
        try:
            catalog, control, sources = self._read()
            if not self._active(control):
                return False
            facts = {f['id']: f for f in catalog['facts']}
            return all(identifier in facts
                       and receipt == approval_digest(facts[identifier], sources)
                       and self._eligible(facts[identifier], control, sources, today)
                       for identifier, receipt in receipts.items())
        except (OSError, ValueError, KeyError, TypeError):
            return False

    def status(self, *, today=None):
        """Read-only runtime evidence for the existing local status route."""
        today = today or date.today()
        try:
            catalog, control, sources = self._read()
            enabled = self._active(control)
            available = [f['id'] for f in catalog['facts']
                         if enabled and self._eligible(f, control, sources, today)]
            held = [f['id'] for f in catalog['facts']
                    if f['holds'] or f['id'] in control.get('blocked_facts', [])]
            return {'enabled': enabled, 'surface': self.surface,
                    'revision': catalog['revision'], 'purpose': control['purpose'],
                    'accepted_count': len(control.get('approved_facts', {})),
                    'available_count': len(available), 'held_fact_ids': held,
                    'held_claim_ids': self.response_limits().get('held_claim_ids', []),
                    'catalog_digest': digest(catalog), 'acceptance_digest': digest(control)}
        except (OSError, ValueError, KeyError, TypeError):
            return {'enabled': False, 'surface': self.surface,
                    'available_count': 0, 'state': 'unavailable'}
