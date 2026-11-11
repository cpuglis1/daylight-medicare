# A useful, honest demo for a Naples resident in ZIP 34102

> Superseded as a scope target by [Naples MVP](NAPLES_MVP.md). Retained as the earlier demo assessment; live chat and the 70-record catalog have since been implemented.

Assessment: October 18, 2026. The immediate target is a facilitated, session-only exploration of 2027 coverage with a resident, using captured source evidence and a live conversational model. The resident should leave with a clear comparison and a list of remaining checks. Enrollment, personal quote delivery and an automated suitability verdict are separate capabilities.

## What exists now

The current release contains real normalized plan records, not just collected web pages. The Collier County catalog has 70 captured records. Its supported comparison scope is 38: 20 Medicare Advantage plans with Part D, 7 Advantage plans without Part D, and 11 standalone Part D plans. The remaining 27 SNP and 5 Regional PPO records are preserved with scope exclusions. An exclusion does not determine a resident's eligibility.

Plan identities include contract, plan, segment and year. Published premiums, Part D deductibles and medical out-of-pocket limits retain source cells and source hashes. All 96 applicable selected monetary fields across the 38 records were checked against the recorded Medicare.gov observations; an additional carrier-document sample covers 16 records across three parent organizations. That validates selected published fields, not all benefits or personal costs.

The source package also includes exact medicine vocabulary choices, pharmacy identity/location choices, formulary restriction queries, multi-product queries, dated pharmacy-network rows, and NCH/Physicians Regional notices. The source engine can already return all supported options, inspect an exact plan and compare exact drug products across plans. The earlier research view supports comparing up to three selected plans. These capabilities need a clearer bridge into the new consumer chat.

The opening UI now has the coverage intake and two educational coverage paths. Its discussion uses a scrolling transcript with a stationary title and reply box. The optional model adapter currently chooses prepared question topics and selects source facts. It does not yet produce a freely phrased, context-sensitive conversation. No live model account is configured in the server environment.

## What is missing in the product connection

- Entering 34102 currently stores a ZIP; it does not resolve or confirm a person's county. The existing Medicare.gov observation URLs use ZIP 34102 with Collier FIPS 12021. For the bounded demo, explicitly confirm Collier County and coverage year 2027, rather than implying support for every ZIP or year.
- Hearing, vision and dental preferences are collected, but do not currently filter a comparison against validated benefit fields. They should remain stated priorities until those specific SB/EOC benefits and conditions are supported.
- Follow-ups retain only the last 16 messages, and the browser has one selected medicine and one pharmacy. A resident's actual needs require a confirmed list of medicines, current coverage, providers, cost preferences, timing and travel that survives a longer conversation.
- A plan listing is currently a series of source paragraphs inside a disclosure. It needs structured plan cards and a small comparison the resident can use, with exact plan identities, explicit ordering, full results and exclusions available.
- Selecting one of the two coverage paths opens education; it does not currently create a comparison of compatible coverage structures or obtain a Medigap quote.

## The live model integration

Keep the existing Python server and Responses adapter. Supply `OPENAI_API_KEY` and `OPENAI_MODEL` through the server environment; `.env.example` is documentation and is not automatically loaded. Keep the key on the server. Do not paste it into the UI, a transcript, source control or client JavaScript.

Add a conversational response contract that permits a natural acknowledgment and one relevant next question, backed by a confirmed session profile and recent dialogue. Keep plan facts in a separate structured part of the response. The model can choose tools, explain available evidence, recognize when a person supplied several details at once, ask for ambiguity to be resolved and follow the person's questions. The data engine controls plan identities, monetary values, product matches, comparison ordering and source limits.

Reuse the existing tools: `market_options`, `plan_details`, `plan_candidates`, `medicine_candidates`, `pharmacy_candidates`, `drug_evidence`, `drug_list_evidence`, `provider_evidence` and `education`. Add a bounded comparison tool around the existing comparison capability and a session-profile update/confirmation contract. Never infer an exact strength, pharmacy branch, clinician network match or purchase authorization from casual language.

Render plan cards directly from returned structured records. A model-written explanation should cite the returned evidence and preserve limitations; a citation alone is not a factuality test. Test the actual model on public cases for grounding, omissions, unsupported certainty, ambiguity, prompt injection, repeated questions, corrected details, long conversations and account/network errors. Use the existing guided fallback if the live account is unavailable. Add streaming after the response/data contract is working if latency warrants it; verified plan fields should not appear as speculative partial tokens.

The current adapter uses `store: false`. That setting is not a complete privacy assessment. Before a resident enters personal health details, make the actual model recipient, data scope and session handling understandable and confirm the selected account's data controls. The first facilitated demonstration can use public examples for the detailed medicine/provider exercises.

