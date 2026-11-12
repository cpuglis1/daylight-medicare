"""Prepare bounded, conflict-checked Brain additions; does not write the vault."""
import hashlib
import json
from pathlib import Path

root = Path('/Users/cep4u/Library/CloudStorage/GoogleDrive-chris@daylightmedicare.com/My Drive/Daylight/Daylight Brain')
changes = []
def edit(name, replacements):
    path = root / name
    original = path.read_text()
    updated = original
    for before, after in replacements:
        assert updated.count(before) == 1, (name, before)
        updated = updated.replace(before, after, 1)
    changes.append({'path':str(path), 'before_sha256':hashlib.sha256(original.encode()).hexdigest(), 'after':updated})

note = '''---
type: infrastructure-note
status: draft
updated: 2026-11-12
owner: Chris Puglisi
---

# Local demo and AWS differences

Chris requested a smaller, verified demo database while keeping the complete research database, then a separate localhost port combining the current frontend and backend before AWS. He also requested this comparison in the second brain. Repo decisions D144–D145. These are implemented local changes; AWS deployment remains open.

## What to use now

Open [Daylight local demo](http://localhost:8895/). One Python app process serves the current interface and API directly on port 8895. PostgreSQL is still a separate local process accessed over its private Unix socket. The frontend does not forward requests through 8893 or 8894.

The service was started November 12. To start it again after it stops, run `Start Daylight Demo.command` in `~/daylight`; keep its Terminal open. It is not installed as an automatic service and will not survive a computer restart. If 8895 is already running, use the existing page instead of starting a second copy.

The frontend files are shared with the current 8894 source, so subsequent frontend edits will appear on both surfaces after reload. Backend code is shared but a running process retains its loaded version until restarted. Guest data and browser cookies are separate.

## Environment comparison

| Area | Existing 8893 and 8894 | Unified local demo 8895 | AWS pilot target, still to deploy |
|---|---|---|---|
| Browser and API | 8894 serves the current UI and proxies its API to 8893 | Current UI and direct API in one loopback process | One HTTPS origin behind the selected CloudFront/WAF controls; exact release still to configure |
| Plan data | Original research-backed adapters plus MA catalog files | Verified 195 MB display DB plus the same seven pinned catalog/authority dependencies | Restore and verify the small DB and catalog bundle on the selected private host; managed RDS and whole-research migration deferred |
| Saved reports and cookies | Existing advisor store and cookie namespace | Separate `var/demo-8895/guides.sqlite3` and `daylight_demo_8895_dev` cookie | Invite-bound guest access; durable saved profiles disabled in the current hosted pilot scope |
| Chat and refresh | Visit-only chat; bounded server-memory recovery | Same behavior in its own process; a restart loses visit recovery | Reverify on the actual hosted process and against deployment/restart behavior |
| Model spending | Existing shared development allowance | Shares that same $15 per provider per UTC day allowance; no additional allowance | One $100 cumulative pilot budget with per-participant tracking; production adapter/ledger binding and host checks remain open |
| Access | Localhost development | Loopback only, its own Host/Origin/CSRF checks; no invitation gate | Invitations, revocation, HTTPS/private origin, retention and launch checks required |
| Current status | Existing processes preserved | Running locally; fixture checks and free live health check passed | Not deployed by this work |

## Large and small databases

- Full research DB `daylight_research_2026_r2`: 31,011,337,919 bytes, about 31.01 GB at verification. The earlier “29 GB” estimate predates later imports. It remains intact.
- Demo DB `daylight_pilot_collier_2026_r1`: 195,002,895 bytes, about 195 MB, 99.37% smaller. Complete eight-table Medigap schema with 320 profiles, 55,040 rate rows, 3,840 benefit rows and source controls. Part D has exact stored responses for all 10 retained 2026 Collier offerings, their restrictions and county record.
- Medicare Advantage remains file-backed: 72 retained offerings and seven catalog/authority dependencies totaling 10.46 MB. Nothing is removed on commercial grounds.
- Verified compressed DB export: 12,179,881 bytes, about 12.18 MB. Artifact directory: `infrastructure/daylight-data/.state/pilot-subset/2026-11-12-r1/` inside the repo. Keep licensed data private; no database contents or credentials are stored in this note.

## Verification and limits

The original and subset matched across all 320 Medigap profiles; the app adapter verification passed 98 assertions. The unified service passed 34 targeted HTTP, isolation, refresh, plan-panel and proxy regression tests. Fixture browser inspection covered desktop, tablet and phone; no paid/live model conversation tests ran. Live health reported the demo database and OpenAI GPT-5.4 available. Existing frontend/proxy files, saved guide rows and budget charge/attribution rows were preserved; only the budget's UTC date guard advanced during health checking.

This is a 2026 Collier display baseline. Medigap prices are the retained November 10 observations for ZIPs 34101–34108 and ages 65–74. Other profiles stay unsupported; no price interpolation or eligibility inference. Part D does not provide verified personal drug costs. All source, method and recommendation holds remain.

The subset is a snapshot. New source STOPs are not automatically replicated from the research database. Run the source-control preflight before a demo or export; any change requires reconciliation and a new verified revision. The retained Part D review deadline is November 24 at 00:00 UTC (November 23 at 7 p.m. Eastern). The model-pricing review currently expires November 18 at 03:09:40 UTC. Neither date is extended by copying or starting the demo.

## Why do this before AWS

This removes the extra frontend proxy from the demo and exercises the small database through the real app. It gives the cloud move a known local baseline with separate demo records. It does not prove target-host restore, private network access, hosted invitation controls, cumulative budget enforcement or participant readiness; those remain in the AWS launch workstream.

No AWS resources, budget alerts or paid model tests were changed. The quoted monthly hosting figures are estimates from the migration discussion, not a priced deployment or approved spend. The $20 AWS alert should be revisited against the selected architecture and actual estimate when provisioning is approved.

## Sources

- [[08 Infrastructure and accounts]]
- [[04 Data]]
- [[05 Pilot and validation]]
- [[Decisions]]
- Repo `audit-evidence/unified-demo-8895-20261112/README.md`: startup, checks, screenshots, live status and preservation receipts.
- Repo `audit-evidence/collier-pilot-subset-20261112/README.md`: exact subset contents, full parity and source-control preflight.
- Repo `infrastructure/daylight-pilot/README.md`: remaining hosted deployment work.
- Owner chat, November 12, 2026: retain both databases, use a separate unified local demo before AWS, track differences in the second brain.
'''
newpath=root/'Inbox/Local demo and AWS differences.md'
assert not newpath.exists(), 'Do not overwrite an existing note.'
changes.append({'path':str(newpath),'before_sha256':None,'after':note})

