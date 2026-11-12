# C09–C12 — October 19, 2026

| Item | Status | Result and evidence |
| --- | --- | --- |
| C09 | Request sent; sending task complete | Sent to OIR Public Records at **22:35 Eastern**. Gmail reference `1a157298265d98b7`. Exact message and sent receipt: `c09-oir-request.md`, `c09-send-receipt.json`. The **OIR-assigned case number remains pending**; the Gmail reference is a transport record, not an agency case number. |
| C10 | Complete — defer purchase | Follow the approved Florida-free sourcing order while OIR responds. **$0 committed**, no subscription or trial. Revisit after OIR’s response or a C23/C24 second-source gap. Decision: `c10-csg-decision.json`. |
| C11 | In progress — awaiting CMS reply | Sent to **MPF@cms.hhs.gov** at **22:35:13 Eastern**. Gmail reference `1a15729b56f1606c`. Exact inquiry and receipt: `c11-cms-request.md`, `c11-send-receipt.json`. The reply is required before this item is complete. |
| C12 | Complete — owner-reported legal approval | Owner stated, **“Legal said we are good. mark as complete”**. This confirmation is the decision evidence; no attorney identity or written opinion is invented. See `c12-legal-decision.json`. |

Both government inquiries were sent from the connected business account, `chris@beaconfederaladvisory.com`. The sent copies were read back from Gmail and their sender, recipient, subject and HTML body were checked against the prepared messages. Gmail’s SENT status confirms sending through the account; it does not establish recipient delivery or agency acknowledgment. No fees or paid service were authorized. The requests contain no beneficiary records, actual prescriptions or credentials.

The OIR request asks for the existing collection behind CHOICES, the most recent complete statewide data plus already-held 2027-effective records, and any maintained schema/instructions. It requests rate basis, insurer/form/letter/variant, geographic, effective-date and discount fields where held. It asks for a cost estimate before any paid work and requests an acknowledgment/tracking number. Receipt of data and ingestion remain C23.

The CMS inquiry covers authorized outside-organization access to CY 2027 MPF drug pricing and CMS-ingested/validated MA provider directories or source-URL rosters. It asks about plan/year/network identifiers, effective dates, application/DUA routes, fees, caching, commercial use and redistribution restrictions. It explicitly distinguishes an independent developer from a plan sponsor. No HPMS access entitlement, available public bulk feed or reuse permission is inferred.

The CMS contact was verified in the current **CY 2027 Drug Pricing Submission Guidelines**, PDF page **18**, within the official pricing-guidelines ZIP. The May 8 and September 2, 2026 provider-directory memos and public Provider Directory API FAQ were also retained. CMS’s separate Finder.HealthCare.gov API is not treated as the Medicare Plan Finder API. Exact source URLs, raw SHA-256 hashes, archive members and the support review are in `sources.json` and `source-review.json`.

CSG’s captured pricing page advertises monthly single-state Bronze **$20**, Silver **$30**, and Gold **$40**. That is advertised per-state pricing, not a verified Florida checkout quote or a data redistribution license. A later manual Medigap cross-check can start by evaluating Bronze monthly if the free sources leave a gap. H03 remains held.

The scoped reply/bounce check found no matching inbound messages as of **2026-10-20 02:37:04 UTC**. This is a dated observation, not a guarantee about later mail. Internal follow-up dates are **October 22** for OIR acknowledgment and **October 26** for CMS; neither date is an agency response deadline. See `agency-reply-check.json` and `status.json`.

C12 approval is recorded against the existing G9 collection scope. C13 remains a separate prerequisite, existing G9 guardrails still apply, and H09 remains held. No collector, paid legal engagement or paid data contract was started. This batch updates the plan and supplier records; it does not change runtime code or the selected testing release.

Official contact/pricing sources: [Florida OIR Public Records](https://floir.gov/resources-and-reports/public-records-requests), [CSG pricing](https://csg-actuarial-wordpress.appspot.com/software/market-advisor/pricing/), and [CMS 2027 pricing guidelines](https://www.cms.gov/files/zip/2027-pricing-data-guidelines-calendar.zip).
