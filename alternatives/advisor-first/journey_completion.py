"""Visit-only useful finishes. No source admission, recommendation or transaction.

Software summarizes recorded work and open dependencies. The language model
still answers questions; ending a conversation never completes a held check.
"""
import re
import copy
from plan_review import readiness, input_digest


def enabled(flow):
    return bool(getattr(flow, 'guided_close', False))


def comparison_status(g, r, pending=None):
    actual=readiness(g,r,pending=pending)
    goal=g['fields'].get('intent.goal',{})
    if not actual['active'] and goal.get('status')=='reported' and goal.get('value') in ('compare','review'):
        shadow=copy.deepcopy(r)
        shadow.setdefault('conversation',{})['task']=goal['value']
        retained=readiness(g,shadow,pending=pending)
        # A detour/pause retains the comparison's information, not permission to review.
        retained['canReview']=False
        return retained
    return actual


def progress(flow, g, r, pending=None):
    status = comparison_status(g, r, pending)
    criteria = status.get('criteria', [])
    return {'active': bool(status.get('active')), 'total': len(criteria),
            'addressed': sum(bool(c['addressed']) for c in criteria),
            'open': [c['label'] for c in criteria if c['state'] in ('unknown','deferred','declined')],
            'ready': bool(status.get('canReview'))}


def reviewed_status(flow, owner, g, r):
    """Recheck a receipt's profile independently of the current discussion view.

    Caller still validates owner, chain, exact report digest and expiry. This
    cannot create a receipt or authorize an unreviewed comparison.
    """
    goal=g['fields'].get('intent.goal',{})
    if enabled(flow) and goal.get('status')=='reported' and goal.get('value') in ('compare','review'):
        r=copy.deepcopy(r)
        r.setdefault('conversation',{})['task']=goal['value']
    return readiness(g,r,pending=flow.pending_for(owner))


def comparison_brief(flow, g, r, state, out=None):
    """A code-owned account of this profile and available actions, not suitability."""
    import enrollment_flow
    out = out or {}
    status = comparison_status(g, r)
    enrollment = out.get('enrollment') or enrollment_flow.view(flow, g, r)
    destination = _close_destination(state)
    rows = [copy.deepcopy(row) for row in flow.rows(g, r)
            if row['id'] in {'T01','T03','T04','T05','RC04','RC11','T06','T07','T08','T09','T10'}]
    # Detail lists stay editable in the existing review. Keep this payoff readable.
    rows = rows[:12]
    steps = []
    line = enrollment.get('line') or {}
    next_enrollment = line.get('next', {})
    record = enrollment.get('record') or {}
    if next_enrollment.get('id') and not next_enrollment['id'].startswith('choose_') and next_enrollment.get('text'):
        # D181: one timing step, written as an action. A route the timing code cannot
        # compute points to the sign-up guide instead of a bare phone number.
        working = 'employer' in (flow.value(g,'coverage.current') or [])
        if working and not (record.get('coverage_end') or flow.report(r,'RC11').get('coverageEnd')):
            steps.append({'text':'Tell me when your job coverage ends, so your Part A and Part B sign-up can be lined up with that date.', 'view':'ab'})
        elif next_enrollment['id'] == 'confirm_with_social_security':
            steps.append({'text':('Ask Social Security about the denial. Your sign-up guide has the details.'
                                  if 'denial' in next_enrollment['text'] else
                                  'Line up your Part A and Part B sign-up with Social Security. Your sign-up guide has the details.'), 'view':'ab'})
        else:
            steps.append({'text':_sentence(next_enrollment['text']), 'view':'ab'})
    names={'paths':'both coverage paths','supplement':'Original Medicare with Medigap',
           'advantage':'Medicare Advantage','part-d':'separate prescription drug plans'}
    reasons = _direction_reasons(flow, g) if destination == 'paths' else ''
    direction = None
    if reasons:
        # Owner-approved process direction (November 15, 2026): where to start looking,
        # from the person's own priorities. Not a fit finding or a recommendation.
        direction = ('Original Medicare with Medigap is worth looking at first, since you put %s first. '
                     'Then look at Medicare Advantage the same way.' % reasons)
        steps.append({'text':'Compare Original Medicare with Medigap first, then Medicare Advantage, using your priorities, doctor access and costs.', 'view':'supplement'})
        import medigap_profile
        if medigap_profile.for_flow(flow, g, r)['status'] == 'ready':
            destination = 'supplement'   # D181: the handoff opens the Medigap prices directly
    else:
        steps.append({'text':'Compare '+names[destination]+' using your priorities, doctor access and costs.', 'view':destination})
    if len(steps) < 3 and destination != 'part-d' and flow.value(g,'needs.medicinesStatus') not in ('no','none'):
        steps.append({'text':'Review medicine coverage and costs for the options you are considering.',
                      'view':{'advantage':'advantage-drugs','paths':'paths'}.get(destination,'part-d')})
    learned = _learned(flow, g, r, line, (out.get('conversationCheck') or {}).get('results', []))
    open_details=[c['label'] for c in status.get('criteria',[]) if c['state'] in ('unknown','deferred','declined','needs_clarification','missing')]
    open_details=list(dict.fromkeys(open_details+[h['label'] for h in status.get('holds',[])]))
    year = flow.report(r,'RC03').get('year')
    if year and str(year) != '2026':
        open_details.append('The requested year’s plan evidence is unavailable; 2026 listings cannot answer that comparison.')
    checks=(out.get('conversationCheck') or {}).get('results', [])
    findings=[]
    for result in checks:
        if result.get('kind')=='doctor_matrix':
            findings.append('Your confirmed doctor office is retained. You can reopen its participation and network results above.')
        elif result.get('kind')=='formulary':
            findings.append('Your exact medicine selections are retained. Drug-list results are available above; personal costs are a separate check.')
    return {'version':'guided-close-v1', 'revision':input_digest(g,r),
            'title':'Your plan from here', 'rows':rows, 'findings':findings[:4],
            'open':open_details, 'steps':steps[:3], 'destination':destination,
            'learned':learned, 'direction':direction,
            'ready':bool(status.get('canReview')), 'recommendation':None,
            'purpose':'Review the retained details and continue the comparison; no coverage choice or personal fit finding is inferred.'}


