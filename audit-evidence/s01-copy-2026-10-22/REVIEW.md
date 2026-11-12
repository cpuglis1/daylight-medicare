# S01 approved teaching-copy correction — 2026-10-22

Owner authorization: “yes, great.” then “implement changes” for the three sentences below. This is a bounded copy change under D19/D22; D23/D24/D66/D68 route, profile, source and budget constraints remain in force. No consumer, legal, qualified Medicare or plan-release approval is recorded.

Active local UI checked: **http://127.0.0.1:8890/** (ten-question guide).

## Applied wording

- Q4 full teaching: “Part A helps cover inpatient hospital care. Part B helps cover doctors’ services and outpatient care.” The remaining timing/eligibility context is preserved. Comfortable mode retains its existing short introduction; Explain more contains the corrected full teaching.
- Q7 full teaching and comfortable-mode introduction: “You can add a separate Part D plan to Original Medicare; most Medicare Advantage plans include drug coverage.” The full teaching retains its opening definition and final exact-plan-rule caution.
- Standalone `advantage` fact: “The Part B premium still applies; some plans help pay all or part of it.” Its surrounding sentences, title and official source link are preserved.

Changed files: [ten-state.js](../../cms-slice/apps/ten-question/ten-state.js), [ten-app.js](../../cms-slice/apps/ten-question/ten-app.js), [teaching-facts.json](../../cms-slice/apps/ten-question/teaching-facts.json), and matching T04/T07 teaching in [guide-contract.json](../../cms-slice/apps/ten-question/guide-contract.json). Before-images and SHA-256 values are in [change-manifest.json](change-manifest.json); [approved-copy.diff](approved-copy.diff) shows only this change. No route, answer, profile, guide-save or budget implementation was changed. No shared product documentation or workbook was edited.

Official comparison sources previously reviewed for this S01 wording: [Parts of Medicare](https://www.medicare.gov/basics/get-started-with-medicare/medicare-basics/parts-of-medicare), [coverage options](https://www.medicare.gov/basics/get-started-with-medicare/get-more-coverage/your-coverage-options), and [Original Medicare versus Medicare Advantage](https://www.medicare.gov/basics/get-started-with-medicare/get-more-coverage/your-coverage-options/compare-original-medicare-medicare-advantage). These are general educational statements, not a 2026/2027 price-table validation or individual coverage determination.

## Focused verification

- JavaScript syntax checks passed for ten-state.js and ten-app.js.
- Existing frontend ten-question suite: **38/38 passed**, including contract synchronization and route/answer preservation.
- Existing backend ten-question suite: **9/9 passed** with `guide_server.ROOT` redirected to a fresh TemporaryDirectory before suite loading. All explicit test databases also use temporary storage.
- Live static UI in fresh Chromium contexts: **6/6 Q4/Q7 cases passed** — new and comfortable familiarity at desktop 1440×1000, tablet 820×1180 and phone 390×844. All compared text matches the approved sentences and preserved context; no page errors or horizontal overflow. Screenshots visually reviewed across the three sizes. Comfortable Q7 shows its short teaching and the same sentence again when Explain more is deliberately opened; existing disclosure behavior is unchanged.
- **3/3 standalone Advantage fact dialog component cases passed**, one per viewport, with the explicit fixture boundary below.
- Browser test intercepted every `/api/*` request before navigation and blocked non-GET and external requests. Evidence records zero real profile requests and zero paid AI calls. No production profile was used for browser navigation.
- Mechanical Impeccable detector on the four changed files returned `[]`.

### Popup boundary

The actual Part C map control opens `routesintro` (“The two coverage routes”), not standalone `advantage`. Its mapping/text was left unchanged and the actual popup was checked in each real UI case. To inspect the approved standalone Advantage copy through the existing dialog renderer, three additional **fixture-only** cases aliased the `advantage` response to the existing control in the isolated browser. This did not alter any application file, live mapping or source approval. Do not describe the standalone Advantage fact as naturally reachable from that Part C button. No live AI response was tested. The active ten-question server was subsequently restarted with its identical command to refresh the facts held in memory. [Server refresh receipt](server-refresh.json) confirms that the ten-question profile, legacy profile and shared AI-budget database SHA-256 values were identical before and after restart; the legacy server was not restarted. Only a static-file GET was used to check readiness, with no profile/API or AI request.

### Test-attempt disclosure

The initial ordinary-sandbox backend attempt had 7 passes and 2 permission errors: binding a test-only localhost server, and an existing default-database constructor reaching the legacy database before an expected runtime-config rejection. It failed at chmod; no session/save/delete functions ran. That constructor can issue SQLite setup pragmas and CREATE TABLE IF NOT EXISTS, so no byte-level nonchange claim is made without a pre-run database hash. The successful final run redirected the default root to temporary storage before loading tests. No guest records were intentionally read or changed.

The first browser pass correctly rendered the new-familiarity case, then its harness wrongly expected the comfortable-mode map to be open. The corrected harness explicitly uses the existing Show map action and all final cases passed. This was a harness correction, not a product mapping change.

## Evidence

- [Browser checks and exact visible text](browser/browser-checks.json)
- [Server refresh and unchanged database hashes](server-refresh.json)
- [Browser harness](browser-check.cjs) — its output directory points to the isolated task workspace used for the run.
- [Desktop Q4](browser/1440-new-q4.png), [desktop Q7 comfortable](browser/1440-comfortable-q7.png)
- [Tablet Q4 comfortable](browser/820-comfortable-q4.png), [tablet Q7](browser/820-new-q7.png)
- [Phone Q4](browser/390-new-q4.png), [phone Q7 comfortable](browser/390-comfortable-q7.png)
- [Actual Part C map popup](browser/390-new-actual-map-popup.png)
- [Standalone Advantage fact — fixture-only](browser/390-advantage-fact-component-fixture.png)

No commit, push, paid AI call, public deployment, workbook approval or release-approval write was made. The existing consumer/qualified review gates remain pending. The Impeccable context loader noted the existing design sidecar is older than DESIGN.md; it was not repaired as part of this copy task.
