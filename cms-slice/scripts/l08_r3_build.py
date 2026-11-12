"""Build additive L08 bootstrap r3 while preserving every parent source row."""
import gzip,json,re,sqlite3
from collections import Counter,defaultdict
from l08_r3_common import BASE,PARENT,ROOT,write,digest,assert_open

def packed(x):return json.dumps(x,ensure_ascii=False,sort_keys=True)
def norm(s):return re.sub(r'[^a-z0-9]','',s.lower())

# Explicit campus aliases, checked against the retained AHCA campus and source
# name/address. Street matching alone never makes a clinician a hospital.
ALIASES={
 'AHCA:9841':['Naples Community Hospital','Naples Community Hospital Inc'],
 'AHCA:10147':['North Collier Hospital','North Naples Hospital'],
 'AHCA:10162':['Physicians Regional Medical Center Pine Ridge','Physicians Regional Medical Center (Pine Ridge)'],
 'AHCA:178823':['Physicians Regional Medical Center Collier','Physicians Regional Medical Center (Collier)'],
 'AHCA:489522':['Physicians Regional Medical Center North'],
 'AHCA:10107':['The Willough At Naples','Axiom Behavioral Health at Naples'],
 'AHCA:458386':['Encompass Health Rehabilitation Hospital of Naples LLC','Encompass Health Rehabilitation Hospital of Naples'],
 'AHCA:10146':['Health Park Medical Center','Healthpark Medical Center'],
 'AHCA:317825':['Select Specialty Hospital - Fort Meyers Inc','Select Specialty Hospital - Fort Myers Inc'],
 'AHCA:455304':['Encompass Health Rehab Hospital of Cape Coral LLC'],
 'AHCA:514411':['Encompass Health Rehabilitation Hospital of Fort Myers LLC'],
}

def match_campus(name,street,city,postal,hospitals):
    if not(name and street and city and postal):return []
    found=[]
    for h in hospitals:
        if norm(name)not in{norm(n)for n in [h['name']]+ALIASES.get(h['id'],[])}:continue
        for a in h['addresses']:
            if a['AddressType']!='ST':continue
            if norm(street)==norm(a['Address'])and norm(city)==norm(a['City'])and postal[:5]==a['Zip'][:5]:found.append(h['id'])
    return sorted(set(found))

