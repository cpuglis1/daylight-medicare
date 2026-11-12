"""One observable learning outcome for a caregiver reviewing current coverage."""
from hashlib import sha256
import re

OUTCOME = 'medigap_cost_sharing'
CONCEPT = 'medigap'
SOURCE = 'medigap'
ASPECT = 'cost_sharing_role'
SIGNALS = ('none', 'unfamiliar', 'unclear', 'applied', 'misconception', 'declined')
RUBRIC = {
    'outcome': OUTCOME,
    'goal': 'Explain why reviewing a supplement takes more than comparing monthly prices.',
    'applied': 'The learner explains that the supplement helps with some of the costs Original '
               'Medicare leaves, or applies that distinction to the coverage review.',
    'misconception': 'The learner says the supplement replaces Original Medicare, pays every bill, '
                     'or that the monthly price alone establishes the value of the coverage.',
    'source': SOURCE,
}
PROBE = 'What’s your understanding of what the supplement does? It’s fine if you’re starting from scratch.'
APPLY = 'If you were explaining this to the person you’re helping, what would you look at besides the monthly price?'
CONTINUE = 'Would it help to know where to find a recent premium notice for the supplement?'
LESSONS = {
    'teach': 'A Medicare supplement helps pay some of the share left after Original Medicare '
             'pays for covered care. To review the policy, look at the monthly price and what '
             'the policy helps pay when the person gets care.',
    'repair': 'Think of a bill for a visit Original Medicare covers. After Medicare pays its share, '
              'there may be a share left over. A supplement can help pay some of that share. '
              'The exact policy tells us what it helps pay.',
}


def relevant(role, goal):
    return role == 'someone' and goal == 'review'


def empty_record():
    return {'signal': 'none', 'evidence': '', 'probe': '', 'repaired': False, 'offered': False}


def validate_record(record):
    if (not isinstance(record, dict) or set(record) != set(empty_record())
            or record['signal'] not in SIGNALS or record['probe'] not in ('', 'initial', 'application')
            or any(type(record[key]) is not bool for key in ('repaired', 'offered'))
            or not isinstance(record['evidence'], str)
            or (record['evidence'] != '' if record['signal'] == 'none'
                else not re.fullmatch(r'[a-f0-9]{64}', record['evidence']))):
        raise ValueError('Use bounded learner review memory.')
    return dict(record)


def observation(proposal, message):
    """Bind a semantic proposal to the learner's actual words, without keeping a quote."""
    if not isinstance(proposal, dict) or set(proposal) != {'signal', 'subject', 'quote'}:
        return None
    signal, subject, quote = (proposal[k] for k in ('signal', 'subject', 'quote'))
    if (signal not in SIGNALS[1:] or subject != 'learner' or not isinstance(quote, str)
            or not quote.strip() or len(quote) > 360 or quote not in message):
        return None
    # An agreement, label or isolated fragment is insufficient for these judgments.
    if signal in ('applied', 'misconception') and len(re.findall(r"\b[\w’']+\b", quote)) < 5:
        return None
    return {'signal': signal, 'evidence': sha256(quote.encode()).hexdigest()}


def next_move(record, familiarity, delivered, observed=False):
    signal = record['signal']
    if signal in ('applied', 'declined'):
        return 'advance'
    if observed and signal in ('misconception', 'unclear', 'unfamiliar') and not record['repaired']:
        return 'repair' if delivered else 'teach'
    if not delivered and (signal in ('unfamiliar', 'unclear') or familiarity == 'new' or record['probe']):
        return 'teach'
    if not record['probe']:
        return 'probe'
    return 'advance'


def shape(core, step):
    """Use one reviewed move before the existing response grounding checks."""
    if not step or core.get('agenda_update', {}).get('pause') is True:
        return core
    mode = step['move']
    if mode == 'probe':
        return {**core, 'question_target': None, 'question': PROBE,
                'reply': 'That gives us a starting point for reviewing the current coverage.',
                'report_refs': [], 'evidence_refs': []}
    if mode in LESSONS:
        return {**core, 'question_target': None, 'question': APPLY, 'reply': LESSONS[mode],
                'report_refs': [], 'evidence_refs': [SOURCE]}
    if step['offer'] and not core.get('question_target'):
        return {**core, 'question': CONTINUE}
    return core
