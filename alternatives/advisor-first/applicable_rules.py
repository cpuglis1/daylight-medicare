"""Deterministic rule selection for the advisor (owner direction, November 8, 2026).

Daylight redirects; it does not deflect. Before the advisor composes a reply,
the server selects the general Medicare rules whose conditions the person's
resolved reports already meet or make relevant, and names the one approved
question that would confirm what is still personal. The model states the rule
in plain words; it never decides eligibility, dates or amounts.

Every rule points at a reviewed statement in ``pilot-rules.json`` or the
existing evidence files. Selection reads resolved reports only, never raw
message text, so the same reports always select the same rules (D64).
"""
from datetime import date
import re

__all__ = ['applicable_rules', 'required_target', 'floor_statement', 'offer_pattern', 'referral_pattern']

# Follow-up questions that merely offer to prepare material or a call for a
# third party. They satisfy "ends with a question" without learning anything
# about the person, so they are not accepted while an approved meaning is open.
offer_pattern = re.compile(
    r"(?i)^\s*(?:would (?:you|it) (?:like|help|be helpful)|do you want (?:me|help|a)|shall i|want me to|"
    r"can i (?:help|put|prepare|draft)|should i (?:put|prepare|draft|write))\b")
referral_pattern = re.compile(
    r"(?i)\b(?:questions?|checklist|list|script|notes?) (?:to|for|you can) (?:ask|take|bring|use|read)\b|"
    r"\b(?:conversation|call|appointment|visit) with (?:social security|medicare|your (?:benefits|hr|plan|pharmacist|doctor)|the (?:plan|pharmacist|employer))\b|"
    r"\bprepar(?:e|ing) (?:for )?(?:that|the|a) (?:call|conversation)\b")


def _choice(report):
    return (report or {}).get('choice')


def _month_start(value):
    """A reported YYYY-MM or YYYY-MM-DD string as the first day of that month, else None."""
    if not isinstance(value, str):
        return None
    match = re.match(r'^((?:19|20)\d{2})-(0[1-9]|1[0-2])', value.strip())
    return date(int(match.group(1)), int(match.group(2)), 1) if match else None


