"""Build the additive, review-only social-insurance index from retained sources.

No network or runtime writes. Existing facts/source records are copied exactly.
New facts require exact acceptance; this script does not create it.
"""
import copy
import hashlib
import json
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
PREVIOUS = ROOT.with_name('pilot-knowledge-2026-11-12-r1')
if (ROOT / 'manifest.sha256.json').exists():
    raise SystemExit('Sealed review revision; make a new revision instead of overwriting it.')
sys.path.insert(0, str(ROOT.parents[2] / 'alternatives/advisor-first'))
from pilot_knowledge import approval_digest


def write(name, value):
    (ROOT / name).write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


catalog = json.loads((PREVIOUS / 'catalog.json').read_text())
catalog['revision'] = ROOT.name
catalog['supersedes'] = PREVIOUS.name
catalog['extension_state'] = 'indexed_candidates_not_accepted_or_active'
old_ids = {f['id'] for f in catalog['facts']}
for folder in ('addendum', 'law-addendum', 'plan-addendum'):
    for source in json.loads((ROOT / folder / 'sources.json').read_text()):
        for field in ('raw_path', 'text_path'):
            if field in source:
                source[field] = folder + '/' + source[field]
        catalog['sources'].append(source)
sources = {s['id']: s for s in catalog['sources']}

# The first-day birthday explanation is a help drawer in the already retained
# HTML, absent from r1's body-only text. Preserve r1; derive a distinct source.
class BirthdayDrawer(HTMLParser):
    content = None
    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if values.get('data-drawer-id') == '55831':
            self.content = unescape(values['data-content'])

class PlainText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
    def handle_data(self, data):
        self.parts.append(data)

drawer = BirthdayDrawer()
drawer.feed((ROOT / sources['start']['raw_path']).read_text())
assert drawer.content
plain = PlainText(); plain.feed(drawer.content)
drawer_text = ' '.join(' '.join(plain.parts).split()) + '\n'
(ROOT / 'derived').mkdir(exist_ok=True)
(ROOT / 'derived/first-day-birthday.txt').write_text(drawer_text)
source = copy.deepcopy(sources['start'])
source.update(id='start-birthday-drawer', title='First-of-month birthday: Medicare enrollment help drawer',
    text_path='derived/first-day-birthday.txt', text_sha256=hashlib.sha256(drawer_text.encode()).hexdigest(),
    extraction='HTML data-content for data-drawer-id 55831, HTML entity decode and text extraction; retained r1 bytes, no new request',
    parent_source_id='start')
catalog['sources'].append(source); sources[source['id']] = source


def span(sid, start, end):
    source = sources[sid]
    assert source['status'] == 'captured', sid
    text = (ROOT / source['text_path']).read_text()
    try:
        a = text.index(start)
        b = text.index(end, a) + len(end)
    except ValueError:
        raise ValueError(f'Missing passage boundary in {sid}: {start!r} through {end!r}') from None
    quote = text[a:b]
    return {'source_id': sid, 'start': a, 'end': b, 'quote': quote,
            'sha256': hashlib.sha256(quote.encode()).hexdigest()}


def add(identifier, topic, title, aliases, text, conditions, support):
    catalog['facts'].append(dict(id=identifier, topic=topic, title=title,
        aliases=aliases, text=text, conditions=conditions, jurisdiction='US',
        coverage_years=[2026], review_by='2026-12-31', review_state='candidate',
        holds=[], support=support,
        source_ids=list(dict.fromkeys(p['source_id'] for p in support))))


add('pk_part_a_benefits', 'coverage', 'What Part A covers',
    ['what does part a cover', 'hospital insurance', 'hospice', 'part a benefits'],
    'Part A is hospital insurance. It covers qualifying inpatient hospital care, skilled nursing facility care, hospice and some home health care. Coverage has service-specific requirements and cost sharing.',
    ['A hospital or nursing-home stay alone does not establish covered inpatient or skilled care. Long-term custodial care is different.'],
    [span('rates-2026', 'Medicare Part A covers inpatient', 'home health care services.')])

