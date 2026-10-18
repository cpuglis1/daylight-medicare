# Naples demo execution checkpoint

Updated during the October 17, 2026 work session (some source receipts are October 18 UTC). This records implemented work and remaining real dependencies; it does not claim qualified sign-off, a consumer study, live vendor access, or enrollment.

## Running the demo

From `cms-slice/`, run `python3 scripts/demo_release.py verify current`, then `python3 scripts/demo.py serve --release current` and open `http://127.0.0.1:8766/`. This is one local Python process and a simple chat. Workspace mode, `python3 scripts/demo.py serve --online`, permits bounded public NLM/NPPES reference requests; the immutable release is offline. Conversation history and private profiles are not saved.

Try “What changed at NCH for 2027?”, “Explain prior authorization”, “Find Trulicity”, “Find CVS in Naples”, “Find BlueMedicare Select”, and “Show PDP plans”. A medicine, store, or similarly named plan requires explicit selection. An exact source-code query can also inspect drug evidence without asserting that the product is someone's prescription.

`OPENAI_API_KEY` and `OPENAI_MODEL` enable the server-side Responses adapter. Neither was available for a live model test in this session. The default source-only mode works without them. Controlled transport tests verify the API/tool contract and rejection of invented facts; they do not establish live model quality. Source-only mode uses bounded local routing, so arbitrary conversational understanding is not claimed.

## Completed engineering work

| Item | Evidence |
|---|---|
| Alternate-cache verification defect | Query verifies the selected cache and optional matching report directory; a real-row prior-authorization alteration is rejected by regression test |
| MA-only plus pharmacy defect | Correct non-Part-D state is retained with a pharmacy argument; no nonexistent pharmacy capture is required |
| General medicine identity | Actual RxNorm resolver; six captured public medicine-name examples; ambiguity and quantity/days remain explicit |
| Pharmacy identity | Actual NPPES city/location search; 120 reported Naples pharmacy organizations in the captured query, with name/address filtering; operation/participation unconfirmed |
| Plan-name resolution | Source-backed candidates, including duplicated BlueMedicare Select names, with explicit plan-ID selection |
| Local/provider education | Thirteen source-bound Medicare/NCH/Physicians Regional/selected benefit facts, with support anchors and source hashes |
| Wider carrier corroboration | Sixteen records across three parent organizations; 39 particular monetary agreements; no conflicts in those checks |
| Full supported-market field check | Actual Medicare.gov browser inspection: 32 non-SNP MA records + 11 PDP records exactly match the captured universe; all 96 applicable amounts in the supported 38-record scope agree, with 18 inapplicable fields preserved |
| Additional medical summaries | Raw official primary/specialist comparison-card observations preserved; cost ranges are not converted to a single price; EOC/deductible/referral conditions remain open |
| Compact tools and indexing | Source-bound facts, IDs and uncertainty; indexed formulary lookup and cached exact pharmacy matches; no inappropriate insulin schedule passed into a non-insulin answer |
| Multi-medicine queries | Up to fifteen distinct exact RxCUI products × all requested supported plans; per-product restrictions, absent evidence and MA-only states retained; no price calculation |
| Independent restriction follow-up | Nine first-carrier cases / 45 agreements, plus three second-carrier cases / 13 agreements, including two positive ST strengths; all twelve original rows replayed; absent brand remains unresolved |
| Chat boundary | Model may choose tools/evidence IDs; server renders factual text; unknown IDs, unconfirmed drug/store choices and unsolicited plan choices are rejected; complete listing membership is retained |
| Minimal local server | Bounded JSON POSTs, same-origin/Host checks, two active requests, rate limits, server-side secret, no profile/application writes or request-body logging |
| Immutable demo packaging | Verified derived inputs, atomic current pointer, same-code data-release selection/rollback, archive containing code plus an approximately 26 MB snapshot; no national source archives or credentials included |
| Dated operation and answer receipts | Review deadline bound to the actual checked input hashes; old bytes do not gain a new review date on rebuild; exact rendered facts/identity choices hashed per answer, with runtime code and model ID when used |

Relevant files: [quality matrix](../cms-slice/reports/demo-quality.json), [official browser observations](../cms-slice/data-sources/medicare-gov-observations.json), [provider diligence](../cms-slice/reports/provider-api-discovery.json), [source registry](../cms-slice/data-sources/demo-sources.json).

## Verification checkpoints

