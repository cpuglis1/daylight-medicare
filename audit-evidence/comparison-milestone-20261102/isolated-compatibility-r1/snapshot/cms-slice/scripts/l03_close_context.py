"""L03 r3 carrier-context, supplemental document and review boundaries.

Public-route absence is an as-of observation, never proof no private/future notice
exists. PA service selections are not procedure-code coverage determinations.
"""
from __future__ import annotations
import collections,html,json,pathlib,re,urllib.parse
import l03_close as c
from l03_close_sources import *

def anchors(t,base):
    return [{'url':urllib.parse.urljoin(base,html.unescape(u)),'label':re.sub(r'\s+',' ',re.sub('<[^>]+>',' ',html.unescape(l))).strip()} for u,l in re.findall(r'''<a\b[^>]*href=["']([^"']+)["'][^>]*>(.*?)</a>''',t,re.I|re.S)]

def policy_packets():
    packets=[]
    for o,m in MATRIX.items():
        if m['document_matches']['EOC']['status']!='matched_for_research':continue
        glob=[]
        for n,p in enumerate(pages(o),1):
            # Full global chapter context is retained, without a keyword-only assertion.
            if n>8 and re.search(r'Chapter\s+3\b',p[:500],re.I):glob.append(c.ep(o,'EOC',n))
            elif n>25 and re.search(r'Chapter\s+4\b',p[:500],re.I) and re.search(r'SECTION\s+[12]\b|Section\s+[12]\.',p,re.I) and re.search(r'prior author|medically necessary|maximum out.of.pocket',p,re.I):glob.append(c.ep(o,'EOC',n))
        sb=c.hits(o,r'prior authorization|referral',k='SB')
        packet={'offering_id':o,'global_EOC_evidence_ids':sorted(set(glob)),'SB_authorization_referral_evidence_ids':sb,'carrier_chart_rows':[r['id']for r in c.ROWS if r['offering_id']==o],'interpretation':['Covered-service rules are conjunctive: covered service, medical necessity/Medicare criteria, network/setting, PA/referral where applicable, then cost sharing and limits.','HMO exceptions for emergency, urgently needed care and qualifying dialysis away from home remain separate from routine out-of-network coverage. PPO/POS options remain distinct.','May require authorization is conditional; a source selected family is not a requirement for every procedure. Referrals, PA, notification and medical necessity are separate concepts.','Published source conditions are retained and explained; no personal eligibility, provider participation or clinical-approval computation is authorized.','Every shared allowance/cap has one budget, its own period and eligible uses; conditional SSBCI enhancements do not imply universal access.','Charge bands, lifetime/benefit-period limits, plan deductibles, service deductibles and medical MOOP keep their own scope. No sum or personal annual total is calculated.'],'accepted':False,'consumer_usable':False}
        if m['parent']=='Humana Inc.':packet['additional_PA_sources']=['HUMANA-PAL-1','HUMANA-PAL-3']+(['HUMANA-PAL-2']if o=='2026:H1036:340:000'else [])
        packets.append(packet)
    dump(R3/'plan-condition-packets.json',packets)
    return packets

def PA_dispositions(packets):
    pm={p['offering_id']:p for p in packets};out=[]
    for r in c.read(R2/'authorization-referral-comparison.jsonl.gz'):
        o=r['offering_id'];p=pm.get(o);sel=r['CMS']['selected_service']
        if not p:state='restricted_carrier_source';interpretation='CMS source control only; inherited access restriction prevents carrier comparison.'
        elif not sel:state='not_selected_no_universal_absence_inference';interpretation='Not selected in this CMS list. Preserve exact carrier rules and general exceptions; never infer the family can never require PA/referral.'
        elif r['carrier_condition_language_located']:state='selected_conditional_carrier_family_language';interpretation='CMS selects family; retained EOC chart contains conditional requirement language. Preserve qualifiers and exceptions; this is not approval or a universal requirement.'
        elif p['SB_authorization_referral_evidence_ids']:state='selected_global_or_SB_policy_only';interpretation='CMS family selection retained with full SB/global EOC policy. No exact child-family corroboration claimed. Consult retained procedure/PA list or carrier for the particular service; do not display a definite requirement from source flag alone.'
        else:state='selected_no_exact_carrier_family_statement';interpretation='Full source retained, but exact family condition is not explicitly corroborated. Hold definite requirement/absence claim.'
        out.append({**r,'r3_state':state,'interpretation':interpretation,'plan_condition_packet':o if p else None,'additional_PA_sources':p.get('additional_PA_sources',[])if p else [],'exact_child_condition_verified':False,'accepted':False,'consumer_usable':False})
    c.write(R3/'authorization-referral-dispositions.jsonl.gz',out);return out

