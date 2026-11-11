"""Archive exact implementation bytes for reproducing this initial local checkpoint."""
from datetime import datetime,timezone
import argparse
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import tarfile
import tempfile
import re

from daylight_data.database import connect
from daylight_data.ingestion.loader import insert_exact
from daylight_data.storage import FileArchive


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--revision',required=True)
    args=parser.parse_args()
    if not re.fullmatch(r'r[1-9][0-9]*',args.revision):
        raise ValueError('Use an explicit numbered implementation revision')
    package=Path(__file__).resolve().parents[1]
    root=package.parents[1]
    output=root/'docs/data/infrastructure-execution-2026-10-29'
    files=[package/name for name in ['pyproject.toml','requirements.lock','README.md','Dockerfile','compose.yaml','.env.example']]
    for name in ['src','migrations','config','tools','tests','runbooks']:
        files.extend(path for path in (package/name).rglob('*') if path.is_file()
                     and '__pycache__' not in path.parts and not path.name.startswith('.'))
    bindings=[]
    bundle=output/('implementation-'+args.revision+'.tar.gz')
    fd,temporary=tempfile.mkstemp(prefix='implementation-',suffix='.tmp',dir=output)
    candidate=Path(temporary)
    with os.fdopen(fd,'wb') as file, gzip.GzipFile(filename='',fileobj=file,mode='wb',mtime=0) as compressed,tarfile.open(fileobj=compressed,mode='w|') as tar:
        for path in sorted(set(files)):
            if path.is_symlink():
                raise ValueError('Implementation archive cannot contain symlinks')
            content=path.read_bytes()
            relative=path.relative_to(root).as_posix()
            digest=hashlib.sha256(content).hexdigest()
            bindings.append({'path':relative,'sha256':digest,'bytes':len(content)})
            entry=tarfile.TarInfo(relative)
            entry.size=len(content);entry.mode=0o644;entry.mtime=0
            tar.addfile(entry,io.BytesIO(content))
    try:
        if bundle.exists():
            if hashlib.sha256(bundle.read_bytes()).digest()!=hashlib.sha256(candidate.read_bytes()).digest():
                raise ValueError('Implementation revision already exists; choose a new revision')
        else:
            os.link(candidate,bundle)
    finally:
        candidate.unlink(missing_ok=True)
    archive=FileArchive(package/'.state/archive')
    with bundle.open('rb') as handle:
        archived=archive.put(handle)
    with connect(os.environ['DAYLIGHT_DATA_DATABASE_URL']) as connection:
        with connection.transaction():
            connection.execute('SET LOCAL ROLE daylight_writer')
            insert_exact(connection,'dl_control.artifact',['sha256','byte_length','object_key'],
                         [archived.sha256,archived.byte_length,archived.object_key],['sha256'])
    if archive.verify(archived.sha256)!=bundle.stat().st_size:
        raise RuntimeError('Implementation archive verification failed')
    with tarfile.open(bundle,mode='r:gz') as tar:
        for binding in bindings:
            with tar.extractfile(binding['path']) as member:
                if hashlib.sha256(member.read()).hexdigest()!=binding['sha256']:
                    raise RuntimeError('Bundled implementation bytes differ')
    receipt={'schema':'daylight-implementation-archive/1','revision':args.revision,'observed_at':datetime.now(timezone.utc).isoformat(),
        'bundle_path':str(bundle.relative_to(root)),'sha256':archived.sha256,'bytes':archived.byte_length,
        'object_key':archived.object_key,'members_verified':len(bindings),'files':bindings,
        'contains_customer_data':False,'contains_credentials':False,'image_lock':'pending_actual_target',
        'meaning':'Exact initial implementation bytes; not all-layer acceptance or a cloud deployment'}
    receipt_path=output/('implementation-archive-'+args.revision+'.json')
    if receipt_path.exists():
        prior=json.loads(receipt_path.read_text())
        if prior['sha256']!=receipt['sha256']:
            raise ValueError('Implementation receipt is immutable; choose a new revision')
    else:
        receipt_path.write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n')
    print(json.dumps({k:receipt[k] for k in ['sha256','bytes','members_verified']}))


if __name__=='__main__':
    main()
