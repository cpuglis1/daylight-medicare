# Current architecture

Reviewed October 21, 2026 from the implementation. This guide describes what exists, not the larger proposed company architecture.

## Application and data boundaries

```text
Guide / focused help / comparison UI     cms-slice/apps/chat/{index.html,app.js,styles.css}
                  │ same-origin HTTP
Loopback Python service                 scripts/demo.py
                  ├ ConsumerAcceptance: exact-release + claim + output admission
                  ├ NaplesCatalog: published records, field ordering, compare
                  ├ Conversation / LiveConversation / ResponsesClient
                  └ DemoTools: bounded, source-backed evidence operations
Immutable release                       releases/<release-id>/ + current.json
                  ↑ verified build and engineering checkpoint
Local source-shaped reports/captures     reports/ + data-sources/raw/
Pinned source registries and parsers     data-sources/*.json + scripts/*.py
```

`cms-slice/scripts/cms_slice.py` sets the slice root from its own path. Many scripts and source manifests use root-relative fixed paths; moving code, config, raw archives, report fixtures, releases, or public assets can invalidate imports, hashes, and evidence. None was moved in this cleanup. `medicare-project-2026-10-17-v1.2/archived-prototype/` is a separate synthetic Node workbench, not an app dependency.

## Frontend

The active frontend is plain JavaScript/HTML/CSS, with self-hosted fonts, SVG assets, and no bundler. Its eight chapters cover basics, A/B, current coverage, medicines, other benefits, options, comparisons, and next steps. Adaptive questions preserve reported answers, uncertain states, work-coverage transitions, notes, and date safeguards. An experienced shortcut skips beginner teaching after necessary inputs; skipped answers remain unknown.

Common source-linked teaching answers are embedded in the guide. Focused help identifies the question, provides visible follow-ups, and returns to the same guide state and unsent draft. Other typed questions depend on a live service. One Continue advances each guided page; choice cards, Back, editing, and help retain explicit labels. See requirements D01–D38 and [learning flow](DAYLIGHT_LEARNING_FLOW.md).

## Service and admission

`demo.py` exposes fixed loopback assets and bounded endpoints including `/api/status`, `/api/catalog`, `/api/chat`, `/api/live-chat`, `/api/conversation`, and `/api/local-resources`. It validates host/request boundaries and does not provide a general filesystem API. Catalog ordering over published fields is separate from personal suitability.

`consumer_acceptance.py` reloads its registry for each operation. Admission requires a named Medicare reviewer, unexpired review, matching immutable release/runtime, all required workstreams/claims, and the exact returned facts, plans, and fields. Missing, revoked, changed, or expired acceptance closes access. Python-only research mode is not an HTTP gate override. With the current pending registry, the real consumer entry shows a validation-pending page and data APIs refuse facts. Tests verify these boundaries.

`demo_release.py` binds runtime files, config, source receipts, and selected derived evidence. Rebuilding after code changes produces another candidate; it does not renew source review or human sign-off. The selected release is stale against current frontend code, a pre-existing condition documented in [status](CURRENT_STATUS.md).

## Data and research modules

| Modules | Responsibility |
| --- | --- |
| `cms_slice.py`, `research.py`, `validate_naples.py` | Pinned landscape/PBP parsing, explicit markets, read model, source lineage and carrier corroboration |
| `prescription.py`, `reference_evidence.py`, `identity_lookup.py`, drug validators | Complete captured market drug/network rows, exact identifiers, public identity examples and independent replay |
| `star_ratings.py`, `core_benefits.py`, `florida_medigap.py`, `local_programs.py` | Separate ratings, benefit matrix, illustrative CHOICES normalization, sourced program/coordination evidence |
| `medicare_collector.py` | Fixed synthetic observation plans, policy checks, rate limits/cache and persistent STOP; no current live resumption |
| `evidence_store.py`, `source_refresh.py`, validation audit helpers | Source hashes, retrieval records, bounded discovery and evidence checks |
| `transcript_log.py`, `usage_metrics.py` | Local submitted-conversation logs and bounded usage metrics |

## State and privacy

Guide inputs/notes and unsent drafts are tab memory, with no account or saved customer profile. Reloading or closing the tab can lose them. Embedded guide answers remain local. Explicit service chat can be transmitted to the configured model; service conversations are logged as local `.txt` files under `cms-slice/reports/conversations/`. Logs and `.env` credentials are ignored. An older starter/conversation API can log explicit starter submissions; do not infer the behavior of those endpoints from the newer guide UI.

The service loads only named model settings when an env file is explicitly supplied. There is no blanket promise that all entered or submitted data stays local. C01 logging/privacy work is deferred for owner testing and remains open before real-user medical/financial inputs. Use conspicuously synthetic QA cases.

## What is deliberately absent

No production customer database, implemented account/sharing grants, validated personal total-cost/ranking engine, binding Medigap quote, proven clinical participation service, staffed purchase queue, or enrollment transaction integration is established here. Broader designs in the original architecture bundle are proposals. See [data gaps](DATA_INVENTORY.md) and the [one-page objectives](planning/collier-mvp-2026-10-21/collier-mvp-plan.pdf).
