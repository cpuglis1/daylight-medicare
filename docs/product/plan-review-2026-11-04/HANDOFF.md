# Advisor closing and Plans handoff

Owner instruction, November 4, 2026 · D86/D73/D90 · :8893 only.

The advisor offers **Review your info** once it has a useful reported profile for the requested comparison. The person sees a consolidated, editable summary and the checks still open. **See plans** confirms that exact profile and requests the in-app Plans workspace. The separately owned Plans workspace and recommendation implementation are not included here.

## Minimum information

These are meanings, not a question count or a prescribed dialogue order. Reuse information already reported, including several facts in one message. Learning and timing-only conversations do not become a comparison questionnaire merely because the legacy router defaults to `compare`.

| Meaning | Required for the initial review | Existing report |
| --- | --- | --- |
| Goal | A current request to find or review coverage | T01 and current task |
| Person | Known beneficiary relationship: self or someone being helped | RC01 / subject role |
| Location | Reported ZIP and resolved county; reference-derived county is labeled, not verified residence | T03 / RC02 |
| Coverage year | One explicit comparison year or year in the reported intended start; conflicting years require clarification | RC03 / T04 |
| Current insurance | Report, including none, or an explicit unknown/defer | T05 |
| Actual Medicare enrollment | Reported A/B/neither/pending status, or explicit unknown/defer; current coverage does not silently supply this | RC04 |
| Doctors and hospitals | Retained names, explicit none, or explicit unknown/defer | T06 / RC21 |
| Prescriptions | Retained names, explicit none, or explicit unknown/defer | T07 / RC22–23 |
| Routine care away from home | Report or explicit unknown/defer | T08 |
| Cost preference | Report, including no preference, or explicit unknown/defer | T09 |
| Priorities | Report or explicit unknown/defer | T10 |

Selecting “add” without retaining any names is incomplete. A lost sensitive list is not treated as “none.” Missing person, location or year prevents this personal handoff; an explicit deferral is preserved without automatically asking it again. Conflicting/stale required reports and an active consequential clarification hold the review. All-unknown intake cannot unlock recommendations.

Exact offices, product strength/form, fills, pharmacies, assistance, enrollment dates and other conditional meanings remain available for actual dependent checks. They are not universally required before the initial review. Understanding and curriculum progress remain separate, tentative dimensions; there is no compulsory quiz or all-41 gate.

## Follow-up contract

Every successful active model response must include a validated follow-up question. The question can advance learning, clarify a report, collect consequential information or offer the review checkpoint. Model metadata claiming a useful stopping point is not permission to omit it. Explicit pauses remain supported.

Missing or removed follow-ups use the existing bounded composition repair. Any retained component is checked again; a reply can only reuse an actually pending or required approved question, not an unrelated intake fallback. A response still lacking a valid question cannot be labeled complete. Provider/service failures remain possible and are reported separately. No canned explanation or case-specific script was introduced. These checks establish the contract, not naturalness or consumer comprehension.

## Integration interface

Implemented in `alternatives/advisor-first/plan_review.py`, `plan_review_http.py`, `natural_flow.py` and `web/plans-handoff.js`.

1. Each conversation response exposes `planReadiness`: `active`, `canReview`, criterion states, missing meanings, requested scope and open checks.
2. The existing conversation API accepts `{type: "review_plans"}` and returns `review.kind = "plan_profile"` with a token and editable rows.
3. `{type: "confirm_plan_review", token}` returns `plansHandoff`. This is the explicit **See plans** action. `{type: "cancel_plan_review", token}` returns to conversation. Profile edits require a current review before confirmation.
4. The Plans frontend registers its existing tab activation function:

```js
const unregister = window.DaylightPlansHandoff.register(async handoff => {
  // Mount/activate the separately implemented Plans workspace here.
  // Keep the receipt in visit memory and preserve its exact requested scope.
  await plansWorkspace.open({reviewReceipt: handoff.token});
  return true;
});
```

`plansWorkspace.open` above is the receiving implementation's callback, not a newly shipped API. Alternatively listen for the cancelable `daylight:plans-requested` event and call `preventDefault()` when the workspace handles it. The event detail is the same handoff. No navigation is claimed if no handler exists: the current UI keeps the profile and explains that the workspace is not connected yet. A failed callback preserves the accepted state and provides an explicit retry.

5. **Resolve the receipt on the backend before using it.** The same-origin, session- and CSRF-protected `POST /api/plans/handoff` accepts only `{ "token": "..." }`. It reads the latest owner-bound server snapshot, never a submitted client profile. The backend equivalent is `NaturalConversation.resolve_plans_handoff(owner, token)`.

The returned `plan-review-20261104-r1` object contains `token`, `expiresAt`, `inputDigest`, `destination: "plans"`, `reportedInfoReviewed: true`, `scope`, the existing normalized `profile` (all 41 meanings retained), `holds` and `personalRecommendationAllowed: false`. Existing externally verified flags remain false; review does not promote them. Review/handoff receipts are bounded to 128 entries per store and expire after ten minutes. They bind to owner, visit chain and all report/disposition/provenance inputs. Corrections, expired visits and deletion invalidate access. Current-request replay is idempotent; historical replay cannot navigate with an old receipt.

The other workspace must preserve year, geography, source/method/purpose gates, current-coverage alternatives and unresolved must-haves. A 2027 request stays 2027 even though the retained Collier catalog is 2026. Source approval, a supported candidate universe and actual eligibility/network/drug checks are separate from reviewing reports. This increment never releases a recommendation or authorizes enrollment.

The full normalized profile is an internal application payload, not new permission to send all fields to an AI provider. Continue using existing purpose-specific AI context and saving permissions. Do not put the receipt/profile in URLs, browser storage, logs or outside sharing. No new persistence, external action or automatic model call accompanies the checkpoint.

## Verification

See `audit-evidence/plan-review-20261104/README.md` for the executed offline checks, fixture browser observations, preserved-source verification and activation status. The browser destination used for testing is explicitly a fixture, not the actual Plans tab.
