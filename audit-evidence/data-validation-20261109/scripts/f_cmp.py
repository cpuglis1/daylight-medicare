import csv,json,gzip,collections,io
W='f/'
L=json.load(open('land_collier.json'))
ma={(r['Contract ID'],r['Plan ID'].zfill(3),r['Segment ID'].zfill(3)):r for r in L['collier']}
pdp={(r['Contract ID'],r['Plan ID'].zfill(3),r['Segment ID'].zfill(3)):r for r in L['flpdp']}
drug_ma={k for k,r in ma.items() if r['Contract Category Type']!='MA'}
target=drug_ma|set(pdp)
print('target drug-bearing plans',len(drug_ma),'+',len(pdp),'=',len(target))
# plan info
pi=collections.defaultdict(set); sup={}; prem={}
with open(W+'plan/plan information  20260930.txt',encoding='latin-1') as f:
    for r in csv.DictReader(f,delimiter='|'):
        k=(r['CONTRACT_ID'],r['PLAN_ID'].zfill(3),r['SEGMENT_ID'].zfill(3))
        if k in target:
            pi[k].add(r['FORMULARY_ID']); sup[k]=r['PLAN_SUPPRESSED_YN']; prem[k]=(r['PREMIUM'],r['DEDUCTIBLE'])
print('plans found in plan info',len(pi),'missing',sorted(target-set(pi)),'multi-formulary',[k for k,v in pi.items() if len(v)>1],'suppressed',[k for k,v in sup.items() if v!='N'])
fids={next(iter(v)) for v in pi.values()}
print('distinct formularies',len(fids))
# compare to daylight plans.csv
dl={}
for r in csv.DictReader(open('/'.join([__import__('os').environ['HOME'],'mnt/daylight/docs/data/l05-drug-coverage-2026-10-25/build-r3/plans.csv']))):
    _,c,p,s=r['offering_id'].split(':'); dl[(c,p,s)]=r
print('daylight plans',len(dl),'only CMS',sorted(set(pi)-set(dl)),'only DL',sorted(set(dl)-set(pi)))
fmis=[(k,next(iter(pi[k])),dl[k]['formulary_id']) for k in pi if k in dl and next(iter(pi[k]))!=dl[k]['formulary_id']]
print('formulary id mismatches',fmis)
# basic
rows=collections.defaultdict(set); ver={}
with open(W+'basic/basic drugs formulary file  20260930.txt',encoding='latin-1') as f:
    for r in csv.DictReader(f,delimiter='|'):
        if r['FORMULARY_ID'] in fids:
            ver.setdefault(r['FORMULARY_ID'],set()).add(r['FORMULARY_VERSION'])
            rows[r['FORMULARY_ID']].add((r['RXCUI'],r['NDC'],r['TIER_LEVEL_VALUE'],r['QUANTITY_LIMIT_YN'],r['QUANTITY_LIMIT_AMOUNT'],r['QUANTITY_LIMIT_DAYS'],r['PRIOR_AUTHORIZATION_YN'],r['STEP_THERAPY_YN'],r['SELECTED_DRUG_YN']))
print('CMS basic rows in scope',sum(len(v) for v in rows.values()),'versions',{k:v for k,v in ver.items() if len(v)>1} or 'one per formulary')
vm=[(k,dl[k]['formulary_version'],ver[next(iter(pi[k]))]) for k in dl if dl[k]['formulary_version'] not in ver[next(iter(pi[k]))]]
print('version mismatches',vm)
cnt=[(k,dl[k]['basic_rows'],len(rows[next(iter(pi[k]))])) for k in dl if int(dl[k]['basic_rows'])!=len(rows[next(iter(pi[k]))])]
print('per-plan basic row count mismatches',cnt[:10],len(cnt))
json.dump({'pi':{'-'.join(k):list(v) for k,v in pi.items()},'fids':sorted(fids)},open('f_scope.json','w'))
# daylight basic rows
dlrows=collections.defaultdict(set)
with gzip.open('/'.join([__import__('os').environ['HOME'],'mnt/daylight/docs/data/l05-drug-coverage-2026-10-25/build-r3/basic.csv.gz']),'rt') as f:
    rd=csv.DictReader(f); hdr=rd.fieldnames; print('DL basic header',hdr)
    for r in rd:
        g=lambda *names: next((r[n] for n in names if n in r),None)
        dlrows[g('formulary_id','FORMULARY_ID')].add((g('rxcui','RXCUI'),g('ndc','NDC'),g('tier','TIER_LEVEL_VALUE','tier_level_value'),g('quantity_limit_yn','QUANTITY_LIMIT_YN'),g('quantity_limit_amount','QUANTITY_LIMIT_AMOUNT'),g('quantity_limit_days','QUANTITY_LIMIT_DAYS'),g('prior_authorization_yn','PRIOR_AUTHORIZATION_YN'),g('step_therapy_yn','STEP_THERAPY_YN'),g('selected_drug_yn','SELECTED_DRUG_YN')))
print('DL basic rows',sum(len(v) for v in dlrows.values()))
tot_only_cms=tot_only_dl=0
for fid in fids:
    a,b=rows[fid],dlrows.get(fid,set())
    tot_only_cms+=len(a-b); tot_only_dl+=len(b-a)
    if a!=b and len(a-b)+len(b-a)<6: print(fid,'CMS-only',list(a-b)[:3],'DL-only',list(b-a)[:3])
print('rows only in CMS',tot_only_cms,'rows only in Daylight',tot_only_dl)
