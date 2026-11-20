"""Pending-question breadth (lesson 27): the 16 plan-path profiles, offline.

Every person message of each profile goes through the real controller twice,
records on both times, with the pending switch off and on. The interpreter is
the same scripted stub as replay_records_breadth.py (its `proposals`), which
reports only a few meanings and never sends pending_disposition. So with the
switch on, a question the stub does not answer is read as a detour every time:
this is the worst case for repeats, not a picture of a live interpreter.

Counts per mode: questions delivered more than once, deliveries that were a
return after a detour, questions parked at the end, offer buttons shown, and
whole-turn errors. No network, no model.

Run: PYTHONPATH=tests:. python3 tests/replay_pending_breadth.py <out.json>
"""
import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path

import test_conversation_records as base
import conversation_records as records
import conversation_planner as planner
from replay_records_breadth import PROFILES, proposals, sentences


def run(profile, pending):
    case = base.RecordsJourney('test_optional_fields_wait_until_raised')
    case.setUp()
    if pending:
        records.enable_pending(case.flow)
    role = profile['person'].get('relationship_to_typist', 'self')
    delivered, returns, offers, errors, turns = Counter(), 0, Counter(), 0, 0
    first = True
    for text in [profile['opening_message']] + [item['reply'] for item in profile['response_script']]:
        ups = []
        if first:
            ups.append(case.update('RC01', {'choice': 'self' if role == 'self' else 'someone'},
                                   sentences(text)[0] if sentences(text) else text))
            first = False
        ups += [case.update(i, fields, quote) for i, fields, quote in proposals(profile, text)]
        try:
            out = case.message(text, extraction=case.read(text, updates=ups, task=''), compose=case.ask_recommended())
        except Exception:
            errors += 1
            continue
        turns += 1
        q = out['assessment'].get('nextQuestion')
        if q:
            delivered[(q['id'], tuple(f['key'] for f in q.get('fields', [])))] += 1
        trace = out['metrics'].get('records') or {}
        returns += bool(trace.get('returned'))
        for card in out.get('cards') or []:
            if card.get('kind') == 'next_step_offer':
                offers[card['actions'][0]['label']] += 1
    parked = sorted({row['question_id'] for row in out.get('questionProgress') or [] if row['state'] == 'parked'}) if turns else []
    state = planner.state(case.flow, case.owner)
    passes = sum(r.get('passes', 0) for r in state.get('question_progress', {}).values())
    case.doCleanups()
    return {'turns': turns, 'turn_errors': errors, 'questions_delivered': sum(delivered.values()),
            'distinct_questions': len(delivered),
            'delivered_more_than_once': sum(1 for n in delivered.values() if n > 1),
            'max_deliveries_of_one_question': max(delivered.values(), default=0),
            'returns_after_detour': returns, 'parked': parked, 'passes': passes,
            'offer_buttons': sum(offers.values()), 'offers_repeated': sum(1 for n in offers.values() if n > 1)}


def main(path):
    records.TODAY = date(2026, 11, 18)
    result = {'method': __doc__.strip().splitlines()[0], 'profiles': {}, 'totals': {}}
    for profile in PROFILES:
        result['profiles'][profile['id']] = {mode: run(profile, flag) for mode, flag in (('off', False), ('on', True))}
    for mode in ('off', 'on'):
        rows = [row[mode] for row in result['profiles'].values()]
        result['totals'][mode] = {key: sum(len(r[key]) if key == 'parked' else r[key] for r in rows)
                                  for key in rows[0] if key != 'max_deliveries_of_one_question'}
        result['totals'][mode]['max_deliveries_of_one_question'] = max(r['max_deliveries_of_one_question'] for r in rows)
    Path(path).write_text(json.dumps(result, indent=1))
    print(json.dumps(result['totals'], indent=1))


if __name__ == '__main__':
    main(sys.argv[1])
