"""Full native-field, image-mask, document, denominator and lineage validation."""
import collections,gzip,itertools,json,re,sqlite3,xml.etree.ElementTree as ET
from pypdf import PdfReader
from pypdf.generic import IndirectObject
from l08_r5_common import ROOT,HOME,PARENT,BASE,write,filehash,digest
from l08_r5_normalize import CITY,PID,ICON_MAP,LEGEND,norm
from l08_r5_build import matched_hospitals

def main():
    counts=collections.Counter();fail=[]
    def check(ok,description):
        if not ok:fail.append(description)
    for m in [HOME/'execution-manifest-r1.json',HOME/'followup-r2/manifest.json',HOME/'bootstrap-r3/manifest.json',PARENT/'manifest.json']:
        for rel,meta in json.loads(m.read_text())['files'].items():
            p=ROOT/rel;check(p.exists()and p.stat().st_size==meta['bytes']and filehash(p)==meta['sha256'],'Sealed parent changed '+rel);counts['parent_files_rehashed']+=1
    db=sqlite3.connect('file:'+str(BASE/'providers.sqlite3')+'?mode=ro',uri=True);old=sqlite3.connect('file:'+str(PARENT/'providers.sqlite3')+'?mode=ro',uri=True)
    check(db.execute('PRAGMA integrity_check').fetchone()[0]=='ok','SQLite integrity')
    append={'sources','directory_documents','directory_pages','directory_search','plan_documents'}
    for table, in old.execute("SELECT name FROM sqlite_master WHERE type='table'AND name NOT LIKE 'sqlite_%'AND name NOT LIKE '%_data'AND name NOT LIKE '%_idx'AND name NOT LIKE '%_content'AND name NOT LIKE '%_docsize'AND name NOT LIKE '%_config'"):
        if table=='hospital_plan_matrix':continue
        n=old.execute('SELECT count(*)FROM "'+table+'"').fetchone()[0];nn=db.execute('SELECT count(*)FROM "'+table+'"').fetchone()[0]
        check(nn>=n if table in append else nn==n,'Parent table count '+table)
        for a,b in itertools.zip_longest(old.execute('SELECT * FROM "'+table+'" ORDER BY rowid'),db.execute('SELECT * FROM "'+table+'" ORDER BY rowid LIMIT '+str(n))):
            check(a==b,'Parent row changed '+table);counts['unchanged_parent_rows_compared']+=1
    check(db.execute('SELECT count(*)FROM offerings').fetchone()[0]==72,'72 pinned MA offerings retained')
    owners=json.loads((BASE/'owner-file-observations.json').read_text());check(len(owners)==6 and len({x['sha256']for x in owners})==4,'Six owner files/four unique PDFs')
    for x in owners:
        p=ROOT/x['retained_path'];check(filehash(p)==x['sha256']and p.stat().st_size==x['bytes'],'Owner retained bytes '+x['filename'])
        check(filehash(__import__('pathlib').Path(x['owner_path']))==x['sha256'],'Owner original/copy parity '+x['filename']);counts['owner_files_compared']+=1
    invs=json.loads((BASE/'document-inventory.json').read_text());natives={};imagexml={};readers={}
    for inv in invs:
        sh=inv['sha256'];src=ROOT/inv['path'];check(filehash(src)==sh and src.read_bytes()[:5]==b'%PDF-','Actual source PDF')
        check(filehash(ROOT/inv['text_path'])==inv['text_sha256'],'Complete text digest')
        pages=(ROOT/inv['text_path']).read_text().split('\f');check(len(pages)==inv['pages']+1 and not pages[-1].strip(),'All PDF pages extracted')
        check('2026'in pages[0]and'Collier'in pages[0]and'09/23/2026'in pages[0]and inv['source_partial_explicit'],'Actual year/county/date/partial scope')
        for pg,t in enumerate(pages[:-1],1):
            check(db.execute('SELECT text,text_sha256 FROM directory_pages WHERE document_sha256=?AND page=?',(sh,pg)).fetchone()==(t,digest(t.encode())),'Complete page/DB text');counts['PDF_pages_compared']+=1
        check(json.loads(db.execute('SELECT metadata_json FROM directory_documents WHERE sha256=?',(sh,)).fetchone()[0])==inv,'Document metadata/DB')
        ns=[json.loads(s)for s in gzip.open(ROOT/inv['native_path'],'rt')];natives[sh]=ns
        check(filehash(ROOT/inv['native_path'])==inv['native_sha256']and filehash(ROOT/inv['xml_path'])==inv['xml_sha256'],'Native/XML source hashes')
        fonts={};seen=0
        with gzip.open(ROOT/inv['xml_path'],'rb')as f:
            for _,page in ET.iterparse(f,events=['end']):
                if page.tag!='page':continue
                pg=int(page.attrib['number'])
                for font in page.findall('fontspec'):fonts[font.attrib['id']]=dict(font.attrib)
                for j,e in enumerate(page.findall('text')):
                    t=''.join(e.itertext()).strip()
                    if not t:continue
                    expected={'page':pg,'node':j,'text':t,'top':float(e.attrib['top']),'left':float(e.attrib['left']),'width':float(e.attrib['width']),
                        'height':float(e.attrib['height']),'font':fonts[e.attrib['font']],'bold':e.find('b')is not None,'italic':e.find('i')is not None}
                    check(ns[seen]==expected,'Full native/XML text node');seen+=1;counts['native_XML_nodes_compared']+=1
                for j,e in enumerate(page.findall('image')):imagexml[sh,pg,j]=dict(e.attrib)
                page.clear()
        check(seen==len(ns)==inv['native_nodes'],'Complete native node population')
        readers[sh]=PdfReader(src)
    check(counts['PDF_pages_compared']==1428,'Unique page denominator 1,428')
    imagecheck=json.loads((BASE/'image-extraction-validation.json').read_text());check(imagecheck['passed']and imagecheck['PDF_graphics_positions_independently_compared']==36291,'Independent PDF image draw/geometry check')
    assetmeta={a['asset_key']:a for a in json.loads((BASE/'image-asset-inventory.json').read_text())};imgs=collections.defaultdict(list);objseen=set()
    for s in gzip.open(BASE/'image-occurrences.jsonl.gz','rt'):
        r=json.loads(s);sh=r['document_sha256'];ix=len(imgs[sh]);imgs[sh].append(r);key=r['asset_key'];meta=assetmeta[key]
        xml=imagexml[sh,r['page'],r['XML_image_node']]
        check(r['geometry']=={k:float(xml[k])for k in ['left','top','width','height']},'Image XML geometry')
        check(max(abs(r['geometry'][k]-r['PDF_geometry'][k])for k in r['geometry'])<=1.1,'Image PDF graphics position independent of XML')
        check(filehash(__import__('pathlib').Path(xml['src']))==r['XML_image_sha256'],'Poppler image bytes')
        ref=(sh,*r['source_ref'])
        if ref not in objseen:
            obj=readers[sh].get_object(IndirectObject(r['source_ref'][0],r['source_ref'][1],readers[sh]));md=obj.get('/Mask');md=md.get_object()if hasattr(md,'get_object')else md
            mask=md.get_data()if hasattr(md,'get_data')else b''
            check(digest(obj.get_data())==r['pixels_sha256']and(digest(mask)if mask else None)==r['mask_sha256'],'Exact PDF color pixels and hard mask')
            check(filehash(BASE/'image-assets'/(key+'.pixels.bin'))==r['pixels_sha256'],'Retained source image pixels')
            if mask:check(filehash(BASE/'image-assets'/(key+'.mask.bin'))==r['mask_sha256'],'Retained source hard mask')
            objseen.add(ref);counts['PDF_image_objects_reconciled']+=1
        check(json.loads(db.execute('SELECT fields_json FROM r5_image_occurrences WHERE document_sha256=?AND image_index=?',(sh,ix)).fetchone()[0])==r,'Image occurrence/DB parity')
        counts['image_occurrences_compared']+=1
    accounts=json.loads((BASE/'extraction-accounting.json').read_text());acby={a['document_sha256']:a for a in accounts};used=collections.defaultdict(set);usedimg=collections.defaultdict(set);records={};ownedcity=collections.defaultdict(set);ownedids=collections.defaultdict(set)
    def literal(sh,nodes):return' '.join(natives[sh][k]['text']for k in nodes)or None
    for s in gzip.open(BASE/'wellcare-records.jsonl.gz','rt'):
        r=json.loads(s);sh=r['document_sha256'];ns=natives[sh];records[r['id']]=r
        nodes=r['name_nodes']+r['body_nodes'];check(not(used[sh]&set(nodes)),'Nonoverlapping source listing text');used[sh].update(nodes)
        check(r['name_raw']==literal(sh,r['name_nodes'])and r['body_raw']==[ns[k]['text']for k in r['body_nodes']],'Every name/body value')
        counts['listing_name_values_compared']+=1;counts['listing_body_values_compared']+=len(r['body_nodes'])
        check(r['practice_raw']==literal(sh,r['practice_nodes'])and r['specialty_raw']==literal(sh,r['specialty_nodes']),'Practice and specialty literal values')
        check(r['section_raw']==literal(sh,r['section_nodes'])and r['county_raw']==ns[r['county_node']]['text'],'Section/county source context')
        for field in ['publisher_identifiers','gender_raw','phones_raw','websites_raw','hours_raw','PCMH_raw','tiers_raw','other_source_text','section_conditions']:
            for x in r[field]:
                check(x['raw']==ns[x['node']]['text'],'Modeled source field '+field);counts['modeled_literal_values_compared']+=1
        for x in r['publisher_identifiers']:
            check(PID.fullmatch(x['raw'])[1]==x['value'],'Source publisher ID');ownedids[sh].add(x['node'])
        for a in r['addresses']:
            check(a['street_raw']==literal(sh,a['street_nodes'])and a['city_line_raw']==literal(sh,a['city_nodes']),'Exact street and city line source')
            m=CITY.fullmatch(a['city_line_raw']);check(m is not None and list(m.groups())==[a['city_raw'],a['state_raw'],a['postal_raw']],'All source city/state/ZIP values')
            ownedcity[sh].update(a['city_nodes']);counts['source_sites_compared']+=1
        for l in r['languages_raw']:check(l['raw']==literal(sh,l['nodes']),'Language/source wrapped text');counts['language_values_compared']+=1
        check(not(usedimg[sh]&set(r['image_indices'])),'Each medical image owned once');usedimg[sh].update(r['image_indices'])
        for icon in r['published_icons']:
            image=imgs[sh][icon['image_index']];flag=ICON_MAP.get(image['asset_key'])
            check(icon['asset_key']==image['asset_key']and icon['flag']==flag,'Exact masked icon interpretation')
            if flag:
                legend=icon['legend'];check(norm(ns[legend['native_node']]['text'])==norm(LEGEND[flag])and legend['page']==7,'Source legend meaning')
            counts['medical_icon_values_compared']+=1
        check(r['symbol_flags']=={flag:True if any(x['flag']==flag for x in r['published_icons'])else None for flag in LEGEND},'Missing icons remain unknown, not negative')
        check(r['npi']is None and r['provider_relationship_period']is None and r['personal_participation_verified']is False,'No invented NPI, relationship period or personal guarantee')
        check(json.loads(db.execute('SELECT fields_json FROM r5_wellcare_records WHERE id=?',(r['id'],)).fetchone()[0])==r,'Every listing database/export parity');counts['listing_records_compared']+=1
    discrepancies=[]
    for a in accounts:
        sh=a['document_sha256'];ns=natives[sh];scopes={p['page']:p for p in a['page_scopes']}
        expected={k for k,x in enumerate(ns)if x['page']in scopes and scopes[x['page']]['body_top']<=x['top']<731 and 40<=x['left']<580}
        check(not(used[sh]&set(a['context_nodes']))and used[sh]|set(a['context_nodes'])==expected,'Every medical-column text node accounted')
        cityset={k for k in expected if CITY.fullmatch(ns[k]['text'])};check(cityset<=ownedcity[sh],'Every visible city/ZIP anchor has a record')
        idset={k for k,x in enumerate(ns)if PID.fullmatch(x['text'])and x['page']!=7};check(idset==ownedids[sh],'Every printed medical publisher ID captured')
        expectedimg={i for i,x in enumerate(imgs[sh])if x['page']in scopes and scopes[x['page']]['body_top']<=x['geometry']['top']<731 and 40<=x['geometry']['left']<580}
        check(not(usedimg[sh]&set(a['image_context_indices']))and usedimg[sh]|set(a['image_context_indices'])==expectedimg,'Every medical image accounted')
        for t in a['totals']:
            observed=sum(r['document_sha256']==sh and r['section_raw']==t['section_raw']for r in records.values())
            check(observed==t['listing_blocks'],'Independent section listing count')
            for k in t['source_total_nodes']:check(int(ns[k]['text'].split(':')[1])in t['advertised_totals'],'Publisher total exact source value')
            if t['advertised_totals']!=[observed]:discrepancies.append({'document_sha256':sh,'section_raw':t['section_raw'],'published_totals':t['advertised_totals'],'observed_visible_listings':observed,'difference':t['advertised_totals'][0]-observed,'status':'unresolved publisher-total definition/count discrepancy; not an invented missing-provider count'})
        check(json.loads(db.execute('SELECT fields_json FROM r5_document_accounting WHERE document_sha256=?',(sh,)).fetchone()[0])==a,'Document accounting/DB parity')
        counts['medical_column_nodes_accounted']+=len(expected)
    check(len(discrepancies)==4 and sum(d['difference']for d in discrepancies)==8,'Four explicitly held publisher count discrepancies')
    write(BASE/'publisher-count-discrepancies.json',discrepancies)
    bindings=json.loads((BASE/'plan-directory-bindings.json').read_text());check(len(bindings)==6 and len({b['offering_id']for b in bindings})==6,'All six exact Wellcare offerings accounted')
    for b in bindings:
        inv=next(i for i in invs if i['sha256']==b['document_sha256']);cover=(ROOT/inv['text_path']).read_text().split('\f')[0]
        check(cover[slice(*b['name_span'])]==b['source_plan_name']and cover[slice(*b['Collier_span'])]=='Collier','Exact cover name/geography spans')
        matches=list(db.execute('SELECT id FROM offerings WHERE name=?',(b['source_plan_name'],)))
        check(matches==[(b['offering_id'],)]and not b['CMS_ID_printed_in_directory'],'Unique pinned Collier name bridge, not an invented printed CMS ID')
        check(json.loads(db.execute('SELECT fields_json FROM r5_plan_directory_bindings WHERE offering_id=?AND document_sha256=?',(b['offering_id'],b['document_sha256'])).fetchone()[0])==b,'Binding database parity');counts['plan_directory_bindings_compared']+=1
    evidence=json.loads((BASE/'new-hospital-evidence.json').read_text());grouped=collections.defaultdict(list)
    for e in evidence:
        r=records[e['record_id']];check(e['hospital_id']in matched_hospitals(r)and r['section_raw']=='Hospitals','Hospital source scope and exact campus rule')
        check(e['plan_binding']in bindings and e['name_raw']==r['name_raw']and e['address']in r['addresses'],'Hospital evidence exact source values')
        grouped[e['hospital_id'],e['offering_id']].append(e);counts['new_hospital_evidence_compared']+=1
    for hid,pid,state,raw in old.execute('SELECT * FROM hospital_plan_matrix'):
        new=db.execute('SELECT state,evidence_json FROM hospital_plan_matrix WHERE hospital_id=?AND offering_id=?',(hid,pid)).fetchone();oe=json.loads(raw);ne=json.loads(new[1])
        check(ne[:len(oe)]==oe and ne[len(oe):]==grouped.get((hid,pid),[]),'Hospital parent evidence exact prefix and additions')
        if(hid,pid)not in grouped:check(new[0]==state,'Unchanged unmatched hospital cell')
        counts['hospital_matrix_cells_compared']+=1
    check(counts['listing_records_compared']==counts['source_sites_compared']==14158,'All 14,158 observed listing/site records')
    result={'passed':not fail,'failures':fail,'counts':dict(counts),'all_modeled_literal_fields_source_compared':True,
        'published_header_totals_fully_reconciled':False,'known_publisher_count_discrepancies':discrepancies,
        'all_visible_medical_address_and_identifier_anchors_accounted':True,'document_acquisition_gap_closed_for_six_Wellcare_offerings':True,
        'comprehensive_network_complete':False,'full_L08_complete':False,'human_accepted':False,'consumer_release_enabled':False}
    write(BASE/'validation.json',result);print(json.dumps({'passed':not fail,'failures':fail[:20],'counts':dict(counts),'publisher_count_discrepancy_total':8}),flush=True)
    if fail:raise SystemExit(1)

if __name__=='__main__':main()
