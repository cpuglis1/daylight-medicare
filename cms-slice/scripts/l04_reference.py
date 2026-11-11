"""Bounded published PDP lookup. No personal coverage, pricing or recommendations."""
import argparse
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT/'docs/data/l04-pdp-availability-2026-10-25'
PACKAGE = BASE/'build-r4'
REGISTRY = ROOT/'cms-slice/data-sources/l04-published-reference-review.json'
CODE = {'l04_build.py','l04_validate.py','l04_reference.py','l04_acquire.py'}
LOADED_SHA = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


class ReferenceError(ValueError):
    pass


class ReferenceHeld(ReferenceError):
    pass


def read(path):
    return json.loads(Path(path).read_text())


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()


def utc(value):
    result = datetime.fromisoformat(value)
    if result.tzinfo is None:
        raise ReferenceHeld('Timezone required')
    return result.astimezone(timezone.utc)


def verify(package=PACKAGE):
    package = Path(package).resolve()
    try:
        manifest = read(package/'manifest.json')
        if (manifest['schema'] != 'l04-build/1' or manifest['year'] != 2026
                or manifest['state'] != 'FL' or manifest['region'] != '11'
                or set(manifest['code_sha256']) != CODE):
            raise ReferenceHeld('Unsupported reference contract')
        for relative, sha in manifest['files_sha256'].items():
            path = (package/relative).resolve()
            if not path.is_relative_to(package) or digest(path) != sha:
                raise ReferenceHeld('Reference artifact changed')
        required = {'inventory.sqlite3','records.json','field-map.json','scope.json','coverage.json','source-manifest.json','column-ledger.json','gaps.json','florida-pdp-reference.csv','field-coverage.json'}
        if not required <= manifest['files_sha256'].keys():
            raise ReferenceHeld('Incomplete reference artifacts')
        for item in manifest['evidence'].values():
            path = (ROOT/item['path']).resolve()
            if not path.is_relative_to(ROOT) or path.stat().st_size != item['bytes'] or digest(path) != item['sha256']:
                raise ReferenceHeld('Retained source evidence changed')
        for name, sha in manifest['code_sha256'].items():
            if digest(ROOT/'cms-slice/scripts'/name) != sha:
                raise ReferenceHeld('Reference implementation changed; rebuild and validate a new revision')
        if LOADED_SHA != manifest['code_sha256']['l04_reference.py']:
            raise ReferenceHeld('Loaded reference implementation changed; reload required')
        validation = read(package.parent/(package.name+'-validation.json'))
        if (validation['schema'] != 'l04-independent-validation/1'
                or validation['manifest_sha256'] != digest(package/'manifest.json')
                or validation['failed'] != 0 or validation['source_fidelity_passed'] is not True):
            raise ReferenceHeld('Exact-build independent source validation required')
        return manifest
    except ReferenceHeld:
        raise
    except (OSError,ValueError,KeyError,TypeError) as error:
        raise ReferenceHeld('Published PDP reference unavailable or malformed') from error


def require_review(package=PACKAGE, registry=REGISTRY, now=None):
    current = now or datetime.now(timezone.utc)
    manifest = verify(package)
    try:
        receipt = read(registry)
        person = receipt['reviewer']
        if (receipt['schema'] != 'l04-published-review/1' or receipt['decision'] != 'accepted'
                or receipt['revoked'] is not False or receipt['package_id'] != manifest['package_id']
                or receipt['manifest_sha256'] != digest(Path(package)/'manifest.json')
                or receipt['validation_sha256'] != digest(Path(package).parent/(Path(package).name+'-validation.json'))
                or receipt['accepted_ids'] != sorted(r['offering_id'] for r in read(Path(package)/'records.json'))
                or receipt['accepted_field_map_sha256'] != manifest['files_sha256']['field-map.json']
                or receipt['accepted_gaps_sha256'] != manifest['files_sha256']['gaps.json']
                or person['qualified_for_scope'] is not True or person['independent_of_sales'] is not True
                or not isinstance(person['name'],str) or not person['name'].strip()
                or not isinstance(person['role'],str) or not person['role'].strip()
                or not isinstance(receipt['receipt'],str) or not receipt['receipt'].strip()
                or not utc(receipt['reviewed_at_utc']) <= current < utc(receipt['review_after_utc']) <= utc(manifest['source_review_after_utc'])):
            raise ReferenceHeld('Published PDP review pending, changed, expired or revoked')
        return manifest
    except ReferenceHeld:
        raise
    except (OSError,ValueError,TypeError,KeyError,AttributeError) as error:
        raise ReferenceHeld('A genuine scoped published-reference review is required') from error


