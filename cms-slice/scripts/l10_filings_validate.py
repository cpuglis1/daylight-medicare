"""Independent pypdf glyph/position audit of owner filing observations.

No import of the pdfplumber builder. OIR Helvetica stamps are excluded from
worksheet body text, while the original PDFs remain untouched.
"""
import argparse
from collections import Counter, defaultdict
from datetime import datetime
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re

from pypdf import PdfReader

ROOT=Path(__file__).resolve().parents[2]
PACKET=ROOT/'docs/data/l10-medigap-2026-10-28/filing-reconciliation-r3'


def read(p):return json.loads(Path(p).read_text())


def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def norm(s):return ' '.join(s.split())


def glyphs(page):
    records=[]
    def visitor(t,cm,tm,font,size):
        if not font or 'Arial' not in str(font.get('/BaseFont','')) or not t or t in ['\n','\r','\r\n']:return
        x=tm[4]*cm[0]+tm[5]*cm[2]+cm[4]
        y=tm[4]*cm[1]+tm[5]*cm[3]+cm[5]
        records.append((x,y,t))
    page.extract_text(visitor_text=visitor)
    return records


def lines(records):
    grouped=[]
    for x,y,t in sorted(records,key=lambda r:-r[1]):
        if not grouped or abs(grouped[-1][0]-y)>3.5:grouped.append((y,[]))
        grouped[-1][1].append((x,t))
    return [(y,norm(''.join(t for x,t in sorted(v)))) for y,v in grouped]


