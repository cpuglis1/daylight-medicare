**D79 route update · October 27:** The active :8891 conversation now uses the server-owned adaptive controller; see [delivery](ADAPTIVE_CONVERSATION.md). The ALT74 endpoints and historical input gates below remain compatibility and fail-closed safeguards, not the new consumer sequence or accepted insurance policy.

# Customer profile and capability gates · ALT74

Implemented in the isolated 8891 alternative, 23 October 2026. The original 8890 app and accepted landing are preserved. This is reported-input preparation and a fail-closed recommendation boundary, not approved Medicare policy or a released recommendation engine.

The recovered [question/field inventory](CUSTOMER_PROFILE_QUESTION_MAP.md) enumerates 38 current primary questions, 3 explicit documented child prompts, 11 overlapping runtime wording templates, 31 detail controls, and RC29/RC30 as non-intake boundaries. It also preserves 46 legacy question-form nodes separately (34 intake/comparison, 12 learning/consent/navigation/operations). They are not made into 46 new required questions. Active parent/child/variant definitions and inactive historical bindings are explicit in `cms-slice/config/profile/question-map.json`.

## One guest aggregate, no parallel database

The machine files are `cms-slice/config/profile/customer-profile.template.json`, `customer-profile.schema.json`, `question-map.json` and `capability-policy.json`. Empty guide fields/readiness facts remain absent, meaning unanswered; the template's null field definitions are metadata, not fabricated reports. Each definition maps to an existing guide envelope or readiness fact/item path with purpose, conditional requirement, provenance, confirmation, dependencies, unknown/deferred and change-review behavior.

The service reuses the existing cookie-owned GuestProfiles and ReadinessProfiles records and existing optional/sensitive-save choices. It neither migrates original profiles nor creates a second customer database. The server derives gates anew from actual reported values; client progress, visited steps, zero queue and cached completeness cannot authorize a recommendation. Saved sensitive omissions remain missing after resume. A visit-only check does not durably save current inputs. Raw transcripts, audio, credentials and government ID numbers are not profile fields; recognized ID/credential submissions are rejected before saving or provider transfer. No unnecessary clinical or financial intake was added.

## Required information differs by capability

| Capability | Required reported inputs when relevant | Independent external hold |
|---|---|---|
| Availability | Home ZIP/county and comparison year | Validated service area/year; only five unvalidated 2027 Collier sample records exist here |
| Coverage comparison | Relevant scope, goal, person, current coverage, actual reported A/B status, requested timing, explicit doctor/medicine scope and routine travel; relevant change consequences | Complete market scope, source/independence/comparison acceptance |
| Enrollment/timing | Relevant A/B/basis and actual B date if active; consequential work/payer-order, separate loss dates, notice/gap, HSA and event details | Official enrollment evidence and reviewed timing policy; no deadline determined |
| Provider fit | Explicit none, or every requested doctor/practice and office city/state; relevant travel location | Identity and exact network verification |
| Drug coverage | Explicit none, or every medicine's exact reported name, strength and form; relevant clinic/pharmacy problem context | Identity and formulary verification |
| Drug pricing | Drug identities plus each fill's quantity, days supply, exact pharmacy/location and channel | Pharmacy identity, formulary/pricing adapter and source acceptance |
| Medigap rights | Relevant A/B/basis/B date, notice/history; prior Advantage/Medigap or replacement reports only on that requested path | Reviewed federal/state policy and official history; no issueability guarantee |
| SNP | Specific relevant program/plan qualification report when this comparison remains requested | Actual qualification verification and reviewed SNP policy |

Knowledge depth, ordinary cost preferences, priorities, optional budget and brand/generic preference are optional. Unknown/deferred never substitutes for a missing required fact; a disposition about an optional remaining detail does not erase other explicitly reported required values. Explicit none doctors/medicines differs from unknown. Reports remain unverified. Scope changes, parent-report revisions, stale flags and baseline dependency changes invalidate affected readiness; they do not delete the guest's answers. No legal rule or clinical conclusion is inferred from completeness.

## Server authority and consumer behavior

`POST /api/profile/readiness` validates this guest's current guide/companion and returns the server-derived assessment without saving it. `GET /api/profile/readiness` derives it from the same guest's saved records. Both use the existing origin/cookie/CSRF boundaries as appropriate. `POST /api/recommendations` and its saved-profile GET cannot return personalized recommendations: missing required inputs produce HTTP 409; even complete reported inputs produce HTTP 503 while external gates remain held. Forged client completion counters cannot change this. No client-supplied verified state is accepted. Sample records remain available through their separate labeled sample endpoint.

When the conversational queue ends, the UI checks the server. Missing information produces a short reason, review access and an optional next useful question through Continue. It does not automatically reopen every unknown, jump to plans or announce readiness. When reported inputs suffice, the UI states the external hold and disables recommendation continuation. **Browse sample plans** remains an explicit optional action, with existing sample limitations and return state intact. A missing external source is not another customer intake question. RC29 remains the source guard; RC30 remains the held future application review.

## Focused evidence and limits

Synthetic Python/HTTP checks cover all-unknown, explicit none, partial/multiple entities, different capability requirements, complete input with external data absent, edits invalidating dependent reports, optional unknown brand without erasing known drug identity, same-guest saved reuse, sensitive-save omissions, typed/provenance validation, recognized ID rejection and forged completion. Semantic DOM fixtures use the actual Python server evaluator and cover all-unknown without automatic plans or unknown loops, useful next question, explicit sample browsing and return. Existing employer and doctor/medicine/travel traces remain in the same chat, now followed by the explicit external hold and optional samples.

No real guest records or paid model calls were used. Browser/Firefox access, rendered desktop/tablet/phone inspection and actual assistive-technology speech remain paused/unverified. The 29 research references are not professionally approved policy. External identity/network/formulary/pricing, comprehensive coverage, professional rule review, unbiased ranking validation, fulfillment and application/enrollment remain unimplemented or held. Optional guest saving is still a local prototype for this browser, not cross-device identity or a multi-person household account.

Before-images and hashes for altered source/runtime files: `audit-evidence/profile-gates-20261023T152218Z/`. Deployment refreshes only `com.daylight.chat-alternative.8891`; no guest database, original app or shared aggregate $1 UTC-day ledger is copied/reset. Keep both versions' records for rollback. No commit, push or public deployment.
