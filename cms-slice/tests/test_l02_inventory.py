"""L02: real full-population evidence plus labeled synthetic boundary cases."""
import copy
import csv
from datetime import datetime,timezone
import io
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.request import urlopen,Request
from urllib.error import HTTPError
import zipfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import cms_slice as cms
import l02_inventory as inv
import l02_service as service
import l02_refresh as refresh
import l02_evidence as evidence

PACKAGE=inv.SPEC
BUILD=Path(os.environ.get('L02_BUILD',str(PACKAGE/'build-r5')))

def example(year='2026'):
 schema=cms.load_json(PACKAGE/'schemas.json')['years'][year]
 row={c:'Not Applicable' for c in schema['columns']}
 row.update({'Contract Year':year,'Contract ID':'H9999','Plan ID':'001','Segment ID':'0','ContractPlanID':'H9999_001','ContractPlanSegmentID':'H9999_001_0','Contract Plan ID':'H9999_001','Contract Plan Segment ID':'H9999_001_0','Contract Category Type':'MA-PD','State Territory Abbreviation':'FL','County Name':'Collier','Plan Type':'HMO','Sanctioned Plan':'No','Special Needs Plan (SNP) Indicator':'No','SNP Type':'Not Applicable','Part D Coverage Indicator':'Yes','Plan Name':'Synthetic duplicate name','Contract Name':'Synthetic legal','Parent Organization Name':'Synthetic parent','Organization Marketing Name':'Synthetic brand'})
 return {k:row[k] for k in schema['columns']}

def fixture(root,rows,pbp=None,area=None):
 root=Path(root);root.mkdir();(root/'raw').mkdir();sources={}
 schema=cms.load_json(PACKAGE/'schemas.json')['years']['2026']
 f=io.StringIO();w=csv.DictWriter(f,fieldnames=schema['columns']);w.writeheader();w.writerows(rows)
 def archive(name,files):
  b=io.BytesIO()
  with zipfile.ZipFile(b,'w') as z:
   for n,v in files.items():z.writestr(n,v)
  raw=b.getvalue();sha=cms.sha256(raw);(root/'raw'/sha).write_bytes(raw);sources[name]={'id':name,'sha256':sha,'bytes':len(raw),'benefit_year':'2026','source_period':'SYNTHETIC'}
 archive('landscape',{'2026.csv':f.getvalue(),'README.txt':'SYNTHETIC fixture; never consumer evidence'})
 if pbp is not None:archive('pbp',pbp)
 if area is not None:
  f=io.StringIO();w=csv.DictWriter(f,fieldnames=inv.AREA_COLUMNS);w.writeheader();w.writerows(area);archive('contract-area',{'areas.csv':f.getvalue(),'readme.txt':'SYNTHETIC'})
 cms.write_json(root/'source-manifest.json',{'sources':sources,'kind':'synthetic'})
 return root

