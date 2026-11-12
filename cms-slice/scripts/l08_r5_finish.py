"""Publish the additive owner-directory research reference after exact checks."""
import argparse,json,subprocess,sys
from datetime import datetime,timezone
from l08_r5_common import ROOT,HOME,PARENT,BASE,write,filehash,assert_open

def prepare():
    assert_open();v=json.loads((BASE/'validation.json').read_text());n=json.loads((BASE/'normalization-summary.json').read_text())
    if not v['passed']:raise ValueError('Modeled-field validation failed')
    invs=json.loads((BASE/'document-inventory.json').read_text());bindings=json.loads((BASE/'plan-directory-bindings.json').read_text());h=json.loads((BASE/'hospital-coverage-summary.json').read_text())
    gaps=json.loads((PARENT/'genuine-gaps.json').read_text())
    for g in gaps:
        if g['id']=='L08-G01':
            g.update(status='applicable_document_acquisition_closed_for_all_six; published_visible_rows_ingested; full_network_not_claimed',
                gap='Four owner-supplied unique published 2026 medical directories now cover all six target plan names with explicit Collier geography. Every visible medical listing/address and printed publisher ID is accounted. The directory publications remain expressly regional/partial.',
                blocked_by=None,need='No further owner download is needed for these six applicable publications. Full network completeness remains subject to the source-total discrepancy and any providers/sites omitted from the published partial reference.',
                r5_progress='Six received files are four unique PDFs, 1,428 pages, dated September 23, 2026. 14,158 visible medical listing/site observations, including 3,532 under Collier headings, and 24 strict campus/plan references were added. All symbols, source conditions and qualified plan-name/CMS bridges are retained.')
    gaps.extend([
       {'id':'L08-WC01','kind':'publisher_total_reconciliation','status':'open; exact_source_discrepancy_preserved',
        'gap':'Four Specialty Providers section headers total eight more listings than are visibly accounted across the four unique publications.',
        'need':'A publisher explanation of the total definition, corrected dated publication or complete applicable official export would reconcile the source totals. Do not invent eight missing doctors or silently change either count.',
        'why':'All visible medical city/ZIP anchors and publisher-ID nodes are captured and every modeled-column text/image node is accounted; the supplied PDFs alone do not explain the count difference.',
        'evidence':'publisher-count-discrepancies.json'},
       {'id':'L08-WC02','kind':'specific_campus_identity_bridge','status':'held_from_current_census_merge; raw_directory_rows_retained',
        'gap':'The abbreviated Physicians Regional North/Creekside record and the separately listed Landmark long-term-care facility cannot be collapsed to one current licensed campus merely because of a similar street.',
        'need':'Exact dated carrier facility/network identity, an explicit campus/NPI crosswalk or equivalent authoritative clarification for the consequential canonical-campus join. The observed directory rows remain usable as qualified source listings.',
        'why':'The source prints separate names/IDs and different hospital categories. Other licensed-campus absences in these partial publications remain unknown, not exclusions.',
        'evidence':'hospital-source-reconciliation.json'}])
    write(BASE/'genuine-gaps.json',gaps)
    write(BASE/'modeled-field-limits.json',{'observed_medical_listings':14158,'observed_source_sites':14158,'Collier_heading_observations':3532,
        'not_unique_doctor_counts':True,'source_publisher_IDs_unprinted_in_some_rows':4127,
        'identifier_policy':'Stable document/native-anchor IDs are retained. Publisher Provider ID is not an NPI or unique person/site identifier. No NPI is fabricated.',
        'symbol_policy':'True means printed symbol; null means not indicated. Missing closed-panel symbol does not establish accepting new patients; no missing-icon negative is inferred.',
        'period_policy':'Benefit year 2026, printed current-as-of September 23, 2026, owner intake October 28, 2026. The source does not publish individual relationship start/end periods.',
        'plan_policy':'Exact cover plan name + explicit 2026/Collier geography uniquely matches the pinned L02 offering. CMS IDs are bridged and are not printed in these PDFs.',
        'supplemental_policy':'The source warns that routine/supplemental services may not be covered by every plan or in every county. The exact section conditions remain attached to the listings.',
        'all_visible_medical_address_anchors_accounted':True,'all_published_header_totals_reconciled':False,
        'historical_and_abbreviated_names_not_silently_corrected':True,'pharmacy_pages_retained_but_L07_unchanged':True,
        'complete_network_or_personal_participation_claimed':False})
    write(BASE/'source-QA.json',{'reviewed':[
       {'file':'render/wellcare-legend.png','scope':'PDF page 7; seven meanings and missing-icon neutrality'},
       {'file':'render/wellcare-Collier-PCP.png','scope':'PDF page 15; names/IDs, practices, source street, languages/hours and closed panels'},
       {'file':'render/wellcare-hospitals.png','scope':'PDF page 250; separate physical campuses, generic publisher IDs and co-located acute/long-term-care names'},
       {'file':'render/actual-mask-QA.png','scope':'Actual decoded hard masks; wheelchair and closed-panel images share black color pixels but have distinct mask shapes'}],
       'sampled_visual_inspection':True,'whole_population_native_field_comparison':'validation.json',
       'raw_Poppler_icon_pixels_alone_are_insufficient':True})
    write(BASE/'intake-receipt.json',{'received_owner_files':6,'unique_PDFs':4,'duplicate_files':2,'unique_pages':1428,
       'all_six_Wellcare_target_offerings_have_applicable_named_2026_Collier_publication':True,
       'additional_owner_download_requested':False,'owner_files_retained_byte_for_byte':True,
       'remote_server_bytes_independently_compared':False,'no_network_requests_or_source_stop_bypass':True,
       'data_acceptance_or_consumer_release_inferred':False})
    write(BASE/'summary.json',{'reference_id':'L08-PUBLISHED-COLLIER-2026-research-r5','date':'2026-10-28',
       'source_as_of':'2026-09-23','owner_files':6,'unique_PDFs':4,'unique_PDF_pages':1428,'normalization':n,
       'hospital_coverage':h,'validation_passed_for_modeled_fields_and_explicit_accounting':True,
       'publisher_total_discrepancies':4,'publisher_total_excess_over_visible_listings':8,
       'Wellcare_document_acquisition_gap_closed':True,'full_L08_complete':False,'human_accepted':False,'consumer_release_enabled':False})
    rows=[]
    for i in invs:
        bs=[b for b in bindings if b['document_sha256']==i['sha256']]
        plans=', '.join(b['offering_id'].split(':')[1]+'-'+b['offering_id'].split(':')[2]for b in bs)
        filename=i['owner_filenames'][0]
        rows.append('| ['+filename+'](intake/'+filename+') | '+str(i['pages'])+' | '+plans+' |')
    discrepancies=json.loads((BASE/'publisher-count-discrepancies.json').read_text())
    countrows=[]
    for d in discrepancies:
        i=next(i for i in invs if i['sha256']==d['document_sha256'])
        countrows.append('| '+i['owner_filenames'][0].split('_')[0]+' | '+str(d['published_totals'][0])+' | '+str(d['observed_visible_listings'])+' | '+str(d['difference'])+' |')
    report=f'''# L08 Wellcare owner-directory intake

October 28, 2026. **The missing applicable Wellcare directory-acquisition gap is closed for all six target offerings.** The six supplied files are four unique 2026 PDFs, covering 1,428 pages. Their stated directory date is **September 23, 2026**. Full L08 remains incomplete; these are explicitly partial/regional publications and unaccepted research evidence.

## Files received and applicability

| Retained original file | Pages | Pinned Collier offering(s) |
|---|---:|---|
{chr(10).join(rows)}

Both `-1` copies are byte-identical duplicates of another received file; all six owner files remain preserved. This does not represent six different publications. Every cover explicitly states 2026 and Collier, and the printed plan names uniquely match these six offerings in the pinned L02 Collier inventory. **The CMS IDs are not printed in the PDFs**; the exact name/year/geography bridge is visible in [plan-directory-bindings.json](plan-directory-bindings.json). No acceptance is inherited from another layer.

[Intake receipt](intake-receipt.json), [owner-file hashes](owner-file-observations.json), [four-document inventory](document-inventory.json), [all 72 offerings](plan-source-coverage.json).

## Data now retained and modeled

- **14,158 visible medical listing/site observations**, including **3,532 observations under Collier headings**. These include repetitions across editions, specialties and locations, plus supplemental provider categories. They are not counts of unique doctors.
- Every observed medical address and all **10,031 printed publisher-ID occurrences** are accounted. Source rows that do not print an ID retain a stable document/native-anchor identifier; no NPI is invented.
- Names, printed carrier IDs, gender text, practice names, exact streets/cities/ZIPs, phones, websites, languages, hours, PCMH/tier text, source specialties and full remaining entry text are preserved with native locations. Continuations across columns and pages are joined without replacing source spelling or expanding unusual street strings.
- All **33,504 medical icon occurrences** are linked to their exact source graphic/mask and legend. These preserve wheelchair access, public transportation, Medicaid acceptance, board certification, cultural competency training, phone/video consultation and **653 closed-panel symbols**. A missing symbol remains not indicated; it does not create a negative fact or establish an open panel.
- Vision/additional-benefit section conditions remain attached, including the warning that routine/supplemental services may not be covered by every plan or in every county. A directory listing is not a benefit-eligibility conclusion.

All original pages, native text, image objects and index/pharmacy material remain retained. Pharmacy pages are outside this medical normalization and do not modify L07. [Research database](providers.sqlite3), [listing records](wellcare-records.jsonl.gz), [modeled limits](modeled-field-limits.json).

## Hospital references

The new source supports **24 additional dated campus/plan references**: four strictly matched Collier campuses across all six Wellcare offerings—NCH Baker/Naples Community, NCH North Naples, Physicians Regional Pine Ridge and Physicians Regional Collier. A hospital section and exact physical street/city/ZIP are required; clinician affiliations and outpatient addresses cannot substitute.

The directory also preserves an abbreviated Physicians Regional North/Creekside entry and a separately named Landmark long-term-care hospital. They have different source roles and names; this revision does not merge them to one current licensed campus or silently supply a missing direction/street expansion. The source rows remain visible for targeted identity reconciliation.

The overall 17-campus × 72-offering matrix now has **{h['positive_published_cells']} positive published cells of 1,224**, including **{h['Collier_positive_published_cells']} of 504 Collier cells**. Unknown cells remain unknown, never out of network. These are qualified dated directory references, not personal participation guarantees. [New evidence](new-hospital-evidence.json), [all hospital source observations](hospital-source-reconciliation.json), [matrix summary](hospital-coverage-summary.json).

## Genuine remaining Wellcare limits

**The printed specialty totals do not fully reconcile.** All 32 section counts were checked. Twenty-eight agree; four Specialty Providers totals exceed the visible listing populations:

| Publication prefix | Printed specialty total | Visible listing blocks | Difference |
|---|---:|---:|---:|
{chr(10).join(countrows)}

The difference totals **eight across four publications**, with repeated underlying material; it does not establish eight unique missing doctors. Every visible medical city/ZIP anchor, publisher-ID node and modeled-column text/image object has an explicit disposition. No synthetic records were added to match a printed total. A publisher explanation of the count definition, corrected publication or applicable complete export would resolve this remaining source-accounting conflict. [Exact discrepancies](publisher-count-discrepancies.json).

Each publication also expressly says more network providers are available beyond its listed material. These files therefore support their actual dated published observations, not exhaustive all-network absence conclusions. Individual historical participation periods and live appointment acceptance are not established by the directory date.

**No further owner download is requested for these six applicable publications.** The former public-route access failure no longer blocks this intake; all work used the supplied originals, with no stopped-host retry, login or warning bypass.

The broader L08 gaps remain: unresolved UHC/Florida Blue and selected Humana exact-network mapping, all-specialty/all-site completeness beyond partial publications and bounded queries, applicable federal Original Medicare snapshots, and explicit internal/source identity limits. [Updated genuine-gap register](genuine-gaps.json).

## Validation and preservation

Whole-population modeled-field and source-accounting validation passed with **zero unexplained field-value mismatches**. It checked all **1,428 pages**, **153,492 native XML text nodes**, **36,291 source image occurrences**, every modeled record field, every visible medical address/identifier anchor, the six name/year/geography bindings, all 32 source section counts and the 24 campus references. Independent PDF graphics coordinates and hard masks were reconciled to the XML image positions; raw black image pixels alone would have confused wheelchair and closed-panel symbols.

The four publisher-total conflicts above remain explicitly open. Passing literal-field validation does not make those totals reconciled or establish a comprehensive network. [Validation](validation.json), [image checks](image-extraction-validation.json), [source QA](source-QA.json), [regression checks](test-results.json).

All **{v['counts']['parent_files_rehashed']:,} sealed parent files** were rehashed and **{v['counts']['unchanged_parent_rows_compared']:,} parent database rows** compared. Earlier rows remain unchanged; each hospital update preserves the exact parent evidence prefix. This additive D64/D73 research revision changes no consumer UI, recommendations, rankings, other-layer acceptance or deployment. All earlier evidence/code stays sealed; source assignment does not constitute acceptance.
'''
    (BASE/'REPORT.md').write_text(report)
    (BASE/'README.md').write_text('# L08 Wellcare intake r5\n\n[Results, source coverage and remaining gaps](REPORT.md), [intake receipt](intake-receipt.json), [validation](validation.json), [database](providers.sqlite3). Applicable directory acquisition is closed for all six Wellcare targets. Full L08 is incomplete and no consumer release or source acceptance is inferred.\n')
    command=[sys.executable,'-m','unittest','discover','-s','cms-slice/tests','-p','test_l08_r5_reference.py','-v'];t=subprocess.run(command,cwd=ROOT,text=True,capture_output=True)
    (BASE/'test-report.txt').write_text(t.stdout+t.stderr);write(BASE/'test-results.json',{'passed':t.returncode==0,'exit_code':t.returncode,'command':command,'report':'test-report.txt'})
    if t.returncode:raise ValueError('Regression checks failed')
    write(BASE/'verification-commands.json',{'steps':['l08_r5_intake.py','l08_r5_icons.py (bundled Python)','l08_r5_normalize.py','l08_r5_build.py','l08_r5_validate.py (bundled Python)','l08_r5_finish.py (bundled Python)','l08_r5_finish.py --publish'],
       'network_requests':0,'source_modifications':0,'consumer_release_enabled':False})
    print(json.dumps({'prepared':True,'modeled_field_validation_passed':True,'regression_checks_passed':True,'publisher_totals_reconciled':False}),flush=True)

