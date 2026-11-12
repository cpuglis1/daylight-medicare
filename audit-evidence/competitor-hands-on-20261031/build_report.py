"""Build a dated, local research handoff from observed browser sessions."""
from pathlib import Path
import csv
import hashlib
import html
import json

ROOT = Path(__file__).resolve().parent
ROWS = []

def add(number, name, group, priority, url, access, status, observed, overlap, next_step, evidence):
    ROWS.append(dict(number=number, name=name, group=group, priority=priority,
                     url=url, access_url=access, test_status=status,
                     observed=observed, daylight_overlap=overlap,
                     manual_next_step=next_step, evidence=evidence.split() if evidence else []))

add(1, 'The Pocket Protector / Dorothy', 'Consumer advisor candidates', 1,
    'https://thepocketprotector.com/', 'https://thepocketprotector.com/tools/medicare-advantage',
    'Partial profile; Dorothy not tested',
    'The existing-Medigap branch immediately advised retaining G/F and offered meetings. The separate MA finder accepted 34102, displayed 56 county plans and opened a four-stage personalizer. That flow was not finished. Dorothy was linked through mobile apps, rather than tested in this web session.',
    'High investigation priority: consumer education, coverage-path guidance and plan research are present across its surfaces. Whether Dorothy actually connects all three remains untested.',
    'Install the Dorothy app and determine its account requirements. Ask whether one conversation can preserve this profile, compare keeping G plus Part D against MA, and inspect actual plan evidence. Finish the separate MA personalizer.',
    'pocket-existing-medigap pocket-ma-personalizer pocket-ma-zip')

add(2, 'MatchYourMedicare / careCycle', 'Consumer advisor candidates', 2,
    'https://www.matchyourmedicare.com/', 'https://www.matchyourmedicare.com/',
    'Live plan results; voice guide not tested',
    'ZIP, DOB, sex, three drug strengths and diabetes/hypertension produced 32 MA options without an account. A detail view showed approximately $629 annual medical and $0 drug cost for BlueMedicare Premier. A separate preference branch produced 74 supplement options, headed by high-deductible F. The tested flow had not established F eligibility or a combined G-plus-Part-D comparison. Voice guidance requested microphone permission.',
    'Strong observed overlap in self-service research and estimated-cost comparison; conversational guidance remains untested. No full verified annual-cost comparison was established.',
    'Run the voice guide with microphone permission and this exact case. Check whether it can challenge its own MA-versus-Medigap defaults, establish eligibility/underwriting, collect quantities and pharmacy, and explain estimate assumptions.',
    'match-plan-detail match-supplement-path match-guide-access')

add(23, 'PlanMatch / Benefits Life — consumer Ramona', 'Consumer advisor candidates', 3,
    'https://planmatchmedicare.com/', 'https://planmatchmedicare.com/?zip=34102#ask',
    'Full scenario and two follow-ups; public chat',
    'Ramona accepted the full case without login. The first reply declined ranking or recommending a specific plan. A narrower education question produced relevant snowbird, HMO/PPO and Medigap-return discussion with source links and explicit unknowns. A verification follow-up could not substantiate exact plan IDs or drug/provider checks. The separate site displayed 2027 options: 32 MA, 27 Medigap and 5 Part D, explicitly limited to plans it offers. Those listings were not personally validated.',
    'The clearest observed combination of accessible Medicare conversation and nearby plan browsing. Its explicit recommendation boundary leaves an important distinction from Daylight’s intended advice-and-action model.',
    'No access request is needed for the public chat. Test whether chat and the drug/pharmacy/plan controls share confirmed context, and whether a consumer can complete a comparison and proceed without a call.',
    'planmatch-ramona-scenario planmatch-education planmatch-verification-reply')

add(4, '64Plus', 'Consumer advisor candidates', 4,
    'https://64plus.org/', 'https://64plus.org/login?redirect=%2Fdashboard%2Fchat',
    'Login gate; no scenario run',
    'The public Ask 64Plus action redirected to a sign-in page for dashboard/chat. No assistant response, personalized research or plan recommendation was observed.',
    'Potential direct consumer-advisor competitor; priority reflects apparent product scope and the live chat entry, not demonstrated quality.',
    'Check account and subscription requirements, then run the synthetic case. Establish whether it researches actual 2027 plans or primarily explains Medicare and uploaded documents.',
    '64plus-access')

add(5, 'Pops', 'Consumer advisor candidates', 5,
    'https://heypops.ai/', 'https://app.pops.health/hub',
    'Verified-contact/account gate; no scenario run',
    'Get Started opened an app requiring verified phone access, with an email alternative. No phone number, email or verification code was submitted.',
    'Potential consumer AI advisor and brokerage competitor. Its actual balance of education, advice and human transfer is untested.',
    'Determine whether email provides a self-service test path and whether a phone conversation is required. Use an approved test account or your own contact details if you choose to proceed.',
    'pops-access')