class IdentityAndPolicy(unittest.TestCase):
 def setUp(self):self.schema=cms.load_json(PACKAGE/'schemas.json')['years']['2026'];self.row=example()
 def test_identity_segment_leading_zero(self):
  self.assertEqual(inv.landscape_row(self.row,'2026',self.schema)[0],'2026:H9999:001:000')
  self.row['Segment ID']='2';self.row['ContractPlanSegmentID']='H9999_001_2'
  self.assertEqual(inv.landscape_row(self.row,'2026',self.schema)[0],'2026:H9999:001:002')
 def test_missing_segment_and_short_plan_rejected(self):
  for field,value in [('Segment ID',''),('Plan ID','1'),('ContractPlanID','H9999_002')]:
   r={**self.row,field:value}
   with self.assertRaises(cms.SourceError):inv.landscape_row(r,'2026',self.schema)
 def test_wrong_year_inside_renamed_file(self):
  self.row['Contract Year']='2027'
  with self.assertRaises(cms.SourceError):inv.landscape_row(self.row,'2026',self.schema)
 def test_unknown_codes_not_silently_omitted(self):
  for f in ['Contract Category Type','Plan Type','SNP Type','Sanctioned Plan']:
   with self.assertRaises(cms.SourceError):inv.landscape_row({**self.row,f:'FUTURE_CODE'},'2026',self.schema)
 def test_commercial_canaries_rejected(self):
  for field in ['commission_cents','appointment_status','partner_referral','conversion_score','LTV_revenue','payout']:
   with self.assertRaises(cms.SourceError):inv.landscape_row({**self.row,field:'CANARY'},'2026',self.schema)
 def test_source_schema_change_fails(self):
  with self.assertRaises(cms.SourceError):list(inv.rows_csv(b'wrong,header\n1,2\n',self.schema['columns']))
 def test_msa_snp_and_missing_are_retained(self):
  r={**self.row,'Contract Category Type':'SNP','Special Needs Plan (SNP) Indicator':'Yes','SNP Type':'Dual-Eligible'}
  self.assertEqual(inv.landscape_row(r,'2026',self.schema)[1],'L02')
  self.assertEqual(inv.landscape_row({**self.row,'Plan Type':'MSA','Contract Category Type':'MA'},'2026',self.schema)[1],'L02')
  self.assertEqual(inv.landscape_row({**self.row,'Contract Category Type':'PDP','Plan Type':'PDP'},'2026',self.schema)[1],'L04')
 def test_enforcement_dates_release_and_penalty(self):
  actions=[{'id':'prior','kind':'enrollment_suspension','effective_from':'2025-12-01','notice_date':'2025-11-01'}, {'id':'penalty','kind':'monetary_penalty','effective_from':'2026-01-01'},{'id':'release','kind':'release','effective_from':'2026-05-01','releases':'prior'}]
  self.assertIn('enrollment_suspension',inv.status_at(actions,'2026-04-30'))
  self.assertNotIn('enrollment_suspension',inv.status_at(actions,'2026-05-01'))
  self.assertIn('monetary_penalty',inv.status_at(actions,'2026-05-01'))
 def test_notice_is_not_effective_date_and_unknown_not_open(self):
  a=[{'id':'x','kind':'marketing_suspension','notice_date':'2026-02-01','effective_from':'2026-04-01'}]
  self.assertEqual(inv.status_at(a,'2026-03-01'),{'enrollment_status':'unknown'})
  self.assertIn('marketing_suspension',inv.status_at(a,'2026-04-01'))
  self.assertIn('unresolved',inv.status_at([{'id':'x','kind':'termination'}],'2026-04-01'))
 def test_zip_ambiguity_is_not_county_choice(self):
  geo=cms.load_json(cms.ROOT/'apps/chat/zip-counties.json')
  self.assertEqual({r[0] for r in geo['zips']['34134']},{'12021','12071'})
  self.assertNotIn('00000',geo['zips'])
 def test_denied_origin_persists_across_capture_versions(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);config=root/'sources.json';state=root/'state.json';cms.write_json(config,[{'id':'SYNTHETIC','url':'https://www.uhc.com/synthetic'}])
   class Denied:
    calls=0
    def open(self,*args,**kwargs):self.calls+=1;raise HTTPError('https://www.uhc.com/synthetic',403,'Synthetic denial',{},None)
   opener=Denied();evidence.capture(config,root/'v1',access_state=state,opener=opener);evidence.capture(config,root/'v2',access_state=state,opener=opener)
   self.assertEqual(opener.calls,1);self.assertEqual(cms.load_json(state)['origins']['www.uhc.com']['status'],'stopped')

