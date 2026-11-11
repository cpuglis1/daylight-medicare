# Collier County Medicare data: gap closure plan

Revised October 19, 2026 (v2). The original version of this plan, also dated October 19, 2026, is superseded. Planning baseline: the supplied [data inventory](../Collier%20County%20Medicare%20Data%20Inventory.md), the October 19 audit workbook, active release `naples-7a0b8eff1577df6e41eb`, and the current application code. The checklist records proposed and completed work. This document does not mark any data gap closed until the checklist records closure evidence.

**Goal.** Let a Collier resident compare both coverage paths with traceable, current evidence:

1. Original Medicare, with optional Medigap and a Part D drug plan.
2. Medicare Advantage.

Conditional options such as special-needs plans (SNPs) and PACE stay visible with their actual eligibility requirements. Every displayed cost, benefit, participation result and rule needs an identifiable source and an explicit verification state.

**What changed in v2.**

- **Scope.** The work is split into Release 1 (R1) and an explicit hold list.
- **New workstream.** G9 adds a Medicare.gov collector.
- **Medigap.** Sourcing now starts with free Florida data.
- **Networks.** Work starts with a hospital-by-plan table.
- **Smaller tracking.** The coverage ledger is reduced to a simple table.
- **Privacy.** Privacy work moves to the first item.

---

## Agent protocol (read before doing anything)

Any person or agent working from this plan must follow these rules.

1. **Read the checklist first.** Pick the lowest-numbered unblocked R1 item that fits your role, unless the owner says otherwise.
2. **When you start an item,** add `IN PROGRESS <date> <who>` to the end of its line.
3. **When you finish an item,** update the checklist in the same change as the work:
   - Change `- [ ]` to `- [x]`.
   - Replace the in-progress note with `DONE <date> — evidence: <path, receipt, PR or test name>`.
   - Never tick an item without closure evidence that meets that workstream's "Done when" test.
4. **When you are blocked,** add `BLOCKED <date> — <reason> — needs: <who/what>` and move on to another item.
5. **When you find new work,** add a new checklist item with the next free ID (C37, C38…) under the right phase. Never renumber existing items.
6. **Hold items need approval.** Don't start them without the owner's written approval, recorded in the Decision log.
7. **Keep the records current:**
   - Update the "Last updated" line at the top of the checklist.
   - Add one line to the Change log at the bottom of this file.
   - Record any scope or source decision in the Decision log.
8. **Never edit history.** Don't edit historical counts or delete audit issue rows. Keep DQ-001 to DQ-014 IDs and add closure receipts.

---

## Checklist

**Last updated:** 2026-10-20 (C37 consumer gate and C43 exact-release review packet complete; C38–C42 data validations remain partial/open; 200 tests + 8 final packaging checks pass; zero accepted claims; selected validation candidate `naples-98038a43549f438d8c38`; C01 deferred; C44 owner review queue complete — `COLLIER_OWNER_REVIEW_REQUIRED.md`)

**Owner review:** [COLLIER_OWNER_REVIEW_REQUIRED.md](COLLIER_OWNER_REVIEW_REQUIRED.md) contains the outside attestations, access/records dependencies and conditional confirmations. The file distinguishes permanent limits on self-certification from temporary source blocks; independently feasible validation remains in this checklist.

### Phase 0: Do first (Week 1)

- [ ] **C01** · P0/G8 · app eng · Stop or limit the app writing visible conversations to local text files before any medication, income or quote question is asked. Define what is requested, logged and retained. Use synthetic inputs only until done. SKIP FOR NOW 2026-10-19 — owner: current conversation logging is for owner testing; proceed with C02–C05. Deferred, not closed.
- [x] **C02** · G0 · data eng · Replay baseline counts: 70 catalog, 61 drug-bearing, 59 medical, 31 packaged networks. Create the simple coverage table (see G0). DONE 2026-10-19 — evidence: `cms-slice/reports/collier-gap-20261019/c02/baseline.json`, `cms-slice/reports/collier-gap-20261019/c02/coverage.md`; replay command: `python3 scripts/collier_baseline.py --out reports/collier-gap-20261019/c02`. Candidate app/workbook alignment remains C34.
- [x] **C03** · G0 · data eng · Refresh CMS catalog discovery in a candidate workspace, keeping the old receipt. Record a new review deadline. Closes DQ-014. DONE 2026-10-19 — evidence: `cms-slice/reports/collier-gap-20261019/c03/discovery.json`, `previous-catalog-receipt.json`, `previous-discovery.json`, `change-assessment.json`. New retrieval 2026-10-20 01:33 UTC (October 19 Eastern); review deadline 2026-10-21 01:33 UTC. Catalog bytes changed; monthly/quarterly distributions unchanged. DQ-014 closure is for candidate discovery; historical audit row retained.
- [x] **C04** · G2 · data eng · Import the 2027 Star Ratings Data Tables (Oct 8, 2026). Join to the 24 captured contracts and keep unrated states. Closes DQ-002. DONE 2026-10-19 — evidence: `cms-slice/reports/collier-gap-20261019/c04/ratings.json`, `independent-check.json` (72 cells / 24 contracts), `technical-review.json`, and C05 extracted-bundle replay. All 70 records have sourced display states: 68 numeric and 2 CMS "Not enough data available"; raw landscape blanks preserved. CSV/XLSX checks are separate extractions of the same CMS publication.
- [x] **C05** · G5 · data + app eng · Package all 61 pharmacy networks and remove the 38-plan restriction in `demo_release.py` and `DemoTools.drug_evidence()`, in the same change. Verify from an extracted bundle. Closes DQ-010. DONE 2026-10-19 — evidence: `cms-slice/reports/collier-gap-20261019/c05/extracted-bundle-replay.json` (61 drug plans + 9 not-applicable MA-only records, no network access), `tests.log` (166 tests pass), `selection-receipt.json`. Queries page at 20 plans; incomplete model comparisons are rejected. Testing release `naples-63ae25f4b9a870fe7848` contains all 61 networks; prior release retained. Startup/memory/latency measurements recorded in replay receipt; no additional index added.
- [x] **C06** · G7 · analyst · Add Hope PACE: current service area, eligibility, and referral route. DONE 2026-10-19 — evidence: `cms-slice/reports/collier-gap-20261019/c06-c08/resources.json`, `source-review.json`, `extracted-bundle-local-programs.json`. CMS October directory confirms H5934; AHCA August report lists Collier operational. County scope is published; no exhaustive ZIP list was found, so exact-address confirmation uses the program enrollment line and personal eligibility remains unknown. Separate conditional program path includes assessment, costs and drug-coverage coordination. Dated cost/MSA search is bounded to the pinned landscape; C18 remains open.
- [x] **C07** · G7 · analyst · Add the official Collier SHINE referral: contacts, appointment info, and the date it was checked. DONE 2026-10-19 — evidence: `cms-slice/reports/collier-gap-20261019/c06-c08/resources.json`, `sources.json`, `visual-qa.json`, `final-browser-resources.jpg`. State phone/TTY, official counseling request link, two Collier appointment routes, members-only restriction and checked date are visible; hosting/volunteer liaison is distinguished from appointment contacts. No appointment or external referral was submitted.
- [x] **C08** · G7 · analyst · Add coordination flags for employer/union retiree coverage, VA/TRICARE for Life and older Medigap policies. DONE 2026-10-19 — evidence: `cms-slice/tests/test_local_programs.py`, `cms-slice/reports/collier-gap-20261019/c06-c08/tests.log` (177 pass), `final-local-programs-tests.log` (11 pass after final wording check), `extracted-bundle-local-programs.json`, `selection-receipt.json`. All four types trigger sourced review notices without eligibility determinations or coverage-change advice; explicit corrections survive bounded tab history. Selected testing release `naples-69c6cdaa28761a4d80c7` preserves all 70 records, 61 pharmacy networks and star states. Earlier releases and review deadlines retained; C01 remains deferred.
- [x] **C09** · G4 · supplier owner · Send a public records request to Florida OIR for the Medicare supplement rate collection data behind CHOICES. Record the request date and reference number. DONE 2026-10-19 — sent at 22:35 Eastern to PublicRecords@floir.com; outbound reference: Gmail message `1a157298265d98b7` (not an OIR case number). Evidence: `cms-slice/reports/collier-gap-20261019/c09-c12/c09-oir-request.md`, `c09-send-receipt.json`. Official OIR case/reference number and data response remain pending; no fees authorized. Data ingestion remains C23. UPDATE 2026-10-20 — OIR acknowledgment assigns official case 26-045612; responsive data pending. Evidence: `cms-slice/reports/collier-gap-20261020/c16-c23/c23-oir-acknowledgment.json`. Original send receipt retained.
- [x] **C10** · G4 · supplier owner · Decide whether to buy a CSG Market Advisor Florida subscription ($20–40/month listed price) as a Medigap cross-check, then record the decision. DONE 2026-10-19 — defer purchase while pursuing the approved Florida-free route; $0 committed and no trial/subscription started. Evidence: `cms-slice/reports/collier-gap-20261019/c09-c12/c10-csg-decision.json`, `sources.json`. Current page advertises single-state monthly Bronze $20 / Silver $30 / Gold $40; Florida checkout and reuse rights are not inferred. Revisit after OIR response or a C23/C24 corroboration gap; H03 remains held.
- [ ] **C11** · G9 · supplier owner · Ask CMS whether 2027 Plan Finder drug pricing and the MA provider directory data are available to outside organizations. Record the request and the reply. IN PROGRESS 2026-10-19 Codex — inquiry sent to MPF@cms.hhs.gov at 22:35:13 Eastern; Gmail reference `1a15729b56f1606c`. Evidence: `cms-slice/reports/collier-gap-20261019/c09-c12/c11-cms-request.md`, `c11-send-receipt.json`. AWAITING CMS REPLY as of 2026-10-20 02:37 UTC; no external access grant inferred. Contact verified in CY 2027 pricing guidelines, PDF page 18. Owner-review dependency: O02 / E01 / E03 in [separate review file](COLLIER_OWNER_REVIEW_REQUIRED.md).
- [x] **C12** · G9 · supplier owner · Get a quick legal read on automated Medicare.gov collection at low volume. Record the decision before C16 runs at scale. DONE 2026-10-19 — owner confirmed: "Legal said we are good. mark as complete". Evidence: `cms-slice/reports/collier-gap-20261019/c09-c12/c12-legal-decision.json`. Owner-reported legal approval recorded; C13 and existing G9 controls remain applicable, and H09 remains held.
- [x] **C13** · G9 · data eng · Review and save Medicare.gov `robots.txt` and the site policies. Record which paths and practices are allowed. DONE 2026-10-20 — evidence: `cms-slice/reports/collier-gap-20261019/c13-c15/c13-site-policy.json`, `c13-site-policy.md`, exact `medicare-robots.txt`, hashed policy-page receipts and `verification.json`. Public entry paths are not disallowed; account paths, robots-denied resources and unreviewed backends remain excluded. C16 must review actual request paths and enforce G9, including browser subresources. C12 approval retained; H09 held. No collector scenarios run.
- [x] **C14** · G5 · data eng · Run the three-day 2027 drug-price source feasibility check (public CMS files and commercial options). Record the findings. DONE 2026-10-20 — evidence: `cms-slice/reports/collier-gap-20261019/c13-c15/c14-price-source-decision.json`, `monthly-archive-inspection.json`, `cms-release-discovery.json`, primary commercial-source receipts. Expedited October 19–20 assessment, not three elapsed days of monitoring. NO GO: monthly 2027 lacks per-drug unit pricing; latest quarterly candidate is 2026 and its documented grain is plan-average retail pricing. ConnectureDRX/SunFire are unlicensed, unvalidated commercial leads; C11 access reply pending. No purchase/outreach. H01/H08/H09 held; DQ-007/008 open.
- [x] **C15** · G6 · data eng · Discover the provider directory API for each of the 8 Advantage parent organizations: endpoint, capability statement, and whether 2027 plan/network mapping exists. DONE 2026-10-20 — evidence: `cms-slice/reports/collier-gap-20261019/c13-c15/c15-provider-api-discovery.json`, `c15-provider-api-discovery.md`, endpoint/schema/pagination receipts and `verification.json`. All 8 parents / 59 MA plans / 18 contracts assigned. Humana and Devoted return two exact 2027 Collier plan/network seeds and qualify for bounded C28 build work; other mappings remain unverified. UHC/Florida Blue observed 2026; Curana contract-only; Centene 403, Aetna app access and Elevance tenant configuration unresolved. Provider participation remains unknown; C26–C28 open.

