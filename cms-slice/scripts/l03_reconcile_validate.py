"""Integrity and accounting validation for r2; never a completeness certificate."""
import collections,itertools,json
from l03_reference_build import dump,sha
from l03_reconcile import OUT,R1,readlines

def run():
 checks=[]
 def check(name,ok,details=None):checks.append({'check':name,'passed':bool(ok),'details':details})
 original={x['id']:x for x in readlines(R1/'benefit-instances.jsonl.gz') if 'category_code' in x};records=list(readlines(OUT/'benefit-records.jsonl.gz'))
 check('Every source benefit instance has exactly one r2 record',{x['id'] for x in records}==set(original) and len(records)==len(original),{'records':len(records)})
 check('Every r2 component equals the exact original PBP component',all(x['source_components']==original[x['id']]['raw']['benefitDetails'] and x['pbp']==original[x['id']]['pbp'] for x in records))
 count=0;bad=0
 for a,b in itertools.zip_longest(readlines(R1/'table-fields.jsonl.gz'),readlines(OUT/'all-source-field-accounting.jsonl.gz')):
  count+=1
  if a is None or b is None or any(b.get(k)!=v for k,v in a.items()):bad+=1
 check('All table source fields, blanks, raw values and normalization states preserved exactly',bad==0,{'instances':count,'differences':bad})
 pages={}
 for x in readlines(R1/'carrier-pages.jsonl.gz'):pages[(x['document_sha256'],x['pdf_page'])]=x
 fragments=0;bad=0
 for r in readlines(OUT/'carrier-chart-rows.jsonl.gz'):
  for f in r['fragments']:
   fragments+=1;p=pages[(r['document_sha256'],f['pdf_page'])]
   if p['text_sha256']!=f['page_text_sha256'] or p['text'].splitlines()[f['line']-1]!=f['text']:bad+=1
 check('Every EOC row fragment equals its exact page, line and hash',bad==0,{'fragments':fragments,'differences':bad})
 cases=json.loads((OUT/'source-led-comparison-ledger.json').read_text());diff=[x for x in cases if not x['equal']]
 check('All 47 documented offerings have source-led cases',len({x['offering_id'] for x in cases})==47,{'cases':len(cases),'numeric_agreements':len(cases)-len(diff),'basis_differences':len(diff)})
 check('Both known base-versus-protected differences remain held',len(diff)==2 and all(x['status']=='basis_difference_held_for_review' and not x['accepted'] for x in diff))
 plans=json.loads((OUT/'offering-reconciliation.json').read_text());check('All 72 offerings retained and all 25 original restrictions remain',len(plans)==72 and sum(x['original_document_status']=='restricted' for x in plans)==25)
 check('Source and comparison records do not unlock consumer use',all(not x['consumer_usable'] and not x['accepted'] for x in records))
 preserve=json.loads((OUT/'preservation-check.json').read_text());check('r1 and 649 protected L01/L02/UI files unchanged',preserve['r1_manifest_pin_unchanged'] and not preserve['r1_changed_files'] and not preserve['protected_changed_files'],preserve)
 s={'technical_checks':len(checks),'technical_checks_passed':sum(x['passed'] for x in checks),'checks':checks,'full_benefit_and_condition_semantics_validated':False,'final_acceptance':False,'note':'Integrity, complete pass accounting and listed source-led cases only; source-family association and amount occurrences are not proof of full semantic correctness.'}
 dump(OUT/'validation-report.json',s);print(json.dumps(s,indent=2));return s
if __name__=='__main__':run()
