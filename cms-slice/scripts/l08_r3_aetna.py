"""Pure source-locator readers reused additively from sealed L08 r2.
Only the filename category grammar is extended to mentalhealth.
"""
import re
from l08_r3_common import ROOT,digest

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
    m=re.fullmatch(r'([H]\d{4})-(\d{3})-(hospital|pcp|mentalhealth)-(\d+)mi-page(\d+)\.ax\.txt',name)
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
