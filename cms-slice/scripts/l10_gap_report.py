"""Generate the exact L10 download handoff and remaining-obligation ledger."""
from collections import defaultdict
import json
from pathlib import Path

from l10_gap_sources import ROOT, BASE, WORK, read, write
from l10_gap_build import BLUE, PRIOR, ORIGINAL, PORTAL


def generate():
    out=WORK/'build-r1'
    if (out/'SEALED').exists():raise ValueError('Sealed revision')
    coverage=read(out/'coverage.json');items=read(out/'download-items.json');by_case={r['case']:r for r in items}
    records={r['case']:r for r in read(out/'filing-records.json')}
    labels={'25-043172':'Blue individual standard: corrected 2026-cycle source',
            '25-043125':'Blue individual SELECT: corrected 2026-cycle source',
            '25-007663':'Humana: prior rates for the supplied New MIPPA forms',
            '25-030887':'American Benefit Life: prior rates for the supplied forms',
            '25-023045':'Washington National: prior rates for the WNIC2096 forms',
            '25-039153':'GPM: prior rates for the supplied MTM forms',
            '17-20542':'Humana: original A/F/F-HD/G/N forms and applications',
            '20-013251':'Humana: original high-deductible G form/application',
            '21-014407':'American Benefit Life: original A/F/G/N policies and application',
            '22-005454':'Washington National: original WNIC2096 policies/application',
            '23-008889':'GPM: original MTM policies and application/payment conditions'}
    first_order=BLUE+PRIOR+ORIGINAL
    lines=['# L10 Medigap filing downloads','',
           'Start with the 11 targeted filings below. A second batch contains 76 additional sample-company, legacy and group filings. Company identity, filing existence and public attachment lists were checked on October 28, 2026; actual 2026 premium periods and product applicability must still be established from the delivered contents.','',
           f'Open [OIR IRFS]({PORTAL}), choose **Quick Search**, enter the exact filing number, select the matching result and use the filing document action. Choose **Single request, entire filing** for its available public portions. Preserve amendments, replaced versions and approval context. Save the original PDFs or native files in `plans/l10-medigap-2026/`, with the filing number in the filename.','',
           'The filing links below open the verified official portal. Its inspected result controls use inline actions and do not expose a verified permanent per-filing/PDF URL. Copy the number into Quick Search. No invented deep links or expiring encrypted attachment tokens are used.','',
           '## First download batch','',
           '| Filing to enter in Quick Search | Purpose | Public documents listed | Approved public schedule documents |',
           '| --- | --- | ---: | ---: |']
    for case in first_order:
        r=by_case[case];lines.append(f"| [{case}]({PORTAL}) | {labels[case]} | {r['public_documents']} | {r['approved_public_schedules']} |")
    lines += ['', 'The four prior-rate filings are exact company/policy-block leads. Their actual approval periods remain a document check. The five original form cases match the supplied form identifiers in retained OIR metadata; subsequent amendments and current application versions must remain in the review. Public schedule counts are document counts, not plan or rate-cell counts.','',
              '## Additional insurer and product filings','',
              'These 76 cases include the 29 sampled insurers still missing filing PDFs and additional Blue/Washington National legacy or group blocks. Some have explicit 2026 memo titles; others have undated or earlier-cycle material that may govern part of 2026. They are a checked source queue, not a claim that all products remain on sale. The pending bulk OIR response may replace many individual downloads.','',
              '| Legal company from retained filing metadata | NAIC | Filing numbers |','| --- | --- | --- |']
    grouped=defaultdict(list)
    for r in items:
        if r['tier']=='2':grouped[(' / '.join(r['companies_raw']),'; '.join(r['naics_raw']))].append(r)
    for (name,naic),rs in sorted(grouped.items()):
        links=', '.join(f"[{r['case']}]({PORTAL})" for r in rs)
        lines.append(f'| {name} | {naic} | {links} |')
    lines += ['', 'The [CSV checklist](build-r1/download-items.csv) contains all 87 unique requested cases, product labels, purposes, cycle-title status and public/restricted document counts. The [document registry](build-r1/document-registry.json) preserves exact attachment titles and statuses. Request public portions only; restricted/secret contents remain outside this request.','',
              '## Cases held for future year evidence','',
              'The following seven cases have 2027 memo/certification titles. They stay out of the 2026 collection batch pending actual period evidence. The two supplied Blue PDFs remain retained in r3.','',
              '| Filing | Company | Year signal |','| --- | --- | --- |']
    for r in read(out/'future-cycle-holds.json'):
        evidence=next(e['title'] for e in r['cycle']['evidence'] if e['year']==2027)
        lines.append(f"| {r['case']} | {' / '.join(r['companies_raw'])} | {evidence} |")
    lines += ['', '## Broader coverage and earlier sources','',
              'Fifty inspected 2024 sample-company cases remain in the [earlier-period reserve](build-r1/earlier-carryforward-reserve.json). Delivered approval periods will determine which of those are needed to establish January 2026 continuity. They are not presumed expired.','',
              'Another 278 recent approved rate cases fall outside the 34-company CHOICES sample and remain in the [broader census classification queue](build-r1/broader-census-classification-queue.csv). Their exact 2026 business state, forms and Collier relevance must be classified against official collection/filing contents before treating every packet as a required owner download. The 34 sampled names and 188 historical leads are not a proven all-market denominator.','',
              'Request **26-045612** remains the bulk route. A new exact-case mail check returned the sent follow-up and original acknowledgment, with no dataset attachment in those two results. No new message was sent. A response containing 2026-effective records, including prior filings and a data dictionary, could satisfy many rows together.','',
              '## Already collected','',
              'The new public source collection includes the FSRBC 2026 Cigna proposal and annual guide, Orange County 2026 retiree handbook and Physicians Life Florida household questionnaire. Those four PDFs are already retained under `public-sources/documents/`; no duplicate owner download is needed. Carrier form lists and membership qualifications are also retained with exact source receipts.','']
    (WORK/'DOWNLOADS.md').write_text('\n'.join(lines))

    ledger=[
        {'id':'F01','status':'partial_required_product_census','resolved_now':'All 74,671 retained metadata rows accounted for in 14,090 cases; 421 recent approved rate cases inspected, plus five original form cases. 315 exact form metadata entries, 2,095 schedule-document leads and 19 carrier-published form identifiers are retained.',
         'remaining':'Actual complete 2026 company/form/letter/variant/business-state/Collier denominator, with group and SELECT qualifications. Current web form lists and metadata do not prove every product remains for sale.',
         'next_evidence':'Official 2026 collection plus applicable delivered filing contents and dated carrier business-state evidence; broader 278-case queue remains explicit.'},
        {'id':'F02','status':'sample_source_pointers_resolved_payloads_pending','resolved_now':'Exact filing leads and public indexes now exist for all 34 sampled company names, including the ten without a lead in the prior 2026-filed-only search. The owner queue has 11 targeted and 76 additional cases.',
         'remaining':'Applicable filed PDF/native contents for the 29 sampled companies without packets, plus unresolved additional products. New group documents are not substitutes for their filing universes.',
         'next_evidence':'Public portions of the listed filings or equivalent bulk OIR delivery; AI handles transcription and joins.'},
        {'id':'F03','status':'earlier_period_source_cases_identified','resolved_now':'Prior matching company/policy-block cases identified: Humana 25-007663; American Benefit Life 25-030887; Washington National 25-023045; GPM 25-039153.',
         'remaining':'Actual earlier-2026 approval intervals and rate values, including amendments and any earlier carry-forward needs.',
         'next_evidence':'Four prior-rate public packets first; use their letters to select from the 2024 reserve if necessary.'},
        {'id':'F04','status':'year_shortlist_corrected_actual_periods_pending','resolved_now':'Blue 25-043172/25-043125 have 2026 cycle evidence. Seven 2027-titled cases across Blue, EPIC, Medico SELECT and Physicians Mutual are separately held.',
         'remaining':'Actual Blue 2026 premium periods, exact form/area relationships and SELECT conditions; titles never supply effective dates.',
         'next_evidence':'Corrected Blue public packets, and available 2026 table/period evidence; no secret contents requested.'},
        {'id':'F05','status':'rating_source_conditions_partially_resolved','resolved_now':'Five original form/application filings matched; ABL original metadata corroborates the P-bearing filed form names without aliasing its conflicting memo. Four Physicians Life questionnaire statements, eight group qualifications and 72 group price observations are retained. Nineteen public form identifiers have 15 exact raw metadata matches; nearby spellings remain candidate-only.',
         'remaining':'Exact application/discount qualification, fees, billing precision and rounding for the applicable forms/periods. Humana and GPM precision differences remain unchosen. Group-specific prices and eligibility remain distinct.',
         'next_evidence':'Original public form/application packets and applicable native rate manuals/workbooks, then qualified interpretation of genuine remaining ambiguity.'},
        {'id':'F06','status':'review_and_release_decisions_pending','resolved_now':'New research is mechanically auditable, with exact sources, scope, dispositions, year/identity/unit safeguards and preserved parents.',
         'remaining':'Qualified review where required, actual source-use decisions for intended use, and acceptance of the exact eventual reference. These are not replaced by tests or the instruction to collect.',
         'next_evidence':'Resolve source/field gaps before exact-scope review; consumer quoting, recommendations and either UI remain outside this change.'}]
    write(WORK/'gap-ledger.json',ledger)
    report=['# L10 Medigap gap resolution','',
        'October 28, 2026. The available retained-data and public-source pass is complete within the scope below. Full L10 remains partial. The owner handoff is a checked filing queue with source questions, not another list based only on submission year.','',
        '## Resolved in this revision','',
        '- Reconstructed all **74,671** retained filing metadata rows into **14,090** case groups and inspected every **421** retained approved rate/Both case submitted in 2024-2026, across all companies. Five older original policy/application cases bring the new inspection scope to **426** cases.','',
        '- Accounted for **10,584 attachment entries**, **315 exact form metadata entries** and **2,095 rate-schedule document leads**. Public/restricted flags, replaced/approved statuses and original strings remain explicit. These are source extents, not counts of verified policies or premiums.','',
        '- Identified filing sources for **all 34 sampled company names**, including the ten that had no approved rate lead in the earlier 2026-filed-only detail set. The 188-company historical catalog remains intact.','',
        '- Identified **four prior-rate packets** and **five original form/application packets** for the supplied models. Original ABL metadata confirms the P-bearing form identifiers used by its approved tables; the memo spelling is retained without automatic aliasing.','',
        '- Corrected **seven 2027-titled cases** out of the primary 2026 queue, including EPIC 26-030965/26-034262, Medico SELECT 26-038954 and Physicians Mutual 26-038999. Late-2026 revision dates cannot relabel those memo cycles. Actual effective intervals remain document checks.','',
        '- Collected **four public PDFs / 140 pages** and 14 additional public pages, retaining 72 group amount observations, eight group qualifications, four Physicians Life questionnaire conditions and five carrier-page claims. Nineteen published form identifiers are cross-referenced, with 15 exact raw-form matches and explicit unresolved edition/spacing candidates.','',
        '## Source qualifications that matter','',
        'The FSRBC materials restrict their group route to participating school-district retirees; the HealthSpring page names Manatee, Orange and Osceola. Orange County’s handbook concerns its eligible retiree/dependent group. These are conditional routes for an eligible person who might reside in Collier, not general individual offers. No employer affiliation or personal eligibility is inferred.','',
        'The FSRBC proposal does not explicitly label its amount unit, so its 30 values keep that uncertainty. Twelve matching guide values have an explicit monthly heading. Orange County contributes 30 monthly values under its own group. Across the two groups, 29 corresponding Florida values agree and one differs by one cent; group/account/form identities are not merged. The guide also contains explicitly older benefit constants, which are retained as context and do not replace accepted 2026 federal costs.','',
        'The public Physicians Life questionnaire supplies two household questions and approval/timing/applicability language, but no discount percentage. Current carrier pages establish published form strings or qualifications only within their stated scope. Americo’s linked Florida outline returned 404, and its basics page contains an older benefit constant; no 2026 prices or constants are inferred. WPS page differences do not settle actual Florida sale status. See [source limits](public-source-limitations.json).','',
        '## Owner download handoff','',
        '[Start with the 11 targeted filings](DOWNLOADS.md#first-download-batch). The same file lists the 76 additional cases; [the CSV](build-r1/download-items.csv) contains all 87 unique entries and their source purposes. Each has a checked public attachment index. IRFS uses in-page actions in the inspected flow, so links open the verified official portal and the exact filing number is supplied for Quick Search. No unverified permanent PDF links are advertised.','',
        'The remaining 50 earlier sample cases and 278 broader-census cases are retained separately for applicability classification, rather than being presumed irrelevant or turned into an indiscriminate owner download request. The pending bulk OIR collection could satisfy many obligations together. A fresh exact-case mail search found the follow-up and original acknowledgment, with no dataset attachment in those results.','',
        '## Remaining full L10 work','',
        'The [six-part gap ledger](gap-ledger.json) names what the new evidence resolves and what remains. Actual filing contents, prior effective intervals, complete 2026 product/business-state/county coverage and precise rating conditions remain required. Further AI field reconciliation depends on those contents; some qualified interpretation and exact acceptance decisions remain separate. The 87-file queue is not a new complete-market denominator.','',
        '## Validation and preservation','',
        '[The independent native-source audit](validation.json) checks original response hashes and values, complete retained row/case accounting, all modeled attachment/form records, the exact download dispositions and every group amount using independent Poppler text reconstruction. [Safeguard and replay results](assurance.json) record the completed checks. Technical validation is not human domain acceptance.','',
        'All **201 protected files** from the parent references, code, source material and selectors are unchanged. The original r2 reference and r3 filing archive remain selected independently; this revision does not alter their denominators or acceptance. No UI, guest data, personal quote, ranking, recommendation or deployment change is included. No message, document request, challenge response, secret-content fetch or payment was submitted.','',
        'New code: `l10_gap_sources.py`, `l10_gap_build.py`, `l10_gap_public.py`, `l10_gap_validate.py`, `l10_gap_report.py` and `l10_gap_seal.py`. A sealed revision must be changed through a new revision with exact review.','']
    (WORK/'README.md').write_text('\n'.join(report))
    print(json.dumps({'download_cases':len(items),'first_batch':len(first_order),'gap_groups':len(ledger)},indent=2))


if __name__=='__main__':generate()
