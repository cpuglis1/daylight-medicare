#!/usr/bin/env python3
"""Attach complete source documents/listing units and campus evidence to L08 SQLite."""
from collections import Counter,defaultdict
import gzip
import json
import re
import sqlite3
from l08_acquire import BASE,OUT,ROOT,write


def normalized(s):
    s=re.sub(r'\bhosp\b','hospital',s or'',flags=re.I)
    s=re.sub(r'\b(?:inc|llc|corporation|corp|the)\b','',s,flags=re.I)
    return re.sub('[^a-z0-9]','',s.lower())


def bindings(document,plans):
    label=document['label']
    erick={'signature-en.pdf':'001','LibertyNoRX-en.pdf':'002','champion-en.pdf':'004','freedom-en.pdf':'006','liberty-en.pdf':'008'}
    if label.startswith('Erickson Florida '):return ['2026:H5652:'+erick[label.split()[-1]]+':000']
    if label=='HealthSpring Florida medical directory':return [p['id']for p in plans if p['contract']=='H5410']
    if label=='Freedom 2026 MAPD directory':return [p['id']for p in plans if p['contract']=='H5427'and p['drug']=='Yes']
    if label=='Optimum exact 2026 directory':return [p['id']for p in plans if p['contract']=='H5594']
    if label=='Aetna 2026 Southwest Florida DSNP directory':return ['2026:H1609:056:000','2026:H1609:078:000']
    return []


