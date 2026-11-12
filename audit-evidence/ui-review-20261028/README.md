# D79 :8891 live-review revision · October 28, 2026

The owner approved implementing the 25 actions extracted from the 10:12 EDT UI review. This is the technical delivery record for `D79-adaptive-20261028-r2`, addressing D49–D57, D64 independence, D73 review, D75 isolation, D79 and the compatible ALT73/ALT74 gates. The active source is `alternatives/chat-first/`; the runtime is `/Users/cep4u/daylight-chat-alternative-runtime`. The original :8890 and retained Documents fallback were not deployment targets.

## Delivered actions

| # | Review action | Implemented result / verification |
| --- | --- | --- |
| 1 | Replace the repeated task menu | Server-owned contextual next steps replace the seven-task hub. Navigation is separate from insurance capability gates. |
| 2 | Bridge learning to personal options | “Understand Medicare and my options” follows reviewed lessons, then explicitly offers personal preparation or samples. Research-only scope stays public. |
| 3 | Ask only necessary missing details | All 41 reviewed IDs remain conditional. Scoped reports and unchanged unknowns are reused; they are not a mandatory intake battery. |
| 4 | Stop repeating the basics | Bounded `learningSeen` metadata advances through reviewed teaching without replaying completed lessons. |
| 5 | Reuse COBRA context | COBRA is retained as coverage type. General timing preparation avoids a redundant Medicare-status ask; a concrete payer-order check can still require the independently missing status. COBRA never implies a Part A/B answer. |
| 6 | Connect the timing questions | Desired Medicare start, actual job end and insurance end remain distinct. Job end is collected when relevant to actual current employment or job loss; COBRA alone ordinarily needs only its insurance end. |
| 7 | Accept natural dates | `1226`, `12/26`, `12/2026` and December 2026 normalize to a displayed December 2026 before submission. Year-only scope is reused when a later task needs its missing month. No day is invented. |
| 8 | Use plain provider/drug prompts | Conversational doctor/hospital and prescription questions replace task jargon. “None” is deterministic. |
| 9 | Eliminate inert task actions | Contextual explore, learn-next, sample, review and resume actions are implemented; completed preparation has a useful next step. |
| 10 | Show progress and profile building | Four stable conversation milestones sit below the brand. Report counts are inspectable; the progress indicator explicitly does not establish verified eligibility or a recommendation. |
| 11 | Provide a clear destination | Explicit See sample plans reaches five source-labeled sample records. Their actual year/location and unvalidated fit remain visible. |
| 12 | Use one deliberate submission | Selection, field entry and free text share one fixed Send. Enter submits; Shift+Enter adds a line; IME and busy/empty guards remain. |
| 13 | Group unknown/defer choices | Unknown and Check later appear with ordinary answers. A partial known date plus unknown companion preserves both independently. |
| 14 | Show submitted selections | Every submitted answer and navigation choice appears as a right-aligned user message, including explanation preferences changed in Review. |
| 15 | Preserve the reading position | Append-only history keeps submitted answers/new explanations in the reading pane. Pending text and question-specific fields survive updates, preference edits and sample dialogs. See browser instrumentation caveat below. |
| 16 | Quiet the chrome | Back, Review information, Browse sample plans and privacy sit below the composer. The persistent unverified-profile banner is removed; relevant source/fit boundaries remain at results/review. |
| 17 | Use consistent chat typography | Conversational text is 18px with bold questions and fewer oversized sections. Smaller source/navigation text remains legible. |
| 18 | Remove repeated acknowledgments | One opening profile-edit explanation replaces routine “I recorded” messages and premature personal-details boilerplate. |
| 19 | Collapse sources | Sources expand inline on demand in teaching and sample records. |
| 20 | Evaluate text reveal | Only validated, newly appended assistant text gets a bounded word reveal (at most about 770ms). Full accessible text is present immediately; reduced motion disables the effect. This is not unvalidated model streaming. |
| 21 | Widen responsive chat | The reading area uses available width; the composer and controls remain within the app viewport at desktop/tablet/phone sizes. |
| 22 | Align the landing geometry | Brand, hero and footer share edges; text/photo fill the available hero height. The approved photograph and identity remain. |
| 23 | Fit the landing in one screen | Verified at 1280×800, 768×1024, 390×844, 375×667 and 320×568 without landing scroll or horizontal overflow. Tablet/phone use a stacked photo. |
| 24 | Keep one arrival action | One centered Get started replaces separate coverage/AI entry buttons. |
| 25 | Simplify arrival copy | Short self-discovery subtitle; duplicate notices/previous-guide link removed. Privacy access, actual consent and photograph attribution/license remain. |

The 2026/2027 sample mismatch was expressly deferred. No dataset was relabeled or promoted to a personal recommendation.

## Verification and live AI

