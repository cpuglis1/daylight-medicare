"""D157: where the UX-pass helpers meet the conversation controller.

``natural_flow.NaturalConversation`` calls four functions here: ``refine``
(which questions may be asked, in what order), ``target`` (the one question a
find-mode turn must ask), ``brief`` (what the model is told) and ``finish``
(what code adds or tidies after the model has written). Every function is
defensive: a failure here never fails a turn.

The model still writes the reply. Dates, cards, the coverage path and what is
left before a tab are computed here from resolved reports only.
"""
import copy
from datetime import date
import logging
import os
import re

from adaptive_flow import metadata
from applicable_rules import floor_statement
import enrollment_flow
import medigap_profile
import conversation_planner
import ux_pass

LOGGER = logging.getLogger(__name__)
PATH_FIELD = 'intent.coveragePath'
TODAY = None   # tests pin the calendar; production uses the real date
# Operational switch: DAYLIGHT_DISABLE_UX_PASS=1 turns every hook below into a
# no-op (the conversation then behaves as it did before D157). Restart to apply.
def disabled():
    return bool(os.environ.get('DAYLIGHT_DISABLE_UX_PASS'))
NEXT_LINE = 'A few questions about your situation, then your options.'
# Closest-to-plans order for a person who asked for their options (CV-02, CV-25).
FIND_ORDER = ('RC01', 'T03', 'T05', 'S_AGE65', 'RC04', 'T10', 'T09', 'MG_AGE', 'MG_SEX', 'MG_TOBACCO',
              'T06', 'T07', 'T08', 'RC02', 'RC03')
TIMING_ASK = re.compile(r"(?i)\bwhen (?:do|does|can|will|should|would)\b[^?]*\b(?:start|sign|enroll|begin|apply)|"
                        r"\b(?:deadline|sign[- ]up window|enrollment (?:window|period)|how long do i have)\b")
MEDIGAP_MENTION = re.compile(r"(?i)\bmedigap\b|\bsupplement\b|\bplan [fgn]\b")
# Both paths named in one message, and a request for Daylight's own pick (15-profile run, November 13, 2026).
BOTH_PATHS = re.compile(r"(?is)(?=.*\b(?:advantage|hmo|ppo)\b)(?=.*\b(?:original medicare|regular medicare|medigap|supplement|plan [gn])\b)")
RECOMMEND_ASK = re.compile(r"(?i)\b(?:would you (?:actually |really )?recommend|what (?:do|would) you recommend|do you recommend|"
                           r"what would you (?:do|pick|choose)|which (?:one )?would you (?:pick|choose)|"
                           r"should (?:i|we|he|she) (?:just )?(?:leave|switch|stay|keep|change))\b")
# Owner sign-off November 13, 2026.
NO_PICK = 'I can’t make that choice for you here. This is how each path fits what you told me.'
READY = {'medigap': ('Your Medigap prices are ready.', 'See your Medigap prices', 'supplement'),
         'part_d': ('Your drug plans are ready.', 'See your Part D drug plans', 'part-d'),
         'advantage': ('Your Medicare Advantage plans are ready.', 'See Medicare Advantage plans', 'advantage')}
ON_MEDICARE = frozenset({'original', 'advantage', 'medigap', 'drug'})


def today():
    return TODAY or date.today()


def register(flow):
    """One additive profile field; the pinned contract file is not edited."""
    node = next(node for node in flow.contract['nodes'] if node['id'] == 'R00')
    if PATH_FIELD not in node['writes']:
        node['writes'] = [*node['writes'], PATH_FIELD]
    flow.ux = ux_pass.VisitLedger()


def _chain(flow, owner):
    return flow.current_chain.get(owner)


def _coverage(flow, g):
    return set(flow.value(g, 'coverage.current') or [])


def _priorities(flow, g):
    return set(flow.value(g, 'needs.priorities') or [])


def cost_preference(flow, g):
    stated = flow.value(g, 'needs.costPreference')
    if stated in ('predictable', 'lower_monthly'):
        return stated
    priorities = _priorities(flow, g)
    # "Predictable costs" picked alone is already the answer to the balance
    # question; both together need the one tie-break (CV-05, CV-24).
    if 'bills' in priorities and 'total_cost' not in priorities:
        return 'predictable'
    return None


def timing(flow, g, r):
    return ux_pass.enrollment_timing(flow.value(g, 'situation.age65'), today(),
                                     flow.report(r, 'RC04').get('choice'))


def path(flow, owner, g, r):
    if conversation_planner.enabled(flow):
        return conversation_planner.path(flow, owner, g, r)
    travel = flow.value(g, 'needs.travel')
    travel = next((item for item in (travel if isinstance(travel, list) else [travel])
                   if item in ('elsewhere_us', 'outside_us')), None)
    chosen = flow.value(g, PATH_FIELD)
    # D161: "Parts A and B only" is the Original Medicare path for navigation.
    chosen = {'original_only': 'original_medigap'}.get(chosen, chosen)
    lean = ux_pass.coverage_path(chosen=chosen if chosen in ux_pass.PATHS else None,
                                 cost_preference=cost_preference(flow, g), travel=travel,
                                 task=metadata(r)['task'])
    start = flow.value(g, enrollment_flow.START_FIELD) if enrollment_flow.enabled(flow) else None
    if lean['state'] != 'chosen' and start in enrollment_flow.STARTS:
        # The person tapped where to start. It is a lean they set themselves, never a choice.
        if start == 'both':
            return {'state': 'undecided', 'path': None, 'because': []}
        return {'state': 'leaning', 'path': start, 'because': lean['because'] if lean['path'] == start else []}
    return lean