### Phase 1: Build (Weeks 1–3)

- [x] **C37** · G0/G8 · app eng + domain reviewer · Enforce validated-only acceptance at field/claim level across consumer chat, cards, ordering, totals and exports; suppress unaccepted outputs and block release on missing required R1 facts. DONE 2026-10-20 — engineering gate: `cms-slice/scripts/consumer_acceptance.py`, `docs/VALIDATED_DATA_OPERATIONS.md`; evidence: `cms-slice/reports/collier-gap-20261020/validation/final-tests.log` (200 pass), `final-packaging-tests.log` (8 pass after final evidence/runtime-inventory checks), `extracted-replay.json`, `selection-receipt.json`. Exact source/field conditions and output receipts, named review, immutable data/runtime binding, expiry/revocation and default pending enforced. No HTTP/CLI bypass; static guidance also held. Current local candidate `naples-98038a43549f438d8c38` has zero accepted claims and shows a validation-pending page. Software completion does not close C36 or data validations C38–C42.

- [x] **C16** · G9 · data eng · Build the Medicare.gov collector with all guardrails in G9. Keep a dry-run mode and a kill switch. DONE 2026-10-20 — collector core: `cms-slice/scripts/medicare_collector.py`, `docs/MEDICARE_COLLECTOR.md`; evidence: `cms-slice/reports/collier-gap-20261020/c16-c23/c16-guardrail-verification.json`, `c16-browser-preflight-9/run.json`, `collector-final-tests.log`. Dry-run, headless capture, persistent STOP, five-second shared pacing, 2,000-request cap, cycle cache, robots/explicit paths, receipts and schema-stop controls implemented. Live preflight received HTTP 403 at public bootstrap; STOP remains active with zero requests after denial. Current task adapters are not admitted; C17/C20/C22 and full G9 observation/release gates remain open. 191 application tests pass.
- [ ] **C17** · G9/G1 · data eng · Collector: observe core plan facts for all 70 plans and for the G1 ZIP set. This extends DQ-005 beyond 38 plans. BLOCKED 2026-10-20 — Medicare.gov public bootstrap returned HTTP 403; no retry/bypass. Needs documented source-access resolution and validated current task schema. Evidence: `cms-slice/reports/collier-gap-20261020/c16-c23/c17-coverage.json`, `c17-dry-run.json`, final preflight receipt. All 70 IDs × four ZIPs prepared (280 cells); zero new observations. Historical 38-plan selected-field check is not extended; DQ-005 stays open. Owner-review dependency: E01 in [separate review file](COLLIER_OWNER_REVIEW_REQUIRED.md).
- [ ] **C18** · G1 · data eng + analyst · Market check: compare CMS identities with Medicare.gov results for the Collier ZIP set in both directions. Explain every difference. BLOCKED 2026-10-20 — depends on C17 source-access resolution. Evidence: `cms-slice/reports/collier-gap-20261020/c16-c23/c18-market-reconciliation.json`. Current four-ZIP bidirectional comparisons are explicitly not run. Historical 34102 diagnostic matches 43 non-SNP IDs; 27 SNPs were outside that old scenario, not proven absent. No unexplained-difference count or complete-market claim is invented. Owner-review dependency: E01 in [separate review file](COLLIER_OWNER_REVIEW_REQUIRED.md).

- [ ] **C38** · G1 · data eng + analyst · **Plan availability validation:** reconcile all 70 exact identities against current 2027 availability for ZIPs 34102, 34109, 34145 and 34142 (Collier County explicitly). Preserve inputs, source bytes, dates and both-direction differences; explain every difference, including restricted offerings. BLOCKED 2026-10-20 — current Medicare.gov observations unavailable after HTTP 403; do not substitute historical coverage or retry around STOP. Carrier service-area evidence can be audited independently. Required before availability claims are accepted. PARTIAL 2026-10-20 — four exact Optimum identities match its public all-plan results in all four ZIPs (16 carrier checks, no differences); exact 2027 SB covers bind internal keys to H5594 IDs. UHC H1889-026 official-page lead says closed to new enrollments from January 2027 despite Collier listing; local source retrieval denied, so this remains an unaccepted reconciliation issue. Evidence: `cms-slice/reports/collier-gap-20261020/validation/carrier-market-check.json`. Owner-review dependency: E01 in [separate review file](COLLIER_OWNER_REVIEW_REQUIRED.md).
- [x] **C19** · G1 · analyst · Define the core benefit field dictionary and build the matrix for all 70 plans. Show each field's verification state. DONE 2026-10-20 — evidence: `cms-slice/reports/collier-gap-20261020/c16-c23/c19-field-dictionary.json`, `c19-core-benefit-matrix.json`, `c19-matrix-overview.md`; reproducible command: `python3 cms-slice/scripts/core_benefits.py`. All 70 records × 24 fields = 1,680 explicit verification states. Historical corroboration keeps its original date/scope; coded benefits and missing SB/EOC interpretations remain pending and cannot drive ranking. This completes the dictionary/matrix milestone, not G1 independent review or DQ-005/006 closure.

