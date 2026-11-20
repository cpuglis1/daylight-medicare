"""D183 wording breadth (lesson 27): the 16 plan-path profiles, offline.

For each profile, every person message (the opening and each scripted reply) is
sent through the real controller twice, with D183 off and on, with the same
scripted interpreter proposals and a stub composer. No network, no model.

The proposals are authored here from each profile's own ground truth, one per
meaning the old vocabulary checks gated (T05 current coverage, RC09 whose job,
RC04 Parts A and B, RC06 how they qualify, MG_AGE age). Each quote is the single
sentence of the message that states it, as a model quotes a span. The harness
uses word overlap only to pick that sentence; the product code never sees it.
What this measures: whether code accepts, confirms or rejects the same meaning
in the person's own words with the records on versus off. It does not measure
a live interpreter's reading.

Run: PYTHONPATH=tests python3 tests/replay_records_breadth.py <out.json>
"""
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

import test_conversation_records as base
import conversation_records as records

ROOT = Path(__file__).resolve().parents[3]
PROFILES = json.loads((ROOT / 'docs/evaluations/plan-paths-2026-11-12/profiles.json').read_text())
WORD = re.compile(r"[a-z0-9]+")


def sentences(text):
    return [s.strip() for s in re.split(r'(?<=[.!?])\s+', text or '') if s.strip()]


def best(text, hint):
    words = set(WORD.findall(hint.lower()))
    scored = sorted(sentences(text), key=lambda s: -len(words & set(WORD.findall(s.lower()))))
    return scored[0] if scored and words & set(WORD.findall(scored[0].lower())) else None


def coverage_choice(text):
    t = text.lower()
    for key, choice in (('cobra', 'cobra'), ('retiree', 'retiree'), ('employer', 'employer'), ('current job', 'employer'),
                        ('advantage', 'advantage'), ('medigap', 'medigap'), ('original medicare', 'original'),
                        ('marketplace', 'none'), ('none', 'none')):
        if key in t:
            return choice
    return None


def proposals(profile, message):
    """The meanings this message states, per the profile's ground truth."""
    truth, inputs = profile['ground_truth'], profile['expected_sorting']['inputs_to_capture']
    out = []
    cov = coverage_choice(str(inputs.get('current_coverage', '')))
    if cov:
        quote = best(message, str(inputs.get('current_coverage', '')) + ' insurance coverage plan job work')
        if quote:
            out.append(('T05', {'choice': cov}, quote))
            if cov in ('employer', 'cobra', 'retiree'):
                out.append(('RC09', {'choice': {'employer': 'my_job'}.get(cov, cov)}, quote))
    medicare = truth.get('medicare') or {}
    if medicare.get('part_a_start_date') or medicare.get('part_b_start_date'):
        quote = best(message, 'part a part b card medicare start started since')
        if quote and re.search(r'(?i)part [ab]|card|medicare', quote):
            both = bool(medicare.get('part_a_start_date') and medicare.get('part_b_start_date'))
            out.append(('RC04', {'choice': 'both' if both else 'a_only' if medicare.get('part_a_start_date') else 'b_only'}, quote))
            out.append(('RC06', {'choice': 'age65'}, quote))
    age = profile['person'].get('age')
    quote = best(message, '%s years old age turn turned birthday' % age)
    if age and quote and re.search(r'\b%s\b|\b6[0-9]\b|\b7[0-9]\b|birthday|turn' % age, quote, re.I):
        out.append(('MG_AGE', {'choice': str(age)}, quote))
    return out


def run(profile, records_on):
    case = base.RecordsJourney('test_optional_fields_wait_until_raised')
    case.setUp()
    if not records_on:
        case.flow.records_v1 = False
    role = profile['person'].get('relationship_to_typist', 'self')
    subject_choice = 'self' if role == 'self' else 'someone'
    counts = defaultdict(Counter)
    messages = [profile['opening_message']] + [item['reply'] for item in profile['response_script']]
    first = True
    for text in messages:
        ups = []
        if first:
            ups.append(case.update('RC01', {'choice': subject_choice}, sentences(text)[0] if sentences(text) else text))
            first = False
        for identifier, fields, quote in proposals(profile, text):
            ups.append(case.update(identifier, fields, quote))
        if not ups:
            continue
        try:
            extraction = case.read(text, updates=ups, task='')
            if not records_on:
                extraction.pop('next_target', None)        # not part of the interpreter contract with D183 off
            out = case.message(text, extraction=extraction, compose=case.ask_recommended())
        except Exception as error:          # a whole-turn failure is a result too
            for identifier, _, _ in [(u['id'], 0, 0) for u in ups]:
                counts[identifier]['turn_error:' + type(error).__name__] += 1
            continue
        got = {item['target']: item['status'] for item in out['metrics'].get('capture') or []}
        why = {item['target']: item['reason'] for item in out['metrics'].get('capture') or []}
        for update in ups:
            status = got.get(update['id'], 'not_reported')
            bucket = ('accepted' if status in ('accepted', 'already_known') else
                      'confirmed' if status in ('needs_clarification', 'conflicting') else
                      'rejected' if status == 'unsupported' else status)
            counts[update['id']][bucket] += 1
            if bucket != 'accepted':
                counts[update['id']]['reason:' + str(why.get(update['id']))] += 1
    case.doCleanups()
    return counts


def main(path):
    records.TODAY = date(2026, 11, 17)
    result = {'method': __doc__.strip().splitlines()[0], 'profiles': {}, 'totals': {}}
    totals = {'off': defaultdict(Counter), 'on': defaultdict(Counter)}
    for profile in PROFILES:
        row = {}
        for mode, flag in (('off', False), ('on', True)):
            counts = run(profile, flag)
            row[mode] = {k: dict(v) for k, v in counts.items()}
            for k, v in counts.items():
                totals[mode][k].update(v)
        result['profiles'][profile['id']] = row
    result['totals'] = {mode: {k: dict(v) for k, v in sorted(t.items())} for mode, t in totals.items()}
    Path(path).write_text(json.dumps(result, indent=1))
    print(json.dumps(result['totals'], indent=1))


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else '/tmp/records-breadth.json')
