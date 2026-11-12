# C06–C08 completion — October 19, 2026

Hope PACE, official Collier SHINE referrals, and existing-coverage coordination are implemented in the source tools, chat, interface, and portable testing release. C01 stays **SKIP FOR NOW** for owner testing. No other checklist work is started by this completion.

| Item | Result | Evidence |
| --- | --- | --- |
| C06 | Hope PACE is a separate conditional program. CMS October 2026 directory identity is H5934; AHCA August 2026 lists Collier operational. Published county scope is Charlotte, Collier and Lee. Exact residence, state care assessment and individual costs require program confirmation. | `resources.json`, `source-review.json`, `sources.json` |
| C07 | Official statewide SHINE phone/TTY, counseling request link, two Collier appointment sites, members-only restriction and checked date are visible. The hosting/volunteer liaison is distinguished from appointment contacts. | `resources.json`, `final-browser-resources.jpg` |
| C08 | Employer/union retiree, VA, TRICARE/TFL and existing Medigap mentions trigger sourced review notices. VA does not imply TFL eligibility. Explicit corrections clear the relevant flags and survive bounded chat history in tab state. Catalog membership/order stays intact. | `tests/test_local_programs.py`, `extracted-bundle-local-programs.json`, `final-browser-coordination.jpg` |

The captured Hope PACE pages do not publish an exhaustive ZIP list. `zip_codes: null` preserves that gap; the enrollment line is the address-based confirmation route. A ZIP match, age, or diagnosis does not establish eligibility. No financial quiz thresholds were imported, and no eligibility decision, referral submission, call or appointment booking was made.

The dated cost-plan/MSA search found no matching record among the 70 pinned Collier landscape records. `source-review.json` records the source hash, snapshot, query conditions and observed types. This is a bounded source result; C18 still covers live market completeness.

The source captures were checked October 19 Eastern / October 20 UTC. The selected testing release is **`naples-69c6cdaa28761a4d80c7`**. `selection-receipt.json` binds its bundle, manifest, test log, isolated replays and visual QA. Previous release `naples-63ae25f4b9a870fe7848` is retained. The existing review deadline remains **2026-10-21 01:33 UTC**; repackaging has not renewed older source reviews. Qualified domain sign-off remains pending.

Validation:

- **177 tests pass** in `tests.log`, including 11 new local-program checks and expanded portable-bundle questions.
- The extracted bundle runs all six new resource/coordination scenarios with an empty PATH, no model credentials, no workspace data and blocked network access. All 11 facts resolve to their 12 packaged source hashes.
- The full catalog regression independently replays all 61 drug plans plus nine MA-only not-applicable states, all 61 pharmacy networks, and star display states for 70 plans / 24 contracts. See `extracted-bundle-catalog-regression.json`.
- Chrome checks cover unknown intake answers, source/appointment disclosures, all four coordination notices, and continued plan browsing. PDF visual checks cover AHCA page 5 and Medicare Medigap guide PDF pages 28 and 31. See `visual-qa.json`.
- A preexisting multi-choice intake bug blocked map entry by replacing selection arrays with the string `set`. The Continue handler now preserves the selected arrays. Existing interface work is preserved.

Reproduce workspace checks from `cms-slice`:

```sh
python3 scripts/local_programs.py verify
python3 -m unittest discover -s tests -v
node --check apps/chat/app.js
```

For the isolated check, extract the selected release tarball into an empty directory and run `verify_offline.py` from that directory, passing an absolute output JSON path. Set PATH, OPENAI_API_KEY and OPENAI_MODEL to empty strings and invoke Python by its absolute executable path. Then run the extracted `scripts/verify_collier_bundle.py --release snapshot --require-isolated --out <absolute-output-path>` under the same environment. The scripts reject workspace-dependent or network-dependent replays.

Official sources include [CMS plan directory](https://www.cms.gov/data-research/statistics-trends-and-reports/medicare-advantagepart-d-contract-and-enrollment-data/ma-plan-directory), [AHCA PACE report](https://ahca.myflorida.com/file/medicaid/August_2026_PACE_Report.pdf), [Hope PACE eligibility](https://hopepace.org/eligibility/), [Medicare PACE rules](https://www.medicare.gov/health-drug-plans/health-plans/your-coverage-options/other-medicare-health-plans/PACE), [Collier SHINE directory](https://www.floridashine.org/Counseling-Sites/Collier.aspx), [Medicare retiree coordination](https://www.medicare.gov/supplements-other-insurance/retiree-insurance), [VA coordination](https://www.va.gov/resources/veterans-turning-65-va-healthcare-medicare-and-tricare-for-life/), [TRICARE Medicare eligibility](https://www.tricare.mil/Plans/Eligibility/MedicareEligible.aspx), and [Medicare Medigap guide](https://www.medicare.gov/publications/02110-medigap-guide-health-insurance.pdf). Exact URLs, retrieval dates, SHA-256 hashes and support locations are retained in the source registry and review artifacts.
