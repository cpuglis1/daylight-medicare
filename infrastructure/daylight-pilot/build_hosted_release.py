#!/usr/bin/env python3
"""Build a verified delta from the installed immutable display release."""
import hashlib
import json
from pathlib import Path
import tarfile
import zipfile
from package_display_rehearsal import selected_files, ROOT

BASE='aaa19850dd02ccd61b25f633e170bc8f01d0321cbe26e5b1715874e2cfe3ec42'

def main():
    directory=Path(__file__).parent
    base=directory/'daylight-rehearsal-20261118.tar.gz'
    assert hashlib.sha256(base.read_bytes()).hexdigest()==BASE
    with tarfile.open(base) as archive:
        before=json.load(archive.extractfile('release-manifest.json'))['files_sha256']
    snapshot=ROOT/'infrastructure/daylight-data/.state/pilot-subset/2026-11-12-r1'
    selected=selected_files(snapshot)
    for name in ('install_hosted_runtime.py','hosted_operations.py','install_hosted_proxy.py','hosted_egress_guard.py'):
        selected['deployment/'+name]=directory/name
    # Freeze each input once: a concurrent workspace edit must never produce a
    # manifest for different bytes than the ones actually shipped.
    if any(path.is_symlink() for path in selected.values()):
        raise ValueError('Release inputs must be regular files')
    contents={name:path.read_bytes() for name,path in selected.items()}
    hashes={name:hashlib.sha256(data).hexdigest() for name,data in contents.items()}
    manifest={'scope':'fictional_invited_hosted_demo','base_release':BASE,'files_sha256':hashes}
    raw=json.dumps(manifest,sort_keys=True,separators=(',',':')).encode()
    release=hashlib.sha256(raw).hexdigest()
    output=directory/f'hosted-release-{release[:12]}.zip'
    if output.exists():
        with zipfile.ZipFile(output) as archive:
            expected={'release-manifest.json':raw,**{name:data for name,data in contents.items() if before.get(name)!=hashes[name]}}
            if len(archive.namelist())!=len(expected) or set(archive.namelist())!=set(expected):
                raise ValueError('Existing release archive inventory differs')
            if any(archive.read(name)!=data for name,data in expected.items()):
                raise ValueError('Existing release archive differs')
    else:
        with zipfile.ZipFile(output,'x',compression=zipfile.ZIP_DEFLATED) as archive:
            for name,data in sorted({'release-manifest.json':raw,**{name:data for name,data in contents.items() if before.get(name)!=hashes[name]}}.items()):
                entry=zipfile.ZipInfo(name,date_time=(1980,1,1,0,0,0))
                entry.compress_type=zipfile.ZIP_DEFLATED
                entry.external_attr=0o100600<<16
                archive.writestr(entry,data)
    report={'file':output.name,'sha256':hashlib.sha256(output.read_bytes()).hexdigest(),
        'bytes':output.stat().st_size,'release':release,'base_release':BASE,
        'files':len(hashes),'changed_files':sum(before.get(n)!=h for n,h in hashes.items())}
    (directory/'hosted-release-candidate.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report))

if __name__=='__main__':main()
