# Plans workspace backend integration

November 5, 2026 · D92, D91, D86/D87, D64/D73 · :8893 only.

The in-app Plans workspace now receives the existing confirmed chat-profile receipt, reads all 72 exact retained 2026 Collier identities and connects selected/visible/comparison context to the existing advisor on deliberate Send. The frontend is intentionally a thin integration shell for the separate UI workstream. No new model stage, standalone chat, guest database, profile migration, commercial input or external action was added.

## Actual release state

| Dimension | Current result |
|---|---|
| Plan coverage | 72/72 exact retained identities, in original ID order; not a complete-market or verified-availability claim |
| Field preparation | 720 benefit cells and 288 fictional-example cells loaded from exact r13, including all material holds |
| Source/method acceptance | Pending. Existing consumer registry unchanged; additive scoped Plans receipt also pending |
| App access | Catalog, profile handoff, explicit priorities, deterministic decision result and contextual-chat APIs connected |
| Consumer publication | Zero benefit amounts released under the current receipt |
| Real recommendations | Zero supported now. The engine returns explicit source/method/personal-check holds |

The source is `docs/product/recommendation-scope-2026-11-04-r13/display-candidate.json`, SHA-256 `ba625a2968a53a46dc72dddf52a4e74064b56b0b14e55c9e8768d2b580fa3609`. Every operation verifies those bytes and the two immediate pinned input packets. The packet's 141 material-held benefit cells and 88 material-held examples never disclose an amount, even if a later receipt accidentally lists them as publishable. Pending source-purpose acceptance additionally suppresses the remaining amounts. Names, exact IDs, retained types and restriction labels describe the dated internal listing, not personal availability. The five Erickson restrictions remain visible.

## Backend interfaces for the UI workstream

All endpoints use the existing cookie owner, same-origin and CSRF checks, JSON request bodies and `Cache-Control: no-store`. Tokens and profiles do not belong in URLs, local/session storage or logs. Extra request fields are rejected.

| POST endpoint | Body | Response |
|---|---|---|
| `/api/plans/catalog` | `{}` | All retained identities, redacted/published cells, coverage counters, dated scope, projection/view digests; no personal recommendation |
| `/api/plans/handoff` | `{token}` | Existing current owner/visit/report-bound normalized profile handoff |
| `/api/plans/workspace` | `{token}` | Server-resolved profile binding/holds, all plans, recommendation decision and its reasons |
| `/api/plans/priorities` | `{token, order, confirmed: true}` | Confirms supported priority order in bounded visit RAM; returns fresh workspace/digest |
| `/api/plans/detail` | `{offeringId}` | Redacted/published plan fields, examples, exact retained source locators and fictional assumptions |

`order` accepts `monthly_plan_premium` and `in_network_medical_limit`, each at most once. It is explicit ordered metadata; the existing T10 answers remain unordered and are not silently converted into weights. The browser's old five-plan 2027 sample endpoint is untouched and is not the Plans dataset. A 2027 profile remains 2027 and receives `REQUESTED_SCOPE_UNSUPPORTED` against this 2026 catalog.

The existing `DaylightPlansHandoff.register(...)` activates the thin workspace after **Review your info → See plans**. The same conversation/composer stays mounted. All 41 meanings continue through the existing adapter; no copied profile, replacement intake or guessed external verification is used. The existing ten-minute review lifetime, correction, visit, deletion and ownership checks remain authoritative.

## Deterministic recommendation service

`plans_ranking.py` applies accepted, profile-digest-bound checks before ranking: coverage path, eligibility, service area, restrictions, drug arrangement, providers, medicines, travel, assistance and current-coverage baseline. These are predicate families, not additional required questionnaire screens. A trusted reviewer/check adapter may substantiate that a check is met or irrelevant in its evidence; an identity match alone never supplies participation, cost or eligibility.

