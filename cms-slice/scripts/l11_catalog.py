"""Authored L11 research normalization; source text remains authoritative.

These are published reference records, not a personal eligibility engine.
All source selectors are resolved against retained, hashed evidence by l11_build.
"""

PRE = ['A', 'B', 'C', 'F', 'F_HIGH', 'K', 'L']
NEW = ['A', 'B', 'D', 'G', 'G_HIGH', 'K', 'L']


def F(path):
    return 'FAC:69O-156.' + path + (':' if ':' not in path else '')


def U(path):
    return 'USC:' + path


def S(section, first, last=None):
    return f'FS:{section}:L{first}' + (f'-{last}' if last else '')


# Q records are exact structured quantities, with a literal source witness.
# Complex clocks and inter-source differences are represented separately below.
def Q(name, value, unit, witness):
    return {'name': name, 'value': value, 'unit': unit, 'witness': witness}


def R(ident, title, family, refs, meaning, quantities=(), holds=()):
    return {'id': ident, 'title': title, 'family': family, 'source_selectors': refs,
            'meaning': meaning, 'quantities': list(quantities), 'hold_ids': list(holds)}


RULES = [
 R('R01','Federal initial Medigap open enrollment','RF02',[U('s-2-A'),U('s-2-B'),U('s-2-C'),U('s-2-D')],
   'Application before or during the protected six-month period anchored to the first month, as of its first day, age 65 or older and enrolled in Part B. Protection against health-based denial/conditioning/pricing is separate from permissible preexisting-condition limits.',
   [Q('open_enrollment_months',6,'months','6 month period'),Q('age_threshold',65,'years','65 years of age')]),
 R('R02','Florida initial opportunities including disability and ESRD','RF03',[S('627.6741',153,156),F('009:1'),'FAQ:3'],
   'Florida resident with Part B: the statute includes qualifying under-65 disability/ESRD as well as age 65 or older. Keep the statute first-month wording, federal age-65 rule, older state rule and FAQ date-of-enrollment summary distinct. Under-65 eligibility does not establish an individual premium.',
   [Q('statutory_window_months',6,'months','6-month period'),Q('age_threshold',65,'years','65 years of age')],['G02','G03']),
 R('R03','Florida opportunity after group health policy termination','RF04',[S('627.6741',153,155),S('627.6741',162), 'FAQ:3'],
   'Florida resident, Part B enrolled, age 65+ or qualifying disability/ESRD: a separate two-month opportunity following termination of coverage under a group health insurance policy. Do not impose the federal employee-welfare supplemental-benefit test on this statutory text or replace months with 63 days.',
   [Q('statutory_window_months',2,'months','2-month period')],['G01']),
 R('R04','Initial enrollment preexisting-condition protection and credit','RF10',[U('s-2-B'),U('s-2-C'),U('s-2-D'),F('009:2'),F('009:3'),S('627.6741',162,167)],
   'Initial enrollment protection does not by itself eliminate every preexisting exclusion. Preserve the six-month maximum/lookback and the qualifying six-month continuous-credit protection, lesser-credit reduction and replacement rules.',
   [Q('maximum_exclusion_months',6,'months','6 months'),Q('lookback_months',6,'months','6 months')],['G04']),
 R('R05','Replacement credit for similar benefits','RF10',[U('s-1'),U('s-2-C'),F('019:1'),F('019:2'),S('627.6741',167)],
   'Waive preexisting/waiting/elimination/probationary time to the extent already served. Similar benefits and the six-month prior-policy condition remain explicit. Florida statute also names replacement of creditable coverage; do not treat extra benefits as automatically credited.',
   [Q('prior_policy_full_credit_months',6,'months','six (6) months')]),
 R('R06','Federal employer supplemental-benefit loss','RF04',[U('s-3-A'),U('s-3-B-i'),U('s-3-E-i'),'ERISA:1'],
   'Federal employee welfare plan supplies benefits supplementing Medicare and terminates or ceases all those supplemental benefits. Notice/claim-denial evidence and the federal notice-based clock are separate from the Florida rules.'),
 R('R07','Florida employer supplemental-benefit loss','RF04',[F('0095:1'),F('0095:2.a'),F('0095:3.a'),F('0095:5.a'),'ERISA:1','ERISA1999:1'],
   'Florida employee-welfare trigger includes termination or cessation of at least Plan A minimum supplemental benefits. Its clock begins at the later of the applicable notice/claim denial and coverage end, followed by 63 days. Preserve this additional state wording.',
   [Q('application_days',63,'days','sixty-three (63) days')]),
 R('R08','MA contract termination or area discontinuation','RF05',[U('s-3-A'),U('s-3-B-ii'), 'MA:e-4-A',F('0095:2.b.1'),F('0095:2.b.2'),F('0095:3.b'),F('0095:3.d'),'CMSFAQ:4','CMSFAQ:5'],
   'Actual contract/plan nonrenewal or area discontinuation can support a right when returning to Original Medicare. An actual nonrenewal crosswalk remains distinct from an ordinary voluntary annual plan change. Election and Medigap application windows remain distinct.'),
 R('R09','MA move and other qualifying loss of eligibility','RF05',[U('s-3-B-ii'),'MA:e-4-B',F('0095:2.b.3')],
   'Qualifying residence or Secretary-specified circumstance changes are different from disenrollment for unpaid premiums or disruptive behavior; those exclusions are retained.'),
 R('R10','MA material breach or marketing misrepresentation','RF07',[U('s-3-B-ii'),'MA:e-4-C',F('0095:2.b.4'),'CMSFAQ:5','CMSFAQ:6'],
   'The event must be demonstrated through the applicable CMS process; an allegation alone does not establish a protection. Preserve materially violated provision, timely necessary care/quality and material marketing misrepresentation as alternative qualifying grounds.'),
 R('R11','CMS exceptional circumstances and significant network changes','RF08',[U('s-3-B-ii'),'MA:e-4-D',F('0095:2.b.5'),'CFRJAN:b.23','CFRJAN:b.27','CMSFAQ:1','CMSFAQ:4','CMSFAQ:8','CMSFAQ:9'],
   'CMS-determined significant network change and affected-enrollee requirements differ from an ordinary provider exit. Case-specific exceptional-circumstance determinations may also support protection. Preserve determination, qualifying SEP, actual disenrollment and notice evidence.',
   [Q('network_sep_additional_calendar_months',2,'calendar_months','2 calendar months'),Q('provider_prior_care_months',3,'months','past 3 months')]),
 R('R12','PACE counterparts to applicable coverage-loss rights','RF05',[U('s-3-B-ii'),F('0095:2.b'),F('0095:2.f')],
   'For the statutory coverage-loss counterpart, retain the age-65-or-older and analogous-circumstance predicates. The first-Part-A-at-65 trial provision is a separate path.',
   [Q('coverage_loss_age_threshold',65,'years','65 years of age')]),
 R('R13','Cost, HCPP and SELECT coverage-loss counterparts','RF05',[U('s-3-B-iii'),F('0095:2.c'),'CMSFAQ:10'],
   'Retain Cost/HCPP and historical demonstration distinctions and analogous loss circumstances. Federal SELECT wording includes no state continuation/conversion provision; Florida separately supplies SELECT conversion opportunities. Do not remove that difference.',holds=['G05']),
 R('R14','Medigap insolvency or other involuntary loss','RF07',[U('s-3-B-iv'),F('0095:2.d'),F('0095:3.c')],
   'Bankruptcy/insolvency or other involuntary loss is distinct from voluntary cancellation and renewal exceptions. Federal involuntary-loss wording retains the lack of a state continuation/conversion provision; state wording must remain visible.',holds=['G05']),
 R('R15','Medigap material breach or misleading marketing','RF07',[U('s-3-B-iv'),F('0095:2.d'),F('0095:3.d')],
   'Material policy breach or material misrepresentation by issuer/agent is a distinct protected-event branch. Preserve evidence and the event-specific voluntary-disenrollment clock.'),
 R('R16','Return after first departure from Medigap','RF06',[U('s-3-B-v'),U('s-3-C-ii'),F('0095:2.e'),F('0095:5.b'),'CFRJAN:b.8'],
   'Actual prior Medigap terminated to enter a qualifying MA/Cost/PACE/SELECT arrangement for the first time, with timely exit. First-ever entry and actual prior-policy transition are required; annual renewal or carrier switch is not a fresh trial.',
   [Q('trial_months',12,'months','twelve (12) months')]),
 R('R17','Trial when first eligible for Part A at age 65','RF06',[U('s-3-B-vi'),U('s-3-C-iii'),F('0095:2.f'),F('0095:5.c'),'CFRJAN:c'],
   'First eligibility for Part A at age 65, entry into MA or PACE and exit within the specified first year. This path does not require an earlier Medigap policy, and its policy-choice rule differs from the return-to-former-policy path.',
   [Q('trial_months',12,'months','twelve (12) months'),Q('age_at_first_part_a',65,'years','age 65')]),
 R('R18','Interrupted trial extensions','RF06',[U('s-3-F'),F('0095:4')],
   'An involuntary termination during the first twelve months followed without intervening enrollment by another qualifying arrangement can be treated as an initial enrollment. Retain the two-year outer limit from the first enrollment; no automatic extra year for every switch.',
   [Q('outer_trial_years',2,'years','2-year period'),Q('initial_trial_months',12,'months','12 months')]),
 R('R19','Florida event-based guaranteed-issue policy choices','RF09',[U('s-3-C'),F('0095:5.a'),F('0095:5.b'),F('0095:5.c'),F('0095:5.d'),U('z'),'FAQ:4','FAQ:5','CMSFAQ:7'],
   'For ordinary listed Florida event protections use the state A/B/C/F/high-F/K/L list, subject to the federal C-to-D and F-to-G transition for newly eligible beneficiaries. Prior-policy return and first-Part-A-at-65 any-policy protections are separate. Availability from the actual issuer remains required.'),
 R('R20','Newly eligible Medicare boundary','RF09',[U('z-1'),U('z-2'),U('z-4'),F('003:14'),F('0086:1'),F('0086:4')],
   'Use the federal definition: newly eligible excludes someone who attained 65 before 2020 OR had the specified Part A entitlement/deemed eligibility before 2020. Age now or current Part B enrollment alone cannot decide this. The state definition summary uses different connective wording and is retained for review.',holds=['G03']),
 R('R21','Guaranteed-issue protections and evidence','RF14',[U('s-3-A'),F('0095:1'),F('0095:6')],
   'Available qualifying policy, eligible event, timely application and evidence of termination/disenrollment or applicable Part D enrollment. No health-based issuance conditioning/pricing or preexisting exclusion under the protected policy. No promise that all applicants pay identical rates.'),
 R('R22','Federal employer notice clock','RF14',[U('s-3-E-i')],
   'The cited federal text begins with applicable termination/cessation notice, or qualifying claim-denial notice if none, and ends 63 days after that applicable notice. Preserve the separate state later-of protection.',
   [Q('application_days',63,'days','63 days')]),
 R('R23','Florida employer later-of clock','RF14',[F('0095:3.a')],
   'Begin at later of notice/qualifying claim-denial notice and coverage termination/cessation; end 63 days thereafter.',
   [Q('application_days',63,'days','sixty-three (63) days')]),
 R('R24','Involuntary plan termination clock','RF14',[U('s-3-E-ii'),F('0095:3.b')],
   'For the specified involuntary MA/analogous/trial branches, begin at receipt of termination notice and end 63 days after coverage terminates.',
   [Q('after_termination_days',63,'days','63 days')]),
 R('R25','Insolvency and involuntary Medigap loss clock','RF14',[U('s-3-E-iii'),F('0095:3.c')],
   'Begin at the earlier of an applicable notice, if any, and coverage termination; end 63 days after termination.',
   [Q('after_termination_days',63,'days','63 days')]),
 R('R26','Qualifying voluntary disenrollment clock','RF14',[U('s-3-E-iv'),F('0095:3.d')],
   'For the listed qualifying voluntary-discontinuance branches, apply from 60 days before effective disenrollment through 63 days after; this is not a general right to voluntary switching.',
   [Q('before_disenrollment_days',60,'days','60 days'),Q('after_disenrollment_days',63,'days','63 days')]),
 R('R27','Residual eligible-event clock','RF14',[U('s-3-E-v'),F('0095:3.f')],
   'Only for an otherwise eligible event not covered by a more specific clock: effective disenrollment through 63 days after.',
   [Q('after_disenrollment_days',63,'days','63 days')]),
 R('R28','Rights notices and proof','RF14',[U('s-3-D'),F('0095:1.a'),F('0095:6')],
   'Retain source event notice duties, contemporaneous termination notices and state ten-working-day disenrollment notification duty. A notice deadline for the issuer is not the beneficiary application deadline.',
   [Q('issuer_disenrollment_notice_working_days',10,'working_days','ten working days')]),
 R('R29','Guaranteed renewability and cancellation limits','RF11',[U('q-1'),S('627.6741',164,166),F('0075:1.e')],
   'Health deterioration alone cannot justify cancellation/nonrenewal; nonpayment and material misrepresentation remain exceptions. Renewal is not a guarantee of unchanged premiums.'),
 R('R30','Group conversion and continuation','RF11',[U('q-2'),U('q-3'),S('627.6741',169,179),F('0075:1.e.3'),F('0075:1.e.4')],
   'Group policy termination without replacement triggers individual conversion choices. Ending group membership brings conversion or, at group-policyholder option, continuation; preserve the option holder and conditions.'),
 R('R31','Group policy replacement safeguards','RF11',[U('q-4'),S('627.6741',180),F('0075:1.e.5')],
   'Coverage offered to all persons covered on the old group policy termination date and no new exclusion for previously covered preexisting conditions. State issue-age/duration retention adds a reserves-transfer condition for a group replacement.'),
 R('R32','Medicaid-related suspension and reinstatement','RF12',[U('q-5-A'),U('n-6-A-ii'),F('0075:1.g.1'),F('0075:1.g.2')],
   'Requested suspension when applied for and determined entitled to Medicaid, limited to 24 months, with timely entitlement notice. Reinstitution effective at loss of entitlement requires timely loss notice; preserve state premium/refund/paid-claim qualifications.',
   [Q('maximum_suspension_months',24,'months','24 months'),Q('notice_days',90,'days','90 days')]),
 R('R33','Disability and employer-group suspension','RF12',[U('q-6'),U('n-6-A-ii'),F('0075:1.g.3'),'MEX:b-1-A-v','TAX:b-1'],
   'The specified disability entitlement plus group health coverage supports requested suspension. Loss-of-group-coverage notice within 90 days supports reinstitution effective at loss, subject to state premium conditions. Do not transplant Medicaid 24-month cap here.',
   [Q('loss_notice_days',90,'days','90 days')]),
 R('R34','Terms of reinstated coverage','RF12',[U('n-6-A-ii'),U('q-5-A'),U('q-6'),F('0075:1.g.4')],
   'No new preexisting waiting period, substantially equivalent prior coverage and premium classification no less favorable than if coverage had not terminated, under the applicable suspension/reinstitution path.'),
 R('R35','Florida free-look return','RF11',[S('627.674',185),F('014:1.e'),'FAQ:4','BLUE:3','BLUESELECT:3'],
   'Return within 30 days of receiving/delivery of the policy or certificate, with premium refund. The clock is delivery/receipt, not application, signature or coverage start. Replacement and cancellation safeguards remain distinct.',
   [Q('free_look_days',30,'days','30 days')]),
 R('R36','SELECT to non-network policy with the same issuer','RF11',[F('030:12'),F('030:13')],
   'At request, after SELECT in force six months, issuer makes a comparable-or-lesser non-restricted policy it offers available without evidence of insurability. Preserve the significant-benefit definition, same-issuer limitation and actual offered policies.',
   [Q('select_in_force_months',6,'months','six (6) months')]),
 R('R37','SELECT program discontinuance protection','RF11',[F('030:14')],
   'If the specified HHS determination about program discontinuance/reauthorization/substantial amendment occurs, preserve continuation and same-issuer comparable-or-lesser unrestricted policy opportunity without insurability evidence. Not every personal network change triggers this provision.'),
 R('R38','Legacy drug-bearing Medigap continuity','RF01',[U('v-1'),U('v-2'),F('005:4')],
   'Existing pre-2006 drug-bearing Medigap can be continued in the specified circumstances. Part D enrollment requires removal of duplicate outpatient drug coverage and adjusted premium. These legacy rights are not a new 2026 drug-bearing product offering.'),
 R('R39','Historical initial Part D substitution protection','RF09',[U('v-3'),U('v-6'),F('0095:2.g'),F('0095:3.e'),F('0095:5.d')],
   'Retain the special legacy Medigap-Rx/initial-Part-D enrollment provisions and same-issuer policy choices as historical context. The referenced initial Part D period is not every annual election period.',holds=['G06']),
 R('R40','Genetic-information protections and limits','RF13',[U('s-2-E'),U('s-2-F'),U('x'),F('020')],
   'Retain bans on genetic testing/information use for underwriting and their statutory definitions/exceptions. These do not create universal issue rights outside protected events; manifested disease and permissible age/sex distinctions are not silently erased.'),
 R('R41','Duplicate or incompatible policy sale safeguards','RF01',[U('d'),F('015'),F('017'),'GUIDE:28','FAQ:3'],
   'Preserve replacement-intent, existing Medigap and MA/Medicaid restrictions and statutory exceptions. Keeping an old policy is distinct from a new incompatible sale. General reference is not authority to cancel an existing policy.'),
 R('R42','Purchasing outside a demonstrated protection','RF13',['GUIDE:15','GUIDE:27','FAQ:3'],
   'A carrier may consider underwriting outside a protected opportunity. Missing or inconclusive history is unresolved, not a verified denial. Extra carrier acceptance programs require exact dated evidence before being claimed.',holds=['G07']),
 R('R43','Same-issuer issue-age replacement protection','RF11',[F('0075:1.e.6')],
   'For the specified same-issuer replacement of an existing issue-age-rated policy/certificate, retain original issue age and policy duration. This is not a binding premium quote or an all-insurer transfer right.'),
 R('R44','Premium-change notice and cancellation refund','RF11',[F('014:1.f'),S('627.6741',181,182)],
   'Preserve state 45-day advance rate-change notice and statutory unearned-premium refund/earned-premium calculation distinctions; termination does not erase pretermination claims.',
   [Q('advance_rate_notice_days',45,'days','45 days')]),
 R('R45','Creditable coverage definitions and exclusions','RF10',[F('003'),S('627.6562',155,212),S('627.6561',152,179)],
   'Retain the specifically incorporated creditable-coverage definition, its included coverage types, excepted benefits and separate supplemental-policy exclusion. Do not transplant group-insurance exclusion periods or dependent-age eligibility into Medigap. The state rule continuity definition uses breaks greater than 63 days; the stale cross-reference is held explicitly.',holds=['G04']),
 R('R46','Policy terms and preexisting-condition definitions','RF01',[F('004'),F('005'),U('g-1')],
   'Retain permissible policy definitions, preexisting-condition lookback and legacy prescription-policy rules. Policy terms cannot silently narrow the protections in the governing provisions.'),
 R('R47','Policy cohorts and continuity qualifications','RF11',[F('006:1'),F('007:1'),F('0075:1')],
   'Retain the general renewal, group conversion, replacement, issue-age/duration, continuous-loss and suspension qualifications for each policy cohort. Cohort dates remain explicit; a modern-policy shortcut does not erase existing-policy rights.'),
 R('R48','Required disclosure and replacement notices','RF14',[F('014'),F('015'),F('017'),S('627.674',153,198)],
   'Retain renewal, rider acceptance, premium notice, guide/outline delivery, replacement and nonduplication safeguards and their exceptions. Regulatory issuer duties are not extra consumer eligibility predicates or authorization for a Daylight sales workflow.'),
 R('R49','SELECT disclosure and initial unrestricted-policy alternatives','RF01',[U('t-1-E'),U('t-1-F'),F('030:9'),F('030:10'),F('030:12')],
   'Retain written network/out-of-area/emergency disclosure, acknowledgment and the unrestricted policies otherwise offered by the same issuer. This is separate from evidence of actual provider participation or a universal product-sale promise.'),
 R('R50','Minimum offering structure and 2020 policy availability','RF09',[F('0086:root'),F('0086:1'),F('0086:2'),F('0086:3'),F('0086:4')],
   'Retain prohibition of Part B deductible coverage for newly eligible beneficiaries and the core-policy/additional-benefit offering structure. An offering standard does not prove an exact insurer/form is currently on sale in Collier; preserve the L10 dependency.'),
 R('R51','Complete referenced MA special-election paragraph inventory','RF08',['CFRJAN:b', 'MA:e-4', 'CMSFAQ:4','CMSFAQ:7','CMSFAQ:8'],
   'Retain every published special-election paragraph in the referenced regulation. Not every enrollment opportunity is itself a proven Medigap purchase protection. The crosswalk records exact source text and distinguishes demonstrated event routes, historical provisions and cases needing specific authority/determination.',holds=['G09'])
]

