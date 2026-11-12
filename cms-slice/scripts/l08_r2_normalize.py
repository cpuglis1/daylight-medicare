#!/usr/bin/env python3
"""Normalize retained L08 publications and exact public Aetna query observations.

The parent snapshot remains immutable. Clinical applicability stays unknown.
Every copied or interpreted field retains source lines or XML/AX locators.
"""
from collections import Counter,defaultdict
import gzip
from itertools import groupby
import json
import re
import sqlite3
from l08_r2_common import BASE,PARENT,ROOT,write,digest
from l08_integrate import normalized

NATIVE=BASE/'pdf-records'
LABELS=re.compile(r'^(Provider Language\(s\)|Language\(s\)|Languages|Provider Speaks|Cultural Capabilities|Ethnicity|Medical Group|Hospital Affiliations|Hours|Web Address|State License\s*#|Primary Care ID)\s*[:#]?\s*(.*)$',re.I)
LABEL_TYPES={'provider language(s)':'language','language(s)':'language','languages':'language','provider speaks':'language','cultural capabilities':'cultural_capabilities','ethnicity':'published_ethnicity','medical group':'medical_group','hospital affiliations':'hospital_affiliations','hours':'hours','web address':'website_raw','state license #':'state_license','primary care id':'primary_care_id'}
LOCAL_CITIES={'naples','marcoisland','immokalee','avemaria','evergladescity','chokoloskee','goodland','copeland','ochopee','vanderbiltbeach'}
HS_MARKERS={('38','«'):'Accepts Medicare and Medicaid',('39','P'):'Existing patients only with provider approval',('40','x'):'Not accepting new patients',('41','\ue77b'):'Telehealth and in-office service available',('39',"'"):'Telehealth only; no in-office services available',('42','é'):'Accessible to customers with disabilities',('42','ë'):'Completed cultural competency training',('40','Y'):'Inclusive care provider'}
ERICKSON_CODES={'1':'Closed to new enrollment','2':'Accepting existing patients only','3':'Board Certified','4':'Practice Limitations','8':'Handicap Accessible','9':'Cultural Competency Training','10':'Essential Community Provider'}
AETNA_MARKERS={'¨':'Accepting current patients only','†':'Board certified','<':'Filled to capacity at this time','\uf03a':'Provides telehealth services','*':'Accepts Medicaid'}


def ax_nodes(text):
    nodes=[];stack=[]
    for line_index,line in enumerate(text.splitlines()):
        m=re.match(r'^(\s*)(\d+) (.*)$',line)
        if not m:continue
        depth=len(m[1]);node={'id':int(m[2]),'line':line_index,'depth':depth,'body':m[3],'parent':None,'end':None}
        while stack and nodes[stack[-1]]['depth']>=depth:nodes[stack.pop()]['end']=len(nodes)
        if stack:node['parent']=stack[-1]
        stack.append(len(nodes));nodes.append(node)
    for i in stack:nodes[i]['end']=len(nodes)
    return nodes


