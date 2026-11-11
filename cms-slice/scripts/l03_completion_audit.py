"""Additive r5 completion audit and office-visit evidence comparisons.

No old revision is rebuilt, no acceptance is inherited, and token occurrence
does not become a verified benefit. Office summaries remain new review work.
"""
from __future__ import annotations
import collections, datetime, gzip, hashlib, json, pathlib, re
import l03_scoped_reference as approved
from l03_close_sources import CATALOG, MATRIX, R1, R2, R3, DATA, doc, pages

OUT = DATA / 'completion-r5'
# Independently transcribed from each exact SB doctor-visit section. Shared
# Freedom/Optimum/Blue tables use the named plan column, never its neighbor.
SPECIALIST = {
 'H1035:019':55,'H1035:045':45,
 'H1036:217':10,'H1036:278':35,'H1036:285':0,'H1036:290':25,
 'H1036:310':15,'H1036:311':15,'H1036:314':0,'H1036:340':0,
 'H1609:027':25,'H1609:056':[0,25],'H1609:078':0,
 'H5216:072':40,'H5216:257':50,'H5216:304':30,'H5216:393':45,
 'H5216:394':0,'H5216:452':50,'H5216:467':40,
 'H5410:047':0,'H5410:055':0,'H5410:060':30,
 'H5427:078':0,'H5427:082':25,'H5427:083':25,'H5427:087':0,
 'H5427:091':15,'H5427:105':25,
 'H5434:002':60,'H5434:042':55,'H5434:045':55,
 'H5521:033':60,'H5521:272':75,'H5521:306':50,'H5521:710':60,
 'H5594:016':0,'H5594:017':0,'H5594:034':40,'H5594:035':40,
 'H7617:108':40,'H7617:109':30,'H7617:111':45,'H7617:112':50,
 'R5826:005':45,'R5826:018':30,'R5826:074':50,
}

def read(path): return json.loads(pathlib.Path(path).read_text())
def rows(path):
 with gzip.open(path,'rt') as f:
  yield from (json.loads(line) for line in f)
def sha(path): return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()
def write(name,data):
 (OUT/name).write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n')
def money(n): return re.compile(r'\$'+str(n)+r'(?:\.00)?(?![\d.])')
def source_page(oid,kind,n):
 d=doc(oid,kind);text=pages(oid,kind)[n-1]
 return {'kind':kind,'document_sha256':d['sha256'],'url':d['url'],
         'pdf_page':n,'page_text_sha256':hashlib.sha256(text.encode()).hexdigest()}

