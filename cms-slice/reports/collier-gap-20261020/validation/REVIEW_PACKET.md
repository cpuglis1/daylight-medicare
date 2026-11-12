# Collier validation and acceptance packet — October 20, 2026

**Consumer acceptance: pending. No claims or rates have been approved.** The consumer runtime is closed while the required checks remain incomplete. The exact immutable candidate is **naples-98038a43549f438d8c38**, recorded in `candidate-binding.json`; `reviewer-template.json` is unsigned and contains no approvals. The preserved source-review deadline is 2026-10-21T01:33:00.069116+00:00.

| Workstream | Completed evidence work | Remaining acceptance work |
| --- | --- | --- |
| Availability | Four exact Optimum plan identities reconciled with carrier results in all four Collier ZIPs; saved searches, plan details, document links and exact 2027 SB covers | Current full 70-plan Medicare.gov reconciliation remains blocked after HTTP 403. UHC H1889-026's official page is a material lead: Collier listed, but new enrollment closed starting January 2027. Local origin retrieval denied; no hashed local UHC document is claimed. |
| Benefits/costs | Fourteen additional SNP/Regional PPO records: 42 selected cells inspected; 40 numeric agreements, one premium-basis difference, one CMS nonapplicable drug field whose carrier negative was not established. Exact source hashes/pages and conditions retained. Earlier 16-plan selected-field checks remain separately dated. | All 70 plans × every required/displayed field need exact SB/EOC interpretation and named review. Neither selected checks nor matching numbers validate whole plans. DQ-003/004 remain open. |
| Drugs/pharmacies | 61 network captures and 3,506,965 rows checked for exact plan identity; synthetic pharmacy join replay. Four new product/formulary cases across two carrier publications, eight plan/product joins, 20 matching selected fields. Twelve older carrier drug cases/58 checks retained. | Carrier formulary versions 27024 v9 and 27025 v10 exceed pinned CMS versions v8/v9; four selected cases are affected. Trulicity quantity has no established common physical unit. Independent current pharmacy participation and adequate authorized pricing/worked costs remain missing. |
| Medigap | Existing 3,876 annual CHOICES research amounts retained with no accepted effective dates. Inbox rechecked: OIR 26-045612 acknowledgment only. | Responsive OIR records, insurer/form/variant/date joins, rating assumptions and independent filing/insurer rate reproduction. No accepted rate and no fee authorized. |
| Providers | Current NCH and Physicians Regional Medical Group source pages saved; 118 hospital × MA-plan review cells inventoried | Exact facility/provider, location, medical network and 2027 plan evidence. NCH's dated 2027 Wellcare notice and generic payer list differ in date/scope; hospital and medical-group Humana lists also differ. No participation cell is confirmed. |
| Release/review | Fail-closed consumer admission and field/output checks; 2,036 required claims; default-pending registry; immutable candidate, portable replay and unsigned reviewer template | Named Medicare subject-matter reviewer, completed required evidence, exact-release acceptance and refresh deadlines. Legal approval is already complete; no domain approval is invented. |

## Evidence to inspect

- `validation-status.json`: summary and remaining independent work.
- `financial-audit.json`: amounts, units, conditions, exact PDF pages and SHA-256 receipts for the new selected financial checks.
- `humana-documents.json`, `optimum-documents.json`, `sources.json`, `raw/`, `pages/`, `text/`: captured PDFs, source metadata, rendered review pages and extracts. Optimum's public links for EOC 16/17 returned non-PDF content; full EOC review is not claimed.
- `carrier-market-check.json`, `optimum-document-receipts.json`, `optimum-document-link-receipts.json`: bounded carrier availability scope and document discovery.
- `optimum-drug-cases.json`: exact products, formulary and version mapping, selected restrictions and quantity-unit limitation.
- `pharmacy-join-audit.json`: every packaged network, raw flags, counts and synthetic worked join.
- `hospital-validation-queue.json`: all 118 unconfirmed cells and material source-scope issues.
- `mail-status.json`, `source-access-log.json`: OIR status, access failures and zero Medicare.gov requests during this validation work.
- `required-claims.json`: research inventory. The candidate's immutable `validation-requirements.json` is the acceptance authority; `candidate-binding.json` and `reviewer-template.json` bind that exact version.
- `final-tests.log`, `extracted-replay.json`, `selection-receipt.json`, `manifest.json`: engineering verification and artifact hashes. Passing tests do not provide domain acceptance.

## Review decisions required

The named reviewer must verify field meaning, exact plan/year/area/population, primary-source pages/rows, monetary and quantity units, exceptions and conditions; resolve material disagreements; review workstream cases; and record a refresh deadline no later than the retained source deadline. Each required claim must be accepted individually. Exact output receipts are also required for consumer facts and structured fields. Missing required facts block release; unsupported optional outputs remain disabled.

The packet is ready for continued evidence work and review. It is not a request to approve missing evidence, accept an entire plan from a sample, or treat an illustrative rate as validated. Full carrier field audits and independent participation checks remain work that Codex can continue; CMS access, OIR delivery and qualified final acceptance require outside action.
