"""Additive database, owner download handoff and explicit remaining source gaps."""
import collections,gzip,json,re,sqlite3
from datetime import datetime,timezone
from pathlib import Path
from l08_r4_common import ROOT,HOME,PARENT,BASE,write,digest,filehash,assert_open

def packed(x):return json.dumps(x,ensure_ascii=False,sort_keys=True)

def handoff(db):
    l03=ROOT/'docs/data/l03-ma-benefits-2026-10-25/source-reconciliation-r6'
    matrix=json.loads((l03/'plan-document-matrix.json').read_text());catalog={x['sha256']:x for x in json.loads((l03/'source-catalog.json').read_text())}
    rows=[]
    for r in matrix:
        if not r['offering_id'].startswith('2026:H1032:'):continue
        sh=r['document_matches']['EOC']['sha256'];src=catalog[sh];p=Path(src['text_path']);text=p.read_text();pages=text.split('\f');evidence=[]
        for pg,t in enumerate(pages,1):
            for m in re.finditer(r'go\.wellcare\.com/\s*2026providerdirectories',t):
                evidence.append({'text_path':str(p.relative_to(ROOT)),'text_sha256':filehash(p),'page':pg,'span':list(m.span()),'raw':m[0]})
        assert evidence
        rows.append({'offering_id':r['offering_id'],'name':r['name'],'document_needed':'2026 medical Provider / Provider and Pharmacy Directory applicable to Collier and this exact plan',
          'official_2026_download_route':'https://go.wellcare.com/2026providerdirectories','direct_pdf_url':None,
          'route_evidence':evidence,'EOC_source_sha256':sh,'file_not_yet_acquired':True,
          'why_needed':'Enumerates named clinicians, practices, sites and hospitals; the EOC does not supply a medical roster.'})
    assert len(rows)==6
    receipts=[json.loads(p.read_text())for p in(BASE/'acquisition/receipts').glob('*.json')]
    advertised=next(r for r in receipts if r['requested_url']=='https://www.wellcarede.com/find-doctor.html')
    html=(ROOT/advertised['path']).read_text()
    assert 'wellcareproviderdirectories.com'in html and'View Provider Directory Documents'in html
    write(BASE/'wellcare-download-handoff.json',{'plans':rows,'verified_direct_PDF_links':0,
        'advertised_independent_directory_documents_site':'https://wellcareproviderdirectories.com/',
        'advertised_site_source_receipt':advertised,'advertised_site_observation':'Browser net::ERR_CERT_AUTHORITY_INVALID; no warning bypass and no content acquired',
        'portal_route_observation':'Prior automatic approval review twice rejected my.wellcare.com redirect, including after owner guest-only approval; no retry this revision',
        'instructions':'Open the official 2026 route; choose Florida, 2026, Collier, and each exact target plan. Download medical provider directory PDFs if offered. One shared file is sufficient when its applicability explicitly lists the relevant plans. Save in /Users/cep4u/daylight/plans. Do not substitute a pharmacy-only directory, Medicaid-only roster, or 2027 directory.',
        'additional_downloads_requested_for_other_internal_fragments':False})
    table='\n'.join('| '+r['offering_id'].split(':')[1]+'-'+r['offering_id'].split(':')[2]+' | '+r['name']+' |'for r in rows)
    (BASE/'WELLCARE_DOWNLOADS.md').write_text('''# Wellcare files needed for L08

The official route printed in all six retained 2026 EOCs is [2026 Provider Directories](https://go.wellcare.com/2026providerdirectories). **This is a download-selection route, not a verified direct PDF link. I could not verify a direct file URL.**

Select **Florida → 2026 → Collier** and the exact plan below, then download the medical **Provider Directory** or combined **Provider and Pharmacy Directory**, if offered. A single shared directory can cover several plans if it explicitly states that applicability. Save the original PDFs in `/Users/cep4u/daylight/plans`.

| Exact plan | Published 2026 plan name |
|---|---|
'''+table+'''

These are the medical rosters that L08 still needs. Existing SB/EOC benefit documents and pharmacy-only directories do not enumerate the doctors/hospital network.

[An official Wellcare public page](https://www.wellcarede.com/find-doctor.html) separately advertises [Provider Directory Documents](https://wellcareproviderdirectories.com/). That download host produced a browser certificate error, so its contents could not be inspected. No security warning was bypassed. If the official route does not offer a usable 2026 Collier directory, the published roster remains a source-access gap; no guessed file URL is supplied.

The advertised live provider finder redirected to `my.wellcare.com`. Automatic approval review rejected that member-portal destination despite the owner's guest-only approval, because it may expose private account information. This revision did not retry it or sign in.

[Exact retained EOC page/span evidence and file checklist](wellcare-download-handoff.json).
''')

