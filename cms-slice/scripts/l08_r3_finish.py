"""Prepare and seal the additive, incomplete L08 public bootstrap reference."""
import argparse,json,sqlite3,gzip
from collections import Counter
from datetime import datetime,timezone
from l08_r3_common import BASE,PARENT,ROOT,write,digest,assert_open
from l08_r3_validate import filehash

def prepare():
    assert_open();summary=json.loads((BASE/'summary.json').read_text());validation=json.loads((BASE/'validation.json').read_text())
    if not validation['passed']:raise ValueError('Validation must pass')
    invs=json.loads((BASE/'humana-document-inventory.json').read_text());groups=json.loads((BASE/'internal-association-summary.json').read_text())
    db=sqlite3.connect('file:'+str(BASE/'providers.sqlite3')+'?mode=ro',uri=True)
    coverage=json.loads((PARENT/'followup-r2/plan-source-coverage.json').read_text())
    bindings=json.loads((BASE/'humana-plan-document-bindings.json').read_text())
    queries=json.loads((BASE/'aetna-mentalhealth-query-accounting.json').read_text())
    for p in coverage:
        p['normalization_revision']='bootstrap-r3'
        added=[b for b in bindings if b['offering_id']==p['offering_id']]
        p['r3_published_directory_bindings']=added
        p['r3_bounded_mentalhealth_queries']=[q for q in queries if q['offering_id']==p['offering_id']]
        p['published_directory_acquired']=p['published_directory_acquired']or bool(added)
        p['full_provider_location_roster_completeness_established']=False
        p['current_supported_hospital_cells']=db.execute("SELECT COUNT(*)FROM hospital_plan_matrix WHERE offering_id=?AND state LIKE 'published%'",(p['offering_id'],)).fetchone()[0]
    write(BASE/'plan-source-coverage.json',coverage)
    gaps=json.loads((PARENT/'followup-r2/genuine-gaps.json').read_text())
    for g in gaps:
        if g['id']=='L08-G01':
            g.update(status='open; public_guest_route_tool_approval_block',
                blocked_by='Existing API/host stops remain. A separately advertised public finder redirected to my.wellcare.com; automatic approval review refused observation even after owner approved guest-only inspection. No member account accessed.',
                need='An applicable 2026 H1032 medical directory/export through a permitted public route, original official files supplied by the owner, or source/tool access resolution. A commercial partnership has not been shown necessary.')
        elif g['id']=='L08-G02':
            g.update(status='partially_closed; all_five_local_hospital_matrices_supported; public_specialty_collection_remains',
                gap='All 35 Collier hospital-campus/plan combinations are now positively listed. Added all 570 observations across five fully captured mental-health facility queries, supplementing the r2 hospital/PCP queries. All-specialty/all-site coverage remains unproved.',
                blocked_by='No blanket public guest-access block. More permitted category, geographic and site collection remains internal acquisition work.',
                need='Continue public specialty/site enumeration or acquire an applicable dated complete local export. A query total proves that query, not the entire network.')
        elif g['id']=='L08-G03':
            g.update(status='directory_acquisition_gap_closed_for_all_22; complete_network_universe_not_established',
                gap='Six applicable 2026 published regional directories now explicitly account for all 22 Humana offerings. All 3,400 pages are retained/indexed; source addresses and conditions are modeled. Public 2026 FL Medicare HMO hospital query is fully captured and joined to its eight exact plan network references.',
                blocked_by='The PDFs explicitly call themselves partial lists. The stopped API still has unresolved broader identities. Full person/practice/site interpretation of newly retained material is internal work.',
                need='Further permitted public directory collection for omitted local providers/sites, and internal semantic association where needed. Do not require a whole-US export merely to support a stated Collier listing, or present a partial publication as an exhaustive absence test.')
        elif g['id']=='L08-G04':
            g['r3_progress']='Official UHC provider site routes guest medical search to findcare.guest.uhc.com, within the inherited source stop. The stopped host was not followed. No commercial dependency established.'
        elif g['id']=='L08-G05':
            g.update(status='working_public_family_directory; exact_2026_crosswalk_still_held',
                blocked_by='Guest directory is accessible after explicitly approved terms; this is not a public access denial. Retained five Classic hospital results and NCH accepted-family details, but the guest display supplies no exact CMS plan ID or explicit benefit year.',
                need='Official evidence linking exact 2026 CMS offerings to the applicable source network codes, or a dated exact-plan directory/export. Continue permitted public collection; do not silently convert current plan-family observations into 2026 exact-plan claims.')
        elif g['id']=='L08-G06':
            g['r3_progress']='Official public catalogs still identify CMS downloads on the stopped data.cms.gov host. No permitted independent official payload was acquired; no proxy or stopped-host retry was used. These are public federal-file gaps, not a carrier partnership requirement.'
        elif g['id']=='L08-G08':
            g.update(status='scope_boundary; no_uninterrupted_full_year_history_claim',
                need='No additional history is required merely to retain these actual dated published observations. An earlier or full-year historical assertion would require its own dated evidence.')
        elif g['id']=='L08-G09':
            g.update(status='closed; current_Axiom_exact_HMO_listing_and_identity_found',blocked_by=None,
                gap='Axiom Behavioral Health at Naples, 9001 Tamiami Trl E, is explicitly In Network for H1609-027 in the 2026 mental-health facility query. Current publisher provider ID 2341726 and NPI 1235024357 differ from the older Willough record used by the failed detail lookup.',
                need='No further source is needed for this published exact-plan campus observation. Original failed lookup and old entity remain retained; no old-entity termination inferred.')
        elif g['id']=='L08-G10':
            g.update(status='closed; exact_NPI_Tampa_location_resolved; publisher_city_error_retained',blocked_by=None,
                gap='NPI 1619487246 identifies The Right Spinal Clinic Inc. Official registry street/suite, Tampa ZIP and phone agree with the clinic website. The source Naples city is an error for this Tampa site.',
                need='No additional source is required to identify this location and exclude the erroneous Naples string as physical Collier proof. Original source values remain unchanged.')
    write(BASE/'genuine-gaps.json',gaps)
    field_counts=Counter();by_section={}
    for line in gzip.open(BASE/'humana-address-observations.jsonl.gz','rt'):
        r=json.loads(line);f=r['fields'];field_counts['address_observations']+=1
        for k in ['name_candidate_raw','street_raw','phone_raw']:
            if not f[k]:field_counts['unmodeled_'+k]+=1;by_section.setdefault(f['section_raw'],Counter())['unmodeled_'+k]+=1
    limits=dict(field_counts,by_section={k:dict(v)for k,v in by_section.items()},
      interpretation='Address/name candidates are literal source observations. A candidate name can be a practice/group; complete person-versus-practice semantics remains internal work. Unmodeled pharmacy phones are outside this medical-provider collection and do not establish a new L08 source gap.')
    write(BASE/'modeled-field-limits.json',limits)
    nonstandard_source=BASE/'humana-partial-street-observations.json'
    if not nonstandard_source.exists():nonstandard_source=BASE/'humana-nonstandard-source-addresses.json'
    nonstandard=json.loads(nonstandard_source.read_text())
    native_rows={}
    for line in gzip.open(BASE/'humana-address-observations.jsonl.gz','rt'):
        r=json.loads(line)
        if r['id']in{x['id']for x in nonstandard}:native_rows[r['id']]=r
    for x in nonstandard:
        x['resolved_street_raw']=native_rows[x['id']]['fields']['street_raw']
        x['state']='nonstandard_source_format_retained_verbatim; no invented spacing or spelling'
    write(BASE/'humana-nonstandard-source-addresses.json',nonstandard)
    if(BASE/'humana-partial-street-observations.json').exists():(BASE/'humana-partial-street-observations.json').unlink()
    total=db.execute("SELECT COUNT(*)FROM hospital_plan_matrix WHERE state LIKE 'published%'").fetchone()[0]
    collier=db.execute("SELECT COUNT(*)FROM hospital_plan_matrix m JOIN hospitals h ON h.id=m.hospital_id WHERE h.county='Collier'AND m.state LIKE 'published%'").fetchone()[0]
    write(BASE/'hospital-coverage-summary.json',{'total_cells':1224,'positive_published_cells':total,'unknown_cells':1224-total,'Collier_total_cells':504,'Collier_positive_published_cells':collier,'Collier_unknown_cells':504-collier,'unknown_is_not_out_of_network':True})
    rows=[]
    for x in invs:
        if not x['collier_geography_explicit']:continue
        rows.append('| '+x['label'].replace('Community Health Medicare PPO-CareComplete Platinum HMO C SNP-','Community PPO / CareComplete - ')+' | '+str(x['pages'])+' | '+x['publication_date_raw']+' | [Official PDF]('+x['requested_url']+') |')
    report=f'''# L08 public network bootstrap results

October 27, 2026. More of the 2026 Collier network map is now supported by public evidence. **Full L08 remains incomplete.** This revision closes two specific source conflicts, acquires applicable Humana directories for all 22 target offerings, and completes another set of Aetna facility queries. All 72 pinned MA offerings remain visible.

## What is now supported

- **Humana:** six applicable published 2026 directories, **3,400 pages**, explicitly list all **22 target offerings**. The source material now supplies **35,220 address observations**, including regional repeats and supplemental/pharmacy sections; these are not 35,220 unique doctors. All source pages, exact plan mentions, county context and raw conditions are retained. Each publication expressly calls itself a partial list.
- **Aetna:** **570 additional facility observations across 30 pages**, with the full published query totals reconciled for all five formerly missing plans. This adds to r2's primary-care and hospital queries. The previously missing H1609-027 behavioral-health campus is now positively listed, bringing those five plans to **35 of 35 Collier hospital-campus/plan combinations**.
- **Hospitals:** **206 additional hospital/plan combinations** now have published evidence, including **119 in Collier**. The census remains 17 campuses across Collier, Lee and Hendry, each checked against all 72 offerings. There are now **{total} positive published cells of 1,224**, including **{collier} of 504 Collier cells**. Unknown cells never mean out of network.
- **Existing documents:** **240 parent context units** are linked to explicit shared name-block/site layouts, including **33 with Collier-city addresses**. These are source layout associations, without invented NPIs or a claim that every employee of a group participates everywhere.
- **Tampa address conflict:** exact NPI 1619487246, official registry and the clinic website resolve The Right Spinal Clinic's location to Tampa. The original Humana Naples city value remains visible as a publisher error; this site no longer supplies physical Collier proof.

[Research database](providers.sqlite3), [all 72 offerings](plan-source-coverage.json), [validation](validation.json), [genuine gaps](genuine-gaps.json), [hospital additions](newly-supported-hospital-cells.json).

## Published Humana directories

The official public Find Care tool was set to Florida and **2026**, and its actual advertised links were retained in [the directory index](ui/humana-2026-directory-links.json). Twelve PDFs totaling 5,408 pages were downloaded. Six other regional editions are preserved but excluded from Collier directory applicability: a plan's broader service area mentioning Collier does not make its other-region provider list a Collier directory.

| Advertised edition | Pages | Printed update | Source |
|---|---:|---|---|
{chr(10).join(rows)}

[Exact plan/document bindings](humana-plan-document-bindings.json) retain contract, plan and segment source spans. Every applicable edition is explicitly partial; absence from it is not an exclusion. The full text is indexed in SQLite, including unmodeled text and source qualifications.

The public guest hospital query independently selected **FL Medicare HMO, 2026, 100 miles from the selected Collier County centroid**. All 50 results across three pages were captured. Its eight exact-plan connections use the pinned InsurancePlan resources' explicit reference to that same named medical network; they do not infer a network from a similar plan-family name. [Network bindings](humana-named-network-bindings.json), [query accounting](humana-public-hospital-accounting.json).

## Aetna hospital gap resolved

The H1609-027 mental-health facility query explicitly lists **Axiom Behavioral Health at Naples, 9001 Tamiami Trl E, Naples 34113, In Network**. Current publisher ID **2341726** and NPI **1235024357** identify a different directory entity from the older Willough record (publisher ID 6200930, NPI 1932138823) used by the failed direct lookup. Official NPI registry identity/address and the retained AHCA campus agree. The old failed lookup does not establish an exclusion or termination.

Each of the four PPO facility searches returned 117 listings; the HMO returned 102. All six pages of each query were retained and compared. The observations include mental-health, substance-use, outpatient and general hospital source categories. They are not a complete all-specialty provider roster. [Queries](aetna-mentalhealth-query-accounting.json), [source observations](aetna-mentalhealth-observations.json), [Axiom identity](axiom-current-identity.json).

## Remaining work and real limits

| Area | What remains | What can fill it |
|---|---|---|
| Wellcare six offerings | Applicable 2026 MA medical rosters are still uncollected. The advertised finder redirects to a member-portal origin that automatic approval review refused, including after guest-only owner approval. | A permitted public exact-plan directory/export, original official files supplied locally, or resolution of that source/tool access block. A paid partnership has not been established as necessary. |
| UHC and Erickson | Exact network-code interpretation and incomplete source pagination remain. Erickson's retained PDFs are real partial publications. The newly checked official provider-site link leads into the inherited stopped uhc.com host. | A permitted dated exact-plan directory, supported network-code explanation, corrected export or source access resolution. |
| Florida Blue five offerings | Public guest search works after approved terms. Five Classic hospital results and NCH accepted-family details are retained, but the display supplies neither an exact CMS plan ID nor explicit benefit year. | Exact 2026 plan/network mapping or dated plan-specific directory evidence. Current family listings stay separate from exact 2026 claims. |
| Original Medicare | The applicable federal clinician, enrollment, assignment, opt-out and hospital identifier snapshots remain uncollected after the inherited CMS data-host stop. | Official dated CMS files/dictionaries through a permitted download or supplied originals. These are public federal data, not a carrier partnership issue. |
| Humana and Aetna completeness | Humana now has applicable public reference documents for all 22 plans, but those are expressly partial. Aetna's captured specialty/radius queries do not cover all doctors, specialties, locations or county geography. | Continue permitted public category/site collection and reconcile overlaps and omissions against exact plan identities. A complete local published export would help; no whole-US export is required to support an individual Collier listing. |
| Internal interpretation | Some original source-only/partial records remain. Newly retained candidate names can be a practice/group as well as a clinician; full person/practice/site interpretation, source-native specialties and county geocoding are not finished. | Additional internal normalization using held evidence first. Do not describe this work as needing a partnership or make the owner find another PDF by default. |

The new address pass retains all conventional and nonstandard printed streets, including alphanumeric house numbers and run-on strings. The remaining 707 unmodeled phone values belong to pharmacy-section observations; complete source text remains available and L07 is unchanged. [Modeled field limits](modeled-field-limits.json), [nonstandard source addresses](humana-nonstandard-source-addresses.json), [shared group sites](published-shared-group-sites.json).

Uninterrupted participation throughout 2026 and live appointment availability are not claims of this dated published reference. Medicare SELECT remains an exact-product dependency on L10 when applicable. These boundaries are not extra collection requirements for the actual dated observations retained here.

## Validation and preservation

[Whole-population validation](validation.json) passed with **zero unexplained modeled-value mismatches**. It compared all **5,408 new PDF pages**, **599,129 native XML nodes**, each modeled address/name-candidate/phone/condition and exact plan source span, all **625 new public observations**, bounded query totals, shared source group layouts, exact registry identities, campus joins and SQLite/export parity. It also rehashed **4,603 sealed parent files** and compared **1,457,474 unchanged parent rows**. Hospital evidence additions preserve each parent's exact evidence prefix.

Eleven regression tests cover real failures: confusing plan service area with directory geography; clipped column-bottom phones; numbered streets; alphanumeric and run-on source addresses; Golisano versus pagination controls; current Axiom versus the older Willough entity; the Tampa/Naples conflict; shared group versus individual identity; year/plan ambiguity; hospital versus co-located clinician; and research/release boundaries.

This is a reproducible research reference under D64/D73. No personalized participation, ranking, recommendation, consumer UI/deployment or inherited acceptance is added. The accepted references and source stops remain unchanged. The [r2 reference](../followup-r2/REPORT.md) and all earlier sources/code remain sealed.
'''
    (BASE/'REPORT.md').write_text(report)
    (BASE/'README.md').write_text('# L08 public network bootstrap\n\nPublished 2026 Collier and nearby provider-directory research, October 27, 2026. Full L08 remains incomplete.\n\nRead [results and remaining gaps](REPORT.md), [validation](validation.json), [all 72 offerings](plan-source-coverage.json), and [research database](providers.sqlite3).\n\nThe parent r2 reference is preserved. Changes to this revision after sealing require a new additive revision. No personal participation guarantee or consumer release is enabled.\n')
    db.close()