def publish():
    assert_open()
    prior=json.loads((HOME/'CURRENT_REFERENCE.json').read_text())
    if prior.get('reference_id')!='L08-PUBLISHED-COLLIER-2026-research-r4'or prior.get('manifest_sha256')!=filehash(PARENT/'manifest.json'):
        raise ValueError('Active parent reference changed; reconcile before publishing')
    for p in ['validation.json','test-results.json','image-extraction-validation.json']:
        if not json.loads((BASE/p).read_text())['passed']:raise ValueError('Failed prerequisite '+p)
    for p in ['REPORT.md','genuine-gaps.json','intake-receipt.json','publisher-count-discrepancies.json']:
        if not(BASE/p).exists():raise ValueError('Missing deliverable '+p)
    (BASE/'SEALED').write_text('L08 owner-directory research r5 sealed; full L08 incomplete; no inferred acceptance\n')
    paths=[p for p in BASE.rglob('*')if p.is_file()and p.name not in ['manifest.json','manifest-validation.json']]
    paths+=list((ROOT/'cms-slice/scripts').glob('l08_r5_*.py'))+[ROOT/'cms-slice/tests/test_l08_r5_reference.py']
    files={str(p.relative_to(ROOT)):{'sha256':filehash(p),'bytes':p.stat().st_size}for p in sorted(set(paths))}
    manifest={'reference_id':'L08-PUBLISHED-COLLIER-2026-research-r5','created_at_utc':datetime.now(timezone.utc).isoformat(),'files':files,
       'parent_manifest_sha256':filehash(PARENT/'manifest.json'),'full_L08_complete':False,'human_accepted':False,'consumer_release_enabled':False,
       'published_header_totals_reconciled':False,'modeled_field_and_explicit_accounting_validation_passed':True}
    write(BASE/'manifest.json',manifest)
    errors=[rel for rel,m in files.items()if(ROOT/rel).stat().st_size!=m['bytes']or filehash(ROOT/rel)!=m['sha256']]
    if errors:raise ValueError('Manifest mismatch '+str(errors[:10]))
    current={'reference_id':manifest['reference_id'],'kind':'incomplete_research_reference','manifest':'wellcare-r5/manifest.json','manifest_sha256':filehash(BASE/'manifest.json'),
       'database':'wellcare-r5/providers.sqlite3','report':'wellcare-r5/REPORT.md','parent_reference_id':'L08-PUBLISHED-COLLIER-2026-research-r4',
       'consumer_release_enabled':False,'human_accepted':False,'comprehensive_layer_complete':False}
    write(HOME/'CURRENT_REFERENCE.json',current);write(BASE/'manifest-validation.json',{'passed':True,'files_rehashed':len(files),'errors':[],
       'active_reference_manifest_sha256_agrees':filehash(BASE/'manifest.json')==current['manifest_sha256']})
    print(json.dumps({'sealed':True,'files':len(files),'active_reference':current['reference_id']}),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--publish',action='store_true');a=p.parse_args()
    if a.publish:publish()
    else:prepare()