add('pk_part_a_premium', 'costs', 'Premium-free Part A and work credits',
    ['40 quarters', 'forty quarters', 'premium free part a', 'part a premium', '10 years of work'],
    'Most people pay no Part A premium because of qualifying Medicare-covered work, generally 40 quarters (about 10 years), on their own or a qualifying family member’s record. People who do not qualify may be able to buy Part A; buying it also requires Part B.',
    ['Premium-free does not mean all care is free. Age, disability and ESRD have different entitlement and work-credit rules; 40 quarters is not a universal requirement for every pathway.'],
    [span('rates-2026', 'Approximately 99%', 'Social Security Administration.'),
     span('eligibility', 'To be eligible for premium-free Part A,', 'during the person\'s working years.'),
     span('costs-2026', 'If you don’t qualify for a premium-free Part A,', 'sign up for Part B to buy Part A.')])

add('pk_part_b_benefits_premium', 'costs', 'Part B coverage and the 2026 standard premium',
    ['what does part b cover', 'medical insurance', 'part b premium', '202.90', 'durable medical equipment', 'part b benefits'],
    'Part B covers services such as doctors’ care, outpatient care, many preventive services and durable medical equipment. Its standard monthly premium is $202.90 in 2026; a person’s amount can differ because of income, penalties or assistance.',
    ['The figure is for 2026, not another coverage year or every person’s bill. Coverage and cost sharing depend on the particular service.'],
    [span('rates-2026', 'Medicare Part B covers physicians', 'certain other medical and health services not covered by Medicare Part A.'),
     span('rates-2026', 'The standard monthly premium for Medicare Part B', 'from $185.00 in 2025.'),
     span('parts', 'Original Medicare includes', 'preventive services.'),
     span('costs-2026', 'Costs for Part B (Medical Insurance)', 'Costs for plans & supplemental coverage')])

add('pk_part_c_premium', 'coverage', 'Medicare Advantage benefits and premiums',
    ['part c premium', 'advantage premium', 'part c benefits', 'what does part c cover'],
    'Part C, or Medicare Advantage, is Medicare coverage through a private plan that provides Part A and Part B benefits and usually Part D. Members must keep Part B and its premium obligation, plus any premium the plan charges; a zero-dollar plan premium does not mean zero total costs.',
    ['Part B premium assistance or a plan’s premium reduction can affect what a person actually pays. Drug coverage and additional benefits vary by plan.'],
    [*copy.deepcopy(next(f for f in catalog['facts'] if f['id']=='pk_routes')['support']),
     span('compare', 'You pay the monthly Part B premium', "you don't have a separate Part D premium."),
     span('costs-2026', 'Medicare Advantage Plan (Part C):', 'covered health services for the rest of the year.')])

add('pk_part_d_optional', 'drugs', 'Part D coverage, premiums and enrollment',
    ['part d optional', 'part d automatic', 'automatic drug coverage', 'what does part d cover', 'part d premium'],
    'Part D covers outpatient prescription drugs through Medicare-approved private plans: a separate drug plan or a Medicare Advantage plan with drug coverage. Part A enrollment alone does not ordinarily add Part D. Plan premiums vary, and delaying without creditable drug coverage can bring a penalty.',
    ['Automatic enrollment can apply to people with Medicare and full Medicaid or Extra Help. Part A or Part B is needed for a standalone drug plan; Medicare Advantage requires both. Some drugs fall under Part A or B instead of D.'],
    [*copy.deepcopy(next(f for f in catalog['facts'] if f['id']=='pk_routes')['support']),
     span('cms-basics', 'Quick Facts\n', 'Page 2 of 8'),
     span('costs-2026', 'Drug coverage (Part D):', 'Example of the Part D penalty.'),
     span('medicaid', 'If you\'re dually eligible, Medicare covers your prescription drugs.', 'Medicaid may still cover it in certain situations.'),
     span('help', 'We’ll automatically enroll you in a', 'You can pick a different Medicare drug plan if you want.'),
     span('drug-tiers', 'Part D & limited drug coverage', 'Learn more about outpatient drug coverage.')])

