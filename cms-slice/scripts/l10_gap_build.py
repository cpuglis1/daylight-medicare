"""L10 additive evidence mapping and explicit owner download handoff."""
from collections import Counter, defaultdict
import csv
import json
from pathlib import Path
import re

from l10_gap_sources import ROOT, BASE, WORK, ACQ, read, write, sha

PORTAL='https://irfssearch.floir.gov/'
PRIOR=['25-007663','25-030887','25-023045','25-039153']
BLUE=['25-043172','25-043125']
ORIGINAL=['17-20542','20-013251','21-014407','22-005454','23-008889']
SUPPLIED={'26-007296','26-018953','26-023593','26-036521','26-037280','26-037285'}


def cycle_evidence(documents):
    """Memo/certification titles are cycle leads, never actual effective dates.

    A trailing 2026 revision date on a 2027 memo cannot turn it into 2026.
    Actuarial trend/projection and administrative years are not cycle evidence.
    """
    evidence=[]
    for d in documents:
        title=d['title']
        if not re.search(r'actmem|memo|certification|actcert',title,re.I):continue
        if re.search(r'authoriz|projection|experience|trend',title,re.I):continue
        m=re.search(r'(?<!\d)(202[4-9])(?:\d{2})?(?!\d)',title)
        if m:evidence.append({'year':int(m[1]),'title':title,'type':d['type']})
    years=sorted({r['year'] for r in evidence})
    state='mixed_cycle_titles_require_review' if 2027 in years and 2026 in years else '2027_cycle_title_hold' if 2027 in years else '2026_cycle_title_candidate' if 2026 in years else 'period_unestablished_from_metadata'
    return {'state':state,'years_observed_in_memo_titles':years,'evidence':evidence,'actual_premium_effective_period':None}


