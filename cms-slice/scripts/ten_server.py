#!/usr/bin/env python3
"""D66 local ten-question entry point. No data migration; original guide stays at --legacy."""
import argparse
from pathlib import Path
from guide_server import make_server
from runtime_env import load_model_env
ROOT=Path(__file__).resolve().parents[1]
def build(port=8890,*,fixture=False,legacy=False,database=None):
 if fixture and legacy:raise ValueError('Choose one surface.')
 original=ROOT/'var/guest-profiles/guides.sqlite3';current=ROOT/'var/ten-question-profiles/guides.sqlite3'
 if database is not None and not fixture:raise ValueError('Custom databases are restricted to synthetic fixtures.')
 if fixture and database and Path(database).resolve() in {original.resolve(),current.resolve()}:raise ValueError('Fixtures cannot use real guide storage.')
 if not fixture:load_model_env(ROOT.parent/'.env')
 web=ROOT/'apps/chat' if legacy else ROOT/'apps/ten-question'
 from l01_http import attach
 return attach(make_server(port,web=web,database=database or (ROOT/'var/ten-question-fixtures/guides.sqlite3' if fixture else original if legacy else current),enable_live=not fixture,live_limit=None,cookie_namespace=None if legacy else 'daylight_ten_fixture' if fixture else 'daylight_ten_dev',budget_database=None if fixture else ROOT/'var/ai-budget/usage.sqlite3',ui_config=None if legacy else {'mockAI':fixture,'legacyUrl':'http://127.0.0.1:8896/'}))
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--port',type=int,default=8890);p.add_argument('--fixture',action='store_true');p.add_argument('--legacy',action='store_true');p.add_argument('--database',type=Path);a=p.parse_args();server=build(a.port,fixture=a.fixture,legacy=a.legacy,database=a.database)
 print(f'Daylight {"synthetic fixture" if a.fixture else "previous guide" if a.legacy else "ten-question guide"} at http://127.0.0.1:{server.server_port}/',flush=True)
 try:server.serve_forever()
 except KeyboardInterrupt:pass
 finally:server.server_close()
if __name__=='__main__':main()