def _candidate(flow, g, r, identifier, purpose, priority=1):
    question = flow.contextual_question(g, r, flow.question(identifier))
    if not question:
        return None
    question = copy.deepcopy(question)
    reason = ux_pass.question_reason(identifier)
    if reason:
        question['why'] = reason
    return {'id': identifier, 'question': question, 'topic': '', 'priority': priority, 'required': False,
            'purpose': purpose}


def refine(flow, owner, g, r, candidates):
    """Ask, use, show: drop questions whose answer changes nothing; add the
    ones the person's path needs; order by what gets them to their plans."""
    if conversation_planner.enabled(flow):
        return conversation_planner.refine(flow, owner, g, r, candidates)
    if disabled():
        return candidates
    try:
        if not isinstance(candidates, list) or any(item.get('required') for item in candidates):
            return candidates
        if metadata(r).get('editing'):
            return candidates
        role = flow.value(g, 'subject.role')
        coverage = _coverage(flow, g)
        priorities = _priorities(flow, g)
        when = timing(flow, g, r)
        view = flow.ux.view(owner, _chain(flow, owner))
        lean = path(flow, owner, g, r)
        in_window = bool(when and when['iep']['phase'] != 'after')
        kept = []
        for item in candidates:
            identifier = item['id']
            # CV-01: familiarity is not a step toward anyone's plans.
            if identifier == 'T02':
                continue
            # CV-07: a COBRA end date changes nothing the person sees.
            if identifier == 'RC11' and 'cobra' in coverage and 'employer' not in coverage:
                continue
            # CV-11: with no coverage from current work, "when would you like
            # Medicare to start" is not a real choice inside the first window.
            if identifier == 'T04' and coverage and 'employer' not in coverage and (in_window or not flow.value(g, 'situation.age65')):
                continue
            # CV-24: never ask the cost balance twice.
            if identifier == 'T09' and cost_preference(flow, g):
                continue
            kept.append(item)
        ids = {item['id'] for item in kept}

        def add(identifier, purpose, priority=1):
            if identifier in ids:
                for item in kept:
                    if item['id'] == identifier:
                        item['priority'] = min(item['priority'], priority)
                        item['purpose'] = purpose
                return
            item = _candidate(flow, g, r, identifier, purpose, priority)
            if item:
                kept.append(item)
                ids.add(identifier)

        dispositions = {**metadata(r).get('baselineDispositions', {}), **r.get('dispositions', {})}
        # CV-06: the 65th-birthday month, early and with its reason, for anyone
        # not already on Medicare. It also gives Medigap its pricing age.
        if (role and not flow.value(g, 'situation.age65') and 'S_AGE65' not in dispositions
                and not coverage & ON_MEDICARE and flow.report(r, 'RC04').get('choice') != 'both'):
            # Early in a general conversation; never ahead of a detail the
            # person is in the middle of giving for a specific check.
            general = metadata(r)['task'] in ('', 'learn', 'compare', 'timing', 'review', 'unresolved', 'medigap')
            add('S_AGE65', 'Ask the month and year of the 65th birthday and give the reason in the same sentence: '
                           'it sets the sign-up window and when coverage can start. One question only.',
                0.5 if general else 2)
        # CV-05: both cost priorities picked: one tie-break, with its reason.
        if ({'total_cost', 'bills'} <= priorities and not flow.value(g, 'needs.costPreference')
                and 'T09' not in dispositions):
            add('T09', 'The person picked both total cost and predictable costs, which can pull in opposite '
                       'directions. Say that in one line, then ask which matters more. Ask once.', 0)
            for item in kept:
                if item['id'] == 'T09':
                    item['question'] = {**item['question'], 'why': 'Total cost and predictable costs can pull in '
                                        'opposite directions, so this sets which comes first.'}
        # CV-28: ask the Medigap pricing details in the conversation, one at a
        # time with the reason, as soon as the person leans that way or asks
        # for plans or prices. Never announce a missing detail.
        if role and (lean['path'] == 'original_medigap' or view['find_mode']) and not coverage & {'advantage'}:
            pricing = medigap_profile.profile(g)
            if pricing['status'] == 'missing' and flow.value(g, 'comparison.scope.zip'):
                for identifier in pricing['missing']:
                    if identifier in medigap_profile.FIELDS and identifier not in pricing['held']:
                        if identifier == 'MG_AGE' and 'S_AGE65' in ids:
                            continue
                        add(identifier, 'Ask this Medigap pricing detail naturally, with its reason in the same '
                                        'sentence. Do not say a detail is missing; ask for it.', 1)
        for item in kept:
            reason = ux_pass.question_reason(item['id'])
            if reason and isinstance(item.get('question'), dict) and not item['question'].get('why'):
                item['question'] = {**item['question'], 'why': reason}
        if view['find_mode']:
            order = {identifier: index for index, identifier in enumerate(FIND_ORDER)}
            kept.sort(key=lambda item: (0 if item['priority'] == 0 else 1,
                                        order.get(item['id'].split('.')[0], len(order))))
        else:
            kept.sort(key=lambda item: item['priority'])
        chain = _chain(flow, owner)
        kept = [item for item in kept if not flow.ux.parked(owner, chain, question_key(item.get('question') or item))]
        return kept[:12]
    except Exception:   # never fail a turn over ordering
        LOGGER.warning('Daylight ux refine skipped', exc_info=True)
        return candidates


def question_key(question):
    """One key per question meaning, for the two-shows-then-park budget."""
    return '%s|%s' % (str((question or {}).get('id') or '').split('.')[0], (question or {}).get('entity') or 'profile')