def main():
    assert_open();dest=BASE/'providers.sqlite3'
    if dest.exists():dest.unlink()
    parent=sqlite3.connect('file:'+str(PARENT/'followup-r2/providers.sqlite3')+'?mode=ro',uri=True)
    db=sqlite3.connect(dest);parent.backup(db);parent.close()
    db.executescript('''
      CREATE TABLE r3_address_observations(id TEXT PRIMARY KEY,document_sha256 TEXT,page INTEGER,fields_json TEXT);
      CREATE TABLE r3_plan_directory_bindings(offering_id TEXT,document_sha256 TEXT,fields_json TEXT,PRIMARY KEY(offering_id,document_sha256));
      CREATE TABLE r3_shared_group_sites(id TEXT PRIMARY KEY,fields_json TEXT);
      CREATE TABLE r3_public_observations(id TEXT PRIMARY KEY,family TEXT,offering_id TEXT,source_path TEXT,fields_json TEXT);
      CREATE TABLE r3_public_query_accounting(id INTEGER PRIMARY KEY,family TEXT,fields_json TEXT);
      CREATE TABLE r3_identity_resolutions(id TEXT PRIMARY KEY,fields_json TEXT);
      CREATE TABLE r3_named_network_bindings(offering_id TEXT,fields_json TEXT);
      CREATE TABLE r3_hospital_evidence(hospital_id TEXT,offering_id TEXT,source_observation TEXT,fields_json TEXT);
    ''')
    inventory=json.loads((BASE/'humana-document-inventory.json').read_text())
    for rp in(BASE/'acquisition/receipts').glob('*.json'):
        r=json.loads(rp.read_text())
        if r.get('http_status')==200:
            db.execute('INSERT INTO sources VALUES(?,?,?,?,?)',('r3:'+r['id'],r['requested_url'],r['sha256'],r['path'],r['retrieved_at_utc']))
    for inv in inventory:
        inv['text_sha256']=digest((ROOT/inv['text_path']).read_bytes())
        db.execute('INSERT INTO directory_documents VALUES(?,?,?,?,?,?)',(inv['sha256'],inv['label'],2026,inv['publication_date_raw'],inv['pages'],packed(inv)))
        pages=(ROOT/inv['text_path']).read_text().split('\f');assert len(pages)==inv['pages']+1
        for i,t in enumerate(pages[:-1],1):
            db.execute('INSERT INTO directory_pages VALUES(?,?,?,?)',(inv['sha256'],i,t,digest(t.encode())))
            db.execute('INSERT INTO directory_search VALUES(?,?,?)',(inv['sha256'],i,t))
    write(BASE/'humana-document-inventory.json',inventory)
    bindings=json.loads((BASE/'humana-plan-document-bindings.json').read_text());bydoc=defaultdict(list)
    for b in bindings:
        bydoc[b['document_sha256']].append(b)
        db.execute('INSERT INTO plan_documents VALUES(?,?,?)',(b['offering_id'],b['document_sha256'],b['state']))
        db.execute('INSERT INTO r3_plan_directory_bindings VALUES(?,?,?)',(b['offering_id'],b['document_sha256'],packed(b)))
    hospitals=[dict(id=r[0],county=r[1],name=r[2],addresses=json.loads(r[3]))for r in db.execute('SELECT id,county,name,addresses_json FROM hospitals')]
    evidence=[];address_count=0
    for line in gzip.open(BASE/'humana-address-observations.jsonl.gz','rt'):
        r=json.loads(line);f=r['fields'];address_count+=1
        db.execute('INSERT INTO r3_address_observations VALUES(?,?,?,?)',(r['id'],r['document_sha256'],r['page'],packed(r)))
        for hid in match_campus(f['name_candidate_raw'],f['street_raw'],f['city_raw'],f['postal_raw'],hospitals):
            # A published hospital section is required, preventing an office at
            # the same address from becoming a licensed hospital-campus listing.
            if 'Hospital'not in f['section_raw']:continue
            for b in bydoc[r['document_sha256']]:
                evidence.append({'hospital_id':hid,'offering_id':b['offering_id'],'source_observation':r['id'],
                  'source_kind':'Humana published exact-plan partial directory','source_page':r['page'],
                  'document_sha256':r['document_sha256'],'name_raw':f['name_candidate_raw'],'street_raw':f['street_raw'],
                  'city_raw':f['city_raw'],'postal_raw':f['postal_raw'],'binding':b,
                  'state':'published_exact_plan_campus_listing; directory partial; personal participation unverified'})
    ars=json.loads((BASE/'aetna-mentalhealth-observations.json').read_text())
    hrs=json.loads((BASE/'humana-public-hospital-observations.json').read_text())
    bs=json.loads((BASE/'blue-current-family-observations.json').read_text())
    for fam,rs in [('aetna',ars),('humana',hrs),('blue',bs)]:
        for r in rs:
            db.execute('INSERT INTO r3_public_observations VALUES(?,?,?,?,?)',(r['id'],fam,r.get('offering_id'),r['source_path'],packed(r)))
    # Unlike a fuzzy product-family match, the pinned InsurancePlan resources
    # explicitly reference the same carrier's named medical network. The guest
    # query independently displays that exact network and benefit year 2026.
    hmo_bindings=[]
    for pid,key,obs,raw,state in db.execute('SELECT offering_id,network_key,plan_observation,reference_json,state FROM plan_networks'):
        ref=json.loads(raw)
        if state=='source_medical_network_reference'and ref.get('display')=='FL Medicare HMO':
            b={'offering_id':pid,'network_key':key,'parent_exact_plan_observation':obs,'parent_reference':ref,
              'public_network_raw':'FL Medicare HMO','benefit_year':2026,
              'public_scope_source':hrs[0]['source_path'],
              'state':'exact published named medical network reference joined to same-carrier same-year selected guest network; no family-name inference'}
            hmo_bindings.append(b);db.execute('INSERT INTO r3_named_network_bindings VALUES(?,?)',(pid,packed(b)))
    assert len(hmo_bindings)==8 and len({b['network_key']for b in hmo_bindings})==1
    write(BASE/'humana-named-network-bindings.json',hmo_bindings)
    for r in hrs:
        f=r['fields']
        if not all(k in f for k in ['street_raw','city_raw','postal_raw']):continue
        for hid in match_campus(f['name_raw'],f['street_raw'],f['city_raw'],f['postal_raw'],hospitals):
            for b in hmo_bindings:
                evidence.append({'hospital_id':hid,'offering_id':b['offering_id'],'source_observation':r['id'],
                  'source_kind':'Humana explicit same-year named medical network query','source_path':r['source_path'],
                  'name_raw':f['name_raw'],'street_raw':f['street_raw'],'city_raw':f['city_raw'],'postal_raw':f['postal_raw'],
                  'named_network_binding':b,'state':'published exact-plan medical-network campus listing; bounded query; personal participation unverified'})
    for r in ars:
        f=r['fields']
        if'In Network'not in f.get('published_network_label',''):continue
        for hid in match_campus(f['name_raw'],f.get('street_raw'),f.get('city'),f.get('postal_code'),hospitals):
            evidence.append({'hospital_id':hid,'offering_id':r['offering_id'],'source_observation':r['id'],
              'source_kind':'Aetna exact 2026 mental-health-facility query','source_path':r['source_path'],
              'name_raw':f['name_raw'],'street_raw':f['street_raw'],'city_raw':f['city'],'postal_raw':f['postal_code'],
              'state':'published_exact_plan_campus_listing; bounded query; personal participation unverified'})
    for fam,file in [('aetna','aetna-mentalhealth-query-accounting.json'),('humana','humana-public-hospital-accounting.json')]:
        for q in json.loads((BASE/file).read_text()):db.execute('INSERT INTO r3_public_query_accounting(family,fields_json)VALUES(?,?)',(fam,packed(q)))
    groups=json.loads((BASE/'published-shared-group-sites.json').read_text())
    for g in groups:db.execute('INSERT INTO r3_shared_group_sites VALUES(?,?)',(g['id'],packed(g)))
    identity=json.loads((BASE/'humana-location-resolution.json').read_text())
    db.execute('INSERT INTO r3_identity_resolutions VALUES(?,?)',('Humana-NPI-1619487246-location',packed(identity)))
    axiom_source=json.loads((BASE/'acquisition/receipts/7c31e9332a586300fb950937322d7f0bf9d1d7fe00e44d61ba583325b5d40266.json').read_text())
    axiom_native=json.loads((ROOT/axiom_source['path']).read_text());ent=axiom_native['results'][0]
    assert ent['number']=='1235024357'
    location=next(a for a in ent['addresses']if a['address_purpose']=='LOCATION')
    axiom={'id':'Axiom-current-entity','npi':'1235024357','registry_source':axiom_source,'registry_entity_pointer':'/results/0',
      'registry_name':ent['basic']['organization_name'],'registry_location':location,
      'registry_location_pointer':'/results/0/addresses/'+str(ent['addresses'].index(location)),
      'current_Aetna_publisher_provider_id':'2341726','exact_HMO_observation':next(r['id']for r in ars if r['offering_id']=='2026:H1609:027:000'and r['fields']['name_raw']=='Axiom Behavioral Health at Naples'),
      'parent_older_publisher_provider_id':'6200930','parent_older_NPI':'1932138823',
      'state':'Current Axiom exact-plan campus listing found independently; earlier Willough detail failure retained; no termination inferred for the older entity'}
    assert norm(location['address_1'])in['9001tamiamitrle','9001tamiamitraile']
    assert location['city']=='NAPLES'and location['postal_code'].startswith('34113')
    write(BASE/'axiom-current-identity.json',axiom);db.execute('INSERT INTO r3_identity_resolutions VALUES(?,?)',(axiom['id'],packed(axiom)))
    cells_before={tuple(x[:2]):x[2]for x in db.execute('SELECT hospital_id,offering_id,state FROM hospital_plan_matrix')}
    grouped=defaultdict(list)
    for e in evidence:
        db.execute('INSERT INTO r3_hospital_evidence VALUES(?,?,?,?)',(e['hospital_id'],e['offering_id'],e['source_observation'],packed(e)))
        grouped[e['hospital_id'],e['offering_id']].append(e)
    for key,es in grouped.items():
        old=db.execute('SELECT evidence_json FROM hospital_plan_matrix WHERE hospital_id=? AND offering_id=?',key).fetchone()
        assert old is not None
        db.execute('UPDATE hospital_plan_matrix SET state=?,evidence_json=? WHERE hospital_id=? AND offering_id=?',
                   ('published_exact_plan_campus_listing; personal applicability unverified',packed(json.loads(old[0])+es),*key))
    write(BASE/'new-hospital-plan-evidence.json',evidence)
    gained=[{'hospital_id':k[0],'offering_id':k[1],'before':cells_before[k],'after':'published_exact_plan_campus_listing; personal applicability unverified'}for k in grouped if cells_before[k].startswith('unknown')]
    write(BASE/'newly-supported-hospital-cells.json',gained)
    aetna_ids=['2026:H1609:027:000']+['2026:H5521:'+p+':000'for p in ['033','272','306','710']]
    aetna_positive=sum(1 for hid,pid,state in db.execute('SELECT hospital_id,offering_id,state FROM hospital_plan_matrix')
        if pid in aetna_ids and next(h['county']for h in hospitals if h['id']==hid)=='Collier'and state.startswith('published'))
    db.execute('PRAGMA user_version=3');db.commit();db.close()
    summary={'published_PDFs_acquired':len(inventory),'all_acquired_PDF_pages':sum(x['pages']for x in inventory),
      'Collier_applicable_partial_directories':sum(x['collier_geography_explicit']for x in inventory),
      'Collier_applicable_PDF_pages':sum(x['pages']for x in inventory if x['collier_geography_explicit']),
      'Humana_exact_target_offerings_with_directory':len({b['offering_id']for b in bindings}),
      'new_Humana_address_observations':address_count,'Aetna_new_facility_query_observations':len(ars),
      'Humana_public_query_observations':len(hrs),'Blue_held_current_family_observations':len(bs),
      'new_hospital_source_observations':len(evidence),'newly_supported_hospital_plan_cells':len(gained),
      'newly_supported_Collier_hospital_plan_cells':sum(next(h['county']for h in hospitals if h['id']==g['hospital_id'])=='Collier'for g in gained),
      'Aetna_five_plans_Collier_hospital_positive_cells':aetna_positive,
      'full_L08_complete':False,'consumer_release_enabled':False,'human_accepted':False}
    write(BASE/'summary.json',summary);print(json.dumps(summary))

if __name__=='__main__':main()
