# Daylight vision guide: implementation and verification

Implemented October 21, 2026 from the owner's authorization to review and implement `docs/DAYLIGHT_VISION_REVIEW_AND_ACTION_GUIDE.md`. This report records the resulting behavior; the supplied review document remains intact.

## Delivered

| Guide action | Result | Requirements |
| --- | --- | --- |
| Purpose first | Four visible goals, no initial answer, one Continue. Ask who once before personal coverage questions. Goals remain editable. | D41, D06, D12 |
| Tailored outcomes | Beginner can learn and leave with a summary without ZIP or personal intake. Comparison can start with category and ZIP. Review/change/add and job-transition paths retain the relevant checks. Keeping current coverage is valid. | D41, D31 |
| Short browsing | Shortcut skips the broad goal, recipient/coverage intake, doctors, and medicines. Choosing to review a personal change then asks who it is for. Category, current scope, and edit controls are explicit. | D41, D47 |
| Adjustable guide | Show/Hide controls, shortcut collapsed by default, manual choice retained through forward/Back/goal changes. The first beginner picture contains Medicare alone. | D42, D29–D30 |
| Local explanations | Named picture pieces replace only the picture contents; task and inputs remain active. Back to picture and Ask more are explicit. | D43, D34–D35 |
| Contained assistant | Desktop dialog over the reference side; phone sheet follows the available viewport. Selected question, sources, visible follow-ups, history/draft, Return, Escape, modal focus protection and restoration retained. | D43–D44, D25, D33–D37 |
| AI and privacy | Visible AI assistant identity and first-use introduction. Source-linked guide replies, live AI replies, unavailable service, and submission/logging disclosure remain distinct. Guide notes are not automatically attached to chat. | D44, D23, D28 |
| Enrollment order | Five requested enrollment answers plus another-situation path, including Part B only. Optional card-reading help follows relevant reported enrollment. Parts unknown and enrollment unknown remain distinct. | D45 |
| Clear teaching | Removed the specified reassurance sentence; plain Advantage explanation; relevant supplement bridge and benefit education instead of a mandatory supplement lesson for everyone. Priorities use “What is most important to you?” | D45, D19–D20 |
| Geography | Complete dated HUD crosswalk, verified 34102 single-county mapping, ambiguity/manual/unknown fallback, Change location, and unchanged local catalog boundary. No external geocoder receives the entered ZIP. | D46, D14, D22 |
| Enter | ZIP form submits through its own validation. Choices do not also advance. Notes retain newlines; chat supports Enter/Shift+Enter with visible instructions and no background journey submission. | D46, D12 |
| Comparison | Category/year/location and exact identifiers, source conditions, missing values, $0, and conflicts remain visible. Two-column records when the picture is collapsed on desktop. Saved candidates survive edits; old results are invalidated. Current-policy facts needed for a full baseline remain explicit. Removed the duplicate sticky comparison action that could cover the table. | D47 |
| Supported finish | One next task, grouped checks, useful editable preparation drafts, Copy, print/save, and correct Back for direct transitions. Optional notes remain. Changed answers flag an existing draft for review; regenerating retains the prior version in tab state. | D48, D21 |
| Print parity | Same summary model, reported/unverified facts, scoped dates, saved candidates, notes, and edited drafts. No duplicate numbering, universal change window, or suggestion that preparation was sent. Sample output inspected as PDF. | D48 |

Durable context updated in `AGENTS.md`, `PRODUCT.md`, and D41–D48 of `DAYLIGHT_REQUIREMENTS.md`. These latest owner-approved refinements supersede the older compulsory basics-before-goal and full-page help presentation. The visual identity and centered arrival remain.

## Verification

- **61 frontend tests pass.** Existing date arithmetic, Medigap effective-month separation, unknowns, job coordination, notes, explicit chat payloads, failed-service states, and ranking limitations retained. Added meaningful checks for the new states, preservation, routes, preparation, and complete geography reference.
- **8 consumer-admission tests pass.** Extended the real HTTP blocked-asset check to include the geography reference and stylesheet. No gate was disabled or accepted status fabricated.
- **14 Chrome walkthrough scenarios pass, zero page errors.** Beginner, experienced browsing, ambiguous/unsupported/unavailable geography, job transition, distinct unknown enrollment, Advantage-to-supplement inquiry, caregiver handoff, full personal path with unknown timing and multiline notes, pending catalog/retry, phone help, tablet, and enlargement.
- Captures inspected at **1440 × 1000**, **820 × 1180**, **390 × 844**, and a reduced **390 × 430** help viewport. A **200% Chromium CSS layout-zoom check** exposed cramped columns; container-based stacking and navigation reflow fixed them. This is not a physical-device or screen-reader certification.
- A delayed stage-focus callback could steal focus after fast typing began. It now respects a control already focused within the task.
- Printed a synthetic job-transition summary with an edited benefits-office draft. Checked screen/print facts and notes, rendered PDF pages, removed the extra nearly empty fourth page, and retained readable three-page output for that example. No requirement forces every summary into one page.
- The pre-existing static preview at `http://127.0.0.1:8766/` serves byte-for-byte current HTML, JS, CSS, and geography data. Its `/api/status` returns 404: that preview is a frontend preview, not a connected plan/chat service.

Reproduction:

```sh
node --test cms-slice/tests/frontend/journey.test.cjs
```

From `cms-slice/`:

```sh
python3 -m unittest discover -s tests -p test_consumer_acceptance.py
python3 tests/frontend/fixture_server.py --port 8881
# In another terminal; puppeteer-core must be available:
PUPPETEER_MODULE=/path/to/puppeteer-core \
  QA_URL=http://127.0.0.1:8881 node tests/frontend/vision.browser.cjs
```

The fixture is conspicuously synthetic and uses invented plan records. Its success demonstrates interface behavior, not real plan acceptance, available live AI, eligibility, or personal fit. The normal service still requires the existing release review. Fixed assets are loaded when that service starts, so restart it after code/asset changes.

Artifacts: `outputs/daylight-vision-20261021/browser-checks.json`, desktop/phone/tablet/enlargement captures, and `transition-summary.pdf`. Before-images of the frontend were retained under `outputs/daylight-vision-20261021/before/` for comparison with this session's edits rather than unrelated uncommitted work.

## Source and service boundaries

The geography source is the **September 2025 complete HUD workbook**, published by CMS and checked October 21, 2026; it is not described as a live 2026 lookup. Its source, hashes, verified rows, and refresh command are documented in `docs/ZIP_COUNTY_REFERENCE.md`. It retains 11,371 multi-county ZIPs rather than selecting a majority county. Update the snapshot through normal data maintenance before production use.

Copy was checked against [Medicare coverage options](https://www.medicare.gov/health-drug-plans/health-plans/your-health-plan-options), [Medigap basics](https://www.medicare.gov/health-drug-plans/medigap/basics), and [Medigap benefits](https://www.medicare.gov/health-drug-plans/medigap/basics/compare-plan-benefits). Supplement education does not promise an insurer quote or purchasing right. Existing cost, date, and evidence safeguards remain.

Preparation assistance is implemented. Staffed outreach is a separate future service, as the approved guide recommends. No email/call is sent, no human availability is promised, and no enrollment occurs. No commit, push, publication, palette/font replacement, or new detector suppression was performed.

The planned **6–8 formative sessions**, actual iPad/iPhone keyboard behavior, assistive-technology use, and real live-service checks remain external validation work. Use the endorsed [W3C older-user guidance](https://www.w3.org/WAI/older-users/) and [COGA guidance](https://www.w3.org/TR/coga-usable/) when observing comprehension, correction, help return, and next-step completion.
