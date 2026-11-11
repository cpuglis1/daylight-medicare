# Naples Medicare MVP

Updated October 18, 2026. This is the active product direction, replacing the earlier facilitated-demo target. The objective is a useful, unbiased research and comparison tool for people in Naples, Florida, with live model conversation, complete local plan coverage, transparent prices and explicit priority ordering. There is no saved customer profile: intake answers, dialogue and explicit selections exist only in the current browser tab/request.

> The current chat flow, request bounds and cost evaluation are in [Milkman chat implementation](MILKMAN_CHAT_IMPLEMENTATION.md) and the [before/after report](../cms-slice/reports/milkman-eval-after.md). The original groundwork below remains relevant; its intake and rendering descriptions are historical.

## Groundwork implemented in the original MVP

- Real model conversation through the server, with natural acknowledgments and follow-up questions, evidence tool calls and the current dialogue. It does not use the earlier canned-question router when live chat is connected.
- Actual account requests were exercised with `gpt-5.4`. The public/synthetic evaluation receipt is `cms-slice/reports/mvp-live-check.json`; all seven final cases completed. No resident data was used. This is a small smoke evaluation, not a general factuality or product acceptance result.
- The complete **captured** 2027 Collier catalog is exposed: **70 records = 23 MA-PD + 9 MA-only + 11 standalone PDP + 27 SNP**. The original supported subset was 38; all 32 previously excluded records now appear with landscape fields and explicit unresolved validation/eligibility notes.
- In-chat plan cards, category filters, numeric ordering by published monthly plan premium, medical spending limit and Part D deductible, and a comparison of two or three chosen plans.
- The person can select first and second priorities. The engine applies supported published fields in exactly that order; plan ID is the final tie-breaker. Commission/partner data is not an input. Unknown, inapplicable and conflicted values are not converted to zero. Unavailable priorities are named as **unscored**, not assigned invented match scores.
- The two existing inter-source SNP drug-premium discrepancies are preserved and marked unresolved in premium ordering. Both observed values remain visible. No source silently replaces another.
- Real medicine candidate selection, up to 15 explicit product selections within the conversation, and the existing exact-code evidence tools remain available. Exact provider participation and personal annual drug prices are not inferred.
- Local model settings can be read from an explicitly selected env file. The loader reads only `OPENAI_API_KEY` and `OPENAI_MODEL`, never sources shell code, and never includes credentials in the public release.
- 74 relevant automated tests passed, covering existing source/model boundaries, live orchestration, complete catalog membership, deterministic priority ordering, source conflicts, HTTP behavior and portable packaging.

The original evidence adapter remains available for source inspection and controlled tests. The consumer UI uses `/api/live-chat` when the live account is configured. A configured live failure is shown as a failed live request; it is not silently presented as a successful model conversation backed by canned text. Public catalog browsing uses `/api/catalog` and remains independent of the model.

## What a person needs to provide

Ask progressively in the conversation. The person can browse without supplying health details, a name, a telephone number or a saved account.

| Desired result | Information from the person | Additional evidence the tool needs |
| --- | --- | --- |
| Browse local plans and sort published premiums | Residence county/ZIP and coverage year | Current complete market inventory and source dates |
| Compare particular plans | Plan IDs or selecting exact plan cards, plus priorities | Exact plan-year/segment fields and benefit conditions |
| Check prescriptions | Exact product/strength/form; quantity and refill days when cost is relevant; actual pharmacy branch or mail order | Formulary restrictions, exceptions, pharmacy participation, year-correct pricing and cost rules |
| Keep doctors/hospitals | Clinician/facility name and practice location; exact plan under consideration | Dated exact plan/network/year participation and conflict handling; hospital and treating clinicians checked separately |
| Order by the person's priorities | Explicit ordered preferences such as lower monthly cost, predictable medical exposure, medicines, doctors, travel or selected benefits | Actual evidence for every scored factor; reviewed cost/compatibility logic |
| Explore restricted SNPs | Only the relevant known eligibility facts, such as Medicaid status or the specific applicable eligibility group | Exact plan requirements and confirmation; an unknown is not a denial of eligibility |
| Review switching/timing | Current coverage and relevant effective dates, retirement/move timing and intended start | Current enrollment/compatibility rules for that situation |
| Obtain Medigap prices | Quote-specific applicant/rating inputs requested by the actual quoting source | Authorized current carrier/supplier quotes, underwriting/acceptance conditions and validity |

Medicare/SSN identifiers, payment details, medical documents and a retained customer profile are unnecessary for research browsing. Public examples are enough for development and model evaluation; the conversation can then ask a real person only for details needed to answer their immediate question.

## What “all plans, ranked, price and priority” requires to finish the MVP

**All local options.** Reconcile current CMS/Medicare.gov inventories for the resident's county/year with carriers and service areas, including SNPs and Regional PPOs. Retain captured records and conditional eligibility rather than dropping them because the initial comparison was narrower. Add the Medigap carrier/product/quote path, plus any other coverage programs claimed by the product. The current 70 records do not include Medigap quotes, PACE or employer plans and are not certified as the complete live market. Confirm county/year instead of treating a ZIP or postal city as proof of residence.

