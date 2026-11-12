"""Seal the L03 r3 research revision and export a compact reviewer packet."""
import collections,datetime,json,pathlib,shutil,sys,zipfile
from l03_close_sources import *
from l03_close_validate import run as validate,REPO,R2_PIN

DETAIL={
'BLUE-MEDICAL-SUPPLIES':('Medical supply subtype','CMS standalone 0% medical supplies cannot be assigned to prosthetic-related supplies, diabetes items or bundled hospital supplies.','Use carrier subtype-specific statements; retain the standalone value as uncorroborated. A same-service carrier clarification is needed to release a flat rate.'),
'HUMANA-WORLDWIDE':('Foreign service cost basis','PBP foreign urgent/transport copays (and one full-dual foreign emergency group) are not explicitly corroborated at the same geography/price basis by SB/EOC/reimbursement clauses.','Publish described worldwide coverage with upfront-payment/reimbursement caveat; retain exact foreign prices and waivers as unknown until a carrier clarification or applicable revision resolves them.'),
'PARTB-INSULIN-LOWER-BOUND':('Part B insulin minimum','Published $35 monthly ceiling and no-deductible rule do not establish a minimum of 0%. Generic rebatable-drug language does not independently settle insulin.','Use exact published ceiling/qualifications. Keep numeric minimum uncorroborated; personal drug prices are outside L03.'),
'DSNP-PUBLISHED-BASIS':('Nominal and assistance protected schedules','Two full-dual offerings have nominal CMS charges beside carrier Medicaid-protected no-charge schedules. The assistance rules do not independently prove each nominal charge on a same-basis carrier schedule.','Retain both source schedules. Proposed published reference uses the qualified carrier wording; raw nominal amounts stay uncorroborated and unavailable for personal output. Qualified review must accept that disposition or request carrier evidence.'),
'AETNA-OTHER1':('Plan defined Other 1','PBP names annual wellness exam and screening mammography as non-Medicare Other 1. EOC describes the named services but does not separately define the extra non-Medicare extension.','Publish EOC service/age/frequency qualifications only. Keep the broader additional-entitlement claim unknown.'),
'AETNA-OTHER2':('Plan defined Other 2','PBP names additional gFOBT/FIT not covered by Medicare. EOC retains stool-screening frequency and FIT lab statements without separately pricing the complete extra subset.','Publish exact EOC test/frequency/setting terms only. Retain broad extra-test claim as unknown.'),
}