def target(flow, owner, g, r, moves, required_id, required_reason):
    """In find mode the turn asks the first open question on the way to plans."""
    if conversation_planner.enabled(flow):
        return conversation_planner.target(flow, owner, g, r, moves, required_id, required_reason)
    if disabled():
        return required_id, required_reason
    try:
        if required_reason in ('clarification', 'pending', 'current_conversation_check'):
            return required_id, required_reason
        view = flow.ux.view(owner, _chain(flow, owner))
        open_tiebreak = next((item['id'] for item in moves if item['id'] == 'T09' and item.get('priority') == 0), None)
        if open_tiebreak:
            return open_tiebreak, 'tie_break'
        if view['find_mode'] and moves and not (required_reason or '').startswith('rule:'):
            order = {identifier: index for index, identifier in enumerate(FIND_ORDER)}
            first = min(moves, key=lambda item: order.get(item['id'].split('.')[0], len(order)))
            return first['id'], 'find_mode'
    except Exception:
        LOGGER.warning('Daylight ux target skipped', exc_info=True)
    return required_id, required_reason


def note_message(flow, owner, g, message, submitted_answer=None, r=None):
    """Read intent from the person's own words before the reply is composed."""
    if conversation_planner.enabled(flow):
        return conversation_planner.note_message(flow, owner, g, message, submitted_answer, r)
    if disabled():
        return
    try:
        chain = _chain(flow, owner)
        if submitted_answer is None and ux_pass.find_intent(message, enrollment_flow.enabled(flow)):
            flow.ux.set_find_mode(owner, chain)
        chosen = ux_pass.path_from_text(message) if submitted_answer is None else None
        if chosen and flow.value(g, PATH_FIELD) != chosen:
            flow.put(g, PATH_FIELD, chosen, 'user_text')
        if submitted_answer is None and r is not None and enrollment_flow.enabled(flow):
            # D161: "I applied", "Part B starts December 1", "Parts A and B only".
            enrollment_flow.capture(flow, g, r, message)
            enrollment_flow.note_asked(flow, g, message)
    except Exception:
        LOGGER.warning('Daylight ux intent skipped', exc_info=True)


CARD_MENTION = re.compile(r'(?i)\bcard\b')
TIMING_WORD = re.compile(r'(?i)timing|sign[- ]?up|window|enroll|start')
REVIEW_STEP = re.compile(r'(?i)\breview your info(?:rmation)?\b|\bth(?:at|e) review\b')


def _timing_card(flow, owner, g, r, message):
    """The timing card this turn carries, or None. One rule decides both what
    the model is told and what software attaches (live run, November 12,
    2026: the model announced a card that was not there)."""
    chain = _chain(flow, owner)
    coverage = _coverage(flow, g)
    when = timing(flow, g, r)
    if not when or coverage & ON_MEDICARE:
        return None
    said = [point for point in ('cobra_trap',) if flow.ux.said(owner, chain, point)]
    card = ux_pass.timing_card(when, coverage, said)
    parts = flow.report(r, 'RC04').get('choice')
    automatic = parts in ('neither', 'a_only') and 'employer' not in coverage
    if card and (TIMING_ASK.search(message or '')
                 or automatic and not flow.ux.shown(owner, chain, 'enrollment_timing')):
        if when['first_day_assumed']:
            card['footnote'] = 'Born on the 1st of the month? Tell me and I’ll move these dates a month earlier.'
        return card
    return None


def brief(flow, owner, g, r, context, moves, message=''):
    """What the model is told: mode, what was already said, what code will show."""
    if conversation_planner.enabled(flow):
        return conversation_planner.prepare(flow, owner, g, r, moves, context)
    if disabled():
        return context
    try:
        view = flow.ux.view(owner, _chain(flow, owner))
        when = timing(flow, g, r)
        lean = path(flow, owner, g, r)
        pages = context.get('plans_pages') or flow.plans_pages(g, r)
        context['conversation_state'] = {
            'mode': 'find' if view['find_mode'] else 'teach',
            'already_said': sorted(view['points']),
            'coverage_path': {'state': lean['state'], 'path': lean['path']},
            'left_before_plans': (_left(flow, g, r, lean, pages) or {}).get('text', ''),
            'already_taught': list(metadata(r).get('journey', {}).get('learningSeen', [])),
            'cards_already_shown': list(view['cards']),
            'software_cards': (
                {'enrollment_timing': True,
                 'note': ('Software shows a card under this reply with this person’s sign-up window, Part A and '
                          'Part B start dates and Medigap window, computed from their reports. Introduce it in '
                          'one clause. Never restate, compute or change its dates.')}
                if _timing_card(flow, owner, g, r, message) else
                {'enrollment_timing': False,
                 'note': 'No timing card is attached to this reply. Do not mention a card.'}),
            'rules': [
                'mode find: the person asked for their options. Stop teaching the curriculum. Ask only the next '
                'missing detail or decision; never offer a menu of topics.',
                'already_said lists points this visit has delivered. Do not say them again unless the person '
                'asks; refer back in a clause at most.',
                'already_taught lists lessons the person has already read; do not teach them again.',
                'cards_already_shown lists cards the person already has above. Refer to them in a clause; '
                'software does not repeat them.',
                'The Medigap and Part D tabs open without a review step. Never send a person to Review your '
                'info before seeing them.',
                'Ask the question alone. Its reason shows on its own line and its options are buttons, so '
                'put neither inside the question.',
                'Never say a detail is missing or needed; ask for it, with its reason in the same sentence.',
                'Never describe a fact in reports as missing or unknown.',
                'Name a Plans tab only when it is on this person’s coverage_path or they asked for it; do not '
                'announce the Part D tab before the coverage path has been discussed.']}
        if enrollment_flow.enabled(flow):
            context['conversation_state']['rules'] += [
                'When a plan list is ready, software shows a button to it under this reply. Say in a few plain words '
                'that the prices or plans are ready. Never name a tab, a step or a page section.',
                'Never recommend in the first person ("I’d keep", "I would switch", "I recommend"). Asked what you '
                'would recommend or whether to switch, relay how each path fits what the person said; software '
                'shows the comparison. A caution about a specific risk is fine ("confirm acceptance before you drop it").',
                'A yes-or-no question about a right or a rule gets the rule and its condition, never a bare "Yes".',
                'Refer to a doctor by the name the person gave, not as he or she, unless the person used one.']
            context['conversation_state']['enrollment'] = enrollment_flow.context(flow, g, r)
            if isinstance(context.get('plans_pages'), dict):
                # The dashboard has two tabs; Medigap and Part D are steps of Original Medicare.
                context['plans_pages'] = enrollment_flow.plans_pages(context['plans_pages'])
    except Exception:
        LOGGER.warning('Daylight ux brief skipped', exc_info=True)
    return context