def aetna_records(path):
    text=path.read_text();nodes=ax_nodes(text);name=path.name
    m=re.fullmatch(r'([H]\d{4})-(\d{3})-(hospital|pcp)-(\d+)mi-page(\d+)\.ax\.txt',name)
    if not m:return [],None
    plan='2026:'+m[1]+':'+m[2]+':000';category=m[3];radius=int(m[4]);page=int(m[5])
    pagination=re.search(r'Page (\d+) of (\d+)',text)
    if not pagination or int(pagination[1])!=page:raise ValueError('AX file/page mismatch '+name)
    expected_id=m[1]+'-'+m[2]
    if not re.search(r'button Aetna Medicare[^\n]*'+expected_id,text)or f'Located Within, {radius} Miles'not in text:raise ValueError('AX scope mismatch '+name)
    advertised=[]
    for n in nodes:
        found=re.search(r'There are (\d+) (more in-network matches|results for)',n['body'])
        if found:advertised.append(int(found[1])+(3 if found[2]=='more in-network matches'else 0))
    seen=set();records=[]
    for i,node in enumerate(nodes):
        if not(node['body'].startswith('heading ')and re.search(r'Value: 2(?:,|$)',node['body'])):continue
        names=[n for n in nodes[i+1:node['end']]if n['body'].startswith('text ')]
        if not names:continue
        heading_name=names[0]['body'][5:]
        j=node['parent']
        while j is not None:
            parent=nodes[j]
            # NPI is optional in the public presentation. A publisher provider
            # ID and exact site still constitute a retained directory record.
            if parent['body'].startswith('container '+heading_name):break
            j=parent['parent']
        if j is None or j in seen:continue
        seen.add(j);card=nodes[j:nodes[j]['end']];header=nodes[j]['body'][len('container '):]
        fields={};locators={}
        def put(key,value,n,subspan=None):
            fields[key]=value;locators[key]={'ax_node':n['id'],'text_line':n['line'],'body':n['body'],'span':subspan}
        put('name_raw',names[0]['body'][5:],names[0],[5,len(names[0]['body'])])
        put('listing_header_raw',header,nodes[j],[len('container '),len(nodes[j]['body'])])
        location=re.search(r', ([A-Za-z][A-Za-z .’\'-]+), ([A-Z]{2}) (\d{5}(?:-\d{4})?)$',header)
        if location:
            for key,k in [('city',1),('state',2),('postal_code',3)]:
                start,end=location.span(k);put(key,location[k],nodes[j],[len('container ')+start,len('container ')+end])
            prefix=header[:location.start()];street=re.search(r', ((?:\d|P\.?O\.? Box|Virtual|Tele).*)$',prefix)
            if street:
                start,end=street.span(1);put('street_raw',street[1],nodes[j],[len('container ')+start,len('container ')+end])
        for k,n in enumerate(card):
            body=n['body']
            if body.startswith('text NPI ID:')or body.startswith('text Provider ID:')or body.startswith('text Primary Care ID:'):
                key='npi'if'NPI ID:'in body else'primary_care_id'if'Primary Care ID:'in body else'publisher_provider_id'
                for nxt in card[k+1:k+4]:
                    found=re.fullmatch(r'text\s+(\d+)',nxt['body'])
                    if found:put(key,found[1],nxt,[found.start(1),found.end(1)]);break
            if body.startswith('text ')and 'In Network'in body:
                put('published_network_label',body[5:],n,[5,len(body)])
            if body.startswith('text ')and(body.startswith('text Accepting New Patients')or body.startswith('text Not Accepting New Patients')):
                put('published_acceptance_text',body[5:],n,[5,len(body)])
            if body.startswith('text As of '):put('published_future_change_text',body[5:],n,[5,len(body)])
            if body=='text Virtual Office':put('office_kind_raw','Virtual Office',n,[5,len(body)])
            if body.startswith('image Wheelchair accessible location'):put('published_accessibility_label',body[len('image '):],n,[len('image '),len(body)])
            if body.startswith('link Description: Call '):
                found=re.search(r'Description: Call ([^,]+), Value:',body)
                if found:put('phone_raw',found[1],n,list(found.span(1)))
        # Specialty labels remain publisher text, including '(n more specialties)'.
        for n in card:
            if n['line']<=names[0]['line']or not n['body'].startswith('text '):continue
            value=n['body'][5:]
            if value==fields['name_raw']or value.startswith(('In Network','Accepting','Not Accepting','Provider ID','Primary Care ID','NPI ID')):continue
            if any(t in value for t in ['Practice','Medicine','Hospital','Physician','Nurse','Therap','Surgery','Cardiol','Pediatr','Clinic','Neurol','Dermat','Gastro','Orthop','Pathol']):
                put('specialty_or_role_raw',value,n,[5,len(n['body'])]);break
        fields['has_unexpanded_multiple_locations']=any('View All Locations'in n['body']for n in card)
        wrapper=nodes[j]['parent']
        affiliation_nodes=[]
        if wrapper is not None and re.fullmatch(r'container [a-f0-9-]{36}',nodes[wrapper]['body']):
            affiliation_nodes=[n for n in nodes[wrapper:nodes[wrapper]['end']]if n['body'].startswith('link Description: ')and('/provider-group/'in n['body']or'/ipa/'in n['body'])]
        for no,n in enumerate(affiliation_nodes,1):put('published_group_affiliation_raw_'+str(no),n['body'],n,[0,len(n['body'])])
        fields['personal_participation_guaranteed']=False
        rid=digest((name+'\n'+str(nodes[j]['id'])).encode())
        records.append({'id':rid,'offering_id':plan,'category':category,'radius_miles':radius,'query_page':page,
            'source_path':str(path.relative_to(ROOT)),'source_sha256':digest(path.read_bytes()),'source_card_root':nodes[j]['id'],
            'fields':fields,'locators':locators,'state':'published_exact_plan_query_observation; all-specialty and all-location completeness unknown',
            'observation_date':'2026-10-27','benefit_year':2026})
    return records,{'offering_id':plan,'category':category,'radius_miles':radius,'page':page,'pages':int(pagination[2]),'cards':len(records),'advertised_counts':sorted(set(advertised)),'source_path':str(path.relative_to(ROOT))}