def build():
 approved.require_review()
 if OUT.exists(): raise RuntimeError('Existing r5 audit is immutable: use a new revision.')
 OUT.mkdir()
 inputs=[R2/'benefit-records.jsonl.gz',R2/'carrier-chart-rows.jsonl.gz',
 R3/'field-dispositions.jsonl.gz',R3/'condition-interpretations.jsonl.gz',
 R3/'authorization-referral-dispositions.jsonl.gz',R3/'rider-dispositions.json',
 R2/'restricted-offering-access-reassessment.json',approved.ROOT/'manifest.json',
 approved.REGISTRY]
 field_counts=collections.defaultdict(collections.Counter)
 for x in rows(R3/'field-dispositions.jsonl.gz'):
  field_counts[x['offering_id']][x['r3_state']]+=1
 benefits=list(rows(R2/'benefit-records.jsonl.gz'))
 byplan=collections.defaultdict(list)
 for x in benefits: byplan[x['offering_id']].append(x)
 chart=list(rows(R2/'carrier-chart-rows.jsonl.gz'))
 office=[];proof={};new_actions=[]
 for oid,m in sorted(MATRIX.items()):
  if m['document_matches']['EOC']['status']!='matched_for_research': continue
  key=':'.join(oid.split(':')[1:3]);expected=SPECIALIST[key]
  sb=pages(oid,'SB');sbnums=[]
  for n,p in enumerate(sb,1):
   if re.search(r'^\s*(?:Doctor Visits|DOCTOR VISITS|Primary Care Provider \(PCP\) and specialist)',p,re.M):
    sbnums.append(n)
    if m['parent']=='Humana Inc.' and not re.search(r'^\s*Specialist\s',p,re.M):sbnums.append(n+1)
    break
  assert sbnums,(oid,'SB doctor section missing')
  crows=[x for x in chart if x['offering_id']==oid and x['section']=='physician']
  assert crows,oid
  # First physician row begins at the actual physician chart section. All
  # linked rows and pages are retained, including exceptions and continuations.
  eocnums=sorted({n for x in crows for n in x['pages']})
  sbtext='\n'.join(sb[n-1]for n in sbnums)
  eoctext='\n'.join(pages(oid)[n-1]for n in eocnums)
  for kind,nums in [('SB',sbnums),('EOC',eocnums)]:
   for n in nums:
    s=source_page(oid,kind,n);proof[f"{s['document_sha256']}:{n}"]=s
  for cat,service,value in [('7a','primary_care',0),('7d','specialist',expected)]:
   pbp=next(x for x in byplan[oid] if x['category_code']==cat)
   costs=[x for x in pbp['cost_sharing']if x['kind']in ['copayment','coinsurance']]
   vals=value if isinstance(value,list)else[value]
   assert all(money(v).search(sbtext)for v in vals),(oid,service,'SB amount not found')
   literal=all(money(v).search(eoctext)for v in vals)
   no_charge=re.search(r'no coinsurance,?\s*(?:copayment|coinsurance)',eoctext,re.I) is not None
   assert literal or no_charge,(oid,service,'EOC amount/qualified no-charge statement missing')
   exceptions=[]
   if m['parent']=='CVS Health Corporation' and 'nursing home' in eoctext.lower():
    exceptions.append('The retained EOC includes a physician-specialist nursing-home exception; preserve the exact page and scope. The general SB amount is not universal.')
   if oid in {'2026:H1035:019:000','2026:H1035:045:000'}:
    exceptions.append('The specialist PBP range includes distinct hearing/balance examination charges. Retain that specific service beside the routine office summary; never flatten the full PBP range to the SB headline.')
   if oid=='2026:H1609:056:000':
    exceptions.append('SB/EOC distinguish $0 for QMB/QMB+/SLMB+/FBDE and $25 for SLMB/QI/QDWI. No personal assistance determination.')
   if oid in {'2026:H1036:340:000','2026:H1609:078:000'}:
    exceptions.append('Use the already accepted DSNP-PUBLISHED-BASIS disposition: assistance-qualified carrier schedule remains separate from nominal CMS amounts. Numeric equality is not claimed.')
   qualifications=[
    'In-network published office-visit summary only. This is not a universal service charge or a personal price.',
    'Keep exact EOC service, setting, deductible, network, medical-necessity, referral and authorization qualifications attached.',
    'Out-of-network and telehealth schedules remain separate; do not propagate this office summary to them.',
    'Additional services performed during a visit may carry separate charges where the carrier states that rule.',
   ]+exceptions
   office.append({'id':f'{oid}:r5:{service}:INN_office_summary','offering_id':oid,
    'service':service,'network':'in_network','published_SB_USD_per_office_visit':value,
    'published_basis':'exact SB doctor-visit headline; material EOC exceptions attached',
    'PBP':pbp['pbp'],'PBP_cost_components':costs,
    'SB_evidence':[source_page(oid,'SB',n)for n in sbnums],
    'EOC_evidence':[source_page(oid,'EOC',n)for n in eocnums],
    'EOC_chart_row_ids':[x['id']for x in crows],
    'literal_amount_or_no_charge_context_present':True,
    'qualifications':qualifications,
    'comparison_state':'AI_office_summary_compared; full_PBP_range_and_exact_condition_binding_require_review',
    'carrier_corroborated_flat_benefit':False,
    'accepted_for_reference':False,'consumer_usable':False,
    'acceptance_inherited_from_r4':False})
  new_actions.append({'offering_id':oid,'task':'Complete exact service/network/setting/period verification of required source fields beyond the accepted r4 allowlist. The office summary comparisons are evidence work, not automatic release.', 'owner':'AI/data reconciliation','blocked_on_external_access':False})
 write('office-visit-comparisons.json',office)
 write('office-source-page-locators.json',list(proof.values()))
 accepted=approved.lookup({'year':2026})
 accepted_by=collections.Counter(e['offering_id']for e in accepted['entries'])
 access=read(R2/'restricted-offering-access-reassessment.json')
 blockers=[]
 for r in access:
  routes=r.get('routes')or{}
  blockers.append({'offering_id':r['offering_id'],'name':r['name'],
   'state':r['current_state'],'required_documents':[
    {'kind':k,'year':2026,'official_observed_url':routes.get(k),
     'acquired':False,'must_check':['exact contract/plan/segment','Collier applicability','revision/effective period','document hash and source-use provenance']}
    for k in ['SB','EOC']],
   'existing_evidence':r['technical_evidence'],'closure':r['next_action'],
   'owner':'source-access owner; no existing source known per explicit user reply',
   'may_retry_or_bypass_stop':False})
 write('external-document-blockers.json',blockers)
 plans=[]
 for oid,m in sorted(MATRIX.items()):
  documented=m['document_matches']['EOC']['status']=='matched_for_research'
  plans.append({'offering_id':oid,'name':m.get('name'),
   'document_state':'matched_SB_EOC'if documented else'restricted',
   'PBP_service_records_retained':len(byplan[oid]),
   'service_field_disposition_counts':dict(field_counts[oid]),
   'r4_accepted_entries':accepted_by[oid],
   'r5_office_summary_comparisons_pending':2 if documented else 0,
   'complete_benefit_field_verification':False,
   'remaining_internal_reconciliation':documented,
   'missing_document_kinds':[]if documented else['SB','EOC']})
 write('per-offering-completion-matrix.json',plans)
 write('internal-reconciliation-obligations.json',new_actions)
 total_fields=collections.Counter()
 for c in field_counts.values():total_fields.update(c)
 summary={'package_id':'L03-COMPLETION-AUDIT-COLLIER-2026-r5',
 'created_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
 'input_offerings':len(plans),'PBP_service_records_retained':len(benefits),
 'documented_offerings':sum(p['document_state']=='matched_SB_EOC'for p in plans),
 'restricted_offerings':len(blockers),'missing_required_carrier_documents':2*len(blockers),
 'new_office_summary_comparisons':len(office),'new_accepted_entries':0,
 'r4_actual_accepted_entries':len(accepted['entries']),
 'service_field_dispositions':dict(total_fields),
 'outstanding_AI_reconciliation_offerings':len(new_actions),
 'user_existing_document_source_reply':'No existing source known',
 'source_truth_resolved_by_acceptance':False,'full_L03_complete':False,
 'reason':'Both missing required carrier documents and unfinished internal exact field/condition reconciliation remain. The six accepted conservative dispositions close review choices but do not supply facts or approve additional fields.',
 'unchanged_acceptance_manifest_sha256':sha(approved.ROOT/'manifest.json'),
 'no_other_layer_UI_or_deployment_changes':True}
 write('summary.json',summary)
 protected=read(DATA/'protected-before.json')
 changed=[p for p,h in protected.items()if sha(approved.REPO/p)!=h]
 approved.require_review()
 checks={'all_72_accounted':len(plans)==72,'all_7305_service_records':len(benefits)==7305,
 'all_47_documented_have_two_office_comparisons':len(office)==94 and len(new_actions)==47,
 'all_25_restricted_have_50_document_obligations':len(blockers)==25 and all(len(x['required_documents'])==2 for x in blockers),
 'all_173124_service_fields_accounted':sum(total_fields.values())==173124,
 'no_new_release_or_inherited_acceptance':all(not x['accepted_for_reference']and not x['consumer_usable']for x in office),
 '649_protected_unchanged':len(protected)==649 and not changed,
 'accepted_r4_still_verified':approved.lookup({'year':2026})['accepted_for_reference']}
 assert all(checks.values()),checks
 write('validation.json',{'passed':True,'checks':checks,'changed_protected_files':changed,
 'limitation':'Accounting and evidence-location checks do not establish full semantic correctness or human approval of new office summaries.'})
 manifest={'package_id':summary['package_id'],'parent_accepted_r4_manifest_sha256':summary['unchanged_acceptance_manifest_sha256'],
 'input_sha256':{str(p.relative_to(approved.REPO)):sha(p)for p in inputs},
 'files_sha256':{p.name:sha(p)for p in OUT.iterdir()if p.is_file()},
 'code_sha256':{str(pathlib.Path(__file__).resolve().relative_to(approved.REPO)):sha(__file__)},
 'full_L03_complete':False,'new_fields_accepted':False}
 write('manifest.json',manifest)
 print(json.dumps(summary,indent=2))

if __name__=='__main__':build()
