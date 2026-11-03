# Core completion — October 21, 2026

**Subsequent D63 activation:** ordinary local AI is now enabled under a persistent shared $1/day UTC cap, no automatic retries and visible usage. See [AI_ACTIVATION.md](AI_ACTIVATION.md) for current status. The test-only activation limitation in this earlier completion record is historical and superseded.

Implemented D60–D62 while preserving D49–D59, approved Candidate02/Option A, the exact tagline **Your coverage, plain as day**, the legacy source/data gates and unrelated work. This completes the locally implemented core extension; it is not a public deployment or a claim that the complete plan-comparison product is ready.

- **Working app:** http://127.0.0.1:8890/
- **Rendered review:** http://127.0.0.1:8897/core-completion/
- [Service/configuration/privacy boundaries](CORE_SERVICE.md)
- [Screenshots and machine-readable evidence](visual-preview/core-completion/index.html)

## Implemented behavior

The active frontend retains the approved arrival and four stable phases. Goal, recipient and voluntary familiarity are separate; free text can propose several facts, which remain editable and uncommitted until explicit confirmation. Confirm and Continue are separate. Confirmed answers satisfy later questions without asking them again; unknowns remain visible. Beginners begin with what Medicare is, then grow the picture only as concepts are introduced. Experienced users can hide teaching, reopen it and browse without completing personal intake. Learning alone finishes usefully. Job-coverage, review/change, caregiver and general comparison routes retain the full master contract and relevant guided questions.

The real OpenAI Responses integration streams progress, validates typed commands, selects reviewed teaching facts and proposes allowlisted reported fields. It cannot generate insurance rules, verify user facts, recommend plans, browse the web or perform outside actions. The user confirms the extracted text before state changes. Grounded local explanations and the visibly labeled local interpreter remain usable when AI is unavailable. Transfer consent and durable saving are separate. Only submitted text plus a small allowlist of reported context is sent; names/dates/health lists are not automatically attached. Provider storage is disabled in requests; that does not establish legal compliance.

Backend guest profiles use private SQLite storage, hashed opaque sessions, HttpOnly SameSite cookies, same-origin/CSRF checks, bounded validated state, optimistic concurrency and idempotency. Explicit saving is required. Same-browser resume works after refresh and process restart. Current-tab history, Back/undo, explicit per-answer conflict merging and a local recovery copy avoid silent overwrites. Review/edit/delete, shared-browser warnings, distinct save receipts and optional sensitive-note saving are implemented. Original text, pending proposals, chat and drafts are not persisted. The local prototype's displayed expiry is seven days from session creation, configurable 1–30 days; no cross-device recovery is promised.

Ask Daylight remains an overlay. It preserves the underlying task geometry, current answer, unsent help draft and scroll; focus is trapped while open and Escape returns to the opener. The guest privacy dialog works within a phone viewport. A finish reviewer found one material issue—the sample task actions followed five records—which was corrected and recaptured without changing the approved visual direction.

## Five sourced sample records

These are actual identities extracted from existing captured CMS rows, not fabricated fixtures. The deterministic subset is not comprehensive or recommended. All prices, provider/drug fit and personalized cost remain unknown or unvalidated. Personalized comparison actions are disabled.

| Exact ID | Source name | Source geography |
|---|---|---|
| H1032-198-000-2027 | Wellcare Giveback (HMO-POS) | Collier County |
| H1032-199-000-2027 | Wellcare Simple (HMO-POS) | Collier County |
| H1036-290-000-2027 | Humana USAA Honor Giveback (HMO) | Collier County |
| S4802-083-000-2027 | Wellcare Classic (PDP) | Florida All Counties |
| S4802-146-000-2027 | Wellcare Value Script (PDP) | Florida All Counties |

