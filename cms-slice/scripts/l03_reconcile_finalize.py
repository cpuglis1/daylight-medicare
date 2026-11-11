"""Complete coverage accounting, condition checks and review holds for L03 r2."""
import collections,gzip,json,pathlib,re
from l03_reference_build import DATA,sha,dump
from l03_reconcile import R1,OUT,readlines,writelines,value_support,role,qualified_unit

def key(oid,source):return (oid,source['member'],source['record_ordinal'],source['field'])

def run():
 records={x['id']:x for x in readlines(OUT/'benefit-records.jsonl.gz')}
 chart={x['id']:x for x in readlines(OUT/'carrier-chart-rows.jsonl.gz')}
 bindings={x['benefit_record_id']:x for x in readlines(OUT/'benefit-chart-bindings.jsonl.gz')}
 docs={x['offering_id']:x for x in json.loads((R1/'plan-document-matrix.json').read_text())}
 # Second pass uses complete chart rows, with continuation pages and explicit
 # per-plan EOCs, to distinguish a short-window extraction miss from a true
 # still-unlocated amount. This does not approve child/network semantics.
 fields=[];unlocated=[];occurrences=collections.defaultdict(list);conditions=[]
 rowtext={k:'\n'.join(f['text'] for f in v['fragments']) for k,v in chart.items()}
 supportcache={}
 for f in readlines(OUT/'field-comparison-ledger.jsonl.gz'):
  rid=f['benefit_record_id'];b=bindings[rid];rows=b['EOC_chart_row_ids'];e=[{'text':rowtext[i]} for i in rows]
  f['complete_chart_row_ids']=rows
  if f['comparison_state']=='typed_value_not_located_in_service_passage':
   ck=(rid,str(f['normalized']['value']),f['qualified_unit'])
   if ck not in supportcache:supportcache[ck]=value_support(f['normalized']['value'],f['qualified_unit'],e)
   support=supportcache[ck]
   if support:
    f['comparison_state']='typed_value_occurs_in_complete_service_chart_binding_unresolved';f['supporting_chart_row_ids']=[rows[i] for i in support]
   else:unlocated.append(f)
  occurrences[key(f['offering_id'],f['source'])].append(rid);fields.append(f)
 writelines(OUT/'field-comparison-complete-chart-ledger.jsonl.gz',fields)
 # All source fields, including global/plan context and unmodeled extras, get
 # exactly one row here. Service-field comparisons above intentionally contain
 # shared-parent references and therefore have a different denominator.
 unique=[]
 for x in readlines(R1/'table-fields.jsonl.gz'):
  k=key(x['offering_id'],x['source']);ids=sorted(set(occurrences.get(k,[])))
  unique.append({**x,'r2_benefit_record_ids':ids,'r2_disposition':'other_layer_L02_retained' if x['disposition']=='retained_other_layer_L02' else 'technical_metadata_retained' if x['disposition']=='technical_metadata' else 'service_field_compared' if ids else 'plan_context_or_unmodeled_source_field_retained','consumer_usable':False})
 writelines(OUT/'all-source-field-accounting.jsonl.gz',unique)
 # Compare explicit CMS PA/referral selections to language in the full exact
 # EOC family row. Absence never proves No; "may" is not universal approval.
 for rid,r in records.items():
  rows=bindings[rid]['EOC_chart_row_ids'];text='\n'.join(rowtext[i] for i in rows)
  for typ,pattern in [('priorAuthorization',r'prior author|preauthor|precertif'),('priorReferral',r'referral')]:
   cms=r['conditions']['authorization_and_referral'][typ];selected=cms['selected_service'];mention=bool(re.search(pattern,text,re.I))
   state='source_restricted' if docs[r['offering_id']]['document_matches']['EOC']['status']=='restricted' else 'CMS_selection_and_carrier_may_require_language_coexist' if selected and mention else 'CMS_selection_not_located_in_exact_family_row' if selected else 'not_selected_in_CMS_no_absence_inference'
   conditions.append({'benefit_record_id':rid,'offering_id':r['offering_id'],'condition':typ,'CMS':cms,'EOC_chart_row_ids':rows,'carrier_condition_language_located':mention,'comparison_state':state,'universal_requirement_or_approval_inferred':False,'carrier_corroborated':False,'accepted':False})
 writelines(OUT/'authorization-referral-comparison.jsonl.gz',conditions)
 # Preserve the complete retained Chapter 3/4 scope alongside chart fragments.
 # This catches prerequisites, footnotes, exclusions, continuation pages and
 # carrier-only service descriptions that no PBP category parser can replace.
 allpages=collections.defaultdict(list)
 for p in readlines(R1/'carrier-pages.jsonl.gz'):allpages[p['document_sha256']].append(p)
 chapter=[];dependencies=[]
 for oid,d in docs.items():
  e=d['document_matches']['EOC']
  if 'sha256' not in e:continue
  for p in allpages[e['sha256']]:
   if re.search(r'Chapter\s+[34](?:\.|\s)',p['text']) and re.search(r'Chapter\s+[34](?:\.|\s)',p['text'][:700]):chapter.append({'offering_id':oid,**p})
   ls=p['text'].splitlines()
   for n,l in enumerate(ls):
    if re.search(r'LIS Rider|Low.Income Subsidy Rider|Evidence of Coverage Rider|errata|addendum|amendment|optional supplemental package',l,re.I):dependencies.append({'offering_id':oid,'document_sha256':p['document_sha256'],'pdf_page':p['pdf_page'],'page_text_sha256':p['text_sha256'],'line':n+1,'reference':l.strip(),'disposition':'source_dependency_reference_retained; not evidence this rider is publicly available or applicable to every member'})
 writelines(OUT/'coverage-network-exclusion-chapters.jsonl.gz',chapter);dump(OUT/'rider-and-revision-reference-register.json',dependencies)
 # Compact the outstanding amount locations by plan, service and amount;
 # retain every original field locator so each issue is concretely reviewable.
 groups={}
 for f in unlocated:
  k=(f['offering_id'],f['category_code'],f['qualified_unit'],str(f['normalized']['value']))
  g=groups.setdefault(k,{'offering_id':k[0],'category_code':k[1],'service_name':records[f['benefit_record_id']]['service_name'],'unit':k[2],'CMS_value':k[3],'source_fields':[],'EOC_chart_row_ids':bindings[f['benefit_record_id']]['EOC_chart_row_ids'],'state':'amount_not_located_with_correct_unit; no contradiction inferred from search failure','closure_evidence':'Exact service/network/setting/condition passage or source correction; retain held until resolved'})
  g['source_fields'].append({'source':f['source'],'label':f['label'],'raw':f['raw']})
 dump(OUT/'unlocated-amount-issues.json',list(groups.values()))
 summary={'all_source_field_instances_accounted':len(unique),'unique_source_field_keys':len({key(x['offering_id'],x['source']) for x in unique}),'source_field_dispositions':dict(collections.Counter(x['r2_disposition'] for x in unique)),'service_field_references':len(fields),'comparison_states':dict(collections.Counter(x['comparison_state'] for x in fields)),'remaining_unlocated_amount_field_references':len(unlocated),'remaining_unlocated_plan_service_amount_groups':len(groups),'authorization_referral_field_comparisons':len(conditions),'authorization_referral_states':dict(collections.Counter(x['comparison_state'] for x in conditions)),'complete_Chapter3_4_page_instances_retained':len(chapter),'rider_revision_references':len(dependencies),'whole_benefit_semantic_approval':False,'no_personal_eligibility_or_cost_output':True}
 dump(OUT/'full-pass-accounting-summary.json',summary);print(json.dumps(summary,indent=2));return summary
if __name__=='__main__':run()
