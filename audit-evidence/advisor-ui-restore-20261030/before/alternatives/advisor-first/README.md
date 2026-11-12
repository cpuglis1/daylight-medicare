# Daylight advisor-first local variant

D86 · October 30, 2026 · **http://127.0.0.1:8893/**

This is the separate implementation of the [LLM-first hybrid plan](../../docs/product/LLM_FIRST_HYBRID_PLAN_2026-10-30.md). The owner authorized implementation and local activation after reviewing the opening. The original :8890 and chat-first :8891 sources, runtime jobs and guest stores remain separate.

The journey opens with **What has you thinking about Medicare today?** The person can describe their circumstances or use an optional goal shortcut. A bounded LLM planner interprets explicit reports, selects reviewed explanations and proposes an eligible next move. Related missing values use inline forms. Clear choices use one Continue; form values and interpreted reports are staged for review. Preparation has a separate, revision-bound confirmation and produces a real editable checklist with copy/print and an operation receipt.

## Source and runtime

| Item | Location |
| --- | --- |
| Source and live working directory | This folder |
| Frontend | `web/index.html`, `web/advisor.js`, `web/advisor.css` |
| Local server | `server.py` |
| Narrative/report/action controller | `advisor_flow.py` |
| Reused engine | Read-only `../chat-first/cms-slice/scripts/`, pinned by `engine-lock.json` |
| New private guest database | `var/profiles/guides.sqlite3` |
| Cookie | `daylight_advisor_dev` |
| Logs | `var/logs/` · request text is not logged |
| Launchd job | `gui/501/com.daylight.advisor-first.8893` |
| Launch configuration | `runtime/com.daylight.advisor-first.8893.plist` |
| Shared AI ledger | `../../cms-slice/var/ai-budget/usage.sqlite3` |

The engine lock checks every pinned script/configuration before startup. An upstream change requires deliberate review and a new lock, rather than silently changing this variant. No original engine file is edited by this implementation. Static teaching/contract/sample files and approved brand assets are local copies; no guest database or `.env` is copied. Live model settings load only the existing allowlisted variables from the main `.env`.

## Operate locally

Check the job:

```sh
launchctl print gui/501/com.daylight.advisor-first.8893
```

After an authorized source change, restart only this variant:

```sh
launchctl kickstart -k gui/501/com.daylight.advisor-first.8893
```

Stop without deleting any records:

```sh
launchctl bootout gui/501/com.daylight.advisor-first.8893
```

Start it again from this folder:

```sh
launchctl bootstrap gui/501 "$PWD/runtime/com.daylight.advisor-first.8893.plist"
```

The checked-in local plist uses the current machine's Python path and source directory. It is not a public or portable hosting configuration. The service binds only to loopback. Do not restart the other Daylight jobs, restore their databases, or reset the shared ledger as part of this variant's rollback.

## Development and verification

Controlled tests use temporary private databases and synthetic model outputs, with no paid generation:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s alternatives/advisor-first/tests -v
node --check alternatives/advisor-first/web/advisor.js
```

For a disposable UI preview, run from this folder with an unused fixture port and temporary database:

```sh
fixture_dir=$(mktemp -d /tmp/daylight-advisor-fixture.XXXXXX)
PYTHONDONTWRITEBYTECODE=1 python3 server.py --fixture --port 8892 --database "$fixture_dir/guides.sqlite3"
```

The fixture explicitly labels mocked replies and does not certify language-model behavior. [Delivery evidence](../../audit-evidence/advisor-first-20261030/README.md) records controlled tests, actual live AI checks, responsive walkthroughs and preservation checks separately.

## Boundaries

- The original 41 reviewed IDs, 78 field records, 14 additive report paths and 14 gaps remain traceable. They are conditional dependencies, not a mandatory questionnaire.
- The model chooses among allowed moves and reviewed fact IDs. It cannot invent insurance prose, bypass missing dependencies, rank plans or expand permissions. The current supported operation is education/preparation; the research/recommendation capabilities remain held.
- Messages and drafts are visit-only. Saving uses the existing opt-in policy with a separate sensitive-detail choice, seven-day guest scope, same-browser resume and explicit deletion. Previous sensitive values and raw history are not automatically sent to AI.
- Reviews expire after ten minutes and are bound to the owner and exact input snapshot. An edit invalidates the affected confirmation. Operation keys prevent duplicate preparation execution. Edited checklist versions remain available in the current visit under Review information.
- The existing $1/UTC-day cap, model/pricing review, bounded token limits and no automatic AI retries remain. The new UI does not display consumer spend banners.
- Sample browsing remains five unvalidated **2027 Collier County** records. Reported 2026 timing is not silently replaced, and no sample establishes personal fit or complete coverage.
- All source/eligibility/provider/drug/price/Medigap/recommendation/enrollment holds, commercial independence and sealed evidence obligations remain intact. A preparation receipt is not an outside verification or a sent request.
- Physical mobile keyboards, assistive-technology execution and observed consumer comprehension/A/B/C comparisons remain separate validation work. No confidence, savings or superiority claim is made from technical tests.
