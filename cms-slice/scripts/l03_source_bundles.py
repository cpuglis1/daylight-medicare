#!/usr/bin/env python3
"""Group normalized source fields with their controls, without inventing coverage."""
import collections,gzip,json
from l03_reference_build import DATA,dump

def build(root=DATA):
 out=root/'build-r1';dictionary=json.loads((out/'field-dictionary.json').read_text())['fields'];dd={(d['file'].lower(),d['name'].lower()):d for d in dictionary};groups={};substantive=0
 for line in gzip.open(out/'table-fields.jsonl.gz','rt'):
  x=json.loads(line)
  if x['disposition'] in ['technical_metadata','retained_other_layer_L02']:continue
  key=tuple(x['dictionary_key']);d=dd.get(key,{})
  group=(x['offering_id'],x['source']['member'],x['source']['record_ordinal'],str(d.get('service_category') or 'source_context'))
  if group not in groups:groups[group]={'offering_id':group[0],'source_table':group[1],'record_ordinal':group[2],'service_category':group[3],'fields':[],
   'source_condition_context':'All source fields in this service-category/table-row bundle retained, including activation flags, amounts, periods, limits, referrals and authorizations. Plan/global/network/SSBCI context remains in the linked source plan.',
   'context_tables':['pbp_Section_A.txt','pbp_Section_C.txt','pbp_Section_C_OON.txt','pbp_Section_C_POS.txt','pbp_Section_D.txt','pbp_b19_model_test.txt'],
   'benefit_interpretation':'normalized source fields; complete consumer benefit semantics and field-level carrier comparison pending',
   'carrier_corroboration':'pending','accepted':False}
  groups[group]['fields'].append({'source':x['source'],'dictionary_rows':d.get('dictionary_rows'),'label':d.get('field_title') or d.get('title'),
    'normalized':x['normalized'],'raw':x['raw'],'unit_basis':'official dictionary label and explicit source qualifiers; unknown where not supplied'})
  substantive+=1
 with gzip.open(out/'normalized-source-bundles.jsonl.gz','wt',encoding='utf-8') as f:
  for key,x in sorted(groups.items()):f.write(json.dumps(x,ensure_ascii=False)+'\n')
 summary={'source_bundles':len(groups),'source_field_instances':substantive,'plans':len({x[0] for x in groups}),'complete_consumer_benefit_records':0,'meaning':'Source-schema normalization with documented codes and controls, not completed benefit composition/corroboration.'}
 dump(out/'normalization-summary.json',summary);print(json.dumps(summary))
if __name__=='__main__':build()
