"""Additive L08 public-source bootstrap; immutable r1/r2 and source stops."""
import json
from pathlib import Path
import l08_acquire as acquisition

ROOT = Path(__file__).resolve().parents[2]
PARENT = ROOT / 'docs/data/l08-provider-networks-2026-10-27'
BASE = PARENT / 'bootstrap-r3'
BASE.mkdir(exist_ok=True)
acquisition.OUT = BASE / 'acquisition'
acquisition.OUT.mkdir(exist_ok=True)
acquisition.INHERITED |= {'apif1.aetna.com'}
for old in [PARENT/'acquisition-r1/stopped-hosts.json',
            PARENT/'followup-r2/acquisition/stopped-hosts.json']:
    if old.exists():
        acquisition.INHERITED |= set(json.loads(old.read_text()))
acquire = acquisition.acquire
body = acquisition.body
write = acquisition.write
digest = acquisition.digest

def assert_open():
    if (BASE/'SEALED').exists():
        raise ValueError('Sealed revision')

if __name__ == '__main__':
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument('url');p.add_argument('--label')
    args=p.parse_args();assert_open()
    print(json.dumps(acquire(args.url,args.label)))