LABELS = {'total_cost': 'total cost', 'bills': 'predictable costs', 'doctors': 'your doctors',
          'drugs': 'your prescriptions', 'travel': 'travel', 'other': 'something else'}
COVERAGE_LABELS = {'cobra': 'COBRA', 'employer': 'coverage from a current job', 'retiree': 'retiree coverage',
                   'none': 'no coverage right now', 'original': 'Original Medicare', 'advantage': 'Medicare Advantage',
                   'medigap': 'a Medigap policy', 'drug': 'a drug plan', 'military': 'VA or military coverage',
                   'medicaid': 'Medicaid'}


def _join(items):
    items = [item for item in items if item]
    return items[0] if len(items) == 1 else ', '.join(items[:-1]) + ' and ' + items[-1] if items else ''


def acknowledge(reports):
    """One plain sentence that uses what the person just said (CV-03)."""
    for report in reports or ():
        identifier, value = report.get('id'), report.get('value')
        if identifier == 'guide.needs.priorities' and isinstance(value, list) and value:
            names = _join([LABELS.get(item, '') for item in value])
            if names:
                return 'You said %s matter%s most.' % (names, 's' if len(value) == 1 else '')
        if identifier == 'guide.needs.costPreference' and value in ('predictable', 'lower_monthly'):
            return 'You said %s matter more.' % ('predictable costs' if value == 'predictable' else 'lower monthly payments')
        if identifier == 'guide.coverage.current' and isinstance(value, list) and value:
            names = _join([COVERAGE_LABELS.get(item, '') for item in value])
            if names:
                return 'You have %s.' % names
        if identifier == 'guide.comparison.scope.zip' and isinstance(value, str):
            return 'ZIP code %s.' % value
        if identifier == 'guide.situation.age65' and isinstance(value, dict) and value.get('month') and value.get('year'):
            return 'You turn 65 in %s %d.' % (ux_pass.MONTH_NAMES[value['month'] - 1], value['year'])
    return 'Thanks, I have that.' if reports else ''


def status(flow, out, g, r):
    """Profile-derived display state for every response; never raises."""
    if disabled():
        return out
    try:
        lean = path(flow, None, g, r)
        out['coveragePath'] = lean
        out['whatsLeft'] = None if conversation_planner.enabled(flow) else _left(flow, g, r, lean)
        when = timing(flow, g, r)
        line = ux_pass.medigap_window_line(when, today()) if when else None
        if line:
            out['medigapWindow'] = line
        if enrollment_flow.enabled(flow):
            out['enrollment'] = enrollment_flow.view(flow, g, r)
    except Exception:
        LOGGER.warning('Daylight ux status skipped', exc_info=True)
    return out


def _related(flow, rules, required_reason, message):
    """A reviewed statement tied to the question being asked, or to the words
    the person just used. Anything else would be an unrelated statement."""
    def text(rule):
        return rule.get('floor_text') or (flow.facts.get(rule['fact_id']) or {}).get('summary', '')
    if str(required_reason or '').startswith('rule:'):
        rule = floor_statement(rules, required_reason)
        if rule:
            return text(rule)
    words = {word for word in re.findall(r'[a-z]{5,}', (message or '').casefold())}
    for rule in rules or ():
        if rule.get('status') == 'not_met':
            continue
        fact = flow.facts.get(rule['fact_id']) or {}
        about = (fact.get('title', '') + ' ' + fact.get('summary', '')).casefold()
        if any(word in about for word in words):
            return text(rule)
    return ''


def _known(flow, g, r):
    """Topics the person has already reported, for the "never call a recorded
    fact missing" check (CV-15)."""
    known = []
    if flow.report(r, 'RC04').get('choice'):
        known.append(r'medicare in place|part a\b|part b\b|have medicare|enrolled in medicare|medicare (?:parts|coverage|status)')
    if flow.value(g, 'comparison.scope.zip'):
        known.append(r'\bzip\b')
    if flow.value(g, 'situation.age65'):
        known.append(r'birthday|turn(?:ed|ing)? 65|birth month')
    if flow.value(g, 'coverage.current'):
        known.append(r'coverage you have|current coverage|insurance you have')
    if flow.value(g, 'needs.costPreference') or cost_preference(flow, g):
        known.append(r'cost preference|predictable|monthly (?:cost|payment)s?')
    return known


def _cards(flow, owner, g, r, message, lean, view, generated):
    cards = []
    chain = _chain(flow, owner)
    when = timing(flow, g, r)
    card = _timing_card(flow, owner, g, r, message)
    if card:
        cards.append(card)
    if (when and when.get('medigap_window') and not any(card['kind'] == 'enrollment_timing' for card in cards)
            and not flow.ux.shown(owner, chain, 'medigap_window')
            and (metadata(r)['task'] == 'medigap' or MEDIGAP_MENTION.search(message or ''))):
        line = ux_pass.medigap_window_line(when, today())
        if line and line['text']:
            cards.append({'kind': 'medigap_window', 'title': 'Your Medigap window', 'text': line['text'],
                          'points': ['medigap_window'], 'statement_ids': ['medigap_window'],
                          'sources': [{'label': 'Medicare.gov: When can I buy a Medigap policy?',
                                       'url': 'https://www.medicare.gov/health-drug-plans/medigap/ready-to-buy/when'}]})
    return cards


