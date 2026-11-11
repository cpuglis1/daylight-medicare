"""Create a portable source runtime without requiring build tools in the data venv."""
import argparse
import gzip
import io
import json
from pathlib import Path
import tarfile

from daylight_data.plan_types.common import code_binding,file_sha


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args()
    package=Path(__file__).resolve().parents[1]
    source=package/'src/daylight_data/plan_types'
    files={'src/daylight_data/__init__.py':package/'src/daylight_data/__init__.py',
           'pyproject.toml':package/'pyproject.toml','requirements.lock':source/'runtime-requirements.lock'}
    for path in sorted(source.iterdir()):
        if path.is_file() and path.suffix in {'.py','.sql','.lock','.md'}:
            files['src/daylight_data/plan_types/'+path.name]=path
    with args.output.open('xb') as target,gzip.GzipFile(filename='',fileobj=target,mode='wb',mtime=0) as zipped,tarfile.open(fileobj=zipped,mode='w|') as archive:
        for name,path in files.items():
            data=path.read_bytes();entry=tarfile.TarInfo(name)
            entry.size=len(data);entry.mode=0o600;entry.mtime=0
            archive.addfile(entry,io.BytesIO(data))
    print(json.dumps({'path':str(args.output),'sha256':file_sha(args.output),'code':code_binding(),
                      'files':len(files),'consumer_release':'held'},sort_keys=True))


if __name__=='__main__':main()