- [ ] **C39** · G1/G5 · data eng + analyst · **Benefits and costs validation:** check every displayed field against the exact plan’s 2027 Summary of Benefits/EOC; preserve amount, units, period, tiers, network, exceptions and conditions with page-level evidence. Resolve DQ-003/DQ-004 rather than treating display-both as acceptance. IN PROGRESS 2026-10-20 Codex — independently recheck saved carrier documents, expand available official evidence, build field-level review packet; unaccepted facts stay suppressed. C19 remains a completed matrix milestone, not domain acceptance. PARTIAL — 14 additional SNP/Regional PPO plans, 42 selected cells: 40 numeric agreements with conditions, one unresolved premium-basis difference and one CMS nonapplicable field with no established carrier negative. Ten new Humana SBs and four exact Optimum 2027 SBs captured/rendered. Evidence: `cms-slice/reports/collier-gap-20261020/validation/financial-audit.json`, `pages/`; all-70/full-field and EOC review remains open. No cells accepted for consumer use. Owner-review dependency: E04 (conditional escalation; public research stays with Codex) in [separate review file](COLLIER_OWNER_REVIEW_REQUIRED.md).
- [ ] **C20** · G9/G5 · data eng · Collector: capture 2027 drug-cost estimates for the fixed synthetic scenario set in G9. BLOCKED 2026-10-20 — same actual Medicare.gov HTTP 403; STOP active. Evidence: `cms-slice/reports/collier-gap-20261020/c16-c23/c20-drug-scenario-coverage.json`, `c20-dry-run.json`. Ten synthetic lists × 61 plans × retail/mail = 1,220 logical targets; exact drug/quantity-unit/pharmacy confirmations remain required. No estimates captured or manufactured; H01/H08/H09 remain held. Owner-review dependency: E01 / E03 in [separate review file](COLLIER_OWNER_REVIEW_REQUIRED.md).
- [x] **C21** · G5 · analyst · Resolve DQ-003/DQ-004 ($0.00 vs $7.30 Part D premium), or display both values with their basis. DONE 2026-10-20 — display-both alternative implemented for H1889-026-000-2027 and H5594-017-000-2027. Evidence: `cms-slice/reports/collier-gap-20261020/c16-c23/c21-premium-basis-display.json`, `extracted-premium-basis.json`, `evidence-final-tests.log`. Catalog cards/facts retain $7.30 Part D total, $7.30 listed CMS-paid subsidy, $0 low-income beneficiary field and $0 monthly PUF PREMIUM with separate source labels/links. PUF basis remains unresolved and premium ordering excludes both conflicts. DQ-003/004 remain recorded with display mitigation. Selected owner-testing candidate: `naples-d2191e850e290c659753`. UPDATE 2026-10-20 — C37 supersedes consumer display-both permission: unaccepted values are research-only. Exact Optimum SB/LIS evidence supports a conditional zero but does not establish the monthly PUF basis; DQ-003/004 remain open.

- [ ] **C40** · G5 · data eng + analyst · **Drugs and pharmacies validation:** verify exact products, strength/form identifiers, formulary joins/restrictions, quantity units and plan × pharmacy joins. Independently replay worked cases. Separate coverage from pricing: estimates require an adequate authorized 2027 source and worked-case checks; C20 access is blocked and H01 remains held. No missing price becomes zero. IN PROGRESS 2026-10-20 Codex — replayed all 61 pharmacy captures (3,506,965 rows) with no cross-plan identity rows; four new product/formulary cases, eight plan/product joins and 20 selected field agreements. Two carrier formularies are one version newer than pinned CMS; Trulicity physical quantity units remain unresolved. Independent current pharmacy participation and authorized pricing/worked costs remain open. Evidence: `cms-slice/reports/collier-gap-20261020/validation/pharmacy-join-audit.json`, `optimum-drug-cases.json`. Owner-review dependency: E03 / E04 (public research stays with Codex) in [separate review file](COLLIER_OWNER_REVIEW_REQUIRED.md).
- [ ] **C22** · G9/G4 · data eng · Collector: capture Medigap policy search results for the Collier ZIP set (insurer × letter × variant). BLOCKED 2026-10-20 — same actual Medicare.gov HTTP 403; STOP active. Evidence: `cms-slice/reports/collier-gap-20261020/c16-c23/c22-medigap-coverage.json`, `c22-dry-run.json`. Four ZIPs × 12 letter/high-deductible families prepared; insurer/SELECT universe not observed. Needs source-access resolution and current UI/workflow validation. Owner-review dependency: E01 in [separate review file](COLLIER_OWNER_REVIEW_REQUIRED.md).
- [ ] **C23** · G4 · data eng + analyst · Build the Florida Medigap dataset from the OIR records response, rate filings and CHOICES. Label all rates "illustrative" unless they are a real quote. IN PROGRESS 2026-10-20 Codex — partial evidence: `cms-slice/reports/collier-gap-20261020/c16-c23/c23-florida-medigap.json`, `choices-source-index.json`, `c23-irfs-review.json`, `c23-oir-acknowledgment.json`. Captured 3,876 illustrative annual-rate rows from 34 insurers across 17 synthetic 34102 cases. One NAIC verified from IRFS filing 26-018953 metadata; no rate-table replay or row-level filing join claimed. OIR acknowledged case 26-045612; responsive records remain pending. Requested 01/01/2027 filter is not a verified effective date. Household-discount/GI assumptions, remaining identifiers, C22 universe and independent per-insurer corroboration remain open; DQ-011 not closed. Owner-review dependency: E02 in [separate review file](COLLIER_OWNER_REVIEW_REQUIRED.md).
- [ ] **C24** · G4 · analyst · Reconcile the Medigap product universe across OIR, Medicare.gov and (if bought) CSG. List the gaps. Owner-review dependency: E02 in [separate review file](COLLIER_OWNER_REVIEW_REQUIRED.md).

- [ ] **C41** · G4 · data eng + analyst · **Medigap rates validation:** obtain OIR case 26-045612 records; establish exact insurer/NAIC/form/variant/rating-area/effective-date matches, verify age/sex/tobacco/discount/fee assumptions, and reproduce rates against filings or insurer evidence. CHOICES query dates are not verified effective dates. BLOCKED IN PART 2026-10-20 — responsive OIR records and accessible rate tables pending; all 3,876 captured annual amounts remain unaccepted research evidence. No illustrative label substitutes for validation. Owner-review dependency: E02 in [separate review file](COLLIER_OWNER_REVIEW_REQUIRED.md).
- [ ] **C25** · G3/G4 · analyst · Write the Medigap buying rules: open enrollment, guaranteed issue, Plan C/F eligibility, Florida under-65 access, SELECT, pre-existing conditions.
- [ ] **C26** · G6 · analyst · Build a hand-checked hospital × plan participation table for 2027, starting with NCH and Physicians Regional.
- [ ] **C27** · G9/G6 · data eng · Collector: run 2027 provider directory lookups for the hospital table and doctor test cases, as a cross-check.
- [ ] **C28** · G6 · data eng · Build insurer directory adapters for parent organizations whose APIs pass C15. Return confidence states. Others show "unknown — call to confirm."

- [ ] **C42** · G6 · data eng + analyst · **Doctors and hospitals validation:** validate exact provider/facility, location, medical network and 2027 plan against current insurer and provider/hospital evidence. Preserve disagreeing sources and dates. Endpoint reachability, insurer plan references and NPI identity alone cannot establish participation. Start with the C26 hospital table; unsupported participation answers stay unavailable. IN PROGRESS 2026-10-20 Codex — current NCH notice/payer list and Physicians Regional Medical Group pages captured; 118 hospital × plan cells explicitly unknown. Dated NCH 2027 Wellcare notice differs in scope/date from generic payer list; hospital and medical-group Humana lists differ. No exact facility/network/location participation inferred. Evidence: `cms-slice/reports/collier-gap-20261020/validation/hospital-validation-queue.json`. Owner-review dependency: O04 (conditional confirmation; public research stays with Codex) in [separate review file](COLLIER_OWNER_REVIEW_REQUIRED.md).
- [ ] **C29** · G3 · analyst · Load the 2027 Part A/B amounts once CMS publishes them, plus IRMAA brackets and Part D parameters. Mark them pending until published.
- [ ] **C30** · G3 · analyst + app eng · Add enrollment windows and Part B/Part D penalty rules, with compatibility checks (no impossible MA + Medigap combinations).
- [ ] **C31** · G3 · app eng · Add a short help-program screener (Extra Help, Medicare Savings Programs, Medicaid) that says "you may qualify" and refers to SHINE, with no eligibility determination.

### Phase 2: Release 1

- [ ] **C32** · G8 · app eng · Integrate both paths in comparisons. Totals appear only when every required component exists; otherwise show components and what's missing.
- [ ] **C33** · G8 · app eng · Run the existing suites (`test_cms_slice`, `test_prescription`, `test_naples_mvp`, `test_demo_release`, conversation tests) plus the R1 scenario replays.
- [ ] **C34** · G0/G8 · data eng · Regenerate the audit workbook from the candidate release, including Medicare.gov observations as their own source type.
- [ ] **C35** · G8 · data eng · Build an immutable candidate release and keep the prior release available.

- [x] **C43** · G0/G8 · data eng · Prepare the exact-release acceptance packet, field inventory, evidence hashes/pointers, reconciliations, unresolved issues, reviewer template and refresh deadlines. DONE 2026-10-20 — `cms-slice/reports/collier-gap-20261020/validation/REVIEW_PACKET.md`, `candidate-binding.json`, `reviewer-template.json`; candidate `naples-98038a43549f438d8c38`, 2,036 required claims, all pending. Supporting audits are frozen inside the candidate manifest. The packet explicitly lists incomplete evidence; no reviewer identity or qualified approval invented. Earliest deadline remains 2026-10-21T01:33:00.069116+00:00.
- [x] **C44** · G0/G8 · data eng + owner · Separate validations that require outside authority, evidence or independent human review into an owner review file; retain independently feasible research in the main plan. DONE 2026-10-20 — [owner review queue](COLLIER_OWNER_REVIEW_REQUIRED.md). O01–O05 identify attestations/outcomes Codex cannot supply alone; E01–E04 identify missing external inputs and conditional escalations. Each entry records the owner action and closure evidence. Source checks Codex can still perform remain C38–C42; no data item, hold or release gate is waived or marked accepted.

