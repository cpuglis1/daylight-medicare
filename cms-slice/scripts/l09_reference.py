"""Bounded research lookup of published 2026 contract quality. No personal fit."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'docs/data/l09-star-ratings-2026-10-28'
LOADED_SHA=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


class ReferenceHeld(ValueError):pass


def digest(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def load(path):return json.loads(Path(path).read_text())


def verify(package):
    package=Path(package).resolve()
    try:
        m=load(package/'manifest.json')
        if m['schema']!='l09-build/1' or m['year']!=2026 or m['archive_sha256']!='a72f4f4965239e12b3b264c843a71ea6bbd9c655547be5b1f95b3b0df4d1cde7' or m['required_observations']!=2448 or m['offerings']!=82 or m['contracts']!=24 or m['consumer_release_enabled'] is not False or m['human_acceptance'] is not None:
            raise ReferenceHeld('Unsupported or promoted reference')
        if (package/'SEALED').read_text().strip()!=digest(package/'manifest.json'):raise ReferenceHeld('Changed seal')
        for rel,sha in m['files_sha256'].items():
            path=(package/rel).resolve()
            if not path.is_relative_to(package) or digest(path)!=sha:raise ReferenceHeld('Changed reference artifact')
        required={'observations.json','offerings.json','scope.json','coverage.json','measure-definitions.json','documents.json','gaps.json','inventory.sqlite3','source-manifest.json','source-members.json','source-tables.json','context-tables.json'}
        if not required<=m['files_sha256'].keys():raise ReferenceHeld('Incomplete reference')
        if set(m['code_sha256'])!={'cms-slice/scripts/'+n for n in ['l09_acquire.py','l09_build.py','l09_validate.py','l09_reference.py']}:raise ReferenceHeld('Incomplete implementation binding')
        for group in ['input_sha256','code_sha256']:
            for rel,sha in m[group].items():
                p=(ROOT/rel).resolve()
                if not p.is_relative_to(ROOT) or digest(p)!=sha:raise ReferenceHeld('Changed input or implementation')
        if m['code_sha256']['cms-slice/scripts/l09_reference.py']!=LOADED_SHA:raise ReferenceHeld('Loaded implementation is stale')
        for s in load(package/'source-manifest.json')['sources'].values():
            p=(ROOT/s['path']).resolve()
            if not p.is_relative_to(ROOT) or digest(p)!=s['sha256'] or p.stat().st_size!=s['bytes']:raise ReferenceHeld('Changed retained source')
        v=load(package.parent/(package.name+'-validation.json'))
        if v['schema']!='l09-independent-validation/1' or v['passed'] is not True or v['manifest_sha256']!=digest(package/'manifest.json') or v['source_cells_checked']!=2448 or v['offering_joins_checked']!=82 or v['unexplained_modeled_value_mismatches']!=0:
            raise ReferenceHeld('Exact-build independent validation required')
        return m
    except ReferenceHeld:raise
    except (OSError,ValueError,KeyError,TypeError) as e:raise ReferenceHeld('L09 evidence is unavailable or malformed') from e


def lookup(request,package=None,*,research=False):
    allowed={'year','county_fips','offering_ids','contract_ids','kinds','offset','limit'}
    if not isinstance(request,dict) or set(request)-allowed:raise ValueError('Only exact year/geography/identities/types and bounded pagination are supported')
    if type(request.get('year')) is not int or request['year']!=2026 or request.get('county_fips','12021')!='12021':raise ReferenceHeld('Only the pinned 2026 Collier/Florida reference is supported')
    if research is not True:raise ReferenceHeld('Research only: exact source-use and published-reference acceptance remain pending')
    if package is None:
        selection=load(BASE/'CURRENT_REFERENCE.json');package=ROOT/selection['package']
        if digest(Path(package)/'manifest.json')!=selection['manifest_sha256'] or digest(Path(package).parent/(Path(package).name+'-validation.json'))!=selection['validation_sha256']:raise ReferenceHeld('Current selection changed')
    package=Path(package).resolve();m=verify(package)
    offerings=load(package/'offerings.json');all_o={r['offering_id'] for r in offerings};all_c={r['contract'] for r in offerings}
    for key,valid in [('offering_ids',all_o),('contract_ids',all_c),('kinds',{'summary','domain','measure_stars','measure_data'})]:
        values=request.get(key)
        if key in request and (not isinstance(values,list) or not values or any(type(v)is not str for v in values) or len(values)!=len(set(values)) or not set(values)<=valid):raise ReferenceHeld('Unknown, duplicate or unsupported '+key)
    offset,limit=request.get('offset',0),request.get('limit',100)
    if type(offset)is not int or offset<0 or type(limit)is not int or not 1<=limit<=250:raise ValueError('Bounded integer offset and limit 1..250 required')
    selected=[r for r in offerings if ('offering_ids' not in request or r['offering_id'] in request['offering_ids']) and ('contract_ids' not in request or r['contract'] in request['contract_ids'])]
    if not selected:raise ReferenceHeld('Requested identity combination has no supported join')
    contracts={r['contract'] for r in selected};kinds=set(request.get('kinds',['summary']))
    with sqlite3.connect('file:'+str(package/'inventory.sqlite3')+'?mode=ro',uri=True) as con:
        records=[json.loads(row[0]) for row in con.execute('SELECT payload FROM observations ORDER BY id')]
    records=[r for r in records if r['contract'] in contracts and r['kind'] in kinds]
    return {'scope':'Published contract quality research; no personal fit or eligibility','year':2026,
        'manifest_sha256':digest(package/'manifest.json'),'research_only':True,'consumer_release_enabled':False,
        'source_review_overdue':datetime.now(timezone.utc)>=datetime.fromisoformat(m['source_review_after_utc']),
        'offerings':selected,'total_observations':len(records),'observations':records[offset:offset+limit],
        'next_offset':offset+limit if offset+limit<len(records) else None,
        'limits':load(package/'gaps.json')['limits']}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--package',type=Path);p.add_argument('--year',type=int,default=2026);p.add_argument('--offering-id');p.add_argument('--research',action='store_true');a=p.parse_args()
    request={'year':a.year}
    if a.offering_id:request['offering_ids']=[a.offering_id]
    print(json.dumps(lookup(request,a.package,research=a.research),indent=2,ensure_ascii=False))