def _medigap_raised(flow, g, r, lean):
    """Has Medigap come up in this conversation: asked about, the person's task, or where they lean."""
    return (metadata(r)['task'] == 'medigap' or lean.get('path') == 'original_medigap'
            or flow.value(g, enrollment_flow.ASKED_FIELD) == 'original_medigap')


def _left(flow, g, r, lean, pages=None):
    """What is left before the person's plans. Owner, November 13: until Medigap has come up
    it is said in general ("2 details left to see plans and prices")."""
    pages = pages or flow.plans_pages(g, r)
    if enrollment_flow.enabled(flow):
        # The line follows what the person is here for (profile PP15, November 13, 2026: "3 details
        # left" counted Medigap pricing details for someone whose drug plan list was already ready).
        task, coverage = metadata(r)['task'], _coverage(flow, g)
        if task in ('drug_pricing', 'drug_coverage'):
            keys = ['part_d']
        elif lean['path'] == 'medicare_advantage' or ('advantage' in coverage and lean['path'] != 'original_medigap'):
            keys = []
        elif 'medigap' in coverage and task != 'medigap':
            keys = ['part_d']
        else:
            keys = ['medigap', 'part_d']
        left = ux_pass.whats_left({key: pages.get(key) for key in keys}, None)
        if not keys and not flow.value(g, 'comparison.scope.zip'):
            left = {'tab': 'advantage', 'count': 1, 'needed': ['home ZIP code'], 'text': '1 detail left to see plans and prices'}
    else:
        left = ux_pass.whats_left(pages, lean['path'])
    if left and left['tab'] == 'medigap' and enrollment_flow.enabled(flow) and not _medigap_raised(flow, g, r, lean):
        left = {**left, 'text': '%d detail%s left to see plans and prices' % (left['count'], '' if left['count'] == 1 else 's')}
    return left


def two_paths(flow, owner, g, r):
    """The comparison card's frame. Listed amounts are filled by software in
    the browser from the same tab data the Plans page shows; none passes
    through the model."""
    lean = path(flow, owner, g, r)
    pages = flow.plans_pages(g, r)
    doctors = flow.value(g, 'needs.providersStatus')
    medicines = flow.value(g, 'needs.medicinesStatus')
    def check(state, text):
        return {'state': state, 'text': text}
    original = [check('ok', 'Any doctor who takes Medicare')]
    advantage = [check('unknown', 'Your doctors: networks not checked yet') if doctors == 'list'
                 else check('unknown', 'Doctors: each plan has its own network')]
    if medicines == 'yes':
        original.append(check('unknown', 'Your medicines: not checked against each drug list yet'))
        advantage.append(check('unknown', 'Your medicines: not checked against each drug list yet'))
    d161 = enrollment_flow.enabled(flow)
    # Owner, November 13: until Medigap has come up, the Original Medicare column says what is left
    # in one general line ("2 details left to see plans and prices"), not as a Medigap row.
    medigap_raised = _medigap_raised(flow, g, r, lean)
    return {'kind': 'two_paths', 'title': 'Your two paths', 'lean': lean,
            # D161: Parts A and B alone, keeping current coverage and waiting are choices too.
            **({'choices': [{'label': 'Parts A and B only', 'say': 'I want Parts A and B only.'},
                            {'label': 'Keep my current coverage', 'say': 'I want to keep my current coverage.'},
                            {'label': 'Wait for now', 'say': 'I’ll wait for now.'}]} if d161 else {}),
            'paths': [
                {'id': 'original_medigap', 'tab': 'medigap',
                 **({'name': 'Original Medicare', 'button': 'See Original Medicare',
                     'what': enrollment_flow.statement('original_what'),
                     'general_left': not medigap_raised,
                     'amounts': [{'label': 'Medigap, if you want it', 'source': 'medigap'},
                                 {'label': 'Part D drug plan, if you want it', 'source': 'part_d'}]} if d161 else
                    {'name': 'Original Medicare + Medigap + Part D', 'button': 'See your Medigap prices',
                     'what': 'Parts A and B from Medicare, a Medigap policy for your share of costs, and a separate drug plan.',
                     'amounts': [{'label': 'Medigap', 'source': 'medigap'}, {'label': 'Part D drug plan', 'source': 'part_d'}]}),
                 'status': pages['medigap']['status'], 'still_needed': pages['medigap']['still_needed'],
                 'checks': original},
                {'id': 'medicare_advantage', 'name': 'Medicare Advantage', 'tab': 'advantage',
                 'button': 'See Medicare Advantage plans',
                 'what': 'Parts A and B through one private plan. Most include drug coverage.',
                 'amounts': [{'label': 'Plan premium', 'source': 'ma_premium'},
                             {'label': 'Yearly in-network limit', 'source': 'ma_limit'}],
                 'status': 'ready' if flow.value(g, 'comparison.scope.zip') else 'missing',
                 'still_needed': [] if flow.value(g, 'comparison.scope.zip') else ['home ZIP code'],
                 'checks': advantage}],
            # Owner sign-off November 12, 2026; CMS fact sheet of November 14, 2025.
            'both': ('You pay the Part B premium with either path. Most people pay $202.90 a month for Part B '
                     'in 2026; people with higher incomes pay more.'),
            'sources': [{'label': 'CMS: 2026 Medicare Parts A & B premiums and deductibles',
                         'url': 'https://www.cms.gov/newsroom/fact-sheets/2026-medicare-parts-b-premiums-deductibles'}],
            'points': ['two_routes'], 'statement_ids': ['options']}


