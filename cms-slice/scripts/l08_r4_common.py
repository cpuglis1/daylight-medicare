"""Additive L08 normalization/public collection; sealed parents remain immutable."""
import hashlib,json
from pathlib import Path
import l08_acquire as acquisition

ROOT=Path(__file__).resolve().parents[2]
HOME=ROOT/'docs/data/l08-provider-networks-2026-10-27'
PARENT=HOME/'bootstrap-r3'
BASE=HOME/'normalization-r4'
BASE.mkdir(exist_ok=True)
acquisition.OUT=BASE/'acquisition'
acquisition.OUT.mkdir(exist_ok=True)
acquisition.INHERITED|={'data.cms.gov','fhir.humana.com','apif1.aetna.com','my.wellcare.com','wellcareproviderdirectories.com'}
for p in [HOME/'acquisition-r1/stopped-hosts.json',HOME/'followup-r2/acquisition/stopped-hosts.json',PARENT/'acquisition/stopped-hosts.json']:
    if p.exists():acquisition.INHERITED|=set(json.loads(p.read_text()))
def acquire(url,label=None):
    assert_open()
    acquisition.OUT=BASE/'acquisition'
    return acquisition.acquire(url,label)
write=acquisition.write
digest=acquisition.digest

def filehash(p):
    h=hashlib.sha256()
    with p.open('rb')as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()

def assert_open():
    if(BASE/'SEALED').exists():raise ValueError('Sealed revision')

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('url');p.add_argument('--label');a=p.parse_args()
    assert_open();print(json.dumps(acquire(a.url,a.label)))
