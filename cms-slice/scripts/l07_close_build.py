#!/usr/bin/env python3
"""Add dated pharmacy address/county evidence without changing any native row."""
from collections import Counter, defaultdict
import copy
import gzip
import hashlib
import json
from pathlib import Path
import re
import sqlite3

from l04_acquire import write
from l07_acquire import file_hash
from l07_close_extract import norm

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'docs/data/l07-pharmacy-networks-2026-10-27'
CLOSE = BASE / 'closeout-r1'
OUT = BASE / 'location-build-r4'
COUNTIES = {'12021':'Collier','12071':'Lee','12051':'Hendry','12087':'Monroe'}
PRIORITY_COUNTIES = {'12021','12071','12051','12015','12043','12087'}


def base_street(value):
    # Geography may be established at building level. Original units remain in
    # the registry record; this does not claim the directory corroborates them.
    value=re.split(r'\s+(?:(?:STE|SUITE|UNIT|APT|BLDG|FLOOR|ROOM|RM)\b|#)',value,flags=re.I)[0].upper()
    value=re.sub(r'\b(?:STATE ROAD|ST RD)\b','SR',value)
    value=re.sub(r'\b(\d+)(?:ST|ND|RD|TH)\b',r'\1',value)
    # A leading/trailing direction is a standard rendering difference. Retain
    # the direction as a token; never drop it to force an address match.
    words=value.split()
    direction={'N':'N','NORTH':'N','S':'S','SOUTH':'S','E':'E','EAST':'E','W':'W','WEST':'W'}
    if len(words)>2 and words[-1] in direction:
        words=[words[0],direction[words[-1]],*words[1:-1]]
    return norm(' '.join(words))


def county_proof(observation, index):
    return {'status':'Published_county','county_fips':observation['county_fips'],
            'basis':'Dated 2026 carrier directory county attribution; no coordinates or live-operation claim.',
            'source':observation['source'],'directory_observation_index':index,
            'directory_updated_date':observation['directory_updated_date']}