def trade_off(flow, owner, g, r):
    """X-04: this person's trade-off, relayed from reviewed statements only."""
    lean = path(flow, owner, g, r)
    facts = flow.facts
    def text(identifier):
        return (facts.get(identifier) or {}).get('summary', '')
    lines = []
    if cost_preference(flow, g) == 'predictable':
        lines.append('You said predictable costs matter more.')
    elif cost_preference(flow, g) == 'lower_monthly':
        lines.append('You said a lower monthly cost matters more.')
    lines.extend(filter(None, [text('medigap'), text('medical_limit'), text('costs')]))
    return {'kind': 'trade_off', 'title': 'What each path trades', 'text': ' '.join(lines),
            'lean': lean, 'statement_ids': ['medigap', 'medical_limit', 'costs']}


FLOORS = frozenset({'I don’t have a checked answer to that question here yet, so I won’t guess.',
                    'Let’s keep going with the next useful detail.',
                    'Let’s keep going. You can ask me anything about your coverage.'})


def finish(flow, owner, out, message, moves, *, rules=(), required_reason=None, accepted_reports=(),
           submitted_answer=None):
    if conversation_planner.enabled(flow):
        return conversation_planner.finish(flow, owner, out, message, moves, rules=rules,
            required_reason=required_reason, accepted_reports=accepted_reports, submitted_answer=submitted_answer)
    """Tidy the turn and attach what code shows. Never raises."""
    if disabled():
        return out
    try:
        g, r = out['guide'], out['record']
        chain = _chain(flow, owner)
        view = flow.ux.view(owner, chain)
        lean = path(flow, owner, g, r)
        helper = flow.value(g, 'subject.role') == 'someone'
        generated = (out.get('generated') or {}).get('status') == 'complete'
        stats = {'generated': generated}
        asked = submitted_answer is None and bool(re.search(
            r"(?i)\?|\b(?:please confirm|confirm that|tell me|explain|is that (?:right|it|the gist))\b", message or ''))
        # CV-03 on both failure paths: when the checker drops the prose and keeps the question, the
        # reply was a floor sentence plus "I couldn't finish that answer" (four turns, November 13, 2026).
        if 'couldn’t finish' in (out.get('notice') or '') or "couldn't finish" in (out.get('notice') or ''):
            out.pop('notice', None)
            if generated and out.get('reply', '').strip() in FLOORS:
                better = _related(flow, rules, required_reason, message if submitted_answer is None else '')
                if better and not flow.ux.seen(owner, chain, better):
                    out['reply'] = better
                    stats['floor_replaced'] = True
        if not generated:
            # CV-03: a fallback uses what the person said and asks the next
            # question. It never shows "I couldn't finish" and never appends a
            # statement unrelated to that question.
            related = _related(flow, rules, required_reason, message if submitted_answer is None else '')
            if related and flow.ux.seen(owner, chain, related):
                related = ''
            ack = acknowledge(accepted_reports)
            if not ack and not related and submitted_answer is None and '?' in (message or ''):
                # Honest and short; the next question keeps the person moving.
                ack = 'I don’t have a checked answer to that question here yet, so I won’t guess.'
            out['reply'] = ' '.join(filter(None, [ack, related])).strip()
            notice = out.get('notice') or ''
            if 'couldn’t finish' in notice or "couldn't finish" in notice:
                out.pop('notice', None)
            question = (out.get('assessment') or {}).get('nextQuestion')
            # An explicit "no more questions" is the person's to call.
            if not question and not (out.get('assessment') or {}).get('intakePaused'):
                nxt = next((item for item in moves if item.get('question')), None)
                if nxt:
                    out['assessment']['nextQuestion'] = copy.deepcopy(nxt['question'])
            if not out['reply'] and not (out.get('assessment') or {}).get('nextQuestion'):
                out['reply'] = 'Okay. I’m here when you want to keep going.'
            if not related and isinstance(out.get('advisor'), dict):
                out['advisor']['sources'] = []
        else:
            specifics = (submitted_answer is None and ux_pass.find_intent(message)
                         and bool(flow.value(g, 'comparison.scope.zip')))
            cleaned, cleaning = ux_pass.clean_reply(
                out.get('reply', ''), message=message, known=_known(flow, g, r),
                drop=('two_routes',) if specifics else (),
                said=lambda point: flow.ux.said(owner, chain, point),
                seen=lambda sentence: flow.ux.seen(owner, chain, sentence))
            out['reply'] = enrollment_flow.tab_names(cleaned) if enrollment_flow.enabled(flow) else cleaned
            stats.update(cleaning)
            # Never when the person asked something: a repeat still answers; silence does not
            # (profile PP10, November 13, 2026: a billed turn with no reply).
            if (not asked and cleaning.get('kept_original') and (out.get('assessment') or {}).get('nextQuestion')
                    and cleaning['verbatim_repeats'] + cleaning['repeated_caveats'] + cleaning['label_openers'] > 0):
                # Nothing new was said; the question carries the turn.
                out['reply'] = ''
            # A menu of topics is never the fallback question (CV-25, CV-29).
            if (view['find_mode'] or moves) and out['reply'].rstrip().endswith(flow.CONTINUATION_QUESTION):
                out['reply'] = out['reply'].rstrip()[:-len(flow.CONTINUATION_QUESTION)].rstrip()
                if moves and not (out.get('assessment') or {}).get('nextQuestion'):
                    # The turn still ends with a question: the next real one.
                    out['assessment']['nextQuestion'] = copy.deepcopy(moves[0]['question'])
                    out['assessment']['intakePaused'] = False
                    stats['topic_menu_replaced'] = True
        question = (out.get('assessment') or {}).get('nextQuestion')
        if question and question.get('question'):
            identifier = question['id']
            if view['find_mode'] and ux_pass.is_topic_menu(question['question']) and moves:
                replacement = copy.deepcopy(moves[0]['question'])
                question = out['assessment']['nextQuestion'] = replacement
                identifier = question['id']
                stats['topic_menu_replaced'] = True
            if not question.get('why'):
                question['why'] = ux_pass.question_reason(identifier)
            # CV-34: options are buttons; the question text never reads them out.
            labels = [str(choice[1]) for choice in question.get('choices') or [] if isinstance(choice, (list, tuple)) and len(choice) > 1]
            if len(labels) >= 4 and sum(label.casefold() in question['question'].casefold() for label in labels) >= 3:
                base = flow.question(identifier.split('.')[0]) or {}
                if base.get('question'):
                    question['question'] = base['question']
                    stats['options_removed_from_question'] = True
            # Live run: the model put the reason and the options inside the
            # question, next to the reason line and the buttons.
            if question.get('why') or labels:
                plain, restructured = ux_pass.plain_question(question['question'], labels)
                if restructured and len(plain.split()) < 6:
                    try:
                        base = (flow.question(identifier.split('.')[0]) or {}).get('question') or ''
                        # The stock wording says "you"; a helper is asked about the person they are helping.
                        if base and not (helper and re.search(r"(?i)\byou(?:r)?\b", base)):
                            plain = base
                    except Exception:
                        pass
                if plain and plain != question['question']:
                    question['question'] = plain
                    stats['question_made_plain'] = True
            # CV-09: never the same words twice.
            # A second ask uses a fixed short wording. There is no third: the turn loop parks a
            # question the person has passed twice (15-profile run, November 13, 2026).
            if flow.ux.asked(owner, chain, identifier, question['question']):
                reworded = ux_pass.shorter_question(identifier, question['question'], helper)
                if reworded != question['question']:
                    flow.ux.asked(owner, chain, identifier, reworded)
                    question['question'] = reworded
                    stats['reask_reworded'] = True
            stats['question_id'] = identifier
        # CV-31: exactly one question per turn, in the question slot, never
        # also inside the body text.
        if generated and out.get('reply'):
            asking = bool((out.get('assessment') or {}).get('nextQuestion'))
            parts = ux_pass.sentences(out['reply'])
            questions = [index for index, part in enumerate(parts) if part.rstrip().endswith('?')]
            drop = set(questions if asking else questions[:-1])
            body = ''.join(part for index, part in enumerate(parts) if index not in drop).strip()
            if drop and body:
                out['reply'] = body
                stats['extra_questions'] = len(drop)
        cards = _cards(flow, owner, g, r, message, lean, view, generated)
        # CV-23: a reviewed statement, once, when a medicine that commonly needs
        # the plan's approval is named (owner sign-off November 12, 2026).
        medicines = str(flow.value(g, 'needs.medications') or '')
        fact = flow.facts.get('glp1_prior_authorization')
        if (fact and re.search(r'(?i)\bozempic\b|\bsemaglutide\b', medicines)
                and not flow.ux.shown(owner, chain, 'medicine_rule')):
            cards.append({'kind': 'medicine_rule', 'title': 'Ozempic and plan approval', 'text': fact['text'],
                          'points': ['prior_authorization'], 'statement_ids': ['glp1_prior_authorization'],
                          'sources': fact.get('sources', [])})
        # CV-22: where no check runs (the participant build), say once that the
        # person's medicines and doctors are not checked against plans yet.
        checks = getattr(flow, 'conversation_checks', None)
        if not checks or not getattr(checks, 'prescriptions', None):
            reported = ' '.join(str(report.get('id')) for report in accepted_reports or ())
            for field, kind in (('guide.needs.medic', ('medicines_note', 'Your medicines',
                                    'Your medicines aren’t checked against each plan’s drug list yet. Each plan shows that.')),
                                ('guide.needs.provider', ('doctors_note', 'Your doctors',
                                    'Plan networks aren’t checked for your doctors yet. Each plan shows that.'))):
                if checks and 'provider' in field:
                    continue   # the doctor check speaks for doctors on this build
                listed = flow.value(g, 'needs.medicinesStatus' if 'medic' in field else 'needs.providersStatus')
                # Shown once, on the first turn the list is known. The live extraction files a
                # medicine under its own report id, so the turn's report ids are not the test.
                if (listed in ('yes', 'list') and not flow.ux.shown(owner, chain, kind[0])
                        and not any(card['kind'] == kind[0] for card in cards)):
                    cards.append({'kind': kind[0], 'title': kind[1], 'text': kind[2]})
        d161 = enrollment_flow.enabled(flow)
        asked_find = submitted_answer is None and ux_pass.find_intent(message, d161)
        zip_known = bool(flow.value(g, 'comparison.scope.zip'))
        typed = message if submitted_answer is None else ''
        task = metadata(r)['task']
        # Someone reviewing one piece of coverage they already have is not choosing between two paths.
        one_piece = d161 and (task in ('drug_pricing', 'drug_coverage')
                              or task == 'medigap' and not BOTH_PATHS.search(typed or ''))
        stated = any(str(report.get('id')) in ('guide.needs.priorities', 'guide.needs.costPreference')
                     for report in accepted_reports or ())
        wants_pick = d161 and bool(RECOMMEND_ASK.search(typed or '')) and not one_piece
        have = enrollment_flow.have_card(flow, g, r) if d161 and not flow.ux.shown(owner, chain, 'coverage_now') else None
        if have:
            cards.append(have)
        if d161:
            # From the state of the conversation, not a phrase list: the person asked about their options,
            # named both paths, or said what matters to them. The card says what is still needed for amounts.
            wants_paths = (asked_find or wants_pick or bool(BOTH_PATHS.search(typed or '')) or stated and zip_known
                           or zip_known and view['find_mode'] and not cards)
            if wants_paths and not one_piece and (wants_pick or not flow.ux.shown(owner, chain, 'two_paths')) \
                    and not (have and not asked_find and not wants_pick):
                cards.append(two_paths(flow, owner, g, r))
            if (cost_preference(flow, g) and not flow.ux.shown(owner, chain, 'trade_off')
                    and task not in ('drug_pricing', 'drug_coverage') and (zip_known or asked_find or stated)):
                cards.append(enrollment_flow.trade_off_card(flow, g, cost_preference(flow, g)))
            if wants_pick and generated and NO_PICK not in out.get('reply', ''):
                out['reply'] = (NO_PICK + ' ' + out.get('reply', '')).strip()
                stats['no_pick_line'] = True
            # The way into the plans, once, the moment a list is ready, whatever question is open.
            coverage = _coverage(flow, g)
            pages = flow.plans_pages(g, r)
            if task in ('drug_pricing', 'drug_coverage'):
                wanted = ['part_d']
            elif lean['path'] == 'medicare_advantage' or ('advantage' in coverage and lean['path'] != 'original_medigap'):
                wanted = ['advantage']
            elif task == 'medigap' or lean['path'] == 'original_medigap' or _medigap_raised(flow, g, r, lean):
                wanted = ['medigap']
            else:
                wanted = []
            for tab in wanted:
                ready = zip_known if tab == 'advantage' else (pages.get(tab) or {}).get('status') == 'ready'
                if ready and not flow.ux.shown(owner, chain, 'ready:' + tab):
                    title, label, opens = READY[tab]
                    cards.append({'kind': 'plans_ready', 'title': title, 'tab': tab, 'button': {'label': label, 'view': opens}})
                    flow.ux.record(owner, chain, '', card='ready:' + tab)
        elif zip_known and (asked_find or view['find_mode'] and not cards):
            # Each card once a visit (live run: both repeated on the next
            # "which is best"). In find mode the two paths appear as soon as
            # the ZIP is known, on a turn that carries no other card.
            if not flow.ux.shown(owner, chain, 'two_paths'):
                cards.append(two_paths(flow, owner, g, r))
            if cost_preference(flow, g) and not flow.ux.shown(owner, chain, 'trade_off'):
                cards.append(trade_off(flow, owner, g, r))
        if asked and not out.get('reply', '').strip() and not cards:
            # The person asked something and nothing survived: say so in one honest sentence, or give the
            # checked statement that matches their words. Never only the next question.
            better = _related(flow, rules, required_reason, message)
            out['reply'] = better if better and not flow.ux.seen(owner, chain, better) else \
                'I don’t have a checked answer to that question here yet, so I won’t guess.'
            stats['asked_floor'] = True
        if enrollment_flow.enabled(flow):
            # D161: a chosen finish's summary, and the sign-up route once.
            cards.extend(enrollment_flow.cards(flow, owner, chain, g, r,
                                               message if submitted_answer is None else '', cards))
            out['enrollment'] = enrollment_flow.view(flow, g, r)
        elif asked_find and not flow.ux.shown(owner, chain, 'next_line'):
            # CV-02: say what happens next, once, in one line.
            if NEXT_LINE not in out.get('reply', ''):
                out['reply'] = (out.get('reply', '').rstrip() + ' ' + NEXT_LINE).strip()
            flow.ux.record(owner, chain, '', card='next_line')
        if generated and out.get('reply'):
            kinds = {card['kind'] for card in cards}
            ready = (lean['path'] == 'original_medigap'
                     and flow.plans_pages(g, r)['medigap']['status'] == 'ready')
            kept = []
            for part in ux_pass.sentences(out['reply']):
                if CARD_MENTION.search(part) and ('enrollment_timing' not in kinds if TIMING_WORD.search(part)
                                                  else not (kinds or view['cards'])):
                    stats['card_mentions_removed'] = stats.get('card_mentions_removed', 0) + 1
                elif ready and REVIEW_STEP.search(part):
                    stats['review_step_removed'] = stats.get('review_step_removed', 0) + 1
                else:
                    kept.append(part)
            body = ''.join(kept).strip()
            if body != out['reply'].strip():
                out['reply'] = body or ('Your Medigap prices are ready.' if ready else '')
        # CV-33: Sources only when the reply or a card states a Medicare fact.
        if isinstance(out.get('advisor'), dict) and not (out['advisor'].get('teachingFactIds') or cards
                                                           or stats.get('points') or out.get('knowledgeReceipts')):
            if not any(pattern.search(out.get('reply', '')) for pattern in ux_pass.POINTS.values()):
                out['advisor']['sources'] = []
        points = [point for card in cards for point in card.get('points', [])]
        for card in cards:
            flow.ux.record(owner, chain, '', card=card['kind'])
        flow.ux.record(owner, chain, out.get('reply', '') + ' ' + ' '.join(card.get('text', '') for card in cards), points=points)
        if cards:
            out['cards'] = cards
        pages = flow.plans_pages(g, r)
        out['coveragePath'] = lean
        left = _left(flow, g, r, lean, pages)
        out['whatsLeft'] = left
        when = timing(flow, g, r)
        line = ux_pass.medigap_window_line(when, today()) if when else None
        if line:
            out['medigapWindow'] = line
        out.setdefault('metrics', {})['ux'] = {key: value for key, value in stats.items()
                                               if isinstance(value, (bool, int, str, list))}
    except Exception:
        LOGGER.warning('Daylight ux finish skipped', exc_info=True)
    return out