def project(request, package=PACKAGE):
    """Deterministic projection used after the public lookup's integrity gate."""
    allowed = {'year','state','county_fips','pdp_region','ids'}
    if not isinstance(request,dict) or set(request)-allowed:
        raise ReferenceError('Only year, state/county/PDP region and optional IDs are supported')
    if type(request.get('year')) is not int or request['year'] != 2026:
        raise ReferenceHeld('This published reference supports benefit year 2026 only')
    if not any(k in request for k in ('state','county_fips','pdp_region')):
        raise ReferenceError('An explicit reference geography is required')
    if 'state' in request and request['state'] != 'FL':
        raise ReferenceHeld('No accepted reference scope for this state')
    if 'pdp_region' in request and request['pdp_region'] != '11':
        raise ReferenceHeld('No accepted reference scope for this PDP region')
    with closing(sqlite3.connect(f'file:{Path(package).resolve()}/inventory.sqlite3?mode=ro',uri=True)) as db:
        if 'county_fips' in request:
            if (not isinstance(request['county_fips'],str)
                    or not db.execute("SELECT 1 FROM counties WHERE fips=? AND state='FL' AND region='11'",(request['county_fips'],)).fetchone()):
                raise ReferenceHeld('Unknown or unsupported county relationship')
        records = [{'offering_id':key,'region':region,'state':state,'ordinal':ordinal,
                    'fields':json.loads(fields),'source':json.loads(locator)}
                   for ordinal,key,region,state,fields,locator in db.execute("SELECT ordinal,offering_id,region,state,fields_json,locator_json FROM catalog WHERE region='11' AND state='FL' ORDER BY offering_id")]
    if 'ids' in request:
        ids = request['ids']
        if (not isinstance(ids,list) or not ids or not all(isinstance(k,str) for k in ids)
                or len(ids) != len(set(ids)) or not set(ids) <= {r['offering_id'] for r in records}):
            raise ReferenceError('Use distinct known reference offering IDs')
        records = [r for r in records if r['offering_id'] in ids]
    return records


def lookup(request, *, package=PACKAGE, registry=REGISTRY, research=False, now=None):
    manifest = verify(package)
    records = project(request,package)
    if not research:
        require_review(package,registry,now)
    current = now or datetime.now(timezone.utc)
    return {'schema':'l04-published-result/1','package_id':manifest['package_id'],'benefit_year':2026,
            'state':'FL','pdp_region':'11','mode':'research_pending_review' if research else 'accepted_published_reference',
            'snapshot':read(Path(package)/'scope.json'),'records':records,
            'source_review_due':current >= utc(manifest['source_review_after_utc']),
            'coverage':read(Path(package)/'coverage.json'),'gaps':read(Path(package)/'gaps.json'),
            'personal_applicability':'not_assessed','live_enrollment_status':'not_established',
            'personal_prices_available':False,'recommendations_available':False,'enrollment_available':False}


def status(package=PACKAGE, registry=REGISTRY, now=None):
    try:
        manifest = verify(package)
        integrity, reason = 'passed',None
    except ReferenceHeld as error:
        return {'integrity':'held','reference_review':'held','reason':str(error),'consumer_reference_available':False}
    try:
        require_review(package,registry,now)
        accepted = True
    except ReferenceHeld as error:
        accepted,reason = False,str(error)
    coverage = read(Path(package)/'coverage.json')
    return {'package_id':manifest['package_id'],'integrity':integrity,'reference_review':'accepted_current' if accepted else 'pending_or_held',
            'consumer_reference_available':accepted,'observed_fl_offerings':coverage['observed_fl_offerings'],
            'published_set_reconciliation_passed':coverage['observed_set_agrees_pbp_monthly'],'reason':reason,
            'personal_prices_available':False,'recommendations_available':False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['status','lookup'])
    parser.add_argument('--package',type=Path,default=PACKAGE)
    parser.add_argument('--registry',type=Path,default=REGISTRY)
    parser.add_argument('--year',type=int)
    parser.add_argument('--state')
    parser.add_argument('--county-fips')
    parser.add_argument('--pdp-region')
    parser.add_argument('--id',action='append')
    parser.add_argument('--research',action='store_true')
    args = parser.parse_args()
    try:
        request = {'year':args.year}
        for key in ('state','county_fips','pdp_region'):
            if getattr(args,key) is not None:request[key] = getattr(args,key)
        if args.id is not None:request['ids'] = args.id
        result = status(args.package,args.registry) if args.command == 'status' else lookup(request,package=args.package,registry=args.registry,research=args.research)
        print(json.dumps(result,indent=2))
    except ReferenceError as error:
        print(json.dumps({'state':'held' if isinstance(error,ReferenceHeld) else 'invalid_request','reason':str(error)}))
        raise SystemExit(2)