add(13, 'Navigage AI', 'Consumer advisor candidates', 6,
    'https://www.navigage.ai/', 'https://app.navigage.ai/login',
    'Login gate; no scenario run',
    'A current public site led to a live app sign-in offering email or Google login. The original inventory’s launch-only description was therefore not an adequate account of the entry point. No authenticated product behavior was tested.',
    'Potential direct competitor for continuing Medicare guidance and coverage support. Personalized selection and cost verification remain unknown.',
    'Check available account tiers and whether the product accepts a fictional profile. Separate ongoing benefits navigation from actual plan shopping when testing.',
    'navigage-access')

add(6, 'ANA Health / CheckRx', 'Consumer advisor candidates', 7,
    'https://checkrx.com/work', 'https://app.anahealth.us/login',
    'ANA login gate; consumer ZIP request failed',
    'Try ANA ultimately opened a web app login, not only app-store downloads. The separate CheckRx senior questionnaire accepted 34102 but failed to fetch county information, leaving Find Plans disabled. Neither produced a usable profile-based comparison.',
    'Worth investigating as a possible consumer-and-agent bridge. Do not infer consumer autonomy from the agent assistant’s positioning.',
    'Establish which ANA account supports a beneficiary rather than an agent. Retry the CheckRx senior plan finder, and request a sandbox if ZIP lookup remains unavailable.',
    'ana-login checkrx-zip-error')

add(18, 'Healthpilot', 'Plan comparison benchmarks', 8,
    'https://www.healthpilot.com/', 'https://medicare.healthpilot.com/',
    'Partial 2027 profile; final ranking not completed',
    'The live 2027 path quiz recommended MAPD after nationwide doctor freedom, frequent domestic travel, willingness to pay for fewer referrals and diabetes were entered; it also offered a supplement alternative. The drug UI supported selecting drug form and displayed dose choices. The metformin form was selected, but the dose/quantity/pharmacy sequence and final quotes were not completed after the user shifted to manual investigation.',
    'A serious self-service recommendation benchmark even without a demonstrated consumer LLM. Its guided intake is relevant to Daylight’s education-and-decision experience.',
    'Finish exact prescriptions, quantities, pharmacy and providers. Examine why its path recommendation weighs chronic conditions against travel and doctor freedom, and compare both paths on the same cost basis.',
    'healthpilot-drug-entry')

add(3, 'MedicareShopper.ai', 'Plan comparison benchmarks', 9,
    'https://medicareshopper.ai/', 'https://medicareshopper.ai/',
    'Live personalized results; detail action led to callback form',
    'A long form using the same demographics, preferences, conditions and drug strengths returned BlueMedicare Premier at $629.37 and Wellcare Simple at $670.79 annual estimated cost, each with $0 pharmacy cost. Dose, quantity and CVS were not collected in that run. The recommendation card asserted a physician-network match although no doctors were supplied. Learn More led to a callback request. Inline commission-independence language conflicted with the footer’s compensation/order disclosure.',
    'Direct substitute for plan matching, with weaker observed education and call-free depth. The conflicting disclosure is evidence of inconsistency, not proof that commissions actually changed a result.',
    'Investigate exact plan year/IDs, cost-model inputs and network reasons. Ask how its independence statements reconcile, and whether detailed plan research is available without submitting a callback request.',
    'shopper-results shopper-detail')

add(21, 'AISmartBids / One & Done', 'Plan comparison benchmarks', 10,
    'https://www.aismartbids.com/', 'https://www.aismartbids.com/login',
    'Login gate; no scenario run',
    'The sign-in menu led to an email/password login. The plan optimizer was inaccessible in this session.',
    'Potential recommendation and annual-reshopping substitute. Conversational education and verified comparison quality are untested.',
    'Check whether beneficiary accounts are available independently of an agent. Request test access to an annual optimization run, including keep-current coverage as a possible outcome.',
    'aismartbids-login')

add(22, 'MedicareHarbor', 'Plan comparison benchmarks', 11,
    'https://medicareharbor.com/', 'https://medicareharbor.com/',
    'Initial match and partial personalized assessment',
    'An initial Wellcare Simple match appeared before detailed drug/provider entry. More-plan access asked for email. In a separate personalization flow, selecting predictable costs and doctor freedom led to a supplement-oriented path message; the flow reached the conditions step. The final detailed comparison was not completed.',
    'A relevant personalized matcher with some observed path sensitivity. No conversational advisor was demonstrated.',
    'Finish the assessment and determine which results need email. Test whether the preliminary match changes once exact prescriptions, travel and provider needs are known.',
    'harbor-personalization')

add(17, 'Chapter', 'Brokerage business benchmarks', 12,
    'https://askchapter.org/', 'https://askchapter.org/',
    'Partial intake; required phone gate before results',
    'ZIP, Medicare status, prescription need, extras, DOB and synthetic name reached a phone/marketing-consent step before matches. No public consumer AI conversation or plan comparison was completed.',
    'Important competitor for the overall Medicare advisory and brokerage service, rather than a demonstrated public autonomous AI experience in this test.',
    'Ask for a demonstration using the same fictional case. Establish what the consumer can see before a call, what agents verify, and how much work an internal copilot performs.',
    'chapter-phone-gate')