add('pk_disability_eligibility', 'eligibility', 'Medicare before 65: disability and ALS',
    ['24 months', 'ssdi', 'als', 'lou gehrig', 'medicare disability', 'under 65 medicare'],
    'People under 65 generally get Medicare automatically after 24 months of entitlement to Social Security disability benefits, with coverage beginning in the 25th month, or at 65 if that comes first. For this disability route, initial enrollment runs from three months before the 25th benefit month through three months after it. For ALS, the Medicare waiting period is waived: coverage starts with the first month of disability-benefit entitlement.',
    ['These are benefit-entitlement rules, not 24 months after diagnosis or application. Qualifying Railroad Retirement disability benefits also have a Medicare pathway; other special cases need their own review. This does not establish a person’s disability award.'],
    [span('eligibility', 'Medicare Based on Disability\n', 'There is no waiting period.'),
     span('eligibility', 'For someone under age 65 who becomes entitled', 'The IEP for people with ESRD and ALS varies based on their situation.'),
     span('other-paths', 'If you’re under 65 and getting disability benefits', 'whichever comes first.')])

add('pk_esrd_eligibility', 'eligibility', 'Medicare based on ESRD has separate start rules',
    ['esrd eligibility', 'kidney failure', 'dialysis', 'kidney transplant'],
    'End-stage renal disease can provide a Medicare pathway at any age for someone needing regular dialysis or a kidney transplant who meets the work or benefit-record requirements and applies. Dialysis-based coverage usually begins in the fourth month of dialysis; qualifying home-dialysis training or transplant circumstances can allow an earlier start.',
    ['ESRD does not mean immediate automatic Medicare on diagnosis. Exact treatment, training, transplant, application and eligibility dates matter. The current-employment Part B SEP is not the ESRD enrollment rule.'],
    [span('eligibility', 'Medicare Based on End-Stage Renal Disease (ESRD)\n', 'Two months prior to the month of transplant if the individual was hospitalized during those months in preparation for the transplant'),
     span('esrd', 'When the beneficiary first enrolls in Medicare based on ESRD', 'When Medicare Coverage Ends'),
     span('start', 'This Special Enrollment Period doesn\'t apply', 'still in your Initial Enrollment Period.')])

add('pk_snf', 'coverage', 'Skilled nursing care and the qualifying hospital stay',
    ['skilled nursing', 'snf', 'three day stay', '3 day stay', 'observation stay'],
    'Original Medicare Part A generally requires a medically necessary inpatient hospital stay of at least three consecutive days before covered skilled nursing facility care. The discharge day and time in observation or the emergency room before inpatient admission do not count. Approved waivers and some Medicare Advantage plans can remove the three-day requirement.',
    ['Other requirements still apply, including a need for daily skilled care, a Medicare-certified facility, available benefit days and generally admission within 30 days after leaving the hospital. It is not a guarantee of long-term nursing-home coverage.'],
    [span('snf', 'Medicare will only cover care', 'Contact your plan for more information.'),
     span('snf', 'You must meet all of these conditions:', 'prevent or delay it from getting worse.')])

add('pk_custodial', 'coverage', 'Long-term custodial care is not a Medicare benefit',
    ['custodial care', 'long term care', 'nursing home coverage', 'help bathing'],
    'Medicare does not pay for long-term custodial care such as help with bathing, dressing and other daily activities. This is different from limited covered skilled nursing care. Medicaid may cover long-term care for someone who meets that state’s program requirements.',
    ['Do not equate every nursing-home service with custodial care, or infer Medicaid eligibility from a need for care.'],
    [span('custodial', 'Long-term care (also called', 'Adult day health care'),
     span('custodial', 'Long-term care is different', 'private long-term care insurance.')])

add('pk_initial_plan_window', 'enrollment', 'First Medicare Advantage or Part D plan enrollment',
    ['initial plan enrollment', 'first drug plan', 'first advantage plan', 'part d enrollment window'],
    'The first plan-enrollment opportunity generally runs around initial Medicare eligibility. A standalone Part D plan needs Part A or Part B; Medicare Advantage needs both. If the plan request is made before the required Medicare coverage starts, plan coverage starts with it; a request after that start generally takes effect the first of the month after the plan receives it.',
    ['For age-65 eligibility, the general window is seven months around the eligibility month; first-of-month birthdays and earlier disability, ALS or ESRD eligibility need their own timing. Plan enrollment and the Part A/B application are separate.'],
    [span('join', 'Initial Enrollment Period\nGenerally', 'Your plan coverage starts the first of the month after the plan gets your request.'),
     *copy.deepcopy(next(f for f in catalog['facts'] if f['id']=='pk_iep')['support'])])

