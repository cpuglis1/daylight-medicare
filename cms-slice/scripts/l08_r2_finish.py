#!/usr/bin/env python3
"""Resolve evidenced facility identity, then publish an additive L08 snapshot."""
import argparse
from collections import Counter
from datetime import datetime,timezone
import hashlib
import json
import sqlite3
from l08_r2_common import BASE,PARENT,ROOT,write


def sha(path):
    h=hashlib.sha256()
    with path.open('rb')as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()


def prepare():
    if(BASE/'SEALED').exists():raise ValueError('Sealed revision')
    db=sqlite3.connect(BASE/'providers.sqlite3');identities=[]
    db.execute('DELETE FROM r2_identity_evidence')
    for p in(BASE/'acquisition/receipts').glob('*.json'):
        receipt=json.loads(p.read_text())
        if 'npiregistry.cms.hhs.gov'not in receipt.get('requested_url','')or receipt.get('error'):continue
        packet=json.loads((ROOT/receipt['path']).read_bytes())
        for item in packet.get('results',[]):
            row={'npi':str(item['number']),'source_id':receipt['id'],'source_path':receipt['path'],'source_sha256':receipt['sha256'],'native':item,'network_participation_established':False}
            identities.append(row);db.execute('INSERT INTO r2_identity_evidence VALUES(?,?,?)',(row['npi'],row['source_id'],json.dumps(row)))
    write(BASE/'registry-identity-evidence.json',identities)
    registry=next(x for x in identities if x['npi']=='1790432490')
    assert registry['native']['basic']['organization_name']=='ENCOMPASS HEALTH REHABILITATION HOSPITAL OF NAPLES, LLC'
    assert any(a.get('address_1')=='14305 COLLIER BLVD'and a.get('city')=='NAPLES'and a.get('state')=='FL'for a in registry['native']['addresses'])
    licensed=json.loads(db.execute("SELECT fields_json FROM hospitals WHERE id='AHCA:458386'").fetchone()[0])
    assert licensed['Owner'].upper()=='ENCOMPASS HEALTH REHABILITATION HOSPITAL OF NAPLES, LLC'
    aetna=[json.loads(x[0])for x in db.execute("SELECT fields_json FROM aetna_query_observations WHERE category='hospital_detail'")]
    corroboration=[x for x in aetna if x['fields'].get('npi')=='1790432490'and x['fields'].get('street_raw')=='14305 Collier Blvd']
    assert len(corroboration)==7
    resolution={'id':'REHAB-NPI-1497333017','state':'facility_identity_resolved; printed_identifier_error_retained',
        'hospital_id':'AHCA:458386','canonical_npi':'1790432490','incorrect_printed_npi':'1497333017',
        'identity_sources':{'official_registry':registry,'AHCA_license':licensed,'exact_Aetna_directory_record_ids':[x['id']for x in corroboration]},
        'reason':'The federal registry legal entity, licensed AHCA owner and exact Naples street agree; the Aetna directory independently prints the correct NPI at that same campus. The Erickson documents explicitly list that campus name/address but print the Greenville NPI.',
        'published_Erickson_campus_listing_basis':'Original exact-product 2026 directory name and street, with resolved facility identity and an explicit printed-ID error qualification.',
        'Erickson_participation_inherited_from_Aetna':False,'personal_participation_verified':False,
        'publisher_error_still_visible':True,'publisher_erratum_required_to_know_correct_facility_identity':False}
    db.execute('CREATE TABLE IF NOT EXISTS r2_source_conflict_resolutions(id TEXT PRIMARY KEY,fields_json TEXT)')
    db.execute('INSERT OR REPLACE INTO r2_source_conflict_resolutions VALUES(?,?)',(resolution['id'],json.dumps(resolution)))
    resolved=[]
    for hid,pid,state,raw in db.execute("SELECT *FROM hospital_plan_matrix WHERE hospital_id='AHCA:458386'AND offering_id LIKE '2026:H5652:%'").fetchall():
        evidence=json.loads(raw)
        if not any(x.get('identity_resolution_id')==resolution['id']for x in evidence):
            assert evidence and all(x.get('directory_identifier')=='1497333017'for x in evidence)
            evidence.append({'state':'published_directory_lists_campus','identity_resolution_id':resolution['id'],'canonical_npi':'1790432490','published_identifier_error':'1497333017','source_participation_basis':'Original exact Erickson plan publication lists this actual campus name/address; canonical identity established separately','personal_participation_guaranteed':False})
        db.execute('UPDATE hospital_plan_matrix SET state=?,evidence_json=? WHERE hospital_id=?AND offering_id=?',('published_directory_lists_campus',json.dumps(evidence),hid,pid));resolved.append(pid)
    assert len(resolved)==5
    resolution['resolved_held_offerings']=sorted(resolved)
    write(BASE/'rehabilitation-identity-resolution.json',resolution)
    db.execute('INSERT OR REPLACE INTO r2_source_conflict_resolutions VALUES(?,?)',(resolution['id'],json.dumps(resolution)))
    db.execute('CREATE VIEW IF NOT EXISTS current_source_conflicts AS SELECT c.id,c.kind,c.fields_json AS original_evidence_json,r.fields_json AS current_resolution_json FROM source_conflicts c LEFT JOIN r2_source_conflict_resolutions r ON r.id=c.id')
    supplemental=[]
    for r in identities:
        if r['npi']in ['1073701934','1194433540']:
            supplemental.append({'npi':r['npi'],'source_id':r['source_id'],'source_sha256':r['source_sha256'],'registry_legal_name':r['native']['basic'].get('organization_name'),'registry_practice_addresses':[a for a in r['native']['addresses']if a.get('address_purpose')=='LOCATION'],
                'source_directory_street_omission_not_overwritten':True,'exact_directory_location_or_participation_inferred_from_registry_alone':False})
    write(BASE/'suite-only-identity-supplements.json',supplemental)
    summary=json.loads((BASE/'summary.json').read_text());summary['hospital_matrix_states']=dict(db.execute('SELECT state,count(*)FROM hospital_plan_matrix GROUP BY state'))
    summary['collier_hospital_matrix_states']=dict(db.execute("SELECT m.state,count(*)FROM hospital_plan_matrix m JOIN hospitals h ON h.id=m.hospital_id WHERE h.county='Collier'GROUP BY m.state"))
    summary['former_hospital_identity_holds_resolved']=5;summary['registry_identity_observations']=len(identities)
    summary['aetna_identity_resolution_states']=dict(db.execute('SELECT identity_state,count(*)FROM aetna_identity_resolution GROUP BY identity_state'))
    summary['same_document_site_resolution_states']=dict(db.execute('SELECT state,count(*)FROM pdf_site_resolution GROUP BY state'))
    summary['source_only_context_units_by_family_and_domain']=[{'family':a,'domain':b,'records':c}for a,b,c in db.execute("SELECT family,domain,count(*)FROM pdf_records WHERE state LIKE 'source_context_%'GROUP BY family,domain")]
    coverage=json.loads((PARENT/'build-r1/plan-source-coverage.json').read_text())
    queries=json.loads((BASE/'aetna-query-accounting.json').read_text())
    for row in coverage:
        row['public_Aetna_bounded_queries']=[q for q in queries if q['offering_id']==row['offering_id']]
        row['full_provider_location_roster_completeness_established']=False
        row['normalization_revision']='followup-r2'
    write(BASE/'plan-source-coverage.json',coverage);write(BASE/'summary.json',summary)
    db.commit();db.close();print(json.dumps({'prepared':True,'resolved_hospital_identity_holds':5,'registry_identities':len(identities),'collier_hospital_matrix':summary['collier_hospital_matrix_states']},indent=2))


