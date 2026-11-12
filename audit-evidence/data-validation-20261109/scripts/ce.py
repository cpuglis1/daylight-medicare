import json,re,collections
from decimal import Decimal as D
d=json.load(open('dl_r13.json'))
mpf=json.load(open('mpf_collier.json'))
L={f"{r['Contract ID']}-{r['Plan ID'].zfill(3)}-{r['Segment ID'].zfill(3)}":r for r in json.load(open('land_collier.json'))['collier']}
by=collections.defaultdict(list)
for r in mpf: by[r['_key']].append(r)
def rows(key,cat,svc=None):
    return [r for r in by[key] if r['Category Name']==cat and (svc is None or r['Service_Desc']==svc) and r['Network_Description'] in (None,'In-Network')]
def money(s):
    m=re.findall(r'\$([\d,]+(?:\.\d+)?)',str(s)); return [D(x.replace(',','')) for x in m]
res=collections.Counter(); bad=[]
for p in d['plans']:
    dc=p['display_candidate']; k=dc['offering_id'].split(':'); key=f'{k[1]}-{k[2]}-{k[3]}'; ce=dc['cost_examples']; lr=L[key]
    def shown(f): 
        v=ce[f]; return D(v['amount']['amount']) if v['state']=='numeric_candidate' else None
    # premium
    s=shown('premium_12_months')
    if s is not None:
        src=lr['Monthly Consolidated Premium (Part C + D)']; src=src if 'Not Applicable' not in src else lr['Part C Premium']
        exp=money(src)[0]*12; ok=(exp==s); res[('premium_12_months','ok' if ok else 'BAD')]+=1
        if not ok: bad.append((key,'premium',s,exp))
    # pcp
    s=shown('pcp_four_visits')
    if s is not None:
        t=' '.join(str(r['Cost_Share']) for r in rows(key,'Doctor visits','Primary'))
        ded=str((rows(key,'Health plan deductible') or [{'Cost_Share':''}])[0]['Cost_Share'])
        m=money(t); exp=None
        if '%' not in t and len(set(m))==1: exp=m[0]*4
        elif t.strip().startswith('$0') and len(set(m))==1: exp=D(0)
        ok=(exp==s); res[('pcp_four_visits','ok' if ok else 'BAD')]+=1
        if not ok: bad.append((key,'pcp',s,exp,t[:80],'ded',ded[:40]))
    # hospital
    for f,days in (('hospital_3',3),('hospital_4',4)):
        s=shown(f)
        if s is None: continue
        t=' || '.join(str(r['Cost_Share']) for r in rows(key,'Inpatient hospital coverage'))
        exp=None
        m1=re.search(r'\$([\d,]+(?:\.\d+)?) per day for days 1 through (\d+)',t)
        m2=re.search(r'\$([\d,]+(?:\.\d+)?) per stay',t)
        if m1 and int(m1.group(2))>=4: exp=D(m1.group(1).replace(',',''))*days
        elif m2 and not m1: exp=D(m2.group(1).replace(',',''))
        ok=(exp==s); res[(f,'ok' if ok else 'BAD')]+=1
        if not ok: bad.append((key,f,s,exp,t[:160]))
for k,v in sorted(res.items()): print(k,v)
for b in bad: print(b)