- [ ] **C36** · G8 · named Medicare subject-matter reviewer · **Final acceptance:** sign off on the exact fields, evidence, cases and immutable R1 release (DQ-012), with review date and refresh deadlines. Required missing facts block release; optional unaccepted features stay disabled. BLOCKED 2026-10-20 — named qualified reviewer and completed data validation required. C12 legal approval is already complete and is distinct from this data review. Owner-review dependency: O01 in [separate review file](COLLIER_OWNER_REVIEW_REQUIRED.md).

### On hold (needs owner approval, recorded in the Decision log)

- [ ] **H01** · G5 · Personal drug-cost calculator. Resume when C14 finds an adequate 2027 price source. Until then, show coverage and pharmacy evidence and link to Plan Finder.
- [ ] **H02** · G3 · Full Florida DCF eligibility rules for QMB, SLMB, QI and QDWI.
- [ ] **H03** · G4 · CSG (or other) Medigap API contract. Resume at national expansion.
- [ ] **H04** · G6 · Commercial provider-network vendor. Resume if the free sources prove too noisy or at expansion.
- [ ] **H05** · G6 · Full sourcing of every provider in all 59 plans as a release gate.
- [ ] **H06** · G0 · National issues DQ-001 (Virginia `H3931-143-000-2027`) and DQ-013 (148 identities). Keep them open in the national ledger; they don't block Collier.
- [ ] **H07** · G8 · Daily refresh operations, rollback rehearsal, full portability gates.
- [ ] **H08** · G4/G5 · Full stratified Medigap test grid and 30-scenario drug replays. R1 uses the smaller sets defined below.
- [ ] **H09** · G9 · Live Medicare.gov queries on behalf of real users, such as a resident's own drug list. This would send personal data through the collector and multiply traffic.

---

## Correct the baseline before measuring progress