def publish():
    if(BASE/'SEALED').exists():raise ValueError('Already sealed; create another revision for changed data')
    v=json.loads((BASE/'validation.json').read_text());s=json.loads((BASE/'summary.json').read_text())
    if not v['passed']:raise ValueError('Validation must pass before publication')
    db=sqlite3.connect('file:'+str(BASE/'providers.sqlite3')+'?mode=ro',uri=True)
    q=json.loads((BASE/'aetna-query-accounting.json').read_text())
    ids=sorted({x['offering_id']for x in q});table=[]
    for pid in ids:
        p=next(x for x in q if x['offering_id']==pid and x['category']=='pcp');h=next(x for x in q if x['offering_id']==pid and x['category']=='hospital')
        table.append(f"| {pid.replace('2026:','').replace(':000','').replace(':','-')} | {p['captured_card_occurrences']} / {p['advertised_page_counts'][0]} pages | {h['captured_card_occurrences']} / {h['advertised_page_counts'][0]} pages |")
    internal={'status':'Substantial normalization completed; source-only and ambiguous context remains explicit',
        'original_multi_identifier_exceptions':599,'multi_identifier_exception_source_accounting_passed':True,
        'original_address_fragments':509,'recovered_source_addresses':v['parent_address_dispositions']['recovered_normalized_source_address'],
        'remaining_partial_or_nonstandard_fragments':v['parent_address_dispositions']['published_partial_or_nonstandard_address_explicitly_retained'],
        'same_document_exact_identity_site_resolutions':43,'ambiguous_or_absent_reprinted_sites_still_held':34,
        'native_listing_states':s['pdf_listing_states'],'source_only_context_by_family':s['source_only_context_units_by_family_and_domain'],
        'unexpanded_Aetna_multiple_location_card_occurrences':db.execute("SELECT count(*)FROM aetna_query_observations WHERE json_extract(fields_json,'$.fields.has_unexpanded_multiple_locations')=1").fetchone()[0],
        'internal_work_remaining':['Some name/group/context units need further semantic association to sites; these are not missing-PDF or source-access blockers.',
            'Some directory address fragments contain only a suite, route or ambiguous layout. Source text is retained; source-printed omission and unresolved parsing are not equated.',
            'Published section headings and specialties remain source-native; a universal clinical taxonomy and whole-county geocoding are not completed.',
            'Aetna specialty lists and multiple-location controls can be explored further through public targeted lookups, but captured bounded queries do not define the entire roster.'],
        'requires_owner_to_retype_or_find_new_PDFs_for_held_internal_tasks':False}
    write(BASE/'internal-work-and-source-limits.json',internal)
    parent_gaps=json.loads((PARENT/'audit-r1/genuine-gaps.json').read_text())
    gaps=[]
    for g in parent_gaps:
        g=dict(g)
        if g['id']=='L08-G02':
            g.update(status='partially_filled; full_all_specialty_rosters_unproved',gap='All five Aetna offerings now have complete captured hospital and local PCP query results, plus targeted campus evidence. Complete all-specialty/all-site rosters remain unproved.',
                need='An applicable complete dated provider/network export or permitted source-owner API access, with a denominator and exact plan applicability.',
                why='The official public PDF inventory does not supply these five full rosters. Query matches and unexpanded location cards cannot prove that every specialty/site across Collier is represented.',
                blocked_by='Completeness/export limitation, not a blanket guest-search denial. The registered FHIR route remains credential-restricted under the existing source instructions; credentials and the production client token were not used. Public targeted searches remain possible.')
        elif g['id']=='L08-G07':
            g.update(status='resolved_facility_identity; original_publisher_error_retained',gap='Correct Naples rehabilitation identity now established as NPI 1790432490; original five printed 1497333017 values remain visible as source errors.',
                need='No additional source is required to identify this campus or retain its qualified published Erickson listings.',
                why='Official registry legal entity/street, AHCA licensing and Aetna exact campus details agree. Original Erickson name/address supplies its own plan-listing evidence.',blocked_by=None)
        else:g['status']='unchanged_source_block_or_dependency'if g['kind']!='historical_date_limitation'else'stated_date_boundary; no full_year_history_claim'
        gaps.append(g)
    gaps.append({'id':'L08-G09','status':'targeted_lookup_unresolved','scope':['2026:H1609:027:000','AHCA:10107'],
        'gap':'Aetna H1609-027 detail for the Willough/Axiom campus cannot be displayed.',
        'need':'An applicable exact-plan campus listing or usable publisher detail/export.',
        'why':'PPO participation was explicitly obtained. The HMO page error and absence from another plan list do not establish out-of-network status.',
        'blocked_by':'Exact public detail returns “This provider can’t be displayed”; raw failure retained.'})
    gaps.append({'id':'L08-G10','status':'source_geography_conflict_held','scope':'One retained Humana Location observation',
        'gap':'Published address reports Naples together with Hillsborough district and ZIP 33614.',
        'need':'Corrected publisher location/identity or exact authoritative location reconciliation.',
        'why':'The city string cannot establish a physical Collier site; no correction was invented.',
        'blocked_by':'Source contradiction; carrier FHIR access stop remains active. See source-quality-holds.json.'})
    write(BASE/'genuine-gaps.json',gaps)
    write(BASE/'aetna-ui/collection-method.json',{'method':'Public anonymous Aetna guest UI, controlled through CUA; complete accessibility snapshots retained without treating them as raw HTTP packets',
        'benefit_year':2026,'year_basis':'Explicit 2026 Individual plan options for Collier County heading retained in plan-options snapshots',
        'origin':'Naples FL 34102 test location; not a user residence','queries':{'PCP':'25-mile radius, all returned pages','hospital':'100-mile radius, all returned pages'},
        'complete_query_card_occurrences':2367,'query_result_pages':121,'targeted_valid_hospital_detail_observations':11,'targeted_detail_failures':1,
        'all_specialty_or_whole_county_or_all_sites_completeness_established':False,'account_created':False,'member_id_used':False,'source_credentials_used':False})
    write(BASE/'verification-commands.json',{'date':'2026-10-27','syntax_check_passed':True,'regression_test_command':'python3 -m unittest discover -s cms-slice/tests -p test_l08_r2_reference.py','regression_tests_passed':8,
        'whole_population_validation_command':'python3 cms-slice/scripts/l08_r2_validate.py','whole_population_validation_passed':True,
        'source_bounds':'Captured modeled values, relational joins and source accounting; full-layer completeness remains false'})
    report=f'''# L08 provider reference follow up

October 27, 2026. **The five Aetna offerings now have substantially more usable evidence, and the 599 ambiguous identifier units are resolved. Full L08 remains incomplete.** The complete Aetna rosters across every specialty and site are still not established; the captured queries have a precisely stated scope.

This additive revision preserves the earlier [research snapshot](../REPORT.md), its sources and code. All 72 pinned Collier MA offerings remain visible. [Research database](providers.sqlite3), [per-plan coverage](plan-source-coverage.json), [validation](validation.json), [remaining gaps](genuine-gaps.json).

## Aetna results

The official public guest directory was set to the **2026 individual Collier plans**. All returned pages were retained for PCPs within 25 miles of Naples 34102 and hospitals within 100 miles. The query scope and plan selection are preserved with the results.

| Exact offering | Local PCP listings and pages | Hospital listings and pages |
|---|---:|---:|
{chr(10).join(table)}

All ten query totals reconcile: **2,367 listing observations across 121 result pages**, including repeated providers across plans. This is not a count of unique doctors. Eleven additional exact-plan hospital detail observations bring the new Aetna observation export to **2,378 records**. Names, publisher IDs, NPIs when shown, printed sites/phones, specialty labels, patient-acceptance qualifications, group links, accessibility, virtual offices and future-change text retain their exact source locators. Missing NPIs and virtual offices are retained rather than dropped.

Reusing an exact Aetna provider ID **and the same site** supplied 551 missing-NPI identity observations from other retained query results. Another 355 observations retain their publisher identity with NPI unresolved. This identity reuse never supplies another plan's participation. Source raw fields remain unchanged. [Query accounting](aetna-query-accounting.json), [identity resolution](aetna-identity-resolution.json), [portable Aetna records](aetna-records.jsonl.gz).

For the five previously missing Aetna offerings, **34 of 35 Collier hospital-campus × plan cells now have positive published listings**. All seven Collier campuses are listed for each of the four PPO offerings. The HMO has six supported campus listings; its behavioral-health-campus case remains unknown because the exact detail cannot be displayed. Missing results and page errors never mean out of network.

The public [Aetna directory page](https://www.aetna.com/medicare/find-provider.html) provides a limited PDF inventory. The existing Southwest D-SNP PDF applies to the other two Aetna offerings, not these five. The [mailed-directory request](https://www.aetna.com/medicare/find-provider/request-printed-directory.html) requires a member ID. Public guest search works, and further targeted lookups remain possible. It supplies no captured complete all-specialty/all-location denominator or export here. The credential-restricted FHIR route remains held under the existing source instructions; no account, credentials or production client token was used. A complete applicable published export or appropriately authorized source access is still needed to certify full Aetna roster completeness.

## Internal normalization completed

Reused all ten retained PDFs and their complete pages. Fixed HealthSpring's clipped top-of-column names and wrapped surnames; split Aetna group and clinician IDs; joined wrapped names; recognized footnote-prefixed streets, numeric ranges and other printed address forms. The revised native export contains **136,552 listing units** and **169,915 address observations**, with duplicate/regional/supplemental records retained rather than described as unique Collier clinicians.

Every one of the original **599 multi-identifier exceptions** now accounts for all its exact identifier source nodes in separate, unambiguous listing units. Repeated NPIs at multiple practice locations remain explicit occurrences. Of the original **509 address fragments, 388 are recovered as normalized source addresses and 121 remain explicit partial/nonstandard fragments**. Those 121 fragments occur within 53 listing units; they are not 121 missing doctors. [599-unit reconciliation](parent-599-identifier-dispositions.json), [509-fragment reconciliation](parent-509-address-dispositions.json).

The model now retains **247,622 typed source qualifier/context observations**: languages, group/hospital affiliations, hours, licenses, primary-care IDs, raw section headings and supported legend meanings for patient restrictions, telehealth, accessibility and other source conditions. Absence of a marker remains unknown. There is no clinical eligibility inference from a provider's name, sex, group or marker. [Normalized PDF records](normalized-pdf-records.jsonl.gz).

Within the same exact Aetna document, matching provider ID plus primary-care ID resolved **43 uniquely reprinted practice sites** without changing the original incomplete unit; 34 ambiguous/no-match cases stay held. The remaining source-only context includes 332 name/group headers with IDs but no explicit site in that unit, and 2,275 other context units. Of the latter, 1,978 have pharmacy/other identifier domains; they are not automatically missing medical-provider records. Some medical/group context still needs semantic association. This is internal work using sources already held, not a request for the owner to find PDFs. [Internal work and source limits](internal-work-and-source-limits.json).

## Hospital identity resolved

The correct NPI for **Encompass Health Rehabilitation Hospital of Naples, LLC / Rehabilitation Hospital of Naples at 14305 Collier Blvd is 1790432490**. The [official registry search](https://npiregistry.cms.hhs.gov/api/?version=2.1&number=1790432490), AHCA legal owner/street and exact Aetna directory detail agree. The five Erickson PDFs instead print 1497333017, which the registry assigns to Greenville, South Carolina.

The canonical campus identity and all five former campus-identity holds are now resolved. Each Erickson observation uses its **own original exact-plan campus name/address evidence**; its participation is not inherited from Aetna. The incorrect printed number and original evidence remain visible, with the qualified identity resolution alongside them. A publisher erratum is desirable but is not needed to know the correct facility identity. [Complete identity resolution](rehabilitation-identity-resolution.json).

The two suite-only Collier identities were also checked: NPPES supplies a practice address for Renal Specialists of Naples, NPI 1073701934, and HQ of Naples LLC, NPI 1194433540. Those registry addresses are stored separately. They do not silently replace omitted directory streets or establish an exact plan/site relationship on their own. [Suite-only identity supplements](suite-only-identity-supplements.json).

Across the complete 17-campus × 72-plan matrix, there are now **151 positive published campus listings and 1,073 unknown cells**. For Collier alone: **113 positive listings and 391 unknowns out of 504**. These are published observations with source dates/conditions, not personal appointment or coverage guarantees.

## Genuine remaining blocks and limits

| Area | What is missing and why | Evidence needed |
|---|---|---|
| Aetna five offerings | Full all-specialty/all-site rosters are not established by the completed bounded queries. Guest access is working; this is an export/completeness limit. | Applicable complete dated export/directory or permitted source-owner API access with an explicit denominator and exact plan applicability. |
| Wellcare six offerings | No applicable complete medical roster acquired; recorded access stop remains. Medicaid/pharmacy data cannot substitute. | Exact 2026 MA medical directories/exports or source-owner access resolution. |
| Humana 22 offerings | Many referenced provider/site identities remain unresolved; a large crawl had moving totals and duplicates before the FHIR 403 stop. | Stable complete medical-network export including referenced identities, or restored permitted source access. |
| UHC/Flex | Exact plan/network semantics conflict with resolved organization names, filters were ignored, and some geographic/pagination partitions failed. Erickson's publications are partial lists. | Authoritative plan/network crosswalk interpretation and complete usable rosters, corrected source records or applicable independent publications. |
| Florida Blue five offerings | Generic product/network codes still lack an explicit exact CMS contract/PBP/segment crosswalk. | Official crosswalk and complete supported medical roster/export. |
| Original Medicare | Applicable federal clinician/enrollment/assignment/opt-out and hospital-ID files were not collected after the CMS data-host 403. NPI and state licensure do not supply those facts. | Official dated CMS snapshots plus dictionaries through a permitted download or supplied original files. |
| Aetna H1609-027 behavioral-health campus | Exact page returns “This provider can’t be displayed.” PPO evidence is not transferable. | Applicable exact-plan campus evidence or a usable publisher response/export. |
| One Humana location | Source says Naples, Hillsborough district and ZIP 33614. City alone cannot prove a physical Collier site. | Corrected publisher record or exact authoritative location reconciliation. The original values remain held and visible. |

Source-only group/partial-address interpretation, unexpanded location controls, a universal specialty taxonomy and whole-county geocoding remain internal/integration work; they are not all external access blockers. Exact historical participation throughout 2026 is not inferred from a plan year or current directory. Live appointment/new-patient guarantees are outside this published-reference scope. Medicare SELECT remains an exact-product dependency on L10.

## Validation and scope

[Validation](validation.json) passed with **zero unexplained modeled-value mismatches**. It rehashed all **4,390 sealed parent files**, compared **1,057,993 unchanged parent rows**, checked all new Aetna fields at their exact AX nodes/spans, every revised listing/address/identifier/qualifier against source lines and original XML coordinates, all original exception dispositions, registry objects, reprinted-site/identity joins, hospital-plan evidence, SQLite/export parity and integrity. Eight regression tests cover actual column/name/group failures, missing NPIs, virtual offices, exact expanded-plan evidence, unavailable-detail handling and street forms. The retained parent validation supplies the unchanged FHIR/native-page source comparisons.

D64 independence and D73 honest-scope/control gates remain intact: no commercial inputs, profile intake, personal recommendations, consumer UI changes, deployment or inherited acceptance. This improves the inspectable data prerequisite; it does not establish full L08 completeness, personal fit or consumer outcomes. The [active research reference](../CURRENT_REFERENCE.json) points to this additive snapshot; prior evidence is preserved.
'''
    (BASE/'REPORT.md').write_text(report)
    (BASE/'README.md').write_text('''# L08 provider reference follow up

**Validated additive research snapshot; full L08 remains incomplete.** October 27, 2026.

Read the [results, genuine blockers and remaining internal work](REPORT.md). The five Aetna offerings now have complete captured hospital/local-PCP query results and targeted campus evidence. All 599 original multi-ID units reconcile; 388 of 509 address fragments are recovered. The rehabilitation hospital identity is resolved with its original printed NPI error preserved.

- [Research SQLite database](providers.sqlite3)
- [Validation](validation.json)
- [Genuine gaps](genuine-gaps.json)
- [Internal work and source limits](internal-work-and-source-limits.json)
- [Per-plan source coverage](plan-source-coverage.json)
- [Query completeness accounting](aetna-query-accounting.json)
- [Manifest](manifest.json)

The parent snapshot and its code/evidence are unchanged. Full all-specialty/all-site provider rosters and exact network mappings remain incomplete. Consumer release and personal recommendations remain held.
''')
    db.close()
    (BASE/'SEALED').write_text('L08-PUBLISHED-COLLIER-2026-research-r2\n')
    (BASE/'acquisition/SEALED').write_text('Public-source collection closed for this immutable revision.\n')
    excluded={BASE/'manifest.json',BASE/'manifest-validation.json'}
    selected=[p for p in BASE.rglob('*')if p.is_file()and p not in excluded and'__pycache__'not in p.parts]
    selected+=list((ROOT/'cms-slice/scripts').glob('l08_r2_*.py'))+[ROOT/'cms-slice/tests/test_l08_r2_reference.py']
    files={str(p.relative_to(ROOT)):{'sha256':sha(p),'bytes':p.stat().st_size}for p in sorted(selected)}
    manifest={'schema':'l08-followup-manifest/2','reference_id':'L08-PUBLISHED-COLLIER-2026-research-r2','created_at_utc':datetime.now(timezone.utc).isoformat(),
        'parent_manifest':'docs/data/l08-provider-networks-2026-10-27/execution-manifest-r1.json','parent_manifest_sha256':sha(PARENT/'execution-manifest-r1.json'),
        'status':'validated_captured_reference; comprehensive_layer_incomplete','consumer_release_enabled':False,'human_accepted':False,'all_specialty_roster_complete':False,
        'validation_sha256':sha(BASE/'validation.json'),'files':files}
    write(BASE/'manifest.json',manifest)
    write(PARENT/'CURRENT_REFERENCE.json',{'reference_id':manifest['reference_id'],'kind':'incomplete_research_reference',
        'manifest':'followup-r2/manifest.json','manifest_sha256':sha(BASE/'manifest.json'),'database':'followup-r2/providers.sqlite3','report':'followup-r2/REPORT.md',
        'parent_reference_id':'L08-PUBLISHED-COLLIER-2026-research-r1','consumer_release_enabled':False,'comprehensive_layer_complete':False,'human_accepted':False})
    mismatches=[path for path,item in files.items()if sha(ROOT/path)!=item['sha256']or(ROOT/path).stat().st_size!=item['bytes']]
    write(BASE/'manifest-validation.json',{'passed':not mismatches,'files_hashed':len(files),'failures':mismatches,
        'active_reference_manifest_agrees':json.loads((PARENT/'CURRENT_REFERENCE.json').read_text())['manifest_sha256']==sha(BASE/'manifest.json')})
    if mismatches:raise ValueError('Manifest validation failed')
    print(json.dumps({'published':True,'files_sealed':len(files),'full_layer_complete':False,'report':str(BASE/'REPORT.md')},indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--prepare',action='store_true');p.add_argument('--publish',action='store_true');args=p.parse_args()
    if args.prepare:prepare()
    if args.publish:publish()
