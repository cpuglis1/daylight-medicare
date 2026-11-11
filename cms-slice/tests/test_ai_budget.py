"""Synthetic budget boundary, concurrency, restart and failure safety; zero paid calls."""
import copy
from datetime import datetime,timezone
import json
from pathlib import Path
import sys,tempfile,threading,unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from ai_budget import DailyBudget,BudgetError,CAP,count_input_tokens
from guide_agent import GuideAgent
from guide_server import make_server
from test_guest_guide import CONTRACT,FACTS,guide,client,reply,WEB

NOW=datetime(2026,10,21,20,tzinfo=timezone.utc).timestamp()
def complete(i=1000,o=100,c=0,**changes):
 return {'status':'completed','model':'gpt-5.4-2026-03-05','service_tier':'default','usage':{'input_tokens':i,'output_tokens':o,'total_tokens':i+o,'input_tokens_details':{'cached_tokens':c}},**changes}
class BudgetTests(unittest.TestCase):
 def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'budget/usage.db';self.now=[NOW];self.b=DailyBudget(self.path,clock=lambda:self.now[0])
 def tearDown(self):self.tmp.cleanup()
 def test_exact_boundary_never_accepts_one_more(self):
  for _ in range(29):self.b.reserve(8000,900,'gpt-5.4')
  self.assertLessEqual(self.b.summary()['accountedUsd'],1)
  with self.assertRaises(BudgetError):self.b.reserve(8000,900,'gpt-5.4')
 def test_reservation_survives_restart_without_refund(self):
  self.b.reserve(8000,900,'gpt-5.4');other=DailyBudget(self.path,clock=lambda:NOW);self.assertEqual(other.summary()['reservedOrUncertainUsd'],.0335)
 def test_different_instances_concurrently_share_one_cap(self):
  results=[]
  def run():
   other=DailyBudget(self.path,clock=lambda:NOW)
   try:other.reserve(8000,900,'gpt-5.4');results.append('yes')
   except BudgetError:results.append('no')
  ts=[threading.Thread(target=run) for _ in range(40)]
  for t in ts:t.start()
  for t in ts:t.join()
  self.assertEqual(results.count('yes'),29);self.assertEqual(results.count('no'),11);self.assertLessEqual(self.b.summary()['accountedUsd'],1)
 def test_measured_usage_settles_at_verified_prices_once(self):
  key=self.b.reserve(1000,900,'gpt-5.4');self.b.settle(key,complete(c=100));self.b.settle(key,complete(c=100));v=self.b.summary();self.assertEqual(v['estimatedUsd'],.003775);self.assertEqual(v['reservedOrUncertainUsd'],0)
 def test_uncertain_failure_keeps_maximum_and_can_only_spend_remaining(self):
  key=self.b.reserve(1000,900,'gpt-5.4');self.b.uncertain(key);self.assertEqual(self.b.summary()['reservedOrUncertainUsd'],.016);self.assertTrue(DailyBudget(self.path,clock=lambda:NOW).summary()['canRequest'])
 def test_missing_usage_or_wrong_tier_model_is_fail_closed(self):
  for index,response in enumerate([{},complete(service_tier='priority'),complete(model='another')]):
   b=DailyBudget(self.path.parent/('case'+str(index)+'.db'),clock=lambda:NOW);key=b.reserve(1000,900,'gpt-5.4')
   with self.assertRaises(BudgetError):b.settle(key,response)
   self.assertFalse(b.summary()['canRequest'])
 def test_unknown_cache_write_price_holds_and_blocks(self):
  k=self.b.reserve(1000,900,'gpt-5.4');r=complete();r['usage']['input_tokens_details']['cache_write_tokens']=20
  with self.assertRaises(BudgetError):self.b.settle(k,r)
  self.assertEqual(self.b.summary()['reservedOrUncertainUsd'],.016)
 def test_oversized_or_inconsistent_usage_cannot_release(self):
  k=self.b.reserve(1000,900,'gpt-5.4')
  with self.assertRaises(BudgetError):self.b.settle(k,complete(i=1001))
  self.assertEqual(self.b.summary()['reservedOrUncertainUsd'],.016)
 def test_unknown_model_expired_or_changed_prices_reject_preflight(self):
  with self.assertRaises(BudgetError):self.b.reserve(1000,900,'gpt-unknown')
  self.now[0]+=8*86400
  with self.assertRaises(BudgetError):self.b.reserve(1000,900,'gpt-5.4')
  self.now[0]=NOW;self.b.rates['input_nano_usd_per_token']=1
  with self.assertRaises(BudgetError):self.b.reserve(1000,900,'gpt-5.4')
 def test_only_reviewed_input_and_output_bounds_are_allowed(self):
  for i,o in [(8001,900),(0,900),(1000,901),(1000,899),(True,900)]:
   with self.assertRaises(BudgetError):self.b.reserve(i,o,'gpt-5.4')
 def test_new_day_resets_completed_usage_but_carries_uncertain(self):
  k=self.b.reserve(1000,900,'gpt-5.4');self.b.settle(k,complete());self.b.reserve(1000,900,'gpt-5.4');self.now[0]+=86400;v=self.b.summary();self.assertEqual(v['estimatedUsd'],0);self.assertEqual(v['reservedOrUncertainUsd'],.016);self.assertTrue(v['resetAt'].startswith('2026-10-23'))
 def test_completion_over_midnight_counts_on_both_days(self):
  k=self.b.reserve(1000,900,'gpt-5.4');self.now[0]+=86400;self.b.settle(k,complete());self.assertEqual(self.b.summary()['estimatedUsd'],.004)
 def test_clock_backwards_cannot_make_new_allowance(self):
  self.b.summary();self.now[0]-=86400;self.assertFalse(self.b.summary()['canRequest'])
  with self.assertRaises(BudgetError):self.b.reserve(1000,900,'gpt-5.4')
 def test_historic_smoke_seed_is_idempotent_and_private(self):
  seed=[('smoke','2026-10-21',7783,0,258)];self.b.seed(seed);self.b.seed(seed);self.assertEqual(self.b.summary()['estimatedUsd'],.0233275);self.assertEqual(self.b.summary()['requestCount'],1);self.assertEqual(self.path.stat().st_mode&0o777,0o600)
 def test_invalid_cap_config_is_rejected(self):
  p=Path(self.tmp.name)/'pricing.json';v=self.b.rates.copy();v['daily_cap_nano_usd']=2*CAP;p.write_text(json.dumps(v))
  with self.assertRaises(BudgetError):DailyBudget(self.path,pricing_path=p)
 def test_count_endpoint_uses_complete_cost_affecting_inputs_once(self):
  class Response:
   def __enter__(self):return self
   def __exit__(self,*args):pass
   def read(self,*args):return b'{"object":"response.input_tokens","input_tokens":1234}'
  payload={k:k for k in ['model','instructions','input','tools','text']};payload['max_output_tokens']=900
  with patch('ai_budget.urlopen',return_value=Response()) as call:
   self.assertEqual(count_input_tokens(client(),payload),1234);self.assertEqual(call.call_count,1);self.assertEqual(json.loads(call.call_args.args[0].data),{k:k for k in ['model','instructions','input','tools','text']})
 def test_count_failure_makes_no_generation_and_no_reservation(self):
  seen=[];c=client(seen=seen)
  def fail(*args):raise BudgetError('count unavailable')
  a=GuideAgent(CONTRACT,FACTS,c,True,max_calls=None,budget=self.b,count_tokens=fail)
  with self.assertRaises(BudgetError):a.run('guest','understand Medicare',guide(),['L00'],'request-00001')
  self.assertFalse(seen);self.assertEqual(self.b.summary()['requestCount'],0)
 def test_failure_has_no_automatic_retry_and_keeps_reservation(self):
  c=client();calls=[]
  def fail(payload):calls.append(1);raise TimeoutError('synthetic timeout')
  c.transport=fail;a=GuideAgent(CONTRACT,FACTS,c,True,max_calls=None,budget=self.b,count_tokens=lambda *_:1000)
  with self.assertRaises(Exception):a.run('guest','understand Medicare',guide(),['L00'],'request-00001')
  self.assertEqual(len(calls),1);self.assertEqual(self.b.summary()['reservedOrUncertainUsd'],.016)
 def test_exhausted_shared_cap_blocks_second_guest_before_generation(self):
  self.b.seed([('used','2026-10-21',400000,0,0)]);seen=[];a=GuideAgent(CONTRACT,FACTS,client(seen=seen),True,max_calls=None,budget=self.b,count_tokens=lambda *_:1000)
  for guest in ['one','two']:
   with self.assertRaises(BudgetError):a.run(guest,'understand Medicare',guide(),['L00'],'request-'+guest+'000')
  self.assertFalse(seen)
 def test_readonly_status_reports_shared_budget_and_held_plan_gate(self):
  server=make_server(0,database=Path(self.tmp.name)/'profile/db',client=client(),enable_live=True,live_limit=None,budget_database=self.path,count_tokens=lambda *_:1000)
  try:
   server.budget.clock=lambda:self.now[0] # Anchor this seed assertion to its fixture UTC day.
   self.assertIsNotNone(server.budget);self.assertEqual(server.budget.summary()['estimatedUsd'],.0233275);self.assertIsNone(server.agent.max_calls)
  finally:server.server_close()
if __name__=='__main__':unittest.main()