**Prices people can use.** Published premium ordering already works. An annual cost estimate additionally needs the person's exact medicines, quantities, refill days, pharmacy, relevant assistance and cost-sharing assumptions, plus a verified current-year pricing source. Medical estimates require explicit utilization scenarios and exact benefit conditions; a medical out-of-pocket limit is not expected annual spend. Medigap needs actual applicant-specific quotes. Never substitute a different year's prices or call a missing price zero.

**A real benefit matrix.** Parse and validate the SB/EOC fields people ask about: service-specific medical costs, network/out-of-network rules, referrals/prior authorization, dental, vision, hearing, allowances and geographic/travel conditions. The intake preferences alone cannot create those facts. Existing selected-field corroboration is useful but is not full-plan validation.

**Doctor and drug fit.** Resolve exact provider identity/location and exact product/store choices, capture dated source evidence, and expose positive, negative, stale, conflicting and unresolved states. Start with real high-demand Naples practices and hospitals and expand through observed requests. Existing public hospital/carrier notices do not certify an individual doctor's network status. Existing full drug evidence interpretation remains narrower than all 70 displayed landscape records; expand and independently verify it before treating those additional records as completely checked.

**Unbiased ranking.** Keep the complete result set. Apply the user's confirmed criteria with a published reproducible method; show components, assumptions, missing factors and reasons for ordering. Compare compatible coverage structures. Commission, insurer commercial relationships and referral payments cannot enter the ordering. Test correction of preferences, ties, missing values, source conflicts and commercial-metadata invariance. The implemented ordering is a foundation: it sorts supported published fields, and explicitly leaves provider/drug/benefit/annual-cost priorities unscored until their evidence and rules exist. It is not yet an overall personal suitability score.

**A maintained public product.** Add regular source refresh/diff review, clear source dates, qualified domain review of the actual consumer outputs, representative live-model evaluations and observable error handling. For remote Naples residents, deploy an HTTPS service with server-side credentials and rate/abuse limits; the present app intentionally accepts loopback hosts/origins. Keep user details transient as requested, with no account or persistent profile. Do not reuse this local-only server as an internet deployment unchanged.

## Conversation architecture

The server supplies the request's current intake answers, dialogue and explicit selections to the model. The model can request the complete catalog, a deterministic ordering, an exact plan, a selected comparison, medicine/store candidates, exact-product evidence, local provider notices and education. It returns conversational text and references to retrieved fact IDs. The app independently renders source-backed facts, product choices, complete plan cards and comparison values; the model does not author the price cells or rearrange engine results.

Tool-call names/arguments, selected identity permissions, output shape, fact identities and monetary/plan-identifier prose limits are checked server-side. Tool facts and limitations are retained rather than dropped by the model. A bounded correction request handles malformed final output before failing visibly. These checks reduce risks; they do not prove every sentence is factually correct. The initial weaker-model tests exposed output-contract failures and were not counted as successful evaluation of the final connected version.

The server stores no dialogue or profile, sends API requests with `store: false`, and does not create persistent Conversations API objects. This does not imply the external provider has zero retention under every account setting; the actual account's data controls still apply. In-browser history is bounded; starting over or refreshing removes the current local conversation.

## Running the connected app

From `cms-slice/`, use a local ignored env file that contains the OpenAI key and optionally the model setting. If the file contains only a key, select the tested model without putting the key in a shell argument:

```sh
OPENAI_MODEL=gpt-5.4 python3 scripts/demo.py serve --release current --env-file /absolute/path/to/local/.env
```

Open `http://127.0.0.1:8766/`. `/api/status` reports the configured model and live availability without exposing credentials. Use **Browse plans** for the complete captured catalog, or ask the live chat to show/sort/compare it. Changing the model is a server environment setting. Rebuild and verify the immutable release after runtime or UI edits.

## Primary references and local receipts

- [OpenAI function calling](https://developers.openai.com/api/docs/guides/function-calling), [conversation state](https://developers.openai.com/api/docs/guides/conversation-state), [GPT-5.4 capabilities](https://developers.openai.com/api/docs/models/gpt-5.4).
- [CMS 2027 PUF methodology](https://data.cms.gov/sites/default/files/2026-10/Methodology-PUF-2027.pdf): the eight published tables, exclusions and update/suppression limits. The PUF is not a complete personal drug-price quote service.
- [Medicare SNP information](https://www.medicare.gov/health-drug-plans/health-plans/your-health-plan-options/SNP): conditional eligibility and the role of these plans.
- `cms-slice/reports/mvp-live-check.json`: actual final-model public-case smoke results, latency, tool calls and code hashes.
- `cms-slice/reports/demo-quality.json`: existing selected monetary-field corroboration.
- `cms-slice/reports/work-package-3/`: existing prescription capture and source discrepancies.

The earlier demo documents remain historical context. They are not the current product-scope limit or an instruction to stop at a demo.
