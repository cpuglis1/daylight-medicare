# Medicare.gov public observation collector

C16 implementation: `cms-slice/scripts/medicare_collector.py`. Optional browser dependency: Playwright **1.64.0**, headless Chromium via the installed Chrome channel. Application/offline query tools do not require Playwright. Use a fresh isolated browser context; do not attach to a resident's profile.

The October 20 preflight received **HTTP 403** from the public app bootstrap endpoint `/api/v1/data/plan-compare/ldflags`. The persistent kill switch is active. Do not retry through another browser, IP, proxy or request implementation. See [the source receipt and run](../cms-slice/reports/collier-gap-20261020/c16-c23/c16-browser-preflight-9/run.json). No new plan, drug-price or Medigap availability observations were obtained. C17/C18/C20/C22 remain blocked.

From the repository root, these commands are safe offline:

```sh
python3 cms-slice/scripts/medicare_collector.py status
python3 cms-slice/scripts/medicare_collector.py plan --task C17 --out /tmp/c17-plan.json
python3 cms-slice/scripts/medicare_collector.py plan --task C20 --out /tmp/c20-plan.json
python3 cms-slice/scripts/medicare_collector.py plan --task C22 --out /tmp/c22-plan.json
python3 cms-slice/scripts/medicare_collector.py stop
```

`plan` is the default behavior for preparing a task; it makes zero network requests and works with an active STOP. The CLI requires an explicit command and accepts no arbitrary URLs, real drug lists or resident data. The immutable fixed query manifest has all 70 CMS IDs, four ZIPs (`34102`, `34109`, `34145`, `34142`, Collier selected), 10 synthetic drug scenarios, 61 drug-plan targets and retail/mail channels, and 12 Medigap letter/high-deductible families. ZIPs are search inputs, not residence eligibility determinations. Drug/form/strength/quantity units and exact pharmacy identities must be confirmed before C20 execution. The current scenario adapters are deliberately not admitted: current UI/network schemas and complete enumeration have not passed source validation.

`preflight` uses the optional Playwright environment for one public entry page, with at most ten new requests. `run --task ...` requires an admitted adapter, the exact pinned task manifest, a fresh policy review and the **00:00–06:00 Eastern** live-batch window. It captures raw pages/responses for parser review; a raw capture never becomes a verified field merely because navigation completed. Full task-specific parsing and workflow validation remain part of the blocked observation tasks. An empty app root is a failure, not a completed page.

Every actual browser request is intercepted. Only explicitly reviewed same-host URLs are admitted, subject to the saved robots rules. External fonts/analytics are excluded before transmission. Normal first-party anonymous security initialization was narrowly reviewed; the collector never constructs signatures, solves challenges or bypasses authentication. Its allowed security POST stores only a body hash, not the browser sensor payload. All other POSTs remain rejected. Service workers, WebSockets and downloads are disabled. Redirects are not automatically followed.

One global file lock prevents overlapping page runs. All requests, including scripts and fonts, share at least five-second pacing and a 2,000-request cap. The cap persists per refresh cycle, a stricter bound than resetting it for every page/run. Identical method/URL/body queries use a hash-verified cycle cache and retain original retrieval dates. Missing/changed cached bytes stop rather than silently refetch.

`cms-slice/var/medicare-collector/STOP` is checked before every request/cache hit and during pacing. A 403, 429, CAPTCHA/block page, unexpected status/redirect, transport failure, changed pinned app script, missing root, unreviewed path/method or expired policy review stops the work. Run events, raw response hashes, source URLs, UTC times, query inputs and parser versions are retained. No login/account/beneficiary workflow or H09 real-user query is authorized.

There is no automatic STOP reset or background retry. The preflight's local path-review and readiness corrections were recorded separately from the final origin denial; that final stop has never been cleared. Any resumption needs a documented source-access resolution and a new engineering review of current policy/paths/schema, not simply deleting STOP. C11 remains the official-access inquiry. A changed source or rebuilt package never renews unrelated review deadlines.

Offline checks:

```sh
python3 -m unittest discover -s cms-slice/tests -p test_medicare_collector.py -v
python3 -m unittest discover -s cms-slice/tests -p test_phase_one_evidence.py -v
```

The tests cover request pacing across contexts, concurrent serialization, cache tampering, operator stop during a wait, origin blocks and challenges, redirect rejection, unknown paths/methods, the request cap, no retry, narrow security POST bodies, and preservation of premium/unit/unknown states. Live source failures are preserved as evidence; fixture tests do not imply live-source compatibility.
