"""Prepare and seal the additive L08 r4 research reference after validation."""
import argparse,collections,gzip,json,sqlite3,subprocess,sys
from datetime import datetime,timezone
from l08_r4_common import ROOT,HOME,PARENT,BASE,write,filehash,assert_open

def prepare():
    assert_open();n=json.loads((BASE/'humana-normalization-summary.json').read_text());legacy=json.loads((BASE/'legacy-normalization-summary.json').read_text());v=json.loads((BASE/'validation.json').read_text())
    if not v['passed']:raise ValueError('Whole-population validation has not passed')
    db=sqlite3.connect('file:'+str(BASE/'providers.sqlite3')+'?mode=ro',uri=True)
    rows=json.loads((BASE/'legacy-unit-dispositions.json').read_text());groups={g['id']:g for g in json.loads((BASE/'legacy-shared-layouts.json').read_text())}
    r3=json.loads((PARENT/'published-shared-group-sites.json').read_text());old={i for g in r3 for i in g['parent_context_units']};local={'Naples','Marco Island','Immokalee','Ave Maria'}
    local_new=sum(bool(r['parent_record_id']not in old and r['shared_layout_id']and any(a['city_raw']in local for a in groups[r['shared_layout_id']]['shared_addresses']))for r in rows)
    local_humana=db.execute("SELECT count(*)FROM r4_address_entry_links l JOIN r3_address_observations a ON a.id=l.address_id WHERE json_extract(a.fields_json,'$.fields.county_context_raw')='COLLIER COUNTY'").fetchone()[0]
    # These are publisher-heading/city priorities, not independent geocoding.
    limits={'normalization_scope':'All 471,137 retained native modeled-column nodes in the six applicable Humana publications and all 2,660 prior exceptional PDF units.',
       'all_35220_Humana_addresses_have_bounded_source_entry':n['unassigned_addresses']==0,
       'Humana_name_type_unasserted_blocks':n['unclassified_published_name'],
       'Humana_listing_blocks_without_direct_or_inherited_site':n['no_explicit_site_in_bounded_entry'],
       'interpretation':'Source blocks repeat by document, specialty and site, and include pharmacy/supplemental listings. No unique-person denominator is claimed. Name kinds are conservative format classifications; raw source values remain authoritative. A shared practice link is a bounded layout association, not employment or a guarantee of personal participation. Unknown names/sites remain explicit.',
       'legacy_remaining_medical_or_group_source_limits':{k:c for k,c in legacy['state_counts'].items()if k in ['source_partial_site_retained; no_unique_full_site_in_this_unit','published_group_header; no_unique_bounded_site_proved','source_name_or_identifier_entry; no_unique_bounded_site_proved','source_context_fragment; no_unique_bounded_site_proved']},
       'requires_owner_to_find_new_PDF_for_every_fragment':False,
       'internal_semantic_review_remaining':'Ambiguous name types, exact person identity and some shared-site/condition scope cannot be promoted beyond their explicit evidence by the automated pass. These are internal interpretation/retained-source limits, not claims of a carrier partnership requirement.',
       'full_semantic_verification_claimed':False,'physical_county_verified_from_city_alone':False,
       'uninterrupted_full_year_participation_claimed':False,'personal_participation_verified':False}
    write(BASE/'modeled-field-limits.json',limits)
    write(BASE/'source-layout-QA.json',{'reviewed_native_source_pages':[
       {'source':'bootstrap-r3/render/humana-hmo-pcp-63.png','purpose':'Clinician/practice distinction, direct site priority, shared PCP# values, per-person age/established-patient conditions; visually inspected'},
       {'source':'normalization-r4/render/aetna-identified-group-29.png','purpose':'Group and person publisher IDs, shared source run continuing onto next page; visually inspected'},
       {'source':'normalization-r4/render/humana-continued-DME-365.png','purpose':'Multiple literal sites continue into next column; expanded-service and preferred-cost-sharing footer is not a heading; visually inspected'}],
       'visual_review_is_sampled':True,'whole_population_literal_comparison':'validation.json','no_inferred_unique_person_IDs':True})
    access={'inherited_source_stops_preserved':True,'no_stopped_host_retry_in_r4':True,
       'Wellcare_independent_download_site':{'url':'https://wellcareproviderdirectories.com/','result':'browser net::ERR_CERT_AUTHORITY_INVALID','warning_bypassed':False,'direct_PDF_link_verified':False},
       'Wellcare_member_portal':{'url':'https://my.wellcare.com','result':'Prior automatic approval review rejected public finder redirect even after guest-only owner approval; not retried in r4','account_accessed':False},
       'new_public_collection':'Two complete 2026 Humana guest hospital queries; no login or production client tokens used',
       'outreach_or_paid_feed_or_registration':False}
    write(BASE/'access-dispositions.json',access)
    gaps=json.loads((PARENT/'genuine-gaps.json').read_text())
    for g in gaps:
        if g['id']=='L08-G01':
            g['r4_progress']='Official 2026 directory-selection URL verified in all six retained exact-plan EOCs. Separate advertised download host has a certificate error. No direct PDF URL or medical roster was verified. Owner handoff is WELLCARE_DOWNLOADS.md.'
        elif g['id']=='L08-G02':
            g['r4_progress']='153 additional legacy shared-site unit associations recovered, including six with Collier-city sites. Aetna clinical domain classification corrected for 595 exceptional records. Public all-specialty/all-site census still unproved.'
        elif g['id']=='L08-G03':
            g['r4_progress']='Every retained Humana address now has a bounded full-name entry association. Full native bodies, printed PCP# suffixes and qualifiers retained. Added 246 public hospital observations in two complete seven-page network queries. Fourteen PPO offerings each reference multiple networks, so the new guest queries are held from exact-plan hospital-matrix joins.'
            g['blocked_by']='Published PDFs expressly partial; exact guest PPO-network applicability remains ambiguous. Automated internal normalization is complete for its stated fields; residual source/semantic limits are explicitly enumerated in modeled-field-limits.json.'
    gaps.append({'id':'L08-I01','kind':'internal_interpretation_and_source_layout_limits','status':'explicit_held_dispositions; not_a_partnership_block',
       'gap':'Some named entries have no uniquely established person type/site, and some old source fragments lack a complete or uniquely associated address.',
       'need':'Use the retained native layouts and exact identifiers for targeted interpretation where consequential. A correctly scoped exact-plan public detail/export can add missing facts; do not request a new PDF for each ambiguous fragment or infer a missing site.',
       'scope':'modeled-field-limits.json and legacy-unit-dispositions.json',
       'why':'Literal extraction completeness is separate from semantic identity and exact plan/site participation.'})
    write(BASE/'genuine-gaps.json',gaps)
    h=json.loads((PARENT/'hospital-coverage-summary.json').read_text());q=json.loads((BASE/'public-query-accounting.json').read_text())
    write(BASE/'summary.json',{'reference_id':'L08-PUBLISHED-COLLIER-2026-research-r4','Humana':n,'legacy':legacy,
       'new_shared_site_units_with_Collier_city':local_new,'parent_Humana_Collier_heading_addresses_retained':local_humana,
       'new_public_network_query_observations':sum(x['observations']for x in q),'public_query_pages':sum(x['pages']for x in q),
       'prior_hospital_matrix_unchanged':h,'modeled_literal_validation_passed':v['passed'],
       'full_L08_complete':False,'human_accepted':False,'consumer_release_enabled':False})
    report=f'''# L08 normalization and public-source follow-up

October 27, 2026. This revision makes the retained network evidence more usable and adds two complete public hospital queries. **Full L08 remains incomplete.** All 72 pinned 2026 Collier MA offerings remain visible; no personal participation or recommendation is activated.

## What changed

- **Every one of the 35,220 retained Humana address observations now has a bounded source-entry association.** The pass accounts for all **471,137 native text nodes** in the modeled columns of the six applicable publications. It separates credentialed name formats, practice/organization names, specialty headings and explicitly unclassified names. It retains whole entry bodies, printed PCP# suffixes, age limits, established-patient statements, dates and other source qualifications. These are repeated source observations across publications and sections, including pharmacy/supplemental entries—not unique doctor counts.
- **2,069 prior address/name candidates now have a different, complete bounded name.** Corrected cases include wrapped names and footer legends that interrupted continued entries. The old candidates remain unchanged in the parent reference.
- **153 more legacy units have an explicit shared-site layout association**, including **{local_new} with Collier-city sites**. There are now **393 such units across 241 source layouts**, including the 240 units retained from r3. Another **15 direct sites** were recovered from native lines, including cities followed by superscript source symbols. Those 15 are outside Collier and are retained as regional evidence. Numeric Aetna IDs no longer cause **595 exceptional clinical-section records** to be treated as nonmedical by default.
- **246 new public hospital observations:** Medicare PPO and Humana Honor PPO each returned **123 results across seven pages**, with Florida/Collier origin, year 2026 and 100-mile radius retained. Every page and modeled field was checked. Repeated name/site rows remain visible; some have different source specialties or phones. Five records per query publish no street, so a “serves Collier” label is not treated as a physical Collier location.

[Research database](providers.sqlite3), [validation](validation.json), [normalization accounting](humana-normalization-accounting.json), [legacy dispositions](legacy-unit-dispositions.json), [public query accounting](public-query-accounting.json).

## What the normalization does and does not establish

The source supplies **{n['entries']:,} bounded blocks**, including **{n['published_specialty_heading']:,} specialty headings**. A practice name and the clinicians listed after it stay separate. A printed PCP# can be shared by several people and is never converted into an NPI or unique person ID. A clinician's own printed site takes priority; a later distinct site ends inheritance of an earlier practice site.

Some published entries still lack uniquely supportable identity or site semantics. **{n['unclassified_published_name']:,} repeated name blocks retain an unasserted person/organization type. {n['no_explicit_site_in_bounded_entry']:,} blocks have no direct or conservatively inherited site in that bounded entry**; many are addressless service listings or clinicians in complex group layouts. Those counts are not unique doctors and are not automatically missing external PDFs. Full bodies and source locations remain available for targeted interpretation.

All **2,660 prior exceptional PDF units** have a disposition. After the recoveries, the remaining medical/group source limits are **53 partial-site units, 82 group headers, 115 name/identifier entries and 25 context fragments** without a uniquely established full site in the supported layout. Another 1,977 are nonmedical identifier context, not missing L08 clinician records. [Modeled limits](modeled-field-limits.json) distinguish these internal/source-layout limits from actual source-access gaps. Complete semantic verification of every clinical relationship is not claimed.

## Why the new PPO observations stay separate from exact-plan claims

The retained InsurancePlan data attach several distinct named PPO networks to **all fourteen PPO offerings**. That reference list alone does not disambiguate which selected guest network applies to each exact offering. The new hospital query facts remain useful as published **2026 named-network evidence**, but this revision adds **zero exact-plan hospital-matrix claims** from that ambiguous join. [Exact crosswalk hold](PPO-network-crosswalk-hold.json).

The prior hospital matrix stays unchanged: **{h['positive_published_cells']} of 1,224 cells** have published positive evidence, including **{h['Collier_positive_published_cells']} of 504 Collier cells**. Unknown remains unknown, never “out of network.”

## Wellcare downloads for the owner

All six retained exact-plan EOCs print the official [2026 Provider Directories route](https://go.wellcare.com/2026providerdirectories). **I could not verify direct PDF download URLs.** This is a selection route, with exact plan IDs and instructions in [WELLCARE_DOWNLOADS.md](WELLCARE_DOWNLOADS.md). Choose Florida, 2026 and Collier, then the applicable medical Provider Directory or combined Provider and Pharmacy Directory. One shared document can cover multiple plans when its applicability says so. Save original files in `/Users/cep4u/daylight/plans`.

The six targets are **H1032-198, -199, -202, -239, -241 and -243**. A pharmacy-only or Medicaid-only directory will not supply the missing MA medical network. The existing EOCs and benefit tables do not enumerate those doctors and hospitals.

The independently advertised [directory-documents site](https://wellcareproviderdirectories.com/) produced a certificate error. The public finder previously redirected to a member-portal origin that automatic approval review rejected despite guest-only owner approval. No security warning was bypassed, portal retried or account accessed. [Access record](access-dispositions.json), [53 exact retained EOC route spans](wellcare-download-handoff.json).

## Genuine remaining collection gaps

| Area | Missing facts | What can fill them |
|---|---|---|
| Wellcare, six offerings | Applicable 2026 Collier medical rosters and exact plan/provider/site relationships. | Original official directory files from the 2026 route, or a permitted public export. Owner download checklist above. |
| UHC / Erickson | Exact network-code interpretation and complete applicable local records; existing Erickson publications are partial. | Corrected authoritative crosswalks or permitted dated exact-plan directories/exports. Existing host stops and pagination failures remain recorded. |
| Florida Blue | Exact 2026 CMS-offering-to-source-network crosswalk; existing public facts are current plan-family observations. | Dated exact-plan mapping or exact-plan directory/export. Public guest access itself works. |
| Original Medicare | Applicable clinician/enrollment/assignment/opt-out snapshots and federal facility identifiers. | Dated official CMS files/dictionaries through a permitted download or supplied originals; the inherited CMS data-host stop remains. |
| Aetna / Humana breadth | All-specialty, all-site county coverage is not proved by partial PDFs or bounded searches; new PPO network/plan mapping is held. | Further permitted public specialty/site collection, exact-plan detail or a complete applicable local export, plus a supported PPO network crosswalk. |

These are not established paid-feed or partnership requirements. Historical uninterrupted participation and live appointment availability are outside this dated published-reference claim. SELECT remains conditional on exact L10 product evidence. [Full gap register](genuine-gaps.json).

## Validation and preservation

Whole-population validation passed with **zero unexplained modeled-value mismatches**. It rehashed **{v['counts']['sealed_parent_files_rehashed']:,} sealed parent files**, compared **{v['counts']['unchanged_parent_rows_compared']:,} unchanged parent database rows**, and checked every new name/body/context/condition, printed ID, address ownership, bounded shared-site relationship, legacy recovery, public source span, query total and database/export row. The four initial legacy city-check failures were wrapped city/ZIP locator omissions; both source lines are now retained and checked.

Native source pages were visually inspected for practice/person layout, continuation across columns/pages and footer handling. The detailed [source QA](source-layout-QA.json) distinguishes sampled visual review from whole-population literal validation. Regression results are in [test-results.json](test-results.json).

This is an additive D64/D73 research revision. Parent r1–r3 sources, code and data remain sealed. No unrelated app, other-layer acceptance, consumer UI, personal guarantee, recommendation, ranking or deployment is changed. Assignment is not source acceptance.
'''
    (BASE/'REPORT.md').write_text(report)
    (BASE/'README.md').write_text('# L08 normalization r4\n\nRead [results and remaining gaps](REPORT.md), [validation](validation.json), [Wellcare download instructions](WELLCARE_DOWNLOADS.md) and [database](providers.sqlite3). Full L08 is incomplete; this research revision is unaccepted and consumer release remains disabled. Earlier revisions remain sealed.\n')
    write(BASE/'authorization.json',{'owner_request':'Great, keep going on L08. Finish the internal normalization using what we have, continue collecting from public sources, and validate it all. Give me direct download links for any Wellcare files you need me to get.',
        'scope':'Published 2026 Collier provider network research; reuse retained documents; no personal participation or consumer release',
        'previous_terms_approval_preserved':'Florida Blue terms; not needed by this revision','previous_guest_only_approval_preserved':'Wellcare guest directory; no member account access or retry after rejection'})
    db.close()
    command=[sys.executable,'-m','unittest','discover','-s','cms-slice/tests','-p','test_l08_r4_reference.py','-v']
    test=subprocess.run(command,cwd=ROOT,text=True,capture_output=True)
    (BASE/'test-report.txt').write_text(test.stdout+test.stderr)
    write(BASE/'test-results.json',{'passed':test.returncode==0,'exit_code':test.returncode,'command':command,'report':'test-report.txt'})
    if test.returncode:raise ValueError('Regression tests failed')
    print(json.dumps({'prepared':True,'validation_passed':True,'tests_passed':True,'new_Collier_city_shared_units':local_new}))