add(20, 'CoverRight', 'Brokerage business benchmarks', 13,
    'https://coverright.com/', 'https://medicareai.coverright.com/',
    'Partial intake; email/contact gate',
    'ZIP, DOB, sex, tobacco status and synthetic name led to a required email/contact screen with marketing language before plan results. No contact details were submitted.',
    'Digital education and brokerage competitor. This session did not establish a public conversational advisor or independent plan-research completion.',
    'Investigate what is accessible after contact submission, whether an agent call becomes necessary, and whether the comparison includes retaining current G plus Part D.',
    'coverright-contact-gate')

add(19, 'Connie Health', 'Brokerage business benchmarks', 14,
    'https://www.conniehealth.com/', 'https://www.conniehealth.com/',
    'Partial intake; required phone gate',
    'The online questionnaire collected the synthetic coverage priorities and name, then required a phone number to review matches. No contact information was submitted and no recommendations were viewed.',
    'A Medicare advisory/distribution competitor; actual consumer AI interaction was not demonstrated.',
    'Investigate whether matches can be reviewed independently, what the local broker contributes, and whether any AI guidance is consumer-facing.',
    'connie-phone-gate')

add(7, 'MedicareCopilot / HealthcareGPS', 'Agent tools and infrastructure', 15,
    'https://medicarecopilot.ai/', 'https://agent.medicarecopilot.ai/',
    'Agent login gate',
    'The live entry was an agent portal requiring email/password. No beneficiary-facing scenario was run.',
    'Relevant as tooling that could let broker competitors deliver similar work. Less direct as a standalone consumer substitute based on the accessible surface.',
    'Request an agent sandbox and ask to see any distinct consumer/white-label experience. Evaluate plan evidence, scoring, missing inputs and commission separation.',
    'medicarecopilot-login')

add(28, 'LivmorIQ / Ask Erin', 'Agent tools and infrastructure', 16,
    'https://livmor.ai/', 'https://livmoriq.livmor.ai/plans',
    'Organization sign-in gate',
    'Following Basic signup reached the plans app and an organizational Microsoft sign-in requirement. No Ask Erin conversation was tested. Tabor is treated as an alias, not another tested offering.',
    'Agent-side research/copilot competitor; consumer self-service overlap remains unestablished.',
    'Ask whether a trial organization or sandbox is available. Test one case across plan finder, conversational explanation and underlying drug/provider evidence.',
    'livmor-access')

add(27, 'Cairie', 'Agent tools and infrastructure', 17,
    'https://letcairie.com/', 'https://letcairie.com/',
    'Trial/launch-list contact route',
    'The trial action requested a work email for extension access; no public research console was available.',
    'Potential agent productivity competitor, not an observed beneficiary advisor.',
    'Request a controlled extension demo with the fictional case and inspect whether it executes searches or mainly summarizes agent context.',
    'cairie-access')

add(24, 'GoHealth / PlanGPT', 'Agent tools and infrastructure', 18,
    'https://www.gohealth.com/',
    'https://www.gohealth.com/newsroom/brand-stories/harnessing-ai-to-enhance-medicare-enrollment-how-gohealths-plangpt-delivered-clarity-this-aep/',
    'Official access research only; no console',
    'The official PlanGPT page described an internal licensed-agent tool. There was no public PlanGPT profile input to use. This is not a hands-on test of PlanGPT.',
    'GoHealth competes in Medicare distribution; PlanGPT is relevant to the agent-assisted operating model rather than a demonstrated public advisor.',
    'Seek a product demo if comparing agent research operations. Ask how document answers become verified recommendations and what consumers can do on their own.',
    'gohealth-plangpt-access')

add(30, 'Gyde / Gia / GydeOS', 'Agent tools and infrastructure', 19,
    'https://www.gydehealth.ai/', 'https://www.gydehealth.ai/contact-us',
    'Agency demo/contact gate',
    'Schedule a demo led to an agency-oriented contact form with terms and CAPTCHA. No Gia conversation or GydeOS scenario was available publicly.',
    'Relevant to AI-enabled brokerage operations and member service. Its direct consumer-selection overlap is untested.',
    'Request a demo distinguishing consumer Gia, agent copilot, renewals and actual plan recommendation workflows.',
    'gyde-demo-gate')

add(11, 'AskRamona — agent surface', 'Agent tools and infrastructure', 20,
    'https://askramona.app/', 'https://askramona.app/',
    'Agent access-code gate',
    'The agent interface required a personal access code tied to an NPN. Entering the scenario did not yield an answer without access. This gate is separate from the working public PlanMatch Ramona chat.',
    'Potential agent research rival within the Ramona ecosystem. Do not count it as an independently demonstrated consumer competitor in addition to PlanMatch.',
    'Request vendor-issued test access; do not substitute an invented NPN. Compare the agent assistant’s research depth with public Ramona.',
    'askramona-access askramona-denied')

