"""Independent accounting and source-integrity checks for additive L03 r3."""
import collections,json,pathlib,gzip
from l03_close_sources import *
from l03_reconcile_reference import verify as verify_r2
from l03_close import read
REPO=pathlib.Path(__file__).resolve().parents[2]
R2_PIN='023f861b503018a89630ab307cf683bc556dcf999e8a42196c242a128a9a6a05'

def key(r):return (r['offering_id'],r['category_code'],r['unit'],r['CMS_value'])
def run():
    checks=[]
    def check(name,ok,detail):
        checks.append({'check':name,'passed':bool(ok),'detail':detail})
        if not ok:raise AssertionError(name+': '+str(detail))
    verify_r2(expected_manifest_sha256=R2_PIN);check('prior_revisions_and_code_hashes',True,'r1/r2 exact manifests and all pinned data/code retained')
    old=json.loads((R2/'unlocated-amount-issues.json').read_text());am=json.loads((R3/'amount-issue-decisions.json').read_text());ev=json.loads((R3/'evidence-pages.json').read_text())
    check('all_252_issue_keys_once',len(am)==252 and len({key(x)for x in am})==252 and {key(x)for x in am}=={key(x)for x in old},len(am))
    check('all_407_original_field_references',sum(len(x['source_fields'])for x in am)==407,407)
    check('all_issue_evidence_and_explicit_gaps',all(x['carrier_evidence_ids'] and all(i in ev for i in x['carrier_evidence_ids']) and x['investigation_complete'] and bool(x['remaining_gap_id'])==x['r3_state'].startswith('held_') for x in am),'Every hold has a named gap, every decision has full page/hash evidence; no empty or pending AI issue disposition')
    # Source-page integrity is checked against actual retained extraction, not a count.
    newer=json.loads((R3/'source-manifest.json').read_text())['sources'];all_docs={**CATALOG,**{s['sha256']:s for s in newer if s.get('text_path')}}
    page_cache={}
    for id,x in ev.items():
        s=all_docs[x['document_sha256']];p=pathlib.Path(s['text_path']);p=p if p.is_absolute()else DATA/p
        if str(p)not in page_cache:page_cache[str(p)]=p.read_text().split('\f')
        page=page_cache[str(p)][x['pdf_page']-1]
        if sha(page.encode())!=x['page_text_sha256'] or '\n'.join(page.splitlines()[x['line_start']-1:x['line_end']])!=x['text']:raise AssertionError('page changed '+id)
    check('all_evidence_pages_match_retained_sources',True,len(ev))
    for s in newer:
        if s.get('path'):
            p=pathlib.Path(s['path']);assert sha(p.read_bytes())==s['sha256']
            if s.get('text_path'):assert sha(pathlib.Path(s['text_path']).read_bytes())==s['text_sha256']
    check('all_new_source_payloads_and_text_hashes',True,len(newer))
    cs=list(read(R3/'condition-interpretations.jsonl.gz'));links=list(read(R3/'condition-service-links.jsonl.gz'));ids={x['id']for x in cs}
    check('condition_reference_accounting',len(cs)==24112 and len(links)==38844 and all(x['condition_id']in ids for x in links),{'unique_source_controls':len(cs),'shared_child_references':len(links)})
    check('no_uninterpreted_condition_fallback',all(x['interpretation_rule']!='dictionary_qualified_control' for x in cs),'Explicit source-question rules, with no consumer/clinical assertion')
    riders=json.loads((R3/'rider-dispositions.json').read_text());check('rider_contexts_and_classes',len(riders)==307 and all(x['classification']!='unclassified_reference_requires_review' and x['context'] and x['evidence_id']in ev for x in riders),dict(collections.Counter(x['classification']for x in riders)))
    ps=json.loads((R3/'plan-condition-packets.json').read_text());check('47_condition_packets',len(ps)==47 and all(p['global_EOC_evidence_ids']and p['carrier_chart_rows']for p in ps),47)
    fields=list(read(R3/'field-dispositions.jsonl.gz'));check('173124_field_reference_accounting',len(fields)==173124 and sum(bool(x['r3_amount_issue_id'])for x in fields)==407,{'references':len(fields),'original_issue_references':sum(bool(x['r3_amount_issue_id'])for x in fields)})
    pa=list(read(R3/'authorization-referral-dispositions.jsonl.gz'));check('14610_PA_referral_comparisons',len(pa)==14610 and sum(x['r3_state']=='restricted_carrier_source'for x in pa)==5056,dict(collections.Counter(x['r3_state']for x in pa)))
    check('no_inherited_acceptance_or_consumer_unlock',all(not x['accepted']and not x['consumer_usable']for x in am+cs+fields+pa),'AI source comparison is separate from qualified acceptance and consumer claims')
    restricted=[o for o,m in MATRIX.items()if m['document_matches']['EOC']['status']=='restricted'];check('25_restricted_offerings_preserved',len(restricted)==25 and not ({p['offering_id']for p in ps}&set(restricted)),restricted)
    before=json.loads((DATA/'protected-before.json').read_text());changed=[p for p,h in before.items()if not (REPO/p).exists()or sha((REPO/p).read_bytes())!=h];check('649_protected_files_unchanged',not changed,{'checked':len(before),'changed':changed})
    dump(R3/'validation-report.json',{'passed':True,'checks':checks,'claim':'Technical integrity and bounded source-accounting validation only; not comprehensive factual approval.'});print(json.dumps({'passed':True,'checks':len(checks),'protected_files':len(before)}));return checks
if __name__=='__main__':run()