[CMS source archive](https://www.cms.gov/files/zip/cy2027-landscape-202609-1.zip), captured October 17, 2026. Archive SHA-256 `0cf545fc36dbb6be8594193c311005d9125ceedf579c24b811c2addcf8daeaab`. Exact member, source row, source update date and capture timestamp are retained in `sample-plans.json` and source-detail dialogs. Statewide PDP source scope is preserved. No acceptance registry or legacy data gate was bypassed.

## Verification and measured limits

| Check | Result |
|---|---|
| Full Python suite | **238 passed**, including 37 new guide/profile/agent tests; isolated temporary databases and synthetic inputs |
| Frontend suite | **128 passed**, including 36 new policy tests; existing 92 preserved |
| JavaScript syntax | Passed for the installed guide files |
| Actual paid GPT-5.4 smoke | **3 requests passed**: multiple fact extraction, grounded Part A teaching, real browser streaming/edit/confirm |
| Paid test cost | **$0.0233275 estimated from measured provider tokens**, not an invoice; 7,783 input + 258 output tokens; conservative pre-call reservations totaled $0.1319125; below both 6-request/$0.50 caps |
| Guest persistence | Refresh, explicit resume, service restart, independent guest isolation, opted-in notes and subsequent removal checked |
| Concurrency/recovery | Actual two-tab conflict, unchecked per-answer merge, acknowledged save and local recovery copy checked |
| Responsive rendering | 1440 desktop, 820 tablet, 390 phone, 320 narrow phone, 1501×708 short desktop; page width matched viewport |
| Ask return | Task geometry unchanged (x128, width554.4297, document y225.5); focus, task draft, help draft and scroll preserved |
| Samples | All five exact source identities/provenance checked, statewide scope retained, five personalized actions disabled; controls precede records on desktop/phone |
| Visual review | Independent Impeccable final disposition **ship for this bounded extension** after sole material fix |

The key was usable and live integration actually ran; no credentials were displayed or copied into fixtures. There were no paid retries. The isolated live-test services have been stopped. The ordinary app service is running with paid AI **disabled**, as the owner's explicit paid approval covered synthetic smoke only. It offers an honest unavailable state and manual/reviewed fallback. A separate ongoing operating budget/request limit is required before enabling ordinary user AI traffic; this is not a credential failure.

Automated tests cover persistence/restart, private permissions, expiry, ownership/CSRF/origin, deletion, concurrency, idempotency, sensitive-field minimization, source identity, production-cookie defaults, model schema rejection, untrusted commands, context minimization and cached retries. Mocked failure tests do not prove real internet outage behavior. Physical mobile keyboards, actual screen-reader speech, complete WCAG conformance and older-adult comprehension testing remain unverified. COGA is supplemental guidance, not certification.

## Files and preservation

Core source changes: `cms-slice/apps/chat/{index.html,app.js,approved.css,guide-state.js,guide-core.js,guide-contract.json,teaching-facts.json,sample-plans.json}`, `cms-slice/scripts/{guest_profiles.py,guide_agent.py,guide_server.py}`, and `cms-slice/tests/{test_guest_guide.py,frontend/guide-policy.test.cjs}`. Documentation adds this report and CORE_SERVICE.md and records D60–D62 in PRODUCT.md/DAYLIGHT_REQUIREMENTS.md.

Nine pre-scope originals and hashes are preserved at [history/2026-10-21-before-core-completion](history/2026-10-21-before-core-completion/manifest.json). Every installed source update was guarded against its current hash to preserve concurrent work. The approved root DESIGN.md, earlier first-slice files, existing flow-state.js and legacy demo.py are unchanged from this scope's starting hashes. Earlier source/catalog/data and all preexisting uncommitted changes remain. No commit, push, deployment or source-data rewrite occurred.

## What remains

1. **Ordinary AI operation:** owner-defined ongoing request/spend limit and activation, separate from the completed smoke allowance. Implementation and configured key are verified. Current working app honestly keeps paid AI off.
2. **Personalized plan integration/validation:** accepted releases, actual supported-year/geography matches, validated benefits/prices/provider/drug fit, consistent comparison dimensions/ranking rationale and personal recommendations. Five source samples do not satisfy that gate.
3. **Public deployment:** production vendor/privacy/retention/backups/encryption/incident and hosting decisions, security review and deployment approval. Local guest persistence is not production compliance sign-off.
4. **Human validation:** real assistive technology/mobile keyboards and representative comprehension/recovery testing. Screenshots and test counts are not owner or participant acceptance.

No new credentials, paid accounts or external outreach were created. Only synthetic profiles were used. Run/configuration instructions and exact safeguards are in CORE_SERVICE.md. Do not enable ordinary paid usage by restarting the smoke allowance or describe source samples as verified matches.