def aetna_hospital_detail(path):
    """Read an explicitly expanded exact-plan panel, never an unexpanded name."""
    text=path.read_text();nodes=ax_nodes(text);m=re.fullmatch(r'(rehab|axiom)-detail-([H]\d{4})-(\d{3})\.ax\.txt',path.name)
    if not m:return None
    if 'This provider can’t be displayed'in text:return None
    short=m[2]+'-'+m[3];pid='2026:'+m[2]+':'+m[3]+':000';fields={};locators={}
    def put(k,v,n,span):fields[k]=v;locators[k]={'ax_node':n['id'],'text_line':n['line'],'body':n['body'],'span':span}
    h1=next(n for n in nodes if n['body'].startswith('heading ')and'Value: 1'in n['body'])
    name_node=next(n for n in nodes if n['parent']==nodes.index(h1)and n['body'].startswith('text '))
    put('name_raw',name_node['body'][5:],name_node,[5,len(name_node['body'])])
    for n in nodes:
        b=n['body']
        found=re.search(r'Provider ID:\s*(\d+)\s+NPI ID:\s*(\d+)',b)
        if found:
            put('publisher_provider_id',found[1],n,list(found.span(1)));put('npi',found[2],n,list(found.span(2)))
        addr=re.search(r'^link Description: (.+?), ([A-Za-z .’\'-]+), ([A-Z]{2}) (\d{5}) - ',b)
        if addr:
            for key,k in [('street_raw',1),('city',2),('state',3),('postal_code',4)]:put(key,addr[k],n,list(addr.span(k)))
        phone=re.search(r'^link Description: Call ([^,]+), Value:',b)
        if phone:put('phone_raw',phone[1],n,list(phone.span(1)))
        if b.startswith('text Office Staff:'):put('office_languages_raw',b[5:],n,[5,len(b)])
        if b.startswith('text Wheelchair Access to'):put('published_accessibility_label',b[5:],n,[5,len(b)])
    # The preview block supplies the selected plan. Other plans require their
    # own expanded panel with an explicit Network Status, not the heading count.
    preview=next((n for n in nodes if n['body'].startswith('text Aetna Medicare')and short in n['body']and'Network Status In Network'in n['body']),None)
    if preview:put('published_plan_network_text',preview['body'],preview,[0,len(preview['body'])])
    else:
        panel=next((n for n in nodes if n['body'].startswith('container Aetna Medicare')and short in n['body']),None)
        if panel is None:raise ValueError('Exact plan not expanded '+path.name)
        block=nodes[nodes.index(panel):panel['end']]
        if not any(n['body']=='text Network Status'for n in block)or not any(n['body']=='text In Network'for n in block):raise ValueError('No explicit plan network assertion '+path.name)
        fields['published_plan_network_text']=' '.join(n['body']for n in block)
        locators['published_plan_network_text']={'mode':'join_nodes','ax_nodes':[n['id']for n in block],'text_lines':[n['line']for n in block],'separator':' '}
    fields['personal_participation_guaranteed']=False;fields['has_unexpanded_multiple_locations']=False
    return {'id':digest(path.name.encode()),'offering_id':pid,'category':'hospital_detail','radius_miles':None,'query_page':None,
        'source_path':str(path.relative_to(ROOT)),'source_sha256':digest(path.read_bytes()),'fields':fields,'locators':locators,
        'benefit_year':2026,'observation_date':'2026-10-27','year_provenance':'Same public 2026 Medicare plan selection retained in aetna-ui/*plan-options.ax.txt',
        'state':'published_exact_plan_hospital_detail; personal applicability unknown'}


