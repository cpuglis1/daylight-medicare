# Selective confirmation and request headroom

Owner approved proposal items 1–4; item 5 (live conversation-quality evaluation) remains with the owner. Scope is D86/D73 on :8893. No visual redesign or customer profile migration.

## Implemented

- Composition confirms newly captured/corrected consequential details close to the answer. Names return when relevant to the current explanation or ambiguity, without fixed mention quotas or rote callbacks. Doctors, medicines and local-care reports cannot establish an unstated priority ranking. Exact reports remain separate from conversational emphasis.
- `request_packing.py` packs repeated-key education catalog/delivery records as explicit columns/rows, retaining every value and qualification. Mixed-shape records stay as objects, preserving absent versus null. The interpreter's compatibility `safeReports` entry is omitted only when a unique current full report contains the same value; stale, conflicting, unmatched and composer entries remain. Full 41-meaning interpreter semantics and all existing eligible composer candidates are retained. Canonical state, corrections, source claims, current message and visit memory are unchanged.
- Request measurements record only static category names, numeric byte sizes and the authoritative configured token count. Diagnostics include before/after and a zero-history byte baseline; they contain no customer values or identifiers. JSON-component sizes are separately labeled and are not claimed to sum to wire bytes. No extra generation or token-count call is added to the production flow; existing bounded history trimming remains a last resort.
- Central `request_limits.py` sets **16,000 input tokens, 900 output tokens and 96,000 request bytes** for this variant. Both atomic turn reservations, per-stage checks and the local budget adapter use the input bound. Exact settlement, uncertain holds, release of certainly unissued reservations, midnight accounting and the **$5 UTC-day aggregate cap** remain. A maximum two-stage reservation is now $0.107; measured usage still determines settled cost. Larger reservations can leave fewer available turns near the daily cap. The live status reports the actual input/output limits.

The pinned engine and original pricing receipt remain unchanged. Their historical 8,000 input/900 output bounds still identify that exact rate-review artifact; current price/model/tier/freshness verification is retained. The separately approved local request policy authorizes larger :8893 requests at those same checked rates. Other variants retain their original request and spending policies.

## Technical evidence

[Full regression output](full-tests.log): **806 passing tests**, including the existing renderer/button checks. After the final additive status-limit fields, [15 budget checks](budget-tests.log) passed again. New checks cover exact 16,000 acceptance and 16,001 rejection, unchanged output/model guards, original-variant 8,000 rejection, atomic/competing reservations, exact high-input settlement, lossless round trips, sparse fields, conflicting reports, idempotence and value-free diagnostics. [Packing tests](packing-tests.log), [agent tests](agent-tests.log).

The [reproducible sizing script](measure_requests.py) creates fictional payloads through the actual two stages, with all 41 interpreter meanings, the existing maximum of 12 composer candidates and all 17 learning concepts. Scripted responses and a temporary ledger avoid provider generation. Six explicit token-count endpoint calls measured the before/after/zero-history payloads; no real user reports or conversation were loaded. [Numeric output](request-sizing.json):

| Stage | Before packing | After packing, history retained | Packed, history removed |
| --- | ---: | ---: | ---: |
| Interpreter | 8,957 tokens | 8,434 tokens | 8,175 tokens |
| Composer | 6,925 tokens | 6,340 tokens | 6,081 tokens |

This controlled case explains how fixed context can exceed the old 8,000-token bound even without dialogue. The 16,000 ceiling leaves useful headroom for it; it is not a universal worst-case proof or a reconstruction of the owner's failed request. Maximum byte and token limits still reject oversized requests before generation. Initial sizing attempted 41 composer candidates and was correctly rejected by the existing 12-candidate guard; the retained script uses that unchanged maximum.

## Activation and remaining evaluation

[Activation receipt](activation.json) records the local restart, live AI status, current limits and source hashes. Only :8893 was restarted. Refresh and start a fresh visit to load the new server-memory context; saved reports are unchanged.

No paid model generation, long-journey live eval, new saving, API compaction, extra agent loop, automatic paid retry, source acceptance or recommendation release was performed. The owner will assess natural confirmation timing, relevance and longer conversation quality. Prompt tests and lossless structural checks do not establish those human outcomes.

D73 review: the consumer task improves continuity and useful acknowledgment; no intake meaning, optional question, coverage-path tradeoff or user correction is removed. Reports remain separate from verified findings and all real research/personal-output gates remain held. No commercial information enters decision logic. Existing v3 deliberate Send, visit-only memory, separate saving and protected variants/stores remain. Evaluation of comprehension and naturalness remains explicitly open.
