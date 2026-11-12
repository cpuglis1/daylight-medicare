# MidMorning on :8894

November 10, 2026 · D121, refining D04/D55/D58 and preserving D24/D44/D54/D64/D73/D93.

The owner selected **MidMorning** and authorized the visible rebrand on :8894. The running local frontend serves the changes after reload; neither service was restarted.

## Copy and scope

- Brand and browser title: **MidMorning**.
- Hero: **Medicare, on your terms.**
- Supporting sentence: **Understand your options, weigh the tradeoffs, and take your next step.**
- Ask controls: **Ask MidMorning**, with corresponding contextual plan labels.
- Accessible assistant/home labels, privacy text, authored status/error messages, review helpers and the local research header use the new name.
- No em dash, additional trust clause or AI wording in the hero. Existing AI/provider, saving and permission disclosures remain.

Eight frontend source files changed, with no CSS or asset changes. The current direction is recorded in the requirements change log, directive history, current state, product/design context, principles and master decision record. `change.diff` and `static-checks.json` identify the exact files. `before/` retains the source/document baseline; `before-hashes.json` also covers the reference/protected frontend files.

No route, question meaning, action, plan ordering, recommendation gate, source acceptance, budget, saved profile, API header, event name, DOM class, JavaScript global or asset path was renamed or changed. The sun, photograph, typography and layout remain.

## Checks actually performed

- `node --check` passed for all **10 JavaScript files** in `web-8894/`.
- All **6 JSON files** in `web-8894/` parsed successfully.
- Compared changed source files with their before-images: `Daylight*` JavaScript identifiers, `X-Daylight-CSRF`, `daylight:` events, `chat-daylight` classes and the existing AI disclosure occurrences are preserved.
- All **86 hashed reference/protected frontend files** remain byte-identical. The :8894 stylesheets and assets also match the baseline.
- Targeted `git diff --check` passed for the governing documents.
- Inspected the served landing page in the in-app browser at **1440×900, 820×1180, 390×844 and 320×740**. DOM document width equaled viewport width at every size. At 320px the headline naturally uses three lines; the full copy and Get started remain visible and readable.
- Get started opened the existing initial advisor screen. Privacy opened with the MidMorning name and explicit OpenAI/AI-provider disclosure. Closing it preserved a fictional unsent draft containing the word “Daylight” exactly as typed.
- Plans opened the existing coverage-path screen. **Ask MidMorning** opened the chat panel, and Close returned to the same Plans screen. The new panel heading was inspected on desktop, tablet, phone and narrow phone; it wraps at 320px without hiding Close. No question was sent.
- The MidMorning home link returned to the new landing page. Viewport overrides were reset afterward.

Screenshots: `after-desktop.jpg`, `after-tablet.jpg`, `after-phone.jpg`, `after-narrow-phone.jpg`, `conversation-phone.jpg`, `privacy-phone.jpg`, and `ask-*.jpg`. The original desktop landing was inspected before editing in the browser; exact pre-change source is retained in `before/`.

An initial standalone Playwright attempt could not launch because its browser executable was absent. Browser verification was completed using the in-app browser instead. A sandboxed curl probe could not reach loopback; the in-app browser successfully loaded the existing :8894 process. No full backend regression suite was run for this copy-only increment. No paid probes, generated conversations, saved reports or privacy choices were submitted.

## Remaining shared-runtime branding

The shared :8893 backend/model instructions still call the advisor Daylight. Server-authored errors and generated replies can therefore still use the old name. The :8894 proxy's unreachable-service message also retains it. This increment does not rewrite arbitrary responses, quoted sources or user-entered text to conceal that boundary.

That follow-up needs a deliberate shared-runtime copy update and activation check: current-state documentation records unrelated pending backend fixes, so restarting it just for branding could activate those changes too. Code/storage/project names and historical evidence are intentionally retained. No legal entity rename, trademark clearance, public release, deployment or owner acceptance of the rendered UI is claimed.
