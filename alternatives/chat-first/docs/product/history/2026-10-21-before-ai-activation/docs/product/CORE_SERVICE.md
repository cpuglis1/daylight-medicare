# Daylight core service

Authorized by D60–D62. Preserve [DESIGN.md](../../DESIGN.md), [master flow](MASTER_DESIGN.md) and the complete node inventory. This service runs the guide, guest profiles and grounded agent independently of personalized plan validation. It does not grant plan acceptance or production deployment approval.

## Run locally

From the repository root:

```sh
python3 cms-slice/scripts/guide_server.py --port 8890 --model-env .env
```

That starts education, manual inputs, profiles and samples with paid AI disabled. After the owner authorizes the live-request budget, add `--enable-live --live-request-limit 6`. The existing model-env loader reads only the existing OpenAI key/model into process memory; never copy credentials into source, fixtures, prompts or logs. The configured model was gpt-5.4 when inspected. Three authorized real-provider synthetic requests passed; see [completion evidence](CORE_COMPLETION.md). The estimated cost from measured tokens was $0.0233275. Ordinary paid use remains disabled pending a separate operating budget, since that approval covered tests only.

Default database: ignored `cms-slice/var/guest-profiles/guides.sqlite3`, in a private directory. `--database` selects a private local path for synthetic test workflows. `--retention-days` accepts 1–30; the local prototype default is seven days from guest-session creation. This is an explicitly displayed development policy, not a legal retention determination. Production hosting, vendor/privacy review, encryption at rest, backup handling, retention selection, incident procedures and deployment are separate owner decisions. This service binds loopback; it does not publish the application.

## Service and policy boundaries

| Boundary | Behavior |
|---|---|
| `GET /api/guest/session` | Opaque HttpOnly SameSite=Strict cookie; CSRF token, expiry and actual saved-version metadata returned separately. No public profile ID or bearer recovery URL. |
| `GET /api/guest/profile` | Cookie-owned profile only; no token/query lookup. Resume is a deliberate UI action. |
| `PUT /api/guest/profile` | Same origin/CSRF, bounded validated JSON, current notice version, explicit saving, optimistic version and idempotency key required. Only confirmed reports/unknown/skipped states; never independent verification. |
| `DELETE /api/guest/profile` | Explicit user confirmation, cookie ownership, CSRF and expected version. Removes this guest guide and session; outside accounts/insurance are unaffected. |
| `POST /api/agent` | Explicit AI transfer; limited context and reviewed teaching, typed command schema, streaming status, final validated output. No profile writes, plan tools, web browsing, arbitrary execution or external actions. |
| `POST /api/agent/confirm` | Guest- and state-version-bound proposal review. UI still requires deliberate confirmation and a separate Continue. |
| `GET /api/sample-plans` | Five actual CMS source identities, exact year/geography/provenance, labeled unvalidated subset; no prices, fit or recommendation. |
| Retained plan endpoints | Unavailable pending validated integration. No research-mode or acceptance-registry bypass. The existing `demo.py` remains unchanged. |

The model orchestrates reported-field proposals, relevant immutable teaching and eligible next-task suggestions. It cannot author new factual insurance prose or mark facts verified. Unsupported questions receive an explicit scope limit. User/source text cannot grant new commands. Manual answers and reviewed local teaching remain available without AI. The optional local interpreter is visibly labeled and never represented as a live response.

The live development budget is at most six provider calls per service run, each with a 24,000-byte complete request bound and 900-output-token cap, no paid built-in tools, no provider storage request and no silent provider retries. Completed request IDs can be replayed from a short-lived owned cache. This is a conservative smoke-test guard, not a customer billing system. Do not restart it to evade a user-approved total cap. Cancel stops UI processing and further stream consumption; work already sent may still incur provider usage.

## Saving, privacy and recovery

- Fresh guides do not save answers until the user chooses saving. A cookie identifies the guest session; no account is created. Same-browser resume is supported; cross-device/lost-cookie recovery is not promised.
- Saved guides contain confirmed normalized answers, teaching presentation and navigation context. Original submitted text, pending proposals, unsent drafts and chat history are not persisted.
- Names, birth details, medicine/pharmacy/provider lists, requested plan-name text and preparation notes are omitted unless the separate optional sensitive-note save choice is enabled. Those values are never automatically attached to the model.
- The model receives the submitted message and only allowlisted reported goal, recipient role, familiarity, coverage category/change/task and priorities. The transfer notice appears before enabling submission. Sending one request is not durable-save consent.
- The service has no transcript logger, request-body logging or health-chat analytics. Provider processing is separate and must be reviewed before production; `store:false` is not a blanket legal/compliance guarantee.
- Only an acknowledged save receipt says Saved. Offline, failed, saving, conflict and visit-only are distinct. Another-tab conflicts preserve current entries and offer the server version for review; there is no automatic overwrite.
- Back restores the actual route and lesson queue. Edits preserve independent entries and flag dependent conclusions. Undo covers recent recorded answers within the current tab; the service does not retain a durable history of superseded sensitive answers.
- Turning saving off leaves the prior saved copy intact. Delete explicitly removes the guest profile/session. Expired rows and request receipts are purged on access and by a minute-scale maintenance loop while the service runs. Filesystem backups/OS recovery are outside this local prototype’s deletion guarantee.
- Local HTTP uses a named development cookie without Secure. The server factory’s production mode requires an explicit HTTPS origin and uses a Secure `__Host-` cookie; this is a default safeguard, not deployment approval.

## Source samples

`sample-plans.json` was extracted from the already captured 2027 CMS Collier landscape snapshot. Selection is deterministic: first two MA-PD, one MA and two PDP records in exact ID order. This provides visual content, not a shortlist. The source’s Florida All Counties scope remains explicit for statewide PDP rows. Premiums, clinical participation, drug fit, personal costs and enrollment rights remain unvalidated/unknown. Records are not substituted for another requested year or geography.

## Verification

Run the existing suite plus `cms-slice/tests/test_guest_guide.py` and frontend policy tests. All profile tests use isolated temporary databases and synthetic text; never point deletion tests at a real profile database. Live smoke must be explicitly authorized, remain within its total cap and record actual results without credentials or personal data. Browser checks must include save/refresh/resume, conflict recovery, optional sensitive fields, knowledge paths, confirmed text, Ask exact return, sample provenance, and held comparison actions on desktop/phone. Physical keyboards, assistive-technology speech and participant comprehension are separate evidence.

API implementation references: [Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs), [Responses streaming](https://developers.openai.com/api/docs/guides/streaming-responses), [configured model](https://developers.openai.com/api/docs/models/gpt-5.4).