def _close_destination(state):
    destination = {'original_medigap':'supplement', 'original':'supplement',
                   'medicare_advantage':'advantage'}.get(state.get('decision', {}).get('path'), 'paths')
    products = state.get('plans_products', state.get('task_investigate', []))
    products = [p for p in products if p in ('medigap','part_d','advantage')]
    if destination == 'paths' and len(products) == 1:
        destination = {'medigap':'supplement','part_d':'part-d','advantage':'advantage'}[products[0]]
    return destination


def medigap_before_close(flow, g, r, state):
    """D181: when the close will point to Medigap, its price details are asked first,
    so the Medigap page opens on prices. Same questions and reasons as the tab uses."""
    import medigap_profile
    destination = _close_destination(state)
    if not (destination == 'supplement' or destination == 'paths' and _direction_reasons(flow, g)):
        return []
    if 'advantage' in (flow.value(g, 'coverage.current') or []):
        return []
    view = medigap_profile.for_flow(flow, g, r)
    if view['status'] != 'missing':
        return []
    return [key for key in view['missing']
            if key not in view['held'] and (key in medigap_profile.FIELDS or key == 'RC06')]


def _sentence(text):
    text = (text or '').strip()
    if not text: return text
    text = text[0].upper() + text[1:]
    return text if text[-1] in '.!?' else text + '.'


def _direction_reasons(flow, g):
    """The person's own priorities that point to starting with Original Medicare
    with Medigap. Mixed signals (lower monthly payments) give no direction."""
    priorities = set(flow.value(g, 'needs.priorities') or [])
    cost = flow.value(g, 'needs.costPreference')
    if cost == 'lower_monthly':
        return ''
    reasons = []
    if 'doctors' in priorities: reasons.append('keeping your doctors')
    if 'bills' in priorities or cost == 'predictable': reasons.append('predictable costs')
    return ' and '.join(reasons)