# Illustrative source-linked predicate patterns for synthetic validation only.
# Full verbatim source conditions remain attached to each right. These patterns
# are deliberately not presented as an exhaustive executable legal model.
PREDICATES = [
 {'id':'P01','rule':'R20','expression':{'not':{'any':['turned_65_before_2020','qualified_part_a_before_2020']}},'source_selectors':[U('z-2')]},
 {'id':'P02','rule':'R01','expression':{'all':['age65_on_first_of_month','part_b_enrolled','application_in_federal_initial_window']},'source_selectors':[U('s-2-A')]},
 {'id':'P03','rule':'R02','expression':{'all':['florida_resident','part_b_enrolled',{'any':['age65_or_older',{'all':['under65',{'any':['disability_eligible','esrd_eligible']}]}]},'application_in_florida_initial_window']},'source_selectors':[S('627.6741',153,154)]},
 {'id':'P04','rule':'R03','expression':{'all':['florida_resident','part_b_enrolled',{'any':['age65_or_older',{'all':['under65',{'any':['disability_eligible','esrd_eligible']}]}]},'group_policy_coverage_terminated','application_in_florida_group_window']},'source_selectors':[S('627.6741',153,155)]},
 {'id':'P05','rule':'R16','expression':{'all':['prior_medigap_terminated_to_join','first_qualifying_program_entry','qualifying_program_type','exit_within_trial','permitted_exit']},'source_selectors':[U('s-3-B-v')]},
 {'id':'P06','rule':'R17','expression':{'all':['first_part_a_eligibility_at65','entered_ma_or_pace_then','exit_within_trial']},'source_selectors':[U('s-3-B-vi')]},
 {'id':'P07','rule':'R18','expression':{'all':['qualifying_underlying_trial','involuntary_termination_within_first12','next_qualifying_enrollment_without_intervening','within_outer_two_year_limit']},'source_selectors':[U('s-3-F')]},
 {'id':'P08','rule':'R11','expression':{'all':['cms_significant_network_determination',{'any':['assigned_to_terminated_provider','currently_receiving_care','received_care_in_past3months']},'uses_qualifying_sep_to_disenroll','returns_to_original_medicare']},'source_selectors':['CFRJAN:b.23',U('s-3-B-ii'),'CMSFAQ:8']},
 {'id':'P09','rule':'R21','expression':{'all':['eligible_event','application_within_applicable_window','required_event_evidence','policy_available_for_new_issue']},'source_selectors':[U('s-3-A'),F('0095:1')]},
 {'id':'P10','rule':'R36','expression':{'all':['existing_select_policy','same_issuer','requested_conversion','policy_offered_comparable_or_lesser','select_in_force_at_least6months']},'source_selectors':[F('030:13')]},
 {'id':'P11','rule':'R32','expression':{'all':['requested_suspension','applied_and_determined_medicaid_entitled','entitlement_notice_within90days','suspension_not_beyond24months']},'source_selectors':[U('q-5-A')]},
 {'id':'P12','rule':'R33','expression':{'all':['requested_suspension','specified_disability_entitlement','qualified_group_health_plan_coverage']},'source_selectors':[U('q-6')]},
 {'id':'P13','rule':'R34','expression':{'all':['applicable_prior_suspension','qualifying_coverage_or_entitlement_loss','loss_notice_within90days','required_premium_paid']},'source_selectors':[F('0075:1.g.2'),F('0075:1.g.3'),F('0075:1.g.4')]},
 {'id':'P14','rule':'R05','expression':{'all':['replacement_policy','similar_benefits','prior_policy_in_force_at_least6months']},'source_selectors':[U('s-2-C'),F('019:2')]}
]

