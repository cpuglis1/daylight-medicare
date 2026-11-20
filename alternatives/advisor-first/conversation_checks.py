"""D154: local evidence work follows reports in the ordinary advisor visit.

The model never gets source candidates, evidence rows, receipts or prices. This
controller owns exact choices and deterministic work; the ordinary conversation
still owns reports, permission, history and its signed, expiring guest head.
"""
from collections import OrderedDict
from copy import deepcopy
from datetime import date, datetime
from hashlib import sha256
import json
import turn_progress
import re
from secrets import token_urlsafe
from time import time

from comparison_profile import build_comparison_profile
from guest_profiles import ProfileError
from advisor_memory import HISTORY_TTL
from natural_flow import list_items
from part_d_profile import profile as scope_profile
from part_d_visit import PrescriptionVisit, reported_fields


def digest(value):
    return sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def address(row):
    return ', '.join(str(row.get(key, '')) for key in ('street', 'city', 'state', 'postal') if row.get(key))


def original_medicare_evidence(evidence):
    """Summarize published evidence for the confirmed clinician and office."""
    opt_out = evidence.get('opt_out', ())
    opted_out = [row['catalog_modified_on'] for row in opt_out
                 if row['interval_state'] in ('published_interval_contains_date', 'boundary_review')]
    if opted_out:
        return {'state': 'unknown', 'record_date': max(opted_out)}
    if evidence['state'] != 'dated_listing':
        return {'state': 'unknown', 'record_date': None}
    assignments = evidence.get('assignment', ())
    states = [('accepts', 'published_accepts_assignment'),
              ('may_accept', 'published_may_accept_assignment')]
    for state, published in states:
        dates = [row['published_on'] for row in assignments
                 if published in (row['individual_state'], row['group_state'])]
        if dates:
            return {'state': state, 'record_date': max(dates)}
    return {'state': 'unknown', 'record_date': max(
        (row['published_on'] for row in (*assignments, *evidence.get('enrollment', ()))), default=None)}


def parse_date(value):
    text = str(value).strip().rstrip('.')
    for fmt in ('%Y-%m-%d', '%B %d, %Y', '%b %d, %Y', '%B %d %Y', '%b %d %Y',
                '%m/%d/%Y', '%B %d', '%b %d', '%m/%d'):
        try:
            parsed = datetime.strptime(text, fmt).date()
            if '%Y' not in fmt:
                parsed = parsed.replace(year=2026)
            if parsed.year == 2026:
                return parsed.isoformat()
        except ValueError:
            pass
    return None


# D181: "Dr. Smith in Naples and Dr. Tunkle" is two doctors. Split only where the
# next part starts with a doctor title, so "Naples Heart and Vascular" and
# "Dr. Maria Lopez, Naples" stay whole. Nothing is rewritten.
_NEXT_DOCTOR = re.compile(r'\s*(?:,\s*(?:and\s+)?|\s+and\s+|\s*&\s*)(?=(?:dr\b\.?|doctor\b)\s*[A-Za-z])', re.I)


def doctor_items(value):
    names = []
    for entry in list_items(value, True):
        for part in _NEXT_DOCTOR.split(entry):
            part = part.strip(' .,')
            if part and part.casefold() not in {name.casefold() for name in names}:
                names.append(part)
    return names


def doctor_reports(guide, record):
    fields = guide['fields']
    status = fields.get('needs.providersStatus', {}).get('value')
    if status in ('no', 'none', 'unknown', 'deferred'):
        return {}
    reported = fields.get('needs.providers', {})
    items = {f'doctor-{i}': {'name': name} for i, name in
             enumerate(doctor_items(reported.get('value')), 1)}
    for fact in build_comparison_profile(guide, record)['facts']:
        if (fact.get('question_id') == 'RC21' and fact['usable_for_bound_subject']
                and fact['temporal_scope'] == 'current' and fact['ref'].get('item_id')):
            key = fact['ref']['item_id']
            field = fact['ref']['path'].rsplit('.', 1)[-1]
            if field in ('name', 'location', 'city', 'practice', 'specialty'):
                items.setdefault(key, {})['location' if field=='city' else field] = fact['value']
    return {key: {**value, 'list_revision': reported.get('revision')}
            for key, value in items.items() if value.get('name')}


DRUG_QUESTIONS = {
    'rxcui': 'Which version of {medicine} do you take?',
    'quantity': 'How many tablets, capsules or milliliters come in each refill of {medicine}?',
    'unit': 'What does that quantity count for {medicine}?',
    'days_supply': 'How many days does one refill of {medicine} last?',
    'fills': 'Which refill dates should I include for {medicine} in 2026?',
    'outlet_zip': 'What is the ZIP code of the pharmacy you use?',
    'pharmacy': 'Which pharmacy location do you use?',
    'channel': 'How do you get these prescriptions?',
    'period': 'Which month should the 2026 cost estimate start with?',
    'assistance': 'Do you have help paying for your prescriptions?',
    'prior_spending': 'At the start of this estimate, do you have any drug spending or deductible credit to carry over?'
}
DRUG_CHOICES = {
    'unit': [('tablet','Tablets'), ('capsule','Capsules'), ('mL','Milliliters'), ('other','Another unit')],
    'days_supply': [(30,'30 days'), (90,'90 days')],
    'channel': [('retail','Pick up at a pharmacy'), ('mail','Mail order')],
    'assistance': [('none','No'), ('reported_help','Yes'), ('unknown','I’m not sure')],
    'prior_spending': [('confirmed_zero','No, both start at zero'), ('nonzero','Yes'), ('unknown','I’m not sure')],
    'period': [(f'2026-{i:02}-01', date(2026, i, 1).strftime('%B 2026')) for i in range(1,13)]
}
HOLDS = {
    'PILOT_EVIDENCE_STALE': 'The source information is due for review, so I can’t show a current result. Your details are still here.',
    'multiple_outlets_unsupported': 'These medicines use different pharmacies. This estimate currently supports one pharmacy at a time.',
    'reported_fill_unsupported': 'The refill details you gave need a cost calculation this demo does not yet support.',
    'assistance_unresolved_or_unsupported': 'Help with drug costs can change what you pay. This estimate cannot yet account for that help.',
    'prior_spending_unresolved_or_unsupported': 'Your earlier spending can change what you pay. This estimate cannot yet account for those balances.',
    'criteria_unresolved': 'This medicine has coverage requirements that still need checking.',
    'quantity_limit_rule_unresolved': 'This medicine has a quantity limit that still needs checking.',
    'only_in_area_retail_average_available': 'The available estimates use local retail pharmacy averages. Mail-order costs still need checking.'
}

