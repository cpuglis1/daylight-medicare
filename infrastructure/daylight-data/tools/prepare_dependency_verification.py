"""Preserve both dependency revisions and materialize exact historical inputs.

The unchanged historical verifier runs against this isolated input root, with
the recovered lock at its original relative locator. No pin is waived and no
current file, package, database object, source or release is changed.
"""
from __future__ import annotations
import argparse
import ctypes
from datetime import datetime,timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tarfile

LOCK='infrastructure/daylight-data/requirements.lock'
VERIFIER='infrastructure/daylight-data/tools/verify_local_database.py'
PACKET='docs/data/infrastructure-execution-2026-10-30-local-full-db/build-r3'
SUMMARY='docs/data/infrastructure-execution-2026-10-30-local-sizing/SUMMARY.json'
ARCHIVE_RECEIPT='docs/data/infrastructure-execution-2026-10-29/implementation-archive-r4.json'
RESERVE=7*1024**3


def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda:source.read(1024**2),b''):h.update(block)
    return h.hexdigest()


def regular(root,relative):
    p=root/relative
    if Path(relative).is_absolute() or '..' in Path(relative).parts or p.is_symlink() or not p.resolve().is_relative_to(root) or not p.is_file():
        raise ValueError('A regular contained input is required: '+str(relative))
    return p


def pinned_versions(data):
    versions={}
    for line in data.decode('utf-8').splitlines():
        if not line.strip() or line.lstrip().startswith('#'):continue
        match=re.fullmatch(r'([A-Za-z0-9_.-]+)==([^\s;]+)',line)
        if not match:raise ValueError('Only exact name==version entries are supported')
        name=re.sub(r'[-_.]+','-',match[1]).lower()
        if name in versions:raise ValueError('Duplicate normalized package')
        versions[name]=match[2]
    return versions


def recover_lock(root,receipt_path,expected):
    receipt_file=regular(root,receipt_path);receipt=json.loads(receipt_file.read_text())
    bundle=regular(root,receipt['bundle_path'])
    if bundle.stat().st_size!=receipt['bytes'] or digest(bundle)!=receipt['sha256']:raise ValueError('Implementation archive differs')
    bindings=[x for x in receipt['files'] if x['path']==LOCK]
    if len(bindings)!=1 or bindings[0]['sha256']!=expected:raise ValueError('Archive does not bind the sealed lock')
    with tarfile.open(bundle,'r:gz') as archive:
        matches=[x for x in archive.getmembers() if x.name==LOCK]
        if len(matches)!=1 or not matches[0].isfile() or matches[0].size>65536:raise ValueError('Exact regular lock member required')
        with archive.extractfile(matches[0]) as source:data=source.read()
    if len(data)!=bindings[0]['bytes'] or hashlib.sha256(data).hexdigest()!=expected:raise ValueError('Recovered lock bytes differ')
    return data,{'path':receipt_path,'sha256':digest(receipt_file),'bundle':receipt['bundle_path'],'bundle_sha256':receipt['sha256']}


def clone_archive(source,destination):
    # Clone only an immutable logical archive; never live PostgreSQL files.
    library=ctypes.CDLL(None,use_errno=True);call=library.clonefile
    call.argtypes=[ctypes.c_char_p,ctypes.c_char_p,ctypes.c_int];call.restype=ctypes.c_int
    if call(os.fsencode(source),os.fsencode(destination),0):raise OSError(ctypes.get_errno(),'Archive COW clone failed; no copy/hardlink fallback')


def execution_receipt_pins(root,packet,count):
    # These results were produced after the build manifest was frozen. The
    # unchanged verifier checks their complete contents against the DB jobs.
    paths=sorted((root/packet/'units').glob('*.json'))
    if len(paths)!=count or any(not re.fullmatch(r'[a-f0-9]{64}',p.stem) for p in paths):
        raise ValueError('Exact completed execution receipt population required')
    return {str(p.relative_to(root)):digest(regular(root,str(p.relative_to(root)))) for p in paths}


def materialize(root,snapshot,pins,sealed_lock):
    if snapshot.exists():raise ValueError('Existing verification snapshot preserved')
    snapshot.mkdir(parents=True,mode=0o700)
    inventory=[]
    for relative,expected in sorted(pins.items()):
        if shutil.disk_usage(root).free<RESERVE+64*1024**2:raise RuntimeError('7 GiB reserve required')
        destination=snapshot/relative
        if relative==LOCK:
            destination.parent.mkdir(parents=True,exist_ok=True)
            with destination.open('xb') as out:out.write(sealed_lock)
            method='exact_archived_member'
        else:
            source=regular(root,relative)
            if digest(source)!=expected:raise ValueError('Unresolved pinned input drift: '+relative)
            destination.parent.mkdir(parents=True,exist_ok=True)
            if source.stat().st_size>8*1024**2:
                if not relative.endswith('.dump.gz'):raise ValueError('Large input is not a retained logical dump')
                clone_archive(source,destination);method='independent_archive_cow_clone'
            else:
                with source.open('rb') as incoming,destination.open('xb') as out:shutil.copyfileobj(incoming,out)
                method='exact_small_file_copy'
            if digest(source)!=expected:raise ValueError('Source changed during capture')
        if digest(destination)!=expected:raise ValueError('Snapshot bytes differ: '+relative)
        destination.chmod(0o444)
        inventory.append({'path':relative,'sha256':expected,'bytes':destination.stat().st_size,'method':method})
    socket=root/'infrastructure/daylight-data/.state/socket'
    (snapshot/'infrastructure/daylight-data/.state').mkdir(parents=True,exist_ok=True)
    (snapshot/'infrastructure/daylight-data/.state/socket').symlink_to(socket,target_is_directory=True)
    return inventory