def _add_months(day, months):
    total = day.month - 1 + months
    return date(day.year + total // 12, total % 12 + 1, 1)


def applicable_rules(report, value, *, focus='', today=None, concern='', plans_view=False,
                     trial_at_first_eligibility=None, age_65_or_older=None, day_precision=False):
    """Return the ordered rules for the resolved state.

    ``report(id)`` returns the resolved report dict for an RC meaning (or {});
    ``value(path)`` returns a guide value. Each rule names the statement to use,
    the reports that made it relevant and the approved question that would
    settle the personal part. Nothing here is a personal finding.
    """
    today = today or date.today()
    coverage = set(value('coverage.current') or [])
    rc09, rc10, rc14 = _choice(report('RC09')), _choice(report('RC10')), _choice(report('RC14'))
    rc07, rc16, rc18 = _choice(report('RC07')), _choice(report('RC16')), _choice(report('RC18'))
    rc04, rc12 = _choice(report('RC04')), _choice(report('RC12'))
    rc06, rc08, rc11, rc26 = _choice(report('RC06')), _choice(report('RC08')), _choice(report('RC11')), _choice(report('RC26'))
    age65 = bool(value('situation.age65'))
    birthday = value('situation.age65') if isinstance(value('situation.age65'), dict) else {}
    # True once the reported 65th-birthday month has passed (reported month, no day).
    turned_65 = bool(birthday.get('year') and birthday.get('month')
                     and date(int(birthday['year']), int(birthday['month']), 1) <= date(today.year, today.month, 1))
    cost_preference = value('needs.costPreference')
    priorities = set(value('needs.priorities') or [])
    # Money pressure the person has stated, as the extractor summarised it in the
    # agenda concern (model-derived, never raw text), or as a cost report.
    # Word stems, because the summary is the model's paraphrase: "affording",
    # "affordability", "high drug costs" (R4, Nov 9, 2026: Extra Help never
    # fired for "can barely afford groceries on a fixed income").
    cost_pressure = bool(re.search(
        r"(?i)\b(?:afford\w*|unaffordab\w*|groceries|can'?t pay|cannot pay|struggl\w* (?:to|with) (?:pay|cost|afford)\w*|too expensive|"
        r"bills? pil\w*|(?:low|fixed|limited|small) income|assistance|help (?:paying|with (?:the )?costs?)|"
        r"(?:lower|reduce|cut|save on|cheaper) (?:\w+ ){0,2}(?:drug|prescription|medication|medicine)s?(?: costs?| prices?)?|"
        r"financial (?:strain|hardship|pressure|stress)|(?:high|rising|steep|crushing|large) (?:\w+ ){0,2}(?:costs?|prices?|bills?|copays?)|"
        r"(?:drug|prescription|medication|medicine|insulin|inhaler|pharmacy) (?:costs?|prices?|bills?|copays?) (?:are|is) (?:too|so|very|eating|killing))",
        concern or ''))
    cost_pressure = cost_pressure or _choice(report('RC25')) == 'amount'
    coverage_ended = _month_start(report('RC11').get('coverageEnd')) or _month_start(report('RC11').get('jobEnd'))
    if coverage_ended and (_month_start(report('RC11').get('jobEnd')) or coverage_ended) < coverage_ended:
        coverage_ended = _month_start(report('RC11').get('jobEnd'))
    ended_already = bool(coverage_ended and coverage_ended <= date(today.year, today.month, 1))
    if day_precision:
        # D183: a reported end later this month has not happened yet. Use the
        # stated day, or the last day of a stated month, never the month start.
        from conversation_records import end_date
        ends = [d for d in (end_date(report('RC11').get('jobEnd')), end_date(report('RC11').get('coverageEnd'))) if d]
        ended_already = bool(ends and min(ends) < today)
    if age_65_or_older:
        age65 = True
    working = bool(value('situation.working')) or rc09 in {'my_job', 'spouse_job', 'family_job'}
    on_medicare = bool(coverage & {'original', 'advantage', 'medigap', 'drug'}) or rc04 in {'both', 'a_only', 'b_only'} or rc07 in {'original', 'advantage'}
    has_drug_coverage = bool(coverage & {'advantage', 'drug', 'employer', 'retiree', 'cobra', 'military', 'medicaid'})
    rules = []

    def add(rule_id, fact_id, because, confirm, note):
        rules.append({'rule_id': rule_id, 'fact_id': fact_id, 'applies_because': because,
                      'confirm_with': confirm, 'how_to_use': note})

    # COBRA or retiree coverage is not current employment: Part B timing is
    # the urgent question, before any plan choice (existing reviewed evidence).
    if ('cobra' in coverage or rc09 == 'cobra') and rc04 not in {'both', 'b_only'}:
        add('cobra_not_current_employment', 'cobra_timing', ['coverage.current includes COBRA'],
            ['RC04'] if rc04 is None else [],
            'Say first that COBRA does not count as current-employment coverage and does not extend the time to sign up for Part B, so Part B timing comes before any plan choice; then ask which Medicare parts they have now. Do not compute a personal deadline.')
    # Working-coverage timing: the most common first-time question.
    if ('employer' in coverage or working) and rc09 not in {'retiree', 'cobra'} and not (
            ended_already if day_precision else (coverage_ended and coverage_ended <= date(today.year, today.month, 1))):
        because = ['coverage.current includes current-job coverage' if 'employer' in coverage else 'situation.working']
        if rc10 == 'yes':
            because.append('RC10: employer has 20 or more employees')
            add('working_coverage_sep', 'working_coverage_sep', because, ['RC14' if rc14 is None else None, 'RC09' if rc09 is None else None],
                'State the rule as it applies to job coverage from an employer of 20 or more. The exact Part B start still needs Social Security, but say what the rule means first.')
        elif rc10 == 'no':
            because.append('RC10: fewer than 20 employees')
            # The reviewed small-employer statement (pilot-rules r2) is preferred
            # once accepted; until then the contrast lives in this note only.
            add('small_employer_pays_first', 'small_employer_pays_first', list(because), ['RC09' if rc09 is None else None],
                'State the small-employer rule: Medicare generally pays first, so Medicare.gov says to sign up for A and B when first eligible; then confirm whose job supplies the coverage.')
            add('working_coverage_small_employer', 'working_coverage_sep', because, ['RC09' if rc09 is None else None],
                'With fewer than 20 employees Medicare generally pays first, so delaying Part B can leave gaps. State that contrast, then confirm whose job supplies the coverage.')
        else:
            # RC10 becomes askable once RC09 (whose job) is known; list both so
            # the required question follows the rule's own dependency order.
            add('working_coverage_sep', 'working_coverage_sep', because, ['RC10', 'RC09' if rc09 is None else None],
                'State the rule conditionally ("if the employer has 20 or more employees…") and ask the employer-size question to settle it.')
    if (('employer' in coverage or working) and rc14 is None and age65 and not ended_already) or rc14 == 'yes':
        add('hsa_medicare', 'hsa_medicare', ['current-job coverage with Medicare approaching' if rc14 is None else 'RC14: contributing to an HSA'],
            ['RC14'] if rc14 is None else [], 'Mention only if the person or employer may be adding money to an HSA; it changes when Part A should start.')

    # Job-based coverage that has already ended (or COBRA/retiree reported) with
    # Part B not yet in place: the 8-month window, resolved against the reported
    # end month when there is one (P20, Nov 9, 2026).
    birthday_month = (date(int(birthday['year']), int(birthday['month']), 1)
                      if birthday.get('year') and birthday.get('month') else None)
    # D157 (CV-08): someone still inside their Initial Enrollment Period whose job
    # coverage did not continue to 65 uses that window; the 8-month Special
    # Enrollment Period is for coverage from current work at or after 65.
    in_initial_window = bool(birthday_month and date(today.year, today.month, 1) <= _add_months(birthday_month, 3)
                             and not (coverage_ended and coverage_ended >= birthday_month))
    if not in_initial_window and rc04 in {'a_only', 'neither', None} and (coverage_ended or rc09 in {'cobra', 'retiree'} or 'cobra' in coverage or rc08 == 'loss') and (ended_already or not working):
        because = ['job-based coverage reported as ended' if coverage_ended else 'coverage.current includes COBRA/retiree coverage or a reported loss of coverage']
        if day_precision and coverage_ended:
            # D183: the person's own window is computed once, by the journey, and
            # shown on a code card. The rule states the general rule only.
            status = 'conditional'
            note = ('State the general 8-month special enrollment period after job-based coverage ends, and that COBRA '
                    'does not extend it. The person\'s own months are on the timing card when it is shown; never restate them.')
        elif coverage_ended and coverage_ended <= date(today.year, today.month, 1):
            window_end = _add_months(coverage_ended, 9)  # 8 full months after the month it ended
            because.append('RC11: coverage ended %s; 8-month Part B window runs through %s' % (coverage_ended.strftime('%B %Y'), _add_months(coverage_ended, 8).strftime('%B %Y')))
            status = 'met' if today < window_end else 'not_met'
            note = ('Say that on the reported end month of %s the 8-month special enrollment period for Part B would run through about %s, '
                    'so Part B can be added now without waiting for January; Social Security processes it and confirms the start date.'
                    % (coverage_ended.strftime('%B %Y'), _add_months(coverage_ended, 8).strftime('%B %Y'))) if status == 'met' else (
                    'Say that on the reported end month of %s the 8-month window would have closed around %s, so the General Enrollment Period '
                    '(January–March) is the route unless another special enrollment period applies.' % (coverage_ended.strftime('%B %Y'), _add_months(coverage_ended, 8).strftime('%B %Y')))
        else:
            status = 'conditional'
            note = 'State the 8-month special enrollment period after job-based coverage ends and that COBRA does not extend it; ask when the job or coverage ended.'
        add('partb_sep_coverage_ended', 'partb_sep_coverage_ended', because, ['RC11'] if rc11 is None and not coverage_ended else [], note)
        rules[-1]['status'] = status
    # Missed Part B with no job-based coverage: the General Enrollment Period and penalty.
    if not in_initial_window and rc04 in {'a_only', 'neither'} and turned_65 and not working and not coverage_ended and rc09 not in {'cobra', 'retiree'} and 'cobra' not in coverage:
        add('partb_gep_penalty', 'partb_gep_penalty', ['RC04: no Part B after the reported 65th birthday month, no current job coverage'], ['RC11'] if rc11 is None else [],
            'Say that without a special enrollment period Part B is added in the General Enrollment Period (January–March, coverage the month after signing up), that fall Open Enrollment does not add Part B, and that the Part B penalty is 10% per full 12 months of delay; ask whether any job-based coverage ended recently before treating the penalty as certain.')
        rules[-1]['status'] = 'met'
    # Loss of creditable drug coverage opens its own Part D window (P20).
    if rc12 == 'yes' and (coverage_ended or rc08 == 'loss') and not has_drug_coverage:
        add('partd_sep_lost_creditable', 'partd_sep_lost_creditable', ['RC12: creditable notice reported; coverage ended'], [],
            'Say that losing creditable drug coverage opens a 2-month special enrollment period to join a drug plan now, with coverage the month after the application, and that joining within 63 days avoids the Part D penalty.')
        rules[-1]['status'] = 'met'
    # Permanent move out of a plan's service area (P19).
    if rc08 == 'move' and ('advantage' in coverage or 'drug' in coverage or rc07 == 'advantage'):
        add('move_sep', 'move_sep', ['RC08: moving'], [],
            'Say that a permanent move outside the plan service area opens a special enrollment period that does not wait for January, and how the window depends on when the plan was told; the plan notice and the exact dates decide it.')
        rules[-1]['status'] = 'met'
        if 'advantage' in coverage or rc07 == 'advantage':
            add('move_medigap_guaranteed_issue', 'move_medigap_guaranteed_issue', ['RC08: moving out of a Medicare Advantage service area'], [],
                'If the person asks about Medigap after the move, say the guaranteed-issue right covers specific plan types (A, B, D, G, K, L) within 63 days of the Advantage coverage ending—not any policy at any price.')
            rules[-1]['status'] = 'met'
    # VA health care (P15).
    if rc26 == 'va' or 'military' in coverage:
        add('va_and_medicare', 'va_and_medicare', ['RC26: VA health care' if rc26 == 'va' else 'coverage.current includes military coverage'], ['RC26'] if rc26 is None else [],
            'Say that VA coverage is not job-based coverage (no Part B protection), that VA drug coverage is creditable for Part D, and that Medicare is what pays outside the VA. Do not confirm blanket penalty protection.')
        rules[-1]['status'] = 'met' if rc26 == 'va' else 'conditional'
    # Medigap Open Enrollment Period, stated for Part A-only and disability cases (P12, P18, P20).
    if (rc04 in {'a_only', 'neither'} and turned_65) or rc06 == 'disability':
        add('medigap_open_enrollment', 'medigap_open_enrollment', ['RC06: disability Medicare approaching 65' if rc06 == 'disability' else 'RC04: Part B not yet in place at 65 or older'], [],
            'Say that the six-month Medigap window starts with Part B at 65 or older—Part A alone does not start it—and, for a disability beneficiary, that it opens again at 65.')
        rules[-1]['status'] = 'met'
    # Help paying for Medicare (P13, P14, P20).
    if rc18 in {'medicaid', 'part_b_help'}:
        add('qmb_billing_protection', 'qmb_billing_protection', ['RC18: Medicaid or help paying Part B reported'], [],
            'If the person has QMB (or Medicaid with Medicare), say that Medicare providers may not bill them for Medicare-covered deductibles, coinsurance or copays whether or not the office takes Medicaid, and that no dual plan is needed for that protection; the letter naming the program confirms which applies.')
        rules[-1]['status'] = 'met'
    if rc18 is None and cost_pressure:
        add('msp_extra_help_basics', 'msp_extra_help_basics', ['stated cost pressure with assistance status unknown'], ['RC18'],
            'Name both programs plainly—Medicare Savings Programs (state) and Extra Help (Social Security)—say that the home you live in and one car are not counted and that applying does not require a plan change; then ask whether they already receive any of them.')
        rules[-1]['status'] = 'conditional'
    # Switching away from Medicare Advantage.
    if 'advantage' in coverage or rc07 == 'advantage':
        confirm = ['RC16'] if rc16 is None else (['RC05'] if _choice(report('RC05')) is None else [])
        because = ['coverage.current includes Medicare Advantage']
        note = 'State the trial right and the 6-month Medigap period as general rules, then ask whether this was their first Advantage plan and when it started.'
        status = 'conditional'
        # Resolve the 12-month window against the person's own reported start
        # (RC16 start month) so the rule is never read as reassurance it is not
        # (Nov 9, 2026: P08 heard the general rule as a guaranteed right six
        # years after joining). Arithmetic on a reported month only; the person
        # still confirms eligibility with the Medigap insurer or Social Security.
        start = _month_start(report('RC16').get('start'))
        if rc16 == 'no':
            status = 'not_met'
            because.append('RC16: not the first Medicare Advantage plan')
            note = ('Say plainly that the 12-month trial right covers a first Medicare Advantage plan joined at 65, '
                    'which the person has reported this is not, so buying Medigap now usually means health questions '
                    'unless another protected right applies. Do not promise acceptance.')
        elif rc16 == 'yes' and start:
            window_end = _add_months(start, 12)
            if today >= window_end:
                status = 'not_met'
                because.append('RC16: first Advantage plan started %s; 12-month window ended %s' % (start.strftime('%B %Y'), window_end.strftime('%B %Y')))
                note = ('Say that on the reported start of %s the 12-month trial right would have ended around %s, so buying Medigap now '
                        'usually means health questions and possible refusal or higher prices unless another protected right applies. '
                        'Use the reported month as reported; do not state eligibility as a fact.' % (start.strftime('%B %Y'), window_end.strftime('%B %Y')))
            elif trial_at_first_eligibility is not False:
                status = 'met'
                because.append('RC16: first Advantage plan started %s; 12-month window runs to %s' % (start.strftime('%B %Y'), window_end.strftime('%B %Y')))
                note = ('Say that on the reported start of %s the 12-month trial right would run until about %s, so leaving for Original Medicare within '
                        'that time carries a guaranteed right to buy Medigap; the insurer confirms the dates. Do not state eligibility as a fact.'
                        % (start.strftime('%B %Y'), window_end.strftime('%B %Y')))
            else:
                note = ('The reported start is within the first 12 months. Give the general rule and say that '
                        'whether this was when the person first qualified at 65 still needs confirmation.')
        add('ma_trial_right', 'ma_trial_right', because, confirm, note)
        rules[-1]['status'] = status
        add('original_nationwide', 'original_nationwide', ['Medicare Advantage with care away from home' if focus in {'travel', 'doctors', 'flexibility'} else 'Medicare Advantage'], [],
            'Use when the person mentions care in another state or a doctor who would not take the plan.')

    # Formerly held Medigap, now on Advantage past the trial right (P16).
    if ('advantage' in coverage or rc07 == 'advantage') and str(report('RC16').get('priorMedigap', '')).casefold() in {'yes', 'true'}:
        add('medigap_return_underwriting', 'ma_trial_right', ['RC16: prior Medigap reported before the current Advantage plan'], [],
            'If a return to Original Medicare with Medigap comes up: say plainly that outside the 6-month Medigap period, the 12-month trial right and a guaranteed-issue event, buying Medigap again usually means health questions and possible refusal or higher prices.')
        rules[-1]['floor_text'] = ('Outside the 6-month Medigap Open Enrollment Period and the 12-month trial right, an insurer can usually '
                                   'ask health questions before selling a Medigap policy and may decline or charge more.')
    # Already holding Medigap: leaving it is easy, getting it back is not.
    if 'medigap' in coverage and 'advantage' not in coverage:
        # The fact's own summary is the trial-right sentence; as a stand-alone
        # floor for someone holding Medigap it reads as a promise of getting it
        # back (P11, Nov 9, 2026). Carry the sentence of the same reviewed text
        # that actually applies here.
        add('medigap_return_underwriting', 'ma_trial_right', ['coverage.current includes Medigap'], [],
            'If the person is weighing a move to Medicare Advantage: say plainly that outside the 6-month Medigap period and the 12-month trial right, buying Medigap again usually means health questions and possible refusal or higher prices, so keeping the current policy is a valid outcome to weigh against the premium. Name what the supplement buys: Parts A and B have no yearly cap on your share of medical costs on their own (cite medical_limit), which is the protection the premium pays for.')
        rules[-1]['floor_text'] = ('Outside the 6-month Medigap Open Enrollment Period and the 12-month trial right, an insurer can usually '
                                   'ask health questions before selling a Medigap policy and may decline or charge more.')
    # Group coverage (employer, union, retiree) and joining an individual
    # Medicare plan: the plan's own rules decide; a dependent spouse can lose
    # coverage too (pilot-rules r2, pending acceptance).
    if coverage & {'retiree', 'employer'} and (focus in {'drugs', 'plan_change', 'compare', 'total_cost', 'bills'} or 'advantage' in coverage or rc07 == 'advantage' or on_medicare):
        add('group_coverage_and_individual_plans', 'group_coverage_and_individual_plans',
            ['coverage.current includes employer/retiree coverage while a Medicare plan is in view'], [],
            'Before any separate Part D or Medicare Advantage plan is treated as the next step, say that joining one can end the group coverage (sometimes for a spouse) and may not be reversible; the benefits administrator confirms the plan\'s rules. Keeping the group coverage is a valid outcome.')
    # Creditable drug coverage already in hand: no penalty while it lasts.
    if rc12 == 'yes' or (has_drug_coverage and coverage & {'employer', 'retiree', 'cobra'} and (on_medicare or age65)):
        add('creditable_coverage_no_penalty', 'creditable_coverage_no_penalty',
            ['RC12: creditable notice reported' if rc12 == 'yes' else 'group drug coverage with Medicare in view'],
            ['RC12'] if rc12 is None else [],
            'If the notice says creditable, say plainly that no Part D penalty accrues while that coverage lasts and that a Medicare drug plan can be joined within 63 days of it ending; if the notice is not confirmed, ask for it. Do not compute a penalty.')
    # Original Medicare without drug coverage.
    if ('original' in coverage or rc07 == 'original') and not has_drug_coverage:
        add('partd_penalty', 'partd_penalty', ['Original Medicare without a drug plan'], ['RC12'] if rc12 is None else [],
            'State the penalty rule and that a stand-alone Part D plan can be added without changing to Medicare Advantage. Ask about creditable coverage; do not compute a penalty amount.')
        # The yearly Part D cap is the number people hear in ads; without a
        # drug plan it does not apply (pilot-rules r2, pending acceptance).
        add('partd_cap', 'partd_cap_2026', ['Original Medicare without a drug plan'], [],
            'If the person mentions the drug spending limit or cap, say that it applies only to people enrolled in Medicare drug coverage, so without a drug plan there is no cap; a plan joined in Open Enrollment starts January 1. Use the published 2026 figure as published.')
        rules[-1]['status'] = 'met'
    if (rc18 is None and cost_pressure) or rc18 in {'medicaid', 'extra_help', 'part_b_help', 'ssi'}:
        add('extra_help', 'extra_help', ['cost concern or assistance status'], ['RC18'] if rc18 is None else [],
            'Say that Extra Help exists and what it does, then ask whether they already get help with Medicare costs.')

    # Medicare Advantage needs both parts. Someone with Part A only (or neither)
    # who is looking at Advantage plans must hear that before comparing them
    # (R6, Nov 9, 2026; statement in pilot-rules r2, pending acceptance).
    if rc04 in {'a_only', 'neither'} and (plans_view or focus in {'compare', 'plans', 'advantage'}
            or re.search(r'(?i)\badvantage\b|\bplans?\b', concern or '')):
        add('ma_requires_a_and_b', 'ma_requires_a_and_b', ['RC04: %s' % ('Part A only' if rc04 == 'a_only' else 'neither part yet')], [],
            'Say plainly that joining a Medicare Advantage plan requires both Part A and Part B, so Part B comes first; '
            'comparing plans now is fine for learning, and Social Security handles the Part B sign-up.')
        rules[-1]['status'] = 'met'

    # Timing of changes for people already on Medicare.
    if on_medicare and ((today.month == 10 and today.day >= 15) or today.month == 11 or (today.month == 12 and today.day <= 7)):
        add('annual_enrollment', 'annual_enrollment', ['already on Medicare during Open Enrollment'], [],
            'Say that Open Enrollment is open now and when changes start; do not give a personal deadline beyond the published dates.')
    for rule in rules:
        rule['confirm_with'] = [item for item in rule['confirm_with'] if item]
        # 'met': the reports satisfy the rule's condition; 'conditional': a
        # confirm question still decides it; 'not_met': the reports show the
        # protection does not apply (the statement is then a caution, never a
        # floor). Timing rules are 'met' but informational.
        rule.setdefault('status', 'conditional' if rule['confirm_with'] else 'met')
    return rules


def floor_statement(rules, required_reason=None):
    """The one rule whose summary may stand alone when composition fails.

    The rule being confirmed by the required question comes first; then a met,
    non-calendar rule; never a rule the reports show does not apply (P08, Nov 9
    2026: the general trial-right sentence read as a guaranteed right).
    """
    if required_reason and str(required_reason).startswith('rule:'):
        wanted = str(required_reason)[5:]
        for rule in rules:
            if rule['rule_id'] == wanted and rule.get('status') != 'not_met':
                return rule
    for rule in rules:
        if rule.get('status') == 'met' and rule['rule_id'] != 'annual_enrollment':
            return rule
    for rule in rules:
        if rule.get('status') == 'conditional':
            return rule
    return None


def required_target(moves, ranked, *, pending_id=None, dispositions=None, rules=()):
    """The one approved question the composed reply must ask, or None.

    Order: an actual required clarification; the question already pending; a
    question a selected rule needs confirmed; then the first unanswered
    candidate relevant to the current decision. Deferred and explicitly
    unknown answers stay open and are never re-asked here.
    """
    dispositions = dispositions or {}
    by_id = {item['id']: item for item in moves}
    def open_(identifier):
        return identifier in by_id and dispositions.get(identifier) not in {'deferred', 'unknown', 'explicit_unknown'}
    required = next((item for item in moves if item.get('required')), None)
    if required:
        return required['id'], 'clarification'
    if pending_id and open_(pending_id):
        return pending_id, 'pending'
    for rule in rules:
        for identifier in rule.get('confirm_with', []):
            if open_(identifier):
                return identifier, 'rule:' + rule['rule_id']
    for item in ranked:
        identifier = item['question']['id']
        if item.get('decision_relevance') == 'current_decision' and open_(identifier):
            return identifier, 'current_decision'
    return None, None