add('pk_enrollment_windows', 'enrollment', 'Choose the enrollment clock by situation and coverage',
    ['enrollment windows', 'enrollment periods', 'when can i enroll', 'when can i sign up', 'which enrollment period'],
    'Medicare has separate enrollment clocks: the initial window around first eligibility; January–March general enrollment for Part B and premium-Part A; a work-based Part B special period; October 15–December 7 for annual health/drug-plan changes; January–March for changes by existing Medicare Advantage members; and a six-month Medigap buying window tied to being 65 or older with Part B. The right window depends on the coverage and situation.',
    ['A plan-change window does not itself enroll someone in Part B or guarantee Medigap. The eight-month work SEP is not a Part D deadline. Confirm eligibility basis, birthday, existing parts and coverage/end dates before a personal timing calculation.'],
    [*copy.deepcopy(next(f for f in catalog['facts'] if f['id']=='pk_iep')['support']),
     *copy.deepcopy(next(f for f in catalog['facts'] if f['id']=='pk_gep')['support']),
     *copy.deepcopy(next(f for f in catalog['facts'] if f['id']=='pk_work_sep')['support']),
     *copy.deepcopy(next(f for f in catalog['facts'] if f['id']=='pk_aep')['support']),
     *copy.deepcopy(next(f for f in catalog['facts'] if f['id']=='pk_ma_oep')['support']),
     *copy.deepcopy(next(f for f in catalog['facts'] if f['id']=='pk_medigap_window')['support'])])

add('pk_work_sep_start', 'enrollment', 'Working past 65: Part B SEP and effective date',
    ['retiring when', 'work sep', 'part b special enrollment', 'eight month window', '8 month window', 'retiree enrollment'],
    'After the Initial Enrollment Period, qualifying current-employment group coverage can allow Part B enrollment while covered or in the eight-month period after employment or coverage ends, whichever happens first, without a late penalty. Coverage generally starts the month after enrollment. While still working or within the first full month after employer coverage ends, a person can request a Part B start delayed by up to three months.',
    ['Own or spouse’s current work is the usual basis; a disabled person covered through another family member needs the large-group condition. COBRA and retiree coverage do not extend this work-based window. ESRD and someone still in the IEP follow separate rules. The Part D/MA plan window is different.'],
    [span('start', 'Have or had health insurance through your job', 'Getting COBRA doesn’t change when this Special Enrollment Period ends.'),
     span('start', 'Situations that don’t qualify for a Special Enrollment Period:', 'Learn more about Medicare coverage for ESRD.'),
     span('work', 'You can wait until you (or your spouse) stop working', 'late enrollment penalty\n.')])

add('pk_first_day_birthday', 'enrollment', 'A birthday on the first shifts initial enrollment earlier',
    ['birthday on the first', 'born on the first', 'birthday is the first', 'first day birthday'],
    'For someone first eligible at 65 whose birthday is on the first of a month, the seven-month Initial Enrollment Period starts four months before the birthday month and ends two months after it. Generally, Medicare can start on the first day of the month before the birthday month, depending on the part and enrollment timing.',
    ['Keep premium-free Part A separate from Part B and premium-Part A. This explains the shifted window; it does not calculate an individual deadline or imply that a late Part B application is backdated.'],
    [span('start-birthday-drawer', 'Your 7-month period starts earlier.', 'your coverage starts May 1st.'),
     *copy.deepcopy(next(f for f in catalog['facts'] if f['id']=='pk_start')['support'])])

add('pk_new_part_b_plan_window', 'enrollment', 'Adding Part B later: first Medicare Advantage enrollment',
    ['adding part b later', 'new to part b', 'part a now adding part b', 'first both a and b'],
    'Someone who already has Part A and adds Part B later has an initial Medicare Advantage enrollment opportunity tied to first having both parts. A request before Part B starts can take effect with Part B; a request after Part B starts generally takes effect the first of the month after the plan receives it.',
    ['A valid plan-enrollment window is still required; check its precise opening and closing dates separately. This does not create a Part B SEP or a new universal Part D window. Creditable drug coverage and any separate drug-plan SEP still matter.'],
    [span('join', 'Initial Enrollment Period – New to Part B', 'Generally, the first of the month after the plan gets your request to join.'),
     span('plan-enrollment', 'Get Part B after your Part A', 'Yearly enrollment periods'),
     *copy.deepcopy(next(f for f in catalog['facts'] if f['id']=='pk_join')['support'])])

