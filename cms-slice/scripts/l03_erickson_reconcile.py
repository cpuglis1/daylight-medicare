"""Reconcile new owner-supplied L03 sources without inheriting approval.

Full source text and conditions remain available alongside typed CMS records.
Service headings and literal amounts identify comparison candidates; they never
turn into an independently verified flat benefit or a coverage denial.
"""
from __future__ import annotations
import collections, decimal, gzip, json, pathlib, re
import l03_erickson_documents as d
from l03_reconcile import ANCHORS, anchor_for
from l03_reconcile_charts import HEADINGS, CAT_SECTION

EXTRA_HEADINGS={
 'annual_physical':'Annual routine physical exam','mammography':'Breast cancer screening',
 'cardiovascular_behavior':'Cardiovascular disease risk reduction',
 'cardiovascular_screen':'Cardiovascular disease testing',
 'alcohol':'Screening and counseling to reduce alcohol misuse',
 'hepatitis_c':'Screening for Hepatitis C', 'lung_screen':'Screening for lung cancer',
 'sti_screen':'Screening for sexually transmitted infections',
 'physician':'Physician/practitioner services', 'vision':'Vision services',
 'inpatient_mental':'Inpatient mental health care',
 'outpatient_diagnostics':'Outpatient diagnostic tests and therapeutic',
 'otc':'Over-the-Counter', 'ssbci':'Special supplemental benefits for the chronically ill',
 'ssbci2':'Special Supplemental Benefits', 'prep':'Pre-exposure prophylaxis',
 'dental_benefit':'Dental benefit','hearing_benefit':'Hearing benefits',
 'otc2':'Wellcare Spendables','fitness2':'Health and wellness education programs',
 'food':'Food and produce','utilities':'Utilities','pest':'Pest control',
 'flex':'Flex Card','carecoord':'Care coordination',
 'meals3':'Meals','fitness3':'SilverSneakers','fitness4':'Silver&Fit',
 'fitness5':'Renew Active','fitness6':'Fitness benefit',
 'nurse':'Nurse advice line','nurse2':'24-hour nurse',
 'inpatient_mental':'Inpatient services in a psychiatric',
 'outpatient_substance2':'Outpatient substance',
 'home_bath':'Home and bath safety devices',
 'post_discharge':'Post-Discharge Personal Home Care',
 'smoking_extra':'Smoking cessation program',
 'otc_cvs':'CVS Over-the-Counter (OTC) Wallet',
 'otc_unhyphenated':'Over the Counter (OTC) products',
 'nurseline':'24/7 Nurseline',
 'fall_prevention':'Fall prevention',
 'everyday':'Everyday Options Allowance',
 'support_shared':'Support services',
 'healthy_options':'Healthy Options Allowance',
 'humana_healthy_options':'Humana Healthy Options Allowance',
 'personal_home_care':'Personal Home Care (PHC)',
}
CAT_EXTRA={'14b':['annual_physical'],'14a':['alcohol','prep'],
 '14c1':['fitness2'],'13b':['otc2','otc_cvs','otc_unhyphenated','healthy_options','humana_healthy_options'],'13c':['meals3'],
 '14c4':['fitness2','fitness3','fitness4','fitness5','fitness6'],
 '14c7':['nurse','nurse2','fitness2','nurseline'],
 '14c8':['home_bath','fall_prevention','everyday'],
 '14c21':['post_discharge','support_shared','personal_home_care'],
 '14c22':['support_shared'],
 '14c16':['support_shared'],
 '14c3':['smoking_extra','smoking'],
 '13d':['annual_wellness','mammography'],'13e':['colorectal_screen'],
 '14e5':['welcome','physician'],'9d':['outpatient_diagnostics','inpatient'],
 '4':['emergency','urgent','ambulance'],
 '14c':['ssbci','ssbci2','food','utilities','pest','flex','carecoord','fitness','fitness2','fitness3','fitness4','fitness5','fitness6','home_safety','support','caregiver','pers','meals3']}
def clean(t):return re.sub(r'\s+',' ',t.replace('‑','-').replace('–','-').replace('’',"'")).strip(' *•\t®©@6')
def page_text(p):return p.get('layout_text',p['text'])
def source_evidence(p):
    return {'document_sha256':p['document_sha256'],'pdf_page':p['pdf_page'],
      'text_sha256':p['text_sha256'],'layout_text_sha256':p.get('layout_text_sha256'),
      'extraction_method':p.get('extraction_method','pdftotext_layout')}