def main():
    if(BASE/'SEALED').exists():raise ValueError('Sealed revision')
    target=BASE/'providers.sqlite3'
    if target.exists():target.unlink()
    db=sqlite3.connect(target);parent=sqlite3.connect('file:'+str(PARENT/'build-r1/providers.sqlite3')+'?mode=ro',uri=True)
    parent.backup(db);parent.close()
    db.executescript('''DROP TABLE pdf_records;DROP TABLE pdf_address_fragments;
        CREATE TABLE pdf_records(id TEXT PRIMARY KEY,document_sha256 TEXT,family TEXT,identifier_kind TEXT,identifier TEXT,name_raw TEXT,page INTEGER,state TEXT,domain TEXT,fields_json TEXT);
        CREATE TABLE pdf_address_fragments(document_sha256 TEXT,page INTEGER,line INTEGER,text TEXT,state TEXT);
        CREATE TABLE published_qualifiers(record_id TEXT,kind TEXT,value TEXT,evidence_json TEXT);
        CREATE TABLE partial_address_observations(record_id TEXT,document_sha256 TEXT,fields_json TEXT,state TEXT);
        CREATE TABLE pdf_site_resolution(record_id TEXT,state TEXT,fields_json TEXT);
        CREATE TABLE aetna_query_observations(id TEXT PRIMARY KEY,offering_id TEXT,category TEXT,source_path TEXT,fields_json TEXT);
        CREATE TABLE aetna_query_accounting(offering_id TEXT,category TEXT,radius INTEGER,fields_json TEXT);
        CREATE TABLE r2_identity_evidence(npi TEXT,source_id TEXT,fields_json TEXT);
        CREATE TABLE aetna_identity_resolution(record_id TEXT,identity_state TEXT,fields_json TEXT);
        CREATE TABLE r2_native_source_coverage(document_sha256 TEXT,fields_json TEXT);
    ''')
    records_stream=iter(gzip.open(NATIVE/'records.jsonl.gz','rt'))
    grouped_records=groupby((json.loads(x)for x in records_stream),key=lambda r:r['document_sha256'])
    line_stream=groupby((json.loads(x)for x in gzip.open(NATIVE/'source-lines.jsonl.gz','rt')),key=lambda r:r['source_sha256'])
    stats=Counter();doc_stats=[];frag=[]
    summaries={x['document_sha256']:x for x in json.loads((NATIVE/'summary.json').read_text())}
    with gzip.open(BASE/'normalized-pdf-records.jsonl.gz','wt')as output:
        for(sh,rs),(line_sh,line_rows)in zip(grouped_records,line_stream):
            if sh!=line_sh:raise ValueError('Record/line stream order changed')
            lines=list(line_rows);rs=list(rs);stats['native_source_lines']+=len(lines)
            candidates=summaries[sh]['unassigned_city_state_postal_lines'];by_city={x['line']:x for x in candidates}
            occupied={};dcount=Counter();site_index=defaultdict(list);needs_site=[]
            name_indices={i for r in rs for i in r['name_source_lines']};source_headings={};last_heading=None
            family=rs[0]['family']if rs else''
            for i,line in enumerate(lines):
                fonts={p['font']for p in line['parts']};text=line['text']
                is_header=(family=='aetna'and'13'in fonts and text!='FLORIDA')or(family=='healthspring'and'34'in fonts and text.isupper()and i not in name_indices)or(family=='erickson'and bool(fonts&{'49','59','68','77','87'}))
                if is_header:last_heading={'value_raw':text,'source_lines':[i],'kind':'source_section_heading_raw','interpretation':'Publisher section context; no new clinical taxonomy or personal applicability inferred'}
                source_headings[i]=last_heading
            for r in rs:
                start,end=r['native_line_range'];qualifiers=[];partial=[]
                if source_headings.get(start):qualifiers.append(source_headings[start])
                identifier_occurrences=[]
                for i in range(start,end):
                    line=lines[i];text=line['text'];m=LABELS.match(text)
                    for kind,pattern in [('npi',r'\bNPI\s*(?:#|:)?\s*(\d{10})\b'),('publisher_provider_id',r'\b(?:Provider ID:|ID#)\s*([A-Z0-9]+)')]:
                        for match in re.finditer(pattern,text):identifier_occurrences.append({'kind':kind,'value':match[1],'source_line':i,'span':list(match.span(1))})
                    if m:
                        kind=LABEL_TYPES.get(m[1].casefold(),'publisher_labeled_field');indices=[i]
                        # Wrapped values are retained only through ordinary body
                        # lines, stopping at another label/address/ID or name style.
                        for j in range(i+1,min(end,i+5)):
                            nxt=lines[j]
                            if nxt['page']!=line['page']or nxt['column']!=line['column']or LABELS.match(nxt['text'])or re.search(r'^(?:NPI|ID#|P:|Provider ID:|Primary Care ID:|\d)|,\s*[A-Z]{2}\s*\d{5}',nxt['text'])or nxt['bold']!=line['bold']:break
                            if any(p['font']in(['34']if r['family']=='healthspring'else ['5']if r['family']=='aetna'else [])for p in nxt['parts']):break
                            indices.append(j)
                        qualifiers.append({'kind':kind,'value_raw':' '.join(lines[k]['text']for k in indices),'source_lines':indices,'interpretation':'Publisher-labeled text; no personal applicability inferred'})
                    if i in by_city:
                        # A missing conventional street does not erase a printed
                        # city/ZIP. Preserve the fragment and local context.
                        context=list(range(max(start,i-3),min(end,i+3)))
                        part={'city_state_postal_raw':text,'source_line':i,'page':line['page'],'context_source_lines':context,
                              'context_raw':[lines[k]['text']for k in context],
                              'state':'published_partial_or_nonstandard_address; precise street association not inferred'}
                        partial.append(part);occupied[i]=r['id']
                # Decode only symbols with a verified, pinned document legend.
                for i in r['name_source_lines']:
                    for p in lines[i]['parts']:
                        if r['family']=='healthspring'and(p['font'],p['text'])in HS_MARKERS:
                            qualifiers.append({'kind':'published_symbol','value_raw':p['text'],'meaning':HS_MARKERS[(p['font'],p['text'])],'source_lines':[i],'source_node':p['node'],'page':p['page'],'font':p['font'],'legend_document':sh,'legend_page':19})
                        name_height=max((x['height']for k in r['name_source_lines']for x in lines[k]['parts']),default=0)
                        if r['family']=='erickson'and re.fullmatch(r'[\d, .]+',p['text'])and p['height']<name_height*.9:
                            for code in re.findall(r'\d+',p['text']):
                                if code in ERICKSON_CODES:qualifiers.append({'kind':'published_symbol','value_raw':code,'meaning':ERICKSON_CODES[code],'source_lines':[i],'source_node':p['node'],'page':p['page'],'font':p['font'],'legend_document':sh,'legend_basis':'Complete published directory footer; code retained verbatim'})
                        if r['family']=='aetna':
                            for char,meaning in AETNA_MARKERS.items():
                                if char in p['text']:qualifiers.append({'kind':'published_symbol','value_raw':char,'meaning':meaning,'source_lines':[i],'source_node':p['node'],'page':p['page'],'font':p['font'],'legend_document':sh,'legend_page':29 if char=='*'else 15})
                r['published_qualifiers']=qualifiers;r['partial_addresses']=partial;r['native_identifier_occurrences']=identifier_occurrences
                pcids={m[1]for q in qualifiers if q['kind']=='primary_care_id'for m in [re.search(r'Primary Care ID:\s*(\d+)',q['value_raw'])]if m}
                if r['identifier_kind']=='publisher_provider_id'and r['identifier']and len(pcids)==1:
                    identity=(r['identifier'],next(iter(pcids)))
                    if r['addresses']:site_index[identity].append(r)
                    else:needs_site.append((r,identity))
                r['geographic_priority']='published_Collier_city_candidate'if any(normalized(a['city'])in LOCAL_CITIES for a in r['addresses'])or any(any(city in normalized(a['city_state_postal_raw'])for city in LOCAL_CITIES)for a in partial)else'other_or_unknown_location'
                r['physical_county_verified_from_city_alone']=False
                if not r['addresses']:
                    if partial:r['state']='source_partial_address; precise site unknown'
                    elif r['family']=='aetna'and r['identifier_kind']=='publisher_provider_id':r['state']='published_name_or_group_header_with_id; no explicit street in this unit'
                    else:r['state']='source_context_or_listing_without_normalized_site; classification retained'
                # Store all source context even when normalized values remain held.
                for q in qualifiers:db.execute('INSERT INTO published_qualifiers VALUES(?,?,?,?)',(r['id'],q['kind'],q.get('meaning',q['value_raw']),json.dumps(q,ensure_ascii=False)))
                for p in partial:db.execute('INSERT INTO partial_address_observations VALUES(?,?,?,?)',(r['id'],sh,json.dumps(p,ensure_ascii=False),p['state']))
                db.execute('INSERT INTO pdf_records VALUES(?,?,?,?,?,?,?,?,?,?)',(r['id'],sh,r['family'],r['identifier_kind'],r['identifier'],r['provider_display_raw'],r['anchor_page'],r['state'],r['listing_domain'],json.dumps(r,ensure_ascii=False)))
                output.write(json.dumps(r,ensure_ascii=False)+'\n');stats['native_pdf_listing_units']+=1;stats['typed_qualifier_observations']+=len(qualifiers);stats['partial_address_observations']+=len(partial);stats['collier_city_priority_units']+=r['geographic_priority']=='published_Collier_city_candidate';dcount[r['state']]+=1
            for x in candidates:
                state='associated_partial_address_with_native_listing'if x['line']in occupied else'preserved_context_fragment_outside_listing; no provider association invented'
                db.execute('INSERT INTO pdf_address_fragments VALUES(?,?,?,?,?)',(sh,x['page'],x['line'],x['text'],state));frag.append({'document':sh,**x,'state':state,'record_id':occupied.get(x['line'])})
            for r,identity in needs_site:
                matches=site_index.get(identity,[]);sites={json.dumps({k:a[k]for k in ['street_raw','city','state','postal_code']},sort_keys=True)for item in matches for a in item['addresses']}
                state='same_document_exact_provider_and_primary_care_ID_resolves_unique_reprinted_site'if len(sites)==1 else'held_multiple_or_no_sites_for_exact_source_identity'
                result={'record_id':r['id'],'document_sha256':sh,'publisher_provider_id':identity[0],'primary_care_id':identity[1],'state':state,
                    'resolved_site':json.loads(next(iter(sites)))if len(sites)==1 else None,'source_record_ids':[x['id']for x in matches],
                    'original_listing_unit_remains_unchanged':True,'personal_participation_verified':False}
                db.execute('INSERT INTO pdf_site_resolution VALUES(?,?,?)',(r['id'],state,json.dumps(result)))
            detail={'document_sha256':sh,'listing_states':dict(dcount),'source_lines':len(lines),'unassigned_candidate_count':len(candidates),'associated_partial_addresses':len(occupied),'all_published_fields_semantically_normalized':False}
            doc_stats.append(detail);db.execute('INSERT INTO r2_native_source_coverage VALUES(?,?)',(sh,json.dumps(detail)))
    write(BASE/'address-fragment-dispositions.json',frag);write(BASE/'pdf-normalization-by-document.json',doc_stats)
    queries=defaultdict(list);aetna=[]
    for path in sorted((BASE/'aetna-ui').glob('*-page*.ax.txt')):
        rows,query=aetna_records(path)
        if not query:continue
        queries[(query['offering_id'],query['category'],query['radius_miles'])].append(query)
        for r in rows:
            aetna.append(r);db.execute('INSERT INTO aetna_query_observations VALUES(?,?,?,?,?)',(r['id'],r['offering_id'],r['category'],r['source_path'],json.dumps(r,ensure_ascii=False)))
    detail_failures=[]
    for path in sorted((BASE/'aetna-ui').glob('*-detail-*.ax.txt')):
        r=aetna_hospital_detail(path)
        if r:aetna.append(r);db.execute('INSERT INTO aetna_query_observations VALUES(?,?,?,?,?)',(r['id'],r['offering_id'],r['category'],r['source_path'],json.dumps(r,ensure_ascii=False)))
        else:detail_failures.append({'source_path':str(path.relative_to(ROOT)),'sha256':digest(path.read_bytes()),'state':'Targeted provider cannot be displayed; not evidence of out-of-network status','participation_conclusion':'unknown'})
    write(BASE/'targeted-detail-failures.json',detail_failures)
    accounting=[]
    for(key,qs)in queries.items():
        qs=sorted(qs,key=lambda q:q['page']);counts=sorted({v for q in qs for v in q['advertised_counts']});last={q['pages']for q in qs};total=sum(q['cards']for q in qs)
        row={'offering_id':key[0],'category':key[1],'radius_miles':key[2],'query_origin':'Naples FL 34102','pages_captured':[q['page']for q in qs],'advertised_page_counts':sorted(last),'source_advertised_match_counts':counts,'captured_card_occurrences':total,
             'pagination_complete':len(last)==1 and [q['page']for q in qs]==list(range(1,next(iter(last))+1)),
             'card_count_agrees':len(counts)==1 and counts[0]==total,'all_specialty_roster_complete':False,'all_locations_expanded':False,
             'full_county_geographic_proof':False,'sources':qs}
        accounting.append(row);db.execute('INSERT INTO aetna_query_accounting VALUES(?,?,?,?)',(key[0],key[1],key[2],json.dumps(row)))
    write(BASE/'aetna-query-accounting.json',accounting)
    with gzip.open(BASE/'aetna-records.jsonl.gz','wt')as output:
        for r in aetna:output.write(json.dumps(r,ensure_ascii=False)+'\n')
    identity_index=defaultdict(list)
    for r in aetna:
        f=r['fields']
        if not f.get('publisher_provider_id')or not f.get('npi'):continue
        key=(f['publisher_provider_id'],normalized(f.get('street_raw','')),normalized(f.get('city','')),f.get('state'),f.get('postal_code'))
        identity_index[key].append(r)
    resolutions=[]
    for r in aetna:
        f=r['fields'];key=(f.get('publisher_provider_id'),normalized(f.get('street_raw','')),normalized(f.get('city','')),f.get('state'),f.get('postal_code'))
        matches=identity_index.get(key,[]);values=sorted({x['fields']['npi']for x in matches})
        if f.get('npi'):state='NPI explicitly displayed in this source observation';npi=f['npi']
        elif len(values)==1 and f.get('publisher_provider_id'):state='identity supplemented from exact publisher ID and same site in another retained plan query';npi=values[0]
        elif len(values)>1:state='held contradictory NPI values for exact publisher ID/site';npi=None
        else:state='NPI not displayed or independently resolved; publisher identity retained';npi=None
        result={'record_id':r['id'],'state':state,'resolved_npi':npi,'source_npi_observations':[x['id']for x in matches],
            'matching_grain':'Exact Aetna provider ID + street/city/state/ZIP; virtual entries retain absent physical site','plan_participation_inherited_from_identity_match':False}
        resolutions.append(result);db.execute('INSERT INTO aetna_identity_resolution VALUES(?,?,?)',(r['id'],state,json.dumps(result)))
    write(BASE/'aetna-identity-resolution.json',resolutions)
    # Apply only exact campus address plus an independently preserved name alias.
    hospitals=json.loads((PARENT/'build-r1/hospital-reference.json').read_text());aliases=json.loads((PARENT/'build-r1/hospital-identity-aliases.json').read_text())['aliases']
    campus=[]
    for r in aetna:
        if r['category']not in ['hospital','hospital_detail']:continue
        f=r['fields']
        if not f.get('street_raw'):continue
        for h in hospitals:
            allowed={normalized(h['Name']),normalized(h['Owner'])}|{normalized(x)for x in aliases.get(h['id'],[])}
            registry_resolved_rehab=h['id']=='AHCA:458386'and f.get('npi')=='1790432490'and r['category']=='hospital_detail'
            if normalized(f['name_raw'])not in allowed and not registry_resolved_rehab:continue
            for a in h['addresses']:
                street=lambda x:normalized(x.replace('Health Park','Healthpark').replace('HEALTH PARK','HEALTHPARK'))
                if a.get('AddressType')!='ST'or street(a.get('Address','')+' '+a.get('Address2',''))!=street(f['street_raw']):continue
                if normalized(a.get('City',''))!=normalized(f.get('city',''))or a.get('State')!=f.get('state')or a.get('Zip','')[:5]!=f.get('postal_code','')[:5]:continue
                evidence={'source':'Aetna exact selected 2026 plan public directory','record_id':r['id'],'source_path':r['source_path'],'source_sha256':r['source_sha256'],'published_fields':f,'identity_basis':'Exact registry NPI/legal Naples rehabilitation entity and licensed primary-campus address'if registry_resolved_rehab else'Exact licensed primary-campus address and hospital name/retained alias','state':'published_directory_lists_campus','current_participation_guaranteed':False}
                old=db.execute('SELECT state,evidence_json FROM hospital_plan_matrix WHERE hospital_id=?AND offering_id=?',(h['id'],r['offering_id'])).fetchone()
                if old:
                    existing=json.loads(old[1]);existing.append(evidence);db.execute('UPDATE hospital_plan_matrix SET state=?,evidence_json=? WHERE hospital_id=?AND offering_id=?',('published_directory_lists_campus',json.dumps(existing),h['id'],r['offering_id']));campus.append({'hospital_id':h['id'],'offering_id':r['offering_id'],'record_id':r['id']})
    write(BASE/'new-hospital-plan-evidence.json',campus)
    identities=[]
    for p in(BASE/'acquisition/receipts').glob('*.json'):
        receipt=json.loads(p.read_text())
        if 'npiregistry.cms.hhs.gov'not in receipt.get('requested_url','')or receipt.get('error'):continue
        packet=json.loads((ROOT/receipt['path']).read_bytes())
        for item in packet.get('results',[]):
            row={'npi':str(item['number']),'source_id':receipt['id'],'source_path':receipt['path'],'source_sha256':receipt['sha256'],'native':item,'network_participation_established':False}
            identities.append(row);db.execute('INSERT INTO r2_identity_evidence VALUES(?,?,?)',(row['npi'],row['source_id'],json.dumps(row)))
    write(BASE/'registry-identity-evidence.json',identities)
    db.executescript('CREATE INDEX pdf_npi ON pdf_records(identifier_kind,identifier);CREATE INDEX pdf_doc ON pdf_records(document_sha256);CREATE INDEX qualifier_record ON published_qualifiers(record_id);')
    db.commit();stats['aetna_query_card_observations']=len(aetna);stats['aetna_query_sets']=len(accounting);stats['new_hospital_plan_observations']=len(campus)
    summary={'scope':'Additive published 2026 Collier provider-reference follow-up; incomplete','counts':dict(stats),'query_accounting_all_passed':all(q['pagination_complete']and q['card_count_agrees']for q in accounting),'pdf_listing_states':dict(db.execute('SELECT state,count(*)FROM pdf_records GROUP BY state')),'hospital_matrix_states':dict(db.execute('SELECT state,count(*)FROM hospital_plan_matrix GROUP BY state')),'collier_hospital_matrix_states':dict(db.execute("SELECT m.state,count(*)FROM hospital_plan_matrix m JOIN hospitals h ON m.hospital_id=h.id WHERE h.county='Collier'GROUP BY m.state")),'comprehensive_layer_complete':False,'consumer_release_enabled':False,'human_acceptance_inherited':False,'sqlite_integrity':db.execute('PRAGMA integrity_check').fetchone()[0]}
    write(BASE/'summary.json',summary);db.close();print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