add('pk_plan_coverage_loss_window', 'enrollment', 'Losing employer or creditable drug coverage: plan windows',
    ['losing drug coverage', 'cobra ends drug plan', 'retiring drug plan', 'loss of creditable coverage', 'two month drug window'],
    'Leaving employer or union coverage, including COBRA, generally gives two full months after the month coverage ends to join a Medicare Advantage or drug plan. Involuntary loss of creditable drug coverage, or notice that it is no longer creditable, has a separate plan SEP ending two full months after the month of loss or notification, whichever is later. Plan coverage generally starts the month after the plan receives the request.',
    ['These plan windows are not the eight-month Part B SEP. A plan SEP does not erase Part D penalty risk from 63 consecutive uncovered days; coordinate the actual drug-coverage end and new start. Confirm plan prerequisites and the specific qualifying event.'],
    [span('special', 'I left coverage from my employer or union', 'whichever is later.I had drug coverage'),
     span('join', 'Special Enrollment Period\nVaries.', 'Generally, the first of the month after the plan gets your request to join.'),
     *copy.deepcopy(next(f for f in catalog['facts'] if f['id']=='pk_creditable')['support'])])

add('pk_ma_oep_effective', 'enrollment', 'Medicare Advantage Open Enrollment: one change and start date',
    ['ma open enrollment', 'advantage open enrollment start', 'switch advantage', 'ma oep'],
    'During January 1–March 31, someone already in Medicare Advantage can make one change to another MA plan or return to Original Medicare and join a separate drug plan. The change takes effect on the first of the month after the plan gets the request. Someone who joined MA during initial enrollment also has a change opportunity within the first three months with Parts A and B.',
    ['This does not let a person in Original Medicare newly join MA during the MA Open Enrollment Period, or create a Medigap guaranteed-issue right. Medical Savings Account plans have separate enrollment limits. Keep annual October 15–December 7 enrollment separate.'],
    [span('join', 'If you joined a Medicare Advantage Plan during your Initial Enrollment Period', 'first 3 months you have Medicare Part A and Part B.'),
     span('plan-enrollment', 'Yearly enrollment periods', 'Special Enrollment Periods\n'),
     *copy.deepcopy(next(f for f in catalog['facts'] if f['id']=='pk_ma_oep')['support'])])

add('pk_medigap_window_scope', 'medigap', 'Medigap buying window and coverage start are separate',
    ['medigap underwriting', 'medigap enrollment window', 'medigap start date', 'six month medigap'],
    'The federal Medigap Open Enrollment Period lasts six months starting the first month a person is at least 65 and enrolled in Part B. During this window, an insurer cannot refuse a policy it offers because of health problems. Starting Part B while still working can start this clock; retirement does not automatically restart it.',
    ['The right to buy does not itself establish a policy’s effective date or resolve any pre-existing-condition waiting period. Confirm the issued policy’s start and applicable rights. The three held Florida legal details remain held.'],
    [span('medigap', 'You get a 6 month', 'Medicare Open Enrollment Period.'),
     span('medigap-window', 'When your employer coverage ends,', 'even if you sign up for Part B while you still have employer coverage.')])

add('pk_penalty_a', 'enrollment', 'Part A late-enrollment penalty',
    ['part a penalty', 'double the years', 'twice the years'],
    'The Part A late-enrollment penalty applies only to people who must buy Part A. Their monthly premium may increase 10%, generally for twice the number of years they delayed enrollment. For example, two countable years late means four years at the higher premium.',
    ['Premium-free Part A has no Part A late penalty. Qualifying Special Enrollment Period protections can prevent the penalty. This is a general formula, not a personal assessment.'],
    [span('penalties', 'Part A late enrollment penalty\nSome people', 'Find out if you’re eligible for a Special Enrollment Period.')])

