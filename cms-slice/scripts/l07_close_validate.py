#!/usr/bin/env python3
"""Independently audit new L07 PDF/GIS matches and preservation of all parents."""
from collections import Counter, defaultdict
import copy
import gzip
import hashlib
import json
from pathlib import Path
import re
import sqlite3

import pdfplumber
from pypdf import PdfReader

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'docs/data/l07-pharmacy-networks-2026-10-27'
CLOSE=BASE/'closeout-r1'
PACKAGE=BASE/'location-build-r4'


def sha(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def key(text):
    abbreviations={'AVENUE':'AVE','BOULEVARD':'BLVD','COURT':'CT','CIRCLE':'CIR','ROAD':'RD',
        'DRIVE':'DR','HIGHWAY':'HWY','LANE':'LN','PARKWAY':'PKWY','PLAZA':'PLZ','STREET':'ST',
        'TRAIL':'TRL','SUITE':'STE','TERRACE':'TER','BYPASS':'BYP','ROOM':'RM',
        'SAINT':'ST','FORT':'FT','HARBOUR':'HARBOR','NORTH':'N','SOUTH':'S','EAST':'E','WEST':'W',
        'NORTHEAST':'NE','NORTHWEST':'NW','SOUTHEAST':'SE','SOUTHWEST':'SW'}
    text=text.upper()
    for a,b in abbreviations.items():text=re.sub(r'\b'+a+r'\b',b,text)
    return re.sub('[^A-Z0-9]','',text)


def street(text):
    text=re.split(r'\s+(?:(?:STE|SUITE|UNIT|APT|BLDG|FLOOR|ROOM|RM)\b|#)',text,flags=re.I)[0].upper()
    text=re.sub(r'\b(?:STATE ROAD|ST RD)\b','SR',text)
    text=re.sub(r'\b(\d+)(?:ST|ND|RD|TH)\b',r'\1',text)
    tokens=text.split();directions={'N':'N','NORTH':'N','S':'S','SOUTH':'S','E':'E','EAST':'E','W':'W','WEST':'W'}
    if len(tokens)>2 and tokens[-1] in directions:tokens=[tokens[0],directions[tokens[-1]],*tokens[1:-1]]
    return key(' '.join(tokens))


def plain(text):return re.sub('[^A-Z0-9]','',text.upper())


def require(condition,message):
    if not condition:raise ValueError(message)


def audit():
    checks={};source_fields=0
    manifest=json.loads((PACKAGE/'manifest.json').read_text())
    for group in ['input_sha256','code_sha256']:
        for p,h in manifest[group].items():require(sha(ROOT/p)==h,'Changed bound input/code '+p)
    for p,h in manifest['files_sha256'].items():require(sha(PACKAGE/p)==h,'Changed output '+p)
    parent_manifest=json.loads((BASE/'location-build-r3/manifest.json').read_text())
    for p,h in parent_manifest['files_sha256'].items():require(sha(BASE/'location-build-r3'/p)==h,'Changed parent output')
    baseline=json.loads((CLOSE/'baseline.json').read_text())
    archived_selection=BASE/'closeout-r1/previous-selection.json'
    for p,h in baseline.items():
        # CURRENT_REFERENCE is the sole intentionally mutable selection pointer.
        # Its exact previous contents remain bound in the additive closeout.
        if p==str((BASE/'CURRENT_REFERENCE.json').relative_to(ROOT)):
            require(sha(archived_selection)==h,'Previous selection not preserved')
        else:require(sha(ROOT/p)==h,'Changed preserved baseline '+p)
    checks['all_bound_inputs_outputs_code_and_baseline_evidence_preserved']=True
    sources=json.loads((CLOSE/'sources.json').read_text())
    for s in sources:require(sha(ROOT/s['path'])==s['sha256'],'Changed public response')
    source=next(s for s in sources if s['label']=='2026 Florida AmeriHealth pharmacy directory')
    codes=next(s for s in sources if s['label']=='Census official county FIPS reference')
    fips={}
    for line in (ROOT/codes['path']).read_text().splitlines()[1:]:
        v=line.split('|')
        if v[0]=='FL':fips[plain(v[4])]=v[1]+v[2]
    observations=json.loads((CLOSE/'directory-observations.json').read_text())
    by_page=defaultdict(list)
    for i,r in enumerate(observations):by_page[r['page']].append((i,r))
    with pdfplumber.open(ROOT/source['path']) as pdf:
        require(len(pdf.pages)==985,'Unexpected directory edition/page count')
        # The cover has a visible dated text overlay above an old placeholder.
        # Pypdf retains the two text objects separately, unlike line sorting.
        require('09-21-2026' in PdfReader(ROOT/source['path']).pages[0].extract_text(),'Printed update date absent')
        for page_number, rows in sorted(by_page.items()):
            page=pdf.pages[page_number-1]
            for index,r in rows:
                require(r['source']==source and r['directory_updated_date']=='2026-09-21','Wrong source/date binding')
                require(r['document_plan']=='H6378-001','Wrong source document label')
                col=r['column'];left=[0,210,405][col-1];right=[210,405,612][col-1]
                lines=[r['npi_line'],*r['street_lines'],r['city_line']]
                if r['phone_line']:lines.append(r['phone_line'])
                if r['county_header']:
                    h=r['county_header']
                    if h['page']==page_number:lines.append(h)
                for line in lines:
                    box=line['bbox'];crop=(max(0,box[0]-1),max(0,box[1]-3),min(page.width,box[2]+1),min(page.height,box[3]+3))
                    found=page.crop(crop).extract_text(x_tolerance=1.5,y_tolerance=2) or ''
                    require(plain(line['text']) in plain(found),'PDF literal differs at observation '+str(index)+': '+line['text']+' / '+found)
                    source_fields+=1
                require(re.fullmatch(r'NPI:\s*'+r['npi'],r['npi_line']['text']) is not None,'Wrong NPI literal')
                require(all(left<=v['bbox'][0]<right for v in [r['npi_line'],*r['street_lines'],r['city_line']]),'Column leakage')
                block=page.crop((left,max(0,r['npi_line']['bbox'][1]-2),right,min(page.height,r['city_line']['bbox'][3]+2))).extract_text() or ''
                ids=re.findall(r'NPI:\s*(\d{10})',block)
                require(ids==[r['npi']],'Address block contains another NPI')
                require(r['street']==' '.join(v['text'] for v in r['street_lines']),'Street field changed')
                require(r['city_line']['text']==r['city']+', '+r['state']+' '+r['postal_code'],'City/state/ZIP field changed')
                require(r['phone']==(r['phone_line']['text'] if r['phone_line'] else None),'Phone field changed')
                h=r['county_header']
                expected=fips.get(plain(h['county_label'])) if h and h['state']=='FL' and h['page']==page_number else None
                require(r['county_fips']==expected,'County FIPS does not follow source heading')
                if expected:
                    require(h['column']<col or h['column']==col and h['bbox'][1]<r['npi_line']['bbox'][1],'County heading follows entry')
                source_fields+=7
            page.flush_cache()
            if page_number%50==0:print('PDF checked through page',page_number,flush=True)
        # The one new published-only name is checked separately, because the
        # general extractor deliberately does not model organization names.
        text=pdf.pages[604].crop((210,70,405,724)).extract_text() or ''
        require('PUBLIXPHARMACY0050' in plain(text),'New identity name absent')
    checks['all_extracted_NPI_address_phone_county_observations_checked_against_independent_PDF_text_positions']=True
    previous={(r['npi'],r['network_zip']):r for r in map(json.loads,gzip.open(BASE/'location-build-r3/locations.jsonl.gz','rt'))}
    current={(r['npi'],r['network_zip']):r for r in map(json.loads,gzip.open(PACKAGE/'locations.jsonl.gz','rt'))}
    decisions=json.loads((CLOSE/'decisions.json').read_text());d={(r['npi'],r['network_zip']):r for r in decisions}
    require(len(d)==len(decisions),'Duplicate closeout resolution')
    require(set(previous)==set(current) and len(current)==66248,'NPI/ZIP relationship lost or added')
    zipmap=json.loads((ROOT/'cms-slice/apps/ten-question/zip-counties.json').read_text())['zips']
    county_labels={'12021':'Collier','12071':'Lee','12051':'Hendry','12087':'Monroe'}
    gis_checks=0
    con=sqlite3.connect('file:'+str(PACKAGE/'inventory.sqlite3')+'?mode=ro',uri=True)
    for pair,row in current.items():
        old=previous[pair]
        if pair not in d:require(row==old,'Unapproved row modification '+str(pair))
        else:
            dec=d[pair];obs=observations[dec['directory_observation_index']]
            require(obs['npi']==pair[0] and obs['postal_code'][:5]==pair[1] and obs['county_fips']==dec['county_fips'],'Incorrect exact published identifier join')
            allowed={'scope_group','county_fips','candidate_locations','location_resolution','published_identity'}
            require({k:v for k,v in row.items() if k not in allowed}=={k:v for k,v in old.items() if k not in allowed},'Native identity/provenance/status altered')
            require({k:v for k,v in dec.items() if k not in ['npi','network_zip','county_fips']}==row['location_resolution'],'Decision/record differ')
            require(row['scope_group']==county_labels.get(dec['county_fips'],'other_Florida_county') and row['county_fips']==dec['county_fips'],'Unsupported scope group')
            require(pair[1] in zipmap and dec['county_fips'] in {v[0] for v in zipmap[pair[1]]},'Directory county conflicts with native ZIP possibility set')
            require(not dec['exact_CMS_snapshot_address_continuity_established'],'Unsupported historical continuity claim')
            candidate=next(c for c in row['candidate_locations'] if c['address_id']==dec['selected_address_id'])
            if old['status']=='identity_missing':
                require(pair==('1245279298','33405') and row['published_identity']['registry_identity_still_unavailable'],'Unsupported missing-identity promotion')
                a=candidate['directory_address']
                require(a=={'origin':'published_2026_carrier_directory','address_1':obs['street'],'address_2':'','city':obs['city'],'state':obs['state'],'postal_code':obs['postal_code'],'telephone_number':obs['phone']},'Directory-only address differs')
                require(row['identity_source'] is None and row['status']=='identity_missing','Registry gap concealed')
            else:
                require(len(row['candidate_locations'])==len(old['candidate_locations'])==1,'Ambiguous multi-location case promoted')
                a=candidate['registry_address'];b=old['candidate_locations'][0]
                require({k:v for k,v in candidate.items() if k!='geography'}=={k:v for k,v in b.items() if k!='geography'},'Original candidate/address/unit changed')
                require(a['state']==obs['state']=='FL' and key(a['city'])==key(obs['city']) and street(a['address_1'])==street(obs['street']),'Street/city/state join differs')
                require(dec['county_fips'] in {v[0] for v in zipmap.get(a['postal_code'][:5],[])},'Registry ZIP/county contradiction')
                if old['status']=='network_registry_zip_mismatch':
                    require(key(a['address_1']+' '+a['address_2'])==key(obs['street']),'ZIP conflict lacks exact full street/unit match')
                    require(dec['registry_ZIP_preserved']==a['postal_code'] and dec['CMS_ZIP_preserved']==pair[1],'ZIP conflict overwritten')
                else:require(old['status']=='unique_zip_matched_location' and old['scope_group']=='Florida_county_unresolved','Unexpected resolution class')
                prior=b.get('geography') or {}
                require(prior.get('status')!='Match' or prior.get('county_fips')==dec['county_fips'],'Existing geography contradiction hidden')
            g=candidate['geography'];require(g['county_fips']==dec['county_fips'],'Geography county differs')
            if g['status']=='Published_county':
                require(g=={'status':'Published_county','county_fips':obs['county_fips'],
                    'basis':'Dated 2026 carrier directory county attribution; no coordinates or live-operation claim.',
                    'source':source,'directory_observation_index':dec['directory_observation_index'],'directory_updated_date':'2026-09-21'},'Unsupported carrier geographic fields')
                require('coordinates' not in g and dec['county_evidence_level']=='carrier_published_county','Unverified coordinates added')
            elif old['candidate_locations'] and g==old['candidate_locations'][0].get('geography'):
                require(dec['county_evidence_level']=='official_geographic_source','Prior GIS evidence relabeled')
            else:
                require(g['status']=='Match' and sha(ROOT/g['source']['path'])==g['source']['sha256'],'County source changed')
                features=json.loads((ROOT/g['source']['path']).read_text())['features']
                require(g['source']['requested_url'].startswith(('https://services7.arcgis.com/8l7Qq5t0CPLAJwJK/','https://services2.arcgis.com/LvWGAAhHwbCJ2GMP/')),'Unsupported county source')
                for index in g['feature_indexes']:
                    attrs=features[index]['attributes'];require(attrs['County']=={'12051':'HENDRY COUNTY','12071':'LEE COUNTY'}[dec['county_fips']],'County GIS field differs')
                    require(street(attrs[g['address_field']])==street(a['address_1']),'Wrong county address point')
                    source_fields+=len(attrs);gis_checks+=1
        stored=con.execute('SELECT record_json FROM locations WHERE npi=? AND network_zip=?',pair).fetchone()
        require(stored and json.loads(stored[0])==row,'Database/export differ')
    require(len(current)==con.execute('SELECT COUNT(*) FROM locations').fetchone()[0],'Extra database row')
    con.execute('ATTACH DATABASE ? AS native',('file:'+str(BASE/'build-r1/inventory.sqlite3')+'?mode=ro',))
    rows=con.execute('SELECT n.offering_id,l.scope_group,COUNT(*) FROM native.network n JOIN locations l ON n.pharmacy_npi=l.npi AND n.PHARMACY_ZIPCODE=l.network_zip GROUP BY n.offering_id,l.scope_group').fetchall()
    require(json.loads((PACKAGE/'plan-location-coverage.json').read_text())==[dict(zip(['offering_id','scope_group','network_rows'],r)) for r in rows],'Per-plan counts differ')
    require(sum(r[2] for r in rows)==4054335 and len({r[0] for r in rows})==71,'Plan/native network denominator changed')
    con.close()
    exceptions=[r for r in current.values() if r['scope_group'] in ['identity_or_location_unresolved','Florida_county_unresolved']]
    require(exceptions==json.loads((PACKAGE/'exceptions.json').read_text()),'Exceptions incomplete')
    require(json.loads((PACKAGE/'Collier-pharmacies.json').read_text())==json.loads((BASE/'location-build-r3/Collier-pharmacies.json').read_text()),'Collier inventory changed')
    require({r['npi'] for r in current.values() if r['scope_group']=='Collier'}=={r['npi'] for r in previous.values() if r['scope_group']=='Collier'},'Collier pharmacy lost')
    coverage=json.loads((PACKAGE/'coverage.json').read_text())
    require(coverage['scope_groups']==dict(Counter(r['scope_group'] for r in current.values())),'Coverage counts differ')
    require(coverage['additive_resolution_kinds']==dict(Counter(r['kind'] for r in decisions)),'Resolution counts differ')
    require(not coverage['consumer_release_enabled'] and not coverage['full_physical_map_complete'],'Scope/hold weakened')
    held=json.loads((CLOSE/'held-directory-cases.json').read_text())
    require({r['npi'] for r in held}=={'1255107496','1699154161'} and not ({r['npi'] for r in held}&{r['npi'] for r in decisions}),'Source contradictions promoted')
    nearby=json.loads((CLOSE/'nearby-priority-cases.json').read_text())
    require(all(r==current[(r['npi'],r['network_zip'])] for r in nearby),'Nearby case export differs')
    unresolved=[r['npi'] for r in nearby if r['scope_group'] in ['identity_or_location_unresolved','Florida_county_unresolved']]
    require(unresolved==coverage['nearby_cases_remaining_unresolved'],'Nearby unresolved list differs')
    health=next(s for s in sources if s['label'].startswith('Lee Health current'))
    require('1285263780' not in (ROOT/health['path']).read_text(),'HealthPark page now supplies identifier; reconsider hold')
    distinction=json.loads((CLOSE/'HealthPark-identity-distinction.json').read_text())
    ids={r['npi']:r for r in distinction['identities']}
    require(set(ids)=={'1285263780','1427893932'},'HealthPark identities omitted')
    for line in gzip.open(BASE/'identity-build-r1/identities.jsonl.gz','rt'):
        item=json.loads(line)
        if item['npi'] in ids:require(item==ids[item['npi']],'HealthPark identity differs from validated registry source')
    require('2393435100' in re.sub(r'\D','',(ROOT/health['path']).read_text()),'Public retail phone absent')
    native=sqlite3.connect('file:'+str(BASE/'build-r1/inventory.sqlite3')+'?mode=ro',uri=True)
    for npi in ids:
        values=native.execute('SELECT source_part,source_ordinal,offering_id,PHARMACY_ZIPCODE,retail_status,mail_status FROM network WHERE pharmacy_npi=?',(npi,)).fetchall()
        require(distinction['native_network_records'][npi]==[dict(zip(['source_part','source_ordinal','offering_id','published_ZIP','retail_status','mail_status'],r)) for r in values],'HealthPark native plan evidence differs')
    native.close()
    require(len(distinction['native_network_records']['1427893932'])==71 and len(distinction['native_network_records']['1285263780'])==7,'HealthPark plan counts differ')
    require(distinction['no_substitution'],'HealthPark source identities conflated')
    checks.update({'all_new_modeled_fields_source_checked':True,'all_66248_relationships_and_database_records_checked':True,
        'all_native_join_states_units_source_ZIPs_and_conflicts_preserved':True,
        'all_71_plan_rollups_sum_to_4054335_original_network_rows':True,
        'all_90_Collier_records_preserved':True,'unresolved_and_multi_location_cases_retained':True,
        'contradictory_directory_counties_held':True,'carrier_counties_separate_from_GIS_and_coordinates':True,
        'registry_missing_state_retained_for_directory_only_identity':True,
        'HealthPark_retail_and_hospital_identifiers_kept_distinct':True,'no_consumer_release_or_pricing_added':True})
    result={'schema':'l07-additive-closeout-validation/1','passed':True,'checks':checks,
        'new_resolutions_checked':len(decisions),'directory_observations_checked':len(observations),
        'source_field_observations_checked':source_fields,'additional_GIS_feature_checks':gis_checks,
        'all_NPI_ZIP_pairs_checked':len(current),'remaining_location_exceptions':len(exceptions),
        'nearby_previous_exceptions':len(nearby),'nearby_remaining_unresolved':unresolved,
        'unexplained_field_mismatches':0,'preserved_baseline_files':len(baseline),
        'manifest_sha256':sha(PACKAGE/'manifest.json'),'validator_sha256':sha(Path(__file__)),
        'limits':'Published directory address/county evidence is dated September 21, 2026; the CMS network snapshot remains September 16. No exact-date continuity or live-operation inference.'}
    (CLOSE/'validation.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':audit()