add(15, 'Maya / NestedLoop', 'Agent tools and infrastructure', 21,
    'https://nestedloop.ai/demos', 'https://nestedloop.ai/demo-maya.html',
    'Demo password gate',
    'Launching the Maya demo reached an access-password page. No synthetic-profile conversation was possible.',
    'Potential technology supplier or white-label competitor; an independent production consumer service was not established.',
    'Ask for a demo password and a reusable fictional-profile sandbox. Clarify what is a demonstration versus deployed carrier/agency functionality.',
    'maya-password')

add(33, 'NestedLoop Member Services & Enrollment demo', 'Agent tools and infrastructure', 22,
    'https://nestedloop.ai/demos', 'https://nestedloop.ai/demo-enrollment.html',
    'Demo password gate',
    'The enrollment/member-services demo also required an access password. It is a second surface from the same vendor, not a second independent company.',
    'Potential infrastructure overlap in plan research and service execution; no performance was observed.',
    'Request access alongside Maya. Ask whether enrollment and formulary steps use real test APIs or scripted demo data.',
    'nestedloop-enrollment-password')

add(25, 'Medicare Vox / Sophia', 'Agent tools and infrastructure', 23,
    'https://medicarevox.com/', 'https://medicarevox.com/',
    'Navigation failed in this browser',
    'Opening the listed domain failed with ERR_SSL_PROTOCOL_ERROR. No security bypass or phone test was attempted. There is no screenshot of a working product in this session.',
    'Possible voice/distribution technology competitor from the supplied inventory; current product scope and access need confirmation.',
    'Verify the current vendor/domain and request a live voice sandbox using this case. Establish whether the function is lead screening, advice, enrollment or agent coaching.',
    '')

add(26, 'eHealth / Alice', 'Agent tools and infrastructure', 24,
    'https://www.ehealthinsurance.com/',
    'https://ir.ehealthinsurance.com/news/news-details/2025/eHealth-Advances-its-AI-Strategy-with-Expanded-Voice-Agent-Capabilities/default.aspx',
    'Official access research; live voice not tested',
    'The official Alice page offered a recorded demonstration and telephone service, not a live text console. No call or microphone interaction was made.',
    'Relevant as a major brokerage’s consumer voice channel. Its full advice capability cannot be inferred from the recorded material.',
    'Locate the current live Alice phone entry or ask for a test number. Test whether it educates, recommends, verifies and preserves context through human transfer.',
    'alice-access')

add(31, 'LeadGPT / Sofia', 'Agent tools and infrastructure', 25,
    'https://leadgpt.com/', 'https://app.leadgpt.com/auth?tab=login',
    'Login gate',
    'The sign-in action opened email/password authentication. Sofia was not run.',
    'Primarily an agent communications/lead-workflow candidate in this inventory. Full Medicare advice was not demonstrated.',
    'Only prioritize a demo if researching acquisition, reception or follow-up operations. Ask the vendor to distinguish qualification from actual plan advice.',
    'leadgpt-login')

add(32, 'MedicareSuite / RamonaChat / Ramona Elite', 'Agent tools and infrastructure', 26,
    'https://medicaresuite.com/', 'https://medicaresuite.com/',
    'Coming-soon/waitlist surface',
    'The main suite promoted a waitlist rather than a usable RamonaChat console. Public PlanMatch and the agent AskRamona page were investigated separately.',
    'Future agent-suite overlap; do not treat suite marketing, public Ramona and agent Ramona as three independently proven competitors.',
    'Confirm which modules are shipping and request test access to those modules only.',
    'medicaresuite-waitlist')

add(9, 'Hughes Health / Kim', 'Lower-priority education and adjacent tools', 27,
    'https://hugheshealth.care/', 'https://hugheshealth.care/ask-an-expert',
    'Full scenario and follow-up; public chat',
    'Kim discussed the coverage paths and snowbird concern, then named local-looking MA options and made drug-coverage assertions without exact 2027 plan/formulary support. A challenge requesting verification returned a processing error and an agent route. The drug assertions were not independently established as correct or incorrect.',
    'Observed educational/advisory overlap, but this run did not establish reliable plan research or cost comparison.',
    'Optional retest: ask for exact contract/PBP/year, formulary evidence and annual cost components. Check whether the prior failure was transient.',
    'hughes-kim-answer hughes-kim-challenge hughes-kim-response')

add(8, 'Medi-Chat / Medicare Advantage Answers', 'Lower-priority education and adjacent tools', 28,
    'https://medicareadvantageanswers.com/', 'https://medicareadvantageanswers.com/compare.html',
    'Scenario entered; Send produced no response',
    'Opening Medi-Chat exposed a composer, but two Send methods left the prompt unchanged without an answer. The comparison link opened a separate external marketplace, which was not run with the profile. This session failure may be environmental or transient.',
    'Possible educational widget plus comparison routing, not an established integrated advisor from this test.',
    'Retry the chat manually and investigate whether the marketplace shares profile context. Confirm support for 2027 rather than assuming it from the chat’s 2026 source label.',
    'medichat-send-no-answer')