add('pk_penalty_b', 'enrollment', 'Part B penalty: full 12-month periods',
    ['part b penalty', '23 months late', '24 months late', 'two years late', '12 month penalty'],
    'The Part B late-enrollment penalty is generally 10% of the standard Part B premium for each full 12-month period a person could have had Part B but did not. It is added monthly and generally lasts while they have Part B. With no excluded months or exemption, 24 countable months gives 20%; 23 countable months gives 10%.',
    ['The examples assume countable delay, not just time since a birthday. Qualifying SEP or Medicare Savings Program protections can change the outcome. Income adjustments are separate. Do not state that an individual owes a lifelong penalty from an incomplete coverage history.'],
    [span('penalties', 'Part B late enrollment penalty\nGenerally', 'Part D late enrollment penalty'),
     span('costs-2026', 'It’s not a one-time late fee — you’ll pay the penalty for as long as you have Part B.', 'Example of the Part B penalty.')])

add('pk_penalty_d', 'enrollment', 'Part D penalty: uncovered months and the national base premium',
    ['part d penalty', 'one percent per month', '1 percent per month', 'national base beneficiary premium', '63 day gap'],
    'A Part D late penalty can apply after the initial enrollment opportunity if someone eligible for Part D goes at least 63 consecutive days without Part D or other creditable drug coverage. The monthly penalty is 1% of the national base beneficiary premium times the number of full uncovered months, rounded to the nearest 10 cents and added to the plan premium. It generally lasts while the person has Part D.',
    ['The 2026 national base beneficiary premium is $38.99; it is not the person’s plan premium and can change each year. Extra Help protects against the penalty. The 63-day trigger, full-month count and enrollment window are different rules; no personal calculation is authorized by this fact.'],
    [span('partd-costs', 'What’s the Part D late enrollment penalty?\nThe Part D', 'What if I don’t agree with the Part D late enrollment penalty?')])

add('pk_payer_disability', 'work', 'Under-65 disability: the 100-employee payer rule',
    ['disability who pays first', '100 employees', 'hundred employees', 'disabled employer coverage'],
    'For a person under 65 with Medicare based on disability and group coverage through their own or a family member’s current employment, the group plan generally pays first if the employer has at least 100 employees. Below 100, Medicare generally pays first unless the multi-employer large-group rule applies.',
    ['Employer size uses Medicare’s counting rules, not just today’s headcount or the number enrolled in insurance. Age-65 and ESRD coordination are different branches; confirm entitlement basis and current-employment status.'],
    [span('cms-payer', '2. Disability and Employer GHP:', 'GHP pays Primary, Medicare pays secondary'),
     span('msp-manual', 'Pursuant to 42 CFR § 411.204', 'based on the individual\'s current employment status or the current employment status of\na family member.'),
     span('msp-manual', 'Medicare is not secondary under the MSP provision for disabled individuals:', '100 or more employees participates;'),
     span('msp-manual', 'The Medicare as secondary for the disabled provision applies only', 'during the previous calendar year.')])

add('pk_payer_esrd', 'work', 'ESRD: 30-month coordination and prior-primary exception',
    ['esrd who pays first', '30 month coordination', '30 months', 'esrd payer', 'esrd cobra'],
    'For ESRD-based Medicare, an employer group plan generally pays first for a 30-month coordination period regardless of employer size or whether coverage comes from current employment, COBRA or retirement. Medicare then generally becomes primary. If Medicare was already properly primary under age or disability rules when ESRD eligibility began, it remains primary.',
    ['The coordination clock is tied to the first month of ESRD eligibility or entitlement, not simply the application date; delaying enrollment does not necessarily delay it. Confirm the earlier entitlement and coverage history before applying the table.'],
    [span('esrd', 'Medicare is the secondary payer to group health plans', 'its benefits are secondary to Medicare.'),
     span('msp-manual', 'The coordination period is a period that begins', 'months to 30 months.'),
     span('msp-manual', 'Medicare is secondary payer during the first 30 months', '(Refer\nto subsection B below if Medicare is properly primary.)'),
     span('msp-manual', 'Rule: If Medicare is the proper primary payer', 'ESRD coordination period.')])

