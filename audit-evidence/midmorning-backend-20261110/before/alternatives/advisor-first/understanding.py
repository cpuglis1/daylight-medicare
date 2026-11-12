"""Versioned teaching and preparation for the three first-transition problems.

The registry pins existing educational statements, not new source acceptance.
The same guide definitions are supplied to composition and rendered by the UI.
Personal rules, calculations and completion require their separate authority.
No retrieval, profile writes, model calls or stored dialogue occur here.
"""
from __future__ import annotations

import copy
from datetime import date, datetime
import hashlib
import json
from pathlib import Path
import re
from zoneinfo import ZoneInfo

VERSION = 'understanding-20261103-r1'
HERE = Path(__file__).resolve().parent
FILES = ('understanding-catalog.json', 'web/teaching-facts.json', 'advisor-evidence.json')
VISUAL_CAPABILITIES = {'transition': 'transition', 'routes': 'coverage_paths',
    'original': 'coverage_paths', 'advantage': 'coverage_paths', 'costs': 'costs'}
MONTH = re.compile(r'\b(?:january|february|march|april|may|june|july|august|september|october|november|december)\b|\b\d{4}-\d{2}(?:-\d{2})?\b', re.I)


class UnderstandingError(ValueError):
    """Fixed codes only, without source or personal values."""


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
        ensure_ascii=False, allow_nan=False).encode()).hexdigest()


class UnderstandingRegistry:
    def __init__(self, root=HERE):
        self.root = Path(root)

    def load(self):
        """Check exact bytes on every use, including cached-turn replay."""
        try:
            lock = json.loads((self.root / 'understanding-lock.json').read_text())
            if (set(lock) != {'version', 'files'} or lock['version'] != VERSION
                    or set(lock['files']) != set(FILES)):
                raise UnderstandingError('UNDERSTANDING_LOCK_INVALID')
            content = {}
            for name in FILES:
                raw = (self.root / name).read_bytes()
                if hashlib.sha256(raw).hexdigest() != lock['files'][name]:
                    raise UnderstandingError('UNDERSTANDING_SOURCE_CHANGED')
                content[name] = json.loads(raw)
            catalog = content['understanding-catalog.json']
            if (catalog['version'] != VERSION or catalog['coverage_year'] != 2026
                    or set(catalog['capabilities']) != {'transition', 'coverage_paths', 'costs'}):
                raise UnderstandingError('UNDERSTANDING_CATALOG_INVALID')
            facts = {}
            for name in FILES[1:]:
                for fact in content[name]['facts']:
                    if fact['id'] in facts:
                        raise UnderstandingError('UNDERSTANDING_FACT_AMBIGUOUS')
                    facts[fact['id']] = fact
            for capability in catalog['capabilities'].values():
                if any(identifier not in facts for identifier in capability['fact_ids']):
                    raise UnderstandingError('UNDERSTANDING_EVIDENCE_MISSING')
            return catalog, facts, _digest(lock)
        except UnderstandingError:
            raise
        except (OSError, ValueError, TypeError, KeyError):
            raise UnderstandingError('UNDERSTANDING_REGISTRY_UNAVAILABLE') from None

    def inventory(self):
        catalog, facts, binding = self.load()
        ids = sorted({ref for c in catalog['capabilities'].values() for ref in c['fact_ids']})
        claims = []
        for ref in ids:
            fact = facts[ref]
            source_file = 'advisor-evidence.json' if ref in {'enrollment_intro', 'cobra_timing'} else 'web/teaching-facts.json'
            claims.append({'claim_id': ref, 'retained_statement': fact['text'],
                'local_evidence': {'path': source_file, 'locator': 'facts[id=' + ref + '].text'},
                'official_source_urls': list(dict.fromkeys(
                    ([fact['source']] if fact.get('source') else []) +
                    [source['url'] for source in fact.get('sources', [])])),
                'scope': 'general_education', 'exceptions_and_conditions': 'preserved_in_retained_statement',
                'review_state': 'incumbent_project_teaching_not_new_independent_review',
                'permitted_uses': ['general_education'], 'personal_use': 'held',
                'effective_period': 'general_teaching_in_2026_pilot_not_a_personal_rule_release',
                'review_due': catalog['review_due']})
        return {'version': VERSION, 'registry_binding': binding,
            'coverage_year': catalog['coverage_year'],
            'source_kind': 'retained_project_educational_statements',
            'official_quotation_verified_by_this_registry': False,
            'capabilities': copy.deepcopy(catalog['capabilities']),
            'claims': claims, 'fact_count': len(ids),
            'personal_purposes': 'held'}

    def guides(self, evidence_ids, *, today=None):
        """Public, non-personal guide vocabulary for the current evidence only."""
        catalog, facts, binding = self.load()
        today = datetime.now(ZoneInfo('America/New_York')).date() if today is None else today
        if type(today) is not date or today >= date.fromisoformat(catalog['review_due']):
            raise UnderstandingError('UNDERSTANDING_REVIEW_DUE')
        if (not isinstance(evidence_ids, (list, tuple)) or len(evidence_ids) > 64
                or any(not isinstance(ref, str) for ref in evidence_ids)):
            raise UnderstandingError('UNDERSTANDING_EVIDENCE_INVALID')
        available = set(evidence_ids)
        output = []
        for key, capability in catalog['capabilities'].items():
            refs = [ref for ref in capability['fact_ids'] if ref in available]
            if not refs:
                continue
            blocks = []
            for definition in capability['blocks']:
                alternatives = [definition['evidence_refs'], *definition.get('alternative_support', [])]
                support = next((candidate for candidate in alternatives if set(candidate) <= available), None)
                if support:
                    block = copy.deepcopy(definition)
                    block.pop('alternative_support', None)
                    block['evidence_refs'] = list(support)
                    blocks.append(block)
            sources = []
            for ref in refs:
                fact = facts[ref]
                links = ([{'url': fact['source'], 'label': fact['title']}] if fact.get('source') else []) + fact.get('sources', [])
                for source in links:
                    if source['url'] not in {item['url'] for item in sources}:
                        sources.append({'url': source['url'], 'label': source.get('label', fact['title'])})
            output.append({'version': VERSION, 'registry_binding': binding,
                'capability': key, 'title': capability['title'], 'coverage_year': 2026,
                'purpose': 'general_education', 'state': 'educational',
                'evidence_refs': refs, 'blocks': blocks, 'sources': sources,
                'personal_result': None, 'personal_authority': 'held',
                'review_due': catalog['review_due']})
        return output

    def composition_guides(self, evidence_ids):
        # Reuse the exact blocks while keeping hashes, source duplicates and
        # maintenance metadata out of the model's bounded factual context.
        return [{key: guide[key] for key in ('capability', 'title', 'blocks')}
                for guide in self.guides(evidence_ids)]