Only accepted structured Decimal metrics enter ordering. Neither display strings nor fictional cost examples are parsed into personal estimates. The algorithm orders lexicographically by the user's confirmed priorities, returns up to three, and reports the same-priority ties including those crossing position three. Exact ID breaks ties only for presentation. Known conflicts stay in the all-plan result; an unresolved potential contender holds the global top three. There is no padding, weighted score, commissioned preference, inferred click preference or LLM ranking. The result includes all per-plan check states, missing metric keys, decision digest, method version and supported top-three reason records.

Current provider/drug identity research remains available through the existing identity workspace; it does not become a completed network/formulary/price check. No new external verification connector is claimed. Unaccepted or absent checks are `needs_check`.

## Exact-purpose acceptance

`cms-slice/data-sources/plans-workspace-acceptance.json` is a new **pending** receipt, not a change to any accepted parent. `plans_authority.py` reloads it on every operation. There is no HTTP, environment or fixture switch that authorizes real data.

A future release must name the exact catalog hash, `plans-strict-priority-20261105-r1`, `runtime_digest()`, an identified source-use owner/receipt/allowed purposes, and an independent Medicare subject-matter reviewer with `independent_of_sales: true`. Both reviews need timezone-aware `reviewed_at` and `expires_at` values and must be current. Any mismatch, revocation, missing review or malformed file fails closed.

`outputs` maps `purpose + ':' + canonical_sha256(payload)` to `true`. The implementation defines these exact payloads:

- `published_display`: `{offering_id, field, cell}` from immutable r13.
- `fictional_example`: `{offering_id, example, cell, assumptions, methods}`; every dependent published field must also be accepted.
- `recommendation_method`: `{method, metrics, checks, offering_ids}` for the exact full universe. This accepts the method, not every person by fiat.
- `personal_check`: `{input_digest, offering_id, check, finding}`. Findings require accepted evidence references and a `meets`/`known_conflict` state.
- `ranking_metric`: `{input_digest, offering_id, metric, finding}`. Requires exact evidence references, nonnegative finite Decimal-string amount, USD and the matching monthly-premium/annual-in-network-limit basis.

`cases[input_digest][offering_id]` contains only the check and metric findings needed for that reviewed case. It is a server-owned evidence seam, never a browser profile or automatic acceptance. No real case data is added in this increment. Future automated checks must supply the same evidence/review binding; source access does not grant it. Do not put raw chat or private provider/medicine lists in this repository receipt. Current unknowns remain visible until an authorized check/release can support them.

## Contextual chat contract

Only an intentional existing `/api/conversation/turn` message may include `plansContextPolicy: 'plans-context-v1'` alongside the existing `natural-context-v3` permission and `aiConsent: true`.

```json
{
  "version": "plans-context-v1",
  "reviewToken": "current receipt, or null for nonpersonal browsing",
  "viewDigest": "digest returned by the Plans API",
  "visibleIds": ["at most 12 retained IDs"],
  "comparedIds": ["at most 3 retained IDs"],
  "selectedId": "retained ID or null",
  "field": "published field key or null",
  "mode": "all"
}
```

`mode` also accepts `recommended` and `compare`. The service rejects unlisted IDs, extra text/amounts, unsupported fields, changed views/priorities and foreign/stale receipts before model work. Personal context is rechecked against the active visit inside the turn boundary. Catalog browsing can discuss general definitions without completing intake; it cannot authorize personal recommendations.

The interpreter receives only selection IDs/field/mode to distinguish references from personal reports. Composition receives bounded retained identities, current holds and purpose-accepted facts for the selected/compared plans. Visible-only plans contribute identities, not full benefit records. Neither the complete profile, review token, candidate amounts nor raw source text is added to model context. Viewing, scrolling, selecting and staging an editable question make no model call. The current view is captured again on Send. ContextVars isolate concurrent requests and reset after each turn.

