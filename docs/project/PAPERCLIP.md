# Daylight Paperclip

Installed November 5, 2026 at the owner's request as a local development
coordinator. This is separate from Daylight's advisor, customer data and research
services. The owner's solo-founder stack evaluation is future context, not
authorization to purchase vendors, select a cloud or deploy its recommendations.

## Open and use

**Current status:** the dashboard and background service are running, and both
agents are **unpaused** and connected through existing subscriptions. On
November 5 the owner explicitly authorized removing Paperclip's dollar hard
stops and 30-run daily caps, then resuming both agents. Provider subscription
limits apply. One concurrent task per agent and runtime sandboxing remain.

- [Daylight dashboard](http://127.0.0.1:3100/DAY/dashboard)
- [Start here](http://127.0.0.1:3100/DAY/issues/DAY-1)
- [Collier 2026 pilot](http://127.0.0.1:3100/DAY/projects/collier-2026-pilot)
- [Codex](http://127.0.0.1:3100/DAY/agents/codex)
- [Claude](http://127.0.0.1:3100/DAY/agents/claude)

Create a task, select **Collier 2026 pilot**, describe a concrete output and assign
an agent. Put it in **Todo** to begin. Inspect the task's run, comments and
artifacts. For an independent review, give the other agent the exact artifact or
diff and relevant checks. A review needs evidence; model agreement is not proof.
The seeded backlog is unassigned and does not run automatically.

**Owner operating preference:** on-demand work, not autonomous 24/7 operation.
Keep timer heartbeats and recurring schedules off. Agents may complete an
explicitly initiated task and its authorized handoffs, then wait for the next
owner request. Suggested backlog items are proposals, not permission to run.

## Coding quick start

1. Open **New Task**, choose **Collier 2026 pilot**, and name one concrete change.
   Include the current problem, desired behavior, target surface, and how to
   verify it. Use the existing DAY-2 development-baseline task as a first exercise
   if you want to establish which checks work in this selected source snapshot.
2. Assign **Codex** or **Claude**, then set **Todo**. One agent implements the
   task in its own project worktree. The other agent can review it afterwards;
   do not assign both to edit the same files at the same time.
3. Follow the task's run and comments. Reply on that task when the agent reports
   a missing input or needs a decision. Require changed-file paths, the actual
   test results, and an attached patch or exact commit reference.
4. Create a separate review task for the other agent. Link the implementation
   task and its actual patch/artifact. Ask for concrete defects, requirement
   regressions, and missing checks. Review conclusions do not replace Daylight's
   source or consumer-purpose acceptance.
5. Review the result, then deliberately integrate the approved patch into the
   main Daylight workspace. Paperclip worktrees are separate development copies;
   completing a task does not update the live app or merge into the original
   repository. Refresh the selected snapshot when later source changes matter.

Example task description:

> Implement [specific change] in the :8893 advisor-first surface. Desired
> behavior: [observable result]. Read the applicable Daylight requirements and
> preserve the protected variants and release gates. Use fictional data. Run
> relevant checks, report failures honestly, and attach a reviewable patch with
> changed paths and verification results. Do not deploy.

Keep follow-up changes on the original implementation task until the patch is
ready. Use **Backlog** for ideas you are not ready to run. Agent pauses stop
execution; leaving the browser closed does not stop a running task.

## Installed configuration

The owner explicitly prefers existing subscriptions over separately billed
provider API keys. Both agents already use signed-in local CLI sessions:
Codex reports ChatGPT authentication; Claude reports the Beacon Max account.
Paperclip records both providers' test usage as `subscription_included`.
Subscription login is explicitly selected in each CLI's settings. Do not switch
to API-key billing without new owner direction. The historical dollar-budget
pause below was an accounting-receipt issue, not a requirement to use API billing.

| Item | Configuration |
| --- | --- |
| Paperclip | Official npm package, pinned `2026.1023.0` |
| Runtime | Dedicated Node `24.22.1` under `~/.paperclip/runtime/bin` |
| Server | Trusted local mode, bound only to `127.0.0.1:3100` |
| Persistence | macOS user LaunchAgent `ing.paperclip.paperclipai.daylight`, starts at login |
| Database | Embedded PostgreSQL, loopback port `54329` |
| Data | `~/.paperclip/instances/daylight/` |
| Telemetry | Disabled in persistent config and instance environment; company feedback sharing off |
| Codex | Installed CLI, `gpt-6.1-sol`, medium reasoning, existing ChatGPT subscription |
| Claude | Dedicated Claude Code `2.1.318`, `sonnet`, authorized Beacon Claude Max subscription |
| Agent permissions | Permission/sandbox bypass disabled; no agent creation or skill creation |
| Execution | One concurrent run per agent; project tasks get isolated Git worktrees |
| Scheduling | Timer heartbeats off; assignments and explicit follow-ups can start work |
| Usage limits | Provider subscription limits; no extra Paperclip dollar or daily-run caps |
| External connections | No GitHub write connector, production credentials, or publication remote added |

The earlier $20/company, $10/agent, and 30-run limits were removed with explicit
owner authorization. Codex's smoke run reports `subscription_included` and no
dollar cost. These settings do not change Daylight's own runtime budget policies.

Paperclip's isolated-workspace feature flag is explicitly enabled; merely saving
the project's workspace policy was insufficient in this release. CLI symlinks
inside the dedicated runtime directory allow the background service to locate
Codex and Claude without changing the machine's global Node version or PATH.

Paperclip's Claude launcher points to a private official npm installation under
`~/.paperclip/runtime/claude-code/`. The regular Homebrew Claude installation is
unchanged. Version 2.1.318 supports the port-specific sandbox network allowlist;
the earlier 2.1.169 CLI rejected that setting. Shell requests to Paperclip use
`curl --noproxy ""` through the sandbox proxy, with only loopback port 3100
allowlisted. Sandbox and permission bypass remain disabled.

## Development source and boundaries

The original `/Users/cep4u/daylight` folder contains extensive uncommitted work.
It was not reset, staged, committed or used as an agent's working directory.

`tools/paperclip/prepare_workspace.py` created a separate local source snapshot
from the existing 361-path publication manifest plus explicit current code and
scope-document additions: **446 copied files**, about **15.9 MB**, with a new
hash manifest. This is a development selection, not a claim that current changed
contents have publication approval or that the whole research archive is present.

- Base repository: `~/.paperclip/workspaces/daylight-source-20261105`
- Base commit: `c0ff4ec` (local-only initial snapshot)
- Agent fallback worktrees: `~/.paperclip/workspaces/daylight-codex` and
  `~/.paperclip/workspaces/daylight-claude`
- Project task worktrees: `~/.paperclip/workspaces/tasks/codex/`
- Exact source selection: `PAPERCLIP_WORKSPACE.json` inside the snapshot
- Agent entrypoint: `tools/paperclip/AGENT_INSTRUCTIONS.md`

No real guest databases, private conversations, raw research archive or live
environment files were copied. The existing placeholder `.env.example` is
included. Linked evidence may be absent: request a task-specific authorized
input instead of reaching into the original workspace. Working copies do not
automatically sync later Daylight changes. Create a new versioned snapshot or
reviewed patch when needed, and return agent patches to the main workspace for
deliberate integration.

Worktrees prevent edit collisions; they are not full host isolation. The
development agents still run as the local macOS user. Do not treat this machine
as a production/customer-data environment. Native runtime permissions remain
enabled, and no customer-data authorization follows from this setup.

## Verification and known limits

- Service health and pinned server version verified; restart completed.
- Codex environment test performed a real model response successfully.
- [DAY-6](http://127.0.0.1:3100/DAY/issues/DAY-6) verified task assignment,
  shell/file tools and saved comments. It used the separate development base
  snapshot before the isolated-workspace feature was enabled; the correction is
  explicitly recorded on that task.
- [DAY-7](http://127.0.0.1:3100/DAY/issues/DAY-7) verified the corrected policy:
  actual `codex/` branch, separate per-task worktree, exact file readback,
  attached artifact and completed task.
- Fictional advisor fixture preparation succeeded in the Codex fallback
  worktree; source acceptance and consumer release remain unchanged. The full
  current advisor suite is a separate starter task, not claimed passed here.
- Claude is connected to the owner-authorized Beacon account,
  `chris@beaconfederaladvisory.com`, with a verified Max subscription and a
  successful real model response. Its separate login directory is
  `~/.paperclip/instances/daylight/claude-beacon`; the existing personal Claude
  login was preserved. No API key was pasted into Paperclip.
- [DAY-8](http://127.0.0.1:3100/DAY/issues/DAY-8) created the correct isolated
  Claude task worktree, then encountered the old CLI's network allowlist
  incompatibility. That run was cancelled. The dedicated CLI upgrade passed a
  separate sandboxed `curl` health check with the original port-specific
  allowlist and no permission denials. After the owner authorized resuming, run
  `6b9b13f0-8a89-4d5d-8113-f9c2f9f5844b` **succeeded**: isolated task branch,
  exact 21-byte Codex artifact comparison, exact 19-byte Claude file readback,
  saved result comment, and completed task. Its final receipt is ready and
  classified `subscription_included`. The file was independently read back by
  the setup assistant. This is a bounded tool/coordination check, not product
  validation or a claim about arbitrary coding tasks.

### Historical accounting hold and owner decision

Cancelled run `8807da88-4fb7-4f4d-a29f-da9822696f90` has an unfinished provider
usage receipt (`accountingReceiptReady: false`). It reports subscription-included
usage but has no final provider result. Paperclip records one pending run; this
previously paused the company and Claude under dollar-budget hard stops, even
with $0 recorded billed spend. The supported accounting retry returned
`accounted: false`; no complete receipt was available to reconstruct.

The owner initially chose **“Keep hard stops; leave agents paused.”** After
confirming that both agents use subscriptions, the owner explicitly superseded
that decision: **“I authorize removing those caps and unpausing both.”**
Paperclip's three dollar-budget policies are now inactive with zero configured
limits, and both daily-run caps are removed. Provider limits apply; the pending
record remains visible rather than being fabricated or erased. Do not describe
recorded $0 as complete accounting. The network problem was resolved separately
by the private CLI upgrade while retaining port 3100 restrictions; wider
localhost access was never applied.

The next product work comes from the current `COLLIER_MVP.md`. All-72 research
access is already delivered; source/method/purpose acceptance, personal checks
and consumer release remain separate. Preserve D64, D73, D86, D91, 41 conditional
meanings, source STOPs and the protected app variants.

## Start, stop and backup

From the original Daylight directory:

```sh
sh tools/paperclip/daylight.sh status
sh tools/paperclip/daylight.sh stop
sh tools/paperclip/daylight.sh start
sh tools/paperclip/daylight.sh restart
sh tools/paperclip/daylight.sh backup
```

Paperclip also configures hourly local database backups with 30-day retention
under `~/.paperclip/instances/daylight/data/backups/`. These are same-machine
backups, not disaster recovery. Keep instance secrets, artifacts and development
repositories alongside the database in any future encrypted off-machine backup;
a database dump alone does not contain every file or credential needed to restore.

The initial manual database backup completed successfully at
`~/.paperclip/instances/daylight/data/backups/paperclip-20261105-151156.sql.gz`.
The earlier setup backup, including the owner's initial keep-paused decision, is
`~/.paperclip/instances/daylight/data/backups/paperclip-20261105-152920.sql.gz`.
The resumed configuration, completed Claude test, and coding guide are backed up
in `~/.paperclip/instances/daylight/data/backups/paperclip-20261105-154328.sql.gz`.

An upgrade is deliberate: the managed install is pinned. Read release changes,
take a backup, update the named version and repeat agent/workspace checks. Keep
experimental features scoped to the features actually in use.