def _learned(flow, g, r, line, checks=None):
    """Two or three plain lines from the person's own reports (code-built)."""
    by_id = {}
    for row in flow.rows(g, r):
        if row.get('status') == 'reported' and row.get('value') not in (None, '', [], 'None', 'No'):
            by_id.setdefault(row['id'], []).append(row['value'] if isinstance(row['value'], str) else ', '.join(map(str, row['value'])) if isinstance(row['value'], list) else str(row['value']))
    first = lambda i: (by_id.get(i) or [None])[-1]
    learned = []
    situation = [v for v in (first('T05'), first('S_RETIREMENT')) if v]
    status = (line or {}).get('status')
    if status: situation.append(status.rstrip('.'))
    if situation: learned.append({'label':'Your situation', 'value':' · '.join(situation)})
    matters = [v for v in (first('T10'), first('T09')) if v]
    if matters: learned.append({'label':'What matters most', 'value':' · '.join(dict.fromkeys(matters))})
    details = [v for v in (first('T06'), first('T07')) if v and v.lower() not in ('none', 'no')]
    if details:
        import plans_fixes
        ran = plans_fixes.learned_checks(checks) if plans_fixes.enabled(flow) and checks is not None else {}
        pairs = [(first('T06'), ran.get('doctors')), (first('T07'), ran.get('medicines'))]
        pairs = [(v, done) for v, done in pairs if v and v.lower() not in ('none', 'no')]
        if hasattr(flow, 'review_check_items'):
            pairs = flow.review_check_items(g, r, checks or [])
        # D189: a doctor or medicine this visit already checked is not listed as still to check.
        for label, wanted in (('Checked', True), ('To check', False)):
            values = [v for v, done in pairs if bool(done) is wanted]
            if values: learned.append({'label':label, 'value':' · '.join(values)})
    return learned


def suggested_priorities(flow, g):
    """D181: answers the person already gave, shown pre-selected on the priorities
    question so they confirm rather than repeat. Never recorded until sent."""
    suggested = []
    if flow.value(g, 'needs.providers'): suggested.append('doctors')
    if flow.value(g, 'needs.costPreference') == 'predictable': suggested.append('bills')
    return suggested


def timing_question(flow, g, r):
    """D181: when code can compute the sign-up window once it knows the birthday
    month, ask for it before the close instead of referring the person out."""
    import enrollment_flow
    if not enabled(flow) or not enrollment_flow.enabled(flow): return None
    if flow.value(g, 'situation.age65') or 'S_AGE65' in (r.get('dispositions') or {}): return None
    try:
        record = enrollment_flow.journey(flow, g, r)
    except Exception:
        return None
    if record.get('unsupported') or record.get('window'): return None
    if not any(part.get('state') == 'needed' for part in record.get('parts', {}).values()): return None
    return 'S_AGE65'


def closing_due(flow, owner, g, r, state):
    if not enabled(flow) or state['guidance']['mode'] != 'work' or r.get('conversation',{}).get('editing'):
        return False
    status = readiness(g,r,pending=flow.pending_for(owner))
    if status.get('canReview'):
        import conversation_planner
        if conversation_planner.timing_ask(flow, owner, g, r, state, probe=True):
            return False
    return bool(status.get('canReview') and state.get('close_delivered') != input_digest(g,r))


def attach(flow, owner, out, state):
    if not enabled(flow): return
    out['profileProgress'] = progress(flow,out['guide'],out['record'],flow.pending_for(owner))
    asked = out['assessment'].get('nextQuestion')
    if (isinstance(asked, dict) and asked.get('id') == 'T10' and not flow.value(out['guide'], 'needs.priorities')):
        suggested = suggested_priorities(flow, out['guide'])
        if suggested:
            asked['suggestedChoices'] = suggested
            asked['why'] = 'I’ve marked what you’ve told me so far. Change anything, then send.'
    brief = comparison_brief(flow,out['guide'],out['record'],state,out)
    checks = out.get('conversationCheck') or {}
    due = closing_due(flow,owner,out['guide'],out['record'],state)
    if state['guidance']['mode']=='pause' and not out.get('review'):
        _, card = summary(flow,owner,out['guide'],out['record'],{**state,'finish_requested':'summary'},out)
        out.setdefault('cards',[]).append(card)
    elif due and not checks.get('question') and not out.get('review'):
        out['comparisonClose'] = {**brief,'show':True}
        state['close_delivered'] = brief['revision']
        out['assessment']['nextQuestion'] = None
    elif state.get('close_delivered') == brief['revision'] or (out.get('review') or {}).get('kind') == 'plan_profile':
        out['comparisonClose'] = {**brief,'show':False}
    if checks:
        delivered=state.setdefault('check_deliveries',{})
        from conversation_checks import digest
        compact=[]
        for result in checks.get('results',[]):
            key=result.get('key',result['kind']);stamp=digest(result)
            if delivered.get(key)==stamp:compact.append(key)
            else:delivered[key]=stamp
        # Hidden during a detour is not invalidated. A changed evidence digest
        # reopens the result; the visit-bound planner owns lifecycle/reset.
        state['check_deliveries']=dict(list(delivered.items())[-64:])
        checks['compactResults']=compact