add('pk_payer_retiree_cobra', 'work', 'Retiree and COBRA payer order',
    ['retiree who pays first', 'cobra who pays first', 'retiree primary', 'cobra primary', 'retiree secondary'],
    'For Medicare based on age or disability, Medicare generally pays before retiree coverage or COBRA. Those plans may calculate benefits as if Medicare had paid even when an eligible person has not enrolled, leaving a large gap.',
    ['ESRD coordination can change payer order, including for COBRA or retiree plans. Confirm actual plan terms and Medicare entitlement; this fact does not decide an individual claim or extend Part B enrollment rights.'],
    [span('cms-payer', '4. Consolidated Omnibus Budget', '6. No-fault Insurance and Liability Insurance'),
     span('payer', 'If you have COBRA and you’re eligible for Medicare:', 'Contact your COBRA plan and ask what percent they pay.'),
     span('payer', 'Retiree coverage might not pay', 'get full benefits from your retiree coverage.'),
     span('msp-manual', 'Covered by an LGHP as a result of past employment', 'employment status;')])

add('pk_payer_injury', 'work', 'Work injury, no-fault and liability insurance',
    ['workers compensation', 'work injury', 'auto accident', 'no fault', 'liability insurance', 'conditional payment'],
    'Workers’ compensation, no-fault and liability insurance generally pay before Medicare for services related to the covered illness or injury. When the responsible payer does not pay promptly, Medicare may make a conditional payment that must be repaid from a later settlement, judgment, award or other payment.',
    ['This is not payer order for all unrelated medical care. Conditional payment is not guaranteed; workers’ compensation set-asides, ongoing responsibility and claim-specific recovery rules need separate review.'],
    [span('cms-payer', '6. No-fault Insurance and Liability Insurance', 'Responsibilities of Beneficiaries Under MSP')])

add('pk_formulary_tiers', 'drugs', 'Formularies and cost-sharing tiers',
    ['drug tiers', 'lower tier', 'formulary tiers', 'preferred drug', 'non preferred drug'],
    'A formulary is a plan’s covered drug list. Many Part D plans organize it into cost-sharing tiers; a lower tier generally costs less. Tier structures vary, so the same drug or tier number can mean different costs in different plans.',
    ['A tier label does not verify a person’s exact drug, pharmacy, price or restrictions. Do not assume every plan has the same tiers or every lower-tier fill costs less in every situation.'],
    [span('drug-tiers', 'A plan’s list of covered drugs', 'plans can choose which drugs they’ll offer.'),
     span('drug-tiers', 'Tiers\nTo lower costs', 'very high-cost prescription drugs')])

add('pk_formulary_exception', 'drugs', 'Formulary exceptions and rule waivers',
    ['formulary exception', 'waive prior authorization', 'waive step therapy', 'waive quantity limit', 'non formulary drug'],
    'A formulary exception asks a Part D plan to cover a Part D drug absent from its formulary, or waive a prior-authorization, step-therapy or quantity-limit requirement for a covered drug. The prescriber must support why the requested drug or amount is medically necessary and the alternatives or limit are unsuitable.',
    ['A request is a coverage determination, not automatic approval or clinical advice. It cannot simply turn an excluded non-Part-D drug into a covered Part D drug. The plan’s decision and appeal rights remain separate.'],
    [span('exceptions', 'An exception request is a type of coverage determination.', 'How to Submit a Supporting Statement')])

add('pk_tiering_exception', 'drugs', 'Tiering exceptions and prescriber support',
    ['tiering exception', 'tier exception', 'lower copayment', 'nonpreferred drug exception'],
    'A tiering exception asks a Part D plan to charge preferred-tier cost sharing for a non-preferred drug. The prescriber must explain why the preferred alternatives would be less effective, cause adverse effects, or both. Approval depends on the plan’s exception rules and the supporting evidence.',
    ['Not every drug or tier qualifies for a lower-tier exception; a request does not guarantee a lower price or an approval. This is different from asking to cover a non-formulary drug.'],
    [span('exceptions', 'An exception request is a type of coverage determination.', 'or both.')])