add(12, 'Insuras Health Benefits', 'Lower-priority education and adjacent tools', 29,
    'https://www.insurashealth.com/', 'https://www.insurashealth.com/plan-finder',
    'Scenario sent; error/human route',
    'The public AI plan-finder entry accepted the case but returned a trouble message and a named human contact. The interface expressly placed licensed human review before policy recommendations.',
    'Education and brokerage overlap, with no substantive AI answer or self-service comparison established in this run.',
    'Retest if desired and ask what the assistant can complete before human review.',
    'insuras-scenario')

add(10, 'Talk Ensure / Ava', 'Lower-priority education and adjacent tools', 30,
    'https://talkensure.com/how-to-use-ava/', 'https://ai.talkensure.com/chat',
    'Scenario and explicit Medicare follow-up; off-topic replies',
    'Both attempts routed back to life-insurance product choices rather than answering the Medicare case.',
    'The claimed Medicare-advisor overlap was not demonstrated. Low manual-investigation priority unless the vendor supplies a different Medicare entry.',
    'Ask for the current Medicare-specific assistant URL before spending time on account or quote setup.',
    'ava-scenario')

add(34, 'MetaCare.ai', 'Lower-priority education and adjacent tools', 31,
    'https://metacare.ai/', 'https://metacare.ai/welcome',
    'Full scenario and follow-up; public chat',
    'The first answer provided useful general path/travel education and acknowledged missing 2027 plan/network/formulary verification. It supplied generic cost ranges rather than actual local options. A follow-up about returning to Medigap elicited a generic request for another health question rather than an answer.',
    'Adjacent health/benefits interpretation, with some Medicare education overlap. No end-to-end shopping capability was demonstrated.',
    'Investigate only if coverage interpretation or connected health records are a priority; keep general explanations separate from verified plan selection.',
    'metacare-response metacare-switching-rights')

add(35, 'MHICO', 'Lower-priority education and adjacent tools', 32,
    'https://mhico.ai/', 'https://mhico.ai/accounts/signup/',
    'Account creation/terms gate',
    'Get Started required email/password, state and explicit agreement to terms/privacy. No account or record connection was created.',
    'Adjacent coverage/claims interpretation candidate. Direct plan-shopping overlap was not established.',
    'If relevant, ask for a synthetic claims/EOB sandbox and establish whether it recommends replacement coverage or only explains existing bills/coverage.',
    'mhico-signup-gate')

add(36, 'HealixAI', 'Lower-priority education and adjacent tools', 33,
    'https://www.healixai.com/', 'https://app.healixai.com/',
    'Full scenario; captured generated clinical response',
    'The public app produced a long Medicare/snowbird answer with illustrative cost ranges, local-carrier/drug assertions and PubMed references. It did not establish exact 2027 plan IDs, formulary or network evidence. It also treated 2027 data as not yet available despite the October 31 test date and digressed into clinical tests and draft-order text. No actual clinical order was placed or confirmed. The latest capture still showed a streaming marker.',
    'Adjacent clinical assistant, not an observed Medicare research engine. Fluent insurance explanation was much stronger than its demonstrated plan verification.',
    'Low priority for plan-shopping competition. If testing, insist on exact year/source evidence and separate clinical drafting from actual supported actions.',
    'healix-latest healix-voice-entry')

add(14, 'AidenRx / RxCare', 'Watch or verify current status', 34,
    'https://aidenrx.com/', 'https://aidenrx.com/',
    'Consumer launch notice; no live consumer composer',
    'Ask Aiden was a sample-image surface, while the availability FAQ pointed to January 2027. The page offered updates rather than a live consumer trial. A separate fixed-profile agent voice demo was not a valid run of this common case.',
    'Emerging prescription/benefits adjacency; not an observed current end-to-end plan-selection competitor.',
    'Recheck consumer availability after launch and confirm whether plan recommendations are in scope.',
    'aidenrx-launch')

add(29, 'Summed AI', 'Watch or verify current status', 35,
    'https://summed.ai/', 'https://www.moonsethealth.com/legal/summed-ai-inc-terms-of-service',
    'Listed domain timed out; associated current site checked',
    'summed.ai timed out in this browser. Associated official legal material identified Moonset Health as a Summed AI product/brand; the current Moonset home page focused on hospice/home-health documentation. That does not prove the Medicare offering was discontinued.',
    'Current Medicare competitor identity and availability are unresolved. Do not count this as a proven active Medicare advisor.',
    'Verify the current product name and live Medicare tool before requesting access or including it in a direct-competitor count.',
    'summed-current-site')

