"""Request-only context packing and value-free size measurements.

Canonical reports, candidates, evidence and visit memory are never mutated.
Tables retain every cell, including nulls and qualifiers. Mixed-shape rows stay
as objects so an absent property never silently becomes an explicit null.
"""
import copy
import json


def json_bytes(value):
    return len(json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode())


def _table(records):
    if (not isinstance(records, list) or len(records) < 2
            or any(not isinstance(row, dict) for row in records)):
        return records
    columns = list(records[0])
    if any(set(row) != set(columns) for row in records):
        return records
    table = {'columns': columns, 'rows': [[row[key] for key in columns] for row in records]}
    return table if json_bytes(table) < json_bytes(records) else records


def compact_context(content, *, claude=False):
    """Mutate only the caller's serialized-copy content, retaining stage scope."""
    for key in ('confirmed_context', 'resolved_context'):
        context = content.get(key)
        if not isinstance(context, dict):
            continue
        education = context.get('education_context')
        if isinstance(education, dict):
            # The composer can cite only facts supplied on this turn. Keep
            # every concept and delivery receipt, but omit unavailable aspect
            # evidence links from Claude's current teaching menu.
            concepts = education.get('catalog', {}).get('concepts')
            if claude and key == 'resolved_context' and isinstance(concepts, list):
                evidence = {fact['id'] for fact in context.get('evidence', [])}
                for concept in concepts:
                    if 'aspects' in concept:
                        concept['aspects'] = {
                            aspect: [ref for ref in refs if ref in evidence]
                            for aspect, refs in concept['aspects'].items()
                            if evidence.intersection(refs)}
            for section, field in (('catalog', 'concepts'), ('learning', 'covered')):
                block = education.get(section)
                if isinstance(block, dict) and field in block:
                    block[field] = _table(block[field])
        # Only the interpreter receives this compatibility lens. A sole current
        # report with an identical value already supplies the same information.
        safe = context.get('safeReports')
        reports = context.get('reports')
        if key == 'confirmed_context' and isinstance(safe, dict) and isinstance(reports, list):
            for name, value in list(safe.items()):
                matches = [row for row in reports if isinstance(row, dict)
                           and row.get('id') == 'guide.' + name]
                if (len(matches) == 1 and matches[0].get('status') in ('reported', 'derived')
                        and matches[0].get('value') == value):
                    del safe[name]
        if claude and key == 'resolved_context':
            # Preserve every guide statement and source reference.
            for guide in context.get('understanding_guides', []):
                guide['blocks'] = _table(guide['blocks'])
            # The renderer uses the original question contract. Drop only its
            # UI signature, repeated ID, and empty/default presentation fields.
            for candidate in content.get('question_candidates', []):
                question = candidate.get('question')
                if isinstance(question, dict):
                    question.pop('signature', None)
                    if question.get('id') == candidate.get('id'):
                        question.pop('id', None)
                    for field in ('why', 'choices', 'fields', 'multi', 'atomicRequests'):
                        if not question.get(field):
                            question.pop(field, None)
            work = context.get('task_work')
            if work:
                work['checks'] = _table(work['checks'])


def request_sizes(payload):
    """Byte measures only. Tokens come exclusively from the configured counter.

Component JSON byte measures are independent and need not sum to wire bytes.
No keys, values, identifiers, or raw text from the request enter the result.
"""
    output = {
        'payload_bytes': len(json.dumps(payload).encode()),
        'instructions_utf8_bytes': len(payload.get('instructions', '').encode()),
        'output_schema_json_bytes': json_bytes(payload.get('text', {})),
    }
    try:
        content = json.loads(payload['input'][0]['content'])
        if not isinstance(content, dict):
            return output
    except (KeyError, IndexError, TypeError, ValueError):
        return output
    key = 'confirmed_context' if 'confirmed_context' in content else 'resolved_context'
    context = content.get(key, {})
    if not isinstance(context, dict):
        return output
    output['stage'] = 'extract' if key == 'confirmed_context' else 'compose'
    output['input_json_bytes'] = json_bytes(content)
    for field in ('reports', 'safeReports', 'question_table', 'education_context',
                  'recent_exchanges', 'evidence', 'advisor_brief', 'resolved_changes', 'task_work'):
        if field in context:
            output[field + '_json_bytes'] = json_bytes(context[field])
    for field in ('question_candidates', 'reviewed_facts', 'field_rules'):
        if field in content:
            output[field + '_json_bytes'] = json_bytes(content[field])
    no_history = copy.deepcopy(payload)
    baseline = copy.deepcopy(content)
    if 'recent_exchanges' in context:
        baseline[key]['recent_exchanges'] = []
    no_history['input'][0]['content'] = json.dumps(baseline, ensure_ascii=False, separators=(',', ':'))
    output['zero_history_payload_bytes'] = len(json.dumps(no_history).encode())
    return output