def main():
    if (CLOSE/'SEALED').exists():raise ValueError('Closeout evidence is sealed')
    OUT.mkdir()
    observations = json.loads((CLOSE/'directory-observations.json').read_text())
    by_npi = defaultdict(list)
    for i, x in enumerate(observations): by_npi[x['npi']].append((i,x))
    crosswalk_path = ROOT/'cms-slice/apps/ten-question/zip-counties.json'
    crosswalk = json.loads(crosswalk_path.read_text())['zips']
    records = [json.loads(line) for line in gzip.open(BASE/'location-build-r3/locations.jsonl.gz','rt')]
    sources = json.loads((CLOSE/'sources.json').read_text())
    gis_sources = json.loads((BASE/'geography-county-r3/requests.json').read_text())
    gis_updates = {}
    for address_id,label,field in [('4295c9409a2e7e3c9eb6','Hendry exact house 1951','FullAddres'),
                                    ('c7cb490b895aa83c63b2','Hendry exact house 1005','FullAddres'),
                                    ('a0b87db9e74fbc638610',None,'Full_Address')]:
        source = next(s for s in sources if s['label']==label) if label else next(s for s in gis_sources if s['address_id']==address_id)
        gis_updates[address_id] = (source,field)
    decisions, held, changes = [], [], []
    for row in records:
        old = copy.deepcopy(row)
        candidates = row['candidate_locations']
        eligible = []
        for index, x in by_npi[row['npi']]:
            if x['state']!='FL' or not x['county_fips'] or x['postal_code'][:5]!=row['network_zip']: continue
            # The older complete crosswalk is a contradiction screen only.
            # Its ratios never select a county or replace the directory header.
            zips = [row['network_zip']]
            for ci,c in enumerate(candidates):
                a = c['registry_address']
                if a['state']!='FL' or norm(a['city'])!=norm(x['city']) or base_street(a['address_1'])!=base_street(x['street']): continue
                if any(z in crosswalk and x['county_fips'] not in {v[0] for v in crosswalk[z]} for z in zips+[a['postal_code'][:5]]):
                    held.append({'npi':row['npi'],'observation_index':index,'reason':'Directory county contradicts existing ZIP/county possibility set'});continue
                g = c.get('geography') or {}
                if g.get('status')=='Match' and g.get('county_fips')!=x['county_fips']:
                    held.append({'npi':row['npi'],'observation_index':index,'reason':'Directory county contradicts existing geocoder/GIS result'});continue
                eligible.append((ci,index,x))
        selected = None
        if row['status']=='unique_zip_matched_location' and row['scope_group']=='Florida_county_unresolved':
            if eligible and len({(ci,x['county_fips']) for ci,i,x in eligible})==1:
                ci,index,x = eligible[0]; selected=(ci,index,x,'county_attribution_added')
        elif row['status']=='network_registry_zip_mismatch' and len(candidates)==1:
            # Exact full street/unit match is mandatory to link the published
            # CMS ZIP to the registry address in a ZIP-conflict case.
            exact = [(ci,i,x) for ci,i,x in eligible if norm(x['street'])==norm(candidates[ci]['registry_address']['address_1']+' '+candidates[ci]['registry_address']['address_2'])]
            if exact and len({(ci,x['county_fips'],x['street']) for ci,i,x in exact})==1:
                ci,index,x=exact[0];selected=(ci,index,x,'address_link_supported_ZIP_conflict_retained')
        if selected:
            ci,index,x,kind=selected;c=candidates[ci]
            proof=county_proof(x,index)
            if (c.get('geography') or {}).get('status')=='Match': proof=c['geography']
            if c['address_id'] in gis_updates:
                source,field=gis_updates[c['address_id']]
                native=json.loads((ROOT/source['path']).read_text())
                feature_indexes=[i for i,f in enumerate(native['features']) if base_street(f['attributes'][field])==base_street(c['registry_address']['address_1'])]
                if not feature_indexes: raise ValueError('Expected exact county street match absent')
                proof={'status':'Match','county_fips':x['county_fips'],'basis':'Official county address-point geography; units retained separately.',
                       'source':source,'feature_indexes':feature_indexes,'address_field':field}
            c['geography']=proof
            row['scope_group']=COUNTIES.get(x['county_fips'],'other_Florida_county');row['county_fips']=x['county_fips']
            row['location_resolution']={'kind':kind,'directory_observation_index':index,
                'directory_updated_date':x['directory_updated_date'],'selected_address_id':c['address_id'],
                'CMS_ZIP_preserved':row['network_zip'],'registry_ZIP_preserved':c['registry_address']['postal_code'],
                'county_evidence_level':'official_geographic_source' if proof['status']=='Match' else 'carrier_published_county',
                'exact_CMS_snapshot_address_continuity_established':False}
            decisions.append({'npi':row['npi'],'network_zip':row['network_zip'],**row['location_resolution'],'county_fips':row['county_fips']})
        if row['npi']=='1245279298' and row['status']=='identity_missing':
            xs=[(i,x) for i,x in by_npi[row['npi']] if x['postal_code'][:5]==row['network_zip'] and x['state']=='FL' and x['county_fips']=='12099']
            if len(xs)!=1: raise ValueError('Published identity case not unique')
            index,x=xs[0]
            a={'origin':'published_2026_carrier_directory','address_1':x['street'],'address_2':'','city':x['city'],
               'state':x['state'],'postal_code':x['postal_code'],'telephone_number':x['phone']}
            aid=hashlib.sha256(json.dumps(a,sort_keys=True).encode()).hexdigest()[:20]
            row['candidate_locations']=[{'address_id':aid,'directory_address':a,'geography':county_proof(x,index),'source_state':'Florida'}]
            row['published_identity']={'npi':row['npi'],'name':'PUBLIX PHARMACY #0050','source':x['source'],
                'page':x['page'],'column':x['column'],'registry_identity_still_unavailable':True}
            row['scope_group']='other_Florida_county';row['county_fips']='12099'
            row['location_resolution']={'kind':'published_directory_identity_added_registry_unavailable',
                'directory_observation_index':index,'directory_updated_date':x['directory_updated_date'],
                'selected_address_id':aid,'CMS_ZIP_preserved':row['network_zip'],
                'county_evidence_level':'carrier_published_county','exact_CMS_snapshot_address_continuity_established':False}
            decisions.append({'npi':row['npi'],'network_zip':row['network_zip'],**row['location_resolution'],'county_fips':row['county_fips']})
        if row!=old: changes.append({'npi':row['npi'],'network_zip':row['network_zip'],'before_scope':old['scope_group'],
            'after_scope':row['scope_group'],'kind':row['location_resolution']['kind']})
    write(CLOSE/'decisions.json',decisions);write(CLOSE/'held-directory-cases.json',held)
    write(CLOSE/'changes.json',changes)
    exceptions=[r for r in records if r['scope_group'] in ['identity_or_location_unresolved','Florida_county_unresolved']]
    with gzip.open(OUT/'locations.jsonl.gz','wt') as stream:
        for r in records: stream.write(json.dumps(r,sort_keys=True)+'\n')
    write(OUT/'exceptions.json',exceptions)
    con=sqlite3.connect(OUT/'inventory.sqlite3')
    con.execute('CREATE TABLE locations(npi TEXT,network_zip TEXT,identity_status TEXT,scope_group TEXT,county_fips TEXT,record_json TEXT,PRIMARY KEY(npi,network_zip))')
    con.executemany('INSERT INTO locations VALUES(?,?,?,?,?,?)',[(r['npi'],r['network_zip'],r['status'],r['scope_group'],r['county_fips'],json.dumps(r,sort_keys=True)) for r in records])
    con.execute('ATTACH DATABASE ? AS native',('file:'+str(BASE/'build-r1/inventory.sqlite3')+'?mode=ro',))
    plans=con.execute('SELECT n.offering_id,l.scope_group,COUNT(*) FROM native.network n JOIN locations l ON n.pharmacy_npi=l.npi AND n.PHARMACY_ZIPCODE=l.network_zip GROUP BY n.offering_id,l.scope_group').fetchall()
    write(OUT/'plan-location-coverage.json',[dict(zip(['offering_id','scope_group','network_rows'],r)) for r in plans])
    con.commit();con.close()
    nearby_cities={'NAPLES','IMMOKALEE','MARCO ISLAND','BONITA SPRINGS','ESTERO','FORT MYERS','FT MYERS','CAPE CORAL','LABELLE','CLEWISTON','LEHIGH ACRES','SANIBEL','FORT MYERS BEACH','BOKEELIA','SAINT JAMES CITY','ST JAMES CITY','MOORE HAVEN','PUNTA GORDA','PORT CHARLOTTE','BABCOCK RANCH'}
    nearby=[]
    old_exceptions={(r['npi'],r['network_zip']) for r in json.loads((BASE/'location-build-r3/exceptions.json').read_text())}
    for r in records:
        if (r['npi'],r['network_zip']) not in old_exceptions:continue
        near=(any(v[0] in PRIORITY_COUNTIES for v in crosswalk.get(r['network_zip'],[])) or
              r['network_zip'].startswith(('339','341')) or any(
              (c.get('registry_address') or c.get('directory_address'))['city'] in nearby_cities or
              any(v[0] in PRIORITY_COUNTIES for v in crosswalk.get((c.get('registry_address') or c.get('directory_address'))['postal_code'][:5],[])) or
              (c.get('geography') or {}).get('county_fips') in PRIORITY_COUNTIES for c in r['candidate_locations']))
        if near:nearby.append(r)
    write(CLOSE/'nearby-priority-cases.json',nearby)
    write(OUT/'Collier-pharmacies.json',json.loads((BASE/'location-build-r3/Collier-pharmacies.json').read_text()))
    coverage={'schema':'l07-location-coverage/2','network_NPI_zip_pairs':len(records),
        'scope_groups':dict(Counter(r['scope_group'] for r in records)),
        'native_identity_join_states_preserved':dict(Counter(r['status'] for r in records)),
        'additive_resolution_kinds':dict(Counter(r['location_resolution']['kind'] for r in records if 'location_resolution' in r)),
        'new_county_evidence_levels':dict(Counter(r['location_resolution']['county_evidence_level'] for r in records if 'location_resolution' in r)),
        'nearby_previous_exception_cases':len(nearby),'nearby_cases_remaining_unresolved':[r['npi'] for r in nearby if r['scope_group'] in ['identity_or_location_unresolved','Florida_county_unresolved']],
        'current_registry_identities':66118,'published_directory_only_identities':1,
        'remaining_without_any_published_identity':129,'source_masked_ZIP_NPIs':126,
        'full_physical_map_complete':False,'consumer_release_enabled':False,
        'limits':'Carrier county attribution is labeled separately from GIS/geocoding. ZIP conflicts and source dates remain visible. No live-operation, exact September-address continuity or personal-pricing claim.'}
    write(OUT/'coverage.json',coverage)
    inputs=[BASE/'build-r1/manifest.json',BASE/'identity-build-r1/manifest.json',BASE/'location-build-r3/manifest.json',
            CLOSE/'sources.json',CLOSE/'directory-observations.json',CLOSE/'decisions.json',CLOSE/'changes.json',CLOSE/'held-directory-cases.json',crosswalk_path]
    write(OUT/'manifest.json',{'schema':'l07-additive-location-build/2','parent':'location-build-r3',
        'input_sha256':{str(p.relative_to(ROOT)):file_hash(p) for p in inputs},
        'code_sha256':{str(Path(__file__).resolve().relative_to(ROOT)):file_hash(Path(__file__))},
        'files_sha256':{p.name:file_hash(p) for p in OUT.iterdir() if p.is_file()},'consumer_release_enabled':False,'human_acceptance':None})
    print(json.dumps(coverage,indent=2))


if __name__=='__main__':main()