Responses identify their source view, selected ID and field. Profile edits hold personal conclusions and require a new review. Source projection changes during generation withhold the response; stale replays do not resurrect it. Plan-turn prose is omitted from cross-turn visit memory to avoid carrying revoked plan claims forward; existing learning/task metadata remains permissioned. Drafts and chat history stay in the existing visit-only UI. No live model evaluation or conversational-quality approval is claimed.

## D73 review and remaining work

The integration makes the user's profile and retained plan evidence inspectable, keeps corrections and keep/defer/current-coverage checks, and allows browsing/learning without mandatory intake. Coverage-path and baseline checks remain conditions for recommendations. No economics enters the catalog, ranking or context. Existing privacy, budget, saving and protected runtimes remain separate. Technical checks establish bindings and failure behavior; consumer comprehension, full assistive-technology evaluation and owner assessment of conversation quality remain outstanding. The separate UI workstream can replace the thin rendering while preserving these APIs, source states, explicit Send, review receipt and decision bindings.

Executed test results and local activation are recorded alongside this file. A passing fixture is not source/method/consumer acceptance.

## Executed verification and activation

- **17 final Plans checks passed** (`focused.log` / `focused-result.json`): exact all-72 identity and field/hold projection, parent corruption, exact field release, material-hold protection, revocation/expiry/runtime mismatch, economic-key rejection, priority reversal, ties, fewer than three, unknown fourth contender, scope mismatch, finite amounts, profile/owner/CSRF boundaries, existing handoff, source lineage, context injection rejection, citation of an accepted field, stale replay suppression, browsing without personal authority and deletion/expiry.
- **169 affected checks passed** (`affected-regression.log`): Plans, review/handoff, normalized profile, existing natural-agent validation, session recovery and current chat contracts. Final small changes to release binding/status/glossary and stale cited-fact suppression were followed by the 17-check final Plans run.
- **40 frontend Send/handoff checks passed** (`frontend.log`), including the production request builder carrying Plans context once on message Send and never on navigation. JavaScript syntax checks passed. A discovered optional-global compatibility issue was corrected before these final checks.
- The guarded broad run executed **1,038 checks: 1,021 passed, 12 failed and 5 errored** (`full.log`, `full-result.json`). All 17 issue identities are present in the preceding plan-review baseline; `regression-comparison.json` records zero new identities. These unresolved historical lesson/visual/state expectations remain visible. The earlier system-Python run also lacked the runtime's `jsonschema` dependency; the retained broad result uses the actual app interpreter. No full-suite-green claim is made.
- The original r13 `build_examples.py --check` replay passes: 200 numeric candidates and 88 held examples. `binding.json` records source/runtime hashes, 72 identities, all 720 current benefit amounts suppressed, all 288 current example amounts suppressed, the unchanged normalized profile source and a successful pinned-engine verification.
- Browser checks on an isolated fixture covered search (six H1032 listings), two-plan comparison, all ten detail rows, locally available definitions, staged editable questions, chat closing/reopening and draft preservation. Desktop 1440×1000, tablet 834×1112 and phone 390×844 have no horizontal document overflow; the tablet chat is 440px wide. An existing unsent draft also survived staging a different plan question and was recovered through Restore draft. Screenshots are retained here. No Send to a real provider was executed. Full screen-reader and physical-keyboard evaluation remains separate UI work.
- Only `com.daylight.advisor-first.8893` was restarted, from PID 45533 to PID 43253. `activation.json` records HTTP 200 for the page, status and new static assets, with both static assets matching source. The live browser rendered **72 cards with no console errors**. `live-8893.png` captures the actual service. Saved guest records, protected variants, research parents and budget ledgers were not migrated or reset. The isolated :8918 fixture server and tab were closed after verification.

`run_offline.py` explicitly blocks non-loopback sockets and real provider curl subprocesses. Scripted response tests check transfer, validation and state behavior only; they are not a live conversational evaluation. Real recommendation release, source/method acceptance and personal external findings remain pending as described above.