| Inventory statement | Verified position and planning consequence |
| --- | --- |
| Only 38 plans can be compared | The catalog and selected-plan comparison expose all **70 captured records**. Some older evidence tools still restrict deeper lookups to the original 38. Remove those restrictions (C05); don't rebuild catalog browsing. |
| 59 Advantage plans and 11 PDPs | Confirmed: **23 non-SNP MA-PD + 9 MA-only + 27 SNP + 11 PDP = 70**. The SNPs are 15 dual-eligible, 9 chronic-condition and 3 institutional. These counts are pending the live-market check (C18). |
| Doctor participation unresolved for all 70 | Clinical networks apply to the **59 Advantage records: 18 contracts across 8 parent organizations** (the inventory said 9 because it counted a PDP-only parent). The 11 PDPs need pharmacy networks. Original Medicare acceptance and Medigap SELECT networks are separate. |
| Package the other 30 pharmacy networks | Correct but incomplete. Packaging, tool eligibility, indexing and tests must change together (C05). |
| 190,096 PBP rows imply complete benefit detail | These are flattened field values, including blanks. Raw capture is complete; consumer interpretation and validation are partial. Measure reviewed consumer fields, not row volume. |
| Stars missing | CMS published the **2027 Star Ratings Data Tables** on October 8, 2026. Import them (C04). [CMS downloads](https://www.cms.gov/medicare/health-drug-plans/part-c-d-performance-data), [technical notes](https://www.cms.gov/files/document/2027-tech-notes-2026-09-30.pdf). |
| Other local options unknown | AHCA's July 2026 report lists **Hope PACE as operational in Collier**. Verify its current service area (C06). [AHCA report, page 5](https://ahca.myflorida.com/file/medicaid/JULY%202026%20Monthly%20PACE%20Report.pdf#page=5). |
| Find the quarterly file for personal drug prices | The monthly 2027 archive has no pricing table, and the quarterly archive is for 2026. Medicare.gov already shows 2027 estimates, which G9 can capture for fixed scenarios. A personal calculator is on hold (H01). [Existing inspection](WORK_PACKAGE_3.md). |

Preserve the supplied inventory as the original assessment. Issue revised status from new evidence rather than editing historical counts.

---

## Scope, timing and roles

**Release 1** covers both coverage paths for Collier with:

- All 70 CMS plan records, with stars and core benefits.
- All 61 drug plans' formulary and pharmacy evidence.
- Florida Medigap products with illustrative rates and buying rules.
- A hospital-by-plan network table, plus doctor lookups where insurer APIs work.
- Original Medicare cost tables (once published), enrollment rules, and a help-program referral.
- PACE, SHINE and coordination flags.
- Medicare.gov observations as an independent check.

**Not in R1:** personal drug-cost calculation, full assistance eligibility, commercial data contracts, and the hold list above.

**Timing.** Annual open enrollment runs October 15 to December 7, 2026, so much of R1 lands late in that window or after it. That's still useful, because Medigap can be bought year-round and new 65-year-olds enroll every month. Prioritize C04, C05 and C06–C08 because they are quick wins during enrollment.

The original plan estimated 6–10 weeks with two engineers. With the cuts above, the working hypothesis for R1 is about 3–5 weeks. Re-estimate after Day 3 (C14, C15 findings) and again once the OIR records response arrives.

**Roles to assign** (responsibilities, not claims that anyone is staffed):

- **Data engineering:** capture, joins, quality checks, the collector, audit exports.
- **Application engineering:** tools, calculations, UI, privacy.
- **Medicare analyst/domain reviewer:** field meaning, rules, independent review.
- **Product/supplier owner:** scope, data access, legal and commercial decisions.

**Parallel start.** Start the three difficult source threads on Day 1 and run them in parallel, not one after another: Medigap (C09), drug prices (C14) and networks (C15).

---

## G0: Baseline and simple coverage table

**Owner:** data engineering. **Effort:** about 1–2 days. **Checklist:** C02, C03, C34.

1. Record the active release, source hashes, parser versions and audit extraction time. Replay the 70/61/59/31 counts. Keep the original 38/32 scope as historical metadata.
2. Keep **one simple coverage table**: layer, status (captured / in app / reviewed), source, retrieval date, open issues, owner, next action. It replaces the more elaborate ledger proposed in v1. Medigap, rules, formularies and providers keep their own native keys; don't force them into a PBP identifier.
3. A blank, unknown or unrated value is never zero and never ineligible.
4. Keep the immutable file/manifest approach. Add an index or SQLite cache only if measured lookup performance requires it. Don't convert all 190,096 PBP values into a relational model.
5. Refresh CMS catalog discovery in a candidate workspace (C03). Rebuilding identical bytes doesn't renew a review.
6. Put audit export generation under a versioned command that reads the same release as the app (C34).

**Done when:** baseline counts replay, every open issue has an owner and next action, and the app and audit workbook come from the same candidate release.

---

## G1: Local market and core benefits

**Owner:** data engineering + analyst. **Checklist:** C17, C18, C19.

**Market check (C18).** Compare 2027 CMS identities and service areas with Medicare.gov results for a fixed Collier ZIP set covering Naples, North Naples, Marco Island and Immokalee. Where a ZIP crosses counties, select Collier explicitly. Use the G9 collector, or manual capture if G9 isn't ready, and save inputs, timestamps and observed IDs. Compare both directions, and explain restricted, withdrawn, sanctioned, statewide PDP and regional offerings instead of deleting them.

**Scope restrictions.** Replace the old comparison-scope checks with evidence-capability checks. Keep SNP eligibility separate from whether its evidence can be read. Review Regional PPO service-area and spending-limit meaning for the 5 additional non-SNP records.

**Core benefit matrix (C19).** Define the field dictionary first. It covers:

- Premiums and Part B reductions.
- Medical and drug deductibles.
- In-network, out-of-network and combined spending limits.
- Primary care, specialist, inpatient, emergency and skilled-nursing costs.
- Referrals and prior authorization.
- Dental, vision and hearing limits.
- Travel and out-of-area rules.

Use 2027 Summary of Benefits / Evidence of Coverage documents to interpret the fields.

**Independent review.** Check critical money and availability fields for all 70 plans:

- Medicare.gov observations from C17 extend the existing 38-plan check.
- Carrier documents extend the 16-plan check.
- An uncertain benefit can't drive a ranking.

**Done when:** the market check has zero unexplained differences; all 70 records have a verification result for every displayed core field; and restricted eligibility is shown without declaring anyone eligible. Closes DQ-005 and DQ-006 only for the fields actually reviewed.

---

## G2: 2027 star ratings

**Owner:** data engineering. **Effort:** 1–2 days. **Checklist:** C04.

Capture the CMS ZIP and technical notes with hashes. Join ratings at contract level to the 24 captured contracts, and keep rating year, publication date and CMS's unrated/suppressed reasons. Don't confuse 2027 ratings with the recalculated 2026 ratings used for quality-bonus payments. The blank star columns in the landscape file stay as raw evidence.

**Done when:** all 70 records show a sourced rating or CMS's stated non-numeric reason, every local contract result is independently checked, and missing ratings never display as zero. Closes DQ-002.

---

## G3: Original Medicare costs, rules and help programs

**Owner:** analyst + application engineering. **Checklist:** C25, C29, C30, C31. **Held:** H02.

**Annual cost tables (C29).** Use effective-dated records for:

- Part A, premium-free and premium-paid.
- Part A benefit-period costs.
- Part B premium, deductible and coinsurance.
- Part B and Part D IRMAA brackets. These are likely relevant for many Naples residents.
- Part D annual parameters.

Import only published 2027 figures, and leave unpublished inputs explicitly pending. Projections and 2026 amounts can't fill in a 2027 total. [Medicare costs](https://www.medicare.gov/basics/costs/medicare-costs).

**Enrollment and compatibility (C30).** Cover initial, general, annual and MA open enrollment windows, supported special enrollment periods, and the Part B and Part D penalties. Medigap open enrollment and guaranteed issue are separate from Advantage switching windows. Compatibility checks prevent impossible packages, such as Advantage plus Medigap. [Joining rules](https://www.medicare.gov/basics/get-started-with-medicare/get-more-coverage/joining-a-plan).

**Medigap buying rules (C25).** Cover:

- The standardized benefits by letter.
- Plan C and F eligibility (first eligible for Medicare before 2020).
- The six-month Medigap open enrollment.
- Guaranteed-issue situations.
- Florida under-65 access.
- SELECT conditions.
- Pre-existing condition treatment.

Sources: [Medicare buying guidance](https://www.medicare.gov/health-drug-plans/medigap/ready-to-buy), [Florida §627.6741](https://www.flsenate.gov/Laws/Statutes/2026/627.6741), [Florida CFO guidance](https://www.myfloridacfo.com/division/consumers/understanding-insurance/medicare-supplement-insurance-overview).

**Help programs (C31), R1 version.** A short screener that says a person *may* qualify for Extra Help, Medicare Savings Programs or Medicaid, explains why, and refers them to SHINE and the official application. It is not an eligibility determination. The full DCF rules engine is held (H02). [SSA Extra Help](https://www.ssa.gov/medicare/part-d-extra-help), [DCF manual](https://www.myflfamilies.com/services/public-assistance/additional-resources-and-services/ess-program-manual/).

**Done when:** every supported rule has a source passage, effective period and reviewer; boundary cases pass; unknown inputs stay unresolved; and the UI never presents a screen as an award or an enrollment guarantee.

---

## G4: Medigap products, rates and rules (Florida-free route first)

**Owner:** supplier owner (access), data engineering + analyst (evidence), application engineering (display). **Checklist:** C09, C10, C22, C23, C24, C25. **Held:** H03, H08.

**Sourcing order (changed from v1).**

1. **Florida OIR public records request (C09).** Since 2008, Florida has required insurers to submit Medicare supplement rates to OIR, and that collection powers CHOICES. Request the underlying dataset under Florida's public records law. This is the cleanest free route. [OIR public records](https://floir.gov/resources-and-reports/public-records-requests), [2008 rule background](https://www.colodnyfass.com/blog/oir-proposed-rule-hearing-report-medicare-supplement-rate-collection/).
2. **OIR rate filings.** Use filings to verify rates and fill gaps; rate tables may need parsing from documents. [IRFS filing search](https://irfssearch.floir.gov/).
3. **CHOICES capture.** Capture CHOICES for Collier scenarios and keep its "illustrative" label. [CHOICES](https://floir.gov/consumers/choices-rate-comparison-search).
4. **Medicare.gov Medigap search (C22, via G9).** Use it to establish which insurer sells which letter in each Collier ZIP.
5. **CSG Market Advisor (C10, optional).** A Florida subscription is listed at $20–40/month and is useful as a cross-check. [CSG pricing](https://csg-actuarial-wordpress.appspot.com/software/market-advisor/pricing/). A CSG API or data-feed contract is held until national expansion (H03).

**Data contract.** Keep these fields:

- Insurer legal identity and NAIC number; product/form, letter, and high-deductible or SELECT variant.
- Rating area, sale status, rate effective date and source.
- Rating basis (age, sex, tobacco), household discounts and conditions, and underwriting assumptions.

Distinguish five states: illustrative rate, filed rate, conditional quote, insurer quote, and unavailable/manual-quote product. A filing shows who *may* sell a product, not who is actively selling it. Never show a conditional premium as guaranteed acceptance.

**R1 validation (smaller than v1).** Use ages 65, 70, 75 and 80, with and without tobacco and household discount, plus one under-65 and one guaranteed-issue case. Reproduce at least one rate per insurer from a second source. Record missing insurers and manual-quote paths. The full stratified grid is held (H08).

**Done when:** the Collier product universe is reconciled across sources, every displayed rate carries its type label and source date, and gaps are listed. DQ-011 closes only when every offered in-scope product has a valid rate or quote route; a partial dataset is a milestone.

**Context for the UI.** Insurers pay agents commissions on Medigap, typically a percentage of premium every year the policy stays in force. Buying direct usually costs the same. Daylight's ranking must never reflect commissions (G8).

---

## G5: Prescription evidence and drug costs

**Owner:** data + application engineering, analyst; supplier owner for price access. **Checklist:** C05, C14, C20, C21. **Held:** H01, H08.

**Unblock existing evidence (C05).** Package and hash all 61 plan pharmacy files plus shared formulary/cost tables. Update `demo_release.py`, the tool/API schemas and `DemoTools.drug_evidence()` together. Bound request size deliberately and test pagination instead of changing 38 to 70. Verify all 61 from the extracted bundle; the 9 MA-only records stay not applicable. Measure startup, memory and latency before adding an index.

**Existing issues.**

- **DQ-003/DQ-004 (C21).** Keep both premium observations, gross and assistance-adjusted, until an authoritative source explains them.
- **DQ-008.** Separate the filename, catalog period, publication and retrieval dates. An October 31 token doesn't prove future freshness.

**Price source check (C14, three days).** Inspect the public CMS distributions for 2027 pricing grain, and assess authorized commercial options in parallel. An average-only source may support a clearly labeled model, never a store-specific quote. [Monthly CMS source](https://data.cms.gov/provider-summary-by-type-of-service/medicare-part-d-prescribers/monthly-prescription-drug-plan-formulary-and-pharmacy-network-information), [quarterly CMS source](https://data.cms.gov/provider-summary-by-type-of-service/medicare-part-d-prescribers/quarterly-prescription-drug-plan-formulary-pharmacy-network-and-pricing-information).

**Medicare.gov estimates (C20).** Capture 2027 drug-cost estimates for the fixed synthetic scenarios in G9. In R1, they validate future calculations and can be shown as dated reference examples labeled "Medicare.gov estimate for this example, retrieved <date>." They are not a resident's personal cost.

**R1 user experience.** Show coverage, tier, restrictions and pharmacy evidence for all 61 drug plans, plus a link to Medicare.gov Plan Finder for a personal cost estimate. The calculator is held (H01). Never import 2026 prices as substitutes.

**Done when:** all 61 drug plans are queryable, DQ-010 is closed, DQ-003/004 are resolved or both shown, and the price-source decision is recorded. DQ-007 stays open until H01 is approved and passes.

---

## G6: Doctor and hospital networks (hospitals first)

**Owner:** data engineering + analyst. **Checklist:** C15, C26, C27, C28. **Held:** H04, H05.

1. **Hospital × plan table (C26).** Hand-check which 2027 Advantage plans each local hospital system accepts, starting with NCH and Physicians Regional, whose pages the audit already captured (`nch-2027-change`, `nch-contracted-plans`, `physicians-regional-group`). Confirm each cell against the insurer directory or a dated hospital/insurer statement. This small table answers the highest-stakes question.
2. **Insurer APIs (C15, C28).** CMS requires public Provider Directory APIs without member/user authentication; developer app registration or API keys may still be required. Public availability does not establish implementation cost or commercial reuse terms. Inspect each of the 8 parent organizations' capability statements, schema, pagination and 2027 plan/network mapping before building adapters. Treat the 8 groups as discovery buckets, not uniform implementations. C15 found representative exact 2027 mappings for Humana and Devoted; the six other groups have documented access/year/mapping gaps. C28 must validate every supported plan and exact provider/location relationship before returning participation answers. [CMS FAQ](https://www.cms.gov/initiatives/burden-reduction/overview/interoperability/frequently-asked-questions/provider-directory-api), [C15 evidence](cms-slice/reports/collier-gap-20261019/c13-c15/c15-provider-api-discovery.md).
3. **Medicare.gov cross-check (C27, via G9).** For plan year 2027, MA organizations submit directories to CMS for Plan Finder. Use those lookups as an independent observation, not ground truth: the Plan Finder directory has shown conflicting entries before. [Washington Post finding, via Rise Health](https://www.risehealth.org/insights-articles/washington-post-report-finds-errors-in-new-medicare-advantage-provider-directory/).
4. **Matching.** NPPES resolves identity and location, not participation. Resolve clinician-at-site and hospital separately; a hospital agreement doesn't prove the physicians there participate. Keep accepting-new-patients and referral/authorization conditions separate from network membership.
5. **States to show:** confirmed, listed in directory, conflicting, stale, unknown. Absence from an incomplete search is not "out of network." Show "call to confirm" whenever the answer drives a decision. Tell users that someone who picks an Advantage plan based on wrong directory information has a 3-month window to switch in their first year.
6. **Original Medicare and SELECT.** Use a separate Medicare participation/assignment route for Original Medicare; SELECT hospital networks are separate again.

**R1 bar (changed from v1):** the hospital table is complete for all 59 Advantage records; doctor lookup works with confidence states for insurers whose APIs passed C15; everything else shows "unknown — call to confirm." Validate at least 15 exact provider/location/plan cases across the insurers covered. Full sourcing of every provider is held (H05).

**Done when:** the R1 bar is met with replayable evidence. DQ-009 stays open for any plan without a verified source mapping.

---

## G7: PACE, other plan types, counseling and coordination flags

**Owner:** analyst + application engineering. **Effort:** 1–3 days. **Checklist:** C06, C07, C08.

- **PACE (C06).** Start from the AHCA July 2026 Hope PACE record. Verify current CMS/state identity, service-area ZIPs, eligibility, assessment, costs and referral. Show it as a separate conditional coverage path, not an add-on. [AHCA reports](https://ahca.myflorida.com/medicaid/recent-medicaid-presentations-and-reports.html).
- **Cost plans, MSAs and other types.** Save a dated search receipt for Collier, whether positive or negative.
- **SHINE (C07).** [Official Collier SHINE directory](https://www.floridashine.org/Counseling-Sites/Collier.aspx). Make the referral visible wherever a rule, assistance or coverage question is unresolved.
- **Coordination flags (C08).** Cover employer/union retiree coverage, VA/TRICARE for Life and existing older Medigap policies. Recognize these before suggesting any coverage change.

**Done when:** PACE has a current documented status and address-based service-area route, other plan types have reproducible search results, and the SHINE contact is usable.

---

## G8: Privacy, integration, review and release

**Owner:** application/data engineering; the domain reviewer signs the review scope. **Checklist:** C01, C37, C32–C36. **Held:** H07.

**Privacy first (C01).** The current app writes visible conversations to local text files. Before any medication, income or quote question reaches real users, define what is requested, logged and retained, and keep personal inputs out of source bundles and the audit workbook. Use synthetic or public cases for development.

**Integration (C32).** Keep Original Medicare alone, Original Medicare + Medigap + PDP, and Advantage configurations distinct. Separate premiums, income adjustments, assistance, drug estimates and utilization assumptions. An out-of-pocket maximum is not expected spending, and Original Medicare doesn't inherit an Advantage cap. A total requires every component; otherwise show the components and what's missing.

**Neutral ranking.** Score only factors supported for that result, and show unscored factors and the full result set. Commissions and insurer relationships must never change ordering. When only some plans have prices, don't call their ordering the cheapest across all local plans.

**Validated-only acceptance (C37, owner requirement October 20).** Every consumer-visible value or claim requires field-level acceptance with authoritative evidence, correct 2027 identity/period/geography/conditions, appropriate independent checks, resolved material conflicts and scoped reviewer approval. Source-only, conflicting, stale and unreviewed values stay research-only. A warning label does not make a value accepted. Missing required R1 facts block release; unsupported optional features stay disabled. The current catalog still exposes source-only monetary fields, so C37 is required before consumer use. See `docs/DATA_VALIDATION_ACCEPTANCE.md`. Engineering completion labels do not assert data acceptance.

**R1 release gates:**

| Gate | Evidence |
| --- | --- |
| Inventory | Market check with explained differences; Medigap and program coverage stated separately from CMS plan counts. |
| Source integrity | Hashes, layouts and unique joins; no silent cross-year substitution; Medicare.gov observations stored as their own source type. |
| Consumer facts | Every consumer-visible field has current, scoped acceptance under C37; unaccepted values are excluded from chat/cards/ordering/totals/exports. Missing required facts block release. |
| Rules | Boundary cases pass; incomplete scenarios are visibly incomplete. |
| Networks and pharmacy | Correct plan/network mapping; dated states; no participation claim from NPI or brand alone. |
| App | All 70 plans browsable; all 61 drug plans usable; restricted eligibility conditional; unsupported factors unscored; same facts in chat, cards and export. |
| Release | Immutable candidate built and the prior release kept (C35). Full rollback rehearsal is held (H07). |
| Review | Named reviewer, date, release hash, fields/cases covered and open limitations (C36). Engineering checks alone don't close DQ-012. |

**R1 refresh (manual, replaces v1's daily operations table):**

- Check CMS landscape/PBP/stars and Medicare.gov observations weekly through December 7, then monthly.
- Ingest each monthly formulary/pharmacy release.
- Recheck Medigap filings monthly and whenever OIR responds.
- Recheck hospital-table cells before each release.
- On a failed refresh, keep the last verified data with its age shown.

---

## G9: Medicare.gov collector (new)

**Owner:** data engineering; supplier owner for C11–C13. **Checklist:** C11, C12, C13, C16, C17, C20, C22, C27. **Held:** H09.

**Why.** Medicare.gov is free to use, CMS-run and commission-free, and it shows things the public files don't yet have:

- 2027 drug-cost estimates during open enrollment.
- 2027 MA provider directory data.
- Medigap insurer and letter availability by ZIP.

There is no public bulk download or API for Plan Finder. CMS's "Finder API" serves Healthcare.gov plans for people under 65, not Medicare. So this is a collector of observations, and it runs alongside the C11 request to CMS for official data access. If CMS grants access, switch to it and retire the collector for that data.

**Before running at scale:**

- **C12, legal.** Get a quick legal read and record the decision. Federal government works aren't copyrighted, and the Medicare.gov privacy policy is silent on automated access, but that is not a substitute for advice.
- **C13, site policies.** Completed policy review is in `cms-slice/reports/collier-gap-20261019/c13-c15/c13-site-policy.json`. The three public entry URLs are not disallowed by saved robots; actual subroutes/backends/other hosts need engineering review in C16. Enforce robots before requests, including browser subresources; `/app-static-content/` is denied. Recheck policies after the recorded review window. Non-denial is not a blanket reuse license.

**Build (C16).**

- **Tooling.** Use Playwright with headless Chromium. Where the site's own pages load structured JSON, capture those responses rather than parsing HTML, and treat them as undocumented and subject to change.
- **Fixed query sets only.** The four query sets are defined below (C17, C20, C22, C27). There are no open-ended crawls and no queries on behalf of real users (H09).
- **Synthetic inputs only.** Use no real resident's data, and no logged-in or Medicare-account pages.
- **Receipts.** For every observation, save the query inputs, URL, timestamp, raw response or page snapshot, a SHA-256 hash, and the parser version, using the existing receipt format.
- **Labels.** Store each value as "Medicare.gov observation, retrieved <date>." It never silently replaces a primary source, and differences go to the discrepancy ledger.
- **Change detection.** If the expected page structure or response shape changes, stop and alert rather than writing partial data.

**Guardrails (proposed defaults; the owner may tighten):**

- **Rate.** At most 1 request every 5 seconds and 2,000 requests per run. Run off-peak, such as overnight Eastern time, especially during open enrollment.
- **Stop conditions.** Stop the run on any 403, 429, CAPTCHA or block page. Never rotate IPs, use proxies to evade limits, or get around logins or CAPTCHAs.
- **Identification.** Send a descriptive User-Agent with a contact address.
- **Cache.** Never re-request an identical query within the same refresh cycle.

**Query sets.**

| Set | Contents | Purpose |
| --- | --- | --- |
| C17, plan facts | All 70 plans × G1 ZIP set: premiums, deductibles, MOOP, drug deductible, star display, plan presence | Market check (G1); extends the 38-plan reference check |
| C20, drug scenarios | About 10 fixed synthetic drug lists: no drugs; common generics; insulin; a brand anticoagulant; a specialty drug; 30- vs 90-day; retail vs mail. Each priced against applicable Collier plans at one retail and one mail pharmacy | 2027 drug-cost reference examples; future calculator validation |
| C22, Medigap | Collier ZIP set × letter plans, high-deductible and SELECT variants | Medigap product universe (G4) |
| C27, providers | The hospital table plus about 30 doctor/practice test cases × relevant Advantage plans | Independent network cross-check (G6) |

**Done when:**

- C12 and C13 decisions are recorded.
- All four query sets have run with complete receipts and stayed within guardrails (shown in the run logs).
- Results are reproducible from saved inputs.
- Observations appear in the regenerated audit workbook as their own source type.
- Differences from CMS or insurer sources are logged, not overwritten.

---

## Coverage of all 15 inventory layers

| Inventory layer | R1 work | Checklist | Closure evidence |
| --- | --- | --- | --- |
| Original Medicare A/B | G3 | C29 | Published 2027 tables; checked scenarios |
| Advantage plan list | G1, G9 | C17, C18 | Two-way market check with receipts |
| Advantage benefit detail | G1 | C19 | Reviewed core field matrix |
| Standalone Part D list | G1 | C18 | Statewide PDP identities reconciled |
| Formularies | G5 | C05 | All 61 plans queryable |
| Drug prices | G5, G9 | C14, C20 (H01 held) | Source decision + dated reference scenarios; personal costs held |
| Pharmacy networks | G5 | C05 | All 61 networks in bundle and tools |
| Doctor/hospital networks | G6, G9 | C15, C26–C28 | Hospital table complete; doctor lookups with confidence states |
| Stars | G2 | C04 | Ratings or CMS reasons for all 70 |
| Medigap plans/prices | G4, G9 | C09, C10, C22–C24 | Reconciled Florida products, labeled rates |
| Medigap buying rules | G3/G4 | C25 | Sourced federal and Florida rules |
| Help programs | G3 | C31 (H02 held) | Screener + SHINE referral |
| Enrollment/penalties | G3 | C30 | Supported rules, boundary cases |
| Other plan types | G7 | C06 | Hope PACE status; dated searches |
| Local counseling | G7 | C07 | Verified SHINE referral |

---

## Disposition of the existing audit issues

| Issue | Action | Checklist |
| --- | --- | --- |
| DQ-001 national landscape-only PBP | Keep open in the national ledger; not a Collier blocker | H06 |
| DQ-002 stars | Import 2027 star data | C04 |
| DQ-003 / DQ-004 premium conflicts | Explain basis or show both | C21 |
| DQ-005 Medicare.gov sampling | Extend to all 70 via collector | C17 |
| DQ-006 carrier sampling | Extend document checks for displayed fields | C19 |
| DQ-007 drug prices | Source decision; calculator held | C14, H01 |
| DQ-008 prescription dates | Keep explicit ambiguity until resolved | C14 |
| DQ-009 clinical participation | Hospital table + insurer APIs + cross-check | C26–C28 |
| DQ-010 packaged networks | Package all 61 + remove cap | C05 |
| DQ-011 Medigap | Florida-free route, reconciled products | C09, C22–C24 |
| DQ-012 qualified review | R1 sign-off | C36 |
| DQ-013 national field variation | Keep tracked; not a Collier blocker | H06 |
| DQ-014 catalog review overdue | New discovery receipt | C03 |

---

## Weekly status report

Report coverage fractions at the right grain, and never combine them into one percentage:

- Reconciled offerings out of expected offerings.
- Reviewed core cells out of applicable core cells.
- Drug plans queryable out of 61.
- Hospital-table cells confirmed out of total.
- Advantage plans with a working doctor-lookup source out of 59.
- Medigap products with a labeled rate out of products identified.
- Collector query sets completed out of 4.
- Checklist items done out of R1 total.

---

## Decision log

| Date | Decision | By | Evidence |
| --- | --- | --- | --- |
| 2026-10-20 | Owner requested a separate file for validations Codex cannot supply alone. C44 creates an owner review queue and distinguishes outside attestations from missing inputs; public-source research remains with Codex. No validation requirement or consumer-release gate is waived. | Plan owner / Codex | [Owner review queue](COLLIER_OWNER_REVIEW_REQUIRED.md) |
| 2026-10-20 | Supersede `naples-a4681d3ab67b75873d38` with `naples-98038a43549f438d8c38` after a concurrent stylesheet change invalidated the earlier workspace binding. Interface change preserved; exact runtime/data file inventories, 8 packaging tests and isolated replay pass. All claims remain pending. | Codex | `cms-slice/reports/collier-gap-20261020/validation/selection-receipt.json`; prior candidate receipts retained in `prior-engineering-candidate/` |
| 2026-10-20 | Select validation testing candidate `naples-a4681d3ab67b75873d38` after isolated bundle replay. Consumer runtime is held until named field/release acceptance; raw research remains available offline. Prior release/bundle retained, no review deadline extended, no consumer approval or legal re-review claimed. | Codex within owner validation instruction | `cms-slice/reports/collier-gap-20261020/validation/selection-receipt.json`; `extracted-replay.json` |
| 2026-10-20 | Owner explicitly authorized inserting the six validation requirements between checklist items and completing all independently feasible work. C37 takes priority; C38–C43 track data checks and acceptance preparation. No unreviewed values may be promoted; external access, OIR delivery and qualified final review remain dependencies. | Plan owner | Current conversation; `docs/DATA_VALIDATION_ACCEPTANCE.md` |
| 2026-10-19 | Plan v2 adopted: R1 scope and hold list; Medicare.gov collector added (G9); Medigap sourcing via free Florida data first; networks start with hospital table | Plan owner | This file |
| 2026-10-19 | Skip C01 for now for owner testing; proceed with C02–C05. C01 remains open and logging behavior is unchanged. | Plan owner | Owner instruction in this conversation: "hold on c01, thats for me and testing ... write skip for now and go on C02 - C05" |
| 2026-10-19 | C04 preserves all three contract rating measures and labels the display as Part D summary for PDP, Part C summary for MA-only, and Overall for MA-PD/SNP. Nonnumeric CMS reasons retain null numeric values. | Codex, engineering source interpretation | `cms-slice/reports/collier-gap-20261019/c04/technical-review.json`; CMS technical notes printed pages 4 and 203; qualified domain review remains C36 |
| 2026-10-19 | Select verified C02–C05 engineering candidate `naples-e63907b345ba6ef846b3` for owner testing, with prior release retained. This is not full R1 sign-off; C32–C36 remain open. | Codex, within owner-authorized C02–C05 work | `cms-slice/reports/collier-gap-20261019/c05/selection-receipt.json` |
| 2026-10-19 | Final testing candidate `naples-63ae25f4b9a870fe7848` supersedes `naples-e63907b345ba6ef846b3` after bounding the release review window by the earliest retained upstream/new-source deadline. Packaging does not renew unchanged source reviews. Prior engineering selection/replay receipts are preserved in `c05/prior-engineering-candidate/`. | Codex | `cms-slice/reports/collier-gap-20261019/c05/selection-receipt.json`; candidate review due 2026-10-21T01:33:00.069116+00:00 |

| 2026-10-19 | C06 uses CMS October 2026 identity and the latest AHCA report linked by the captured index (August 2026). Published Hope PACE county scope is retained; no complete ZIP list is invented. Exact-address eligibility and state assessment use the direct program route. No financial quiz thresholds imported. | Codex, source interpretation | `cms-slice/reports/collier-gap-20261019/c06-c08/source-review.json`; `sources.json` |
| 2026-10-19 | Cost-plan/MSA negative result is limited to the 70-record pinned Collier landscape, not certified live-market absence. SHINE appointment contacts and restrictions come from the official county directory; no booking or referral submission made. | Codex | `cms-slice/reports/collier-gap-20261019/c06-c08/resources.json`; C18 remains open |
| 2026-10-19 | Select verified C06–C08 testing release `naples-69c6cdaa28761a4d80c7`; previous releases retained. The original earliest review deadline remains 2026-10-21T01:33:00.069116+00:00. Concurrent interface updates were preserved and the final bundle rechecked. Qualified domain sign-off and remaining R1 gates remain open. | Codex, within owner-authorized C06–C08 work | `cms-slice/reports/collier-gap-20261019/c06-c08/selection-receipt.json`; `closure.json` |

| 2026-10-19 | C12 legal review is complete on the owner’s explicit confirmation: "Legal said we are good. mark as complete". This records owner-reported approval without inventing counsel identity or opinion text; existing G9 scope/controls and separate C13 review remain. | Plan owner | `cms-slice/reports/collier-gap-20261019/c09-c12/c12-legal-decision.json` |

| 2026-10-19 | C09 public-records request sent from the connected business Gmail account to the official OIR Public Records address. Outbound Gmail/RFC message references are recorded separately from an unassigned agency case number. Fees require separate approval. | Codex, owner-authorized C09 | `cms-slice/reports/collier-gap-20261019/c09-c12/c09-send-receipt.json` |
| 2026-10-19 | C10 decision: defer optional CSG purchase, follow Florida-free sources first, and reconsider if OIR response/C23–C24 identifies a corroboration gap. No trial, subscription or paid API contract started. | Codex, delegated sourcing decision | `cms-slice/reports/collier-gap-20261019/c09-c12/c10-csg-decision.json` |
| 2026-10-19 | C11 inquiry sent to the general MPF mailbox verified in current CY 2027 pricing guidance. Request covers authorized external pricing/provider data access and usage restrictions; supplier access is not assumed while the reply is pending. | Codex, owner-authorized C11 | `cms-slice/reports/collier-gap-20261019/c09-c12/c11-send-receipt.json`; `source-review.json` |

| 2026-10-20 | C13 accepts bounded synthetic public-entry observations under the existing C12 approval and G9 controls. Exact robots denials apply to browser subresources as well; unreviewed API paths/hosts are not automatically approved. C16 must resolve required-path dependencies without bypassing denials. H09 stays held. | Codex, source review | `cms-slice/reports/collier-gap-20261019/c13-c15/c13-site-policy.json` |
| 2026-10-20 | C14 expedited source assessment is complete with a NO GO for personal pricing. No adequate authorized 2027 negotiated price feed obtained; no three-day monitoring claim, purchase or new outreach. Maintain coverage/pharmacy evidence and Plan Finder referral; reopen on adequate authorized source/sample and existing hold approval. DQ-007/008 remain open. | Codex, source feasibility decision | `cms-slice/reports/collier-gap-20261019/c13-c15/c14-price-source-decision.json` |
| 2026-10-20 | C15 allows bounded C28 build work for Humana/Devoted based on two exact 2027 plan/network seeds. Remaining plan mappings and all provider/location participation require validation. Six other parent groups defer with explicit blockers and unknown states. Correct G6: CMS permits developer app registration/API keys, distinct from member authentication. | Codex, primary-source discovery | `cms-slice/reports/collier-gap-20261019/c13-c15/c15-provider-api-discovery.json`; saved CMS FAQ |

| 2026-10-20 | C16 source preflight must stop on the actual HTTP 403 from public bootstrap. Preserve the sticky kill switch; no alternate browser/IP/transport retry or challenge bypass. Local path/readiness reviews before the denial are separate retained evidence. No current plan/drug/Medigap observation set is claimed. | Codex, G9 enforcement | `cms-slice/reports/collier-gap-20261020/c16-c23/c16-guardrail-verification.json`; `c16-active-stop.json` |
| 2026-10-20 | C19 matrix records unknown/coded benefits explicitly for all 70 plans and retains old selected-field review dates. Candidate PBP sections are navigation references, not interpreted benefit values; no expanded DQ-005/006 closure or ranking of unreviewed benefits. | Codex, evidence classification | `cms-slice/reports/collier-gap-20261020/c16-c23/c19-core-benefit-matrix.json` |
| 2026-10-20 | C21 uses the permitted display-both treatment. Show gross/subsidy/beneficiary source fields and monthly PUF PREMIUM separately; never infer a subsidy-adjusted PUF basis or personal eligibility from matching zeros. Source conflicts remain unrankable. | Codex, source-preserving display | `cms-slice/reports/collier-gap-20261020/c16-c23/c21-premium-basis-display.json` |
| 2026-10-20 | C23 partial dataset uses annual illustrative CHOICES amounts only. A requested 2027 date is not a confirmed effective date. IRFS insurer/filing metadata is not a row-level premium join. OIR case 26-045612 is acknowledged but no responsive dataset has arrived; no fees/new messages authorized or sent. DQ-011 remains open. | Codex, source scope | `cms-slice/reports/collier-gap-20261020/c16-c23/c23-florida-medigap.json`; `c23-oir-acknowledgment.json` |
| 2026-10-20 | Select tested C21 owner-testing candidate `naples-d2191e850e290c659753`, retaining prior releases, all 70 records/61 networks/24 star contracts and original review deadline 2026-10-21T01:33:00.069116+00:00. Existing interface work retained; recursive asset packaging preserves its fonts/art. This is not R1/domain sign-off. | Codex, within authorized implementation | `cms-slice/reports/collier-gap-20261020/c16-c23/selection-receipt.json`; isolated bundle/premium replays |

| 2026-10-20 | Owner requires validated-only data. A completed engineering milestone, source hash or passing test suite is insufficient acceptance. Add C37 to require per-field evidence/reconciliation/reviewer acceptance and prevent consumer exposure of unaccepted values. Existing research evidence and historical milestones remain; C19/C21 completion is not domain approval. No production acceptance granted to the current candidate. | Plan owner | Owner: "non-validated data is unacceptable"; `docs/DATA_VALIDATION_ACCEPTANCE.md` |

## Change log

| Date | Change | By |
| --- | --- | --- |
| 2026-10-19 | v2: added Agent protocol, checklist (C01–C36, H01–H09), G9 Medicare.gov collector; revised G0, G3, G4, G5, G6, G8; moved privacy to C01; added decision and change logs | Claude |
| 2026-10-19 | Recorded owner-directed C01 deferral and started C02 baseline replay and coverage table. | Codex |
| 2026-10-19 | C02 replayed and preserved the 70/61/59/31 baseline, source/runtime hashes and coverage/issue ownership table; started isolated C03 catalog refresh and C04 official CMS source capture. | Codex |
| 2026-10-19 | C03 completed with retained prior receipts and a one-day review deadline; C04 imported 24 contracts with 72 CSV/workbook cell checks; started C05 packaging and bounded query access. | Codex |
| 2026-10-19 | Completed C04/C05: sourced stars for 70 records, packaged all 61 pharmacy networks, capability-based paginated drug access, 166 passing tests and offline extracted-bundle replay; selected the testing candidate and added separate DQ-002/DQ-010/DQ-014 closure receipts without editing the historical audit. | Codex |
| 2026-10-19 | Final freshness check retained original source review limits; all 166 tests and the extracted-bundle replay passed again for selected testing release `naples-63ae25f4b9a870fe7848`. | Codex |
| 2026-10-19 | Started owner-authorized C06–C08, beginning with official Hope PACE/state service-area and eligibility evidence. C01 remains deferred. | Codex |
| 2026-10-19 | Completed C06–C08 with 11 pinned-source PACE/SHINE/coordination facts, 12 packaged primary sources, dated bounded other-plan-type search, 177 passing tests, final 11-case source check, Chrome evidence and isolated offline replay. Selected testing release `naples-69c6cdaa28761a4d80c7`; historical audit and C01 deferral preserved. | Codex |
| 2026-10-19 | Started owner-authorized C09–C12: verify OIR/CMS request routes, decide the optional CSG cross-check purchase, and prepare the legal review packet. C01 remains deferred; no collector run or paid contract authorized by this status entry. | Codex |
| 2026-10-19 | Recorded owner confirmation of legal approval and completed C12. C09–C11 work continues. | Codex |
| 2026-10-19 | C09 request sent and transport reference saved; C10 purchase deferred with a sourced decision; C12 legal approval recorded per owner. C11 inquiry sent and remains open for the CMS reply. Eight official/vendor source captures and exact sent-message body checks saved under `c09-c12`. Runtime and testing release unchanged. | Codex |
| 2026-10-19 | Started owner-authorized C13–C15: site-policy review, 2027 pricing-source feasibility assessment, and discovery of provider-directory interfaces for all eight Advantage parent organizations. | Codex |
| 2026-10-20 | Completed C13–C15 with saved robots/policies, expedited 2027 pricing no-go decision, eight-parent/59-plan API discovery, retained raw failures, schema/pagination checks and offline evidence verification. Corrected G6 app-registration assumption. C01 deferral, C11 reply dependency, DQ history, hold list, selected release and original source review deadlines retained. | Codex |
| 2026-10-20 | Started owner-authorized C16–C23: guarded collector, fixed synthetic observation sets, market comparison, core benefit matrix, premium basis display and Florida Medigap source assembly. | Codex |
| 2026-10-20 | Built C16 guarded collector core and preserved actual HTTP 403 stop; C17/C18/C20/C22 remain blocked with prepared fixed queries and explicit missing coverage. Completed C19 70-plan/24-field matrix and C21 separate premium bases; C23 partial CHOICES/IRFS dataset plus official OIR case acknowledgment saved. 191 tests and isolated 61-plan/9-MA-only/24-contract/premium replays pass; new owner-testing release selected without renewing source deadlines. | Codex |
| 2026-10-20 | Recorded owner's stricter data-acceptance bar and added C37 before consumer use. Audited current validation scope and the catalog's source-only display/ordering path; documented exact validation requirements, external dependencies and pending domain acceptance. No runtime behavior changed by this policy update. | Codex |

- 2026-10-20 — Inserted the owner’s validation requirements beside the related checklist items (C38–C42), strengthened C36, added acceptance-packet task C43, and began C37/C39/C43. Existing milestone/history evidence and all holds retained.

- 2026-10-20 — Validation execution: fail-closed runtime implemented; 200 tests pass before the final supporting-evidence packaging change. Added 14-plan selected financial audit, four-plan/four-ZIP carrier reconciliation, all-61 pharmacy join replay, four additional product/formulary cases with version/unit issues, and a 118-cell hospital validation queue. Complete acceptance remains pending.

- 2026-10-20 — Completed C37 engineering admission gate and C43 unsigned review-packet preparation; selected and isolated-replayed `naples-a4681d3ab67b75873d38`. All 2,036 required claims remain pending; C36 and C38–C42 remain open. Prior artifacts and original refresh deadline retained. No outbound messages, paid actions, real-user scenarios or Medicare.gov retries.

- 2026-10-20 — Final validation candidate `naples-98038a43549f438d8c38` preserves concurrent stylesheet work; exact runtime/data file inventory checks prevent unlisted files inheriting acceptance. Eight final packaging tests and isolated CLI/HTTP replay pass. Superseded candidate receipts retained; consumer access stays closed and the original deadline is unchanged.

- 2026-10-20 — Completed C44: created `COLLIER_OWNER_REVIEW_REQUIRED.md` and linked dependencies beside the affected checklist items. Listed outside review/access/records and conditional confirmations separately from work Codex can still complete. Acceptance state, source-review deadlines, C12 approval and all holds unchanged.