class SyntheticBuild(unittest.TestCase):
 def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
 def tearDown(self):self.tmp.cleanup()
 def build(self,rows,**kwargs):
  acq=fixture(self.root/'acq',rows,**kwargs);out=self.root/'build';inv.build(acq,out);return out
 def test_duplicate_quarantine_and_missing_pbp_stay_visible(self):
  r=example();out=self.build([r,r]);db=sqlite3.connect(out/'inventory.sqlite3')
  self.assertEqual(db.execute('SELECT COUNT(*) FROM quarantine').fetchone()[0],1)
  self.assertEqual(db.execute('SELECT COUNT(*) FROM offerings').fetchone()[0],1);db.close()
  a=cms.load_json(out/'row-accounting.json')['landscape'];self.assertEqual(a,{'raw':2,'parsed':1,'quarantined':1})
  record=cms.load_json(out/'12021/offerings.json')[0];self.assertFalse(record['pbp_match']);self.assertEqual(record['personal_applicability'],'not_assessed')
 def test_contract_grain_partial_does_not_create_plan(self):
  area={c:'' for c in inv.AREA_COLUMNS};area.update({'Contract ID':'H9999','FIPS':'12071','County':'Lee','State':'FL','Partial':'*'})
  out=self.build([example()],area=[area]);self.assertEqual(cms.load_json(out/'12071/offerings.json'),[])
  self.assertEqual(len(cms.load_json(out/'12071/contract-only-observations.json')),1)
  c=sqlite3.connect(out/'inventory.sqlite3');self.assertEqual(c.execute("SELECT extent FROM areas WHERE source='contract-area'").fetchone()[0],'partial');c.close()
 def test_distinct_segments_same_name_do_not_merge(self):
  r=example();s={**r,'Segment ID':'2','ContractPlanSegmentID':'H9999_001_2'};out=self.build([r,s]);self.assertEqual(len(cms.load_json(out/'12021/offerings.json')),2)
 def test_corrupt_archive_cannot_produce_healthy_build(self):
  a=fixture(self.root/'acq',[example()]);s=cms.load_json(a/'source-manifest.json')['sources']['landscape'];(a/'raw'/s['sha256']).write_bytes(b'PKtruncated')
  with self.assertRaises(cms.SourceError):inv.build(a,self.root/'build')
  self.assertFalse((self.root/'build').exists())
 def test_pbp_only_addition_wrong_year_and_segment_are_visible(self):
  def doc(year,segment):return json.dumps({'contractYear':year,'section':'synthetic','pbp':[{'contractId':'H9999','planId':'002','segmentId':segment,'planCharacteristics':{'isSnp':'No','isOfferRx':'Yes'}}]})
  out=self.build([example()],pbp={'H9999-002-002-2026.json':doc('2026',2),'H9999-002-000-2026.json':doc('2027',0)})
  c=sqlite3.connect(out/'inventory.sqlite3');self.assertEqual(c.execute("SELECT count(*) FROM differences WHERE direction='secondary_only'").fetchone()[0],1);self.assertEqual(c.execute("SELECT count(*) FROM quarantine WHERE source='pbp'").fetchone()[0],1);c.close()
 def test_replay_diff_and_tombstones(self):
  a=fixture(self.root/'a',[example()]);one=self.root/'one';two=self.root/'two';inv.build(a,one);inv.build(a,two)
  d=refresh.compare(one,two);self.assertTrue(d['identical_outputs']);self.assertEqual(d['added'],[])
  b=fixture(self.root/'b',[]);three=self.root/'three';inv.build(b,three);delta=refresh.compare(one,three);self.assertEqual(len(delta['removed_tombstones']),1);self.assertFalse(delta['consumer_promotion'])
  pointer=self.root/'selection.json';refresh.select(one,pointer);refresh.select(three,pointer);refresh.select(one,pointer);self.assertEqual(cms.load_json(pointer)['build'],str(one.resolve()))
 def test_exact_receipt_scope_expiry_code_and_unknown_inputs(self):
  out=self.build([example()]);receipts=self.root/'acceptance.json';i=service.Inventory(out,receipts)
  with self.assertRaises(service.Held):i.query(year='2027',county='12021')
  with self.assertRaises(service.Held):i.query(year='2026',county='99999')
  with self.assertRaises(service.Held):i.query(year='2026',county='12021',capability='recommendation')
  with self.assertRaises(service.Held):i.query(year='2026',county='12021',capability='published_inventory')
  r={'id':'SYNTHETIC-ONLY','decision':'accepted','benefit_year':'2026','county_fips':'12021','population':i.policy['population'],'capability':'published_inventory','build_manifest_sha256':i.build_hash,'source_manifest_sha256':i.manifest['source_manifest_sha256'],'claim_version':inv.CLAIM,'service_code_sha256':cms.file_hash(service.__file__),'reviewer':'Synthetic Reviewer','reviewer_role':'independent_medicare_reviewer','independent_of_sales':True,'review_evidence':'SYNTHETIC','accepted_claims':['published_inventory'],'expected_offering_count':1,'gates':{f'G{x:02d}':'accepted' for x in range(1,6)},'accepted_at_utc':'2026-10-25T00:00:00+00:00','expires_at_utc':'2026-10-26T00:00:00+00:00','coverage_dates':['2026-10-25']}
  cms.write_json(receipts,{'receipts':[r]});now=datetime(2026,10,25,tzinfo=timezone.utc)
  result=i.query(year='2026',county='12021',capability='published_inventory',coverage_date='2026-10-25',now=now);self.assertFalse(result['personal_recommendations_accepted'])
  self.assertFalse(result['claims']['verified_address_availability']);self.assertFalse(result['claims']['open_to_enroll'])
  for field,value in [('county_fips','12071'),('claim_version','changed'),('service_code_sha256','changed'),('expires_at_utc','2026-10-24T00:00:00+00:00'),('build_manifest_sha256','changed'),('reviewer_role','sales_agent')]:
   cms.write_json(receipts,{'receipts':[{**r,field:value}]})
   with self.assertRaises(service.Held):i.query(year='2026',county='12021',capability='published_inventory',coverage_date='2026-10-25',now=now)
  for malformed in [[],{'receipts':'bad'},{'receipts':[None,'truthy',{}]}]:
   cms.write_json(receipts,malformed)
   with self.assertRaises(service.Held):i.query(year='2026',county='12021',capability='published_inventory',coverage_date='2026-10-25',now=now)
 def test_schema_and_shared_helper_changes_hold_build(self):
  out=self.build([example()]);real_hash=cms.file_hash
  for changed in [inv.SPEC/'schemas.json',Path(cms.__file__)]:
   def altered(path):return 'CHANGED' if Path(path).resolve()==changed.resolve() else real_hash(path)
   with patch.object(cms,'file_hash',side_effect=altered):
    with self.assertRaises(service.Held):service.verify_build(out)
 def test_response_tamper_after_start_is_held(self):
  out=self.build([example()]);i=service.Inventory(out);(out/'12021/offerings.json').write_text('[]')
  with self.assertRaises(service.Held):i.query(year='2026',county='12021')