CLOCKS = [
 {'id':'C01','rule':'R01','start':'first_month_age65_and_part_b_first_day','end':'start_plus_6_calendar_months_exclusive','unit':'months','amount':6,'personal_calculation_enabled':False},
 {'id':'C02','rule':'R02','start':'first_qualifying_month_under_florida_statute','end':'six_month_period_source_wording','unit':'months','amount':6,'personal_calculation_enabled':False,'hold_ids':['G02']},
 {'id':'C03','rule':'R03','start':'following_group_policy_termination','end':'two_month_period_source_wording','unit':'months','amount':2,'personal_calculation_enabled':False,'hold_ids':['G01']},
 {'id':'C04','rule':'R22','start':'applicable_notice_or_claim_denial_notice','end':'notice_plus_63_days','unit':'days','amount':63,'personal_calculation_enabled':False},
 {'id':'C05','rule':'R23','start':'later_of_notice_or_claim_denial_and_coverage_end','end':'start_plus_63_days','unit':'days','amount':63,'personal_calculation_enabled':False},
 {'id':'C06','rule':'R24','start':'termination_notice_received','end':'coverage_end_plus_63_days','unit':'days','amount':63,'personal_calculation_enabled':False},
 {'id':'C07','rule':'R25','start':'earlier_of_applicable_notice_if_any_and_coverage_end','end':'coverage_end_plus_63_days','unit':'days','amount':63,'personal_calculation_enabled':False},
 {'id':'C08','rule':'R26','start':'disenrollment_minus_60_days','end':'disenrollment_plus_63_days','unit':'days','amount':63,'before_days':60,'personal_calculation_enabled':False},
 {'id':'C09','rule':'R27','start':'effective_disenrollment','end':'disenrollment_plus_63_days','unit':'days','amount':63,'personal_calculation_enabled':False},
 {'id':'C10','rule':'R35','start':'policy_delivery_or_receipt','end':'receipt_plus_30_days','unit':'days','amount':30,'personal_calculation_enabled':False},
 {'id':'C11','rule':'R28','start':'issuer_receives_disenrollment_notice','end':'ten_working_days_for_issuer_notice','unit':'working_days','amount':10,'personal_calculation_enabled':False},
 {'id':'C12','rule':'R32','start':'medicaid_entitlement_or_loss_as_applicable','end':'respective_event_plus_90_days_for_notice','unit':'days','amount':90,'personal_calculation_enabled':False},
 {'id':'C13','rule':'R33','start':'group_coverage_loss','end':'loss_plus_90_days_for_notice','unit':'days','amount':90,'personal_calculation_enabled':False},
 {'id':'C14','rule':'R44','start':'planned_rate_change','end':'at_least_45_days_advance_notice','unit':'days','amount':45,'personal_calculation_enabled':False}
]

