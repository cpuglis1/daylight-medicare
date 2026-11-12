# Daylight strategic thesis and evidence roadmap

Owner direction · October 25, 2026 · Updated October 30, 2026 · D73. **Canonical strategy, not a second flow specification or implementation approval.** Read [PRINCIPLES](../../PRINCIPLES.md) first. [PRODUCT](../../PRODUCT.md), [owner requirements](../../DAYLIGHT_REQUIREMENTS.md), [MASTER_DESIGN](MASTER_DESIGN.md) and the applicable surface contract govern implementation. This strategy extends D64's independence requirements and preserves existing source, privacy, recommendation and release gates.

## Central product ambition

Owner-endorsed direction · October 30, 2026 · D73.

> **Tell Daylight what is happening in your life. It figures out what you need to understand, investigates the relevant details, and helps you reach an informed decision without managing the research yourself.**

Daylight's ambition is an AI-native, self-service digital brokerage that makes Medicare education, self-discovery and decision preparation dramatically easier. People should be able to describe their situation in ordinary language, learn exactly what matters to their decision, and have substantial research completed for them. Understanding is a primary outcome; a recommended plan is one possible output. Human staff maintain the service and handle necessary exceptions rather than defining the default consumer journey.

**The central interaction question is whether directed textual conversation through an LLM, alone or combined with inline structured input, can make this easier than an excellent adaptive form using the same underlying evidence.** Test three interface conditions: an excellent adaptive form, directed textual LLM conversation and a hybrid of conversation with inline mini-forms. Easier, informed self-service is the goal. Superiority to a straightforward questionnaire does not settle that question; the comparison must be with an excellent adaptive experience.

### What the person should experience

Someone might begin: “I'm leaving work in March, my spouse is keeping employer coverage, and we spend part of the year somewhere else. I want to keep my specialists, but I don't know where to start.”

The intended service recognizes the consequential issues, clarifies only what is needed, explains the relevant coverage paths and carries out supported research. It brings back understandable tradeoffs, the evidence behind important conclusions, what remains uncertain and a useful next action. The person can ask why, correct a fact and reconsider a priority without restarting the work.

The intended reaction is: **“It understood my situation, caught something I hadn't considered, and made this manageable.”** The consumer should have less research to coordinate, less repetition and less irrelevant material to work through. A longer conversation or a larger collection of answers is not success by itself.

### Depth should make the tool simpler

**Does the depth matter to consumers? Sometimes directly, often through the experience it enables.**

Consumers generally will not value “249,000 condition predicates.” They may value discovering that an apparently attractive benefit has an important limitation, understanding why a coverage path fits their priorities, or avoiding hours of contradictory research. The 15 layers are an enabling foundation; their value must appear in the person's experience.

There are three ways the extra depth could earn its cost:

- **It changes a consequential conclusion or next action.**
- **It supports a clearer, more trustworthy explanation.**
- **It lets the software complete work the person would otherwise do.**

**Daylight could recommend the same plan as a simpler tool and still be substantially more valuable.** The person may reach that selection with better understanding, fewer unresolved questions and much less effort. Selecting a different plan is not required to demonstrate value. Confidence alone is insufficient: the explanation and research must be sound, and the person must understand the important tradeoffs.

Comprehensive research should produce a manageable decision. Investigate the complete relevant universe, explain the differences that matter now and let the person inspect the supporting details and other options. More backend depth should not become a longer universal questionnaire or a demand that every person learn every Medicare rule. Simpler presentation does not justify silent exclusions, lost conditions or treating unknown evidence as poor fit.

### Strongest starting audience

**Independent researchers facing their first Medicare transition, especially when employer coverage or family circumstances make the decision feel consequential.** They have an immediate reason to act, lack a trusted agent and may want to understand before committing. Adult children helping a parent are another promising audience to investigate, with appropriate permission and clarity about whose situation is being considered.

This is the owner-endorsed starting audience to test. Urgency, preference for directed conversation and the size of the reachable market remain hypotheses. People without an agent are not automatically dissatisfied or in need of Daylight; competing for people who already like their agent is not the acquisition objective. Existing supported audiences remain supported.

