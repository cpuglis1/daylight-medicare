"""Fingerprint and verify an exact L11 research revision; never accept it."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'docs/data/l11-medigap-rights-2026-10-28'


def fingerprint(path):
    with Path(path).open('rb') as stream:
        sha=hashlib.file_digest(stream,'sha256').hexdigest()
    return {'sha256':sha,'bytes':Path(path).stat().st_size}


def seal(build):
    target=build/'manifest.json'
    if target.exists():raise ValueError('Exact revision already sealed')
    validation=json.loads((build/'validation.json').read_text())
    tests=json.loads((build/'tests-result.json').read_text())
    if validation['status']!='passed' or tests['exit_code']!=0:
        raise ValueError('Required checks did not pass')
    sources=json.loads((build/'sources.json').read_text())
    paths=set()
    for source in sources.values():
        for key in ['path','receipt_path','text_path','paragraphs_path']:
            if source.get(key):paths.add(source[key])
        for row in source.get('original_captures',[]):paths.add(row['path'])
        if source.get('wire_sha256'):
            paths.add('docs/data/l11-medigap-rights-2026-10-28/acquisition-r1/raw/'+source['wire_sha256'])
    for name in ['PLAN.md','reuse-audit.json','source-needs.json','planning-verification.json',
                 'synthetic-cases-r1.json','acquisition-r1/extraction-index.json']:
        paths.add(str((BASE/name).relative_to(ROOT)))
    for file in (build/'code').iterdir():
        paths.add('cms-slice/'+('tests/' if file.name.startswith('test_') else 'scripts/')+file.name)
    manifest={'schema':'l11-exact-research-manifest/1','created_at_utc':datetime.now(timezone.utc).isoformat(),
              'files':{str(p.relative_to(build)):fingerprint(p) for p in sorted(build.rglob('*')) if p.is_file()},
              'external_inputs':{p:fingerprint(ROOT/p) for p in sorted(paths)},
              'reference_year':2026,'reference_date':'2026-10-28','research_only':True,
              'full_l11_complete':False,'qualified_R16_review':None,'human_acceptance':None,'consumer_release_enabled':False}
    target.write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
    return verify(target)


def verify(path):
    manifest=json.loads(path.read_text());errors=[]
    for name,wanted in manifest['files'].items():
        p=path.parent/name
        if not p.is_file() or fingerprint(p)!=wanted:errors.append(name)
    for name,wanted in manifest['external_inputs'].items():
        p=ROOT/name
        if not p.is_file() or fingerprint(p)!=wanted:errors.append(name)
    if manifest['human_acceptance'] is not None or manifest['consumer_release_enabled'] or manifest['full_l11_complete']:
        errors.append('Research/review guard changed')
    result={'status':'passed' if not errors else 'failed','errors':errors,
            'manifest_sha256':fingerprint(path)['sha256'],'files_checked':len(manifest['files']),
            'external_inputs_checked':len(manifest['external_inputs'])}
    if errors:raise ValueError(json.dumps(result))
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('path',type=Path);parser.add_argument('--verify',action='store_true');args=parser.parse_args()
    print(json.dumps(verify(args.path) if args.verify else seal(args.path),indent=2))