add('pk_medigap_drug_exclusion', 'medigap', 'Medigap sold since 2006 does not include drug coverage',
    ['medigap drug coverage', 'medigap prescriptions', 'medigap 2006', 'medigap part d'],
    'Medigap policies sold after 2005 do not include prescription drug coverage. Someone buying Medigap now can obtain separate Part D coverage; an older Medigap policy with a drug benefit has different considerations.',
    ['Do not assume an older drug benefit is creditable or cancel existing benefits without checking the policy. Medigap and Part D are separate policies even if one insurer offers both.'],
    [span('medigap-drugs', 'Medigap plans sold after 2005', 'Contact your insurance company for more details.')])

add('pk_part_d_cap', 'costs', 'Part D annual out-of-pocket cap: 2026',
    ['part d cap', 'drug cap', '2100', '2 100', 'drug out of pocket', '2000 cap'],
    'The Part D annual out-of-pocket cap began at $2,000 in 2025 and is $2,100 in 2026, with annual adjustment. Once qualifying out-of-pocket spending reaches the threshold, the person pays no cost sharing for covered Part D drugs for the rest of that calendar year.',
    ['This is the covered-Part-D drug threshold, not a cap on all medical costs, premiums or drugs outside Part D coverage. Certain payments on the person’s behalf count, including Extra Help. Use the plan’s Explanation of Benefits to track qualifying spending; do not use the 2025 or 2027 amount for 2026.'],
    [span('partd-redesign', 'The CY 2026 annual out-of-pocket (OOP) threshold', 'previous year (API).'),
     span('partd-costs', 'Initial coverage stage:', 'what counts toward your out-of-pocket costs and your total drug costs.')])

add('pk_medicaid_governance', 'assistance', 'Who funds and administers Medicaid',
    ['who funds medicaid', 'who runs medicaid', 'medicaid federal state', 'medicaid administration'],
    'Medicaid is jointly funded by the federal and state governments. Each state administers its program within federal law and guidelines, including state eligibility standards, covered services and payment rates. Medicare and Medicaid are distinct programs, and a person can qualify for both.',
    ['This structural overview does not establish Florida eligibility, financial limits or entitlement to a specific service. The 2024 CMS fact sheet is used only for program structure, not dated enrollment statistics or benefit figures.'],
    [span('cms-basics', 'Quick Facts\n', 'Page 2 of 8'),
     span('medicaid', 'People who have both Medicare and full-benefit Medicaid coverage', 'Medicaid pays last, after Medicare and any other health insurance you have.')])

add('pk_ssa_disability_definition', 'eligibility', 'Social Security’s adult disability standard',
    ['social security disability definition', 'strict disability', 'substantial gainful activity', 'ssdi definition', '12 months disability'],
    'The general adult Social Security disability standard requires a medically determinable physical or mental impairment that prevents substantial gainful work and has lasted, or is expected to last, at least 12 continuous months or result in death. Generally, the person must be unable to do previous work or other substantial gainful work existing in the national economy, considering age, education and work experience.',
    ['This is not the same as a private policy’s own-occupation test or a short-term inability to work. Special blindness rules and other benefit requirements apply; this explanation does not determine disability eligibility. The blocked SSA webpage is not used as evidence; support comes directly from 42 USC 423(d).'],
    [span('ssa-law', '(d) “Disability” defined', '(3) For purposes of this subsection')])

assert len(catalog['facts']) == len({f['id'] for f in catalog['facts']})
write('catalog.json', catalog)
write('review-digests.json', {'revision': ROOT.name, 'purpose': 'general_education',
    'status': 'review_only_not_approvals',
    'fact_digests': {f['id']: approval_digest(f, sources) for f in catalog['facts']}})
write('addition-ids.json', [f['id'] for f in catalog['facts'] if f['id'] not in old_ids])
# This is a portable review fixture with only the already accepted receipts.
# It is NOT the running app's controls file.
control = json.loads((ROOT.parents[2] / 'alternatives/advisor-first/pilot-knowledge-review-8895.json').read_text())
control['revision'] = ROOT.name
control['extension_state'] = 'new_facts_pending_exact_acceptance'
write('review-controls.json', control)
print(f'{len(catalog["facts"])} indexed facts; {len(catalog["facts"])-len(old_ids)} new candidates; existing 40 receipts preserved.')
