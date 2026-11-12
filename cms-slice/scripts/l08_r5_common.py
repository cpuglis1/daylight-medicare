"""Owner-supplied Wellcare directories; additive research only, October 28, 2026."""
import hashlib,json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
HOME=ROOT/'docs/data/l08-provider-networks-2026-10-27'
PARENT=HOME/'normalization-r4'
BASE=HOME/'wellcare-r5'
BASE.mkdir(exist_ok=True)

def write(p,x):
    p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,indent=2,sort_keys=True,ensure_ascii=False)+'\n')

def digest(b):return hashlib.sha256(b).hexdigest()

def filehash(p):
    h=hashlib.sha256()
    with p.open('rb')as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()

def assert_open():
    if(BASE/'SEALED').exists():raise ValueError('Sealed revision')
