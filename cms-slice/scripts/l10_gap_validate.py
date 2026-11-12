"""Native response and Poppler audit independent of L10 gap builders."""
from collections import Counter, defaultdict
from decimal import Decimal
import hashlib
import html
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'docs/data/l10-medigap-2026-10-28'
WORK=BASE/'gap-resolution-r4'


def read(p):return json.loads(Path(p).read_text())
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def norm(s):return ' '.join(s.split())


def validate(out=None):
    out=Path(out) if out is not None else WORK/'build-r1'
    index=read(WORK/'case-index.json');case_index={r['case']:r for r in index}
    source_rows={}
    expected_selected=set()
    with (BASE/'build-r2/filing-metadata.jsonl').open() as source:
        for line in source:
            r=json.loads(line);assert r['id'] not in source_rows;source_rows[r['id']]=r['source_native'];n=r['source_native']
            if n['FilingType'] in ['Rates','Both'] and n['FinalAction']=='APPROVED' and n['FileDt'][-4:] in ['2024','2025','2026']:
                expected_selected.add((n['AppSrc'],n['FileLogNumber'],n['FilingId']))
    seen=[]
    for r in index:
        native_rows=[source_rows[i] for i in r['source_row_ids']];seen.extend(r['source_row_ids'])
        assert all((n['AppSrc'],n['FileLogNumber'],n['FilingId'])==(r['app_src'],r['case'],r['filing_id']) for n in native_rows)
        assert set(r['companies'])=={n['CoNm'] for n in native_rows}
        assert set(r['naics'])=={str(n['NaicCoCd']) for n in native_rows}
        assert set(r['forms'])=={n['FormNum'] for n in native_rows if n['FormNum']}
        assert set(r['market_names'])=={n['MktNm'] for n in native_rows if n['MktNm']}
    assert len(seen)==len(set(seen))==len(source_rows) and set(seen)==set(source_rows)
    assert {(r['app_src'],r['case'],r['filing_id']) for r in index if r['selected_for_metadata']}==expected_selected
    selected={r['case'] for r in index if r['selected_for_metadata']}
    original={'17-20542','20-013251','21-014407','22-005454','23-008889'}
    snapshots={p.stem:read(p) for p in (WORK/'filings').glob('*.json')}
    assert set(snapshots)==selected|original
    status=read(WORK/'acquisition-status.json')
    assert not status['failures'] and status['complete_selected_metadata'] is True
    native={};receipts={};receipt_count=0
    for p in (WORK/'acquisition').glob('*.json'):
        r=read(p);raw=WORK/'acquisition/raw'/r['sha256']
        assert sha(raw)==r['sha256'] and raw.stat().st_size==r['bytes'] and r['http_status']==200
        assert r['endpoint'] in ['/Search/GetDocuments','/Search/GetFiling'] and r['retries']==0
        case=r['inputs']['fn'];assert case in snapshots
        assert r['inputs']['src']==case_index[case]['app_src']
        native[(case,r['endpoint'])]=read(raw);receipts[(case,r['endpoint'])]=r;receipt_count+=1
    parent={d['source_native']['FileLogNumber']:d['source_native'] for d in read(BASE/'build-r2/filing-details.json')}
    for case,s in snapshots.items():
        if (case,'/Search/GetFiling') in native:expected=native[(case,'/Search/GetFiling')]
        elif case in parent:expected=parent[case]
        else:expected=read(BASE/'filing-reconciliation-r3/metadata-r1'/(case+'-detail.json'))
        assert expected==s['detail'] and expected['FileLogNumber']==case
    document_entries=read(out/'document-registry.json');native_document_count=0
    for case,s in snapshots.items():
        source=native[(case,'/Search/GetDocuments')];assert source['IsRestricted'] is False
        ds=[r for r in document_entries if r['case']==case];assert len(ds)==len(source['Documents'])
        for i,(d,r) in enumerate(zip(source['Documents'],ds)):
            assert (r['title'],r['type'],r['date'],r['status'],r['trade_secret'],r['form_number_raw'],r['sequence_id'])==(d['DocumentTitle'],d['DocumentType'],d['DocumentDate'],d['DocumentStatus'],d['IsTradeSecret'],d.get('FormNumber'),d.get('SequenceId'))
            assert r['source_response_sha256']==receipts[(case,'/Search/GetDocuments')]['sha256']
            assert r['source_pointer']==f'/Documents/{i}' and r['document_content_obtained'] is False
            assert r['public_request_candidate']==(not d['IsTradeSecret'])
            native_document_count+=1
    forms=read(out/'exact-form-leads.json');expected_forms=[]
    for case,s in sorted(snapshots.items()):
        for i,f in enumerate(s['detail'].get('Forms') or []):expected_forms.append((case,i,f['FormNum'],f.get('MktNm')))
    actual_forms=[(f['case'],int(f['source_pointer'].split('/')[-1]),f['form_number_raw'],f['market_name_raw']) for f in forms]
    assert sorted(actual_forms,key=str)==sorted(expected_forms,key=str)
    filing_records=read(out/'filing-records.json');assert {r['case'] for r in filing_records}==set(snapshots)
    for r in filing_records:
        source=snapshots[r['case']]['detail']
        assert (r['filing_type'],r['final_action'],r['product_raw'])==(source['FilingType'],source['FinalAction'],source.get('ProdNm'))
        assert r['actual_rate_period'] is None and r['current_sale']=='unknown' and r['acceptance']=='pending'
        for e in r['cycle']['evidence']:
            assert any(d['title']==e['title'] and d['type']==e['type'] for d in document_entries if d['case']==r['case'])
            assert e['year']==int(re.search(r'(?<!\d)(202[4-9])(?:\d{2})?(?!\d)',e['title'])[1])
    blocks=read(out/'schedule-block-leads.json')
    assert {b['document_id'] for b in blocks}=={d['id'] for d in document_entries if d['type']=='Rate Schedule'}
    assert all(b['actual_rate_period'] is None and b['title_dates_are_not_premium_periods'] is True for b in blocks)
    catalog=read(BASE/'build-r2/insurer-catalog.json');matrix=read(out/'company-evidence-matrix.json')
    assert {m['company_raw'] for m in matrix}=={m['company_name_raw'] for m in catalog}
    for m in matrix:
        assert set(m['exact_name_case_ids'])=={c for c,s in snapshots.items() if m['company_raw'] in case_index[c]['companies']}
        assert m['current_sale']=='unknown' and m['complete_2026_product_census'] is False
    assert sum(m['in_CHOICES_samples'] and bool(m['exact_name_case_ids']) for m in matrix)==34
    future={r['case'] for r in read(out/'future-cycle-holds.json')}
    assert future=={'26-030965','26-034262','26-037280','26-037285','26-038954','26-038999','26-041590'}
    for case in future:assert any('2027' in d['title'] and re.search(r'memo|certification|actcert',d['title'],re.I) for d in document_entries if d['case']==case)
    supplied={'26-007296','26-018953','26-023593','26-036521','26-037280','26-037285'}
    downloads=read(out/'download-items.json')
    assert len({d['case'] for d in downloads})==len(downloads)
    assert not {d['case'] for d in downloads}&(future|supplied)
    assert {d['case'] for d in downloads if d['tier']=='1'}==original|{'25-043172','25-043125','25-007663','25-030887','25-023045','25-039153'}
    sample_names={c['company_name_raw'] for c in catalog if c['choices_observation_count']}
    expected_extra={c for c in selected if case_index[c]['filed_date'][-4:] in ['2025','2026'] and set(case_index[c]['companies'])&sample_names}-future-supplied
    assert {d['case'] for d in downloads}==expected_extra|original|{'25-007663','25-030887','25-023045','25-039153','25-043172','25-043125'}
    for d in downloads:
        assert d['public_documents']==sum(r['public_request_candidate'] for r in document_entries if r['case']==d['case'])
        assert d['actual_rate_period'] is None and d['url']=='https://irfssearch.floir.gov/' and d['permanent_filing_link_verified'] is False
    broader=read(out/'broader-census-classification-queue.json')
    assert {r['case'] for r in broader}=={c for c in selected if not set(case_index[c]['companies'])&sample_names}
    public_results=validate_public(out)
    protected=read(WORK/'preservation-before.json')
    assert all(sha(ROOT/p)==wanted for p,wanted in protected.items())
    return {'passed':True,'native_metadata_receipts_checked':receipt_count,'filings_checked':len(snapshots),
        'parent_metadata_rows_accounted':len(source_rows),'retained_case_groups_accounted':len(index),
        'recent_approved_rate_cases_checked':len(selected),'document_entries_checked':native_document_count,
        'exact_form_metadata_entries_checked':len(forms),'schedule_block_leads_accounted':len(blocks),
        'company_names_accounted':len(matrix),'sample_companies_with_filing_leads':34,
        'owner_download_items_checked':len(downloads),'future_cycle_holds_checked':len(future),
        'protected_files_unchanged':len(protected),**public_results,
        'unexplained_modeled_value_mismatches':0,'human_acceptance':None,'consumer_release_enabled':False,'full_l10_complete':False}