def publish():
    assert_open()
    if not json.loads((BASE/'validation.json').read_text())['passed']:raise ValueError('Validation failed')
    for name in ['REPORT.md','genuine-gaps.json','test-results.json']:
        if not(BASE/name).exists():raise ValueError('Missing deliverable '+name)
    if not json.loads((BASE/'test-results.json').read_text())['passed']:raise ValueError('Tests failed')
    (BASE/'SEALED').write_text('L08 public research bootstrap r3 sealed\n')
    (BASE/'acquisition/SEALED').write_text('Public acquisition sealed; all inherited source stops preserved\n')
    paths=[p for p in BASE.rglob('*')if p.is_file()and p.name not in ['manifest.json','manifest-validation.json']]
    paths+=list((ROOT/'cms-slice/scripts').glob('l08_r3_*.py'))+[ROOT/'cms-slice/tests/test_l08_r3_reference.py']
    files={str(p.relative_to(ROOT)):{'sha256':filehash(p),'bytes':p.stat().st_size}for p in sorted(set(paths))}
    manifest={'reference_id':'L08-PUBLISHED-COLLIER-2026-research-r3','created_at_utc':datetime.now(timezone.utc).isoformat(),
      'files':files,'parent_manifest_sha256':filehash(PARENT/'followup-r2/manifest.json'),
      'full_L08_complete':False,'human_accepted':False,'consumer_release_enabled':False}
    write(BASE/'manifest.json',manifest)
    current={'reference_id':manifest['reference_id'],'kind':'incomplete_research_reference','manifest':'bootstrap-r3/manifest.json',
      'manifest_sha256':filehash(BASE/'manifest.json'),'database':'bootstrap-r3/providers.sqlite3','report':'bootstrap-r3/REPORT.md',
      'parent_reference_id':'L08-PUBLISHED-COLLIER-2026-research-r2','consumer_release_enabled':False,'comprehensive_layer_complete':False,'human_accepted':False}
    write(PARENT/'CURRENT_REFERENCE.json',current)
    errors=[rel for rel,meta in files.items()if not(ROOT/rel).exists()or(ROOT/rel).stat().st_size!=meta['bytes']or filehash(ROOT/rel)!=meta['sha256']]
    write(BASE/'manifest-validation.json',{'passed':not errors,'files_rehashed':len(files),'errors':errors,'active_reference_manifest_sha256_agrees':filehash(BASE/'manifest.json')==current['manifest_sha256']})
    print(json.dumps({'sealed':not errors,'files':len(files),'active_reference':current['reference_id']}))
    if errors:raise SystemExit(1)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--publish',action='store_true');a=p.parse_args()
    if a.publish:publish()
    else:prepare()