add(16, 'Hyperspace AI Medicare Navigation', 'Watch or verify current status', 36,
    'https://hyperspace.ai/ai/ai-medicare-navigation', 'https://hyperspace.ai/ai/ai-medicare-navigation',
    'Listed product URL returned 404',
    'The specific Medicare navigation URL returned a 404 page. No scenario could be run there.',
    'No currently usable competing Medicare experience was established at the supplied entry.',
    'Only investigate further if the vendor supplies a replacement live URL.',
    'hyperspace-404')

PROFILE = ('This is a fictional research test, not a real person or enrollment request. '
           'I am a 67-year-old woman in Naples, Florida, ZIP 34102, Collier County, born April 15, 1959. '
           'I have Medicare A and B, Medigap Plan G and a standalone Part D plan. I am reviewing coverage for 2027. '
           'I take metformin 500 mg twice daily (60 tablets/month), lisinopril 10 mg daily (30/month), '
           'and atorvastatin 20 mg daily (30/month), filled at CVS. I have diabetes and high blood pressure, '
           'no Medicaid or Extra Help, and do not smoke. I spend four months a year in New Jersey and want routine care '
           'there as well as in Florida. Help me understand keeping Original Medicare plus G and Part D versus switching '
           'to Medicare Advantage before recommending policies. Then show actual local options and estimated total annual '
           'costs, tell me what you checked and what remains unknown, and let me continue without a sales call.')

assert len(ROWS) == 36 and {r['number'] for r in ROWS} == set(range(1, 37))
for row in ROWS:
    for key in row['evidence']:
        for folder, ext in [('snapshots', 'txt'), ('screenshots', 'png')]:
            assert (ROOT / folder / f'{key}.{ext}').is_file(), (row['name'], key, folder)

DATA = {'test_date': '2026-10-31', 'timezone': 'America/New_York',
        'purpose': 'Prioritized manual-access handoff after live public-browser investigation',
        'scope': '36 named offerings in the supplied inventory; not 36 independent companies; not an exhaustive market census',
        'synthetic_profile': PROFILE, 'name_if_requested': 'Pat Morgan',
        'limitations': ['Not every gated tool was used with the profile.',
                        'A single experienced-beneficiary snowbird case does not measure beginner teaching quality.',
                        'Quotes, drug/network assertions, plan counts and completeness were not independently validated.',
                        'No accounts, subscriptions, calls, microphone permissions, enrollment or medical orders were created.',
                        'Manual-investigation priorities are judgments, not performance scores for inaccessible products.'],
        'offerings': sorted(ROWS, key=lambda r: r['number'])}
(ROOT / 'competitors.json').write_text(json.dumps(DATA, indent=2, ensure_ascii=False))
(ROOT / 'synthetic-profile.txt').write_text(PROFILE + '\n\nName if requested: Pat Morgan.\n'
    'Current Medigap/PDP carrier and premiums, named doctors, Medicare eligibility date and underwriting facts remain unknown.\n')
with (ROOT / 'competitors.csv').open('w', newline='') as f:
    fields = list(ROWS[0])
    writer = csv.DictWriter(f, fieldnames=fields)
    writer.writeheader()
    for row in sorted(ROWS, key=lambda r: r['priority']):
        writer.writerow({**row, 'evidence': ' '.join(row['evidence'])})

def esc(value):
    return html.escape(str(value), quote=True)

def link(url, label):
    return f'<a href="{esc(url)}">{esc(label)}</a>'

def proof(keys):
    if not keys:
        return 'Navigation error recorded in the session; no product screenshot.'
    return ' · '.join(f'{link("screenshots/" + key + ".png", key + " image")} '
                      f'({link("snapshots/" + key + ".txt", "text")})' for key in keys)

shortlist = ''.join(f'<tr><td>{r["priority"]}</td><td>{link(r["url"], r["name"])}</td>'
                    f'<td>{esc(r["test_status"])}</td><td>{esc(r["manual_next_step"])}</td></tr>'
                    for r in ROWS if r['priority'] <= 11)
sections = []
for group in dict.fromkeys(r['group'] for r in sorted(ROWS, key=lambda r:r['priority'])):
    cards = []
    for r in sorted([x for x in ROWS if x['group'] == group], key=lambda r:r['priority']):
        cards.append(f'''<article id="offering-{r['number']}">
          <h3>{esc(r['name'])}</h3><p class="meta">Investigation priority {r['priority']} · Original inventory #{r['number']}</p>
          <p><span class="status">{esc(r['test_status'])}</span></p>
          <p><strong>Observed:</strong> {esc(r['observed'])}</p>
          <p><strong>Daylight overlap / judgment:</strong> {esc(r['daylight_overlap'])}</p>
          <p><strong>Manual next step:</strong> {esc(r['manual_next_step'])}</p>
          <p>{link(r['url'], 'Website')} · {link(r['access_url'], 'Access / demo entry')}</p>
          <p class="proof">{proof(r['evidence'])}</p></article>''')
    sections.append(f'<section><h2>{esc(group)}</h2>{"".join(cards)}</section>')