def documents():
    old=json.loads((DATA/'source-manifest.json').read_text())['sources'];new=json.loads((R3/'source-manifest.json').read_text())['sources'];routes=[]
    aet=json.loads((R3/'aetna-public-route-links.json').read_text())
    for r in aet:routes.append({'offering_id':'2026:'+r['offering'].replace('-',':')+':000','route':r['url'],'verified_heading':r['heading'],'links':r['links'],'result':'2026 exact-plan public DOM inspected; no specifically labelled medical rider/errata/addendum link in document list','as_of':'2026-10-25','private_or_unpublished_notices_excluded':True})
    for s in new:
        if s['kind'] not in ['current_public_document_route','discovery']:continue
        if not s.get('path'):continue
        t=pathlib.Path(s['path']).read_text(errors='replace');a=anchors(t,s.get('final_url',s['url']))
        routes.append({'source_id':s['id'],'url':s['url'],'sha256':s['sha256'],'links':a,'revision_label_links':[x for x in a if re.search(r'rider|errata|addendum|amendment|correction',x['label'],re.I)],'as_of':'2026-10-25','result':'Retained public HTML/links; no universal absence inference. Humana member-document route requires member details for individualized notices.'})
    dump(R3/'public-document-route-checks.json',routes)
    aset={x['url']for r in aet for x in r['links']};supp=[]
    for s in old+new:
        if s['kind']not in ['supplemental_detail','supplemental_benefit_document','prior_authorization_list','coverage_determination']:continue
        if not s.get('text_path'):continue
        t=pathlib.Path(s['text_path']);t=t if t.is_absolute()else DATA/t
        body=t.read_text();pg=body.split('\f');pg=[p for p in pg if p.strip()]
        placeholder='please check back soon' in body.lower() and len(body.strip())<200
        if placeholder:status='carrier_placeholder_not_benefit_evidence';decision='Official current link repeats placeholder. Do not count as collected dental benefits. Use exact EOC dental schedule; separate public explainer remains missing.'
        elif s['kind']=='coverage_determination':status='procedural_EOC_extract';decision='Document begins EOC Chapter 9 appeals/complaints. It does not replace the medical benefit chart or supply a new PA/rider schedule.'
        elif s['kind']=='prior_authorization_list':status='dated_PA_source_retained';decision='Retain full code/category list and stated scope. Notification is not prior approval; urgent/emergent and transition exceptions preserved. Revised lists do not establish full-year historical criteria.'
        elif 'MemberHandbook'in s['url']:status='educational_handbook_EOC_controls';decision='Plan-specific 2026 handbook, educational summary. Its own legal text directs to EOC for exclusions/limits/conditions. Do not overwrite exact EOC or compute personal outcomes.'
        elif '/otc/'in s['url']:status='wallet_conditions_reconciled';decision='Guide requires individual wallet letter for amount/period; use published plan EOC amount. Approved products/retailers, no cash/ATM, over-balance member payment, taxes and expiry without rollover are retained. Catalog item prices are not a personal drug-price feed.'
        else:status='benefit_detail_retained_with_EOC';decision='Carrier supplemental dental/vision/hearing/transport detail linked from exact 2026 public plan route; retain covered items, vendor/network, booking, frequency, allowances and over-limit/exclusion clauses with EOC. No individualized coverage approval inferred.'
        linked=['2026:'+r['offering'].replace('-',':')+':000'for r in aet if any(l['url']==s['url']for l in r['links'])]
        supp.append({'source_id':s['id'],'url':s['url'],'sha256':s['sha256'],'pages':len(pg),'linked_offerings':linked,'status':status,'decision':decision,'complete_text_sha256':sha(t.read_bytes()),'source_text_path':str(t),'accepted':False})
    dump(R3/'supplemental-document-reconciliation.json',supp)
    dump(R3/'revision-boundaries.json',{'as_of':'2026-10-25','specific_medical_benefit_amendment_identified_in_307_references':False,'generic_notice_is_not_missing_named_document':True,'known_history_gap':'Humana Florida fully-integrated January and July labels both resolve to the same July 1 2026 list revised September 28 2026. January snapshot is not established. General MA January list is revised June 1; July list revised October 1. These snapshots cannot establish all historical PA changes.','member_notice_boundary':'Member-specific/private notices cannot be proven complete from public sources; no invented member credentials or outreach.','placeholder_gap':'Aetna LibertyDen200HMOMand_DSNP.pdf remains a one-page placeholder, including current route recheck.','acceptance':'Pending Chris Puglisi L03 review; L01 acceptance does not transfer.'})
    return routes,supp

def field_outcomes():
    am=json.loads((R3/'amount-issue-decisions.json').read_text());mp={}
    for r in am:
        for s in r['source_fields']:mp[(r['offering_id'],r['category_code'],s['source']['member'],s['source']['record_ordinal'],s['source']['field'])]=r
    out=[]
    for x in c.read(R2/'field-comparison-complete-chart-ledger.jsonl.gz'):
        s=x['source'];k=(x['offering_id'],x['category_code'],s['member'],s['record_ordinal'],s['field']);r=mp.get(k);state=x['comparison_state']
        if r:new=r['r3_state']
        elif state=='condition_or_source_detail_retained_for_exact_interpretation':new='interpreted_source_control_with_carrier_context'
        elif state.startswith('typed_value_occurs'):new='value_occurrence_retained_with_source_context_not_independent_verification'
        else:new=state
        out.append({**x,'r3_state':new,'r3_amount_issue_id':r['issue_id']if r else None,'condition_interpretations':'condition-interpretations.jsonl.gz','carrier_context':'plan-condition-packets.json','carrier_corroborated':False,'accepted':False,'consumer_usable':False})
    c.write(R3/'field-dispositions.jsonl.gz',out);return out

def run():
    c.run();p=policy_packets();a=PA_dispositions(p);ro,s=documents();fields=field_outcomes();dump(R3/'evidence-pages.json',c.E)
    sm=json.loads((R3/'decision-summary.json').read_text());sm.update(plan_condition_packets=len(p),PA_referral_comparisons=len(a),PA_referral_states=dict(collections.Counter(r['r3_state']for r in a)),supplemental_documents=len(s),supplemental_states=dict(collections.Counter(r['status']for r in s)),field_references_accounted=len(fields),evidence_pages=len(c.E))
    dump(R3/'decision-summary.json',sm);print(json.dumps({k:sm[k]for k in ['plan_condition_packets','PA_referral_states','supplemental_states','field_references_accounted']},indent=2))
if __name__=='__main__':run()
