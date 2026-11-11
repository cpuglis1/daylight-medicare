#!/usr/bin/env python3
"""Build an additive research provider reference with explicit unsupported joins."""
from collections import Counter, defaultdict
import gzip
import json
from pathlib import Path
import re
import sqlite3
from urllib.parse import urlparse
from l08_acquire import BASE, OUT, ROOT, digest, write

BUILD=BASE/'build-r1'
TYPES={'InsurancePlan','Organization','Practitioner','PractitionerRole','Location','OrganizationAffiliation','HealthcareService'}
FIELDS={'resourceType','id','identifier','active','status','name','alias','type','gender','address','telecom',
        'communication','qualification','period','meta','extension','practitioner','organization','location',
        'network','code','specialty','healthcareService','availableTime','notAvailable','availabilityExceptions',
        'coverageArea','ownedBy','administeredBy','plan','participatingOrganization','position','partOf'}


def canonical(x):return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':'))
def key(host,typ,id):return host+'/'+typ+'/'+id
def refkey(host,ref):
    bits=ref.rstrip('/').split('/')
    namespace=urlparse(ref).hostname or host
    return key(namespace,bits[-2],bits[-1]) if len(bits)>1 else None
def leaves(x):
    if isinstance(x,dict):return sum(leaves(v)for v in x.values())
    if isinstance(x,list):return sum(leaves(v)for v in x)
    return 1
def npi(x):return [i['value']for i in x.get('identifier',[])if 'us-npi'in i.get('system','')and i.get('value')]
def networks(x):return x.get('network',[])+[e['valueReference']for e in x.get('extension',[])if e.get('url','').endswith('/network-reference')and 'valueReference'in e]


def exact_offering_ids(x):
    """Use actual identifiers and period, never the search URL or display name."""
    if not str(x.get('period',{}).get('start','')).startswith('2026'):
        return set()
    ids=set()
    for v in x.get('identifier',[]):
        value=v.get('value','');m=re.fullmatch(r'([HR]\d{4})-(\d{3})-(\d{3})-(2026)',value)
        if m:ids.add(':'.join([m[4],m[1],m[2],m[3]]))
        m=re.fullmatch(r'([HR]\d{4})(\d{3})(\d{3})',value)
        if m:ids.add('2026:'+':'.join(m.groups()))
    return ids