def main():
    assert_open();dest=BASE/'providers.sqlite3'
    if dest.exists():dest.unlink()
    p=sqlite3.connect('file:'+str(PARENT/'providers.sqlite3')+'?mode=ro',uri=True);db=sqlite3.connect(dest);p.backup(db);p.close()
    db.executescript('''
    CREATE TABLE r4_humana_entries(id TEXT PRIMARY KEY,document_sha256 TEXT,page INTEGER,name_kind TEXT,site_state TEXT,fields_json TEXT);
    CREATE TABLE r4_address_entry_links(address_id TEXT PRIMARY KEY,entry_id TEXT,fields_json TEXT);
    CREATE TABLE r4_legacy_dispositions(parent_record_id TEXT PRIMARY KEY,state TEXT,fields_json TEXT);
    CREATE TABLE r4_legacy_shared_layouts(id TEXT PRIMARY KEY,fields_json TEXT);
    CREATE TABLE r4_public_observations(id TEXT PRIMARY KEY,network_raw TEXT,source_path TEXT,fields_json TEXT);
    CREATE TABLE r4_public_query_accounting(network_raw TEXT PRIMARY KEY,fields_json TEXT);
    ''')
    for s in gzip.open(BASE/'humana-entries.jsonl.gz','rt'):
        r=json.loads(s);db.execute('INSERT INTO r4_humana_entries VALUES(?,?,?,?,?,?)',(r['id'],r['document_sha256'],r['page'],r['name_kind'],r['site_association_state'],packed(r)))
    for s in gzip.open(BASE/'humana-address-entry-links.jsonl.gz','rt'):
        r=json.loads(s);db.execute('INSERT INTO r4_address_entry_links VALUES(?,?,?)',(r['address_id'],r['entry_id'],packed(r)))
    for r in json.loads((BASE/'legacy-unit-dispositions.json').read_text()):db.execute('INSERT INTO r4_legacy_dispositions VALUES(?,?,?)',(r['parent_record_id'],r['state'],packed(r)))
    for r in json.loads((BASE/'legacy-shared-layouts.json').read_text()):db.execute('INSERT INTO r4_legacy_shared_layouts VALUES(?,?)',(r['id'],packed(r)))
    for r in json.loads((BASE/'public-hospital-observations.json').read_text()):db.execute('INSERT INTO r4_public_observations VALUES(?,?,?,?)',(r['id'],r['network_raw'],r['source_path'],packed(r)))
    for r in json.loads((BASE/'public-query-accounting.json').read_text()):db.execute('INSERT INTO r4_public_query_accounting VALUES(?,?)',(r['network_raw'],packed(r)))
    for p in(BASE/'ui').glob('*.ax.txt'):
        db.execute('INSERT INTO sources VALUES(?,?,?,?,?)',('r4-ui:'+p.name,'https://findcare.humana.com/medical',filehash(p),str(p.relative_to(ROOT)),datetime.now(timezone.utc).isoformat()))
    for p in(BASE/'acquisition/receipts').glob('*.json'):
        r=json.loads(p.read_text())
        if r.get('http_status')==200:db.execute('INSERT INTO sources VALUES(?,?,?,?,?)',('r4:'+r['id'],r['requested_url'],r['sha256'],r['path'],r['retrieved_at_utc']))
    db.execute('PRAGMA user_version=4');db.commit();handoff(db)
    inherited=json.loads((PARENT/'plan-source-coverage.json').read_text());write(BASE/'plan-source-coverage.json',inherited)
    # Every 2026 PPO offering references many networks in the retained source.
    # Expose this ambiguity instead of silently promoting generic guest queries
    # into new exact-plan hospital-matrix facts.
    refs=[]
    for pid,raw,state in db.execute('SELECT offering_id,reference_json,state FROM plan_networks'):
        r=json.loads(raw)
        if state=='source_medical_network_reference'and r.get('display')in['Medicare PPO','Humana Honor PPO','Community Health Medicare PPO']:
            refs.append({'offering_id':pid,'parent_reference':r,'state':'retained_source_reference; exact_guest_network_applicability_not_accepted_by_r4'})
    write(BASE/'PPO-network-crosswalk-hold.json',{'references':refs,'exact_offerings':len({r['offering_id']for r in refs}),
       'reason':'All fourteen PPO offerings reference multiple distinct named networks. The generic reference list alone does not disambiguate the applicable selected guest network for each exact offering.',
       'new_exact_hospital_plan_cells_asserted':0,'existing_parent_evidence_unchanged':True})
    db.close();print(json.dumps({'database_bytes':dest.stat().st_size,'r4_tables':6,'parent_copied_unchanged':True}))

if __name__=='__main__':main()