def request(text):
    text = (text or '').replace('’', "'")
    finish = re.search(r"\b(?:summari[sz]e|summary|recap|enough for today|finish (?:here|later)|before we finish|need from the box|bring .*finish later|next (?:steps?|action)|what (?:must|do) I (?:still )?(?:confirm|need to check)|wait before choosing)\b", text, re.I)
    if not finish:
        return None
    clauses = re.split(r'(?<=[.!?])\s+|;', text)
    for clause in clauses:
        if re.search(r"\b(?:if|whether|should|would|you (?:said|showed))\b", clause, re.I):
            continue
        if re.search(r"\b(?:I(?:'m| am|'ll| will)? (?:going to )?wait|I'll (?:decide|choose) later)\b", clause, re.I):
            return 'wait'
        if re.search(r"\b(?:I'll |I will |I am |I'm )?keep(?:ing)? (?:my |the )?(?:current|work|employer) coverage\b", clause, re.I):
            return 'keep_current'
    if re.search(r'\b(?:part [ab]|a and b|a & b|sign[ -]?up)\b', text, re.I):
        return 'ab_preparation'
    return 'summary'


def summary(flow, owner, g, r, state, out):
    import enrollment_flow
    kind = state['finish_requested']
    record = enrollment_flow.journey(flow, g, r)
    investigations = state.get('task_investigate', [])
    checks = out.get('conversationCheck') or {}
    results = checks.get('results', [])
    controller = getattr(flow, 'conversation_checks', None)
    if controller and state.get('last_check_results'):
        # Revalidate retained checks against current reports and source STOPs.
        # No selections or missing personal inputs are supplied by finishing.
        results = controller.reconcile(owner, g, r).get('results', [])
    work, unresolved = [], []
    if any((flow.value(g, field) or {}).get('status') == 'conflicting' for field in enrollment_flow.PART_FIELDS.values()):
        unresolved.append('Clarify which Medicare parts are currently in effect; contradictory reports remain unresolved.')
    for result in results:
        if result.get('kind') == 'doctor_matrix':
            rows = list(result.get('plans', {}).values())
            listed = sum(row.get('membership') in ('listed_in_network', 'in_network') for row in rows)
            unknown = sum(row.get('state') not in ('listed', 'not_listed')
                          and row.get('membership') not in ('listed_in_network', 'in_network', 'not_listed') for row in rows)
            work.append('%s: dated office evidence checked across %s Advantage offerings; %s list this office in network, and %s remain unknown. Original Medicare participation is a separate result.' % (result['name'], len(rows), listed, unknown))
            if unknown:
                unresolved.append('Confirm %s at the exact office with any plan whose network evidence remains unknown before relying on that plan for this doctor.' % result['name'])
        elif result.get('kind') == 'formulary':
            work.append('The selected medicine identities were checked against the dated medicine lists. Listing alone does not establish price.')
        elif result.get('kind') == 'drug_comparison':
            rows = list(result.get('plans', {}).values())
            ready = sum(row.get('state') == 'offline_average_candidate' for row in rows)
            work.append('%s of %s offerings have a premium-plus-drug estimate for the supplied refill period. These use retail averages, not exact-store prices.' % (ready, len(rows)))
            if ready < len(rows): unresolved.append('Confirm missing medicine and pharmacy evidence for %s held offerings before choosing on total cost; unavailable costs are not ranked as cheaper or more expensive.' % (len(rows)-ready))
    year = flow.report(r, 'RC03').get('year') or '2026'
    unsupported_year = str(year) != '2026'
    if unsupported_year:
        unresolved.append('The requested %s plan, medicine and pharmacy evidence is unavailable. Available 2026 records do not answer that request.' % year)
    if 'doctors' in investigations or flow.value(g, 'needs.providers'):
        if not any(x.get('kind') == 'doctor_matrix' for x in results):
            unresolved.append('Confirm each doctor and exact office, then check Original Medicare participation and each Advantage network separately.')
    if set(investigations) & {'medicines', 'part_d'} or flow.value(g, 'needs.medications'):
        if not any(x.get('kind') == 'drug_comparison' for x in results):
            unresolved.append('Personal drug costs remain unchecked. Bring the medicine name, strength, form, quantity, days supply and exact pharmacy; assistance and refill-period inputs also need confirmation.')
    if 'medigap' in investigations:
        work.append('Requested Medigap premium research retained. Listed premiums are not a binding quote, acceptance guarantee or total annual cost.')
        unresolved.append('Confirm the exact policy type, current quote, switching rights and effective date before replacing coverage.')
    if kind == 'summary':
        kind = 'education_complete' if state.get('education_only') or not investigations and not results and not unresolved else 'research_summary'
    if unsupported_year or kind == 'research_summary' and unresolved:
        kind = 'source_blocked'
    if kind == 'ab_preparation':
        work.append('Part A / Part B status and the applicable sign-up preparation route reviewed.')
        unresolved.append('Confirm the application route and coverage start with Social Security. Preparation has not submitted an application.')
    if kind in ('wait', 'keep_current'):
        unresolved.append('Confirm any enrollment deadline and effects on current coverage before a later change; waiting does not stop a deadline.')
    decision = {'keep_current': 'Keep current coverage', 'wait': 'Wait before choosing additional coverage'}.get(kind)
    if not decision:
        components = record['components']
        decision = ('Keep the existing Medigap policy; separate drug choice remains open'
                    if components['medigap'] == 'keep_existing' else 'No coverage choice recorded' if state['decision']['stance'] != 'chosen'
                    else state['decision']['path'].replace('_', ' '))
    if not work:
        work = ['Reviewed the coverage questions and reports in this visit. No personal comparison is recorded as completed.']
    # D200: Parts A and B not yet in effect or not confirmed are the concrete next
    # step, never "reopen this conversation".
    open_parts = [part for part in ('A', 'B')
                  if ((record.get('parts') or {}).get(part) or {}).get('state') in ('needed', 'unknown', 'needs_info')]
    ab_step = (('Call Social Security (%s) to confirm when %s should start. Waiting does not stop a sign-up deadline.'
                % (enrollment_flow.SSA_PHONE, ' and '.join('Part ' + part for part in open_parts))) if open_parts and kind != 'ab_preparation' else None)
    action = ('Use the Part A / Part B sign-up guide and confirm the dates that apply to your situation.' if kind == 'ab_preparation'
              else 'Return when the requested year’s plan, formulary and pharmacy evidence is available.' if unsupported_year
              else unresolved[0] if unresolved else ab_step if ab_step
              else 'Reopen this conversation when you want to explore further; no policy was selected by browsing.')
    outcome = {'kind': kind, 'goal_complete': kind in ('education_complete', 'research_summary', 'ab_preparation', 'keep_current', 'wait'),
               'decision': decision, 'work': work, 'unresolved': unresolved, 'next_action': action}
    card = {'kind': 'finish_summary', 'title': 'Your visit summary', 'finish': kind,
            'rows': [{'label': 'Work performed', 'value': ' '.join(work)}, {'label': 'Your decision', 'value': decision},
                     {'label': 'Still open', 'value': ' '.join(unresolved) or 'No further personal checks requested in this visit.'},
                     {'label': 'Next action', 'value': action}], 'sources': []}
    if enabled(flow):
        brief = comparison_brief(flow,g,r,state,out)
        brief['findings'] = work
        brief['open'] = list(dict.fromkeys(brief['open'] + unresolved))
        brief['decision'] = decision
        if kind in ('keep_current','wait','education_complete','source_blocked'):
            brief['steps'] = [{'text':action,'view':'ab' if action == ab_step else None}]
        elif kind == 'ab_preparation':
            brief['steps'] = [{'text':action,'view':'ab'}]
        card = {'kind':'guided_summary', **brief}
    return outcome, card
