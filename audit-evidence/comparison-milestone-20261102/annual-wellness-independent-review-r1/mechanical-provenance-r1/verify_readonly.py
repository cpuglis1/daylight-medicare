"""Independent wellness provenance/schema replay only. No DB/network/app access."""
from pathlib import Path
import collections,csv,gzip,hashlib,json,struct,sys
sys.dont_write_bytecode=True
O=Path(__file__).resolve().parent
ROOT=O.parents[3]
P=ROOT/'docs/data/l03-ma-benefits-2026-11-02-whole-offering-r12/structured-annual-wellness-comparison-r1'
R11=ROOT/'docs/data/l03-ma-benefits-2026-11-01-whole-offering-r11/source-preparation/generated-r2'
R9=ROOT/'docs/data/l03-ma-benefits-2026-10-25/semantic-inventory-r9'
N=0
def ck(x,m):
 global N
 N+=1
 if not x:raise AssertionError(m)
def j(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def canon(x):return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
def dh(x):return hashlib.sha256(canon(x)).hexdigest()
def at(x,p):
 for k in p.split('/')[1:] if p else []:x=x[int(k)] if isinstance(x,list) else x[k.replace('~1','/').replace('~0','~')]
 return x
def walk(x,p=''):
 if isinstance(x,dict):
  for k,v in x.items():yield from walk(v,p+'/'+k.replace('~','~0').replace('/','~1'))
 elif isinstance(x,list):
  for i,v in enumerate(x):yield from walk(v,p+'/'+str(i))
 else:yield p,x
ck(ROOT.name=='daylight','own repo root')
freeze=j(P/'FREEZE_R1.json');ck(sha(P/'FREEZE_R1.json')=='16679ea784200b1bafa20c61d482d5d2b8c6f6fcc3f052106973b81d4a76e05f','exact frozen wellness candidate')
for x in freeze['members']:
 f=P/x['path'];ck(sha(f)==x['sha256'] and f.stat().st_size==x['bytes'],'frozen member '+x['path'])
bindings=j(P/'INPUT_BINDINGS.json')
for x in bindings['inputs']:
 f=ROOT/x['path'];ck(sha(f)==x['sha256'] and f.stat().st_size==x['bytes'],'bound input '+x['path'])
for x in j(P/'INITIAL_CARRIER_READING_FREEZE_R1.json')['members']:
 f=P/x['path'];ck(sha(f)==x['sha256'] and f.stat().st_size==x['bytes'],'initial producer reading seal')
raw=gzip.decompress((R11/'offering-canonical.jsonl.gz').read_bytes()).splitlines(keepends=True);original=[json.loads(x) for x in raw];oid={x['id']:x for x in original};ck(len(raw)==len(oid)==4675,'r11original4675');ck(sha(R11/'offering-canonical.jsonl.gz')=='872c969620487f130b62ba77fbe760440fdcfa163176056f1e891dcb691c3080','original r11 exact gzip hash')
ck(dict(collections.Counter(x['kind'] for x in original))=={'claim':1778,'condition':2897} and sum('required_evidence_missing' in x['states'] for x in original)==16,'original kinds16missing');ck(all(x['accepted_for_reference'] is False for x in original),'originals unaccepted')
with gzip.open(P/'ORIGINAL_ID_AND_PAYLOAD_LINEAGE.jsonl.gz','rt') as f:ledger=list(map(json.loads,f))
cache={};per_id=[];native_count=0
ck(len(ledger)==len({x['id'] for x in ledger})==608,'608unique originals')
for x in ledger:
 i=x['canonical_ordinal']-1;o=original[i];ck(o==x['original_payload'] and o['id']==x['id'],'full original payload '+x['id'])
 ck(hashlib.sha256(raw[i]).hexdigest()==x['original_JSONL_line_sha256_including_line_ending'] and dh(o)==x['payload_sha256_canonical_JSON'],'exact line/full payload hashes '+x['id'])
 ck(x['whole_ID_equivalence_asserted'] is False and x['payload_state_kind_changed'] is False,'no adoption/equivalence '+x['id'])
 ck([z['record']['raw_payload']['id'] for z in x['original_observations']]==o['observation_ids'],'all observation IDs '+x['id'])
 for z in x['original_observations']+x['original_clauses']:
  path=z['file']
  if path not in cache:cache[path]=json.loads(gzip.decompress((ROOT/path).read_bytes()))['records']
  nr=cache[path][z['record_index_zero_based']];native_count+=1
  ck(nr==z['record'] and dh(nr['raw_payload'])==nr['raw_sha256'],'whole retained native row/raw hash')
  ck(json.loads(nr['raw_payload']['payload'])==z['parsed_payload'],'native payload exact parse')
 per_id.append({'id':x['id'],'r11_ordinal':i+1,'role':x['role'],'payload_sha256':dh(o),'original_line_sha256_including_line_ending':hashlib.sha256(raw[i]).hexdigest(),'full_payload_equal':True,'native_observations':len(x['original_observations']),'native_clauses':len(x['original_clauses']),'meaning_or_equivalence_verified':False})
roles=dict(collections.Counter(x['role'] for x in ledger));ck(roles=={'whole_page_or_proposition_context_only':575,'direct_wellness_or_exact_CMS_dependency':33},'33direct575context roles')
ids={x['id'] for x in ledger};scopes={x['original_payload'].get('context',{}).get('complete_source_proposition_scope') for x in ledger}-{None};ck(all(x['id'] in ids for x in original if x.get('context',{}).get('complete_source_proposition_scope') in scopes),'whole selected-proposition siblings retained')
native=j(R11/'CMS-native-member.json');nf=j(P/'NATIVE_OBJECTS_AND_FORMAT_SCOPE.json');native_objects=[];ck(len(nf['objects'])==6,'six whole native objects')
for x in nf['objects']:
 actual=at(native,x['pointer']);ck(actual==x['raw'] and type(actual)==type(x['raw']) and dh(actual)==x['raw_sha256_canonical_JSON'],'native whole object '+x['pointer']);native_objects.append({'pointer':x['pointer'],'whole_object_sha256':dh(actual),'whole_value_and_type_equal':True})
group=at(native,'/pbp/0/costShareGroups/pointOfServiceGroups/pointOfServiceGroupsDetails/posGroupsData/1');uid=group['groupId'];refs=[{'pointer':p,'raw':v} for p,v in walk(native) if v==uid];ck(refs==nf['UUID_reference_joins'] and len(refs)==3,'UUID all three exact references')
ck(at(native,'/pbp/0/benefitDetails/benefitDetailsInfo/59')['categoryCode']=='14a' and at(native,'/pbp/0/benefitDetails/benefitDetailsInfo/71')['categoryCode']=='15-3','distinct native reference categories')
ck(group['coinsuranceFG']=={'bdCoinsuranceAmountYesNoMinMax':'3','bdCoinsuranceAmount':'','bdCoinsuranceMinAmount':'0','bdCoinsuranceMaxAmount':'40'},'selector/blank/0/40 raw strings remain distinct')
for x in nf['retained_official_format_decisions']:ck(j(ROOT/x['original_file'])['records'][x['ordinal']-1]==x['record'],'whole retained format record')
ck(nf['wellness_specific_rate_from_operands_asserted'] is False and nf['native_PA_or_referral_No_from_absence_asserted'] is False,'no native decoder/alias authority transfer')
source=j(P/'SOURCE_EVIDENCE.json');parents={x['id']:x for x in source['parents']};ck(len(parents)==36,'36source parents');parent_receipts=[]
for x in parents.values():
 rb=x['render_binding'];f=ROOT/rb['path'];ck(sha(f)==rb['sha256'] and list(struct.unpack('>II',f.read_bytes()[16:24]))==rb['pixels']==[1750,2250] and rb['render_dpi']==200,'render bytes/dimensions '+x['id'])
 loc=x['locator'];f=ROOT/loc['ocr_tsv']['path'];ck(sha(f)==loc['ocr_tsv']['sha256'] and f.stat().st_size==loc['ocr_tsv']['bytes'],'OCR locator input '+x['id']);selected=[]
 with f.open() as stream:
  for n,w in enumerate(csv.DictReader(stream,delimiter='\t'),2):
   if w['level']!='5' or not w['text'].strip():continue
   l,t,ww,hh=[int(w[k]) for k in ['left','top','width','height']]
   if any(a<=l+ww/2<=c and b<=t+hh/2<=d for a,b,c,d in loc['bounded_regions_xyxy']):selected.append({'tsv_line':n,'text':w['text'],'bbox_xywh':[l,t,ww,hh]})
 ck(selected==loc['selected_words'] and bool(selected),'exact bounded words '+x['id']);quote=' '.join(z['text'] for z in selected);ck(quote==x['OCR_locator_quote'] and hashlib.sha256(quote.encode()).hexdigest()==x['OCR_locator_quote_sha256'],'locator hash '+x['id'])
 ck(hashlib.sha256(x['authored_pixel_reading'].encode()).hexdigest()==x['authored_pixel_reading_sha256'],'authored meaning string hash only '+x['id']);ck(set(x['original_ids'])<=ids and x['source_interpretation_accepted'] is False,'bounded source/original roles '+x['id'])
 parent_receipts.append({'id':x['id'],'record_sha256':dh(x),'source_sha256':x['source_sha256'],'physical_page':x['physical_page'],'original_IDs':x['original_ids'],'locators_and_hashes_equal':True,'pixel_meaning_approved':False})
leaves=j(P/'EXISTING_UNADOPTED_WELLNESS_LEAF_BINDINGS.json')['records']
with gzip.open(P.parent/'clinical-meaning-refinement-r2/material-leaves-corrected.jsonl.gz','rt') as f:old_leaves={x['id']:x for x in map(json.loads,f)}
ck(len(leaves)==len({x['id'] for x in leaves})==13,'13unadoptedexistingchildren')
for x in leaves:ck(x==old_leaves[x['id']] and x['canonical_adoption'] is False and x['accepted_for_reference'] is False,'exact prior leaf/no adoption '+x['id'])
sys.path[:0]=[str(ROOT/'docs/data/l03-ma-benefits-2026-10-25/inventory-r8/code'),str(R9/'code')]
import jsonschema
from l03_r9_comparison import compare
from l03_comparison_contract import CONDITION_FAMILIES,observation_ready
schema=j(R9/'comparison-record.schema.json');records=j(P/'COMPARISON_RECORDS_R1.json');record_receipts=[];ck(len(records)==2,'two comparison records')
material={x['id'] for x in leaves}
for x in records:
 jsonschema.Draft202012Validator(schema).validate(x);ck(True,'exact sealed schema '+x['id']);ck(set(x['inventory_root_ids'])==ids and len(x['inventory_root_ids'])==608,'exact608record root membership');ck(x['accepted_for_reference'] is False and x['interpretation_review_receipt'] is None,'no acceptance/interpretation receipt')
 for side in ['cms','carrier']:
  v=x[side];ck(set(v['conditions'])==set(CONDITION_FAMILIES),'ten condition families');ck(observation_ready(v,side) is False,'partial observation remains unready')
  for c in v['conditions'].values():ck(set(c['obligation_ids'])<=ids|material and set(c['evidence_ids'])<=set(parents)|set(source['evidence_reference_registry']),'obligation/evidence reference closure')
  if side=='carrier':
   for e in v['evidence']:
    p=parents[e['location']['source_parent_id']];ck(e['source_sha256']==p['source_sha256'] and e['pdf_page']==p['physical_page'] and e['passage_sha256']==p['OCR_locator_quote_sha256'],'carrier evidence source and locator hash scope')
 result=compare(x['cms'],x['carrier']);ck(result['outcome']==x['outcome']=='insufficient_evidence' and result['accepted_for_reference'] is False,'r9 exact insufficient outcome')
 record_receipts.append({'id':x['id'],'record_sha256':dh(x),'sealed_schema_valid':True,'actual_r9_outcome':result['outcome'],'accepted_for_reference':False,'source_meaning_approved':False})
ck(bindings['new_canonical_obligations']==0 and bindings['original_inventory_accepted_or_mutated'] is False and source['source_interpretation_accepted'] is False,'mechanical scope only')
if (O/'FREEZE_R1.json').exists():
 for x in j(O/'FREEZE_R1.json')['members']:
  p=O/x['path'];ck(sha(p)==x['sha256'] and p.stat().st_size==x['bytes'],'own frozen receipt')
print(json.dumps({'schema':'independent-annual-wellness-mechanical-provenance/r1','status':'pass_mechanical_only','checks':N,'candidate_freeze_sha256':sha(P/'FREEZE_R1.json'),'source_meanings_reviewed':False,'root_confirmed_summary_scope_omission_unresolved_by_this_check':True,'no_semantic_acceptance_inferred':True,'original_full_payloads_checked':608,'original_line_hashes_checked':608,'roles':roles,'native_record_occurrences_checked':native_count,'native_whole_objects':native_objects,'UUID':uid,'UUID_reference_joins':refs,'source_parent_receipts':parent_receipts,'original_payload_receipts':per_id,'unchanged_unadopted_children':[{'id':x['id'],'record_sha256':dh(x)} for x in leaves],'schema_record_receipts':record_receipts,'provenance_findings':[],'database_connections':0,'app_runtime_writes':0,'frozen_authoring_scripts_executed':0,'canonical_adoptions':0,'source_acceptances':0},sort_keys=True,indent=2))