# Directory answers that mean "no such listing", not a fault in the data service.
NOT_FOUND_CODES = frozenset({'DOCTOR_QUERY_EMPTY', 'DOCTOR_SEARCH_NEEDS_NAME_OR_DETAIL', 'INVALID_LITERAL_PROVIDER_REQUEST'})
TOWNS = frozenset({'naples', 'north naples', 'east naples', 'marco island', 'bonita springs', 'estero', 'fort myers',
                   'ft myers', 'ft. myers', 'immokalee', 'golden gate', 'ave maria', 'cape coral', 'lehigh acres',
                   'everglades city', 'pelican bay', 'vanderbilt beach'})
_ENTRY_CUT = re.compile(r"(?i),|;|\(|\s[—–-]\s|\s+(?:at|on|in|for|from|with|who|whom|near|by)\s+|\s+(?:my|our|his|her)\s+")
_SENTENCE_WORD = re.compile(r"(?i)\b(?:i|i'm|i've|i'd|i'll|me|my|we|he|she|they|his|her|him|is|are|was|were|am|do|does|did|don't|doesn't|"
                            r"didn't|have|has|had|want|wants|need|needs|like|likes|keep|think|thinks|just|never|not|but|because|"
                            r"so|yes|no|female|male|tobacco|why|how|what|instead|actually|medicine|take|stop|pause|year|month|"
                            r"plan|plans|premium|cost|costs)\b|\$")
_PRACTICE_WORD = re.compile(r"(?i)\b(?:clinic|medical|health|healthcare|associates|group|center|centre|cardiology|physicians?|"
                            r"hospital|practice|care|institute|orthop\w+|partners|specialists?|nch|lee health|millennium|"
                            r"concierge|internal medicine|family medicine|primary care|heart)\b")


