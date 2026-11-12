import json,collections,re
d=json.load(open('dl_r13.json'))
mpf=json.load(open('mpf_collier.json'))
L={}
for r in json.load(open('land_collier.json'))['collier']:
    L[f"{r['Contract ID']}-{r['Plan ID'].zfill(3)}-{r['Segment ID'].zfill(3)}"]=r
by=collections.defaultdict(list)
for r in mpf: by[r['_key']].append(r)
want={'medical_deductible':('Health plan deductible',None),'medical_maximums':('Maximum out-of-pocket enrollee responsibility (does not include prescription drugs)',None),'primary_care_in_network':('Doctor visits','Primary'),'specialist_in_network':('Doctor visits','Specialist'),'hospital_in_network':('Inpatient hospital coverage',None),'emergency':('Emergency care/urgent care','Emergency'),'urgent':('Emergency care/urgent care','Urgent care')}
def money(s):
    s=str(s or '')
    vals=set()
    for m in re.finditer(r'\$\s?([\d,]+(?:\.\d+)?)(?:\s?-\s?\$?([\d,]+(?:\.\d+)?))?',s):
        vals.add(float(m.group(1).replace(',','')))
        if m.group(2): vals.add(float(m.group(2).replace(',','')))
    return vals
def pct(s):
    s=str(s or ''); vals=set()
    for m in re.finditer(r'([\d.]+)(?:\s?-\s?([\d.]+))?\s?%',s):
        vals.add(float(m.group(1)))
        if m.group(2): vals.add(float(m.group(2)))
    return vals
res=collections.Counter(); flags=[]
for p in d['plans']:
    dc=p['display_candidate']; k=dc['offering_id'].split(':'); key=f'{k[1]}-{k[2]}-{k[3]}'
    lr=L[key]
    for f,b in dc['benefits'].items():
        if b['state']!='published_candidate': res[(f,b['state'])]+=1; continue
        v=b['value']
        if f=='plan_premium':
            src=lr['Monthly Consolidated Premium (Part C + D)']; ok=money(v)==money(src) or (money(v)=={0.0} and money(src)=={0.0})
        elif f=='part_d_deductible':
            src=lr['Annual Part D Deductible Amount']; ok=money(v)==money(src)
        elif f=='part_b_reduction':
            res[(f,'not_checked_here')]+=1; continue
        else:
            cat,svc=want[f]
            rows=[r for r in by[key] if r['Category Name']==cat and (svc is None or r['Service_Desc']==svc) and (f=='medical_maximums' or f=='medical_deductible' or r['Network_Description'] in (None,'In-Network','None'))]
            src=' || '.join(str(r['Cost_Share']) for r in rows)
            dm,dp=money(v),pct(v); sm,sp=money(src),pct(src)
            if str(src).strip()=='0' and dm=={0.0}: sm={0.0}
            ok=bool(dm|dp) and dm<=sm and dp<=sp
            if f=='medical_maximums': 
                lm=money(lr['In-Network Maximum Out-of-Pocket (MOOP) Amount'])
                if not lm<=dm: ok=False; src+=' | LANDSCAPE INN MOOP '+lr['In-Network Maximum Out-of-Pocket (MOOP) Amount']
            # oversimplification: source has more distinct amounts than display, for single-rate fields
            if ok and f in ('emergency','urgent','primary_care_in_network','specialist_in_network') and len(sm|sp)>len(dm|dp):
                res[(f,'match_but_source_has_more_values')]+=1; flags.append((key,f,'MORE',v,src[:200])); continue
        res[(f,'match' if ok else 'MISMATCH')]+=1
        if not ok: flags.append((key,f,'MISMATCH',v,str(src)[:250]))
for k,v in sorted(res.items()): print(k,v)
print('---- flags',len(flags))
for x in flags: print(x)
json.dump(flags,open('flags.json','w'))