def validate(out):
    out=Path(out);intake=read(PACKET/'intake.json')
    schedules=read(out/'schedules.json');rates=read(out/'rate-cells.json');pages=read(out/'page-inventory.json')
    by_source=defaultdict(list)
    for r in rates:by_source[(r['case'],r['source_page'])].append(r)
    checked_fields=checked_rates=checked_headers=0;all_source_schedules=0
    for doc in intake['documents']:
        path=ROOT/doc['retained_path'];case=path.name[:9]
        assert sha(path)==doc['sha256'] and sha(ROOT/doc['owner_path'])==doc['sha256']
        pdf=PdfReader(path);assert len(pdf.pages)==doc['pages']
        native_text=read(PACKET/'text'/(path.stem+'-pypdf.json'))
        source_starts={i+1 for i,t in enumerate(native_text) if 'Filing Company' in t}
        source_schedules=[s for s in schedules if s['case']==case]
        assert {s['source_pages'][0] for s in source_schedules}==source_starts
        for s in source_schedules:
            hp=s['source_pages'][0];raw=native_text[hp-1]
            status='APPROVED' if 'APPROVED' in raw else 'REPLACED' if 'REPLACED' in raw else 'unknown'
            assert s['status']==status and s['source_pdf_sha256']==doc['sha256']
            label_lines=lines(glyphs(pdf.pages[hp-1]))
            label_anchors={text:y for y,text in label_lines if text in s['fields']}
            assert set(label_anchors)==set(s['fields'])
            value_glyphs=glyphs(pdf.pages[hp]);age_x=next(x for x,y,t in value_glyphs if t.strip()=='Age')
            left=[(x,y,t) for x,y,t in value_glyphs if x<age_x-20]
            for label,expected in s['fields'].items():
                chunks=[(x,t) for x,y,t in left if abs(y-label_anchors[label])<6]
                actual=norm(''.join(t for x,t in sorted(chunks))) or None
                assert actual==expected,(case,hp,label,actual,expected)
                checked_fields+=1
            for page in s['source_pages'][1:]:
                gs=value_glyphs if page==hp+1 else glyphs(pdf.pages[page-1])
                money={}
                for x,y,t in sorted(gs,key=lambda r:-r[1]):
                    if re.fullmatch(r'\$[\d,]+\.\d{2}',t.strip()):
                        anchor=next((a for a in money if abs(a-y)<3.5),y)
                        money.setdefault(anchor,[]).append((x,t.strip()))
                assert len(money)==37,(case,page,'source money row count',len(money))
                cols=[c for c in s['source_columns'] if c['page']==page]
                assert all(len(v)==len(cols) for v in money.values()),(case,page,'column count')
                top_y=max(money)
                header_glyphs=[(x,y,t) for x,y,t in gs if y>top_y+6 and (page!=hp+1 or x>age_x+20)]
                header_lines=lines(header_glyphs)
                assert len(header_lines)==2,(case,page,'header lines',header_lines)
                assert header_lines[0][1]==norm(' '.join(c['class_raw'] for c in cols)),(case,page,'class header',header_lines)
                assert header_lines[1][1]==norm(' '.join(c['sex_raw'] for c in cols)),(case,page,'sex header',header_lines)
                checked_headers+=len(cols)*2
                expected_ages=['0-64']+[str(i) for i in range(65,100)]+['100+']
                for ri,((y,values),age) in enumerate(zip(sorted(money.items(),reverse=True),expected_ages)):
                    for column,(x,amount) in zip(cols,sorted(values)):
                        r=next(z for z in by_source[(case,page)] if z['source_column']==column['column'] and z['age_raw']==age)
                        assert r['schedule_id']==s['id'] and r['amount_raw']==amount
                        assert r['annual_premium_cents']==int(Decimal(amount.replace('$','').replace(',',''))*100)
                        assert r['class_raw']==column['class_raw'] and r['sex_raw']==column['sex_raw']
                        assert r['unit']=='USD/year' and r['source_status']==status and r['personal_quote'] is False
                        assert r['rate_effective_from']==s['rate_effective_from'] and r['rate_effective_through']==s['rate_effective_through']
                        assert r['zero_meaning']==('unresolved_not_a_free_offer' if r['annual_premium_cents']==0 else None)
                        checked_rates+=1
            assert s['policy_issue_range_from']==s['fields']['Date Range From']
            assert s['date_range_is_not_rate_effective_date'] is True and s['current_sale_status']=='not_established_by_approval'
            if status=='REPLACED':assert s['rate_effective_from'] is None and s['rate_effective_through'] is None
            all_source_schedules+=1
        assert {(r['case'],r['page']) for r in pages if r['case']==case}=={(case,i+1) for i in range(len(pdf.pages))}
    assert checked_rates==len(rates) and all_source_schedules==len(schedules)
    approvals=read(out/'approval-letters.json')
    for approval in approvals:
        doc=next(d for d in intake['documents'] if d['owner_path'].split('/')[-1].startswith(approval['case']))
        text=PdfReader(ROOT/doc['retained_path']).pages[approval['page']-1].extract_text()
        m=re.search(r'rate change of\s+([\d.]+)%,?\s+effective\s+(\d+/\d+/\d+)\s+through\s+(\d+/\d+/\d+),?\s+are\s+APPROVED',text,re.S)
        assert m,(approval['case'],'approval period extraction')
        assert m[1]==approval['approved_change_percent']
        assert datetime.strptime(m[2],'%m/%d/%Y').date().isoformat()==approval['effective_from']
        assert datetime.strptime(m[3],'%m/%d/%Y').date().isoformat()==approval['effective_through']
        assert approval['acceptance']=='pending'
    periods={a['case']:(a['effective_from'],a['effective_through']) for a in approvals}
    for s in schedules:
        actual=(s['rate_effective_from'],s['rate_effective_through'])
        assert actual==(periods[s['case']] if s['status']=='APPROVED' and s['case'] in periods else (None,None))
        assert s['acceptance']=='pending' and s['personal_quote'] is False
    comparison_audit=validate_comparisons_and_conditions(out,schedules,rates)
    baseline=read(PACKET/'preservation-before.json')
    assert all(sha(ROOT/p)==h for p,h in baseline.items())
    assert not read(out/'exceptions.json')
    return {'schema':'l10-owner-filings-independent-audit/1','passed':True,'source_pdfs':len(intake['documents']),
            'pages_accounted':len(pages),'schedules_checked':all_source_schedules,'field_values_checked':checked_fields,
            'column_headers_checked':checked_headers,'annual_rate_cells_checked':checked_rates,
            'approval_periods_checked':len(approvals),'protected_files_unchanged':len(baseline),
            'unexplained_source_value_mismatches':0,**comparison_audit,
            'human_acceptance':None,'consumer_release_enabled':False}


