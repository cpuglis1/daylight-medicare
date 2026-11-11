"""Append owner-supplied Wellcare research; preserve every sealed parent row."""
import collections,gzip,json,sqlite3
from datetime import datetime,timezone
from l08_r5_common import ROOT,HOME,PARENT,BASE,write,digest,assert_open
from l08_r5_normalize import norm

def packed(x):return json.dumps(x,ensure_ascii=False,sort_keys=True)

# Deliberately narrow published name/street rules. Other hospital observations,
# including the abbreviated Creekside and co-located Landmark entries, stay
# visible without an unsupported canonical-campus merge.
CAMPUS_RULES=[
 {'hospital_id':'AHCA:9841','name_raw':'Naples Community Hospital','street_raw':'350 7th St N','postal_raw':'34102'},
 {'hospital_id':'AHCA:10147','name_raw':'Naples Community Hospital','practice_raw':'Nch North Naples Hospital','street_raw':'11190 Health Park Blvd','postal_raw':'34110'},
 {'hospital_id':'AHCA:10162','name_raw':'Physicians Regional Med Ctr','street_raw':'6101 Pine Ridge Rd','postal_raw':'34119'},
 {'hospital_id':'AHCA:178823','name_raw':'Physicians Regional Med Ctr','street_raw':'8300 Collier Blvd','postal_raw':'34114'},
]

def matched_hospitals(r):
    if r['section_raw']!='Hospitals':return []
    result=[]
    for rule in CAMPUS_RULES:
        if norm(r['name_raw'])!=norm(rule['name_raw']):continue
        if 'practice_raw'in rule and norm(r['practice_raw']or'')!=norm(rule['practice_raw']):continue
        for a in r['addresses']:
            if a['state_raw']=='FL'and norm(a['city_raw'])=='naples'and norm(a['street_raw']or'')==norm(rule['street_raw'])and a['postal_raw'][:5]==rule['postal_raw']:result.append(rule['hospital_id'])
    return sorted(set(result))

