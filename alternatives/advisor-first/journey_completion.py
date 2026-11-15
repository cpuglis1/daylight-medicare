"""Visit-only useful finishes. No source admission, recommendation or transaction.

Software summarizes recorded work and open dependencies. The language model
still answers questions; ending a conversation never completes a held check.
"""
import re


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
    action = ('Use the Part A / Part B sign-up guide and confirm the dates that apply to your situation.' if kind == 'ab_preparation'
              else 'Return when the requested year’s plan, formulary and pharmacy evidence is available.' if unsupported_year
              else unresolved[0] if unresolved else 'Reopen this conversation when you want to explore further; no policy was selected by browsing.')
    outcome = {'kind': kind, 'goal_complete': kind in ('education_complete', 'research_summary', 'ab_preparation', 'keep_current', 'wait'),
               'decision': decision, 'work': work, 'unresolved': unresolved, 'next_action': action}
    card = {'kind': 'finish_summary', 'title': 'Your visit summary', 'finish': kind,
            'rows': [{'label': 'Work performed', 'value': ' '.join(work)}, {'label': 'Your decision', 'value': decision},
                     {'label': 'Still open', 'value': ' '.join(unresolved) or 'No further personal checks requested in this visit.'},
                     {'label': 'Next action', 'value': action}], 'sources': []}
    return outcome, card
