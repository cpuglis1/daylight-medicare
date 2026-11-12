"""Package the validated CMS supplement and advance the research reference without cloning MA data."""
import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone

from l08_r6_common import BASE, HOME, PARENT, ROOT, assert_open, filehash, write


def prepare():
    assert_open()
    v=json.loads((BASE/'validation.json').read_text())
    if not v['passed']:
        raise ValueError('Source validation failed')
    n=json.loads((BASE/'normalization.json').read_text())
    cases=json.loads((BASE/'case-summary.json').read_text())
    api={k:json.loads((BASE/(k+'-api-accounting.json')).read_text()) for k in ['enrollment','optout']}
    parent_gaps=json.loads((PARENT/'genuine-gaps.json').read_text())
    for g in parent_gaps:
        if g['id']=='L08-G06':
            g.update(status='core_Original_Medicare_reference_collected_normalized_and_source_checked; specific_unknowns_retained',
                gap='The clinician and facility-affiliation archive, all five Q4 enrollment tables and the full nominal September opt-out release are now retained and normalized. The federal Hospital General Information CSV remains unavailable, and dated source differences remain explicitly unresolved for particular identities.',
                blocked_by='Hospital Provider Data Catalog route returned 403; that route family remains stopped. Working CMS Data API/catalog routes are owner-authorized and now implemented.',
                need='Applicable 2026 Hospital General Information CSV and dictionary. Exact newer dated enrollment/source clarification is needed only for positive claims about the enumerated unmatched or assignment/opt-out overlap cases.',
                r6_progress='189,932 Florida enrollment API records and 59,071 national opt-out API records match their publisher CSVs field for field. All five enrollment files and the clinician/affiliation inputs are normalized; 1,503,632 selected source observations are retained separately from the MA database.')
    parent_gaps.extend([
        {'id':'L08-OM01','kind':'federal_hospital_reference','status':'source_missing',
         'gap':'Applicable 2026 CMS Hospital General Information CSV/dictionary not acquired.',
         'need':'Owner-supplied published CSV/dictionary or an independently permitted official source. Do not bypass the denied Provider Data Catalog API family.',
         'official_download_page':'https://data.cms.gov/provider-data/dataset/xubh-q36u',
         'why':'AHCA licenses/campuses and clinician affiliation CCNs do not independently supply the complete federal hospital reference or a reliable canonical CCN/campus join.'},
        {'id':'L08-OM02','kind':'published_snapshot_identity_difference','status':'explicit_unknowns; no_negative_enrollment_inference',
         'gap':str(cases['unmatched_clinician_enrollment_ids'])+' clinician enrollment IDs ('+str(cases['unmatched_clinician_listing_rows'])+' listing rows) are absent from the complete dated enrollment extract.',
         'evidence':'unmatched-clinician-enrollments.json',
         'need':'A later applicable dated enrollment source or CMS clarification for any consequential exact-case positive enrollment claim. This does not mean that the clinician is ineligible or that source collection is incomplete.'},
        {'id':'L08-OM03','kind':'assignment_optout_source_overlap','status':'held_for_personal_participation_claims',
         'gap':str(cases['assignment_optout_overlapping_NPIs'])+' clinician NPIs appear in the assignment archive and a published opt-out interval spanning October 28.',
         'evidence':'assignment-optout-overlaps.json',
         'need':'Retain both dated observations; exact-case source clarification/current official confirmation before a positive participation claim. No universal phone-call requirement for ordinary nonconflicting published listings.'}])
    write(BASE/'genuine-gaps.json',parent_gaps)
    write(BASE/'authorization.json',{'owner_request':'great implement!', 'date':'2026-10-28',
        'scope':'Public CMS API scripting and dated Original Medicare reference integration; no consumer release, paid service, account, outreach or source-denial bypass.',
        'data_CMS_API_and_catalog_ordinary_reads_authorized':True,
        'Provider_Data_Catalog_denied_route_family_remains_stopped':True,
        'earlier_MA_layer_acceptance_and_all_source_stops_other_than_authorized_working_CMS_API_routes_unchanged':True})
    old=json.loads((HOME/'cms-api-check-2026-10-28/hospital-owner-metadata.receipt.json').read_text())
    write(BASE/'hospital-access-evidence.json',{'prior_ordinary_probe':old,
        'implementation_retried_denied_route':False,'SQL_or_alternate_PDC_query_route_used':False})
    limits={
        'clinician_modified_date':'2026-10-02','archive_release_date':'2026-10-15',
        'enrollment_nominal_release':'2026-10-01','enrollment_source_extract_filename_date':'2026-09-29',
        'enrollment_catalog_modified':'2026-10-19','optout_nominal_release':'2026-09-01',
        'optout_catalog_modified':'2026-10-26','retrieval_date':'2026-10-28',
        'optout_record_Last_Updated_can_exceed_nominal_September_period':True,
        'nominal_period_not_forced_to_equal_row_update_or_relationship_date':True,
        'clinician_source_12_month_claims_lookback_not_all_clinician_census':True,
        'assignment_Y':'CMS publishes accepts assignment', 'assignment_M':'CMS publishes may accept assignment; not a yes/no guarantee',
        'blank_or_unrecognized_assignment':'unknown; retain original value',
        'PPEF_locations':'City/state/ZIP only; no exact street or personal participation inferred',
        'PPEF_33_enrollment':'Ordering/referring only, separate from billing enrollment',
        'reassignment':'Billing relationship; not a provider-site or MA network contract',
        'affiliation':'Published clinician/facility relationship; not MA network membership or exact campus contract',
        'optout_endpoint_boundaries':'Review, rather than an invented inclusive/exclusive end rule',
        'absent_record':'Unknown in the applicable source/selection; not an exclusion',
        'geography':'Florida clinician superset plus related enrollment context; city search is not county proof. No NPI is deduplicated across distinct source locations.',
        'utilization_file':'Retained in original archive only; no quality/ranking/use interpretation added',
        'personal_coverage_or_appointment_claims_enabled':False}
    write(BASE/'modeled-field-limits.json',limits)
    command=[sys.executable,'-m','unittest','discover','-s','cms-slice/tests','-p','test_l08_r[56]_reference.py','-v']
    t=subprocess.run(command,cwd=ROOT,capture_output=True,text=True)
    (BASE/'test-report.txt').write_text(t.stdout+t.stderr)
    write(BASE/'test-results.json',{'passed':t.returncode==0,'exit_code':t.returncode,'command':command,'report':'test-report.txt'})
    if t.returncode:
        raise ValueError('Regression checks failed')
    total=sum(i['selected_rows'] for i in n.values())
    write(BASE/'summary.json',{'reference_id':'L08-PUBLISHED-COLLIER-2026-research-r6',
        'selected_source_observations':total,'source_counts':{k:{'national_rows':i['national_source_rows'],'selected_rows':i['selected_rows']}for k,i in n.items()},
        'Florida_enrollment_API_rows':api['enrollment']['rows'],'national_optout_API_rows':api['optout']['rows'],
        'Florida_clinician_listing_rows':cases['Florida_clinician_listing_rows'],
        'Florida_distinct_clinician_NPIs':cases['Florida_distinct_clinician_NPIs'],
        'unmatched_clinician_enrollment_ids':cases['unmatched_clinician_enrollment_ids'],
        'assignment_optout_overlapping_NPIs':cases['assignment_optout_overlapping_NPIs'],
        'all_five_enrollment_tables_acquired':True,'Hospital_General_Information_acquired':False,
        'validation_passed':True,'tests_passed':True,'consumer_release_enabled':False,
        'full_L08_complete':False,'human_accepted':False,'database_architecture':'pinned MA parent plus separate normalized Original Medicare supplement'})
    table='\n'.join('| '+k.replace('_',' ')+' | '+format(i['national_source_rows'],',')+' | '+format(i['selected_rows'],',')+' |'for k,i in n.items())
    report=f'''# L08 Original Medicare reference and CMS API integration

October 28, 2026. The core published Original Medicare reference is now collected, normalized and source-checked. It includes the owner-supplied clinician and facility-affiliation archive, all five CMS enrollment tables and the complete national opt-out release. **The federal Hospital General Information file remains missing, and specific source disagreements stay unknown. Full L08 remains partial.**

## Sources and exact dates

The owner supplied the October 15 clinician archive. Its manifest dates the national clinician and facility-affiliation files **October 2, 2026**. All five received files, including the unmodeled utilization file and dictionary, are retained losslessly as gzip originals with original-byte hashes. The national clinician file has **3,630,233 listing rows**; its **270,559 Florida rows represent 114,699 distinct NPIs**, with multiple locations/enrollments retained. They are not 270,559 unique doctors. [Owner receipt](owner-intake.json), [CMS clinician definitions](dictionaries/clinicians.txt).

The enrollment release is nominally **October 1**, catalog-modified **October 19**, with source filenames dated **September 29**. CMS lists **3,030,022 national enrollment records**. All five relational tables are retained: enrollment, additional NPIs, practice locations, reassignment and secondary specialty. All **189,932 records whose enrollment state is Florida** were collected through the version-specific API across 38 populated pages plus an empty terminal page and compared field for field to the national CSV. The broader normalized selection also retains cross-state enrollment/context links; it is not restricted to that API filter. [Release metadata and dictionaries](releases.json), [download receipts](sources.json), [API accounting](enrollment-api-accounting.json).

The opt-out release is nominally **September**, catalog-modified **October 26**, and contains record-level updates into October. Its nominal period is not substituted for a relationship start/end or row update date. All **59,071 national records** were collected over 12 populated pages plus an empty terminal page and match the published CSV across every field. National retention avoids silently missing an opt-out record because its mailing address is outside Florida. [API accounting](optout-api-accounting.json), [CMS opt-out methodology](dictionaries/optout_methodology_pdf.txt).

## Normalized data and geography

| Source | National source rows accounted | Selected database observations |
|---|---:|---:|
{table}

The database contains **{total:,} source observations**, not unique people. Every modeled source field remains literal with source identity and CSV row locator. Providers, enrollment applications, locations, group billing relationships and facility affiliations remain separate facts. NPI, enrollment/PAC identifiers and ZIPs remain strings. Non-UTF-8 enrollment CSVs use explicitly recorded strict Windows-1252 decoding; no replacement characters or silent cleanup are used.

The selection includes all Florida clinician listings, Florida enrollment and practice-location records, additional-NPI/clinical-ID links and exactly one hop of published billing reassignments. National source originals remain retained for repeatable geographic expansion. All **336,844 selected reassignment edges have both enrollment endpoints retained**. City searches support Naples, Marco Island, Immokalee and nearby care without claiming city or ZIP proves county membership. [Exact selection](selection.json), [all-source counts and schemas](normalization.json).

The [Original Medicare SQLite database](original-medicare.sqlite3) is a separate component alongside the exact, unchanged [MA parent database](../wellcare-r5/providers.sqlite3). The active research pointer explicitly names both. It does not present the MA database alone as the new Original Medicare reference.

## What the fields establish

- CMS assignment **Y** means the source publishes acceptance of assignment; **M** means it may be accepted. Individual and group flags remain separate, and an absent/unrecognized code stays unknown.
- An enrollment of type **33** is ordering/referring only; it is not promoted to billing enrollment. The other recognized billing types remain qualified to the dated extract.
- Published enrollment practice locations supply **city/state/ZIP, not street addresses**. The clinician archive's detailed street/site rows remain separate.
- Reassignment is a billing relationship; facility affiliation is a clinician/facility relationship. Neither establishes participation in an MA plan or in every location of a health system.
- An opt-out interval and its record update date remain visible. Endpoint boundary cases require interpretation; a missing opt-out result is not proof of positive participation.

These limits are enforced by the source-qualified lookup and tested independently. No personal coverage, live appointment availability or recommendation is enabled. [Modeled limits](modeled-field-limits.json).

## Genuine remaining gaps

**One federal source is still missing:** the applicable 2026 [Hospital General Information CSV and dictionary](https://data.cms.gov/provider-data/dataset/xubh-q36u). Its metadata API returned 403 before this implementation; the Provider Data Catalog API family remains stopped, including SQL/alternate query routes. The working CMS Data API and catalog do not imply that every CMS route is accessible. AHCA licenses and affiliation CCNs cannot silently replace the missing federal hospital reference. An owner-supplied original CSV/dictionary would fill this acquisition gap. [Access evidence](hospital-access-evidence.json).

**Specific published sources do not completely agree.** There are **{cases['unmatched_clinician_enrollment_ids']:,} clinician enrollment IDs across {cases['unmatched_clinician_listing_rows']:,} listing rows** absent from the complete dated enrollment extract, and **{cases['assignment_optout_overlapping_NPIs']} NPIs** appear in both the clinician assignment archive and an opt-out interval spanning October 28. Different snapshot dates/populations and the clinician file's claims lookback are retained; they are not an explanation proven for every discrepancy. Both sides remain visible and positive current participation claims stay unresolved for those identities. These are source differences, not missing API pages or evidence that those doctors are ineligible. [Exact unmatched IDs](unmatched-clinician-enrollments.json), [assignment/opt-out cases](assignment-optout-overlaps.json).

The agreed MVP can retain qualified published listings, unknowns and targeted verification tasks. It does not require a complete historical relationship timeline or live appointment confirmation. Earlier MA network-mapping, internal interpretation and Wellcare source limitations remain unchanged in the [updated gap register](genuine-gaps.json).

## Validation and use

Independent validation accounted for **{v['counts']['national_source_rows_accounted']:,} national source rows** and compared **{v['counts']['literal_source_fields_compared']:,} selected literal fields**, every normalized assignment/enrollment/opt-out/reassignment value, all API page populations, source-byte hashes and every sealed parent file. There were **zero unexplained modeled-field mismatches**. Publisher API/CSV totals and populations agree for the exact collected scopes. This verifies the extraction; it does not erase the genuine source differences above. [Validation](validation.json), [regression results](test-results.json).

Use `python3 cms-slice/scripts/l08_r6_reference.py --npi 1003017427` for a source-qualified lookup. The collector and builder are frozen with this research revision. Reproduction uses retained source receipts; refreshing or changing data requires a new revision and exact-scope review. The collection sequence is recorded in [verification commands](verification-commands.json).

D64/D73: no commercial inputs, ranking, customer profile, consumer UI, outreach, deployment or inherited acceptance was added. The r5 MA database and sealed files remain unchanged. New evidence remains unaccepted; the active pointer is an incomplete research reference.
'''
    (BASE/'REPORT.md').write_text(report)
    (BASE/'README.md').write_text('# L08 Original Medicare reference\n\n[Results and remaining gaps](REPORT.md), [source validation](validation.json), [database](original-medicare.sqlite3), [gap register](genuine-gaps.json). The unchanged MA parent remains a separate pinned component. Full L08 is partial and consumer release is disabled.\n')
    write(BASE/'verification-commands.json',{'commands':[
        'python3 cms-slice/scripts/l08_r6_discover.py',
        'python3 cms-slice/scripts/l08_r6_collect.py',
        'python3 cms-slice/scripts/l08_r6_build.py',
        'python3 cms-slice/scripts/l08_r6_cases.py',
        'python3 cms-slice/scripts/l08_r6_validate.py',
        'python3 cms-slice/scripts/l08_r6_finish.py',
        'python3 cms-slice/scripts/l08_r6_finish.py --publish'],
        'dictionary_text_extraction':'pdftotext -layout for the retained CMS dictionaries/methodology; no PDF edits',
        'consumer_release_enabled':False})
    print(json.dumps({'prepared':True,'source_validation_passed':True,'regression_checks_passed':True}),flush=True)