REPORT = f'''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Daylight competitor investigation — October 31, 2026</title>
<style>
:root{{font-family:system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;color:#182c33;background:#f5f5f0;line-height:1.6}}
body{{margin:0}}main{{max-width:1080px;margin:auto;padding:40px 24px 80px}}h1{{font-size:clamp(2rem,4vw,3rem);line-height:1.15;max-width:900px}}h2{{margin-top:42px}}h3{{margin-bottom:2px;font-size:1.25rem}}a{{color:#075e79;overflow-wrap:anywhere}}.eyebrow,.meta,.proof{{font-size:.87rem;color:#4d6269}}.lead{{font-size:1.15rem;max-width:900px}}.note{{border-left:4px solid #ba6b25;padding:12px 20px;background:#fff6e9}}.status{{display:inline-block;padding:3px 9px;background:#e6efed;border-radius:4px;font-size:.9rem}}article{{background:white;border:1px solid #d3dedb;border-radius:8px;padding:20px 24px;margin:16px 0}}article p{{margin:10px 0}}table{{width:100%;border-collapse:collapse;font-size:.94rem;background:white}}td,th{{padding:12px;text-align:left;vertical-align:top;border:1px solid #d3dedb}}th{{background:#e6efed}}.table-scroll{{overflow-x:auto}}blockquote{{margin:0;background:white;padding:20px;border:1px solid #d3dedb}}figure{{margin:24px 0}}img{{display:block;width:100%;height:auto;border:1px solid #cbd5d3}}figcaption{{font-size:.85rem;color:#4d6269}}li{{margin-bottom:8px}}footer{{font-size:.85rem;margin-top:50px;color:#4d6269}}@media(max-width:650px){{main{{padding:24px 16px}}article{{padding:16px}}table{{min-width:850px}}}}@media print{{body{{background:white}}main{{max-width:none;padding:0}}article{{break-inside:avoid}}a{{color:inherit}}}}
</style></head><body><main>
<p class="eyebrow">LIVE PUBLIC-BROWSER INVESTIGATION · OCTOBER 31, 2026 · MANUAL ACCESS HANDOFF</p>
<h1>Which Medicare tools deserve Daylight’s attention?</h1>
<p class="lead">Start with Pocket Protector, MatchYourMedicare and PlanMatch for observable consumer overlap. Investigate 64Plus, Pops, Navigage and ANA next because their actual assistants were gated. Use Healthpilot as a serious self-service recommendation benchmark, even without demonstrated consumer chat.</p>
<p class="note"><strong>This is not a completed test of every product.</strong> All 36 named offerings received an entry/access investigation; accessible chats and forms received the same synthetic case where supported. Several required accounts, credentials, contact consent, voice access or demo passwords. The user then asked to stop dependent tests and compile candidates for manual investigation. An access barrier is not a negative quality score.</p>
<p>{link('competitors.csv','Download the prioritized checklist (CSV)')} · {link('competitors.json','Structured evidence registry (JSON)')} · {link('synthetic-profile.txt','Copy the common synthetic profile')}</p>

<h2>First investigation queue</h2>
<p>The numbers below are suggested investigation order, not a ranking of product quality. The first seven are consumer-advisor candidates; the next four are comparison benchmarks. Gated candidates have not earned a capability verdict.</p>
<div class="table-scroll"><table><thead><tr><th>Order</th><th>Product</th><th>Actual test depth</th><th>What to investigate manually</th></tr></thead><tbody>{shortlist}</tbody></table></div>

<h2>What the live tests establish about overlap</h2>
<ul>
<li><strong>Education plus plan browsing already exists.</strong> PlanMatch’s public Ramona gave relevant coverage-path education with sources and explicit unknowns, alongside actual 2027 plan listings. It expressly declined specific recommendations; the chat could not substantiate the personal drug/provider checks.</li>
<li><strong>Plan results without a sales call already exist.</strong> MatchYourMedicare and MedicareShopper returned named plans and annual estimates. That establishes useful self-service competition, not validated personal total-cost accuracy. Their leading plans and near-identical estimates were similar; a shared data engine is only a hypothesis.</li>
<li><strong>Recommendation explanations can overstate the research performed.</strong> MedicareShopper’s card asserted a network match with no named doctors entered. Hughes and Healix supplied plan/drug assertions without the exact evidence needed to verify them. These are observed verification gaps, not proof every named assertion was false.</li>
<li><strong>Coverage-path decisions need scrutiny.</strong> Healthpilot and MedicareShopper steered this travel-and-doctor-freedom case toward MA; Harbor’s separate personalization branch shifted toward supplements. A single case cannot establish systematic bias or which path is personally correct.</li>
<li><strong>Daylight’s differentiation is a demanding execution standard.</strong> The intended combination is contextual teaching, fair path comparison, verified plan/drug/provider research, inspectable cost assumptions, commercial independence and useful progress without a mandatory call. This session did not establish that any tested product completed that entire chain.</li>
</ul>
<figure><a href="screenshots/shopper-results.png"><img src="screenshots/shopper-results.png" alt="Actual MedicareShopper result from the synthetic profile, showing a named plan, estimated annual cost and recommendation reasons"></a><figcaption>Actual browser capture from the synthetic test. The displayed estimates and network claim were not independently validated. {link('snapshots/shopper-results.txt','Accessible page text')}.</figcaption></figure>

<h2>The common case and what remains unknown</h2>
<blockquote>{esc(PROFILE)}</blockquote>
<p>Name, where a form requested one: <strong>Pat Morgan</strong>. Forms received supported fields rather than invented substitutes. Preferences favored predictable costs, doctor freedom and domestic travel; diabetes and hypertension were entered, and extras were low priority. Drug strength alone was not treated as evidence of dose, quantity or pharmacy verification.</p>
<p>Current G/PDP carrier and premiums, exact doctors, Medicare eligibility date, prior MA history and underwriting facts were intentionally unresolved. A defensible keep-versus-switch cost comparison needs additional information. The profile is an experienced beneficiary, so this test does not establish beginner teaching quality. The single case is neither an exhaustive market study nor a repeatability/adversarial evaluation.</p>
<p>No login account, paid subscription, phone call, microphone permission, callback request, enrollment or medical order was created. No real user health records were connected. Contact-gated results were left untested.</p>

<h2>Daylight comparison boundary</h2>
<p>The comparison uses Daylight’s intended product standard in {link('../../PRINCIPLES.md','PRINCIPLES.md')} and {link('../../docs/product/STRATEGIC_THESIS.md','D73 strategic thesis')}, not a claim that its planned recommendation features are live. Personalized plan recommendations and supporting acceptance gates remain held.</p>
<p>The local advisor-first Daylight surface at :8893 was also tried twice with this case (full and shorter prompts). Both returned a model failure notice; the local error log recorded provider_failure. No successful Daylight answer was available for a response-quality comparison in this session. This is a runtime observation, not a verdict on the product thesis. {proof(['daylight-first-send-error','daylight-second-send-error'])}.</p>

<h2>All 36 offerings: observations and access routes</h2>
<p>Product surfaces are retained from the original inventory to make the handoff auditable. They are not 36 independent companies: Ramona surfaces and NestedLoop demos overlap, and the inventory mixes consumer services, agent software, demos and adjacent health tools. Website links are entry points; “observed” statements are backed by the linked local captures where available. Plans and prices below are reports of outputs, not consumer recommendations.</p>
{''.join(sections)}

<h2>Questions to use in a manual demo</h2>
<ol>
<li>Can I use this fictional case in a sandbox without becoming a sales lead?</li>
<li>Will it fairly compare retaining Original Medicare plus G plus Part D against MA before choosing individual policies?</li>
<li>Can it show the precise year, contract/PBP, plan universe, exclusions and source date?</li>
<li>What exact doses, monthly quantities, CVS location and Florida/New Jersey providers did it actually verify?</li>
<li>What is included in annual cost: premiums, drugs, expected medical use, travel/out-of-network exposure and the current-coverage baseline?</li>
<li>What facts are missing, and will it ask rather than silently filling them in?</li>
<li>Can I inspect alternatives and keep current coverage, without a call or an enrollment?</li>
<li>Do commercial relationships affect inclusion, ordering or explanations, and what evidence supports the answer?</li>
</ol>
<p>For exact medical/coverage rules, independently check official sources such as {link('https://www.medicare.gov/plan-compare/','Medicare Plan Compare')} and {link('https://www.medicare.gov/basics/get-started-with-medicare/get-more-coverage/your-coverage-options/compare-original-medicare-medicare-advantage','Medicare’s coverage-path comparison')}. This handoff evaluates observed product behavior; it does not certify plan facts or legal rights.</p>
<footer>Prepared October 31, 2026. Scope: the user-supplied inventory and current public entry points. Evidence includes screenshots and accessibility snapshots; historical filenames and raw observations are retained. The curated registry corrects provisional notes: Pocket’s ZIP flow eventually advanced; ANA has a web login; Healthpilot’s complete medication setup was not finished; MedicareShopper’s detail action led to a callback form; Healix’s last capture may still be streaming. No Daylight app or sealed source evidence was changed.</footer>
</main></body></html>'''
(ROOT / 'competitor-investigation.html').write_text(REPORT)

manifest = []
for folder in ('snapshots', 'screenshots'):
    for path in sorted((ROOT / folder).glob('*')):
        b = path.read_bytes()
        manifest.append({'path': str(path.relative_to(ROOT)), 'bytes': len(b),
                         'sha256': hashlib.sha256(b).hexdigest()})
(ROOT / 'evidence-manifest.json').write_text(json.dumps(manifest, indent=2))
print(json.dumps({'offerings':len(ROWS), 'shortlist':sum(r['priority']<=11 for r in ROWS),
                  'evidence_files':len(manifest), 'report':str(ROOT/'competitor-investigation.html')}, indent=2))