def find_chapter(p):
    t=page_text(p);front='\n'.join(t.splitlines()[:10])
    if 'Table of Contents'in front:return None
    m=re.search(r'Chapter\s+(\d+)\b',front,re.I)
    return int(m.group(1))if m else None

def extract_chart(oid,pages):
    pats=[(k,re.compile('^'+re.escape(clean(v)),re.I))for k,v in list(HEADINGS.items())+list(EXTRA_HEADINGS.items())]
    records=[];current=None;chapter_pages=[];global_pages=[];base_chart_ended=False
    for pg in pages:
        t=page_text(pg);chapter=find_chapter(pg)
        if chapter not in [3,4]:continue
        if chapter==3:global_pages.append(source_evidence(pg));continue
        chapter_pages.append(source_evidence(pg));ls=t.splitlines()
        # Optional riders and exclusions are separate contexts, never continued
        # cost columns of the last medical service in the alphabetical chart.
        if re.search(r'Section\s+2\.1\s+Extra|Section\s+\d+\s+Services.*(?:not|aren.t) covered',clean(t),re.I):
            base_chart_ended=True
            if current:records.append(current);current=None
        if base_chart_ended:global_pages.append(source_evidence(pg));continue
        chart=bool(re.search(r'Covered\s+[Ss]ervice|Services that are covered|What\s+you\s+pay',t))
        if not chart:global_pages.append(source_evidence(pg));continue
        col=None
        for l in ls:
            m=re.search(r'What\s+you\s+pay|What\s+you',l,re.I)
            if m and m.start()>25:col=m.start();break
        for lineno,l in enumerate(ls,1):
            left=l[:col]if col else l;sl=clean(left)
            label=next((key for key,pat in pats if pat.match(sl)),None)
            indent=len(l)-len(l.lstrip())
            # Printed headings are short and begin the left service column.
            # Every fragment is retained; short index-only hits are flagged below.
            heading=label is not None and indent<24 and len(sl)<120 and not re.search(r'^(?:See |For |If |The |Our )',sl)
            if label=='blood'and not re.fullmatch(r'Blood(?:\s*[-:(].*(?:continued|cont[.]).*)?',sl,re.I):heading=False
            if heading:
                if current and current['section']==label and ('continued'in sl.lower()or not current['fragments']):pass
                else:
                    if current:records.append(current)
                    current={'id':f'{oid}:r7:chart:{len(records)}','offering_id':oid,'section':label,'source_heading':sl,'fragments':[]}
            if current:
                current['fragments'].append({'pdf_page':pg['pdf_page'],'line':lineno,'text':l,'service_column_end':col,'source_page':source_evidence(pg)})
            else:global_pages.append(source_evidence(pg))
    if current:records.append(current)
    for r in records:
        text='\n'.join(f['text']for f in r['fragments']);r['text']=text;r['text_sha256']=d.sha(text.encode());r['pages']=sorted({f['pdf_page']for f in r['fragments']})
        r['source_evidence']=list({(f['pdf_page'],f['source_page']['document_sha256']):f['source_page']for f in r['fragments']}.values())
        body=' '.join(clean(f['text'][:f['service_column_end']])for f in r['fragments'][1:]if f['service_column_end'])
        # A short, explicit benefit row can be substantive: e.g. UHC individual
        # and group substance-use visits. Length alone discarded those costs.
        explicit_cost=bool(re.search(r'\$\s*\d|\d\s*%|no (?:coinsurance|copayment)|no cost',text,re.I))
        r['index_only_or_short_heading_candidate']=len(body)<80 and not explicit_cost
        r['binding']='source_native_service_family; exact child fields not automatically equivalent'
        r['condition_tags']=[tag for tag,pat in [('authorization',r'prior author|preauthor|precertif|double dagger'),('referral',r'referral'),('network',r'in.network|out.of.network|network provider'),('deductible',r'deductible'),('period',r'per year|each year|every year|per month|each month|calendar year|every \d|once|twice'),('limits',r'limited|limit|maximum|up to|unlimited'),('qualification',r'eligible|eligibility|qualif|chronic|medical necessity|medically necessary|QMB|Medicaid'),('exception',r'waiv|unless|except|if you|if the'),('exclusion',r'not cover|excluded|exclusion|not included') ]if re.search(pat,text,re.I)]
        r['carrier_corroborated_flat_benefit']=False;r['accepted_for_reference']=False
    unique=lambda a:list({(x['document_sha256'],x['pdf_page']):x for x in a}.values())
    return records,unique(chapter_pages),unique(global_pages)