def prepare(root,output,snapshot):
    root=root.resolve();output=output.resolve();snapshot=snapshot.resolve()
    if not output.is_relative_to(root) or not snapshot.is_relative_to(root):raise ValueError('Outputs must stay in the workspace')
    if output.exists() or snapshot.exists():raise ValueError('Existing reconciliation revision preserved')
    manifest_path=regular(root,PACKET+'/BUILD_MANIFEST.json');manifest=json.loads(manifest_path.read_text())
    active=regular(root,LOCK);active_bytes=active.read_bytes();active_hash=hashlib.sha256(active_bytes).hexdigest()
    sealed_hash=manifest['executable_files'][LOCK]
    sealed,archive_binding=recover_lock(root,ARCHIVE_RECEIPT,sealed_hash)
    old=pinned_versions(sealed);current=pinned_versions(active_bytes)
    added={k:v for k,v in current.items() if k not in old}
    changed={k:{'before':v,'after':current.get(k)} for k,v in old.items() if current.get(k)!=v}
    if changed:raise ValueError('Changed or removed historical versions need their own revision review')
    installed={name:importlib.metadata.version(name) for name in current}
    if installed!=current:raise ValueError('Current installed environment differs from the current lock')
    pins={}
    for mapping in ('executable_files','selected_receipt_files','recovery_receipt_files'):
        for path,value in manifest[mapping].items():
            if path in pins and pins[path]!=value:raise ValueError('Conflicting sealed input pins')
            pins[path]=value
    checkpoint=json.loads(regular(root,manifest['predecessor']['logical_checkpoint_path']).read_text())
    pins[checkpoint['path']]=checkpoint['sha256']
    for name in ('BUILD_MANIFEST.json','TARGET.json','LOAD_COMPLETE.json'):
        relative=PACKET+'/'+name;pins[relative]=digest(regular(root,relative))
    complete=json.loads(regular(root,PACKET+'/LOAD_COMPLETE.json').read_text())
    receipts=execution_receipt_pins(root,Path(PACKET),complete['unit_receipts'])
    pins.update(receipts)
    pins[VERIFIER]=digest(regular(root,VERIFIER))
    inventory=materialize(root,snapshot,pins,sealed)
    if active.read_bytes()!=active_bytes:raise ValueError('Current lock changed during reconciliation')
    output.mkdir(parents=True)
    (output/'sealed-requirements.lock').write_bytes(sealed)
    (output/'current-requirements.lock').write_bytes(active_bytes)
    for p in output.glob('*.lock'):p.chmod(0o444)
    result={'schema':'daylight-dependency-reconciliation/1','at':datetime.now(timezone.utc).isoformat(),
        'historical_packet':PACKET,'historical_manifest_sha256':digest(manifest_path),
        'historical_lock_sha256':sealed_hash,'current_lock_sha256':active_hash,
        'historical_packages':len(old),'current_packages':len(current),'added_packages':added,
        'changed_or_removed_historical_versions':changed,'installed_versions':installed,
        'current_environment_matches_current_lock':True,'archive_binding':archive_binding,
        'verification_snapshot':str(snapshot.relative_to(root)),'verifier_sha256':pins[VERIFIER],
        'snapshot_files':inventory,'socket_alias_only':'existing project-private Unix socket; same target/cluster guards',
        'completed_execution_receipts':len(receipts),'preparation_tool_sha256':digest(Path(__file__)),
        'historical_pins_waived':False,'sealed_history_modified':False,'current_lock_modified':False,
        'packages_installed_or_removed':False,'source_method_purpose_acceptance_changed':False,
        'historical_environment_recreated':False,'verification_runtime':'current environment; every historical locked version remains identical; five additions retained'}
    result['python_version']=sys.version.split()[0]
    path=output/'reconciliation.json'
    with path.open('x') as out:json.dump(result,out,indent=2);out.write('\n')
    print(json.dumps({k:result[k] for k in ('historical_lock_sha256','current_lock_sha256','historical_packages','current_packages','added_packages','current_environment_matches_current_lock','verification_snapshot')}),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repository',required=True,type=Path);p.add_argument('--output',required=True,type=Path);p.add_argument('--snapshot',required=True,type=Path)
    args=p.parse_args();prepare(args.repository,args.output,args.snapshot)