class ConversationChecks:
    def __init__(self, flow, doctors, drugs, plans):
        self.flow, self.doctors, self.drugs = flow, doctors, drugs
        self.prescriptions = PrescriptionVisit(flow, drugs, assume_30_days=True,
            pharmacy_first=getattr(flow, 'd166', False)) if drugs else None
        self.plans = plans
        self.visits = OrderedDict()

    def visit(self, owner, guide, record):
        now = time()
        for key in list(self.visits):
            if (self.visits[key]['expires'] <= now or key in self.flow.revoked_owners
                    or self.visits[key]['chain'] != self.flow.current_chain.get(key)):
                self.visits.pop(key)
        chain = self.flow.current_chain.get(owner)
        subject = guide['fields'].get('subject.role')
        state = self.visits.get(owner)
        if not state or state['chain'] != chain or state['subject'] != subject:
            state = {'chain':chain, 'subject':deepcopy(subject), 'doctors':{}, 'drug':{},
                     'question':None, 'results':[], 'skipped':{}, 'expires':now + HISTORY_TTL}
            self.visits[owner] = state
        state['expires'] = now + HISTORY_TTL
        self.visits.move_to_end(owner)
        while len(self.visits) > 128:
            self.visits.popitem(last=False)
        return state

    def snapshot(self, guide, record, chain):
        # Internal only: the public request has already passed the ordinary
        # turn's owner/head/signature checks. Stable across unrelated replies.
        signature = digest(reported_fields(guide,record))
        return {'response':{'guide':guide, 'record':record,
                            'continuation':chain + '.' + signature}, 'expires':time()+HISTORY_TTL}

    def ask(self, state, kind, field, text, *, choices=(), why='', item=None, **extra):
        choices = [dict(value=value, label=label) for value, label in choices]
        shape = dict(kind=kind, field=field, question=text, why=why, choices=choices, item=item, **extra)
        old = state.get('question')
        token = old['token'] if old and old.get('_shape') == digest(shape) else token_urlsafe(24)
        question = {**shape, 'token':token, '_shape':digest(shape)}
        state['question'] = question
        return question

    def context(self):
        return {'doctors':'available in this conversation' if self.doctors else 'unavailable',
                'prescriptions':'available in this conversation' if self.drugs else 'unavailable',
                'scope':'2026 local evaluation; participant use remains held',
                'behavior':'Reuse reported doctors, medicines and pharmacies. Software presents exact choices and results inline. '
                           'Once products and offices are confirmed, software checks across available plans. '
                           'A requested drug-cost comparison reuses one confirmed medicine list, pharmacy and refill schedule across plans. '
                           'Dated pharmacy listings and retail-average estimates are different from exact-store prices. '
                           'Unavailable estimates remain unresolved; premium order cannot identify the cheapest drug plan. '
                           'Do not suggest a separate check button, another tab or a fictional setup. '
                           'Do not invent a completed check, network membership, medicine coverage or amount.'}

    def observe(self, owner, guide, record, action, plans_context=None):
        state = self.visit(owner, guide, record)
        words = action.get('message', '') if action.get('type') == 'message' else ''
        if getattr(self.flow, 'd166', False) and re.search(r'\b(?:cost\w*|cheap\w*|price\w*|pay|order)\b', words, re.I) and re.search(
                r'\b(?:medicine\w*|drug\w*|prescription\w*|pharmacy|plans?)\b', words, re.I):
            # This is an investigation, never a coverage decision. A reported
            # MA plan keeps a drug-cost review on the MA route.
            held = self.flow.value(guide, 'coverage.current') or []
            state['drug_compare'] = ('advantage' if 'advantage' in held or re.search(r'\b(?:hmo|ppo|advantage)\b', words, re.I)
                                     else 'part_d' if 'drug' in held or re.search(r'\b(?:drug plan|part d)\b', words, re.I) else 'both')
        if words and not re.search(r"\b(?:not|don.t|instead|versus|without)\b", words, re.I):
            pricing = re.search(r'\b(?:cost|price|pay|estimate)\w*\b', words, re.I)
            matches = [p for p in self.plans() if p['name'].casefold() in words.casefold()] if pricing else []
            # A deliberately shared Plans selection is a research target only
            # when this message asks to check it, never a coverage preference.
            if (pricing and not matches and plans_context and re.search(r'\b(?:this|that) plan\b',words,re.I)
                    and re.search(r'\b(?:doctor|medicine|drug|prescription|pharmacy|cover)\w*\b',words,re.I)):
                matches = [p for p in self.plans() if p['id']==plans_context.get('selected_id')]
            for kind, candidates in (('doctor', [p for p in matches if p['id'][5] == 'H']),
                                     ('drug', [p for p in matches if p['id'][5] in 'SHR'])):
                if len(candidates) == 1:
                    state[kind + '_plan'] = candidates[0]['id']
            if re.search(r'\boriginal medicare\b', words, re.I) and not re.search(r'\b(not|don.t|instead|versus|or)\b', words, re.I):
                state['doctor_plan'] = 'original_medicare'

    def reconcile(self, owner, guide, record):
        from daylight_data.serving.binding import ResearchServingError
        state = self.visit(owner, guide, record)
        scope = scope_profile(guide, record)
        state['results'] = state.pop('notes', [])
        # Only a held confirmation about the doctors or medicines themselves waits; any other one
        # (a birthday, a start date) no longer stops the directory search (profile PP13, November 13, 2026).
        held = self.flow.pending_for(owner)
        if scope['status'] != 'ready' or (held and str(held['update'].get('id', '')).split('.')[0] in ('T06', 'T07', 'RC21', 'RC22', 'RC23')):
            state['question'] = None
            return self.public(state)
        providers = doctor_reports(guide, record)
        try:
            import ux_flow
            if ux_flow.disabled():
                raise LookupError
            lean = ux_flow.path(self.flow, owner, guide, record)
            when = ux_flow.timing(self.flow, guide, record)
            today = ux_flow.today()
            start = (when or {}).get('part_b_start')
            state['doctor_plan_default'] = 'original_medicare' if lean['path'] == 'original_medigap' else None
            state['doctor_date_default'] = (start if start and start.year == today.year and start > today else today).isoformat()
        except Exception:
            state['doctor_plan_default'] = state['doctor_date_default'] = None
        report_stamp = digest([scope, providers, reported_fields(guide, record)])
        if state.get('report_stamp') != report_stamp:
            state['history'] = []
            state['report_stamp'] = report_stamp
        state['doctors'] = {k:v for k,v in state['doctors'].items() if k in providers}
        pending = None
        for item, report in providers.items():
            stamp = digest([state['subject'], scope['inputs'], report])
            previous = state['doctors'].get(item, {})
            if previous.get('stamp') != stamp:
                previous = {'stamp':stamp, 'report':report}
                state['doctors'][item] = previous
            if state['skipped'].get('doctor:'+item) == stamp:
                continue
            if not self.doctors:
                continue
            try:
                question, result = self.doctor_step(state, item, previous)
                if result:
                    state['results'].append(result)
                if question and pending is None:
                    pending = question
                    break
            except ResearchServingError as error:
                previous.pop('result', None)
                if pending is None:
                    pending = self.ask(state, 'doctor', 'doctor_retry',
                        'Would you like to continue with the other details while this doctor check is unavailable?',
                        choices=[('__later__','Continue with my other details'), ('__retry__','Try the doctor again')],
                        why=self.hold_message(str(error)), item=item)
                    break
        # One active question. Medicines remain queued behind the doctor already
        # being discussed; there is no second form or separate session.
        if pending:
            state['question'] = pending
            return self.public(state)
        try:
            question, result = self.drug_step(owner, state, guide, record)
            if result:
                state['results'].append(result)
            state['question'] = question
        except ResearchServingError as error:
            state['drug'].pop('result', None)
            self.ask(state, 'drug', 'drug_retry',
                'Would you like to continue with the plan details while the drug-cost check is unavailable?',
                choices=[('__later__','Continue with my other details'), ('__retry__','Try again')],
                why=self.hold_message(str(error)))
        return self.public(state)

    def doctor_step(self, state, item, detail):
        from daylight_data.serving.pilot_doctors import place_office

        report = detail['report']
        name = report['name']
        display, hinted, stated_practice = self.doctor_entry(name)
        place = hinted or report.get('location')
        practice = report.get('practice') or stated_practice
        if not detail.get('doctor'):
            # D157: "Ashley Tunkle in Naples" names a person and a place. Search
            # and ask with the name; never ask again for a city already given.
            location = detail.get('location') or place
            if 'candidates' not in detail:
                passed = set(detail.get('passed', ()))
                def search(region, **facets):
                    if place or facets.get('location'):
                        facets.update(location=facets.get('location') or place, prefer_place=True)
                    try:
                        if hasattr(self.doctors, 'network_matrix'):
                            facets['combine_identity'] = True
                        found = turn_progress.run('doctors', self.doctors.search, name=display, year=2026, region=region,
                                                    offset=detail.get('offset', 0), **facets)
                    except Exception as error:
                        # A name the directory does not know, or text it cannot read, is
                        # "not found", never "unavailable" (15-profile run, November 13, 2026).
                        if str(error) in NOT_FOUND_CODES:
                            return [], None
                        raise
                    rows=[];seen=set()
                    for p in found['candidates']:
                        if p['kind']!='clinician' or not p['site_count']:continue
                        # CV-16: never show again a match the person already passed over.
                        if p['candidate_id'] in passed:continue
                        unique=(json.dumps([p['source_npis'],p['office_previews']],sort_keys=True)
                                if len(p['source_npis'])==1 and p['site_count']==1 else p['candidate_id'])
                        if unique not in seen:rows.append(p);seen.add(unique)
                    return rows, found.get('next_offset')
                answer = detail.get('location')
                known = dict(practice=practice, specialty=report.get('specialty'))
                if detail.get('practice_asked') and answer:
                    attempts = [dict(practice=answer, specialty=report.get('specialty')), dict(location=answer, **known)]
                else:
                    # The name alone is tried when the stated practice narrows it to nothing:
                    # people say "at NCH" for an office the directory lists under another name.
                    attempts = ([dict(location=location, **known)]
                                + ([dict(location=location)] if any(known.values()) else [])
                                + ([dict(practice=answer)] if answer else []))
                region = detail.get('region', 'regional')
                candidates, following = [], None
                for facets in attempts:
                    candidates, following = search(region, **facets)
                    if candidates:
                        detail['place'] = place or facets.get('location')
                        break
                if not candidates and region == 'regional':
                    # CV-17: nothing nearby, so widen once instead of asking the
                    # person to choose "look outside this area" on an empty list.
                    detail.update(region='all_retained', offset=0, widened=True)
                    for facets in [dict(practice=answer, specialty=report.get('specialty'))] if detail.get('practice_asked') and answer else [known, {}]:
                        candidates, following = search('all_retained', **facets)
                        if candidates:
                            detail['place'] = place
                            break
                detail['candidates'] = candidates
                detail['next_offset'] = following
                if (not location and not practice and len(detail['candidates']) != 1
                        and not detail.get('refined')):
                    detail['needs_location'] = True
            candidates = detail['candidates']
            if (len(candidates) == 1 and candidates[0].get('site_count', 0) > 1 and detail.get('next_offset') is None
                    and not detail.get('needs_location')):
                # D181: one listed clinician with several offices is one question, not two:
                # choosing the office confirms both. "None of these" still searches again.
                detail['doctor'] = candidates[0]
                detail['implicit_doctor'] = True
                return self.doctor_step(state, item, detail)
            if detail.get('needs_location') or not candidates:
                # Someone who already gave the town or the practice is not asked for it again.
                if not candidates and (detail.get('practice_asked') or practice) and not detail.get('needs_location'):
                    # CV-19: say once what leaving it open means, then move on.
                    state['skipped']['doctor:' + item] = detail['stamp']
                    return None, {'kind': 'note', 'key': 'doctor:' + item, 'name': display, 'participant_release': False,
                                  'details': ['I couldn’t find %s in the doctor directories I have, so plan networks '
                                              'aren’t checked for this doctor. Each plan will show that.' % display]}
                # CV-18: ask only for what is missing.
                ask = ('What is the name of %s’s practice or office?' % display if location
                       else 'What city or practice is %s in?' % display)
                why = ('I couldn’t find %s in the doctor directories I have%s. The practice name often finds the right listing.'
                       % (display, ' for ' + location if location else '') if not candidates
                       else 'That will help me find the right person.')
                return self.ask(state, 'doctor', 'doctor_location', ask, why=why, item=item), None
            choices = [(p['candidate_id'], p['label'] + ' — ' + '; '.join(address(a) for a in p['office_previews']))
                       for p in candidates]
            if detail.get('next_offset') is not None:
                choices.append(('__more__','More matches'))
            choices.append(('__refine__','None of these: search by practice name'))
            if detail.get('region','regional') == 'regional':
                choices.append(('__all__','Look outside this area'))
            public_candidates = [
                {'candidate_id': p['candidate_id'], 'label': p['label'],
                 'offices': [place_office(office, detail.get('place')) for office in p['office_previews']]}
                for p in candidates
            ]
            return self.ask(state, 'doctor', 'doctor', f'Which of these is {display}?',
                            choices=choices, item=item, candidates=public_candidates), None
        doctor = detail['doctor']
        place = detail.get('place')
        if not detail.get('office'):
            if 'offices' not in detail:
                combined = {'combine_identity': True} if hasattr(self.doctors, 'network_matrix') else {}
                found = turn_progress.run('doctors', self.doctors.sites, candidate_id=doctor['candidate_id'], offset=detail.get('office_offset',0),
                                           **combined, **({'place': place} if place else {}))
                detail['offices'] = found['sites']
                detail['next_office'] = found.get('next_offset')
            choices = [(p['site_id'], address(p['address'])) for p in detail['offices']]
            if detail.get('next_office') is not None:
                choices.append(('__more__','More offices'))
            if detail.get('implicit_doctor'):
                choices.append(('__refine__','None of these: search by practice name'))
            if (len(detail['offices']) == 1 and detail.get('next_office') is None and not detail.get('office_offset')
                    and not detail.get('implicit_doctor')):
                # D157 (live run): a single listed office is not a question.
                detail['office'] = detail['offices'][0]
            else:
                return self.ask(state, 'doctor', 'office', f'Which office do you visit for {doctor["label"]}?',
                    choices=choices, why='Coverage can differ by office, so I’ll use the location you confirm.', item=item,
                    offices=[{'site_id': p['site_id'], **place_office(p['address'], place)} for p in detail['offices']]), None
        if hasattr(self.doctors, 'network_matrix'):
            return None, self.doctor_matrix(state, item, detail, place)
        plan = state.get('doctor_plan')
        if not plan and state.get('doctor_plan_default') and not state.get('doctor_plan_asked'):
            # D157 (live run): never a 70-option list for someone whose path is
            # Original Medicare. "Change coverage" on the result still offers it.
            plan = state['doctor_plan'] = state['doctor_plan_default']
        if plan and not state.get('doctor_date') and state.get('doctor_date_default') and not state.get('doctor_date_asked'):
            state['doctor_date'] = state['doctor_date_default']
        if not plan:
            choices = [('original_medicare','Original Medicare')]
            choices += [(p['id'],p['name']) for p in self.plans() if p['id'][5]=='H']
            return self.ask(state, 'doctor', 'doctor_plan', 'Which coverage would you like me to check for this doctor?',
                choices=choices, item=item), None
        if not state.get('doctor_date'):
            return self.ask(state, 'doctor', 'doctor_date', 'For what date in 2026 would you like me to check that coverage?',
                why='For example, November 17. A directory listing may not establish participation on a later date.', item=item), None
        selection = self.doctors.selection(candidate_id=doctor['candidate_id'], site_id=detail['office']['site_id'],
            offering_id=None if plan=='original_medicare' else plan, intended_date=state['doctor_date'],
            route='original_medicare' if plan=='original_medicare' else 'medicare_advantage')
        # Always revalidate live controls. An earlier displayed result is not
        # authority after an expiry, source withdrawal or profile correction.
        evidence = turn_progress.run('doctors', self.doctors.evidence, selection)
        result = {'kind':'doctor', 'key':'doctor:'+item, 'name':doctor['label'],
                  'office':address(detail['office']['address']), 'plan':self.plan_name(plan),
                  'office_parts': place_office(detail['office']['address'], place),
                  'date':state['doctor_date'], 'state':evidence['state'], 'participant_release':False,
                  'details':self.doctor_summary(evidence, plan=='original_medicare')}
        if plan == 'original_medicare':
            result['original_medicare'] = original_medicare_evidence(evidence)
        detail['result'] = result
        return None, result

    def doctor_matrix(self, state, item, detail, place):
        from daylight_data.serving.pilot_doctors import place_office

        office = detail['office']
        doctor = detail['doctor']
        intended = state.get('doctor_date') or state.get('doctor_date_default') or date.today().isoformat()
        found = turn_progress.run('doctors', self.doctors.network_matrix, office.get('evidence_candidate_id', doctor['candidate_id']),
                                           office['site_id'], intended)
        original = found['original_medicare']
        plan_rows = {}
        for identifier, evidence in found['plans'].items():
            observations = evidence.get('observations', ())
            dates = sorted({row['observed_on'] for row in observations if row.get('observed_on')})
            plan_rows[identifier] = {'name': evidence['name'], 'state': evidence['state'],
                                     'membership': evidence.get('membership'), 'evidence_dates': dates}
        return {'kind': 'doctor_matrix', 'key': 'doctor:' + item, 'name': doctor['label'],
                'office_parts': place_office(office['address'], place),
                'date': intended, 'plans': plan_rows, 'participant_release': False,
                'original_medicare': original_medicare_evidence(original),
                'details': self.doctor_summary(original, True)}

    @staticmethod
    def doctor_name(name):
        """The person's name for search and display, and any place stated with it."""
        plain, place, _ = ConversationChecks.doctor_entry(name)
        return plain, place

    @staticmethod
    def doctor_entry(name):
        """Name, town and practice from one entry as the person wrote it.

        "Dr. Mark Speake at NCH on 9th Street" is a name and a practice;
        "Dr. Kelly Craig, my internist for years" is a name. Searching the whole
        entry as a name matched no one in fifteen live runs (November 13, 2026).
        Only the name is searched; nothing is rewritten or guessed."""
        text = ' '.join(str(name or '').split()).strip(' .')
        cut = _ENTRY_CUT.search(text)
        plain, rest = (text[:cut.start()].strip(' ,.'), text[cut.start():]) if cut else (text, '')
        if not plain or len(plain.split()) > 5:
            return text, None, None
        place = practice = None
        found = re.search(r"(?i)(?:^|[\s,])in\s+((?:[A-Z][\w.'-]*\s?){1,3}(?:,\s*[A-Za-z]{2})?)", rest)
        if found:
            place = found.group(1).strip(' ,.')
        else:
            found = re.match(r"\s*,\s*((?:[A-Z][\w.'-]*\s?){1,3})\s*$", rest)
            if found and found.group(1).strip().casefold() in TOWNS:
                place = found.group(1).strip()
        found = re.search(r"(?i)(?:^|[\s,])(?:at|with)\s+(?:the\s+)?(.+?)(?=,|;|\s+on\s+|\s+in\s+|\s+for\s+|$)", rest)
        if found and not re.match(r"(?i)(?:her|his|their|my|an?|that)\b", found.group(1).strip()):
            practice = found.group(1).strip(' ,.') or None
        return plain, place, practice

    @staticmethod
    def looks_like_place(text):
        """True only for a town, a ZIP code or a practice name typed on its own.

        Any other sentence belongs to the ordinary turn: in the 15-profile run a
        short message ("Female, and I've never used tobacco.") was taken as the
        doctor's city, got no reply and was lost."""
        plain = ' '.join(str(text or '').replace('’', "'").split()).strip(' .!')
        if not plain or '?' in plain or len(plain.split()) > 8 or _SENTENCE_WORD.search(plain):
            return False
        bare = re.sub(r"(?i)^(?:in|at|near|it's|its|the)\s+", '', plain).casefold()
        if re.fullmatch(r'\d{5}', bare) or bare in TOWNS or re.sub(r',?\s*(?:fl|florida)$', '', bare) in TOWNS:
            return True
        if _PRACTICE_WORD.search(plain):
            return True
        words = plain.split()
        return len(words) <= 4 and all(word[:1].isupper() or word.casefold() in ('of', 'and', '&', 'the') for word in words)

    def plan_name(self, plan):
        return 'Original Medicare' if plan=='original_medicare' else next((p['name'] for p in self.plans() if p['id']==plan), '')

    @staticmethod
    def doctor_summary(evidence, original):
        if original:
            lines = []
            if evidence.get('enrollment'):
                for row in evidence['enrollment']:
                    label = {'published_approved_billing_enrollment_in_extract':'approved billing enrollment',
                             'published_ordering_referring_only_enrollment':'ordering and referring only'}.get(row['published_state'],'enrollment status unresolved')
                    lines.append({'approved billing enrollment': f'Medicare lists this doctor as enrolled to bill Medicare (record dated {row["published_on"]}).',
                                  'ordering and referring only': f'Medicare lists this doctor for ordering and referring only, not for billing visits (record dated {row["published_on"]}).'}
                                 .get(label, f'Medicare’s record for this doctor doesn’t settle whether they are enrolled (record dated {row["published_on"]}).'))
            else:
                lines.append('Daylight didn’t find a Medicare enrollment record for this doctor.')
            for row in evidence.get('assignment',[]):
                states = {row['individual_state'], row['group_state']}
                lines.append(f'This office accepts Medicare’s approved amount as full payment (record dated {row["published_on"]}).' if 'published_accepts_assignment' in states
                             else f'This office may accept Medicare’s approved amount as full payment; ask the office (record dated {row["published_on"]}).' if 'published_may_accept_assignment' in states
                             else 'The records don’t show whether this office accepts Medicare’s approved amount as full payment. The office can tell you.')
            if not evidence.get('assignment'):
                lines.append('The records don’t show whether this office accepts Medicare’s approved amount as full payment. The office can tell you.')
            optout = evidence.get('opt_out',[])
            if any(r['interval_state']=='published_interval_contains_date' for r in optout):
                lines.append('Medicare lists this doctor as opted out of Medicare on the date checked.')
        else:
            messages = {'confirmed':'The dated evidence confirms participation for this doctor, office, plan and date.',
                        'dated_listing':'The dated directory lists this doctor and office for this plan. Participation on your intended date still needs confirmation.',
                        'unknown':'Participation is still unknown for this exact office, plan and date.',
                        'stale':'Newer evidence is needed for this office.', 'conflict':'The records disagree; participation remains unresolved.'}
            lines = [messages.get(evidence['state'], messages['unknown'])]
            if evidence.get('membership')=='out_of_network':
                lines[0] = 'The dated evidence confirms this office is out of network for this plan and date.'
            dates = sorted({r['observed_on'] for r in evidence.get('observations',[]) if r.get('observed_on')})
            if dates:
                lines.append('Directory evidence dated ' + ', '.join(dates) + '.')
        if evidence.get('held_plan_joins'):
            lines.append('Some network records could not be linked to this exact plan.')
        return list(dict.fromkeys(lines))

    def drug_step(self, owner, state, guide, record):
        scope, meds, assistance, stamps = reported_fields(guide,record)
        if not meds:
            state['drug'] = {}
            return None, None
        if not self.prescriptions:
            # With no drug service attached, the conversation itself says once that
            # medicines are not checked (ux_flow.finish), so nothing is added here.
            return None, None
        stamp = digest([meds, assistance, stamps, state.get('drug_plan'), state.get('drug_compare')])
        detail = state['drug']
        if detail.get('stamp') != stamp:
            detail.pop('result',None)
            detail.pop('formulary_checked', None)
            detail['stamp'] = stamp
        if state['skipped'].get('drug') == stamp:
            return None, None
        plan = state.get('drug_plan')
        comparing = state.get('drug_compare') if getattr(self.flow, 'd166', False) else None
        selected = {}
        entry = self.snapshot(guide,record,state['chain'])
        if hasattr(self.drugs, 'formulary_matrix'):
            from daylight_data.serving.part_d_math import EstimateHold

            try:
                matrix = self.prescriptions.formulary_matrix(owner, entry)
            except EstimateHold as error:
                return self.drug_hold(state, str(error)), None
            if matrix['state'] == 'held':
                return self.drug_hold(state, matrix['hold']), None
            if matrix['needs']:
                missing = matrix['needs'][0]
                choices = [(row['value'], row['label']) for row in missing['choices']]
                if not choices:
                    return self.ask(state, 'drug', 'formulary_product',
                        'What strength and form does the label show for %s?' % missing['label'],
                        item=missing['item'], why='I haven’t found a product that matches these details.'), None
                return self.ask(state, 'drug', 'formulary_product',
                    DRUG_QUESTIONS['rxcui'].format(medicine=missing['label']),
                    choices=choices, item=missing['item'],
                    why='Choose the strength and form on your label so I can match it to each drug list.'), None
            result = {'kind': 'formulary', 'key': 'formulary', 'name': 'Your medicines across plans',
                      'plans': matrix['plans'], 'participant_release': False}
            example = next(iter(matrix['plans'].values()))['medicines']
            result['products'] = [medicine['rxcui'] for medicine in example]
            result['evidence_date'] = example[0]['evidence_date']
            if comparing:
                selected = {key: value for key, value in matrix['plans'].items()
                            if comparing == 'both' or (key.startswith('2026:S') == (comparing == 'part_d'))}
                # A stable internal input lens, not a selected or recommended plan.
                plan = next(iter(sorted(selected)), None)
                detail['input_plan'] = plan
            if not plan:
                detail['formulary_checked'] = True
                return None, result
            state['results'].append(result)
        if not plan:
            # D157 (CV-21, CV-22): never ask the person to pick a plan so a check
            # can run. Say once that medicines are not checked against each drug
            # list yet; checking every plan is a data-layer capability (handoff).
            # One line that stays with the check results. It was a one-time result,
            # and the page reads the checks more than once a turn, so the live run
            # never showed it (November 12, 2026).
            return None, {'kind': 'note', 'key': 'drug', 'name': 'Your medicines', 'participant_release': False,
                          'details': ['Your medicines aren’t checked against each plan’s drug list yet. '
                                      'Each plan shows that.']}
        current = self.prescriptions.dispatch(owner, {'action':'read', 'continuation':entry['response']['continuation'],
                                                       'offering_id':plan}, _entry=entry)
        detail['current'] = current
        if comparing and selected:
            from drug_comparison import compare
            live, medicines, help_report, issue = self.prescriptions.sync(owner, entry, plan)
            report = self.prescriptions.report(live, medicines, help_report)
            if not issue and report.get('pharmacy') and report['pharmacy'].get('channel'):
                compared = compare(self.drugs, report, live['revision'], selected, costs=current['state'] == 'ready')
                compared['editable'] = current.get('editable', [])
                state['results'].append(compared)
                if current['state'] == 'ready':
                    return None, None
        if current['state']=='missing':
            q = current['question']
            field = q['field']
            # Home ZIP is a search starting point only. The person explicitly
            # chooses the exact outlet; it never establishes pharmacy identity.
            if field=='outlet_zip' and not detail.get('custom_zip'):
                current = self.prescriptions.dispatch(owner, {'action':'answer',
                    'continuation':entry['response']['continuation'], 'offering_id':plan,
                    'revision':current['revision'], 'value':scope['inputs']['zipcode']}, _entry=entry)
                detail['current'] = current
                q = current.get('question',q); field=q['field']
            choices = [(p['value'],p['label']) for p in q.get('choices',[])] or DRUG_CHOICES.get(field,[])
            if field=='rxcui' and not detail.get('all_products',{}).get(q.get('item')):
                single=[p for p in choices if '/' not in p[1]]
                if single and len(single)<len(choices):
                    choices=[*single,('__products__','Show other matches, including combination medicines')]
            if field=='pharmacy':
                reported = q.get('reported') or ''
                brand = re.split(r'[,;]|\bin\b',reported, maxsplit=1)[0].strip().casefold()
                matched = [p for p in choices if brand and brand in p[1].casefold()]
                if matched: choices=matched
                choices = [*choices, ('__zip__','My pharmacy is in another ZIP code')]
            why = {'rxcui':'The strength and form need to match before I use a drug-list record.',
                   'days_supply':'Use 30 days for this estimate, or choose 90 days if that matches your refill.',
                   'pharmacy':f'I’m showing locations near ZIP {q.get("zip",scope["inputs"]["zipcode"])}. Choose your exact store.',
                   'fills':('For example, December 1, 2026. Separate several dates with semicolons. Only those fills will be included.'
                            if len(meds)==1 else 'Give each date and its order among all medicines filled that day, for example December 1, 2026 / 2 for the second fill. Separate several fills with semicolons.'),
                   'period':'The estimate covers that month through December 31, 2026.',
                   'prior_spending':'Earlier spending can change how much of a refill you pay.'}.get(field,'')
            if field in ('rxcui','pharmacy') and not q.get('choices'):
                why = 'I haven’t found an exact match. You can correct the details in your message or leave this open.'
            question = ('Should I use a 30-day refill for {medicine}?' if field == 'days_supply'
                        else 'Which location of your reported pharmacy should I use?' if field == 'pharmacy' and q.get('reported')
                        else DRUG_QUESTIONS[field])
            return self.ask(state,'drug',field,question.format(medicine=q.get('label','this medicine')),
                choices=choices, why=why, item=q.get('item')), None
        if current['state']=='held':
            return self.drug_hold(state,current['hold']), None
        if current['state']=='ready':
            cached=detail.get('result')
            if cached and detail.get('receipt') and detail.get('receipt_revision')==current['revision']:
                valid=self.prescriptions.dispatch(owner, {'action':'validate',
                    'continuation':entry['response']['continuation'], 'offering_id':plan,
                    'revision':current['revision'], 'receipt':detail['receipt']},_entry=entry)
                if valid['state']=='current':return None,cached
                detail.pop('result',None)
                return self.drug_hold(state,valid.get('hold','result_changed')),None
            result = self.prescriptions.dispatch(owner, {'action':'estimate',
                'continuation':entry['response']['continuation'], 'offering_id':plan,
                'revision':current['revision']}, _entry=entry)
            if result['state']!='offline_average_candidate':
                return self.drug_hold(state,result.get('hold','unavailable')), None
            detail['result'] = {'kind':'prescription', 'key':'drug', 'name':self.plan_name(plan),
                'amounts':{k:result[k] for k in ('drug_spending_cents','plan_premium_cents','plan_premium_plus_drugs_cents')},
                'start':result['start'], 'end':result['end'], 'expires_at':result['expires_at'],
                'summary':current.get('summary'), 'participant_release':False,
                'editable':current.get('editable',[]),
                'details':['Estimate using published retail averages. Your pharmacy’s price may differ.',
                           'Local evaluation only; this is not an approved personal quote.']}
            detail['receipt']=result['receipt'];detail['receipt_revision']=current['revision']
            return None, detail['result']
        return None, None

    def drug_hold(self,state,reason):
        state['drug'].pop('result',None)
        return self.ask(state,'drug','drug_hold','Would you like to continue with the plan details and leave this cost check open?',
            choices=[('__later__','Continue with my other details')], why=self.hold_message(reason))

    @staticmethod
    def hold_message(reason):
        if reason.startswith('PILOT_SOURCE_'):
            return 'The source information is unavailable, so I can’t show a current result. Your details are still here.'
        return HOLDS.get(reason,'I can’t establish this result from the available evidence. We can keep going with the details we do have.')

    def answer(self, owner, guide, record, token, value, parked=False):
        state = self.visit(owner,guide,record)
        q = state.get('question')
        if not q or q['token'] != token:
            raise ProfileError('That question changed. Use the current question; your details are still here.',409)
        before = deepcopy({key: value for key,value in state.items() if key != 'history'})
        drug_before = deepcopy(self.prescriptions.visits.get(owner)) if self.prescriptions else None
        if value=='__later__':
            key='doctor:'+q['item'] if q['kind']=='doctor' else 'drug'
            state['skipped'][key]=(state['doctors'][q['item']]['stamp'] if q['kind']=='doctor' else state['drug'].get('stamp'))
            # CV-19: one line on what leaving it open means, shown with the next reply.
            if q['kind']=='doctor':
                who=self.doctor_name(state['doctors'][q['item']]['report']['name'])[0]
                state.setdefault('notes',[]).append({'kind':'note','key':key,'name':who,'participant_release':False,
                    'details':[('I’ll leave %s’s office open for now. You can add it any time.' if parked else
                                'Left open: plan networks aren’t checked for %s. Each plan will show that.') % who]})
            else:
                state.setdefault('notes',[]).append({'kind':'note','key':key,'name':'Your medicines','participant_release':False,
                    'details':['I’ll leave your medicine details open for now. You can add them any time.' if parked else
                               'Left open: your medicines aren’t checked against plan drug lists. Each plan will show that.']})
        elif q['kind']=='doctor':
            detail=state['doctors'][q['item']]
            field=q['field']
            if value=='__retry__': detail.pop('candidates',None)
            elif field=='doctor_location':
                if not isinstance(value,str) or not 1 <= len(value.strip()) <= 120:
                    raise ProfileError('Tell me the city or practice, or leave this detail open.',422)
                detail.update(location=value.strip(), refined=True, needs_location=False, practice_asked=True,
                              offset=0)
                detail.pop('candidates',None)
            elif field=='doctor' and value in ('__more__','__refine__','__all__'):
                detail['passed']=[*detail.get('passed',[]),*(p['candidate_id'] for p in detail.get('candidates',[]))][-200:]
                if value=='__more__': detail['offset']=detail.get('next_offset') or 0
                if value=='__refine__': detail['needs_location']=True
                if value=='__all__': detail.update(region='all_retained',offset=0,refined=True)
                if value!='__refine__': detail.pop('candidates',None)
            elif field=='office' and value=='__refine__' and detail.get('implicit_doctor'):
                detail['passed']=[*detail.get('passed',[]),detail['doctor']['candidate_id']][-200:]
                for key in ('doctor','implicit_doctor','offices','next_office','office_offset'):
                    detail.pop(key,None)
                detail['needs_location']=True
            elif field=='office' and value=='__more__':
                detail['office_offset']=detail.get('next_office') or 0
                detail.pop('offices',None)
            elif field in ('doctor','office'):
                rows=detail['candidates' if field=='doctor' else 'offices']
                key='candidate_id' if field=='doctor' else 'site_id'
                matches=[p for p in rows if p[key]==value]
                if len(matches)!=1: raise ProfileError('Choose the exact doctor or office shown here.',422)
                detail[field]=matches[0]
            elif field=='doctor_plan':
                self.listed(q,value);state['doctor_plan']=value
                if value != 'original_medicare' and not state.get('drug_plan'):
                    state['drug_plan']=value
            elif field=='doctor_date':
                checked_date=parse_date(value)
                if not checked_date: raise ProfileError('Use a date in 2026, such as November 17, 2026.',422)
                state['doctor_date']=checked_date
            else: raise ProfileError('Use the current doctor question.',422)
        elif q['field']=='drug_plan':
            self.listed(q,value);state['drug_plan']=value
        elif q['field']=='formulary_product':
            self.listed(q, value)
            entry = self.snapshot(guide, record, state['chain'])
            self.prescriptions.select_formulary_product(owner, entry, q['item'], value)
        elif value=='__retry__':
            pass
        elif q['field']=='rxcui' and value=='__products__':
            state['drug'].setdefault('all_products',{})[q['item']]=True
        else:
            detail=state['drug']; plan=detail.get('input_plan') or state.get('drug_plan')
            entry=self.snapshot(guide,record,state['chain'])
            current=detail.get('current',{})
            body={'action':'answer','continuation':entry['response']['continuation'],
                  'offering_id':plan,'revision':current.get('revision'),'value':value}
            if value=='__zip__' and q['field']=='pharmacy':
                body={'action':'edit',**{k:v for k,v in body.items() if k not in ('action','value')},'field':'outlet_zip','item':None}
                detail['custom_zip']=True
            else:
                body['value']=self.drug_value(q,value,guide,record)
            self.prescriptions.dispatch(owner,body,_entry=entry)
        state.setdefault('history',[]).append((before,drug_before))
        state['history'] = state['history'][-24:]
        state['question']=None

    def back(self,owner,guide,record):
        self.reconcile(owner,guide,record)
        state=self.visit(owner,guide,record)
        if not state.get('history'):
            raise ProfileError('There is no earlier check answer in this visit.',409)
        before,drug_before=state['history'].pop()
        history=state['history']
        state.clear();state.update(before,history=history,results=[],question=None)
        state['drug'].pop('result',None);state['drug'].pop('receipt',None)
        if self.prescriptions:
            if drug_before:
                drug_before.pop('receipt',None)
                self.prescriptions.visits[owner]=drug_before
            else:self.prescriptions.visits.pop(owner,None)

    @staticmethod
    def listed(question,value):
        if not any(row['value']==value for row in question['choices']):
            raise ProfileError('Choose one of the listed answers.',422)

    @staticmethod
    def drug_value(q,value,guide,record):
        field=q['field']
        if field in ('quantity','days_supply') and isinstance(value,str):
            match=re.fullmatch(r'(\d+)(?:\s+(?:tablets?|capsules?|days?))?[.!]?',value.strip(),re.I)
            if match: return int(match[1])
        if field=='fills' and isinstance(value,str):
            _,meds,_,_=reported_fields(guide,record)
            fills=[]
            for text in re.split(r';|\n|\s+and\s+',value):
                pair=text.rsplit(' / ',1)
                parsed=parse_date(pair[0].strip())
                order=int(pair[1]) if len(pair)==2 and pair[1].strip().isdigit() else (1 if len(meds)==1 else None)
                if not parsed or not order:
                    raise ProfileError('Give each refill date and, for multiple medicines, its order that day: December 1, 2026 / 2.',422)
                fills.append({'date':parsed,'order':order})
            if not fills:
                raise ProfileError('Give a date such as December 1, 2026, or several dates separated by semicolons.',422)
            return fills
        if field=='period' and isinstance(value,str):
            for row in DRUG_CHOICES['period']:
                if value.strip().casefold() in (row[1].casefold(),row[1].split()[0].casefold()): return row[0]
        return value

    def text_answer(self,owner,guide,record,text):
        state=self.visit(owner,guide,record);q=state.get('question')
        if not q:return False
        plain=text.strip().rstrip('.!?').casefold()
        value=None
        if plain in ("i don't know",'i don’t know','not sure','later','skip','check later','leave it open'):
            value='__later__'
        else:
            matches=[p['value'] for p in q['choices'] if plain in (str(p['value']).casefold(),p['label'].casefold())]
            if len(matches)==1: value=matches[0]
            elif q['field'] in ('quantity','days_supply') and re.fullmatch(r'\d+(?:\s+(?:tablets?|capsules?|days?))?',plain): value=text
            elif q['field'] in ('doctor_date','fills') and parse_date(text): value=text
            elif q['field']=='fills' and all(parse_date(x.strip().rsplit(' / ',1)[0]) for x in re.split(r';|\n|\s+and\s+',text)): value=text
            elif q['field']=='period' and any(plain in (label.casefold(),label.split()[0].casefold()) for _,label in DRUG_CHOICES['period']): value=text
            elif q['field']=='outlet_zip' and re.fullmatch(r'\d{5}',plain): value=text
            elif q['field']=='doctor_location' and self.looks_like_place(text): value=text
        if value is None:return False
        self.answer(owner,guide,record,q['token'],value)
        return True

    def edit(self,owner,guide,record,key,field):
        state=self.visit(owner,guide,record)
        if key.startswith('doctor:') and key[7:] in state['doctors'] and field in ('plan','date','office'):
            if field=='office':state['doctors'][key[7:]].pop('office',None)
            else:
                state.pop('doctor_'+field,None)
                state['doctor_'+field+'_asked']=True
            state['skipped'].pop(key,None)
        elif key == 'formulary' and field == 'products':
            prior = self.prescriptions.visits.get(owner) if self.prescriptions else None
            if prior:
                prior['meds'].clear()
                prior.pop('matrix', None)
            state['drug'].pop('formulary_checked', None)
            state['skipped'].pop('drug', None)
            state['shown'] = {key: value for key, value in state.get('shown', {}).items()
                              if not key.startswith('drug:')}
        elif key=='drug' and field=='plan':
            state.pop('drug_plan',None);state['drug'].pop('result',None);state['skipped'].pop('drug',None)
        elif key=='drug' or key.startswith('drug:'):
            item=key[5:] if key.startswith('drug:') else None
            current=state['drug'].get('current',{})
            if not any(row['field']==field and row['item']==item for row in current.get('editable',[])):
                raise ProfileError('Choose a detail from the current estimate.',422)
            entry=self.snapshot(guide,record,state['chain'])
            self.prescriptions.dispatch(owner,{'action':'edit','continuation':entry['response']['continuation'],
                'offering_id':state['drug'].get('input_plan') or state.get('drug_plan'),'revision':current['revision'],'field':field,'item':item},_entry=entry)
            state['drug'].pop('result',None);state['drug'].pop('receipt',None)
            if field=='outlet_zip':state['drug']['custom_zip']=True
            state['skipped'].pop('drug',None)
        else:
            raise ProfileError('Choose a detail from the current check.',422)
        state['question']=None

    @staticmethod
    def public(state):
        q=state.get('question')
        return {'question':{k:v for k,v in q.items() if not k.startswith('_')} if q else None,
                'results':deepcopy(state['results']), 'canBack':bool(state.get('history')), 'participant_release':False}

    def answered_locally(self,owner,guide,record):
        state=self.visits.get(owner)
        if not state:return set()
        current=digest([scope_profile(guide,record),doctor_reports(guide,record),reported_fields(guide,record)])
        if current != state.get('report_stamp'):return set()
        suppressed=set()
        doctors=state['doctors']
        if doctors and all(d.get('office') or state['skipped'].get('doctor:'+key)==d['stamp'] for key,d in doctors.items()):
            suppressed.add('RC21')
        drug=state['drug']
        if drug.get('result') or drug.get('formulary_checked') or drug.get('stamp') and state['skipped'].get('drug')==drug['stamp']:
            suppressed.update(('RC22','RC23'))
        return suppressed

    def attach(self,owner,out,*,show_question=True,count=False):
        if getattr(self.flow, 'd166', False) and not show_question:
            # Preserve the visit's check state for resumption; unrelated questions
            # neither run more research nor render an old result card.
            out['conversationCheck'] = {'question': None, 'results': [], 'canBack': False,
                                        'participant_release': False, 'paused': True}
            return out
        view=self.reconcile(owner,out['guide'],out['record'])
        if count and show_question and view['question']:
            # One question never owns the conversation (15-profile run, November 13, 2026):
            # shown once, shown once more, then parked with one line. It comes back
            # from "Edit doctor details" or when the person raises it.
            state=self.visits.get(owner) or {}
            q=state.get('question')
            if q:
                item = q.get('item')
                stamp = (state['doctors'].get(item, {}).get('stamp') if q['kind'] == 'doctor'
                         else state['drug'].get('stamp'))
                key=':'.join(str(part) for part in (q['kind'],item,q['field'],stamp))
                shown=state.setdefault('shown',{})
                shown[key]=shown.get(key,0)+1
                if shown[key]>2:
                    self.answer(owner,out['guide'],out['record'],q['token'],'__later__',parked=True)
                    view=self.reconcile(owner,out['guide'],out['record'])
        if not show_question:
            view['question']=None
        view['paused']=not show_question
        out['conversationCheck']=view
        q=view['question'] if show_question else None
        if q:
            identifier='RC21' if q['kind']=='doctor' else 'RC22' if q['field'] in ('rxcui', 'formulary_product') else 'RC23'
            out['assessment']['nextQuestion']={'id':identifier,'entity':q.get('item') or 'profile',
                'question':q['question'],'why':q['why'],'choices':[], 'fields':[],
                'conversational':True, 'signature':'check:'+q['token'], 'localCheck':True}
            out['assessment']['narrative']['opener']=False
            out['assessment']['intakePaused']=False
        elif show_question and (out['assessment'].get('nextQuestion') or {}).get('id') in self.answered_locally(owner,out['guide'],out['record']):
            choices=self.flow.eligible(owner,out['guide'],out['record'])
            out['assessment']['nextQuestion']=deepcopy(choices[0]['question']) if choices else None
        return out