def validate_comparisons_and_conditions(out,schedules,rates):
    parent=ROOT/'docs/data/l10-medigap-2026-10-28/build-r2'
    schedule_map={s['id']:s for s in schedules};rate_map={r['id']:r for r in rates}
    companies={s['fields']['Issuing Carrier'] for s in schedules}
    compared={}
    for line in (out/'illustration-comparisons.jsonl').open():
        r=json.loads(line);assert r['illustration_id'] not in compared;compared[r['illustration_id']]=r
    counts=Counter();by_company=defaultdict(Counter);checked=0;compared_zips=set()
    regions={'26-007296':'Area 2','26-018953':'1','26-023593':'320 to 322 327 to 329 335 to 339 341 to 349','26-036521':'Area 1'}
    for line in (parent/'illustrations.jsonl').open():
        obs=json.loads(line);n=obs['source_native'];inputs=obs['synthetic_inputs'];name=n['companY_NM']
        if name not in companies:continue
        r=compared[obs['id']];checked+=1;compared_zips.add(inputs['zipCode'])
        assert r['company']==name and r['listing_id']==obs['listing_id']
        assert r['illustrative_annual_cents']==obs['annual_premium_cents']
        assert r['personal_quote'] is False and r['acceptance']=='pending'
        requested=datetime.strptime(inputs['effectiveDate'],'%m/%d/%Y').date().isoformat()
        assert r['illustration_requested_date']==requested
        if name=='BLUE CROSS & BLUE SHIELD OF FLORIDA, INC.':
            assert r['status']=='rate_effective_period_unresolved' and r['candidate_rate_ids']==[] and r['filed_annual_cents']==[]
        else:
            assert len(r['candidate_rate_ids'])==1
            cell=rate_map[r['candidate_rate_ids'][0]];s=schedule_map[cell['schedule_id']];f=s['fields']
            assert s['status']=='APPROVED' and f['Issuing Carrier']==name and f['Region']==regions[s['case']]
            assert {'F-HD':'F*','G-HD':'G*'}.get(f['Plan'],f['Plan'])==n['plaN_CD']
            assert cell['age_raw']==n['agE_CD'] and cell['sex_raw']=={'f':'Female','m':'Male'}[inputs['gender']]
            assert f['Underwritten (Yes/No)']=={'y':'Yes','n':'No'}[n['guaranteeD_ISSUE_CD']]
            if cell['class_raw'] in ['Smoker','Non-Smoker']:
                assert cell['class_raw']=={'s':'Smoker','o':'Non-Smoker'}[inputs['smoker']]
            else:assert cell['class_raw']==n['ratinG_CLASS_NM']
            assert cell['rate_effective_from']<=requested<=cell['rate_effective_through']
            assert r['filed_annual_cents']==[cell['annual_premium_cents']]
            assert r['status']==('same_annual_grid_amount' if cell['annual_premium_cents']==obs['annual_premium_cents'] else 'different_annual_grid_amount')
        counts[r['status']]+=1;by_company[name][r['status']]+=1
    assert checked==len(compared)
    assert len(compared_zips)==25 and all(z.startswith('341') for z in compared_zips)
    summary=read(out/'comparison-summary.json')
    assert dict(counts)==summary['status_counts'] and {k:dict(v) for k,v in by_company.items()}==summary['by_company']
    catalog=read(parent/'insurer-catalog.json')
    missing={c['company_name_raw'] for c in catalog if c['choices_observation_count'] and c['company_name_raw'] not in companies}
    assert {c['company_name'] for c in summary['missing_file_packets_for_CHOICES_companies']}==missing
    facts=read(out/'conditions.json');docs=read(PACKET/'intake.json')['documents']
    for fact in facts:
        doc=next(d for d in docs if Path(d['retained_path']).name.startswith(fact['case']))
        raw=PdfReader(ROOT/doc['retained_path']).pages[fact['source_page']-1].extract_text()
        assert norm(fact['excerpt']) in norm(raw) and fact['source_pdf_sha256']==doc['sha256']
        assert fact['acceptance']=='pending' and fact['consumer_release_enabled'] is False
        values=fact['values'];quote=norm(fact['excerpt'])
        for k,v in values.items():
            if k in ['policy_fee_cents','application_fee_cents']:
                assert v==int(re.search(r'\$(\d+)',quote)[1])*100
            elif k=='household_discount_percent':assert v==re.search(r'([\d.]+)%',quote)[1]
            elif k=='area_factor':assert v==(quote.split()[1] if fact['case']=='26-036521' else quote.split()[-1])
            elif k=='unit':assert v=='USD/year' and quote=='All Rates are ANNUAL.'
            elif k=='monthly_basis_memo':assert v in quote
            elif k=='rounding_formula_raw':assert v==quote
            elif k=='memo_form_prefix':assert v in quote
            elif k=='worksheet_and_approval_prefix':
                assert any(s['case']==fact['case'] and s['fields']['Form Number'].startswith(v) and s['status']=='APPROVED' for s in schedules)
                assert v in next(a['form_heading'] for a in read(out/'approval-letters.json') if a['case']==fact['case'])
            elif k=='source_county_code':assert v in quote
            elif k=='county':assert v in quote
            elif k=='zip_prefixes_for_Collier_test_cases':assert v==['341'] and '341-' in quote
            elif k=='region':assert v==regions[fact['case']]
            elif k=='frequency':assert v=='one_time' and 'one-time' in quote
            elif k=='condition':assert v in quote
            elif k=='source_business_basis':assert v==['inforce','new_business'] and 'both inforce and new business' in quote
            elif k=='source_class_condition':assert v=='tobacco user in open enrollment or guaranteed issue -> standard' and 'standard class' in quote and 'tobacco user' in quote
            elif k=='rating_dimensions':assert v==['issue_age','gender','zip_code','tobacco_use'] and 'issue age, gender, zip code and tobacco use' in quote
            else:raise AssertionError('Unaudited modeled condition field: '+k)
    assert sum(f['values'].get('unit')=='USD/year' for f in facts)==len(docs)
    for case in regions:
        assert any(f['case']==case and f['values'].get('region')==regions[case] for f in facts)
    groups=read(out/'filed-product-census.json');seen=[]
    for group in groups:
        assert group['current_sale']=='unknown' and group['full_2026_continuity']=='not_established'
        for sid in group['schedule_ids']:
            seen.append(sid);s=schedule_map[sid];f=s['fields']
            assert (f['Issuing Carrier'],f['Form Number'],f['Plan'],f['Insurance Type'],s['policy_issue_range_from'],s['policy_issue_range_through'])==(group['company'],group['form_raw'],group['plan_raw'],group['insurance_type_raw'],group['policy_issue_from_raw'],group['policy_issue_through_raw'])
        assert set(group['approved_schedule_ids'])=={sid for sid in group['schedule_ids'] if schedule_map[sid]['status']=='APPROVED'}
    assert len(seen)==len(set(seen))==len(schedules) and set(seen)==set(schedule_map)
    queue=read(out/'company-source-queue.json')
    assert {c['company_raw'] for c in queue}=={c['company_name_raw'] for c in catalog}
    assert len(queue)==len(catalog)
    for q in queue:assert q['owner_packet_obtained']==(q['company_raw'] in companies)
    pages=read(out/'page-inventory.json');sparse=read(PACKET/'sparse-page-review.json')
    assert len({(p['case'],p['page']) for p in sparse})==len(sparse)
    for p in sparse:
        actual=next(x for x in pages if (x['case'],x['page'])==(p['case'],p['page']))
        assert actual['role']!='image_or_sparse_page_requires_visual_classification'
        assert actual['render_sha256']==sha(ROOT/p['render_path'])==p['render_sha256']
    delta=read(out/'before-after.json')['after']
    assert delta['source_form_issue_type_groups']==len(groups) and delta['condition_records']==len(facts)
    coverage=read(out/'coverage.json')
    assert coverage['full_l10_complete'] is False and coverage['human_acceptance'] is None and coverage['consumer_release_enabled'] is False
    return {'illustration_comparisons_checked':checked,'comparison_status_counts':dict(counts),
            'source_condition_records_checked':len(facts),'form_issue_type_groups_accounted':len(groups),
            'parent_company_leads_accounted':len(queue),'CHOICES_companies_missing_packets':len(missing),
            'sparse_pages_rendered_and_classified':len(sparse)}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('package',type=Path);p.add_argument('--out',type=Path);a=p.parse_args()
    result=validate(a.package)
    if a.out:a.out.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps(result,indent=2))