def main():
    assert_open();dest=BASE/'providers.sqlite3'
    if dest.exists():dest.unlink()
    parent=sqlite3.connect('file:'+str(PARENT/'providers.sqlite3')+'?mode=ro',uri=True);db=sqlite3.connect(dest);parent.backup(db);parent.close()
    db.executescript('''
      CREATE TABLE r5_wellcare_records(id TEXT PRIMARY KEY,document_sha256 TEXT,page INTEGER,publisher_provider_id TEXT,section_raw TEXT,county_raw TEXT,fields_json TEXT);
      CREATE TABLE r5_plan_directory_bindings(offering_id TEXT,document_sha256 TEXT,fields_json TEXT,PRIMARY KEY(offering_id,document_sha256));
      CREATE TABLE r5_image_occurrences(document_sha256 TEXT,image_index INTEGER,page INTEGER,asset_key TEXT,fields_json TEXT,PRIMARY KEY(document_sha256,image_index));
      CREATE TABLE r5_document_accounting(document_sha256 TEXT PRIMARY KEY,fields_json TEXT);
      CREATE TABLE r5_hospital_evidence(hospital_id TEXT,offering_id TEXT,record_id TEXT,fields_json TEXT);
    ''')
    owners=json.loads((BASE/'owner-file-observations.json').read_text());invs=json.loads((BASE/'document-inventory.json').read_text());bydoc=collections.defaultdict(list)
    for owner in owners:
        db.execute('INSERT INTO sources VALUES(?,?,?,?,?)',('r5-owner:'+owner['filename'],owner['owner_path'],owner['sha256'],owner['retained_path'],owner['received_at_utc']))
    for inv in invs:
        inv['label']='Wellcare owner-supplied '+inv['owner_filenames'][0]
        db.execute('INSERT INTO directory_documents VALUES(?,?,?,?,?,?)',(inv['sha256'],inv['label'],2026,inv['published_as_of'],inv['pages'],packed(inv)))
        pages=(ROOT/inv['text_path']).read_text().split('\f')[:-1]
        for pg,t in enumerate(pages,1):
            db.execute('INSERT INTO directory_pages VALUES(?,?,?,?)',(inv['sha256'],pg,t,digest(t.encode())))
            db.execute('INSERT INTO directory_search VALUES(?,?,?)',(inv['sha256'],pg,t))
    write(BASE/'document-inventory.json',invs)
    for b in json.loads((BASE/'plan-directory-bindings.json').read_text()):
        bydoc[b['document_sha256']].append(b)
        db.execute('INSERT INTO r5_plan_directory_bindings VALUES(?,?,?)',(b['offering_id'],b['document_sha256'],packed(b)))
        db.execute('INSERT INTO plan_documents VALUES(?,?,?)',(b['offering_id'],b['document_sha256'],b['state']))
    imageindices=collections.Counter()
    for s in gzip.open(BASE/'image-occurrences.jsonl.gz','rt'):
        r=json.loads(s);sh=r['document_sha256'];ix=imageindices[sh];imageindices[sh]+=1
        db.execute('INSERT INTO r5_image_occurrences VALUES(?,?,?,?,?)',(sh,ix,r['page'],r['asset_key'],packed(r)))
    for r in json.loads((BASE/'extraction-accounting.json').read_text()):db.execute('INSERT INTO r5_document_accounting VALUES(?,?)',(r['document_sha256'],packed(r)))
    evidence=[];hospitalobs=[];before={(r[0],r[1]):r[2]for r in db.execute('SELECT hospital_id,offering_id,state FROM hospital_plan_matrix')}
    for s in gzip.open(BASE/'wellcare-records.jsonl.gz','rt'):
        r=json.loads(s);db.execute('INSERT INTO r5_wellcare_records VALUES(?,?,?,?,?,?,?)',(r['id'],r['document_sha256'],r['page'],r['publisher_provider_id'],r['section_raw'],r['county_raw'],packed(r)))
        if r['section_raw']!='Hospitals':continue
        matches=matched_hospitals(r)
        hospitalobs.append({'record_id':r['id'],'document_sha256':r['document_sha256'],'page':r['page'],'name_raw':r['name_raw'],
          'practice_raw':r['practice_raw'],'addresses':r['addresses'],'specialty_raw':r['specialty_raw'],'matched_current_census_campuses':matches,
          'state':'exact_source_name_and_current_census_street'if matches else'published_hospital_listing_retained; no_strict_canonical_campus_join; no_exclusion_inferred'})
        for hid in matches:
            # Require the exact current licensed street/city/ZIP, not a mailing
            # address, co-located outpatient site or clinician affiliation.
            hs=json.loads(db.execute('SELECT addresses_json FROM hospitals WHERE id=?',(hid,)).fetchone()[0])
            a=r['addresses'][0];assert any(x['AddressType']=='ST'and norm(x['Address'])==norm(a['street_raw'])and norm(x['City'])==norm(a['city_raw'])and x['Zip'][:5]==a['postal_raw'][:5]for x in hs)
            for binding in bydoc[r['document_sha256']]:
                e={'hospital_id':hid,'offering_id':binding['offering_id'],'record_id':r['id'],'document_sha256':r['document_sha256'],'page':r['page'],
                    'source_kind':'owner-supplied published 2026 Wellcare medical directory','name_raw':r['name_raw'],'practice_raw':r['practice_raw'],
                    'address':a,'plan_binding':binding,'published_as_of':r['published_as_of'],
                    'state':'published_dated_plan_name_and_Collier_scope_campus_reference; unique_CMS_offering_bridge; personal_participation_unverified'}
                evidence.append(e);db.execute('INSERT INTO r5_hospital_evidence VALUES(?,?,?,?)',(hid,binding['offering_id'],r['id'],packed(e)))
    grouped=collections.defaultdict(list)
    for e in evidence:grouped[e['hospital_id'],e['offering_id']].append(e)
    for key,es in grouped.items():
        old=db.execute('SELECT evidence_json FROM hospital_plan_matrix WHERE hospital_id=?AND offering_id=?',key).fetchone();assert old
        db.execute('UPDATE hospital_plan_matrix SET state=?,evidence_json=?WHERE hospital_id=?AND offering_id=?',
            ('published_exact_plan_campus_listing; source_plan_name_Collier_bridge; personal applicability unverified',packed(json.loads(old[0])+es),*key))
    write(BASE/'hospital-source-reconciliation.json',hospitalobs);write(BASE/'new-hospital-evidence.json',evidence)
    write(BASE/'newly-supported-hospital-cells.json',[{'hospital_id':hid,'offering_id':pid,'prior_state':before[hid,pid]}for hid,pid in grouped if before[hid,pid].startswith('unknown')])
    coverage=json.loads((PARENT/'plan-source-coverage.json').read_text())
    write(BASE/'parent-plan-source-coverage.json',coverage)
    # A separate full pinned inventory keeps the old snapshot intact and
    # reports r5 additions without changing historical coverage claims.
    offered=[]
    for pid,name,parent in db.execute('SELECT id,name,parent FROM offerings ORDER BY id'):
        offered.append({'offering_id':pid,'name':name,'parent':parent,'new_Wellcare_documents':[b for bs in bydoc.values()for b in bs if b['offering_id']==pid],
          'prior_coverage':'parent-plan-source-coverage.json','full_network_complete':False})
    write(BASE/'plan-source-coverage.json',offered)
    total=db.execute("SELECT count(*)FROM hospital_plan_matrix WHERE state LIKE 'published%'").fetchone()[0]
    local=db.execute("SELECT count(*)FROM hospital_plan_matrix m JOIN hospitals h ON h.id=m.hospital_id WHERE h.county='Collier'AND m.state LIKE 'published%'").fetchone()[0]
    write(BASE/'hospital-coverage-summary.json',{'total_cells':1224,'positive_published_cells':total,'unknown_cells':1224-total,
       'Collier_total_cells':504,'Collier_positive_published_cells':local,'Collier_unknown_cells':504-local,
       'new_published_evidence_rows':len(evidence),'newly_supported_cells':sum(before[k].startswith('unknown')for k in grouped),
       'unknown_is_not_out_of_network':True,'strict_campus_rules':CAMPUS_RULES})
    db.execute('PRAGMA user_version=5');db.commit();db.close()
    print(json.dumps({'database_bytes':dest.stat().st_size,'new_hospital_evidence':len(evidence),'new_hospital_cells':len(grouped)}),flush=True)

if __name__=='__main__':main()