def publish():
    assert_open()
    current=json.loads((HOME/'CURRENT_REFERENCE.json').read_text())
    pin=json.loads((BASE/'parent-pin.json').read_text())
    if current!=pin['reference'] or filehash(PARENT/'providers.sqlite3')!=pin['database_sha256']:
        raise ValueError('Pinned active parent changed')
    for name in ['validation.json','test-results.json','case-validation.json']:
        if not json.loads((BASE/name).read_text())['passed']:
            raise ValueError('Failed prerequisite '+name)
    for name in ['REPORT.md','genuine-gaps.json','summary.json','assignment-optout-overlaps.json']:
        if not (BASE/name).exists():
            raise ValueError('Missing deliverable '+name)
    (BASE/'SEALED').write_text('L08 research r6; source-qualified Original Medicare supplement; full layer incomplete; no inferred acceptance\n')
    paths=[p for p in BASE.rglob('*') if p.is_file() and p.name not in {'manifest.json','manifest-validation.json'}]
    paths+=list((ROOT/'cms-slice/scripts').glob('l08_r6_*.py'))+[ROOT/'cms-slice/tests/test_l08_r6_reference.py']
    files={str(p.relative_to(ROOT)):{'sha256':filehash(p),'bytes':p.stat().st_size}for p in sorted(set(paths))}
    manifest={'reference_id':'L08-PUBLISHED-COLLIER-2026-research-r6',
        'created_at_utc':datetime.now(timezone.utc).isoformat(),'files':files,
        'parent_manifest_sha256':pin['manifest_sha256'],'parent_database_sha256':pin['database_sha256'],
        'database_components':['wellcare-r5/providers.sqlite3','original-medicare-r6/original-medicare.sqlite3'],
        'full_L08_complete':False,'human_accepted':False,'consumer_release_enabled':False}
    write(BASE/'manifest.json',manifest)
    errors=[rel for rel,m in files.items()if filehash(ROOT/rel)!=m['sha256'] or (ROOT/rel).stat().st_size!=m['bytes']]
    if errors:
        raise ValueError('New manifest hash mismatch')
    pointer={'reference_id':manifest['reference_id'],'kind':'incomplete_research_reference',
        'manifest':'original-medicare-r6/manifest.json','manifest_sha256':filehash(BASE/'manifest.json'),
        'database':'wellcare-r5/providers.sqlite3','database_role':'unchanged_MA_directory_component',
        'original_medicare_database':'original-medicare-r6/original-medicare.sqlite3',
        'report':'original-medicare-r6/REPORT.md','parent_reference_id':current['reference_id'],
        'parent_manifest':'wellcare-r5/manifest.json','parent_manifest_sha256':pin['manifest_sha256'],
        'consumer_release_enabled':False,'human_accepted':False,'comprehensive_layer_complete':False}
    write(HOME/'CURRENT_REFERENCE.json',pointer)
    write(BASE/'manifest-validation.json',{'passed':True,'files_rehashed':len(files),'errors':[],
        'active_reference_manifest_hash_agrees':pointer['manifest_sha256']==filehash(BASE/'manifest.json'),
        'parent_database_hash_agrees':filehash(PARENT/'providers.sqlite3')==pin['database_sha256']})
    print(json.dumps(pointer),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--publish',action='store_true')
    a=p.parse_args()
    publish()if a.publish else prepare()