def reported_dates(rows):
    """Preserve source-native precision and preference/actual-date meaning."""
    if not isinstance(rows, list):
        return []
    current = [row for row in rows if isinstance(row, dict) and row.get('status') == 'reported']
    output = []

    def add(row, label, value, field=None):
        if not isinstance(value, str) or len(value) > 200 or not MONTH.search(value):
            return
        entry = {'label': label, 'value': value, 'state': 'reported',
                 'report_ref': row['id'] + ('.' + field if field else '')}
        if entry not in output:
            output.append(entry)

    for row in current:
        if row.get('id') == 'S_AGE65':
            add(row, '65th birthday', row.get('value'))
    starts = [row for row in current if row.get('id') == 'T04']
    preferred = next((row for row in starts if row.get('label') == 'Preferred coverage start'
                      and isinstance(row.get('value'), str) and MONTH.search(row['value'])), None)
    if preferred is None:
        preferred = next((row for row in starts if isinstance(row.get('value'), str)
                          and MONTH.search(row['value'])), None)
    if preferred:
        add(preferred, 'Preferred coverage start', preferred['value'])
    for row in current:
        if row.get('id') == 'RC11' and isinstance(row.get('value'), dict):
            for field, label in (('jobEnd', 'Job end'), ('coverageEnd', 'Insurance end')):
                add(row, label, row['value'].get(field), field)
    return output


def attach_understanding(out, *, registry=None, historical=False):
    """Attach one explicitly requested, supported guide after turn resolution.

    Citation alone never selects a visual. A failed turn or a historical replay
    cannot produce a new guide. The caller owns session/profile authentication.
    """
    out.pop('understanding', None)
    if historical or out.get('generated', {}).get('status') == 'unavailable':
        return out
    advisor = out.get('advisor', {})
    visual = advisor.get('visual', 'none')
    capability = VISUAL_CAPABILITIES.get(visual)
    if capability is None:
        return out
    refs = advisor.get('teachingFactIds', []) or [fact['id'] for fact in out.get('facts', [])
        if isinstance(fact, dict) and isinstance(fact.get('id'), str)]
    if not refs:
        out['understanding'] = {'version': VERSION, 'state': 'unavailable', 'visual': None}
        return out
    try:
        guide = next((item for item in (registry or UnderstandingRegistry()).guides(refs)
                      if item['capability'] == capability), None)
    except UnderstandingError:
        # An optional guide may fail closed without dropping valid reports.
        out['understanding'] = {'version': VERSION, 'state': 'unavailable', 'visual': None}
        return out
    if guide is None or not guide['blocks']:
        # Explicitly own suppression too: legacy client mappings must not add
        # richer concepts when this registry lacks support for the intent.
        out['understanding'] = {'version': VERSION, 'state': 'unavailable', 'visual': None}
        return out
    guide['visual'] = visual
    if capability == 'coverage_paths':
        guide['blocks'] = [block for block in guide['blocks']
            if visual == 'routes' or block.get('route') in {None, visual}]
    if capability == 'transition':
        guide['reported_dates'] = reported_dates(out.get('reportedRows', []))
        guide['date_basis'] = 'reported_only_no_personal_window_calculated'
        guide['open_checks'] = [
            'Confirm which enrollment rules apply to your existing coverage.',
            'Confirm enrollment and the actual Medicare coverage start with Social Security.']
    if capability == 'costs' and 'costs' in refs:
        # Optional local teaching example. It is excluded from model evidence,
        # reports and comparisons; invented figures never become Medicare data.
        from understanding_scenarios import cost_example
        guide['fictional_examples'] = [cost_example(2), cost_example(12)]
    guide['snapshot_binding'] = _digest({'guide_revision': out.get('guide', {}).get('stateVersion'),
        'record_revision': out.get('record', {}).get('stateVersion'),
        'reported_dates': guide.get('reported_dates', [])})
    out['understanding'] = guide
    return out
