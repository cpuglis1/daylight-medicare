"""Additive L08 follow-up paths and public-source acquisition guards."""
import json
from pathlib import Path
import l08_acquire as acquisition

ROOT=Path(__file__).resolve().parents[2]
PARENT=ROOT/'docs/data/l08-provider-networks-2026-10-27'
BASE=PARENT/'followup-r2'
BASE.mkdir(exist_ok=True)
acquisition.OUT=BASE/'acquisition'
acquisition.OUT.mkdir(exist_ok=True)
acquisition.INHERITED|={'apif1.aetna.com'}|set(json.loads((PARENT/'acquisition-r1/stopped-hosts.json').read_text()))
acquire=acquisition.acquire
body=acquisition.body
write=acquisition.write
digest=acquisition.digest