def value_occurs(raw,unit,text):
    try:n=decimal.Decimal(str(raw))
    except decimal.InvalidOperation:return False
    z=format(n.normalize(),'f');digits=re.escape(z)
    if n==n.to_integral():digits=rf'{int(n):,}'.replace(',',r',?')+r'(?:\.00)?'
    else:digits+=r'0*'
    if unit and unit.startswith('USD'):pat=r'\$\s*'+digits+r'(?!\d|\.\d)'
    elif unit=='percent':pat=r'(?<![\d.])'+digits+r'\s*%'
    else:return False
    return bool(re.search(pat,text))

def reconcile(require_complete_intake=True):
    if (d.ROOT/'manifest.json').exists():raise RuntimeError('Sealed r7 is immutable')
    import l03_scoped_reference as accepted
    accepted.require_review()
    oldcat=d.load(d.R1/'carrier-document-catalog.json');newcat=d.load(d.ROOT/'source-catalog.json')
    if require_complete_intake and len(newcat)!=53:raise RuntimeError('Intake incomplete; wait for all 53 unique documents')
    cat={x['sha256']:x for x in oldcat+newcat};byhash=collections.defaultdict(list)
    for p in d.rows(d.R1/'carrier-pages.jsonl.gz'):byhash[p['document_sha256']].append(p)
    for p in d.rows(d.ROOT/'new-source-pages.jsonl.gz'):byhash[p['document_sha256']].append(p)
    for h in byhash:byhash[h].sort(key=lambda p:p['pdf_page'])
    relations=d.load(d.ROOT/'document-relations.json');matrix=d.load(d.R1/'plan-document-matrix.json')
    newrel=collections.defaultdict(dict)
    for r in relations:
        if r['visible_front_matter_identity_match']:newrel[r['offering_id']][r['kind']]=r
    plans=[];charts=[];contexts=[];sbviews=[];riders=[];byoff=collections.defaultdict(list);all_benefits=list(d.rows(d.R2/'benefit-records.jsonl.gz'))
    for b in all_benefits:byoff[b['offering_id']].append(b)
    for old in matrix:
        o=old['offering_id'];m={**old,'document_matches':{k:dict(v)for k,v in old['document_matches'].items()}}
        for k in ['SB','EOC']:
            # The accepted old evidence stays primary for already documented plans.
            if m['document_matches'][k]['status']=='matched_for_research':continue
            r=newrel[o].get(k)
            if r:m['document_matches'][k]={'status':'matched_owner_supplied_for_reconciliation','sha256':r['document_sha256'],'identity_evidence':r}
        ready=all(m['document_matches'][k].get('sha256')for k in ['SB','EOC'])
        m.update(documented=ready,missing_document_kinds=[k for k in ['SB','EOC']if not m['document_matches'][k].get('sha256')],prior_restriction_preserved_as_history=old['document_matches']['EOC']['status']!='matched_for_research',new_acceptance_inherited=False,all_benefits_complete=False)
        plans.append(m)
        if not ready:continue
        sbh=m['document_matches']['SB']['sha256'];eh=m['document_matches']['EOC']['sha256'];eoc=byhash[eh];sb=byhash[sbh]
        rs,chapter,globalps=extract_chart(o,eoc);charts+=rs
        contexts.append({'offering_id':o,'EOC_document_sha256':eh,'SB_document_sha256':sbh,'entire_EOC_chapter_4_evidence':chapter,'global_rules_evidence':globalps,'interpretation':['Attach all coverage conditions: Medicare coverage/medical necessity, assistance basis, service/subtype, setting, network, PA/referral, period and cap.','Never add shared allowances twice; an allowance is not a cash payment and a charge band is not a covered-day limit.','An unselected PBP enhancement or missing chart term does not establish noncoverage.','Exact drug, clinician and pharmacy claims belong to other layers.','Published reference only; no personal eligibility, clinical approval, annual total or recommendation.'],'accepted_for_reference':False})
        for pg in sb:
            text=page_text(pg);view,cols=d.shared_wellcare_view(text,o)if o.startswith('2026:H1032:')else(text,{'shared_plan_columns':False})
            sbviews.append({'offering_id':o,'source_evidence':source_evidence(pg),'text':view,'text_sha256':d.sha(view.encode()),'column_binding':cols,'other_plan_amounts_must_not_be_used':bool(cols.get('shared_plan_columns'))})
        for pg in eoc:
            ls=page_text(pg).splitlines()
            for n,l in enumerate(ls,1):
                if not re.search(r'\briders?\b|\baddendums?\b|\berrata\b|\bamendments?\b|\bcorrections?\b',l,re.I):continue
                ctx='\n'.join(ls[max(0,n-4):min(len(ls),n+4)])
                normal=clean(ctx)
                if re.search(r'Platinum Dental|Optional Supplemental Rider|dental rider',normal,re.I):state='named_optional_dental_rider; separate_benefit_variant_requires_terms'
                elif re.search(r'personal information|your phi|privacy|correction.*information|health information|medical management records',normal,re.I):state='privacy_or_record_right; not medical benefit amendment'
                elif re.search(r'LIS rider|low.income subsidy|Extra Help|prescription drugs',normal,re.I):state='member_specific_PartD_assistance_insert; outside_L03_medical_reference'
                elif re.search(r'notices|affect your coverage|sometimes called|changes to.*coverage|notice of change',normal,re.I):state='generic_notice_reference; not identified applicable amendment'
                elif re.search(r'attachments,? riders,? or other optional coverage',normal,re.I):state='generic_glossary_attachment_definition; no_named_medical_rider'
                else:state='unclassified_named_or_context_reference_requires_source_review'
                riders.append({'offering_id':o,'pdf_page':pg['pdf_page'],'line':n,'source_evidence':source_evidence(pg),'context':ctx,'classification':state,'accepted_for_reference':False})
    d.dump(d.ROOT/'plan-document-matrix.json',plans);d.write_rows(d.ROOT/'carrier-chart-rows.jsonl.gz',charts);d.dump(d.ROOT/'plan-condition-packets.json',contexts);d.write_rows(d.ROOT/'SB-exact-plan-pages.jsonl.gz',sbviews);d.dump(d.ROOT/'rider-reference-reconciliation.json',riders)
    chartmap=collections.defaultdict(list);sbmap=collections.defaultdict(list);ctxmap={c['offering_id']:c for c in contexts}
    for r in charts:
        if not r['index_only_or_short_heading_candidate']:chartmap[(r['offering_id'],r['section'])].append(r)
    for r in sbviews:sbmap[r['offering_id']].append(r)
    services=[];sm={}
    for b in all_benefits:
        o=b['offering_id'];catcode=b['category_code'];sections=CAT_SECTION.get(catcode,[])+CAT_EXTRA.get(catcode,[])
        rs=[x for sec in sections for x in chartmap[(o,sec)]]
        selected=[]
        for pg in sbmap[o]:
            if re.search(anchor_for(catcode),pg['text'],re.I):selected.append(pg)
        text='\n'.join(r['text']for r in rs)
        s={'id':b['id'],'offering_id':o,'category_code':catcode,'service_name':b['service_name'],'category_type_interpretation':b['category_type_interpretation'],'PBP_source':b['pbp'],'PBP_cost_sharing':b['cost_sharing'],'PBP_coverage_controls':b['coverage'],'PBP_authorization_referral':b['conditions']['authorization_and_referral'],'EOC_chart_row_ids':[r['id']for r in rs],'EOC_source_evidence':list({(e['document_sha256'],e['pdf_page']):e for r in rs for e in r['source_evidence']}.values()),'SB_candidate_page_evidence':[p['source_evidence']for p in selected],'plan_condition_packet':o if o in ctxmap else None,'comparison_state':'carrier_source_missing'if o not in ctxmap else'service_family_source_context_retained'if rs else'no_exact_service_heading_binding','exact_child_field_verification':False,'accepted_for_reference':False,'consumer_usable':False}
        s['unmodeled_is_unknown_not_excluded']=True;services.append(s);sm[b['id']]=(s,text)
    d.write_rows(d.ROOT/'service-reconciliation.jsonl.gz',services)
    # Every field is accounted for with fresh evidence candidates. No token-match
    # auto-promotion; existing accepted observations retain their separate receipt.
    fields=[];conditions={};pa=[]
    from l03_close import condition_rule
    for old in d.rows(d.R3/'field-dispositions.jsonl.gz'):
        s,text=sm[old['benefit_record_id']];x={k:old[k]for k in ['benefit_record_id','offering_id','category_code','source','label','semantic_role','normalized','qualified_unit','raw']}
        norm=x['normalized'];unit=x['qualified_unit'];blank=norm.get('state')=='source_blank'
        state='source_blank_retained'if blank else'carrier_source_missing'if not s['plan_condition_packet']else'no_exact_service_heading_binding'if not s['EOC_chart_row_ids']else'dictionary_control_interpreted_carrier_context_attached'
        token=False
        if not blank and unit in ['USD','USD/day','USD/year','USD/month','percent']:
            token=value_occurs(norm.get('value'),unit,text)
            state='typed_amount_occurs_in_service_family; exact_binding_pending'if token else'typed_amount_not_found_in_service_family; exact_binding_pending'
        x.update(r7_state=state,typed_amount_occurrence=token,EOC_chart_row_ids=s['EOC_chart_row_ids'],plan_condition_packet=s['plan_condition_packet'],carrier_corroborated=False,accepted_for_reference=False,consumer_usable=False)
        fields.append(x)
        if not blank and x['semantic_role']not in ['copayment','coinsurance']:
            key=(x['offering_id'],x['source']['member'],x['source']['record_ordinal'],x['source']['field'])
            if key not in conditions:
                rule,meaning=condition_rule(x)
                conditions[key]={'id':'L03-R7-COND-'+d.sha(json.dumps(key).encode())[:20],'offering_id':x['offering_id'],'source':x['source'],'source_label':x['label'],'raw':x['raw'],'decoded':norm,'interpretation_rule':rule,'interpretation':meaning,'service_ids':set(),'EOC_chart_row_ids':set(),'exact_child_condition_verified':False,'accepted_for_reference':False}
            conditions[key]['service_ids'].add(x['benefit_record_id']);conditions[key]['EOC_chart_row_ids'].update(s['EOC_chart_row_ids'])
    for c in conditions.values():
        c['service_ids']=sorted(c['service_ids']);c['EOC_chart_row_ids']=sorted(c['EOC_chart_row_ids'])
    for b in all_benefits:
        s,text=sm[b['id']]
        for name,control in b['conditions']['authorization_and_referral'].items():
            pat=r'prior author|preauthor|precertif'if name=='priorAuthorization'else r'referral'
            found=bool(re.search(pat,text,re.I));selected=control['selected_service']
            state='carrier_source_missing'if not s['plan_condition_packet']else'not_selected; no_universal_absence_inferred'if not selected else'selected_conditional_family_language_retained'if found else'selected; exact_child_carrier_condition_not_established'
            pa.append({'benefit_record_id':b['id'],'offering_id':b['offering_id'],'category_code':b['category_code'],'condition':name,'PBP':control,'EOC_chart_row_ids':s['EOC_chart_row_ids'],'state':state,'exact_child_condition_verified':False,'universal_requirement_or_approval_inferred':False,'accepted_for_reference':False})
    d.write_rows(d.ROOT/'field-dispositions.jsonl.gz',fields);d.write_rows(d.ROOT/'condition-interpretations.jsonl.gz',conditions.values());d.write_rows(d.ROOT/'authorization-referral-dispositions.jsonl.gz',pa)
    summary={'package_id':d.PACKAGE,'working_partial_intake':len(newcat)!=53,'input_offerings':len(plans),'documented_offerings':sum(p['documented']for p in plans),'missing_document_offerings':sum(not p['documented']for p in plans),'missing_required_documents':sum(len(p['missing_document_kinds'])for p in plans),'owner_files':54,'unique_owner_documents_processed':len(newcat),'PBP_service_records_accounted':len(services),'service_field_references_accounted':len(fields),'new_chart_family_rows':len(charts),'SB_plan_page_views':len(sbviews),'source_condition_controls_interpreted':len(conditions),'PA_referral_comparisons':len(pa),'field_states':dict(collections.Counter(x['r7_state']for x in fields)),'service_states':dict(collections.Counter(x['comparison_state']for x in services)),'PA_referral_states':dict(collections.Counter(x['state']for x in pa)),'rider_reference_states':dict(collections.Counter(x['classification']for x in riders)),'accepted_r4_entries_unchanged':len(accepted.lookup({'year':2026})['entries']),'new_accepted_entries':0,'full_L03_complete':False,'literal_or_heading_matches_are_not_semantic_verification':True}
    d.dump(d.ROOT/'summary.json',summary)
    print(json.dumps(summary,indent=2));return summary
if __name__=='__main__':
    import sys
    reconcile(require_complete_intake='--working'not in sys.argv)