def run(destination):
    checks=validate();s=json.loads((R3/'decision-summary.json').read_text());am=json.loads((R3/'amount-issue-decisions.json').read_text());gaps=[]
    for id,(name,why,disposition)in DETAIL.items():
        rs=[r for r in am if r['remaining_gap_id']==id]
        gaps.append({'id':id,'name':name,'groups':len(rs),'offering_ids':sorted({r['offering_id']for r in rs}),'issue_ids':[r['issue_id']for r in rs],'why_held':why,'proposed_disposition_for_review':disposition,'resolved':False,'accepted':False,'closure_type':'qualified source-basis review or new same-scope carrier evidence; not more table transcription'})
    gaps.extend([
      {'id':'PA-EXACT-FAMILY','name':'PA/referral exact family corroboration','comparisons':782,'why_held':'CMS family selections have global/SB policy support, without exact child-service corroboration. General may-required wording and retained code lists cannot establish every procedure requirement.','proposed_disposition_for_review':'Retain conditional policy/context; do not display a definite PA/referral requirement or absence from these flags alone.','resolved':False},
      {'id':'AETNA-DENTAL-PLACEHOLDER','name':'Aetna dental public explainer','why_held':'The public 2026 HMO D-SNP dental explainer still returns a one-page Please check back soon PDF. It was rechecked at the exact observed public link.','proposed_disposition_for_review':'Use retained exact EOC dental schedules and their exclusions. Keep separate supplemental document missing; do not count placeholder as acquired coverage.','resolved':False},
      {'id':'PA-HISTORY','name':'Historical prior authorization revisions','why_held':'Humana Florida January/July links resolve to the same July-effective September-revised file. General MA January/July snapshots were themselves revised June/October. Full-year historical revision series is unavailable from these routes.','proposed_disposition_for_review':'Treat retained lists as their stated dated revisions; no all-year historical criteria claim.','resolved':False},
      {'id':'MEMBER-NOTICES','name':'Private or future benefit notices','why_held':'Public routes and 307 reference contexts do not establish all private/member-specific or later notices.','proposed_disposition_for_review':'Reference is a dated public-source snapshot; require exact applicable notice before changing a benefit. LIS inserts are personal Part D assistance dependencies, outside this L03 scope.','resolved':False},
      {'id':'OPAQUE-PARTD-FLAGS','name':'Legacy Part D N flags','why_held':'Preserved r1 evidence has 332 repeated opaque N observations across 31 offerings in two flags whose dictionary defines 0/1.','proposed_disposition_for_review':'Leave flags uninterpreted and unused; use corroborated plan-level drug structure, without drug-specific coverage/pricing inference.','resolved':False},
      {'id':'RESTRICTED-25','name':'19 UHC and six Wellcare offerings','why_held':'Inherited UHC HTTP 403 stops and Wellcare systematic/commercial source-use restriction remain. Prior normal public-route reassessment is retained in r2; no bypass or new restricted-host requests.','proposed_disposition_for_review':'Keep all 25 visible and restricted until permitted exact documents are supplied or an authorized source route is established.','resolved':False},
      {'id':'CORROBORATION-BOUNDARY','name':'Value occurrences are not approved benefit claims','why_held':'The retained 7,705 typed value occurrences from r2 are evidence locations, with source-control and carrier context attached in r3. They are not 7,705 independent same-setting/network verified claims. Shared controls and source fields are not a semantic completeness denominator.','proposed_disposition_for_review':'Accept only explicitly supported named comparisons and retained source-native reference context. Keep unmodeled flat claims unavailable. A future consumer field release must define its exact fields and corroboration requirements.','resolved':False},
      {'id':'L03-ACCEPTANCE','name':'L03 human acceptance','why_held':'No L03 acceptance has been given. L01 acceptance is separate.','proposed_disposition_for_review':'Chris reviews the bounded comparison dispositions and explicit exclusions. No whole-market or fully verified benefit acceptance is requested.','resolved':False}
    ])
    dump(R3/'gap-register.json',gaps)
    status=[]
    for o,m in MATRIX.items():status.append({'offering_id':o,'name':m['name'],'parent':m['parent'],'carrier_document_state':m['document_matches']['EOC']['status'],'amount_issue_ids':[r['issue_id']for r in am if r['offering_id']==o],'remaining_amount_gap_ids':sorted({r['remaining_gap_id']for r in am if r['offering_id']==o and r['remaining_gap_id']}),'accepted':False,'consumer_usable':False})
    dump(R3/'offering-status.json',status)
    dump(R3/'acceptance.json',{'package_id':'L03-PUBLISHED-COLLIER-2026-reconciliation-r3','decision':'pending','accepted':False,'reviewer_name':None,'accepted_claim_ids':[],'excluded_gap_ids':[g['id']for g in gaps],'L01_acceptance_inherited':False,'requested_review':'Bounded source-reference and explicit held-claim dispositions; not comprehensive benefit acceptance.'})
    dump(R3/'RELEASE.json',{'id':'L03-PUBLISHED-COLLIER-2026-reconciliation-r3','state':'public_source_review_pass_finished_with_explicit_holds','accepted':False,'consumer_release':False,'personal_applicability':False,'comprehensive':False,'demo_activated':False,'parent_revisions_immutable':True,'scope':'Only approved published 2026 L03 source reconciliation; exact unresolved claims remain held.'})
    dump(R3/'visual-source-checks.json',{'new_rendered_and_inspected':[{'offering_id':'2026:'+cp+':000','kind':'SB','pdf_page':p,'decision':'Exact target column visually checked: mail-order $0 copay, retail 20%, PA may apply.'}for cp,p in [('H5427:083',15),('H5427:091',17),('H5427:105',17),('H5594:035',20)]],'prior_r2_checks_retained':True,'not_every_page_visually_reviewed':True})
    resolved=len(am)-s['amount_remaining_source_gap_groups'];qualified=resolved-s['amount_same_unit_direct_bindings']
    summary=f'''L03 2026 Collier published Medicare Advantage benefit review

The public-source reconciliation pass is finished with explicit source holds. L03 is still partial and unaccepted. The package covers the approved published-reference scope; it is not a personal benefit calculator or a comprehensive verified plan release.

72 observed L02 identities remain in the input: 47 have matched Summary of Benefits and Evidence of Coverage documents. The 19 UHC and six Wellcare offerings stay flagged as restricted. L02 all-market acceptance is not inherited.

THE 252 AMOUNT ISSUES
All 252 groups / 407 original field references have exact source locators, an evidence-backed decision and a claim limit:
- {s['amount_same_unit_direct_bindings']} direct same-unit bindings: eight outpatient-hospital nuclear-medicine maximums, five $20 acupuncture subservice maximums linked by 2026 CMS category instructions, and two explicit HealthSpring percentage ranges.
- {qualified} qualified reconciliations: channel, allowance, assistance or default-versus-lower-bound distinctions are retained. These include 60 Part B drug cases; those do not independently verify a universal 0% drug minimum.
- {s['amount_remaining_source_gap_groups']} held claim groups in six source-gap families. They are investigated holds, not numeric agreements or verified benefits.

HELD AMOUNT CLAIMS
'''+''.join(f"- {g['groups']} {g['name']}: {g['why_held']}\n"for g in gaps[:6])+f'''
CONDITIONS AND RIDERS
The 38,844 condition references are linked to 24,112 unique source controls with explicit interpretation rules. Shared-parent references are deduplicated; No copay is not no total charge, vendor restrictions are not referrals, and day bands are not covered-day caps. All 47 documented offerings retain full global/EOC chart context. This is source interpretation, not 24,112 independently carrier-approved clinical predicates.

All 14,610 PA/referral comparisons have a disposition. Of these, 782 selected comparisons have only global/SB policy support; exact child-service requirements stay unverified. Dated Humana PA lists are retained with their revision and emergency/transition qualifications. Historical full-year PA criteria remain incomplete.

All 307 rider references were reviewed in context: 47 generic future-notice sentences, 211 member-specific LIS references, 49 privacy-amendment references. None identifies a specific missing medical benefit amendment. This is not proof that private or future notices do not exist. Public document routes were checked, seven Aetna handbooks and three wallet guides were added, and the official 2026 CMS service-category instructions were acquired. Aetna's D-SNP dental explainer remains a one-page PDF placeholder; the exact EOC dental schedule is retained.

VALIDATION AND PRESERVATION
15 integrity/accounting checks pass; 35 regression tests pass (14 new plus 21 retained). All 252 issue identities, 407 original issue references, 38,844 condition links, 307 rider contexts, 173,124 service-field references and retained source hashes are accounted for. Four new shared-column PDF pages were visually checked. All 649 protected L01/L02/UI files and the pinned r1/r2 data/code remain unchanged. These checks do not establish factual completeness or human acceptance.

WHAT YOUR REVIEW CAN ACCEPT
Review the named supported comparisons, qualified wording and proposed exclusions in the gap register. Keep the 153 held amount claims, 782 exact-family PA/referral comparisons, opaque flags and missing/revision boundaries explicit. The 7,705 retained r2 value occurrences are locations with context, not independently verified benefit claims. No comprehensive L03 acceptance is requested, and your prior L01 acceptance does not transfer.

Portable packet: structured decisions, source locators, interpretations, gap register and code/hash receipts. Original carrier PDFs and full carrier page extracts stay in the repository research evidence; they are not bundled in this export. The complete r3 data package is under docs/data/l03-ma-benefits-2026-10-25/reconciliation-r3/ in Daylight.

Review Page: https://chatgpt.com/space/page_5b21f787f354819195ad5ed1e6645ea7
'''
    (R3/'README.md').write_text('# L03 r3 published source review with explicit holds\n\n'+summary.split('\n',2)[2])
    # Seal only after data, test receipts and documentation have been saved.
    code=['cms-slice/scripts/'+n for n in ['l03_close_sources.py','l03_close.py','l03_close_context.py','l03_close_validate.py','l03_close_reference.py','l03_close_finalize.py']]+['cms-slice/tests/test_l03_close.py']
    mf={'package_id':'L03-PUBLISHED-COLLIER-2026-reconciliation-r3','r1_manifest_sha256':sha((R1/'package-manifest.json').read_bytes()),'r2_manifest_sha256':R2_PIN,'files':{str(p.relative_to(R3)):sha(p.read_bytes())for p in sorted(R3.rglob('*'))if p.is_file() and p.name!='package-manifest.json'},'code_files':{p:sha((REPO/p).read_bytes())for p in code},'accepted':False}
    dump(R3/'package-manifest.json',mf);pin=sha((R3/'package-manifest.json').read_bytes())
    out=pathlib.Path(destination);out.mkdir(parents=True,exist_ok=True);(out/'L03-r3-review-summary.txt').write_text(summary)
    export=[n for n in mf['files']if '/'not in n and n not in ['evidence-pages.json','README.md']]
    # Portable locators identify exact source pages without copying carrier pages.
    ev=json.loads((R3/'evidence-pages.json').read_text());loc={k:{a:b for a,b in v.items()if a!='text'}for k,v in ev.items()}
    with zipfile.ZipFile(out/'l03-r3-review-data.zip','w',zipfile.ZIP_DEFLATED)as z:
        for n in export:z.write(R3/n,'reconciliation-r3/'+n)
        z.writestr('reconciliation-r3/evidence-page-locators.json',json.dumps(loc,ensure_ascii=False,indent=2))
        z.write(R3/'package-manifest.json','reconciliation-r3/package-manifest.json')
        z.writestr('README.txt',summary)
        for p in code:z.write(REPO/p,'code/'+p)
    archive=out/'l03-r3-review-data.zip'
    with zipfile.ZipFile(archive)as z:
        if z.testzip()is not None:raise AssertionError('Archive CRC failed')
        entries=len(z.namelist())
    dump(out/'delivery.json',{'package_id':mf['package_id'],'repository_manifest_sha256':pin,'archive_sha256':sha(archive.read_bytes()),'archive_entries':entries,'archive_bytes':archive.stat().st_size,'carrier_originals_and_full_pages_excluded':True,'repository_complete_package_files':len(mf['files']),'code_files':len(code),'accepted':False,'consumer_release':False})
    print(json.dumps({'manifest_sha256':pin,'resolved_or_qualified':resolved,'direct_bindings':s['amount_same_unit_direct_bindings'],'qualified':qualified,'held':s['amount_remaining_source_gap_groups'],'archive_entries':entries,'archive_bytes':archive.stat().st_size},indent=2))
if __name__=='__main__':run(sys.argv[1])
