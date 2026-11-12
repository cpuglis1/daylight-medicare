"""Normalize retained guest-directory observations with literal AX locators."""
import re,json
from l08_r3_common import BASE,ROOT,write,digest,assert_open
from l08_r3_aetna import ax_nodes,aetna_records

def humana(path):
    s=path.read_text();ns=ax_nodes(s);rs=[]
    assert 'FL Medicare HMO'in s and 'Plan Year 2026'in s and 'Distance: 100 mi'in s
    m=re.search(r'(\d+) in network results for “Hospitals” for 2026',s);assert m
    for i,n in enumerate(ns):
        if n['body'].startswith('button ')and n['body']not in ['button View details','button More']:
            parent=n['parent']
            if parent is None:continue
            card=ns[parent:ns[parent]['end']]
            # Cards live inside the actual result list, not in the outer page
            # container (which can also contain the floating Feedback button).
            ancestor=parent;inside=False
            while ancestor is not None:
                if ns[ancestor]['body']=='container findcare-domain__results-list-container':inside=True;break
                ancestor=ns[ancestor]['parent']
            direct_buttons=[x for x in card if x['parent']==parent and x['body'].startswith('button ')]
            if not inside or ns[parent]['body']!='container'or not direct_buttons or direct_buttons[0]['id']!=n['id']or not any(x['body']=='text In network'for x in card):continue
            if n['body'].startswith('button View details')or n['body'].startswith('button Go to page'):continue
            fields={'name_raw':n['body'][7:]};loc={'name_raw':{'line':n['line'],'span':[7,len(n['body'])],'body':n['body']}}
            texts=[x for x in card if x['body'].startswith('text ')and x['body']not in ['text More']]
            fields['published_card_text']=[x['body'][5:]for x in texts]
            loc['published_card_text']=[{'line':x['line'],'span':[5,len(x['body'])],'body':x['body']}for x in texts]
            for x in texts:
                am=re.search(r'(\d+\s+[^,]+),\s+([^,]+),\s+([A-Z]{2})\s+(\d{5})',x['body'])
                if am:
                    for field,k in [('street_raw',1),('city_raw',2),('state_raw',3),('postal_raw',4)]:
                        fields[field]=am[k];loc[field]={'line':x['line'],'body':x['body'],'span':list(am.span(k))}
                pm=re.fullmatch(r'text (\(\d{3}\)\s*\d{3}-\d{4})',x['body'])
                if pm:fields['phone_raw']=pm[1];loc['phone_raw']={'line':x['line'],'body':x['body'],'span':list(pm.span(1))}
            rs.append({'id':digest((path.name+':'+str(n['id'])).encode()),'source_path':str(path.relative_to(ROOT)),
                       'source_sha256':digest(path.read_bytes()),'fields':fields,'locators':loc,
                       'year':2026,'network_raw':'FL Medicare HMO','radius_miles':100,
                       'state':'published_named_network_query; exact plan network references retained separately; no unique clinician guarantee'})
    return rs,{'source_path':str(path.relative_to(ROOT)),'page':int(re.search(r'page(\d+)',path.name)[1]),'cards':len(rs),'advertised_total':int(m[1]),'scope':'Hospitals; FL Medicare HMO; 100 miles from selected Collier County centroid; benefit year 2026'}

def blue(path):
    s=path.read_text();ns=ax_nodes(s);rs=[]
    assert 'BlueMedicare Classic (HMO)'in s and'Viewing 1 -  5 of 5 results'in s
    for i,n in enumerate(ns):
        if not(n['body'].startswith('heading ')and'Value: 2'in n['body']):continue
        kids=ns[i+1:n['end']];links=[x for x in kids if x['body'].startswith('link Description:')and'/providerDetails?'in x['body']]
        if not links:continue
        end=next((j for j in range(n['end'],len(ns))if ns[j]['body'].startswith('heading ')and'Value: 2'in ns[j]['body']),len(ns))
        card=ns[i:end];link=links[0];name=re.search(r'Description: (.*?), Value:',link['body'])[1]
        texts=[x for x in kids if x['body'].startswith('text ')]
        # The heading's own link is its complete published name.
        name_span=list(re.search(r'Description: (.*?), Value:',link['body']).span(1))
        fields={'name_raw':name,'detail_link_raw':link['body']};loc={'name_raw':{'line':link['line'],'body':link['body'],'span':name_span},'detail_link_raw':{'line':link['line'],'body':link['body'],'span':[0,len(link['body'])]}}
        addr=next((x for x in card if x['body'].startswith('text ')and re.search(r', (?:Naples|NAPLES), Florida \d{5}',x['body'])),None)
        if addr:fields['address_raw']=addr['body'][5:];loc['address_raw']={'line':addr['line'],'body':addr['body'],'span':[5,len(addr['body'])]}
        ph=next((x for x in card if'Value: tel:'in x['body']),None)
        if ph:
            m=re.search(r'Description: (.*?), Value:',ph['body']);fields['phone_raw']=m[1];loc['phone_raw']={'line':ph['line'],'body':ph['body'],'span':list(m.span(1))}
        rs.append({'id':digest((path.name+':'+str(n['id'])).encode()),'source_path':str(path.relative_to(ROOT)),
                   'source_sha256':digest(path.read_bytes()),'fields':fields,'locators':loc,
                   'plan_family_raw':'BlueMedicare Classic (HMO)','observed_date':'2026-10-27',
                   'benefit_year':None,'exact_CMS_offering':None,'radius_miles':20,
                   'state':'published_current_plan_family_listing; exact 2026 plan mapping held'})
    assert len(rs)==5
    return rs

def main():
    assert_open();ars=[];aqs=[];hrs=[];hqs=[]
    for p in sorted((BASE/'ui').glob('*-mentalhealth-*.ax.txt')):
        r,q=aetna_records(p);ars.extend(r);aqs.append(q)
    for p in sorted((BASE/'ui').glob('humana-hmo-hospitals-100mi-page*.ax.txt')):
        r,q=humana(p);hrs.extend(r);hqs.append(q)
    bs=blue(BASE/'ui/blue-classic-hospitals-20mi.ax.txt')
    write(BASE/'aetna-mentalhealth-observations.json',ars);write(BASE/'aetna-mentalhealth-query-accounting.json',aqs)
    write(BASE/'humana-public-hospital-observations.json',hrs);write(BASE/'humana-public-hospital-accounting.json',hqs)
    write(BASE/'blue-current-family-observations.json',bs)
    print(json.dumps({'Aetna_records':len(ars),'Aetna_pages':len(aqs),'Humana_records':len(hrs),'Humana_pages':len(hqs),'Blue_family_records':len(bs)}))

if __name__=='__main__':main()
