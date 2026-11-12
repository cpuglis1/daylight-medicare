"""Whole-population field, query, source, lineage and SQLite checks for L08 r3."""
import gzip,hashlib,json,re,sqlite3,xml.etree.ElementTree as ET
from collections import Counter,defaultdict
from l08_r3_common import BASE,PARENT,ROOT,write,digest
from l08_r3_aetna import ax_nodes
from l08_r3_pdf import CITY,PLAN
from l08_r3_build import match_campus

def filehash(p):
    h=hashlib.sha256()
    with p.open('rb')as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()

def main():
    counts=Counter();fail=[]
    def check(ok,description):
        if not ok:fail.append(description)
    for manifest in [PARENT/'execution-manifest-r1.json',PARENT/'followup-r2/manifest.json']:
        obj=json.loads(manifest.read_text());files=obj.get('files',{})
        check(bool(files),'Parent manifest has files '+str(manifest))
        for rel,meta in files.items():
            p=ROOT/rel;check(p.exists()and p.stat().st_size==meta['bytes']and filehash(p)==meta['sha256'],'Parent changed '+rel)
            counts['parent_sealed_files_rehashed']+=1
    db=sqlite3.connect('file:'+str(BASE/'providers.sqlite3')+'?mode=ro',uri=True)
    check(db.execute('PRAGMA integrity_check').fetchone()[0]=='ok','SQLite integrity')
    parent=sqlite3.connect('file:'+str(PARENT/'followup-r2/providers.sqlite3')+'?mode=ro',uri=True)
    # Every old row remains exactly present. For the hospital matrix only,
    # compare the old evidence as an exact prefix of each additive observation.
    tables=[x[0]for x in parent.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE '%_data' AND name NOT LIKE '%_idx' AND name NOT LIKE '%_content' AND name NOT LIKE '%_docsize' AND name NOT LIKE '%_config' AND name NOT LIKE 'sqlite_%'")]
    allowed_added={'sources','directory_documents','directory_pages','directory_search','plan_documents'}
    for table in tables:
        if table=='hospital_plan_matrix':continue
        cols=len(parent.execute('PRAGMA table_info("'+table+'")').fetchall())
        oldcur=parent.execute('SELECT * FROM "'+table+'" ORDER BY rowid')
        # The SQLite backup preserves existing rowids; inserts only append.
        newcur=db.execute('SELECT * FROM "'+table+'" ORDER BY rowid LIMIT '+str(parent.execute('SELECT COUNT(*)FROM "'+table+'"').fetchone()[0]))
        for old,new in zip(oldcur,newcur):
            check(old==new,'Parent row changed in '+table);counts['unchanged_parent_rows_compared']+=1
        nold=parent.execute('SELECT COUNT(*)FROM "'+table+'"').fetchone()[0]
        nnew=db.execute('SELECT COUNT(*)FROM "'+table+'"').fetchone()[0]
        check(nnew>=nold if table in allowed_added else nnew==nold,'Parent count changed '+table)
    check(db.execute('SELECT COUNT(*)FROM offerings').fetchone()[0]==72,'Exact 72-offering denominator')
    for rp in(BASE/'acquisition/receipts').glob('*.json'):
        r=json.loads(rp.read_text())
        if r.get('path'):
            p=ROOT/r['path'];check(p.stat().st_size==r['bytes']and filehash(p)==r['sha256'],'HTTP response hash '+r['id']);counts['HTTP_responses_hashed']+=1
    invs=json.loads((BASE/'humana-document-inventory.json').read_text());bydoc={x['sha256']:x for x in invs};natives={}
    for inv in invs:
        p=ROOT/inv['path'];check(p.read_bytes()[:5]==b'%PDF-','Actual PDF header '+inv['sha256'])
        txt=(ROOT/inv['text_path']).read_text();pages=txt.split('\f')
        check(len(pages)==inv['pages']+1 and not pages[-1].strip(),'PDF page accounting '+inv['sha256'])
        check(filehash(ROOT/inv['text_path'])==inv['text_sha256'],'PDF text digest')
        row=db.execute('SELECT metadata_json FROM directory_documents WHERE sha256=?',(inv['sha256'],)).fetchone()
        check(json.loads(row[0])==inv,'Document inventory/SQLite parity')
        for i,t in enumerate(pages[:-1],1):
            stored=db.execute('SELECT text,text_sha256 FROM directory_pages WHERE document_sha256=? AND page=?',(inv['sha256'],i)).fetchone()
            check(stored==(t,digest(t.encode())),'Complete page text parity '+inv['sha256']+':'+str(i));counts['new_PDF_pages_compared']+=1
        check('2026'in pages[0]and'This is a partial list'in pages[0],'Published year/partial boundary')
        region=None
        for page in pages[:10]:
            m=re.search(r'This directory is for providers in the following State\(s\) or counties:\s*\n(.*?)(?:\n\s*\n)',page,re.S)
            if m:region=m[1].strip();break
        check(region==inv['geography_raw'],'Printed geography paragraph')
        check(inv['collier_geography_explicit']==bool(region and re.search(r'\bCollier\b',region)),'Plan service area is not directory geography')
        if not inv['collier_geography_explicit']:
            check(not db.execute('SELECT 1 FROM plan_documents WHERE document_sha256=?',(inv['sha256'],)).fetchone(),'Wrong region not bound to Collier')
            continue
        ns=[json.loads(x)for x in gzip.open(ROOT/inv['native_path'],'rt')];natives[inv['sha256']]=ns
        check(filehash(ROOT/inv['native_path'])==inv['native_sha256'],'Native file hash')
        check(filehash(ROOT/inv['xml_path'])==inv['xml_sha256'],'Native XML digest')
        fonts={};seen=0;pages_seen=0
        with gzip.open(ROOT/inv['xml_path'],'rb')as stream:
            for _,page in ET.iterparse(stream,events=('end',)):
                if page.tag!='page':continue
                pages_seen+=1;pg=int(page.attrib['number'])
                for f in page.findall('fontspec'):fonts[f.attrib['id']]=dict(f.attrib)
                for j,e in enumerate(page.findall('text')):
                    value=''.join(e.itertext()).strip()
                    if not value:continue
                    expected={'page':pg,'node':j,'text':value,'top':int(e.attrib['top']),'left':int(e.attrib['left']),
                        'width':int(e.attrib['width']),'height':int(e.attrib['height']),'font':fonts[e.attrib['font']]}
                    check(ns[seen]==expected,'Native/XML node mismatch '+inv['sha256']+':'+str(seen));seen+=1;counts['native_XML_nodes_compared']+=1
                page.clear()
        check(seen==len(ns)and pages_seen==inv['pages'],'Whole XML/page population')
    bindings=json.loads((BASE/'humana-plan-document-bindings.json').read_text());byp=defaultdict(set)
    for b in bindings:
        inv=bydoc[b['document_sha256']];pages=(ROOT/inv['text_path']).read_text().split('\f')
        for mention in b['plan_mentions']:
            page=pages[mention['page']-1];a,z=mention['span'];raw=page[a:z]
            check(raw==mention['raw'],'Exact plan ID source span')
            m=PLAN.fullmatch(raw);check(m is not None and'2026:'+':'.join(m.groups())==b['offering_id'],'Exact contract/PBP/segment')
            counts['exact_plan_mentions_compared']+=1
        check(inv['collier_geography_explicit']and inv['partial_list_explicit'],'Binding scope')
        check(json.loads(db.execute('SELECT fields_json FROM r3_plan_directory_bindings WHERE offering_id=? AND document_sha256=?',(b['offering_id'],b['document_sha256'])).fetchone()[0])==b,'Plan binding database parity')
        byp[b['document_sha256']].add(b['offering_id'])
    humana_targets={r[0]for r in db.execute("SELECT id FROM offerings WHERE parent='Humana Inc.'")}
    actual={b['offering_id']for b in bindings}
    # Parent labels can vary, so use the pinned 22-offering gap denominator.
    expected=set(next(g['scope']for g in json.loads((PARENT/'followup-r2/genuine-gaps.json').read_text())if g['id']=='L08-G03'))
    check(actual==expected and len(actual)==22,'All 22 exact Humana offerings accounted')
    anchors=defaultdict(set)
    for line in gzip.open(BASE/'humana-address-observations.jsonl.gz','rt'):
        r=json.loads(line);ns=natives[r['document_sha256']];f=r['fields'];loc=r['locators'];anchors[r['document_sha256']].add(r['native_city_node'])
        for field in ['name_candidate_raw','street_raw','phone_raw','county_context_raw','section_raw']:
            indices=loc[field];value=' '.join(ns[i]['text']for i in indices)or None
            check(f[field]==value,'Field source mismatch '+r['id']+':'+field);counts['Humana_modeled_values_compared']+=1
        city=ns[loc['city_state_postal'][0]];m=CITY.fullmatch(city['text']);check(m is not None,'Valid city anchor')
        for field,group in [('city_raw','city'),('state_raw','state'),('postal_raw','postal')]:
            check(f[field]==m[group],'City state ZIP source comparison');counts['Humana_modeled_values_compared']+=1
        check(f['conditions_raw']==[ns[i]['text']for i in loc['conditions_raw']],'Condition text retained');counts['Humana_condition_values_compared']+=len(f['conditions_raw'])
        check(r['printed_county_is_collier']==(f['county_context_raw']=='COLLIER COUNTY'),'County context flag')
        check(json.loads(db.execute('SELECT fields_json FROM r3_address_observations WHERE id=?',(r['id'],)).fetchone()[0])==r,'Address SQLite/export parity');counts['Humana_address_records_compared']+=1
    for sh,ns in natives.items():
        pages=set(bydoc[sh]['modeled_pages'])
        expected={i for i,x in enumerate(ns)if x['page']in pages and 72<=x['top']<755 and 30<=x['left']<574 and CITY.fullmatch(x['text'])}
        check(anchors[sh]==expected,'Every modeled-page city/ZIP anchor accounted '+sh)
    public=[('aetna','aetna-mentalhealth-observations.json'),('humana','humana-public-hospital-observations.json'),('blue','blue-current-family-observations.json')]
    snapshots={}
    for fam,filename in public:
        rs=json.loads((BASE/filename).read_text())
        for r in rs:
            p=ROOT/r['source_path'];s=p.read_text();lines=s.splitlines();snapshots[r['source_path']]=s
            check(filehash(p)==r['source_sha256'],'Public snapshot digest')
            for k,locator in r['locators'].items():
                if fam=='aetna':
                    if'span'in locator and locator['span']is not None:
                        raw=re.match(r'^\s*\d+ (.*)$',lines[locator['text_line']])[1]
                        check(raw==locator['body'],'Aetna locator body')
                        a,z=locator['span'];check(raw[a:z]==r['fields'][k],'Aetna field source '+r['id']+':'+k)
                    else:continue
                else:
                    locs=locator if isinstance(locator,list)else[locator];vals=[]
                    for lc in locs:
                        raw=re.match(r'^\s*\d+ (.*)$',lines[lc['line']])[1];check(raw==lc['body'],'Public locator body');a,z=lc['span'];vals.append(raw[a:z])
                    check((vals if isinstance(locator,list)else vals[0])==r['fields'][k],'Public field source '+r['id']+':'+k)
                counts['public_modeled_fields_compared']+=1
            check(json.loads(db.execute('SELECT fields_json FROM r3_public_observations WHERE id=?',(r['id'],)).fetchone()[0])==r,'Public SQLite/export parity');counts['public_records_compared']+=1
            if fam=='blue':check(r['benefit_year']is None and r['exact_CMS_offering']is None,'Blue year/plan ambiguity stays held')
    aqs=json.loads((BASE/'aetna-mentalhealth-query-accounting.json').read_text());groups=defaultdict(list)
    for q in aqs:groups[q['offering_id']].append(q)
    check(len(groups)==5,'All five Aetna target queries')
    for pid,qs in groups.items():
        check(sorted(q['page']for q in qs)==list(range(1,qs[0]['pages']+1)),'Every Aetna result page')
        totals={n for q in qs for n in q['advertised_counts']}
        check(len(totals)==1 and sum(q['cards']for q in qs)==next(iter(totals)),'Aetna full query cardinality')
    hqs=json.loads((BASE/'humana-public-hospital-accounting.json').read_text());check([q['page']for q in hqs]==[1,2,3]and[q['cards']for q in hqs]==[20,20,10],'Humana whole query accounting')
    # Shared group evidence is compared against the sealed original source
    # lines, including all names and addresses, with no global identity join.
    gs=json.loads((BASE/'published-shared-group-sites.json').read_text());needed={i for g in gs for i in g['name_lines']+g['native_body_lines']};oldlines={}
    for line in gzip.open(PARENT/'followup-r2/pdf-records/source-lines.jsonl.gz','rt'):
        x=json.loads(line)
        if x['source_sha256']==gs[0]['document_sha256']and x['index']in needed:oldlines[x['index']]=x
    for g in gs:
        check(g['name_block_raw']==[oldlines[i]['text']for i in g['name_lines']],'Shared complete name block')
        for a in g['shared_addresses']:
            check(a['street_raw']==' '.join(oldlines[i]['text']for i in a['street_lines']),'Shared street')
            m=CITY.fullmatch(oldlines[a['city_line']]['text']);check(m and [a['city_raw'],a['state_raw'],a['postal_raw']]==[m['city'],m['state'],m['postal']],'Shared city/ZIP')
            if a['phone_line']is not None:check(a['phone_raw']==oldlines[a['phone_line']]['text'],'Shared phone')
            counts['shared_group_sites_compared']+=1
        check(json.loads(db.execute('SELECT fields_json FROM r3_shared_group_sites WHERE id=?',(g['id'],)).fetchone()[0])==g,'Shared group SQLite parity')
    ident=json.loads((BASE/'humana-location-resolution.json').read_text());reg=json.loads((ROOT/ident['registry_source']['path']).read_text())['results'][0]
    check(reg['number']==ident['npi']and reg['addresses'][0]==ident['registry_location']and reg['addresses'][0]['city']=='TAMPA','Exact Humana location identity')
    clinic=(ROOT/ident['clinic_source']['path']).read_text()
    for ev in ident['clinic_HTML_evidence_spans']:
        for m in ev['matches']:
            a,z=m['span'];check(clinic[a:z]==m['raw'],'Clinic source span')
    check(ident['original_values_unchanged']and ident['canonical_city']=='Tampa','Source error retained; canonical city resolved')
    axiom=json.loads((BASE/'axiom-current-identity.json').read_text());reg=json.loads((ROOT/axiom['registry_source']['path']).read_text())['results'][0]
    ai=int(axiom['registry_location_pointer'].rsplit('/',1)[1])
    check(reg['number']==axiom['npi']and reg['basic']['organization_name']==axiom['registry_name']and reg['addresses'][ai]==axiom['registry_location']and reg['addresses'][ai]['address_purpose']=='LOCATION','Exact Axiom registry identity')
    named=json.loads((BASE/'humana-named-network-bindings.json').read_text())
    check(len(named)==8 and len({b['network_key']for b in named})==1,'Unique Humana named medical network')
    for b in named:
        row=parent.execute('SELECT reference_json,state,plan_observation FROM plan_networks WHERE offering_id=?AND network_key=?',(b['offering_id'],b['network_key'])).fetchone()
        check(row is not None and json.loads(row[0])==b['parent_reference']and row[1]=='source_medical_network_reference'and row[2]==b['parent_exact_plan_observation'],'Pinned exact plan/network reference')
        check(b['parent_reference']['display']==b['public_network_raw']=='FL Medicare HMO'and b['benefit_year']==2026,'Exact same-year named medical network')
        ss=(ROOT/b['public_scope_source']).read_text();check('text FL Medicare HMO'in ss and 'text Plan Year 2026'in ss,'Guest selected network/year')
    hospitals=[dict(id=r[0],county=r[1],name=r[2],addresses=json.loads(r[3]))for r in db.execute('SELECT id,county,name,addresses_json FROM hospitals')]
    evs=json.loads((BASE/'new-hospital-plan-evidence.json').read_text());ed=defaultdict(list)
    for e in evs:
        check(e['hospital_id']in match_campus(e['name_raw'],e['street_raw'],e['city_raw'],e['postal_raw'],hospitals),'Campus exact name/address/ZIP')
        if e['source_kind'].startswith('Humana published'):check(e['offering_id']in byp[e['document_sha256']],'Hospital own exact-plan publication binding')
        if e['source_kind'].startswith('Humana explicit'):check(e['named_network_binding']in named and e['offering_id']==e['named_network_binding']['offering_id'],'Hospital explicit named medical network binding')
        ed[e['hospital_id'],e['offering_id']].append(e);counts['new_hospital_evidence_compared']+=1
    for hid,pid,oldstate,oldj in parent.execute('SELECT * FROM hospital_plan_matrix'):
        state,newj=db.execute('SELECT state,evidence_json FROM hospital_plan_matrix WHERE hospital_id=? AND offering_id=?',(hid,pid)).fetchone()
        expected=json.loads(oldj)+ed.get((hid,pid),[]);check(json.loads(newj)==expected,'Hospital evidence additive prefix')
        if(hid,pid)not in ed:check(state==oldstate,'Unchanged hospital state')
        counts['hospital_cells_compared']+=1
    check(db.execute("SELECT state FROM hospital_plan_matrix WHERE hospital_id='AHCA:10107'AND offering_id='2026:H1609:027:000'").fetchone()[0].startswith('published'),'Aetna formerly missing HMO campus resolved')
    summary=json.loads((BASE/'summary.json').read_text())
    check(summary['Aetna_five_plans_Collier_hospital_positive_cells']==35,'All 35 Aetna Collier hospital cells supported')
    check(not summary['full_L08_complete']and not summary['consumer_release_enabled']and not summary['human_accepted'],'Research and release boundaries')
    result=dict(counts,passed=not fail,failures=fail,unexplained_modeled_value_mismatches=len(fail),
      scope='All new/transformed modeled values and retained new PDF pages; whole bounded public queries; immutable parent rows. Candidate name association is not complete person/site reconciliation.',
      full_L08_complete=False,personal_participation_verified=False)
    write(BASE/'validation.json',result);print(json.dumps(result))
    if fail:raise SystemExit(1)

if __name__=='__main__':main()
