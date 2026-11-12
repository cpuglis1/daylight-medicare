"""Fictional caregiver evaluation. One arm per process; no saved profile or retries."""
import argparse
import json
from pathlib import Path
import sys
import tempfile
import time
import uuid

PACKET = Path(__file__).resolve().parent
VARIANT = PACKET.parents[1] / 'alternatives/advisor-first'
sys.path.insert(0, str(VARIANT))
from server import build
from natural_flow import CONTEXT_POLICY
import natural_agent
import learner_review

MODEL = 'gpt-6.1-sol'
MAX_SENDS = 8
OPENING = ("I'm helping my mom review her Medicare. She's happy with her doctors "
           "but wants to understand whether her coverage still makes sense.")


def message(text):
    return {'type': 'message', 'message': text}


def answer(out, history):
    question = out['assessment'].get('nextQuestion') or {}
    target = question.get('id')
    if target == 'T05':
        return {'type': 'choice', 'id': 'T05', 'fields': {'choice': 'original,medigap'}}
    if target == 'RC01':
        return {'type': 'choice', 'id': 'RC01', 'fields': {'choice': 'someone'}}
    facts = {
        'T02': "I'm new to Medicare.",
        'T03': 'Her home ZIP is 34102.',
        'T06': 'She wants to keep Dr. Rivera at Example Clinic in Naples and Dr. Lee at Example Hospital in Tampa.',
        'T07': 'She takes Example Med 5 mg tablets and Example Med 10 mg tablets, as separate entries.',
        'T10': "Keeping both doctors and having predictable costs matter equally. She hasn't chosen one over the other.",
        'T09': "We don't have a cost target yet.",
        'T08': 'She does not need routine care while traveling.',
    }
    if target:
        text = facts.get(target)
        return message(text) if text and not any(row['action'] == message(text) for row in history) else None
    # Free-text responses only when the delivered text actually calls for them.
    question_text = (out['reply'].split('\n\n')[-1] if '?' in out['reply'].split('\n\n')[-1] else '').casefold()
    if any(word in question_text for word in ('understanding', 'familiar', 'know about', 'understand', 'think the supplement')):
        return message("I'm new to this. I don't know what the supplement does.")
    if any(phrase in question_text for phrase in ('besides the monthly price', 'in your own words',
            'what other costs', 'other costs would', 'besides the premium')):
        return message('I would check which bills she would have to pay a share of if she did not have it.')
    if 'where to find' in question_text or 'where to look' in question_text:
        return message('Yes, please help me find the premium notice.')
    return None


def run(arm):
    if arm != 'backend':
        # Isolate the intervention on the same app, model, facts and validators.
        start = natural_agent.COMPOSE_INSTRUCTIONS.index('When learner_review is present')
        end = natural_agent.COMPOSE_INSTRUCTIONS.index('Respect pause and direction changes.', start)
        natural_agent.COMPOSE_INSTRUCTIONS = (natural_agent.COMPOSE_INSTRUCTIONS[:start]
            + natural_agent.COMPOSE_INSTRUCTIONS[end:])
        learner_review.relevant = lambda *_: False
        original = natural_agent.NaturalAgent._extract_once
        def without_rubric(self, owner, text, guide, context, request, reservation):
            return original(self, owner, text, guide,
                {k: v for k, v in context.items() if k != 'learner_review'}, request, reservation)
        natural_agent.NaturalAgent._extract_once = without_rubric
        if arm == 'prompt':
            natural_agent.COMPOSE_INSTRUCTIONS += (
                '\nIn a caregiver review with reported Original Medicare and a supplement, '
                'find out what the learner understands about the supplement before moving on to ZIP '
                'if their understanding is unclear. If new, explain one idea: the supplement helps '
                'pay some of the share Original Medicare leaves. Link this to checking the monthly '
                'premium and costs when using care. One application question can help check the '
                'explanation. Move ahead when they show understanding. Honor a decline. When '
                'finishing a review, offer help finding a recent premium notice if useful.')
    receipts, history = [], []
    started = time.monotonic()
    report = {'arm': arm, 'model': MODEL, 'fictional': True, 'send_limit': MAX_SENDS, 'turns': history}
    path = PACKET / f'{arm}.json'
    with tempfile.TemporaryDirectory(prefix='learner-eval-', dir=VARIANT / 'var') as temporary:
        app = build(0, database=Path(temporary) / 'fictional.sqlite3')
        agent = app.adaptive.model_agents[MODEL]
        agent.connection_retries = 0
        reserve = agent.reserve_turn
        def bounded_reserve(stages=('extract', 'compose')):
            if len(receipts) + len(stages) > MAX_SENDS * 2:
                raise RuntimeError('Fictional evaluation stage ceiling reached.')
            result = reserve(stages=stages)
            receipts.extend(stage.key for stage in result.stages.values() if stage.key is not None)
            return result
        agent.reserve_turn = bounded_reserve
        owner = uuid.uuid4().hex
        guide, record = app.adaptive.initial()
        out = app.adaptive.turn(owner, {'guide': guide, 'record': record,
            'action': {'type': 'start'}, 'requestId': str(uuid.uuid4())})
        action = message(OPENING)
        try:
            for _ in range(MAX_SENDS):
                tick = time.monotonic()
                out = app.adaptive.turn(owner, {'guide': out['guide'], 'record': out['record'],
                    'continuation': out['continuation'], 'action': action, 'requestId': str(uuid.uuid4()),
                    'model': MODEL, 'aiProvider': 'OpenAI', 'aiConsent': True, 'contextPolicy': CONTEXT_POLICY})
                memory = app.adaptive.memory.learner_review(
                    owner, app.adaptive.current_chain[owner], CONTEXT_POLICY)
                row = {'action': action, 'reply': out.get('reply'), 'notice': out.get('notice'),
                    'question': (out['assessment'].get('nextQuestion') or {}).get('question'),
                    'target': (out['assessment'].get('nextQuestion') or {}).get('id'),
                    'learner_signal': memory['signal'], 'source_ids': out.get('advisor', {}).get('teachingFactIds', []),
                    'generated': out.get('generated'), 'elapsed_seconds': round(time.monotonic() - tick, 2)}
                history.append(row)
                path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
                print(json.dumps(row, ensure_ascii=False), flush=True)
                if (row['generated'] or {}).get('status') != 'complete':
                    report['stop'] = 'response not complete'
                    break
                action = answer(out, history)
                if not action:
                    report['stop'] = 'no applicable scripted answer to the delivered question'
                    break
            else:
                report['stop'] = 'send ceiling'
        finally:
            with agent.budget.db() as db:
                charges = [db.execute('SELECT charged,measured FROM ai_charges WHERE id=?',
                    (identifier,)).fetchone() for identifier in receipts]
            report['elapsed_seconds'] = round(time.monotonic() - started, 2)
            report['accounted_usd'] = sum(row[0] or 0 for row in charges if row) / 1e9
            report['measured_usd'] = sum(row[1] or 0 for row in charges if row) / 1e9
            path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
            app.server_close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('arm', choices=('baseline', 'prompt', 'backend'))
    run(parser.parse_args().arm)