The completed full suite passed **115 tests in 66.518 seconds**. After adding NLM's requested static attribution, the affected demo tests passed **45 tests in 4.256 seconds** and the portable-release tests passed **six tests in 22.550 seconds**. Those include extracting/running the actual archive in a clean directory with no national archives and no PDF tools. The [execution receipt](../cms-slice/reports/demo-execution-receipt.json) records the logs, hashes and final package.

The existing four upstream verifiers remain required. After changing the prescription script, the full capture was rebuilt rather than merely changing its recorded code hash. After changing the read server, the read model was rebuilt. New immutable releases must be built after runtime or source changes; an old release rejects changed runtime files.

Build a release with `python3 scripts/demo_release.py build`, verify with `python3 scripts/demo_release.py verify current`, and bundle with `python3 scripts/demo_release.py bundle current`. Run `python3 scripts/demo.py serve --release current` locally. An extracted archive runs with `python3 scripts/demo.py serve --release snapshot`. It contains saved public vocabulary examples; new online vocabulary requests use the workspace mode instead. This runtime is tested on macOS/Python 3.14.7; Unix file locking is used.

A separate **92.3 MB public-evidence review archive** preserves 84 verified files, including 62 indexed source receipts/candidates, carrier PDFs and local notices. Its [manifest receipt](../cms-slice/reports/evidence-review-bundle.json) identifies the archive and hashes. It supports manual source review and is separate from the runnable demo. The national archives are excluded; this local pack does not establish an off-device backup or permission to distribute every source.

Local benchmark: index/startup 1.65 seconds; one medicine across 31 Part D plans with the example pharmacy 2.66 seconds initially; five subsequent code queries over the same plans/pharmacy 0.0006 seconds after reuse. These are local query measurements, excluding model/network latency, not production SLOs.

## Provider-source discovery result

CMS's National Provider Directory exposes FHIR resources, but this audit has not demonstrated a usable exact 2027 Collier mapping. Five target plan-name searches returned no entries, and a positive-control name taken from an actually returned resource also returned no entries. Thus an empty search is particularly unsuitable as a negative participation verdict. The sampled resources had 2026 periods; one sample had HMO in its name versus PPO type text. Keep those observations as source-quality questions rather than silently approving a clinical adapter.

The official Medicare.gov public provider search was also exercised with the previously captured physician NPI `1891082467`, using both the shortened and complete published surname. It returned “No providers found” for that example. NPPES identity still does not establish exact 2027 participation, and that result does not establish out-of-network status. No beneficiary identity or private medical history was entered.

The [carrier follow-up](../cms-slice/reports/carrier-provider-probe.json) reached Devoted's actual 2027 Collier plan selector and searched the public physician example and NCH name. Both displayed no matches. That demonstrates a usable plan-selection flow, not a negative network verdict; the directory's own confirmation/completeness qualifications were retained.

## Remaining dependencies and next audit priorities

1. Obtain qualified review of the declared factual demo, source use, monetary interpretations, copay-range conditions, and unresolved restrictions. Engineering checks are not that review.
2. Expand the two-carrier restriction sample to the remaining carriers, retaining product/package and quantity-unit uncertainty. Positive ST and absent-brand examples are now captured; neither establishes a personal approval or noncoverage decision.
3. Establish actual exact clinical provider/location/plan/year evidence through usable public payer payloads or authorized supplier access; include positive, negative, stale and conflicting cases. The current provider capability is dated local notices plus honest unresolved checks.
4. Exercise the Responses adapter with a real approved account/model, then run held-out grounding and comprehension checks. No key exists in the current environment, and none was extracted from another application.
5. Run roughly 8–12 facilitated, consented local sessions after the applicable review. No participants, study owner, interviews or outcomes have been invented, and no recruitment messages have been sent.
6. Add actual 2027 personal drug pricing if cost-based choices are part of the next promise. Medigap quoting and enrollment require their own real access and operating evidence. Neither is simulated as successful.

Keep the five Regional PPOs and 27 SNPs visibly outside this comparison scope. The official non-SNP universe check supports completeness of the captured 43 ordinary MA/PDP records; the supported comparison remains 38. Do not silently expand scope or treat exclusions as personal ineligibility. Keep the Virginia source gap off this demo's critical path.

The [re-audit](NAPLES_DEMO_REAUDIT.md) records the after-state. The [handoff](DEMO_HANDOFF.md) contains the exact review tasks, blank observation template and external inputs still required. No sign-off, live model result, participant or vendor integration has been invented.
