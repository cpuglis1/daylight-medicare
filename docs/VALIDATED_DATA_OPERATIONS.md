# Validated data operations

The owner requires validated data only. The consumer runtime now fails closed while acceptance is pending. The local app displays a holding page; catalog, comparison, chat and resource APIs return no unaccepted facts. Workspace research data, successful technical checks and prior testing releases do not authorize consumer use.

## Admission contract

`cms-slice/scripts/consumer_acceptance.py` checks a named Medicare subject-matter review against the exact immutable release manifest, including runtime code hashes. It reloads the acceptance registry on every operation. Missing, changed, revoked, malformed or expired review records block access. Review deadlines cannot extend past the release's retained source-review deadline. Rebuilding does not renew source reviews.

The immutable `validation-requirements.json` contains 2,036 required claims: 280 plan/ZIP availability claims, 1,680 core cells, 70 star-rating claims and six workstream completion claims. The workstream claims include the additional drug, pharmacy, Medigap, clinical and rule/program checks; those are substantive evidence requirements, not six arbitrary checkmarks. Every required claim needs its exact hash, conditions review, reconciliation receipt, reviewer and dates. A named review of an entire plan cannot replace field-level review.

Returned facts, structured plan records, individual metric cells, drug results, candidates, resources and coordination results require exact output receipts as well. Optional outputs without receipts remain unavailable. No missing amount becomes zero, no conflict becomes an accepted price, and no source-only value reaches sorting or totals. Consumer data access is blocked entirely until all required R1 claims are accepted. Unsupported totals and held calculators stay unavailable.

`data-sources/consumer-acceptance.json` is intentionally pending. Nothing in the audit/packet commands sets it to accepted. There is no HTTP, environment or CLI bypass. Python-only `DemoTools(research_mode=True)` supports offline evidence research and existing source/parser regressions. The HTTP boundary always ignores that flag. Tests that intentionally exercise the legacy research UI use an explicit test-only admission double; `test_consumer_acceptance.py` tests the actual gate without that double, and portable-release tests check the default frozen runtime remains closed.

## Reproduce and review

From `cms-slice`:

```
python3 scripts/validation_audit.py
python3 -m unittest discover -s tests -v
python3 scripts/demo_release.py build --candidate
python3 scripts/validation_audit.py --release /absolute/path/to/the/candidate
```

The audit is offline. It verifies captured carrier PDF hashes and exact plan/year context, replays selected financial comparisons and product/formulary joins, inventories every required claim and preserves unresolved conditions. Source capture helpers and receipts are in `reports/collier-gap-20261020/validation/`; running the audit does not rerun those network captures.

The unsigned reviewer template binds the exact release manifest and every required claim. The reviewer must first resolve substantive missing evidence, then record their name, scope, dates, reconciliation receipts and exact approved outputs. Source or code changes require a new candidate and new acceptance; old receipts cannot be copied to another release. A template with all entries pending is a preparation artifact, not approval. Required incomplete claims prevent final acceptance. Current core-source review deadline remains October 21, 2026 at 01:33 UTC; no extension was made.

## External dependencies and open work

Medicare.gov's original HTTP 403 STOP remains active. Do not retry around it. OIR case 26-045612 has an acknowledgment but no responsive records. A named qualified Medicare reviewer has not been assigned. No new outreach, paid purchase, enrollment, contact request or real-user scenario was submitted during this validation work.

Further autonomous work remains possible: complete the remaining exact SB/EOC field audits, independently corroborate more formulary/pharmacy cases, and research exact hospital/plan/network/location evidence. The current selected-field comparisons are partial. Two Optimum carrier formularies are one version ahead of the pinned CMS versions; matching selected rows do not establish whole-formulary agreement. Physical quantity units remain unresolved for the selected Trulicity comparison. General NCH payer listings conflict in date/scope with its explicit 2027 notice and distinguish hospital contracts from medical-group contracts. These are review issues, not accepted participation determinations.

C01 remains skipped for owner testing; the existing conversation logging behavior and hold list remain in force. Legal approval in C12 is complete and is distinct from data acceptance in C36.