Official references: [Responses function calling](https://developers.openai.com/api/docs/guides/function-calling), [conversation state](https://developers.openai.com/api/docs/guides/conversation-state), [structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses).

## How to surface the captured options

1. Confirm **34102 → Collier County → 2027** with the resident. If the county or year changes, stop applying this fixed catalog to their case.
2. Ask whether to explore the general coverage paths, Advantage plans or standalone drug plans. Explain the relationship among coverage types before comparing incompatible combinations.
3. Retrieve the complete supported source set for the explicitly chosen category. Show a count, source date and scope. Use source identity order initially; label any later user-chosen sort accurately.
4. Show readable cards with plan name, type, exact year/ID and published monthly plan premium. Show medical spending limit and drug deductible when applicable. Distinguish an inapplicable field, an unknown field and zero. Preserve other Medicare obligations and plan-condition notes.
5. Let the resident select two or three plans to compare. Retain source links and the complete option set; do not treat the first few cards as a personal recommendation.
6. Add the confirmed medicine list and exact pharmacy to this comparison, showing formulary tier/restrictions, dated store evidence and unresolved details. A formulary listing does not prove approval, a personal fill price or annual cost.
7. Show provider evidence separately: exact plan/year, clinician or facility, address and checked date. A local insurer-level hospital notice does not resolve the treating clinician's participation.
8. End with a useful handoff: what the resident said matters, the plans they inspected, the factual differences, sources/dates and the questions still needing verification. The next human should not have to repeat intake.

For reference, [Medicare's official tools](https://www.medicare.gov/basics/get-started-with-medicare/using-medicare/helpful-tools) separately support plan comparison, medicine-based cost estimates and Medigap search. Our captured source package supports only the specific pieces listed above.

## Remaining evidence boundaries

| Resident's question | Can support today | What must be added for a stronger answer |
| --- | --- | --- |
| “What plans are in the captured local set?” | Full supported Collier 2027 source set with exclusions disclosed | ZIP/county/year confirmation and in-chat plan presentation |
| “How do these plans differ?” | Published premium, drug deductible, medical limit and selected qualified visit summaries | More SB/EOC fields only for benefits the conversation actually discusses |
| “Do they list my prescriptions?” | Exact-product formulary evidence, tiers and PA/ST/QL flags | Confirmed full medicine list; quantity/package interpretation and broader exception/absence cases |
| “What will my medicines cost?” | Published plan premium and some restriction context | Year-correct price data, exact product/quantity/days/store, applicable cost assumptions and validated estimates |
| “Can I keep this doctor?” | Dated local notices and identity/location research | Exact clinician/facility + location + plan/network/year verification, including conflict/currentness handling; a reviewed manual check is practical for a small demo |
| “What does Medigap cost me?” | General education and published illustrative source scope | Authorized actual quote payloads, applicant assumptions and conditions |
| “Which is best for me?” | Explain factual differences and what remains unknown | Confirmed criteria, supported costs/provider/drug evidence and a reviewed, reproducible comparison/ranking method |

Source review and qualified interpretation remain open in the existing project audit. Refresh relevant notices before the session and have a Medicare domain reviewer check the small set of claims used. Rebuilding captured bytes does not renew their review dates. No new supplier access, domain approval, resident consent or successful live-model result is claimed by this plan.

## Smallest useful next implementation

The next build should combine: (1) the natural model conversation and confirmed in-tab profile, (2) explicit Collier/2027 confirmation, (3) structured browsing and comparison of the existing records, and (4) a reviewed exact medicine/provider example. Then run the whole sequence with a facilitator and observe whether a person understands premium versus total cost, listing versus approval, and unresolved versus no coverage.

This is a focused integration effort because the local data and query tools exist. A reasonable planning estimate is several engineering days for the model/profile/catalog connection and live case evaluation once a usable account is supplied; the exact provider and personal pricing gaps depend on obtaining and reviewing real evidence. This estimate is not an implementation commitment or a claim that those external dependencies can be closed on that schedule.

For an in-person demo, the existing local server is enough. For a remote resident, add a private HTTPS deployment, server-side secrets, bounded sessions and explicit personal-data handling; the current server intentionally accepts loopback hosts/origins only. Publishing the existing loopback app unchanged would not provide a usable remote demo.

## Acceptance walkthrough

A person enters 34102, confirms Collier/2027, completes the short intake and sees the two opening paths. They can say “I want to keep my doctors and I take these two medicines” without being forced through unrelated repeated questions. The conversation resolves ambiguous products/locations, displays actual captured plan records and compares plans they choose. It answers a published-plan question with traceable data, and says what evidence is missing for a personal price or exact doctor check. The conversation can be scrolled while the reply box stays visible, and failure of the live account leaves the session usable. The facilitator records actual misunderstandings and corrections.