edit('08 Infrastructure and accounts.md', [
('status: stub\nupdated: 2026-11-11','status: draft\nupdated: 2026-11-12'),
('> Stub. Drafted in reorganization step 7. Until then, use the sources below and ask Chris.', '> Partial draft: local demo and AWS differences are recorded below. The broader account inventory still awaits reorganization step 7.'),
('## Direction\n','## Direction\n\n- D144–D145, November 12: retain the full research database, use a verified small demo database and establish a separate unified local app before AWS. Record the environment differences here.\n'),
('## Current status\n','''## Current status

[Local demo on port 8895](http://localhost:8895/) runs the current frontend and API in one app process against the 195 MB demo database. It uses its own guest store and cookies, shares the existing development model budget and does not depend on 8893/8894. Both older services remain running. PostgreSQL remains a separate local process. This is a local integration baseline; hosted access, the cumulative pilot budget and deployment review remain open.

See [[Inbox/Local demo and AWS differences]] for the environment comparison, startup instructions, verification and freshness limits. No AWS resource or budget alert was changed by this work.
'''),
('## Sources\n','## Sources\n\n- [[Inbox/Local demo and AWS differences]] (D144–D145, November 12).\n')])
edit('04 Data.md', [
('status: stub\nupdated: 2026-11-11','status: draft\nupdated: 2026-11-12'),
('> Stub. Drafted in reorganization step 6. Until then, use the sources below and ask Chris.', '> Partial draft: the verified local demo subset is recorded below. The broader dataset review still awaits reorganization step 6.'),
('## Direction\n','## Direction\n\n- D144, November 12: preserve the complete research database and create a separate, lean verified Collier demo database. Delete nothing.\n'),
('## Current status\n','''## Current status

The full research DB remains intact (31.01 GB measured; previously described as 29 GB). A separate verified 195 MB demo DB retains the complete Medigap cache/control schema and exact Part D app responses. The 72 MA offerings remain file-backed. Port 8895 now uses that subset. All 320 Medigap profiles passed parity; source STOPs, scope/freshness checks and recommendation holds remain. The compressed export is 12.18 MB.

See [[Inbox/Local demo and AWS differences]] for exact contents, source-preflight requirements and the distinction between data copied, app access and accepted consumer use. This subset does not change the full research database's readiness or the broader data gaps.
'''),
('## Sources\n','## Sources\n\n- [[Inbox/Local demo and AWS differences]] (D144–D145, November 12).\n')])
edit('Decisions.md', [
('updated: 2026-11-11','updated: 2026-11-12'),
('## 2026-11-11\n','''## 2026-11-12

- **Local demo before AWS (D144–D145).** Chris requests a lean verified database alongside the intact full research database, then a separate localhost port combining the current frontend/backend with that subset before the AWS move, with the differences tracked in the second brain. Port 8895 is the implemented local baseline. This replaces whole-research-database migration as the immediate pilot-data task; the existing 8893/8894 services remain available. It does not change the pilot schedule, authorize cloud provisioning or establish a new spending amount. See [[Inbox/Local demo and AWS differences]].

## 2026-11-11
''')])

Path('audit-evidence/unified-demo-8895-20261112/brain-update.json').write_text(json.dumps(changes,indent=2)+'\n')
print('Prepared one new note and three targeted updates; vault not yet changed.')