- [139 targeted Python checks](test-summary.json) pass, including 17 new review-flow checks. Fixtures use temporary stores and mocked transport. A sandbox-only attempt could not bind loopback sockets; the identical suite passed with authorized loopback access. Its diagnostic log is retained separately.
- [JavaScript checks](javascript-checks.log): new renderer syntax and four retained compatibility scripts pass. Three legacy DOM harnesses now explicitly use the sealed before-review HTML fixture because they exercise retained `chat-app.js`, not the new renderer. They do not substitute for new-UI browser testing.
- One historical source-identity test is explicitly excluded: its relocated pinned `data-sources/release.json`/read-model package is absent. This is an unresolved source-package check, not passing domain acceptance.
- [Actual live AI](live-verification.json): three GPT-5.4 generations settled, totaling an estimated **$0.036515**, within the unchanged aggregate **$1/UTC-day** cap. No uncertain reservations remain. The first multi-fact test revealed a stale DOM composer; it was fixed, then the same live scenario passed. A separate Medicare Advantage explanation retained the active task and a new draft typed during the request.
- The successful transition message supplied current-job coverage and a December 2026 intended start. Only job end and insurance end were asked next. November 2026 job end plus unknown insurance end remained separate. Continuing to options reused context and asked ZIP, doctors, prescriptions and travel. None/choices/date entry/sample/review actions added **zero** generation requests. The explicit sample destination showed five correctly labeled records.
- The alternative pricing review was renewed against [the official GPT-5.4 model page](https://developers.openai.com/api/docs/models/gpt-5.4), with unchanged rates and bounds; see [pricing evidence](pricing-review.json). Its expiry is November 4, 2026 at 00:00 UTC. The original :8890 pricing configuration was preserved and remains expired; its AI availability was false before and after this task.
- [Browser checks](browser-checks.json) and [captures](capture-inventory.json) cover desktop/tablet/phone, learning, real AI, dates, grouped unknowns, sample navigation, draft retention and isolated synthetic save/resume. A non-consented saved start date remains missing on resume while COBRA is reused. A preference edit preserves an in-progress `1226` field and produces a visible user message.
- [Static detector output](detector.log) has no reported findings. CSS/JS scans are regex-only, and this is not accessibility certification. The existing narrow `overused-font=fraunces` exception is retained for the approved identity; no new suppression was added.

The in-app browser injects `codex-browser-sidebar-comments-root` outside BODY. Its document scroll area grew during dialog testing; all app BODY boxes still fit the viewport. On modal return an outer-page scroll was restored by focusing the header. No application workaround was added for browser instrumentation. Physical mobile keyboard, screen-reader execution, reduced-motion OS switching, sustained long-conversation performance and older-adult comprehension testing remain unperformed. The disabling CSS and full accessible text were inspected; reduced-motion behavior is not claimed as an executed OS test.

## Preservation and exact accounting

[Store fingerprints](store-preservation.json) show all three original and four alternative pre-existing guest rows unchanged, all pre-existing readiness rows unchanged, and both database inodes retained. Live synthetic conversation reports were not saved. Saving tests used only the temporary :8892 fixture. No store, credential, launch configuration or ledger was copied or reset. Seventeen historical ledger rows remain retained.

[Original-file accounting](original-preservation.json) compares all 218 captured original app/script/config files: 217 are byte-identical. `cms-slice/scripts/l09_build.py` changed independently during this task's execution; the change belongs to concurrent L09 research and was left intact. No original UI/service source was changed by this task. Both :8890 and :8891 return HTTP 200.

[Contract accounting](field-accounting.json) retains the same 41 question IDs, all 78 original field records, 14 optional report paths and 14 named gap records, with **zero external gaps closed**. Original question records remain unchanged; presentation copy is adapted in the controller. Two bounded journey metadata properties record teaching completion and explicit sample visibility, not customer insurance facts. Unknown answers do not establish readiness. All personal recommendations, eligibility, payer order, exact enrollment rights/deadlines, provider fit, personal drug pricing, Medigap rights, ranking and enrollment retain their independent gates. Commercial economics do not enter these decisions.

## Operations and evidence

[Runtime comparison](runtime-check.json) reports 137 deployable source files synchronized with no differences or runtime-only files. Six source-only before-image manifests are under `alternatives/chat-first/runtime/backups/`: `20261028T152710726304Z`, `20261028T153156339998Z`, `20261028T153331408579Z`, `20261028T153937067564Z`, `20261028T154443649316Z` and `20261028T154923710864Z`. The existing identity-checked sync workflow restarted only `gui/501/com.daylight.chat-alternative.8891`. The temporary :8892 fixture was stopped after checks. A fresh [localhost :8891](http://localhost:8891/) landing was opened for delivery.

The scoped [before manifest](before-manifest.json), retained before-images and [after manifest](source-after.json) distinguish this revision from substantial earlier uncommitted work. `verify_backend.py` reproduces the bounded synthetic suite; `verify_delivery.py` performs read-only preservation/contract/service/usage checks and writes evidence. Its exact three-call assertion describes this delivery checkpoint, not a promise that future user chat will leave the ledger unchanged.

These results establish technical delivery, not owner acceptance, independently accepted insurance evidence or a measured consumer-completion improvement. D73's minimal intake, inspectable decisions, useful teaching, coverage path and permissioned continuity are implemented and checked here; human comprehension and source acceptance remain separate.
