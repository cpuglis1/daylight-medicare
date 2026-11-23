# D222: selected-plan conversation and confirmed-office reuse

Prepared November 23, 2026 from GitHub `dev` commit
`27a341c02cee7157fb7985df2d4adf5b02471f0d`. Work is isolated from the original
workspace. No newer local changes, real conversations, customer stores, AWS
configuration or live invitations were modified.

## Cause and change

The browser already sends `plans-context-v1`, and `NaturalConversation.turn`
already validates and rehydrates the selected/compared fields. The one-call
`_model_turn` omitted that context from both the model input and its reply
grounding. Its instructions also told the model never to name plans returned by
`get_plan_status`, and to open Plans even when answering an existing comparison.
Those omissions explain why both local and hosted one-call comparisons denied
details visible on screen.

The patch passes the current server-rehydrated fields and citable evidence IDs
to the one-call request and reply validator. It reuses the existing D189 adapter
for Medigap and Part D selections. Changed profile inputs refresh evidence before
reply validation or repair. Consent, stale-view rejection, publication states,
conditions and unknown values remain enforced. No new model stage is added.

Exact doctor/office picker selections were also absent from the automatic
one-call input. Current selections and results now reach the advisor through the
existing check controller. A source withdrawal removes the finding while keeping
the person's confirmed office. A corrected doctor invalidates the old selection.
Old doctor/medicine tool results are excluded from reply grounding when a current
controller context is available. Original Medicare assignment and Advantage
network participation remain separate. Unknown network cards now distinguish an
office already confirmed from a check with no result; no missing edge is invented.

Advantage, Medigap and Part D plan lists no longer show the numbered enrollment
strip above their content. Enrollment data and its dedicated steps remain.

## Hosted baseline and verification

The retained release `808fe01b2bbf6977ec254aceb6f5b252d547fb875756e6c64bc6f92577c42210`
was reconstructed from existing release archives. All **544 manifest file hashes**
matched before applying the patch. Its `one_call_flow.py`, `one_call_prompt.py`,
`one_call_plan_checks.py` and `web-8894/plans-workspace.js` are byte-identical to
the pinned `dev` versions. This is evidence of a shared code defect, not a claim
that the current live service was inspected during this task.

All model responses below are scripted; all visits and invitations are fictional.
Temporary ledgers/history doubles are used. No paid model or live conversation
probe was run.

| Check | Result |
| --- | --- |
| `test_one_call_plans_context`, `test_one_call_plan_checks`, `test_one_call_prompt`, `test_one_call_check`, `test_one_call_agent` | 126 passed |
| Patched retained release: `test_one_call_hosted_plans`, `test_hosted_one_call.Integration`, `.OneCallSelectors`, `.WorkerBudget` | 14 passed |
| Node `test_plans_header.js`, `test_planner_routes_20261114.js`, `test_plans_handoff.js` | 5 test entries passed, including 7 workspace-route assertions |
| JavaScript syntax and `git diff --check` | Passed |
| `test_one_call_flow` and `test_one_call_first_visit` | 83 run: 80 passed; 2 failures and 1 error reproduced on untouched `dev` |
| `test_one_call_tools` | 38 run: 36 passed; 2 failures reproduced on untouched `dev` |

The new hosted test sends the comparison question through the authenticated HTTP
handler under both owner/default and accelerator/ultrafast policies. The handler
returns the two fictional published premiums, retains low reasoning, uses the
existing hosted ledger and archives the response before delivery. Unauthenticated
requests remain rejected. Existing hosted tests cover selectors, reset-descendant
budget enforcement and attribution of background work. This exercises the hosted
adapter in memory, not AWS or the real PostgreSQL history store.

The five pre-existing failures concern four subject-change expectations and the
absent `Start Daylight One-Call 8897.command` file. They were not suppressed or
changed to make this patch pass. The broader suite is therefore not fully green.

## Remaining work and release boundary

- No browser/computer-control tool or screen-permission request is exposed in
  this session. Firefox and the AWS account could not be inspected. No deployment
  or local server restart occurred.
- The execution sandbox rejects access to the existing PostgreSQL Unix socket
  with `Operation not permitted`; the actual reported doctor's network evidence
  could not be checked. Do not turn its unknown network result into a positive
  finding on the basis of Original Medicare enrollment or assignment.
- Desktop, tablet and phone rendering and real-model conversational quality
  remain unverified. The header test executes its rendering code with DOM stubs;
  it is not a screenshot or browser walkthrough.
- GitHub `dev` lacks the hosted adapter files; the hosted verification uses only
  their hash-verified retained-release copies. Do not deploy a bare `dev` checkout
  as if it were a complete hosted release.
- Existing deployment authorization remains in force. Once workload-account
  access is available, verify `020055445580` in `us-east-1`, apply the bounded
  patch to a new immutable release with rollback, test owner first, then Techstars.
  Preserve invitation URLs, histories, backups, expiry, logging, owner settings,
  and Techstars' model/tier/reasoning, unlimited admissions, four resets, $5
  original-session family cap and $50 cumulative cap including background calls.
  No new paid resource or upgrade is part of this patch.
