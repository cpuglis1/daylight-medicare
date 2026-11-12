"""Tentative, evidence-linked learner observations. Never a dialogue router."""
import copy

from education import catalog_context

VERSION = 'learner-observations-v1'
TURN_LIMIT = 3
MEMORY_LIMIT = 12
SIGNALS = ('unfamiliar', 'self_reported_familiar', 'uncertain', 'misconception', 'applied', 'skip')


def _valid(item, concepts):
    if not isinstance(item, dict) or set(item) != {
            'concept_id', 'aspect_ids', 'signal', 'subject', 'quote', 'interpretation'}:
        return False
    concept = item['concept_id']
    if (not isinstance(concept, str) or concept not in concepts
            or not isinstance(item['signal'], str) or item['signal'] not in SIGNALS
            or item['subject'] != 'learner'):
        return False
    aspects = item['aspect_ids']
    return (isinstance(aspects, list) and len(aspects) <= 3
        and all(isinstance(a, str) and a in concepts[concept]['aspects'] for a in aspects)
        and len(set(aspects)) == len(aspects)
        and all(isinstance(item[key], str) and item[key].strip() and len(item[key]) <= limit
                for key, limit in (('quote', 240), ('interpretation', 160))))


def observations(proposals, message):
    """Validate provenance and vocabulary, not the model's semantic judgment."""
    concepts = {item['concept_id']: item for item in catalog_context()['concepts']}
    if not isinstance(proposals, list) or len(proposals) > TURN_LIMIT:
        return []
    return [copy.deepcopy(item) for item in proposals if _valid(item, concepts)
            and item['quote'] in message]


def empty_record():
    return {'version': VERSION, 'observations': []}


def validate_record(record):
    concepts = {item['concept_id']: item for item in catalog_context()['concepts']}
    if (not isinstance(record, dict) or set(record) != {'version', 'observations'}
            or record['version'] != VERSION or not isinstance(record['observations'], list)
            or len(record['observations']) > MEMORY_LIMIT
            or any(not _valid(item, concepts) for item in record['observations'])):
        raise ValueError('Use bounded learner observations.')
    return copy.deepcopy(record)


def merge(record, updates):
    record = validate_record(record)
    for item in updates:
        # A later observation revises only the same scope. Knowing premiums
        # does not erase uncertainty about deductibles, even in one concept.
        scope = (item['concept_id'], set(item['aspect_ids']))
        record['observations'] = [old for old in record['observations']
            if (old['concept_id'], set(old['aspect_ids'])) != scope]
        record['observations'].append(copy.deepcopy(item))
    record['observations'] = record['observations'][-MEMORY_LIMIT:]
    return validate_record(record)


def context(record):
    return {**validate_record(record), 'assessment_is_tentative': True,
            'observations_are_chronological': True,
            'unobserved_is_unknown': True}