def main():
    BUILD.mkdir(exist_ok=True)
    dbpath=BUILD/'providers.sqlite3'
    if dbpath.exists():dbpath.unlink() # This build is unsealed until validation succeeds.
    db=sqlite3.connect(dbpath)
    db.executescript('''
      PRAGMA journal_mode=OFF; PRAGMA synchronous=OFF;
      CREATE TABLE sources(id TEXT PRIMARY KEY,url TEXT,sha256 TEXT,path TEXT,retrieved TEXT);
      CREATE TABLE observations(id TEXT PRIMARY KEY,entity_key TEXT,type TEXT,source_id TEXT,pointer TEXT,fields_json TEXT,native_json TEXT,modeled_leaf_count INTEGER);
      CREATE TABLE entities(entity_key TEXT PRIMARY KEY,type TEXT,observation_id TEXT,npi_json TEXT,name_json TEXT,status_json TEXT,period_json TEXT);
      CREATE TABLE locations(entity_key TEXT PRIMARY KEY,observation_id TEXT,name_json TEXT,address_json TEXT,telecom_json TEXT,position_json TEXT);
      CREATE TABLE roles(entity_key TEXT PRIMARY KEY,observation_id TEXT,provider_key TEXT,organization_key TEXT,locations_json TEXT,networks_json TEXT,specialty_json TEXT,period_json TEXT,qualifiers_json TEXT);
      CREATE TABLE offerings(id TEXT PRIMARY KEY,name TEXT,parent TEXT,category TEXT,drug TEXT,native_json TEXT);
      CREATE TABLE plan_networks(offering_id TEXT,network_key TEXT,plan_observation TEXT,reference_json TEXT,resolved_network_observation TEXT,state TEXT,reason TEXT);
      CREATE TABLE relationships(offering_id TEXT,role_key TEXT,role_observation TEXT,provider_key TEXT,location_key TEXT,network_key TEXT,state TEXT,reason TEXT);
      CREATE TABLE hospitals(id TEXT PRIMARY KEY,county TEXT,name TEXT,source_id TEXT,source_pointer TEXT,fields_json TEXT,addresses_json TEXT);
      CREATE TABLE hospital_plan_matrix(hospital_id TEXT,offering_id TEXT,state TEXT,evidence_json TEXT,PRIMARY KEY(hospital_id,offering_id));
    ''')
    seen={};latest={};occurrences=Counter();field_count=0;source_count=0;invalid=[]
    receipts=sorted([json.loads(f.read_text())for f in(OUT/'receipts').glob('*.json')],key=lambda r:(r.get('retrieved_at_utc',''),r['id']))
    with gzip.open(BUILD/'resources.jsonl.gz','wt')as export:
        for r in receipts:
            if r.get('http_status')!=200 or not r.get('path'):continue
            host=urlparse(r.get('requested_url','')).hostname
            if host not in {'fhir.humana.com','flex.optum.com','apigw.bcbsfl.com'}:continue
            raw=(ROOT/r['path']).read_bytes()
            if digest(raw)!=r['sha256']:raise ValueError('Source hash mismatch '+r['id'])
            try:j=json.loads(raw)
            except (ValueError,UnicodeDecodeError):
                invalid.append({'source_id':r['id'],'reason':'Non-JSON response; not provider data','bytes':r['bytes']});continue
            if j.get('resourceType')=='Bundle':items=[(e['resource'],'/entry/'+str(i)+'/resource')for i,e in enumerate(j.get('entry',[]))]
            else:items=[(j,'')]
            if not any(x.get('resourceType')in TYPES for x,_ in items):continue
            db.execute('INSERT OR IGNORE INTO sources VALUES(?,?,?,?,?)',(r['id'],r['requested_url'],r['sha256'],r['path'],r['retrieved_at_utc']));source_count+=1
            for x,pointer in items:
                typ=x.get('resourceType')
                if typ not in TYPES:continue
                ek=key(host,typ,x['id']);fields={k:v for k,v in x.items()if k in FIELDS};nat=canonical(x)
                oid=digest((ek+'\n'+nat).encode());occurrences[typ]+=1
                if oid not in seen:
                    fields_count=leaves(fields);field_count+=fields_count
                    row={'id':oid,'entity_key':ek,'type':typ,'source_id':r['id'],'pointer':pointer,'fields':fields,'native':x,'modeled_leaf_count':fields_count}
                    db.execute('INSERT INTO observations VALUES(?,?,?,?,?,?,?,?)',(oid,ek,typ,r['id'],pointer,canonical(fields),nat,fields_count));export.write(canonical(row)+'\n');seen[oid]=True
                latest[ek]={'id':oid,'native':x,'source_id':r['id'],'retrieved_at_utc':r['retrieved_at_utc']}
        for ek,o in latest.items():
            x=o['native'];typ=x['resourceType'];status={k:x[k]for k in['status','active']if k in x}
            db.execute('INSERT INTO entities VALUES(?,?,?,?,?,?,?)',(ek,typ,o['id'],canonical(npi(x)),canonical(x.get('name')),canonical(status),canonical(x.get('period'))))
            if typ=='Location':db.execute('INSERT INTO locations VALUES(?,?,?,?,?,?)',(ek,o['id'],canonical(x.get('name')),canonical(x.get('address')),canonical(x.get('telecom')),canonical(x.get('position'))))
            if typ in ['PractitionerRole','OrganizationAffiliation']:
                host=ek.split('/')[0];locs=[refkey(host,l['reference'])for l in x.get('location',[])if l.get('reference')];nets=[refkey(host,n['reference'])for n in networks(x)if n.get('reference')]
                qualifiers={k:x[k]for k in['extension','active','code','availableTime','notAvailable','availabilityExceptions','identifier','telecom']if k in x}
                provider=x.get('practitioner',{})if typ=='PractitionerRole'else x.get('participatingOrganization',x.get('organization',{}))
                db.execute('INSERT INTO roles VALUES(?,?,?,?,?,?,?,?,?)',(ek,o['id'],refkey(host,provider.get('reference','')),refkey(host,x.get('organization',{}).get('reference','')),canonical(locs),canonical(nets),canonical(x.get('specialty')),canonical(x.get('period')),canonical(qualifiers)))
    plans=json.loads((BASE/'plan-source-matrix.json').read_text());planids={p['id']for p in plans}
    for p in plans:db.execute('INSERT INTO offerings VALUES(?,?,?,?,?,?)',(p['id'],p['name'],p['parent'],p['category'],p['drug'],canonical(p)))
    netjoins=[]
    for ek,o in latest.items():
        x=o['native']
        if x['resourceType']!='InsurancePlan':continue
        host=ek.split('/')[0];candidates=exact_offering_ids(x)&planids
        product_candidate=host=='apigw.bcbsfl.com'
        if product_candidate:
            norm=lambda t:re.sub('[^a-z0-9]','',t.casefold())
            candidates={p['id']for p in plans if norm(p['name'])==norm(x.get('name',''))}
        for pid in sorted(candidates):
            for n in x.get('network',[]):
                nk=refkey(host,n.get('reference',''));target=latest.get(nk);state='held_medical_network_semantics';reason='Medical-network meaning is not established by this source reference alone'
                display=n.get('display','');target_name=target['native'].get('name','')if target else''
                if any(v in display.lower()for v in['rx','pharmac','dental','careington','vision','long term','infusion']):state='excluded_nonmedical_network';reason='Publisher labels this as a nonmedical/supplemental network'
                elif product_candidate:
                    state='held_product_to_CMS_crosswalk';reason='Source identifies the 2026 product family; exact CMS contract/plan/segment crosswalk is absent'
                elif host=='fhir.humana.com' and target and str(display).strip().lower()not in ['','n/a','unknown']and any(c.get('code')=='ntwk'for t in target['native'].get('type',[])for c in t.get('coding',[])):
                    state='source_medical_network_reference';reason='Exact 2026 plan ID and publisher network reference/type retained; relationship history not inferred'
                elif target and display and display.casefold()!=str(target_name).casefold():state='held_reference_name_conflict';reason='Plan reference display and resolved Organization name differ'
                if not str(x.get('period',{}).get('start','')).startswith('2026'):state='held_plan_period';reason='Actual source period not 2026'
                values=(pid,nk,o['id'],canonical(n),target['id']if target else None,state,reason)
                netjoins.append(values)
    # Deduplicate repeated publisher network references without deleting native duplicates.
    netjoins=list(dict.fromkeys(netjoins));db.executemany('INSERT INTO plan_networks VALUES(?,?,?,?,?,?,?)',netjoins)
    bynet=defaultdict(list)
    for row in netjoins:
        if row[5]!='excluded_nonmedical_network':bynet[row[1]].append(row)
    relationships=[];unresolved=Counter();rolekeys=set()
    for ek,o in latest.items():
        x=o['native'];host=ek.split('/')[0]
        if x['resourceType']not in ['PractitionerRole','OrganizationAffiliation']:continue
        provider=x.get('practitioner',{})if x['resourceType']=='PractitionerRole'else x.get('participatingOrganization',x.get('organization',{}))
        rolekeys.add(ek);pk=refkey(host,provider.get('reference',''));locs=[refkey(host,l['reference'])for l in x.get('location',[])if l.get('reference')]
        for rk in [pk]+locs:
            if rk and rk not in latest:unresolved[rk.split('/')[-2]]+=1
        for nk in {refkey(host,n['reference'])for n in networks(x)if n.get('reference')}:
            for p in bynet.get(nk,[]):
                for lk in locs or[None]:
                    state='source_listed_observation'if p[5]=='source_medical_network_reference'else'held_network_join'
                    reason=p[6]
                    if not pk or pk not in latest or lk not in latest:state='held_unresolved_entity_or_location';reason='Exact referenced practitioner or location not returned/resolved'
                    if x.get('active')is False:state='source_inactive_role';reason='Publisher marks this role inactive'
                    relationships.append((p[0],ek,o['id'],pk,lk,nk,state,reason))
    db.executemany('INSERT INTO relationships VALUES(?,?,?,?,?,?,?,?)',relationships)
    profiles=json.loads((BASE/'reuse-r1/ahca-profile-payloads.json').read_text());hospitalrows=[]
    for obs in profiles:
        groups={g[0]['LABEL']:g[1:]for g in obs['payload']};d=groups['FacilityDetails'][0];addresses=groups.get('AddressResults',[])
        fields={k:d.get(k)for k in['LicenseID','LicenseNumber','FileNumber','Name','Owner','FacilityType','County','LicenseStatus','FacilityIsClosed','LicenseEffectiveDate','LicenseExpirationDate','OriginalLicenseDate','ClosedDate','WebAddress']}
        hid='AHCA:'+d['LicenseID'];db.execute('INSERT INTO hospitals VALUES(?,?,?,?,?,?,?)',(hid,d.get('County'),d['Name'],obs['receipt'],'profilelist/FacilityDetails/1',canonical(fields),canonical(addresses)))
        hospitalrows.append({'id':hid,**fields,'addresses':addresses,'source_id':obs['receipt']})
        for p in plans:db.execute('INSERT INTO hospital_plan_matrix VALUES(?,?,?,?)',(hid,p['id'],'unknown_no_exact_campus_plan_evidence','[]'))
    db.executescript('CREATE INDEX obs_entity ON observations(entity_key); CREATE INDEX role_plan ON relationships(offering_id); CREATE INDEX role_identity ON relationships(role_key);')
    db.commit();integrity=db.execute('PRAGMA integrity_check').fetchone()[0]
    counts={t:db.execute('SELECT count(*)FROM '+t).fetchone()[0]for t in['sources','observations','entities','locations','roles','offerings','plan_networks','relationships','hospitals','hospital_plan_matrix']}
    states=dict(db.execute('SELECT state,count(*)FROM relationships GROUP BY state'))
    summary={'scope':'published 2026 Collier research reference; incomplete','counts':counts,'resource_occurrences':dict(occurrences),
             'modeled_leaf_observations':field_count,'relationship_states':states,'unresolved_role_reference_occurrences':dict(unresolved),
             'hospital_counties':dict(Counter(h['County']for h in hospitalrows)), 'sqlite_integrity':integrity,
             'consumer_release_enabled':False,'human_acceptance_inherited':False,'comprehensive_provider_map_complete':False}
    write(BUILD/'summary.json',summary);write(BUILD/'hospital-reference.json',hospitalrows);write(BUILD/'nonprovider-payloads.json',invalid)
    # SQLite is the complete machine-readable normalized export. Portable JSONL
    # carries every modeled observation and the complete native FHIR object.
    db.close();print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
