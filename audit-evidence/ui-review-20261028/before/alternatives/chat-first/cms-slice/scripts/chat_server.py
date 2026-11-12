#!/usr/bin/env python3
"""Isolated local chat-first alternative. Never replaces the 8890 app or its profiles."""
import argparse
from pathlib import Path
from guide_server import make_server
from chat_conversation import ChatConversation
from profile_readiness import ProfileReadiness
from adaptive_flow import AdaptiveConversation
from runtime_env import load_model_env
ROOT=Path(__file__).resolve().parents[1]
ORIGINAL=Path('/Users/cep4u/daylight')
SHARED_BUDGET=ORIGINAL/'cms-slice/var/ai-budget/usage.sqlite3'
def build(port=8891,*,fixture=False,database=None,client=None,count_tokens=None):
    if port==8890:raise ValueError('Port 8890 belongs to the preserved current app.')
    if not fixture and database is not None:raise ValueError('Custom database paths are fixture-only.')
    if not fixture:load_model_env(ORIGINAL/'.env')
    db=Path(database)if database else ROOT/('var/chat-alternative-fixtures'if fixture else 'var/chat-alternative-profiles')/'guides.sqlite3'
    if db.resolve().is_relative_to(ORIGINAL):raise ValueError('Alternative profiles cannot use original storage.')
    return make_server(port,web=ROOT/'apps/chat-alternative',database=db,enable_live=not fixture,client=client,live_limit=None,count_tokens=count_tokens,cookie_namespace='daylight_chat_alt_fixture'if fixture else 'daylight_chat_alt_dev',budget_database=None if fixture else SHARED_BUDGET,ui_config={'mockAI':fixture,'alternative':True,'currentUrl':'http://127.0.0.1:8890/'},conversation_class=ChatConversation,allow_microphone=True,profile_gate_class=ProfileReadiness,adaptive_class=AdaptiveConversation)
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--port',type=int,default=8891);p.add_argument('--fixture',action='store_true');p.add_argument('--database',type=Path);a=p.parse_args();server=build(a.port,fixture=a.fixture,database=a.database)
    print(f'Daylight chat alternative at http://127.0.0.1:{server.server_port}/',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()
if __name__=='__main__':main()
