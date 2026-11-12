"""Private synthetic browser fixture, never a live runtime or paid transport."""
import argparse
from pathlib import Path
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'alternatives/chat-first/cms-slice/tests'),str(ROOT/'alternatives/chat-first/cms-slice/scripts')]
from chat_server import build
from persona_scenarios import install_scripted_transport

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=8892);args=parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='daylight-ui2-personas-') as directory:
        server=build(args.port,fixture=True,database=Path(directory)/'private/personas.sqlite3')
        install_scripted_transport(server,virtual_pacing=True)
        print('Synthetic personas fixture ready on loopback port',server.server_port,flush=True)
        try:server.serve_forever()
        except KeyboardInterrupt:pass
        finally:server.server_close()
