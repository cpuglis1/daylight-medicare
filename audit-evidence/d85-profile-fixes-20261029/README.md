# D85 profile repairs and metadata preparation · October 29, 2026

T07/T08 are repaired in the canonical `alternatives/chat-first` source. T16's exact metadata export is prepared. This packet records source/fixture verification; it does not assert a live deployment, database import, source acceptance or recommendation release.

The targeted changes address D85/T07/T08, D79 reuse/unknown/correction behavior, ALT74's multiple-entity and capability gates, D24 rendered verification, D64/D73 independence and D75 isolation. The existing visual design, questionnaires, source holds, profiles, consent and aggregate budget are retained.

## Behavior and evidence

- Explicit `entity=new` reports retain separate items even when medicine names match across strengths/forms or practice names match across offices. An unbound correction cannot choose among namesakes. A bound identity correction preserves the prior report in existing history and marks only that item's fill details stale. The other medicine and unrelated job dates remain intact.
- Choice-only non-baseline unknown/defer dispositions now appear in the existing open-details summary. The collector deduplicates choice/disposition paths, respects task relevance, clears a later answered disposition and continues to withhold personalized recommendations. All-open compare/timing/Medigap/drug tasks terminate and retain their open answers.
- [The exact audit recheck and preservation receipt](verification.json) reproduces the original counterexamples: two explicit new strengths now remain two items, and RC01 unknown appears in the summary while recommendations remain false. Original audit packets remain unchanged.
- 49 adaptive, 10 profile-readiness, 13 readiness, 6 alternative-service and 3 metadata-export tests passed: 81 Python checks. Four retained JavaScript compatibility traces passed. The independent technical QA agent reviewed the patch and separately ran 48 adaptive checks before the final added all-open-task regression; it found no blocking issue. This is technical verification, not independent insurance-domain review.

## D24 rendered check

[Responsive browser metrics](render-verification.json) and [the rendered DOM](unknown-defer-dom.txt) come from the actual canonical fixture at `127.0.0.1:8878`, using a fresh temporary SQLite database, mocked AI and no existing profile/budget stores. The browser performed Get started → Find coverage → recipient unknown → six relevant Check later answers → expand Details still open.

| Viewport | Open details shown | Horizontal overflow | Capture |
| --- | ---: | --- | --- |
| Desktop 1280×800 | 7 | None | [Desktop](screenshots/unknown-defer-desktop.png) |
| Tablet 768×1024 | 7 | None | [Tablet](screenshots/unknown-defer-tablet.png) |
| Phone 390×844 | 7 | None | [Phone](screenshots/unknown-defer-phone.png) |

RC01 appears as “Who is this coverage for? — unknown”; the other six answers say “for later.” Samples remain an explicit optional action with the existing limitation. Console errors: zero. This uses browser viewport emulation, not physical hardware, a screen reader or a consumer comprehension study. Impeccable context/audit guidance was used for this narrow preservation check; no visual design decision or UI-source edit was made. The temporary viewport was reset, tab closed and fixture stopped.

## T16 metadata preparation

[`profile-contract.2026.json`](../../infrastructure/daylight-data/config/profile-contract.2026.json) is a deterministic, source-hash-bound export of the canonical definitions and existing review crosswalk. It retains 41 question definitions, 78 field records, 14 gaps, three documented child aliases, eleven retained wording variants and fourteen additive optional paths. Existing runtime policy remains distinct from proposed capability bridges. No customer row or new mandatory interview is included; no customer store is created or migrated. The original definitions and their current enums remain exact source metadata rather than being relabeled for a different year.

Rebuild or verify with:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 infrastructure/daylight-data/tools/export_profile_contract.py --check
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s infrastructure/daylight-data/tests -p 'test_profile_contract_export.py'
```

The PostgreSQL migration/import is separate work; preparing this file does not complete all of T16.

## Preservation and runtime handoff

The [before receipt](preservation-before.json) contains hashes only and source before-images. All 301 protected root source fingerprints remain unchanged by this task. Every baseline row and inode in the alternative guest store, legacy original guest store and live shared ledger remains unchanged. No personal value was copied into evidence. The actual active :8890 ten-question store baseline is owned separately by T03/QA; this packet does not substitute the legacy store for that check.

The live alternative controller still matches its pre-change hash at this packet's source-only handoff. The final dry run reports exactly one changed deployable file: `cms-slice/scripts/adaptive_flow.py`. The primary agent then attempted the reviewed update under approved escalation. It failed safely before any backup/copy/restart: `launchctl` could not find `gui/501/com.daylight.chat-alternative.8891` (exit 113). Runtime activation is pending because the required service identity is unavailable. The guard was preserved; no direct runtime copy, substitute service or manual startup was used.

From `/Users/cep4u/daylight/alternatives/chat-first`, the exact read-only comparison is:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 runtime/sync_runtime.py --check
```

The reviewed existing source-only update path, for the primary agent's authorized final operation, is:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 runtime/sync_runtime.py --apply --restart
```

That script verifies the exact :8891 launchd/port identity, creates allowlisted source before-images and preserves runtime stores, `.env`, ledger, launch configuration and original :8890. Rollback must restore only that source before-image after comparing any later changes, retaining compatible validators and all guest records. No commit, installation, paid AI, public deployment or source/recommendation acceptance is part of this packet.
