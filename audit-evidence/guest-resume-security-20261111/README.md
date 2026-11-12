# D141 guest refresh and AWS security preparation

November 11, 2026 · requirements D54, D61, D86/D90, D93, D99/D101 and D140–D141.
Implemented and technically verified locally. Consumer acceptance, source
acceptance and deployed security are separate and remain subject to their gates.

## Result and scope

- :8894 keeps only a request reference, page, saving-choice booleans and expiry
  in tab sessionStorage. No report, transcript, draft, credential or model
  response is stored there. The reference cannot authorize access by itself.
- `POST /api/conversation/resume` uses the existing guest cookie, CSRF and
  origin checks to retrieve the latest trusted response from the in-memory
  journal. It rechecks authority, grants no saving permission and never sends
  a model request. In-flight work is polled; a previous accepted reference can
  recover after a request fails to reach the server.
- An ordinary reload restores accepted reports, the latest reply and the
  current plan tab. New tabs remain at the landing page. A later reopened tab
  offers Resume. Existing saved reports retain their separate explicit choices.
- The local proxy rejects foreign origins/hosts, ambiguous request framing,
  oversized bodies and incomplete or stalled bodies before forwarding. Pilot
  pacing and chat switches also cover choices requesting AI composition.
- The [AWS runbook](../../infrastructure/daylight-pilot/README.md) and
  [edge policies](../../infrastructure/daylight-pilot/edge-policies.json) prepare
  CloudFront/WAF for the invite-only pilot. One **$100 cumulative model cap**
  remains the approved allowance. Public limits require later re-evaluation.

## Exact checks run

Environment: macOS; Python 3.14.7; Node v20.16.0. The activated :8894 proxy
retains its existing Python 3.10 interpreter. The workspace is uncommitted;
`before.json`, the narrow `before/` copies and `after.json` identify source
bytes rather than claiming the Git HEAD contains this implementation.

| Check | Observed result |
| --- | --- |
| Initial Python HTTP, recovery, pilot access/budget, proxy and provider-budget suites | 70 passed; [log](python-tests.log) |
| Final HTTP/recovery suites after adding reconnect request references | 31 passed, including reset/resumed references that can themselves reopen; [log](python-recovery-final.log). These overlap the 70, not 31 additional distinct tests. |
| Production :8894 JavaScript request/turn, refresh marker and plans handoff tests | 45 passed; [log](javascript-8894-tests.log) |
| Same harness against the reference `web/` | 45 passed before the final harness-helper correction; [log](javascript-tests.log) |
| CloudFront/WAF local JSON and privacy invariants | Passed; [log](edge-policy-checks.log). No AWS schema or deployed validation claimed. |
| Targeted `git diff --check` | Passed for tracked diffs. Most variant files are already untracked in this workspace; hashes record their actual revision. |
| Local activation | :8893 and :8894 return 200, new resume endpoint returns `expired` for a fictional unowned reference, foreign origin returns 403 and the new browser script serves successfully. [Results](activation-checks.json), [probe](activation_probe.py). Zero conversation-turn or model requests. |

Python suites used a process audit hook that rejects all non-loopback socket
bind/connect/address-resolution operations. They used temporary fictional
databases. Local sockets required sandbox escalation; external access stayed
blocked. The initial suite names were `test_http`, `test_session_recovery`,
`test_session_recovery_http`, `test_pilot_security`, `test_ui_proxy`,
`test_advisor_budget` and `test_provider_budget`. Final reproduction from the
repository root:

```sh
python3 - <<'PY'
import sys, unittest
from pathlib import Path
def loopback_only(event, args):
    if event in {'socket.bind', 'socket.connect', 'socket.getaddrinfo'}:
        host = args[0] if event == 'socket.getaddrinfo' else args[1][0]
        if host != '127.0.0.1':
            raise PermissionError('Offline test permits loopback only')
sys.addaudithook(loopback_only)
sys.path.insert(0, str(Path('alternatives/advisor-first/tests').resolve()))
suite = unittest.defaultTestLoader.loadTestsFromNames([
    'test_http', 'test_session_recovery', 'test_session_recovery_http'])
result = unittest.TextTestRunner(verbosity=2).run(suite)
sys.exit(not result.wasSuccessful())
PY
DAYLIGHT_TEST_WEB=web-8894 node --test alternatives/advisor-first/tests/test_ai_send.js alternatives/advisor-first/tests/test_visit_resume.js alternatives/advisor-first/tests/test_plans_handoff.js
```

The first :8894 JavaScript run exposed a missing test-harness dependency on the
production `plain` notice helper. The harness now reads both relevant helpers
from the selected production source; the final run passes. The first attempt
to detach the local UI proxy exited with its shell; it was restarted using a
separate process session and the activation checks then passed.

## Browser observations

The [temporary browser fixture](fixture_server.py) used the production build
in fictional mode, a temporary database and loopback-only networking. No live
conversation or paid probe ran. Its process and preview tabs were closed after
inspection.

- A fictional caregiver choice survived reload at the next question. Another
  answer succeeded after restoration and survived a second reload.
- Medigap and Part D tabs reopened after reload with the visit intact.
- A separate fresh tab opened at the landing page without revealing reports.
- A controlled reload with an unsent draft left the current page and draft in
  place. The browser's native warning was not exposed by the automation API,
  so its dialog presentation is not claimed as verified.
- Desktop 1440×1000, tablet 820×1180 and phone 390×844 were visually inspected.
  Document width equalled viewport width in all three; [measurements](browser-layouts.json).
  [Desktop](desktop-resumed.jpg), [tablet](tablet-resumed.jpg), [phone](phone-resumed.jpg).

## Limits and launch work

Recovery depends on the existing one-hour, capacity-bounded memory journal.
Restart, expiry, eviction, revocation and deletion can end it. Unsent drafts
and earlier displayed chat are not saved. Browser storage restrictions and
mobile leave-page behavior can limit recovery and warnings. The UI explains
restoration failure; it does not silently generate a replacement reply.

Only :8893/:8894 were restarted. No protected variant, customer store, pinned
engine, source acceptance or recommendation gate was deliberately changed.
The shared controller changed concurrently during the task; its original and
final hashes are retained, and this task's recovery logic lives in the separate
`session_recovery.py` seam.

The active local development runtime retains its existing development budget.
The invite-only cumulative ledger is implemented/tested in the isolated pilot;
its live model adapter is not yet bound. No AWS resources were provisioned.
Before participant admission: bind every paid stage to that ledger, verify the
provider route/account, validate and deploy the AWS policies, prove private
origin isolation and cache behavior through HTTPS, verify retention/backup and
incident operations, and complete the release/privacy/source gates in the
[launch runbook](../../infrastructure/daylight-pilot/README.md). WAF rate values
are provisional, and provider/AWS budget alerts do not establish a hard model
cap. The application ledger must enforce the $100 cumulative ceiling.