def build(out=None):
    out=Path(out) if out is not None else WORK/'build-r1'
    if (out/'SEALED').exists():raise ValueError('Use a new revision')
    out.mkdir(exist_ok=True)
    index=read(WORK/'case-index.json');by_case={r['case']:r for r in index}
    catalogs=read(BASE/'build-r2/insurer-catalog.json')
    records={};documents=[];forms=[];blocks=[]
    for p in sorted((WORK/'filings').glob('*.json')):
        record=read(p);case=record['case'];detail=record['detail'];rec=by_case[case]
        matching=list(ACQ.glob('attachments-*-'+case+'.json'));assert len(matching)==1
        receipt=read(matching[0]);raw=read(ACQ/'raw'/receipt['sha256'])
        ds=[]
        for i,d in enumerate(raw['Documents']):
            entry={'id':f'{case}:document:{i}','case':case,'title':d['DocumentTitle'],'type':d['DocumentType'],
                   'date':d['DocumentDate'],'status':d['DocumentStatus'],'trade_secret':d['IsTradeSecret'],
                   'form_number_raw':d.get('FormNumber'),'sequence_id':d.get('SequenceId'),
                   'source_response_sha256':receipt['sha256'],'source_pointer':f'/Documents/{i}',
                   'document_content_obtained':False,'public_request_candidate':not d['IsTradeSecret']}
            ds.append(entry);documents.append(entry)
            if entry['type']=='Rate Schedule':
                blocks.append({'document_id':entry['id'],'case':case,'title_raw':entry['title'],
                               'status':entry['status'],'trade_secret':entry['trade_secret'],
                               'filing_companies':detail.get('Companies',[]),'title_dates_are_not_premium_periods':True,
                               'current_sale':'unknown','actual_rate_period':None})
        for i,f in enumerate(detail.get('Forms') or []):
            forms.append({'case':case,'source_pointer':f'/Forms/{i}','form_number_raw':f['FormNum'],
                          'market_name_raw':f.get('MktNm'),'current_sale':'unknown'})
        records[case]={'case':case,'companies_raw':rec['companies'],'naics_raw':rec['naics'],
                       'filed_date':rec['filed_date'],'product_raw':detail.get('ProdNm'),
                       'filing_type':detail['FilingType'],'final_action':detail['FinalAction'],
                       'cycle':cycle_evidence(ds),'public_documents':sum(not d['trade_secret'] for d in ds),
                       'restricted_documents':sum(d['trade_secret'] for d in ds),
                       'approved_public_schedules':sum(d['type']=='Rate Schedule' and d['status']=='APPROVED' and not d['trade_secret'] for d in ds),
                       'form_strings':[f['FormNum'] for f in detail.get('Forms') or []],
                       'url':PORTAL,'permanent_filing_link_verified':False,
                       'actual_rate_period':None,'current_sale':'unknown','acceptance':'pending'}
    write(out/'document-registry.json',documents);write(out/'filing-records.json',list(records.values()))
    write(out/'exact-form-leads.json',forms);write(out/'schedule-block-leads.json',blocks)

    matrix=[]
    for company in catalogs:
        naic=company['exact_name_unique_naic'];name=company['company_name_raw']
        exact=[r for r in records.values() if name in r['companies_raw']]
        alias=[r for r in records.values() if name not in r['companies_raw'] and naic in r['naics_raw']]
        matrix.append({'company_raw':name,'naic_exact_name_association':naic,
                       'in_CHOICES_samples':company['choices_observation_count']>0,
                       'exact_name_case_ids':[r['case'] for r in exact],
                       'same_naic_other_name_leads':[r['case'] for r in alias],
                       'same_naic_alias_is_not_accepted_equivalence':True,
                       'current_sale':'unknown','complete_2026_product_census':False})
    write(out/'company-evidence-matrix.json',matrix)

    # Concrete handoff: known questions first, then remaining sample-company
    # 2025/2026 packets. Earlier carry-forward and broader census remain separate.
    requested={};future=[];reserve=[]
    def add(case,tier,purpose):
        r=records[case]
        if case in SUPPLIED:return
        assert r['public_documents']>0
        if case not in requested:requested[case]={'case':case,'tier':tier,'purpose':[purpose],**{k:v for k,v in r.items() if k not in ['case']}}
        elif purpose not in requested[case]['purpose']:requested[case]['purpose'].append(purpose)
    for case in BLUE:add(case,'1','Corrected Blue 2026-cycle table/effective-period source')
    for case in PRIOR:add(case,'1','Prior approved tables/letter for the earlier-2026 interval of supplied forms')
    for case in ORIGINAL:add(case,'1','Original exact policy/application forms and rating/payment/discount conditions')
    sample_names={c['company_name_raw'] for c in catalogs if c['choices_observation_count']}
    for case,r in records.items():
        rec=by_case[case]
        if not set(r['companies_raw'])&sample_names or not rec['selected_for_metadata']:continue
        if r['cycle']['state']=='2027_cycle_title_hold':future.append(r);continue
        if rec['filed_date'][-4:] in ['2025','2026']:
            add(case,'2','Missing sample-company or additional legacy/group product packet; verify actual 2026 applicability from contents')
        else:reserve.append(r)
    items=sorted(requested.values(),key=lambda r:(r['tier'],r['companies_raw'],r['case']))
    write(out/'download-items.json',items);write(out/'future-cycle-holds.json',future)
    write(out/'earlier-carryforward-reserve.json',reserve)
    broader=[r for case,r in records.items() if by_case[case]['selected_for_metadata'] and not set(r['companies_raw'])&sample_names]
    write(out/'broader-census-classification-queue.json',broader)
    with (out/'broader-census-classification-queue.csv').open('w',newline='') as f:
        writer=csv.writer(f);writer.writerow(['case','companies','naics','product','cycle_title_state','public_documents','source_url','next_action'])
        for r in broader:writer.writerow([r['case'],' / '.join(r['companies_raw']),';'.join(r['naics_raw']),r['product_raw'],r['cycle']['state'],r['public_documents'],r['url'],'Classify actual 2026 product/business/county relevance against official collection before requesting every packet'])
    with (out/'download-items.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=['tier','case','company','naic','product','year_evidence','public_documents','approved_public_schedules','restricted_documents','url','purpose'])
        writer.writeheader()
        for r in items:writer.writerow({'tier':r['tier'],'case':r['case'],'company':' / '.join(r['companies_raw']),
            'naic':';'.join(r['naics_raw']),'product':r['product_raw'],'year_evidence':r['cycle']['state'],
            'public_documents':r['public_documents'],'approved_public_schedules':r['approved_public_schedules'],
            'restricted_documents':r['restricted_documents'],'url':r['url'],'purpose':' | '.join(r['purpose'])})
    coverage={'metadata_cases_inspected':len(records),'selected_recent_rate_cases':421,
              'additional_original_form_cases':len(ORIGINAL),'document_entries':len(documents),
              'exact_form_metadata_entries':len(forms),'rate_schedule_block_leads':len(blocks),
              'company_names_accounted':len(matrix),'sample_companies_with_exact_name_case_leads':sum(m['in_CHOICES_samples'] and bool(m['exact_name_case_ids']) for m in matrix),
              'download_items':len(items),'download_items_by_tier':dict(Counter(r['tier'] for r in items)),
              'future_cycle_case_holds':len(future),'earlier_sample_carryforward_reserve':len(reserve),
              'broader_recent_case_classification_queue':len(broader),
              'human_acceptance':None,'consumer_release_enabled':False,'full_l10_complete':False}
    write(out/'coverage.json',coverage);return coverage


if __name__=='__main__':print(json.dumps(build(),indent=2))