GAPS = [
 {'id':'G01','kind':'precise_deadline_interpretation','title':'Florida two-month group-termination boundary','meaning':'The statute gives a two-month period following termination. Exact opening/last-day convention for mid-month/month-end events is not specified in the retained clause. Preserve months and refer for a personal deadline; do not convert it to 60 or 63 days.','closure':'Florida-qualified interpretation with exact authority or official clarification, plus boundary cases.','additional_bulk_data_needed':False},
 {'id':'G02','kind':'nonstandard_enrollment_anchor','title':'Retroactive or nonstandard Part B/under-65 timing','meaning':'Statute first-month wording and FAQ date-of-enrollment wording differ in precision. Ordinary published rule is retained; a backdated notice, delayed determination or uncertain effective date requires exact administrative evidence and qualified application.','closure':'Dated official administrative guidance for any claimed exception and qualified interpretation; actual notices only for a later individual case.','additional_bulk_data_needed':False},
 {'id':'G03','kind':'definition_summary_difference','title':'State newly-eligible summary versus federal exclusion definition','meaning':'State rule .003(14) uses anyone who attains 65 on/after 2020 OR first becomes eligible on/after 2020. Federal law excludes prior qualifying Part A eligibility even if age 65 occurs later. Retain controlling federal wording and flag the state summary instead of denying C/F to prior-disability beneficiaries.','closure':'Qualified confirmation of the combined federal/state treatment. Exact federal definition and state wording are already retained.','additional_bulk_data_needed':False},
 {'id':'G04','kind':'stale_definition_cross_reference','title':'Creditable-coverage cross-reference and break boundary','meaning':'FAC .003(6) points to 627.6561(5), which is absent in the retained 2026 section. Current 627.6741 expressly imports 627.6562(3). Preserve definitions/exclusions, similar-benefit credit and the state greater-than-63-day break wording; do not silently substitute a Part D creditability rule.','closure':'Qualified reconciliation of the stale rule cross-reference and applicable continuity/credit calculation, with actual prior-coverage facts only for later cases.','additional_bulk_data_needed':False},
 {'id':'G05','kind':'state_federal_interaction','title':'Continuation/conversion and specific protected-event interactions','meaning':'Federal SELECT/involuntary-loss branches contain no-state-continuation/conversion qualifications that state summaries do not repeat. Florida separately provides conversion rights. Both are retained; exact available route must not be collapsed into a universal all-carrier purchase right.','closure':'Florida-qualified branch review using retained clauses and any exact product conversion terms needed for an actual claim.','additional_bulk_data_needed':False},
 {'id':'G06','kind':'historical_scope','title':'Legacy initial-Part-D substitution','meaning':'The original initial Part D enrollment provisions are retained as historical context. No new annual or generic 2026 initial-Part-D right is inferred from them.','closure':'Qualified confirmation before applying any legacy substitution to an actual represented case.','additional_bulk_data_needed':False},
 {'id':'G07','kind':'conditional_carrier_evidence','title':'Optional extra carrier acceptance and actual former-policy availability','meaning':'No complete verified all-carrier voluntary acceptance/underwriting program inventory. It is needed only to claim a specific extra opportunity or actual policy return availability; statutory rights remain represented.','closure':'Exact Florida carrier/form/program/date conditions for a claimed opportunity; otherwise keep unknown.','additional_bulk_data_needed':True,'required_for_statutory_reference':False},
 {'id':'G08','kind':'independent_qualified_review','title':'Exact R16 review and acceptance','meaning':'AI source normalization, comparisons and synthetic checks are not independent Florida Medicare review or owner acceptance. No personal applicability or consumer release is enabled.','closure':'Qualified reviewer identity/role, decisions on named material interpretations and exact source/model/code fingerprints, followed by applicable exact-release acceptance.','additional_bulk_data_needed':False},
 {'id':'G09','kind':'exceptional_sep_classification','title':'Exact Medigap treatment of other MA special-election cases','meaning':'The complete referenced MA special-election text is retained and inventoried. Cases beyond the expressly compared termination/move/breach/trial/network routes need exact statutory-authority or CMS-determination review; neither all SEPs nor no other SEPs are assumed to give Medigap rights.','closure':'Source-linked case classification for each represented exceptional SEP, or a specific CMS determination for an actual case, approved in R16.','additional_bulk_data_needed':False}
]
