#!/usr/bin/env python3
"""Publish the captured L08 research audit, explicit gaps, and additive seal."""
from collections import Counter,defaultdict
from datetime import datetime,timezone
import gzip
import hashlib
import json
import sqlite3
from urllib.parse import urlparse
from l08_acquire import BASE,OUT,ROOT,write


def sha(path):
    h=hashlib.sha256()
    with path.open('rb')as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()


def main():
    b=BASE/'build-r1';summary=json.loads((b/'summary.json').read_text())
    validation=json.loads((b/'validation.json').read_text())
    if not validation['passed']:raise ValueError('Captured-field validation must pass first')
    plans=json.loads((BASE/'plan-source-matrix.json').read_text());coverage=json.loads((b/'plan-source-coverage.json').read_text())
    docs=json.loads((BASE/'document-index-r1/documents.json').read_text())
    db=sqlite3.connect('file:'+str(b/'providers.sqlite3')+'?mode=ro',uri=True)
    audit=BASE/'audit-r1';audit.mkdir(exist_ok=True)
    receipts=[json.loads(p.read_text())for p in sorted((OUT/'receipts').glob('*.json'))]
    receipt_by_id={r['id']:r for r in receipts}
    crawls=[]
    for p in sorted((OUT/'crawls').glob('*.json')):
        c=json.loads(p.read_text());q=c.get('query',{})
        crawls.append({'id':c['id'],'receipt_accounting':str(p.relative_to(ROOT)),
            'scope':q.get('scope'),'query':q,'pages':len(c.get('pages',[])),
            **{k:c.get(k)for k in ['complete','advertised_totals','match_records','unique_matches','duplicate_match_occurrences','exact_total_agrees','error']},
            'pagination_exhausted_is_not_full_roster_proof':True})
    write(audit/'crawl-accounting.json',crawls)
    source_stats={'retained_receipts':len(receipts),'responses_with_retained_bytes':sum(bool(r.get('path'))for r in receipts),
        'response_status_counts':dict(Counter(str(r.get('http_status'))for r in receipts)),
        'crawl_attempts':len(crawls),'pagination_exhausted':sum(bool(c['complete'])for c in crawls),
        'not_exhausted_or_failed_or_stopped':sum(not c['complete']for c in crawls),
        'new_access_stops':json.loads((OUT/'stopped-hosts.json').read_text()),
        'inherited_access_stops':['uhc.com and subdomains','wellcare.com and subdomains','medicare.gov and subdomains','iopc-pd.api.centene.com'],
        'authentication_html_is_not_provider_data':True}
    write(audit/'source-accounting.json',source_stats)
    family=[]
    for parent in sorted({p['parent']for p in plans}):
        rows=[p for p in plans if p['parent']==parent];ids={p['id']for p in rows}
        cs=[c for c in coverage if c['offering_id']in ids]
        family.append({'parent':parent,'offering_count':len(rows),'offerings':sorted(ids),
            'offerings_with_downloaded_2026_publication':sum(c['published_directory_acquired']for c in cs),
            'full_provider_location_roster_complete':False})
    write(audit/'carrier-coverage.json',family)
    def ids(contract=None,parent_contains=None):
        return [p['id']for p in plans if (contract is None or p['contract']==contract)and(parent_contains is None or parent_contains.casefold()in p['parent'].casefold())]
    gaps=[
      {'id':'L08-G01','kind':'additional_source_or_restored_access','scope':ids(contract='H1032'),
       'gap':'No applicable complete 2026 Wellcare MA medical-provider roster acquired for six offerings.',
       'need':'Official 2026 Collier medical directory/export with exact H1032 plan/network applicability, or source-owner resolution of the recorded access stop.',
       'why':'The existing plan and benefit records do not enumerate doctors, sites or hospital participation. A Medicaid or pharmacy directory cannot substitute.',
       'blocked_by':'Existing Centene 403 and Wellcare host stop; no permitted complete public alternative found in this collection.'},
      {'id':'L08-G02','kind':'additional_source_or_complete_public_export','scope':['2026:H1609:027:000','2026:H5521:033:000','2026:H5521:272:000','2026:H5521:306:000','2026:H5521:710:000'],
       'gap':'Five Aetna offerings lack a collected complete dated roster.',
       'need':'Applicable 2026 directories or complete guest-directory exports for these five exact plans, retaining all sites and conditions.',
       'why':'The acquired Southwest DSNP publication applies to target H1609-056 and H1609-078. It does not cover the other five. A successful targeted browser lookup is not a whole roster.',
       'blocked_by':'Complete export not acquired. Public guest search works for all seven, so this is not a blanket Aetna access claim; credentialed API 401 remains separately recorded.'},
      {'id':'L08-G03','kind':'additional_source_or_restored_access','scope':ids(parent_contains='Humana'),
       'gap':'Humana exact plan records were acquired, but complete stable provider/location identities and rosters were not.',
       'need':'A stable applicable 2026 medical-network export including all referenced Practitioner/Location resources, or source-owner resolution permitting complete directory collection.',
       'why':'Many roles reference opaque unresolved IDs. A large network crawl had moving totals and duplicates; local city searches do not prove the whole county.',
       'blocked_by':'FHIR responses redirected to authentication HTML and then returned 403; persisted host stop. Independently advertised HMO/PPO PDFs examined covered Manatee/Sarasota, not Collier.'},
      {'id':'L08-G04','kind':'additional_source_or_corrected_relationships','scope':ids(parent_contains='United'),
       'gap':'UHC/Flex network references conflict with resolved organization names, and local location/role pagination remains incomplete.',
       'need':'Authoritative exact 2026 CMS-plan-to-medical-network mapping and complete applicable directory/export; use corrected source records or independently permitted dated publications.',
       'why':'A Florida plan reference can resolve to an organization named for another state/plan. An address-state filter returned California. Failed Naples/34102 partitions leave missing records.',
       'blocked_by':'Source contradictions and recorded HTTP 500 pagination failures. The five Erickson PDFs add real published evidence but explicitly describe partial lists, dated August 10, 2025 for benefit year 2026.'},
      {'id':'L08-G05','kind':'additional_crosswalk_evidence','scope':ids(parent_contains='GuideWell'),
       'gap':'Florida Blue medical products and local provider records lack an explicit CMS contract/PBP/segment crosswalk.',
       'need':'Official mapping from the five exact CMS offerings to the source product/network codes, plus a complete supported network/geographic export.',
       'why':'Matching a family/product name does not establish exact plan participation. The source rejects its advertised network search parameter; a local-city query is not a whole-network census.',
       'blocked_by':'Exact mapping not present in the held plan/product records or general directory routes. All five joins remain held.'},
      {'id':'L08-G06','kind':'additional_official_snapshots','scope':'Original Medicare and hospital federal identifiers',
       'gap':'No applicable CMS 2026 clinician/enrollment/assignment/opt-out dataset snapshots acquired.',
       'need':'Dated Doctors and Clinicians national file and dictionary, facility affiliations, all five public enrollment relational files, opt-out affidavits, and Hospital General Information.',
       'why':'NPPES identifies an entity; AHCA licenses a hospital. Neither establishes Medicare enrollment, published assignment status, opt-out periods, or exact federal CCNs.',
       'blocked_by':'data.cms.gov returned 403 on metadata requests; host stop preserved. A permitted official archived download or supplied original files can fill it.'},
      {'id':'L08-G07','kind':'specific_source_identity_conflict','scope':['AHCA:458386']+ids(contract='H5652'),
       'gap':'All five Erickson directories print an NPI for the Naples rehabilitation hospital that the registry assigns to a Greenville, South Carolina organization.',
       'need':'Publisher correction or specific authoritative evidence resolving the Naples legal entity/campus identifier and applicable listing.',
       'why':'The discrepancy is visibly printed in the PDFs and confirmed by the exact federal registry response. It cannot be repaired by silently replacing the NPI.',
       'blocked_by':'Conflicting source facts; five hospital-plan identity cells held. Listing and address remain retained.'},
      {'id':'L08-G08','kind':'historical_date_limitation','scope':'All directory sources where no relationship period is published',
       'gap':'A 2026 plan and a current directory observation do not establish uninterrupted participation throughout 2026 or at an unrelated earlier snapshot.',
       'need':'Dated editions or explicit effective/termination evidence only when such historical claims are required.',
       'why':'Benefit year, publication date, retrieval date and provider relationship period are distinct. Sources can overwrite live relationships.',
       'blocked_by':'Historical periods often not published; retained observations remain usable for their actual stated scope.'},
      {'id':'L08-D01','kind':'conditional_other_layer_dependency','scope':'Medicare SELECT only if L10 establishes an applicable product',
       'gap':'Exact SELECT policy/form/network applicability not established in this L08 collection.',
       'need':'The exact applicable L10 insurer/form/network and its dated directory, if relevant.',
       'why':'Ordinary Medigap does not supply an MA-style network; SELECT is policy-specific.',
       'blocked_by':'L10 product/form dependency; this does not assert SELECT is absent.'},
    ]
    # Match parent spellings from the pinned denominator rather than assuming.
    for g in gaps:
        if g['id']in ['L08-G03','L08-G04','L08-G05']and not g['scope']:raise ValueError('Empty carrier gap scope '+g['id'])
    write(audit/'genuine-gaps.json',gaps)
    states=dict(db.execute('SELECT state,count(*)FROM pdf_records GROUP BY state'))
    internal={'kind':'internal_normalization_using_retained_sources','requires_wholesale_new_sources':False,
       'pdf_record_states':states,'unassigned_address_fragments':summary['unassigned_source_address_fragments'],
       'work_remaining':['Resolve 599 native listing units containing multiple identifiers before asserting a single entity/location association.',
         'Review 3,047 source name/identifier mentions without a normalized location; some are contextual mentions rather than distinct providers.',
         'Assign or explicitly classify 509 retained address fragments using original page/column context.',
         'Complete semantic normalization of PDF specialties, group/IPA restrictions, accepting-new-patients, language/accessibility and legends; complete source text and native line ranges are retained.',
         'Reconcile repeated native listing units and multi-site entities without equating counts to unique doctors or a whole-county census.'],
       'external_source_blocker_for_these_tasks':False,
       'captured_field_roundtrip_validation_is_not_complete_semantic_verification':True}
    write(audit/'internal-normalization-holds.json',internal)
    quality=defaultdict(list);checked=0
    def valid_npi(value):
        if len(value)!=10 or not value.isdigit():return False
        return sum((2*int(c)//10+2*int(c)%10)if i%2 else int(c)for i,c in enumerate(('80840'+value)[::-1]))%10==0
    for oid,native in db.execute('SELECT id,native_json FROM observations'):
        for ident in json.loads(native).get('identifier',[]):
            if 'us-npi'not in ident.get('system',''):continue
            value=ident.get('value','');checked+=1
            if not value:quality['missing_value'].append({'observation_id':oid,'source_locator':'identifier system declares NPI but value absent'})
            elif not valid_npi(value):quality['invalid_nonempty_value'].append({'observation_id':oid,'value':value})
    for rid,value in db.execute("SELECT id,identifier FROM pdf_records WHERE identifier_kind='npi'"):
        checked+=1
        if not valid_npi(value or''):quality['invalid_nonempty_value'].append({'pdf_record_id':rid,'value':value})
    if not valid_npi('1720085137')or valid_npi('1720085138'):raise ValueError('NPI check-digit control failed')
    write(b/'npi-syntax-quality.json',{'schema':'l08-npi-syntax-quality/2','algorithm':'NPI Luhn check digit with 80840 prefix',
        'npi_claim_observations_checked':checked,'missing_npi_value_claims':len(quality['missing_value']),
        'invalid_nonempty_npi_claims':len(quality['invalid_nonempty_value']),'cases':dict(quality),
        'registry_match_or_medical_participation_established_by_checksum':False})
    exclusions=[
      {'source':'Optimum indexed dlsecure/?_id=1203811','state':'excluded_wrong_actual_year','actual':'Downloaded cover is 2027 despite 2026 search metadata; exact yeardoc=2026 publication separately collected.'},
      {'source':'Humana assets H1036FLHS04EG26pdf and H5216FLLS01EG26pdf','state':'excluded_wrong_geography','actual':'2026 covers and Oct 11, 2026 update retained; actual service-area page lists Manatee/Sarasota, not Collier.'},
      {'source':'Freedom 2026 MA-only companion','state':'retained_no_target_binding','actual':'1,394 pages retained, but all six target Freedom offerings are drug-bearing and bind to the MAPD edition.'},
      {'source':'Florida Health hospital GIS service','state':'excluded_stale_denominator','actual':'Returned records dated January 2017 and duplicates; replaced with active/open AHCA search and 17 exact profiles.'},
      {'source':'Sunshine SMI directory','state':'not_substituted','actual':'Medicaid program is not the six target Wellcare Medicare Advantage offerings.'},
      {'source':'CMS national provider directory exact-ID probes','state':'not_negative_evidence','actual':'Empty bundles from a search parameter not advertised by metadata do not establish plan absence.'},
      {'source':'Humana 200 authentication HTML and any OperationOutcome/errors','state':'excluded_nonprovider_or_incomplete','actual':'Retained receipts; never normalized as an empty successful provider roster.'},
      {'source':'NCH January 2027 notice and older 2027 C15 cells','state':'not_2026_network_evidence','actual':'No 2026 termination or participation conclusion inherited.'}]
    write(audit/'exclusions.json',exclusions)
    db.close()
    report=f'''# L08 published 2026 doctors and hospitals — collection result

Collected October 27, 2026. **The captured reference is validated; comprehensive L08 is still incomplete.** This is an additive research reference for the 2026 Collier MVP. The remaining gaps are missing usable rosters, exact network mappings, federal participation files and one concrete hospital-identity conflict—not a blanket requirement for a second source or phone calls.

All **72 pinned Collier MA offerings** remain accounted for, including 61 drug-bearing and 11 MA-only offerings. Standalone PDPs are outside medical-network scope. The original [approved collection plan](PLAN.md) and its planning manifest remain historical; [execution authorization](execution-authorization-r1.json) records this collection. Consumer release and personal recommendations remain held.

## What was reused and collected

Reused the L02 exact contract/plan/segment identities, all 144 held L03 SB/EOC slots for directory routes and applicability, the saved 2026 Blue/UHC resources, and existing identity/geography research. Prior references and reused PDF bytes passed preservation checks. Main benefit documents were not mistaken for provider rosters.

| Source family | Target offerings | Downloaded applicable 2026 publications | What the new evidence establishes / its limit |
|---|---:|---:|---|
| Freedom / Optimum | 10 | 2 shared carrier directories | Sept 1, 2026 editions, native plan/group conditions retained. Broad published listings; not a blanket guarantee that every listed provider serves every plan/site. |
| Erickson within UHC | 5 | 5 exact product directories | Benefit year 2026, actual publication date Aug 10, 2025; source expressly describes partial lists. |
| HealthSpring | 3 | 1 Central/Southern Florida directory | Oct 8, 2026; exact H5410 plan applicability retained. Medical and pharmacy portions distinguished. |
| Aetna | 7 | 1 Southwest DSNP directory covering 2 targets | Actual live PDF Aug 18, 2026. Public guest search observed for all seven; a targeted lookup does not complete the other five rosters. |
| Humana | 22 | No applicable Collier PDF acquired | All 22 exact 2026 plan API records plus network/provider/location observations. Complete stable roster/identity resolution remains unproved. |
| Other UHC | 14 | No complete applicable PDF acquired | All exact 2026 plan API records acquired; network-name conflicts and failed geography/pagination partitions held. |
| Florida Blue | 5 | No complete applicable PDF acquired | Reused 27 product resources, collected local providers/sites; exact CMS-plan/product crosswalk absent. |
| Wellcare | 6 | None | Existing access stop preserved; Medicaid/pharmacy directories not substituted. |

Nine applicable PDFs support **20 of 72 offerings** and contain **8,811 pages**. A separate Freedom MA-only companion adds 1,394 retained pages but covers no target offering in this denominator. Total indexed evidence is **10 PDFs / 10,205 complete pages**. These counts measure acquired publications, not complete networks. [Document inventory and direct official download URLs](document-index-r1/documents.json).

The database retains **82,055 versioned FHIR observations**, 6,025 publisher location entities, 72,223 role entities, and **133,484 native PDF listing units** with 169,547 address observations. These are repeated, regional and sometimes supplemental/source-context records—not unique local doctors. Original source objects, complete pages, qualifiers, source columns/lines and identifiers are retained. [SQLite reference](build-r1/providers.sqlite3), [portable FHIR export](build-r1/resources.jsonl.gz), [PDF listing export](pdf-records-r1/records.jsonl.gz).

## Hospitals: actual campuses, explicit unknowns

The official [Florida AHCA active/open hospital search](https://quality.healthfinder.fl.gov/Facility-Search/FacilityLocateSearch) returned **7 Collier, 9 Lee and 1 Hendry entries**, each with a separately collected licensing/profile record. This is the published active/open search result at retrieval, not a census of every outpatient facility or every historical 2026 campus. Shared licenses, legal owners and individual campuses remain distinct. Federal CCNs await the CMS file.

The seven Collier entries are NCH Baker, NCH North Naples, Physicians Regional Pine Ridge, Physicians Regional Collier Boulevard, Physicians Regional North, Rehabilitation Hospital of Naples, and Axiom Behavioral Health at Naples. [Official names, addresses, license dates and source receipts](build-r1/hospital-reference.json).

The complete **17 × 72 = 1,224-cell** hospital-plan matrix has **85 published campus-listing observations, 5 held identifier conflicts and 1,134 unknowns**. For Collier alone: **72 published observations, 5 held conflicts and 427 unknowns out of 504 cells**. A published observation means the applicable source lists that campus with its native qualifications; it does not guarantee current personal participation. Unknown never means out of network.

One genuine conflict: the five Erickson PDFs print NPI **1497333017** beside the Naples rehabilitation hospital at 14305 Collier Blvd. The [exact NPPES registry response](https://npiregistry.cms.hhs.gov/api/?version=2.1&number=1497333017) assigns it to Encompass Health Rehabilitation Hospital of Greenville, LLC, South Carolina. The PDF image was checked; this is not an extraction typo. Both facts are retained and the five identity cells remain held. We need a publisher correction or specific authoritative resolution, not an invented replacement. [Exact source pages and conflict evidence](build-r1/hospital-identity-conflicts.json), [rendered page](render-r1/rehab-npi-conflict.png).

## What validation passed—and what it does not prove

[Full captured-field validation](build-r1/validation.json) passed with **zero unexplained modeled-value mismatches**. It checks every retained response's bytes/hash; every FHIR native object and modeled field at its exact source pointer; entity/location/role projections; every plan/network and relationship reference; every complete PDF page; every indexed NPI/publisher-ID/phone span; all parsed listing names/IDs/addresses/contact values against source lines and original extraction nodes; all 17 hospital profiles; SQLite/export parity and integrity; and preservation of reused inputs. The five safety regression tests cover wrong-year IDs, product names versus CMS IDs, namespaces/locations, HTTP-200 errors and truncated includes.

This establishes faithful storage of **captured modeled information**. It does not certify source truth, complete semantic parsing of every directory field, a complete provider universe, or a person's current coverage. For example, Humana's large FL HMO crawl exhausted pagination but returned 35,396 match occurrences, 35,295 unique records and 101 duplicates while totals changed through 23 values. UHC's advertised Florida filter returned California records; some Naples/34102 pages failed. Blue rejects its advertised network filter. These are explicit source limitations, not successful empty lists. [Every query and pagination outcome](audit-r1/crawl-accounting.json).

## Genuine additional data needed

| Gap | Additional evidence needed | Why it matters |
|---|---|---|
| Wellcare: 6 plans | Applicable 2026 MA medical directory/export or source-owner access resolution | No complete roster acquired; plan/PBP and Medicaid data do not supply those doctor/site relationships. |
| Aetna: 5 plans | Complete applicable dated directories or public guest exports for H1609-027 and H5521-033/272/306/710 | The acquired DSNP directory covers two other target plans. Guest search works, but complete export has not been collected. |
| Humana: 22 plans | Stable complete medical-network export with all referenced provider/location identities, or restored permitted API access | Opaque unresolved references and moving/duplicated pages prevent a complete usable map. FHIR eventually returned 403; the host stop is preserved. The public PDF alternatives examined cover Manatee/Sarasota, not Collier. |
| UHC/Flex: 19 plans, including partial Erickson publications | Correct exact-plan/network mappings plus complete applicable rosters | Source network names conflict, some filters are ignored, and failed partitions leave missing sites/roles. The five PDFs add real evidence without repairing those gaps. |
| Florida Blue: 5 plans | Official CMS contract/PBP/segment → product/network crosswalk and supported complete roster export | Product-family matches cannot support exact plan participation. |
| Original Medicare and hospital federal IDs | Dated official CMS clinician, enrollment, opt-out, affiliation and hospital files with dictionaries | NPI and state licensure do not establish enrollment, assignment, opt-out periods or CCNs. data.cms.gov returned 403; collection stopped. |
| Naples rehabilitation identity | Specific authoritative correction/resolution of the printed NPI conflict | Prevents attaching the wrong legal entity to five published plan/campus listings. |

The federal sources needed are [Doctors and Clinicians](https://data.cms.gov/provider-data/dataset/mj5m-pzi6), [facility affiliations](https://data.cms.gov/provider-data/dataset/27ea-46a8), the [five public enrollment files and methodology](https://data.cms.gov/resources/fee-for-service-public-provider-enrollment-methodology-q1-2026), [opt-out affidavits](https://data.cms.gov/provider-characteristics/medicare-provider-supplier-enrollment/opt-out-affidavits), and [Hospital General Information](https://data.cms.gov/provider-data/dataset/xubh-q36u). Each answers a different question; none replaces an MA directory. Enrollment extracts and the claims-lookback clinician file also have stated population/date limits.

Historical participation needs dated editions/effective records only if making a claim for an earlier date or all of 2026. Missing unpublished appointment availability is outside this published-reference scope. Medicare SELECT remains a conditional exact-product/network dependency on L10, rather than an invented general Medigap network. [Machine-readable gaps, exact affected offerings, evidence needed and reasons](audit-r1/genuine-gaps.json).

## Internal work still open using sources already held

This is separate from the source gaps above: **599 multiple-identifier listing units**, **3,047 source mentions without normalized locations**, and **509 retained address fragments** need further interpretation. PDF specialty/group/IPA/accepting-new-patient/language/accessibility conditions and legends are preserved in source text but are not all normalized into comparable fields. Duplicate and multi-site reconciliation also remains. These tasks do not require the owner to find new PDFs. [Internal normalization register](audit-r1/internal-normalization-holds.json).

The scalable model separates publisher-namespaced entities, locations, networks, exact L02 offerings and versioned relationship observations. It preserves plan year, publication, retrieval and relationship dates separately. County filtering can reuse the same regional source without duplicating provider identities, but whole-county geography is not yet established by the city searches.

The current result supports inspection of published evidence and explicit verification tasks. **It does not close comprehensive L08 or unlock personal doctor/hospital recommendations.** Original plan/acceptance gates and other layers remain unchanged. [Source exclusions](audit-r1/exclusions.json), [source accounting](audit-r1/source-accounting.json), [execution manifest](execution-manifest-r1.json).
'''
    (BASE/'REPORT.md').write_text(report)
    (BASE/'README.md').write_text('''# L08 doctors and hospitals

**Collected research reference; comprehensive L08 remains incomplete.** October 27, 2026.

Read the [collection result and genuine gaps](REPORT.md). All 72 pinned 2026 Collier MA offerings are retained. Nine applicable downloaded directories support 20 offerings; API records and 17 official hospital profiles add evidence. Captured modeled fields and exports passed full-population source comparisons. Missing complete rosters, exact network mappings, federal participation files, one hospital NPI conflict and explicit internal normalization holds remain.

- [Validated SQLite research reference](build-r1/providers.sqlite3)
- [Captured-field validation](build-r1/validation.json)
- [Exact per-plan source coverage](build-r1/plan-source-coverage.json)
- [Genuine additional-source gaps](audit-r1/genuine-gaps.json)
- [Internal work using retained sources](audit-r1/internal-normalization-holds.json)
- [Directory inventory and official PDF links](document-index-r1/documents.json)
- [Execution manifest](execution-manifest-r1.json)

The [original collection plan](PLAN.md), [planning audit](validation.json) and original manifest are preserved historical planning artifacts. [Execution authorization](execution-authorization-r1.json) supersedes their proposed-only status for this collection; it does not confer data acceptance or consumer release. L01–L07 references and the consumer interfaces were not changed by this execution.
''')
    selected=[*sorted(BASE.rglob('*')),*sorted((ROOT/'cms-slice/scripts').glob('l08_*.py')),ROOT/'cms-slice/tests/test_l08_reference.py']
    exclude={BASE/'execution-manifest-r1.json',BASE/'execution-manifest-validation-r1.json',BASE/'CURRENT_REFERENCE.json'}
    files={str(p.relative_to(ROOT)):{'sha256':sha(p),'bytes':p.stat().st_size}for p in selected if p.is_file()and p not in exclude and '__pycache__'not in p.parts}
    manifest={'schema':'l08-execution-manifest/1','created_at_utc':datetime.now(timezone.utc).isoformat(),
        'reference_id':'L08-PUBLISHED-COLLIER-2026-research-r1','status':'captured_reference_validated_comprehensive_layer_incomplete',
        'execution_authorized':True,'human_acceptance_inherited':False,'consumer_release_enabled':False,
        'full_roster_completeness_established':False,'captured_field_validation_passed':True,
        'files':files}
    write(BASE/'execution-manifest-r1.json',manifest)
    write(BASE/'CURRENT_REFERENCE.json',{'reference_id':manifest['reference_id'],'kind':'incomplete_research_reference',
        'manifest':'execution-manifest-r1.json','manifest_sha256':sha(BASE/'execution-manifest-r1.json'),
        'database':'build-r1/providers.sqlite3','report':'REPORT.md','consumer_release_enabled':False,
        'comprehensive_layer_complete':False,'human_accepted':False})
    failures=[path for path,expected in files.items()if sha(ROOT/path)!=expected['sha256']or(ROOT/path).stat().st_size!=expected['bytes']]
    write(BASE/'execution-manifest-validation-r1.json',{'passed':not failures,'files_hashed':len(files),'failures':failures,
        'current_reference_manifest_hash_agrees':json.loads((BASE/'CURRENT_REFERENCE.json').read_text())['manifest_sha256']==sha(BASE/'execution-manifest-r1.json')})
    print(json.dumps({'files_sealed':len(files),'manifest_validation_passed':not failures,'report':str(BASE/'REPORT.md'),'complete':False},indent=2))
    if failures:raise SystemExit(1)


if __name__=='__main__':main()