def validate_public(out):
    pub=WORK/'public-sources';receipts=0
    for p in pub.glob('*.json'):
        r=read(p);raw=pub/'raw'/r['sha256'];assert sha(raw)==r['sha256'] and raw.stat().st_size==r['bytes'];receipts+=1
    rows=read(out/'group-rate-observations.json');assert len({r['id'] for r in rows})==len(rows)
    text=lambda name:(pub/'text'/(name+'.txt')).read_text().split('\f')
    pattern=r'Issue\s+Age\s*(<65|65-69|70-74|75-79|80\+)\s*(\$[\d,]+\.\d{2})\s*(\$[\d,]+\.\d{2})'
    expected=[]
    pairs=re.findall(pattern,text('fsrbc-cigna-rates-2026.pdf')[0]);assert len(pairs)==15
    for ri,(age,left,right) in enumerate(pairs):
        for zone,amount in [('FL_330_334',left),('FL_except_330_334',right)]:expected.append(('FSRBC_Cigna_proposal',['F','G','N'][ri//5],age,zone,amount,'not_explicitly_labeled_in_proposal'))
    triples=re.findall(pattern+r'\s*(\$[\d,]+\.\d{2})',text('orange-county-retiree-guide-2026.pdf')[42]);assert len(triples)==10
    for ri,(age,*amounts) in enumerate(triples):
        for plan,amount in zip(['G','F','N'],amounts):expected.append(('Orange_County_retirees',plan,age,'FL_except_330_334' if ri<5 else 'FL_330_334',amount,'USD/month'))
    triples=re.findall(pattern+r'\s*(\$[\d,]+\.\d{2})',text('fsrbc-annual-enrollment-2026.pdf')[24]);assert len(triples)==4
    for age,*amounts in triples:
        for plan,amount in zip(['G','N','F'],amounts):expected.append(('FSRBC_HealthSpring_guide',plan,age,'FL_except_330_334',amount,'USD/month'))
    actual=[(r['group'],r['plan_letter_raw'],r['issue_age_band_raw'],r['zone'],r['amount_raw'],r['unit']) for r in rows]
    assert sorted(actual)==sorted(expected)
    assert 'Retiree Monthly Rates (Premiums)' in text('orange-county-retiree-guide-2026.pdf')[41]
    assert '2026 Monthly Premiums' in text('fsrbc-annual-enrollment-2026.pdf')[24]
    for r in rows:
        assert sha(ROOT/r['source_pdf'])==r['source_sha256'] and r['amount_cents']==int(Decimal(r['amount_raw'].replace('$','').replace(',',''))*100)
        assert r['filed_rate_approval_period'] is None and r['policy_form'] is None and r['personal_quote'] is False and r['acceptance']=='pending'
    conditions=read(out/'group-conditions.json')+read(out/'published-discount-questionnaire.json')
    for c in conditions:
        doc=Path(c['source_pdf']).name
        assert norm(c['excerpt']) in norm(text(doc)[c.get('page',1)-1])
        assert sha(ROOT/c['source_pdf'])==c['source_sha256'] and c['acceptance']=='pending'
    comparisons=read(out/'group-comparisons.json');by_id={r['id']:r for r in rows}
    for c in comparisons:
        x,y=by_id[c['left_id']],by_id[c['right_id']]
        assert (x['plan_letter_raw'],x['issue_age_band_raw'],x['zone'])==(y['plan_letter_raw'],y['issue_age_band_raw'],y['zone'])
        assert c['same_amount']==(x['amount_cents']==y['amount_cents']) and c['groups_merged'] is False
    assert Counter(c['same_amount'] for c in comparisons)=={True:41,False:1}
    claims=read(out/'carrier-published-claims.json')
    for c in claims:
        r=read(pub/(c['source_id']+'.json'));raw=(pub/'raw'/r['sha256']).read_text()
        raw=re.sub(r'<(script|style)\b[^>]*>.*?</\1>',' ',raw,flags=re.S|re.I)
        flattened=norm(html.unescape(re.sub(r'<[^>]+>',' ',raw)))
        assert norm(c['excerpt']) in flattened and c['source_sha256']==r['sha256']
        assert c['current_or_future_sale']=='not_determined'
    metadata={}
    with (BASE/'build-r2/filing-metadata.jsonl').open() as source:
        for line in source:
            r=json.loads(line);metadata[r['id']]=r['source_native']
    crosswalk=read(out/'carrier-form-crosswalk.json')
    for c in crosswalk:
        for match in c['exact_metadata_matches']:
            source=metadata[match['row_id']];assert source['CoNm']==c['company'] and source['FormNum']==c['form_code_published']==match['form_raw']
        assert c['actual_2026_period'] is None and c['acceptance']=='pending'
    return {'public_source_receipts_checked':receipts,'group_amount_observations_checked':len(rows),
        'group_conditions_and_questionnaire_claims_checked':len(conditions),'group_comparisons_checked':len(comparisons),
        'carrier_published_claims_checked':len(claims),'carrier_form_crosswalk_entries_checked':len(crosswalk)}


if __name__=='__main__':
    result=validate()
    if not (WORK/'build-r1/SEALED').exists():(WORK/'validation.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps(result,indent=2))