@unittest.skipUnless((BUILD/'build-manifest.json').exists(),'Set L02_BUILD to a real immutable build')
class FullPopulation(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.db=sqlite3.connect(BUILD/'inventory.sqlite3');cls.db.row_factory=sqlite3.Row
 @classmethod
 def tearDownClass(cls):cls.db.close()
 def test_every_source_row_accounted(self):
  for source,a in cms.load_json(BUILD/'row-accounting.json').items():self.assertEqual(a['raw'],a['parsed']+a['quarantined'],source)
  self.assertEqual(self.db.execute('SELECT count(*) FROM ledger').fetchone()[0],138260)
 def test_independent_raw_population_and_parent_key_set(self):
  m=cms.load_json(PACKAGE/'acquisition-r1/source-manifest.json')['sources']['landscape'];p=PACKAGE/'acquisition-r1/raw'/m['sha256']
  with zipfile.ZipFile(p) as z:
   r=csv.DictReader(io.StringIO(z.read(next(n for n in z.namelist() if n.endswith('.csv'))).decode('utf-8-sig')));raw=list(r)
  keys={':'.join([r['Contract Year'],r['Contract ID'],r['Plan ID'],r['Segment ID'].zfill(3)]) for r in raw if r['State Territory Abbreviation']=='FL' and r['County Name']=='Collier'}
  normalized={r['id'] for r in cms.load_json(BUILD/'12021/offerings.json')};self.assertEqual(keys,normalized);self.assertEqual(len(raw),138260);self.assertEqual(len(keys),72)
 def test_all_carriers_snp_regional_and_missing_neutrality(self):
  rows=cms.load_json(BUILD/'12021/offerings.json');self.assertEqual(len({r['parent'] for r in rows}),7);self.assertEqual(sum(r['snp']=='Yes' for r in rows),29);self.assertEqual(sum(r['pbp_match'] for r in rows),72)
  self.assertTrue(any('Regional' in r['plan_type'] for r in rows));self.assertTrue(all(r['personal_applicability']=='not_assessed' for r in rows))
 def test_denominator_and_consumer_gates_held_all_scopes(self):
  for county in ['12021','12071','36061']:
   r=cms.load_json(BUILD/county/'completeness-report.json');self.assertIsNone(r['denominator']['expected_offering_count']);self.assertFalse(r['conclusion']['comprehensive_inventory']);self.assertFalse(r['conclusion']['consumer_inventory_accepted']);self.assertGreater(r['identity_accounting']['distinct_offerings'],0)
   self.assertEqual({g['id'] for g in cms.load_json(BUILD/county/'gap-register.json')} & {f'L02-G{i:02d}' for i in range(1,13)},{f'L02-G{i:02d}' for i in range(1,13)})
 def test_national_quarantines_and_partial_grain(self):
  self.assertEqual(self.db.execute("SELECT count(*) FROM quarantine WHERE source='snp'").fetchone()[0],3)
  self.assertEqual(self.db.execute("SELECT count(*) FROM areas WHERE source='contract-area' AND extent='partial'").fetchone()[0],58)
  self.assertEqual(self.db.execute("SELECT count(*) FROM areas WHERE source='contract-area' AND offering_id IS NOT NULL").fetchone()[0],0)
 def test_real_http_research_and_fail_closed_consumer(self):
  server=service.make_server(BUILD,0);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
  try:
   base=f'http://127.0.0.1:{server.server_port}/inventory'
   with urlopen(base+'?year=2026&county=12021') as response:self.assertEqual(json.load(response)['count'],72)
   for query in ['?year=2027&county=12021','?year=2026&county=12021&capability=published_inventory','?year=2026&county=12021&commission=100','?year=2026&county=12021&county=12071']:
    with self.assertRaises(HTTPError) as error:urlopen(base+query)
    self.assertEqual(error.exception.code,503)
  finally:server.shutdown();server.server_close();thread.join()

if __name__=='__main__':unittest.main()