def publish():
    assert_open()
    for p in ['validation.json','test-results.json']:
        if not json.loads((BASE/p).read_text())['passed']:raise ValueError('Failed check '+p)
    for p in ['REPORT.md','WELLCARE_DOWNLOADS.md','genuine-gaps.json','modeled-field-limits.json','source-layout-QA.json']:
        if not(BASE/p).exists():raise ValueError('Missing deliverable '+p)
    (BASE/'SEALED').write_text('L08 additive normalization/public research r4 sealed\n')
    (BASE/'acquisition/SEALED').write_text('Public acquisition sealed; inherited access stops preserved\n')
    paths=[p for p in BASE.rglob('*')if p.is_file()and p.name not in ['manifest.json','manifest-validation.json']]
    paths+=list((ROOT/'cms-slice/scripts').glob('l08_r4_*.py'))+[ROOT/'cms-slice/tests/test_l08_r4_reference.py']
    files={str(p.relative_to(ROOT)):{'sha256':filehash(p),'bytes':p.stat().st_size}for p in sorted(set(paths))}
    m={'reference_id':'L08-PUBLISHED-COLLIER-2026-research-r4','created_at_utc':datetime.now(timezone.utc).isoformat(),
       'files':files,'parent_manifest_sha256':filehash(PARENT/'manifest.json'),'full_L08_complete':False,'human_accepted':False,'consumer_release_enabled':False}
    write(BASE/'manifest.json',m)
    errors=[rel for rel,meta in files.items()if(ROOT/rel).stat().st_size!=meta['bytes']or filehash(ROOT/rel)!=meta['sha256']]
    if errors:raise ValueError('Manifest mismatch '+str(errors))
    current={'reference_id':m['reference_id'],'kind':'incomplete_research_reference','manifest':'normalization-r4/manifest.json',
       'manifest_sha256':filehash(BASE/'manifest.json'),'database':'normalization-r4/providers.sqlite3','report':'normalization-r4/REPORT.md',
       'parent_reference_id':'L08-PUBLISHED-COLLIER-2026-research-r3','consumer_release_enabled':False,'comprehensive_layer_complete':False,'human_accepted':False}
    write(HOME/'CURRENT_REFERENCE.json',current)
    write(BASE/'manifest-validation.json',{'passed':True,'files_rehashed':len(files),'errors':[],
        'active_reference_manifest_sha256_agrees':filehash(BASE/'manifest.json')==current['manifest_sha256']})
    print(json.dumps({'sealed':True,'files':len(files),'reference':m['reference_id']}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--publish',action='store_true');a=p.parse_args()
    if a.publish:publish()
    else:prepare()