Within this audience, a promising segment is **people who can describe their situation but struggle to translate it into the categories and questions a Medicare tool expects**. They may need clarification, plain-language explanations and help organizing the decision, even when the eventual plan selection is straightforward. This is an inference from adjacent research, not an established Medicare segment or a validated market size. **Age alone is not a supported way to identify this need.** Familiarity with Medicare, difficulty expressing circumstances in a form, comfort with digital tools and reading/typing burden are more useful dimensions to investigate; none becomes a new mandatory intake or eligibility gate.

The audience hypothesis to test is:

> **For some independent Medicare researchers, directed conversation reduces the effort of expressing their circumstances and understanding relevant tradeoffs, while preserving accuracy and control.**

### Evidence for conversation and its limits

Research reviewed October 30, 2026, following the owner's request to incorporate these findings. **There is credible evidence that conversation can outperform forms for some users and tasks.** It supports testing Daylight's hypothesis; it does not establish that textual LLM chat will outperform an excellent adaptive form for Medicare decisions.

| Evidence | Finding | What it supports and its limit |
| --- | --- | --- |
| **Health information search — randomized trial, 89 participants.** [Bickmore et al., 2016](https://www.jmir.org/2016/1/e1/). | On a specified clinical-trial search task, **5/14 (36%)** in the low-health-literacy agent subgroup found a correct trial, versus **0/8** using the conventional interface. The overall correct-trial difference was not statistically significant. | Guided interaction may help users who struggle with domain terminology. The subgroup was small, and the agent spoke through an animated character with selectable responses. This does not isolate free-text chat, LLMs or an excellent adaptive form. |
| **Survey participation — randomized experiment with Philippine K–12 teachers.** [Beam, 2023, author-hosted full paper](https://eabeam.github.io/assets/pdf/Beam2023_JDE_SocialMedia.pdf). | Completion conditional on clicking the recruitment advertisement was **48% with chat versus 29% with a web form**. Among those who consented, completion was **76% versus 74%**, not significantly different. Chat took longer. | Supports an advantage in getting people into the survey in this setting, rather than a general claim of substantially better persistence after starting. Does not establish comprehension or decision quality. |
| **Health intake — 206 participants completed both interfaces.** [Soni et al., 2022](https://www.frontiersin.org/journals/digital-health/articles/10.3389/fdgth.2022.954069/full). | **69.9% preferred the chatbot**, despite longer completion time. Its System Usability Scale score was not significantly better. | Some people may value conversation despite slower completion. This was a crowdsourced sample, not a Medicare cohort; authors disclosed employment, ownership or leadership interests in companies connected with the technology. Preference does not establish better decisions. |
| **AI interviewing — randomized experiment, 1,800 participants.** [Barari et al., 2026](https://ojs.ub.uni-konstanz.de/srm/article/view/8624). | Adaptive probes elicited more specific and explanatory answers. Elaboration/relevance probing increased average interview time from about **3 to 6 minutes**, with some deterioration in reported experience. Fuller responses did not consistently add new concepts. | Supports adaptive clarification as a possible mechanism, with a burden tradeoff. All conditions used a chat interface: this tests probing, not chat versus forms. More detail alone does not establish more consequential information or consumer understanding. |
| **Repeated survey use — two-week longitudinal study.** [Zarouali et al., 2024, university-hosted full paper](https://pure.uva.nl/ws/files/181581126/Comparing_Chatbots_and_Online_Surveys_for_Longitudinal_Data_Collection.pdf). | Web surveys often produced better response characteristics and data quality. Users rated chat less favorably for enjoyment, usefulness and security. | Counterevidence to a general conversational advantage. This was survey administration rather than Medicare decision support, but it reinforces the need to measure performance rather than assume chat presentation helps. |

**The evidence is mixed, and the measures are different.** Participation, preference, answer detail, search success and decision understanding cannot be treated as interchangeable proof. The cited studies do not establish which of Daylight's three proposed interface conditions works best for Medicare. The proposed audience and clarification mechanism are inferences to validate, not findings that these papers established for Medicare. The hybrid condition below is an owner-requested addition to Daylight's proposed study, not a result attributed to these papers or proof of an enterprise-wide adoption trend.

### Two hypotheses to test separately

| Hypothesis | Comparison that isolates it | What would count as useful evidence |
| --- | --- | --- |
| **Which interaction makes the experience easier?** | Three conditions: **A — excellent adaptive form; B — directed textual LLM conversation; C — hybrid conversation with inline mini-forms**. Use the same underlying evidence, supported research capabilities, tasks and comparable participants. Match explanation access, validation, correction and pre-action review standards. | Better comprehension, fewer consequential omissions or misunderstandings, successful correction, manageable effort and successful completion of supported work. Record active time, elapsed time, reading/typing/correction burden, abandonment and staff involvement. Preference is supporting evidence. |
| **Does deeper evidence improve the outcome?** | Basic versus richer research using the same interface and comparable tasks and participants. Record exactly which additional evidence or checks differ. | A consequential conclusion or next action changes, an explanation becomes materially clearer or better supported, or useful research is completed that the person would otherwise perform. Report errors, unresolved checks, consumer effort and maintenance/support cost. |

Keep the evidence fixed when testing the interaction, and the interface fixed when testing evidence depth. Better results from a conversation backed by richer data cannot establish that conversation itself caused the improvement. These are research comparisons within supported scope, not permission to omit required checks from a released service.

#### Three interface conditions

| Condition | How it works | What the comparison tests |
| --- | --- | --- |
| **A — Excellent adaptive form** | Purposeful structured fields, adaptive follow-ups, contextual explanations, visible validation and easy review/editing. Reuse known facts and provide the same supported research tools as the other conditions. | Whether a well-designed structured experience already meets the need with less effort. |
| **B — Directed textual LLM conversation** | A text-led exchange gathers and clarifies circumstances, teaches in context and summarizes interpretations. Capture relies on conversation rather than inline multi-field forms; explicit review and confirmation controls remain available. | Whether expressing circumstances and resolving ambiguity through directed text improves understanding or reduces effort. |
| **C — Hybrid conversation and inline mini-forms** | Conversation establishes the goal and clarifies context. When several related structured values are needed, show a compact inline form, often **3–5 fields**, followed by a conversational summary, review/editing and explicit confirmation before an authorized action executes. | Whether conversation's guidance plus structured capture reduces typing, omissions or correction work compared with A and B. |

The owner describes Daylight's current direction as already partly hybrid, making C a relevant condition rather than an afterthought. This description is not a fresh audit that the complete pattern is implemented. Three conditions belong to the interaction experiment; evidence depth remains the second, separate hypothesis.

#### Hybrid capture, review and confirmation

The intended research condition follows this sequence:

1. **Open with the person's task.** Invite them to describe what they want to do, then clarify only consequential ambiguity.
2. **Capture structured details inline when useful.** Group related missing fields in a mini-form. Three to five fields is a useful example, not a quota or another universal questionnaire. Reuse known facts and make suggested or auto-filled values visible and editable.
3. **After the form is submitted, show what was captured.** Submission stages inputs for review; it does not execute the downstream action. Summarize material values and distinguish what the person entered from any AI interpretation or suggestion. Offer explicit editing without restarting or losing other answers.
4. **Confirm the named action, then execute only that authorized action.** The review-and-confirm step happens **after form submission and before workflow execution**. Use an action-specific control such as “Run this comparison” where supported, alongside “Make edits,” rather than an ambiguous “Submit.” Confirming an interpretation is distinct from authorizing enrollment, sharing data or another consequential action. Changed inputs require the affected summary/result to be updated before acting.

The purpose is **trust and error recovery**: people can see what the system understood, correct mistakes and control the next action. Whether this increases trust, confidence, adoption or decision quality is something to measure, not an established result for Daylight. This is not a new confirmation turn after every message or a requirement to reconfirm unchanged facts.

For a fair comparison, **all three conditions must offer equivalent opportunities to review, edit and confirm before comparable consequential actions**, with the same evidence, tools, access to known facts and validation rules. Give A useful explanations and adaptive follow-ups. A benefit from adding a review checkpoint only to C would not isolate the benefit of the hybrid interface. Measure errors remaining after capture and after review, successful edits without restart, incorrect confirmations and the effort added by review as well as the existing outcome measures. Use supported or clearly simulated actions within the existing release boundaries.

Compare results across the hypothesized need for clarification, Medicare familiarity and digital comfort rather than treating all older adults as one audience. Observe whether people can identify and successfully correct an incorrect interpretation, not just agree with a proposed summary. Longer answers and higher completion or preference are useful observations, but stronger proof is better understanding and sound completed work with manageable effort. These are research measures, not a new consumer quiz or readiness requirement.

Directed conversation could help people express ambiguous circumstances, uncover consequential context they did not know to mention, receive explanations suited to their understanding and delegate research. It could also add reading, typing, repetition, latency or false confidence. An adaptive form may be faster or clearer for some tasks. Those are competing hypotheses to observe, not conclusions already established by choosing an AI-native operating model.

The product ambition remains useful whichever condition performs best for a task or audience. Use the findings to improve the interaction rather than defending chat or hybrid presentation as an end in itself. Existing visual teaching, explicit controls and inspectable comparisons remain available under the applicable design contracts; this ambition does not mandate an all-chat interface or authorize a flow change.

## Source and status

This is a paraphrased synthesis of the owner's October 25 attachment, **Pasted text(1).txt**, Library ID `libfile_363b065cedd88191813a6fcdeabb68f4`, and the instruction to incorporate its thesis into future UI and system work. It is not a verbatim archival copy. The attachment is strategic source material, not evidence of shipped capabilities, legal conclusions, competitor behavior or achieved outcomes. No external references were checked for the original October 25 synthesis. The [October 30 research addition](#evidence-for-conversation-and-its-limits) checks the five linked primary papers and preserves their methods, findings and limits separately from Daylight-specific inferences.

The October 30 central ambition above records the owner's explicit endorsement of the product proposition, consumer value of depth, same-plan value, starting audience and two separate experiments. It builds on [the product purpose](../../PRODUCT.md#product-purpose), [D64 principles](../../PRINCIPLES.md), [D73 requirements](../../DAYLIGHT_REQUIREMENTS.md#strategic-thesis-and-consumer-proof--d73--october-25-2026), the [master design](MASTER_DESIGN.md), [shortest sufficient conversation](SHORTEST_SUFFICIENT_CONVERSATION.md) and [15-layer guide](../scale/GUIDE.md). It establishes high-level ambition and evaluation direction, not demonstrated consumer demand or a new implementation/release approval.

The subsequent October 30 owner direction adds [hybrid conversation and structured capture as condition C](#three-interface-conditions), including review after mini-form submission and confirmation before execution. It expands the proposed interaction study, not the claims of the cited research or the authorized runtime scope. The dated copy is refreshed to include this direction; the undated file remains canonical.

Distinguish four things in every proposal and completion report: binding principles; hypotheses to test; current implementation with dated evidence; and a gated next milestone or later roadmap. A strategic ambition cannot promote data, release recommendations or authorize implementation by itself. Older execution plans remain useful within their scope and yield to current owner requirements and this strategy on strategic direction.

## Thesis and first audience

Build a **free, directly used Medicare decision platform**, funded through a licensed brokerage and distributed through trusted partners. The intended relationship spans initial exploration, comparison and, when authorized and operationally supported, enrollment; automated coverage reviews then help maintain a continuing relationship. The proposition to prove is that consumers can make informed decisions with less staff involvement while retaining control, inspecting recommendations and receiving sound support. Economics must work without degrading recommendation quality.

The strongest initial audience to test is first-time Medicare decision makers researching independently without a trusted agent, especially when employer coverage or family circumstances make the decision feel consequential. Adult children helping a parent are another promising audience to investigate. Urgency, preference and reachable market size remain hypotheses. Existing members and caregivers remain supported audiences; this focus does not discard either local variant or useful existing paths. Evaluate Original Medicare, optional Medigap and separate Part D, and Medicare Advantage comprehensively. **Understand and compare coverage paths before selecting individual policies.** A low premium or a single preference cannot settle that choice.

**Owner audience clarification · October 28, 2026 · D73:** The primary audience is people who do not have an agent and may be researching Medicare on their own. Competing for people who already like their agent is not the acquisition objective. Evaluate Daylight against the target person's actual independent research process and available self-service tools; a good agent remains a useful quality benchmark. No-agent status alone does not establish unmet need, urgency or product preference. Specific urgent subsegments and a substantially better research-to-decision experience remain hypotheses to validate with real users. This clarification does not exclude existing supported audiences or authorize new implementation, personal recommendations or changes to evidence/release gates.

**Owner operating-model clarification · October 30, 2026 · D73:** The intended business is an AI-native, self-service digital brokerage that minimizes human involvement. Adaptive AI conversation should investigate consequential circumstances at the depth a capable agent would, help the person understand options and tradeoffs, and complete supported work; receiving a plan recommendation is one possible output. Human staff support the service and necessary exceptions rather than serving as the default consumer journey. The Pocket Protector is the owner's closer product reference; Healthpilot is less aligned with the envisioned experience. The specific market hypothesis is people who need more contextual assessment or explanation than a straightforward questionnaire provides but prefer virtual self-service and self-discovery. The prevalence of that need, preference for AI, competitor assessment depth and comparative quality/staff-effort advantage remain research questions, not established findings. This clarification authorizes no runtime change, new unsupported capability, reduced source work or release-gate bypass.

The differentiation to demonstrate is useful work people can complete themselves and understanding they can retain: gathering consequential facts, exploring tradeoffs, preparing a decision and completing supported actions. Chat, AI branding and assertions of being unbiased are insufficient evidence. Keep the accepted landing, sun/name, sole tagline **Your coverage, plain as day**, visual teaching and simple adaptive conversation; this thesis is not replacement landing copy or permission to redesign navigation.

## Data quality and geographic scale

**Owner-requested guide · October 29, 2026 · D73:** [Data quality, the 15 layers and national scale](../scale/GUIDE.md) preserves the scalability assessment in a dedicated [scale folder](../scale/README.md) and examines competitive advantage beyond the five largely reusable national layers (L01, L02, L04, L09, L13). The assessment is that verified integration of benefits, drug conditions, provider networks, Medigap/state rules and personal circumstances could make self-service research more useful and maintenance more economical. Public data access alone does not establish exclusivity; complete conditions, exact identities/periods, provenance, reliable updates, honest gaps, independence and understandable decisions are the capabilities to prove.

This is a strategic hypothesis, not an achieved competitive advantage, a comparative competitor audit or an approval of national rollout. Apply the [consumer value test for depth](#depth-should-make-the-tool-simpler) and isolate it from the [interaction experiment](#two-hypotheses-to-test-separately). Validate it through material accuracy/completeness, consumer understanding/control, actual staff and maintenance costs and repeatable geographic expansion under the cohort definitions below. Preserve full L03 comparison/review obligations and all source, privacy and exact-release gates. The current chat-by-chat workflow must evolve into reusable collection, validation and refresh pipelines; the guide distinguishes public bulk files, APIs and optional supplier feeds without committing to purchases or personal pricing. Inventory counts describe evidence/comparison obligations, not verified facts or consumer benefit.

## Binding product and system commitments

1. **Let people ask questions before extensive personal intake.** Build and correct the profile progressively. Ask a fact because it can change the requested check, comparison or next action, and explain why. More data is not automatically better. Reuse confirmed reports, distinguish explicit none from unknown/deferred, and do not turn the alternative's question inventory into a mandatory interview.
2. **Make tradeoffs revisable and understandable.** Compare costs, provider access, restrictions and future flexibility on consistent evidence and assumptions. Let people change priorities, revisit comparisons, correct facts, challenge a conclusion and inspect its supporting evidence. Preserve current coverage as a baseline. Retaining coverage or deferring with an explicit unresolved check can be a valid outcome.
3. **Make independence testable.** Full-market coverage is an ambition; actual geography, year, categories, included records, exclusions, source dates, assumptions and uncertainty must be disclosed. Include nonrevenue options without penalties. Commissions, sponsorship and partner preferences cannot enter ingestion selection, eligibility, ranking, explanation or the AI context. Apply [I01–I10](INDEPENDENCE_ACCEPTANCE.md), including economics counterfactuals and missing-data neutrality; disclosure alone does not establish independence.
4. **Keep an inspectable decision record.** Before releasing recommendations, preserve the minimized, permissioned inputs and evidence/version identifiers, candidate universe, exclusions, rationale and unresolved checks needed to reproduce and challenge them. Provide independent quality review. Audit human overrides with actor, before/after decision, evidence, reason and review outcome; an override cannot bypass required evidence or quietly favor commercial fulfillment. A saved explanation does not authorize retaining raw health chat or every sensitive fact.
5. **Keep control and permission specific.** Save/resume must reflect actual storage receipts and retention policy. Family participation requires appropriate permission and scoped sharing; a caregiver label is not sharing authority. Saving, AI transfer, family sharing and human handoff are separate choices. Do not promise household accounts or cross-device sharing from a same-browser guest profile.
6. **Use automation where it is reliable.** Automate information gathering, comparison, explanation and preparation only within reviewed rules and verified tool capabilities. Licensed professionals handle required involvement and exceptions through an actually supported service. Offer human help when useful without withholding otherwise supported self-service research or requiring a sales call. Legal/operational requirements need separate review; this is not a finding about which activities require a license.
7. **Make economics fit neutral decisions.** Test commercial viability across the recommendation mix, including no-commission choices, keeping coverage and deferral. Revenue and support analysis stays outside recommendation features, prompts, model selection, training objectives and evaluation labels. Poor economics calls for operational or business-model changes, not steering toward a paying carrier or suppressing an option.

## Current implementation and protected variants

This is a documentation snapshot based on existing local contracts, not a fresh runtime certification. The original app at **:8890** lives in `/Users/cep4u/daylight`, with the ten-question frontend in `cms-slice/apps/ten-question/`. [The ten-question contract](TEN_QUESTION_CONTRACT.md) and [conversational readiness contract](READINESS_CONVERSATION.md) record the accepted sequence, editable summary and optional conversation/sample boundary. The preserved `apps/chat` previous guide on :8896 is distinct from the :8891 alternative.

The **:8891 alternative** has editable source at [/Users/cep4u/daylight/alternatives/chat-first](/Users/cep4u/daylight/alternatives/chat-first) and its preserved separate runtime at `/Users/cep4u/daylight-chat-alternative-runtime`. D75 brought the canonical source into this repository without merging either UI or moving data; see [source/update/rollback instructions](../../alternatives/chat-first/README.md). The old Documents source remains a noncanonical fallback. Its [customer-profile readiness contract](/Users/cep4u/daylight/alternatives/chat-first/docs/product/CUSTOMER_PROFILE_READINESS.md) and [question map](/Users/cep4u/daylight/alternatives/chat-first/docs/product/CUSTOMER_PROFILE_QUESTION_MAP.md) describe 38 primary plus 3 explicit child questions, with overlapping clarification variants. That inventory is conditional capability preparation, not a fixed required question count. Neither variant is abandoned. A small alternative agent pointer references this canonical strategy; it does not synchronize code, profiles or runtime files.

Existing documentation records local AI, permissioned same-browser guest saving, reported-input preparation and a labeled five-record sample subset. Those records do **not** establish a complete market, a validated recommendation engine, exact provider/drug coverage, personalized pricing, Medigap quotes, enrollment or ongoing review operations. Existing acceptance holds and source-review limitations remain. Preserve both variants' guest records, existing consent and shared aggregate budget controls; no strategy edit migrates data or changes a service.

### Customer completeness and external verification are independent gates

| Boundary | Required meaning | What cannot satisfy it |
| --- | --- | --- |
| Reported inputs for a requested capability | Relevant consequential facts are present, confirmed as reports and current; missing, tentative, unknown and deferred stay explicit. Optional preferences are not universal requirements. | Finishing ten screens, a zero queue/count, all-unknown answers, an AI assertion or a client completion flag. |
| External evidence and release acceptance | Exact source/entity/year/location, policy review, coverage scope, network/formulary/pricing and comparison acceptance required by that capability. | A complete customer profile, a name match, a captured dataset, research references or a staff override without required evidence. |
| Sample browsing | Explicit, honestly labeled exploration with scope and limitations. It can remain available without complete personal intake. | Personal fit, ranking, a verified price or authorization to enroll. |

**Ten unknown answers cannot earn a personalized recommendation. Complete reported inputs cannot remove an external hold. A missing external source is not another intake question. Sample browsing is not a recommendation.** Readiness is specific to the requested capability, not a global badge. Changed facts or evidence invalidate affected results while preserving the person's prior reports for review under the existing privacy policy.

## Roadmap: proof before expansion

These are strategic stages and dependencies, not a new approved implementation schedule. No numeric targets or achieved results are asserted.

| Stage | Work and evidence | Gate / limit |
| --- | --- | --- |
| Current prototype | Preserve both local variants, accepted teaching/chat, editable reports, guest privacy and labeled samples. State unresolved personal pricing, matching and market-data gaps. | Technical checks and documented intent are not consumer, legal or data acceptance. |
| Next milestone: scoped consumer proof | Define a first-time-user cohort, requested capabilities, market/year, comparison baseline and acquisition channel. Close and independently accept the exact data/policy/capability gaps needed for that scope; then observe informed decisions, correction/control and staff effort. Exercise economic independence across compensated, uncompensated, keep and defer outcomes. | While external gates remain held, limit work to education, input preparation and labeled samples. Any actual recommendation or enrollment requires its own evidence, authorization and qualified operations. |
| Repeatable acquisition and licensed fulfillment | Test referrals and trusted retirement advisers, employers, benefits platforms and community partners. The partner introduces the member; Daylight maintains the permissioned profile and continuing relationship. Measure completion, support burden and contribution by cohort/channel. | Partner attribution/preferences do not influence recommendations. Brokerage, human escalation and enrollment promises require actual reviewed capability and permission. |
| Continuing coverage reviews | Initially reuse proven profile/evidence infrastructure for coverage changes, medication updates, deadlines and routine notices. Make each check's source date, permission and remaining work visible. | Reliable data refresh, authorized outreach, privacy/retention and exception ownership must exist before promising automation. No recurring task is created here. |
| Later expansion | Add labor-intensive advocacy only after funding and service costs are established. Consider selective government deployments after consumer proof. | Do not divert the first milestone into broad government sales or an unfunded advocacy commitment. |

Defensibility should accumulate in versioned coverage/eligibility evidence, verified provider and drug identities/coverage, reproducible comparisons, permissioned history, reliable integrations/distribution, quality evidence and efficient exception handling. An LLM interface alone does not create that asset. Evidence retention remains purposeful and access-controlled rather than a reason to collect everything.

## Evidence definitions for the first cohort

Before measurement, record cohort eligibility, scope/year, channel, observation window, denominator, baseline/comparator, policy/model/data versions, reviewer and missing observations. Use appropriate permission and minimized records; no private transcript collection is implied. Report exclusions, failures and uncertainty alongside rates. Set decision thresholds explicitly when designing the study; this document invents no targets, traction or results.

Use these measures for the [two separate hypotheses](#two-hypotheses-to-test-separately): interaction quality with evidence held fixed, and evidence value with the interface held fixed. Record same-plan outcomes as potentially successful when independently supported understanding, effort or completed work improves; neither switching nor confidence alone demonstrates value.

Report interaction outcomes separately for [A, B and C](#three-interface-conditions). For comparable actions, record errors before and after review, successful correction without restart, incorrect confirmations and the burden of reaching a confirmed action, alongside comprehension and completion. Shared confirmation standards are part of the comparison design, not an advantage reserved for the hybrid condition.

The [audience insight and research](#strongest-starting-audience) further distinguish comprehension, consequential omissions, successful correction, effort and completion from preference, confidence and answer length. Record relevant participant/task differences and failed or abandoned sessions; do not infer benefit from age or from outcomes among completers alone.

| Measure | Evidence definition |
| --- | --- |
| Accuracy and independence | Independently adjudicated material claims/decisions against exact scoped source evidence; report reviewed count, errors by severity, unresolved claims and corrections. Include I01–I10 results and override audit. Do not count unreviewed statements as accurate. |
| Comprehension and control | Observed ability to explain the chosen coverage path and key tradeoffs/uncertainty, inspect a reason and correct an input. Record task rubric, observer, eligible/observed counts and failures; stated confidence or chat satisfaction alone is insufficient. Observation does not impose a new consumer quiz gate. |
| Enrollment completion | Where enrollment is separately authorized and supported, distinguish preference, application started/submitted, accepted and effective coverage with actual receipts/status. Report denominators and pending/failed outcomes. Keeping/deferring is separately classified, not mislabeled as failed enrollment. |
| Staff minutes per outcome | Measured licensed and nonlicensed time for preparation, escalation, support, exceptions and rework, including unsuccessful cases. Report distributions and comparable baseline for the same scope; automated reply counts are not labor savings. |
| Contribution after acquisition and support | Realized revenue with relevant reversals, less attributable acquisition, AI/data, fulfillment, staff and ongoing support costs for the cohort/window. Report neutral outcome mix and allocation assumptions, including zero-revenue outcomes; do not substitute gross commissions or forecast LTV for measured contribution. |
| Retention and continuing value | Among members eligible for follow-up with permission, measure return/use and completed supported reviews over a stated window, plus unresolved work and support cost. An undeleted saved profile does not establish retention. |
| Repeatable acquisition | Record channel/referral source, eligible arrivals, informed-decision outcomes and acquisition effort/cost across repeated cohorts. State selection bias and limits; one favorable demonstration does not establish repeatability. |

Seed evidence means a cohort demonstrating informed decisions with lower staff minutes through a repeatable acquisition route, supported by accuracy, comprehension, completion, contribution and retention evidence. This remains a hypothesis to test, not a financing or performance claim.

## UI and system change review checklist

Every future UI/system proposal and completion report must address the applicable items, name requirement IDs (including D73 where relevant), and give evidence or an explicit unresolved status. A small change can say why an item is unaffected; it cannot silently weaken the boundary.

- [ ] **Consumer task:** What useful work or understanding improves for the initial audience? Does the change preserve the accepted landing, teaching, simple adaptive chat, correction and return paths?
- [ ] **Consequential intake:** Why can each requested fact change this capability's result? Can the person ask/learn/browse before extensive intake? Are optional, none, unknown/deferred and repeated reports handled distinctly without a second mandatory questionnaire?
- [ ] **Coverage path and tradeoffs:** Are Original/Medigap/Part D and Advantage represented fairly before policy selection, with costs, access, restrictions, future flexibility and a current-coverage/keep baseline where relevant?
- [ ] **Two gates and honest scope:** Which reported inputs suffice, and which independent source/release holds remain? Do all-unknown, stale and incomplete cases fail closed for personal recommendations while explicit sample browsing stays accurately labeled?
- [ ] **Independence and challenge:** Could any commercial/partner input change inclusion, ordering, explanation or next research work? Where are source dates, exclusions, assumptions, reproducible reasons, user challenge/correction and independent/override review evidenced?
- [ ] **Permission and control:** What is saved, transferred to AI, shared with family or handed to a human; under which separate permission, access and retention policy? Does the implementation preserve both variants' actual guest data and privacy/budget controls?
- [ ] **Actual capability:** What did the tool/service really execute? Distinguish reported from verified, prepared from sent, sample from recommendation, submitted from accepted/effective coverage. Keep required licensed help and unsupported operations explicit.
- [ ] **Proof and stage:** Which cohort measure or prerequisite improves? Identify current evidence, limits and next milestone; assess economics outside decision logic across neutral outcomes. Do not claim comprehension, savings, complete coverage or readiness from documentation or test totals alone.

## Owner-supplied reference links

Preserved as references supplied with the thesis, **not freshly verified sources or adopted legal/competitive findings**. Recheck the relevant primary source and obtain required domain review before using a claim in consumer advice, rules or marketing. Competitor marketing does not prove internal product behavior or independence.

- [Medicare.gov: ready to buy Medigap](https://www.medicare.gov/health-drug-plans/medigap/ready-to-buy)
- [Chapter: comparison with other Medicare agents](https://askchapter.org/magazine/chapter-and-you/medicare-resources/chapter-vs-other-medicare-agents)
- [CMS: agent/broker compensation](https://www.cms.gov/medicare/health-drug-plans/managed-care-marketing/medicare-marketing-guidelines/agent-broker-compensation)
- [Chapter partnerships](https://askchapter.org/partnerships)