def main():
    b=BASE/'build-r1';db=sqlite3.connect(b/'providers.sqlite3');plans=json.loads((BASE/'plan-source-matrix.json').read_text())
    db.executescript('''
      CREATE TABLE directory_documents(sha256 TEXT PRIMARY KEY,label TEXT,year INTEGER,published_date_text TEXT,pages INTEGER,metadata_json TEXT);
      CREATE TABLE plan_documents(offering_id TEXT,document_sha256 TEXT,scope_state TEXT,PRIMARY KEY(offering_id,document_sha256));
      CREATE TABLE directory_pages(document_sha256 TEXT,page INTEGER,text TEXT,text_sha256 TEXT,PRIMARY KEY(document_sha256,page));
      CREATE VIRTUAL TABLE directory_search USING fts5(document_sha256 UNINDEXED,page UNINDEXED,text);
      CREATE TABLE directory_identifiers(document_sha256 TEXT,page INTEGER,kind TEXT,value TEXT,projection TEXT,span_json TEXT);
      CREATE TABLE pdf_records(id TEXT PRIMARY KEY,document_sha256 TEXT,family TEXT,identifier_kind TEXT,identifier TEXT,name_raw TEXT,page INTEGER,state TEXT,domain TEXT,fields_json TEXT);
      CREATE TABLE pdf_address_fragments(document_sha256 TEXT,page INTEGER,line INTEGER,text TEXT,state TEXT);
      CREATE TABLE source_conflicts(id TEXT PRIMARY KEY,kind TEXT,fields_json TEXT);
    ''')
    docs=json.loads((BASE/'document-index-r1/documents.json').read_text());docmap={d['source_sha256']:d for d in docs};plan_docs=defaultdict(list)
    for d in docs:
        sha=d['source_sha256'];db.execute('INSERT INTO directory_documents VALUES(?,?,?,?,?,?)',(sha,d['label'],2026,d['published_date_text'],d['pages'],json.dumps(d)))
        for pid in bindings(d,plans):
            state='exact_2026_product_publication'if d['label'].startswith(('Erickson','Aetna','HealthSpring'))else'published_shared_carrier_2026_directory_with_native_conditions'
            db.execute('INSERT INTO plan_documents VALUES(?,?,?)',(pid,sha,state));plan_docs[pid].append(sha)
    for line in gzip.open(BASE/'document-index-r1/pages.jsonl.gz','rt'):
        r=json.loads(line);db.execute('INSERT INTO directory_pages VALUES(?,?,?,?)',(r['source_sha256'],r['page'],r['text'],r['text_sha256']));db.execute('INSERT INTO directory_search VALUES(?,?,?)',(r['source_sha256'],r['page'],r['text']))
    for line in gzip.open(BASE/'document-index-r1/identifiers.jsonl.gz','rt'):
        r=json.loads(line);db.execute('INSERT INTO directory_identifiers VALUES(?,?,?,?,?,?)',(r['source_sha256'],r['page'],r['kind'],r['value'],r['projection'],json.dumps(r['span'])))
    for d in json.loads((BASE/'pdf-records-r1/summary.json').read_text()):
        for x in d['unassigned_city_state_postal_lines']:
            db.execute('INSERT INTO pdf_address_fragments VALUES(?,?,?,?,?)',(d['document_sha256'],x['page'],x['line'],x['text'],'held_source_address_fragment; association not inferred'))
    hospitals=json.loads((b/'hospital-reference.json').read_text());hbyid={h['id']:h for h in hospitals}
    aliases={h['id']:{normalized(h['Name']),normalized(h['Owner'])}for h in hospitals}
    curated={
      'AHCA:9841':['Naples Community Hosp','NCH Baker Hospital'],
      'AHCA:10147':['North Collier Hospital','Naples Community Hosp','Naples Community Hospital Inc'],
      'AHCA:10162':['Physicians Regional Medical Center'],
      'AHCA:178823':['Physicians Regional Medical Center'],
      'AHCA:489522':['Physicians Regional Medical Center'],
      'AHCA:458386':['Encompass Health Rehabilitation Hospital'],
      'AHCA:10107':['The Willough at Naples','Willough Healthcare Inc'],
    }
    for hid,names in curated.items():aliases[hid]|={normalized(n)for n in names}
    # Exact primary-campus address, not a doctor's hospital affiliation, supplies
    # the campus grain. Names must independently match the hospital/owner alias.
    def addrkey(a):
        s=a.upper().replace('HEALTH PARK','HEALTHPARK')
        return re.sub('[^A-Z0-9]','',s)
    primary={}
    for h in hospitals:
        primary[h['id']]=[a for a in h['addresses']if a.get('AddressType')=='ST']
    campus_evidence=defaultdict(list);pdfcounts=Counter();addresscounts=Counter();conflict_records=[]
    for line in gzip.open(BASE/'pdf-records-r1/records.jsonl.gz','rt'):
        r=json.loads(line);sha=r['document_sha256'];pdfcounts[sha]+=1;addresscounts[sha]+=len(r['addresses'])
        db.execute('INSERT INTO pdf_records VALUES(?,?,?,?,?,?,?,?,?,?)',(r['id'],sha,r['family'],r['identifier_kind'],r['identifier'],r['provider_display_raw'],r['anchor_page'],r['state'],r['listing_domain'],json.dumps(r,ensure_ascii=False)))
        if r['listing_domain']!='medical_or_supplemental_provider'or r['state'].startswith('held_'):continue
        rawname=r['provider_display_raw']or''
        # Superscript legend markers remain in source fields; exclude them only
        # in this separately documented name-comparison key.
        name=normalized(re.sub(r'\d+(?:[, .]\d+)*$','',rawname).strip())
        for hid,h in hbyid.items():
            if name not in aliases[hid]:continue
            for a in r['addresses']:
                for pa in primary[hid]:
                    if addrkey(a['street_raw'])!=addrkey(pa.get('Address','')+' '+pa.get('Address2','')):continue
                    if normalized(a['city'])!=normalized(pa.get('City',''))or a['state']!=pa.get('State')or a['postal_code'][:5]!=pa.get('Zip','')[:5]:continue
                    state='published_directory_lists_campus'
                    if r['identifier']=='1497333017':
                        state='held_identifier_conflict'
                        conflict_records.append({'pdf_record_id':r['id'],'document_sha256':sha,'page':r['anchor_page'],'hospital_id':hid})
                    for pid in bindings(docmap[sha],plans):
                        campus_evidence[(hid,pid)].append({'state':state,'record_id':r['id'],'document_sha256':sha,'publication_date_text':r['publication_date_text'],
                            'page':r['anchor_page'],'directory_provider_name':rawname,'directory_identifier':r['identifier'],'directory_address':a,
                            'identity_basis':'Hospital-name/owner alias plus exact licensed primary-campus street/city/state/ZIP; source qualifiers retained',
                            'current_participation_guaranteed':False})
    for(hid,pid),evidence in campus_evidence.items():
        state='published_directory_lists_campus'if any(e['state']=='published_directory_lists_campus'for e in evidence)else'held_identifier_conflict'
        db.execute('UPDATE hospital_plan_matrix SET state=?,evidence_json=? WHERE hospital_id=?AND offering_id=?',(state,json.dumps(evidence),hid,pid))
    r=next(json.loads(f.read_text())for f in(OUT/'receipts').glob('*.json')if json.loads(f.read_text()).get('label')=='NPPES hospital identity 1497333017')
    source_conflict={'id':'REHAB-NPI-1497333017','kind':'published_hospital_identifier_conflict',
        'directory_npi':'1497333017','directory_hospital':'Encompass Health Rehabilitation Hospital','directory_street':'14305 Collier Blvd, Naples FL 34119',
        'registry_organization':'ENCOMPASS HEALTH REHABILITATION HOSPITAL OF GREENVILLE, LLC','registry_practice_address':'3372 LAURENS ROAD, GREENVILLE SC 29607',
        'registry_source_id':r['id'],'registry_source_sha256':r['sha256'],'directory_records':conflict_records,
        'disposition':'Retain source listing and both facts. Hold resolved identity and consequential campus participation inference pending publisher correction or specific authoritative evidence.'}
    db.execute('INSERT INTO source_conflicts VALUES(?,?,?)',(source_conflict['id'],source_conflict['kind'],json.dumps(source_conflict)))
    write(b/'hospital-identity-conflicts.json',[source_conflict]);write(b/'hospital-identity-aliases.json',{'comparison':'remove corporate suffix/punctuation; expand Hosp; drop trailing source footnote digits only for comparison','aliases':curated,'not_a_name_only_match':True,'registry_is_not_a_network_source':True})
    coverage=[]
    for p in plans:
        nets=dict(db.execute('SELECT state,count(*)FROM plan_networks WHERE offering_id=?GROUP BY state',(p['id'],)))
        rels=dict(db.execute('SELECT state,count(*)FROM relationships WHERE offering_id=?GROUP BY state',(p['id'],)))
        coverage.append({'offering_id':p['id'],'name':p['name'],'parent':p['parent'],'downloaded_2026_directories':plan_docs[p['id']],
                         'network_reference_states':nets,'api_relationship_observation_states':rels,
                         'published_directory_acquired':bool(plan_docs[p['id']]),'full_provider_location_roster_completeness_established':False,
                         'personal_participation_guaranteed':False})
    write(b/'plan-source-coverage.json',coverage)
    summary=json.loads((b/'summary.json').read_text());summary.update({
        'directory_pdfs':len(docs),'pdfs_bound_to_target_offerings':sum(bool(bindings(d,plans))for d in docs),
        'directory_pdf_pages':sum(d['pages']for d in docs),'target_bound_directory_pages':sum(d['pages']for d in docs if bindings(d,plans)),
        'offerings_with_downloaded_2026_publication':sum(bool(c['downloaded_2026_directories'])for c in coverage),
        'native_pdf_listing_units':sum(pdfcounts.values()),'native_pdf_address_observations':sum(addresscounts.values()),
        'pdf_identifier_kinds':dict(db.execute('SELECT identifier_kind,count(*)FROM pdf_records GROUP BY identifier_kind')),
        'unassigned_source_address_fragments':db.execute('SELECT count(*)FROM pdf_address_fragments').fetchone()[0],
        'hospital_matrix_states':dict(db.execute('SELECT state,count(*)FROM hospital_plan_matrix GROUP BY state')),
        'collier_hospital_matrix_states':dict(db.execute("SELECT m.state,count(*)FROM hospital_plan_matrix m JOIN hospitals h ON h.id=m.hospital_id WHERE h.county='Collier'GROUP BY m.state")),
        'all_source_fields_semantically_verified_as_personal_coverage':False,
        'original_medicare_enrollment_assignment_opt_out':'not collected: data.cms.gov access STOP; NPI/AHCA do not substitute',
        'SELECT':'Conditional L10 exact product/form/network dependency; not inferred absent'})
    db.executescript('CREATE INDEX pdf_npi ON pdf_records(identifier_kind,identifier);CREATE INDEX pdf_doc ON pdf_records(document_sha256);')
    db.commit();db.close();write(b/'summary.json',summary);print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
