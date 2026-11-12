"""Source-grid comparisons only; no personal rating or quote calculation."""
from collections import Counter, defaultdict
from datetime import datetime
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'docs/data/l10-medigap-2026-10-28'
PARENT=BASE/'build-r2'
OUT=BASE/'filing-reconciliation-r3/build-r1'
REGIONS={'26-007296':'Area 2','26-018953':'1',
         '26-023593':'320 to 322 327 to 329 335 to 339 341 to 349','26-036521':'Area 1'}


def write(path,data):path.write_text(json.dumps(data,indent=2,sort_keys=True)+'\n')


def variant(plan):return {'F-HD':'F*','G-HD':'G*'}.get(plan,plan)


def run(out=OUT):
    out=Path(out)
    if (out/'SEALED').exists():raise ValueError('Sealed filing revision; use a new output directory')
    schedules=json.loads((out/'schedules.json').read_text());rates=json.loads((out/'rate-cells.json').read_text())
    approved={s['id']:s for s in schedules if s['status']=='APPROVED'}
    companies={s['fields']['Issuing Carrier'] for s in approved.values()}
    selected={sid:s for sid,s in approved.items() if s['case'] in REGIONS and s['fields']['Region']==REGIONS[s['case']]}
    index=defaultdict(list)
    for r in rates:
        if r['schedule_id'] not in selected:continue
        s=selected[r['schedule_id']];f=s['fields']
        key=(f['Issuing Carrier'],variant(f['Plan']),r['age_raw'],r['sex_raw'],f['Underwritten (Yes/No)'])
        index[key].append(r)
    counts=Counter();by_company=defaultdict(Counter);listings=defaultdict(Counter)
    with (PARENT/'illustrations.jsonl').open() as source,(out/'illustration-comparisons.jsonl').open('w') as target:
        for line in source:
            observation=json.loads(line);n=observation['source_native'];name=n['companY_NM']
            if name not in companies:continue
            f=observation['synthetic_inputs'];key=(name,n['plaN_CD'],n['agE_CD'],{'f':'Female','m':'Male'}.get(f['gender']),{'y':'Yes','n':'No'}.get(n['guaranteeD_ISSUE_CD']))
            candidates=index.get(key,[])
            candidates=[r for r in candidates if (r['class_raw'] in ['Smoker','Non-Smoker'] and r['class_raw']=={'s':'Smoker','o':'Non-Smoker'}[f['smoker']]) or (r['class_raw'] in ['Preferred','Standard'] and r['class_raw']==n['ratinG_CLASS_NM'])]
            requested_date=datetime.strptime(f['effectiveDate'],'%m/%d/%Y').date().isoformat()
            if name=='BLUE CROSS & BLUE SHIELD OF FLORIDA, INC.':status='rate_effective_period_unresolved'
            elif len(candidates)!=1:status='no_unique_matching_source_grid'
            elif not candidates[0]['rate_effective_from']<=requested_date<=candidates[0]['rate_effective_through']:status='requested_date_outside_filed_period'
            elif candidates[0]['annual_premium_cents']==observation['annual_premium_cents']:status='same_annual_grid_amount'
            else:status='different_annual_grid_amount'
            result={'illustration_id':observation['id'],'listing_id':observation['listing_id'],
                    'company':name,'status':status,'candidate_rate_ids':[r['id'] for r in candidates],
                    'illustration_requested_date':requested_date,
                    'illustrative_annual_cents':observation['annual_premium_cents'],
                    'filed_annual_cents':[r['annual_premium_cents'] for r in candidates],
                    'scope':'Exact observed company/variant/age/sex/class/Collier-area annual grid comparison. Policy-issue applicability, sale, discounts and personal rights remain unestablished.',
                    'personal_quote':False,'acceptance':'pending'}
            target.write(json.dumps(result,sort_keys=True,separators=(',',':'))+'\n')
            counts[status]+=1;by_company[name][status]+=1;listings[observation['listing_id']][status]+=1
    catalog=json.loads((PARENT/'insurer-catalog.json').read_text())
    missing=[{'company_name':c['company_name_raw'],'naic':c['exact_name_unique_naic'],
              'missing':'Applicable approved rate packet, exact form/effective-period/class/area/sale evidence',
              'state':'required_missing_source'} for c in catalog if c['choices_observation_count'] and c['company_name_raw'] not in companies]
    summary={'source_companies':len(companies),'source_company_names':sorted(companies),'comparisons':sum(counts.values()),
             'status_counts':dict(counts),'by_company':{k:dict(v) for k,v in sorted(by_company.items())},
             'listing_status_counts':{k:dict(v) for k,v in sorted(listings.items())},
             'missing_file_packets_for_CHOICES_companies':missing,
             'complete_all_market_denominator':False,
             'additional_universe_obligation':'188 historical and 89 2026-filed company leads still need actual 2026 product-continuation/sale and county classification. 34 sample names are not the complete denominator.',
             'source_grid_agreement_is_not_personal_price_verification':True,'human_acceptance':None}
    write(out/'comparison-summary.json',summary)
    print(json.dumps({k:v for k,v in summary.items() if k in ['source_companies','comparisons','status_counts']},indent=2))


if __name__=='__main__':run()
