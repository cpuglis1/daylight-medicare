"""Published L01 reference only: no personal inputs, selection or calculations.

The data files are inspectable research. Consumer lookup requires the owner's
genuine, exact-scope review receipt; this module cannot create that receipt.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / 'docs/data/l01-national-2026/published-reference-r1'
REGISTRY = ROOT / 'cms-slice/data-sources/l01-published-reference-review.json'
CODE_FILES = ('l01_reference.py', 'l01_reference_build.py')
LOADED_SHA = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


class ReferenceError(ValueError):
    pass


class ReferenceHeld(ReferenceError):
    pass


def read(path):
    return json.loads(Path(path).read_text())


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def utc(value):
    date = datetime.fromisoformat(value)
    if date.tzinfo is None:
        raise ReferenceHeld('Review dates require a timezone')
    return date.astimezone(timezone.utc)


def verify(package=PACKAGE, now=None):
    package = Path(package).resolve()
    try:
        manifest = read(package / 'manifest.json')
        year, revision = manifest['year'], manifest['revision']
        if (manifest['schema'] != 'l01-published-manifest/1' or type(year) is not int
                or not 2000 <= year <= 2200 or type(revision) is not int or revision < 1
                or manifest['package_id'] != f'L01-PUBLISHED-US-{year}-r{revision}'):
            raise ReferenceHeld('Invalid annual reference identity')
        required = {'scope.json', 'inventory.json', 'costs.json', 'bands.json', 'notes.json',
                    'observations.json', 'sources.json', 'conflicts.json', 'source-dispositions.json',
                    'checks.json', 'review-packet.json'}
        if not required <= set(manifest['files_sha256']):
            raise ReferenceHeld('Incomplete reference manifest')
        for relative, sha in manifest['files_sha256'].items():
            path = (package / relative).resolve()
            if not path.is_relative_to(package) or digest(path) != sha:
                raise ReferenceHeld('Reference data changed')
        for relative, sha in manifest['evidence_sha256'].items():
            path = (ROOT / relative).resolve()
            if not path.is_relative_to(ROOT) or digest(path) != sha:
                raise ReferenceHeld('Bound source evidence changed')
        if set(manifest['code_sha256']) != set(CODE_FILES):
            raise ReferenceHeld('Reference implementation binding missing')
        for filename, sha in manifest['code_sha256'].items():
            if digest(ROOT / 'cms-slice/scripts' / filename) != sha:
                raise ReferenceHeld('Reference implementation changed')
        if LOADED_SHA != manifest['code_sha256']['l01_reference.py']:
            raise ReferenceHeld('Loaded reference code differs; reload required')
        for item in read(package / 'costs.json') + read(package / 'bands.json') + read(package / 'notes.json'):
            if item['premium_year'] != year or item['effective_from'] != manifest['effective_from'] or item['effective_until'] != manifest['effective_until']:
                raise ReferenceHeld('Reference entry year/period mismatch')
        checks = read(package / 'checks.json')
        if checks['failed'] or not checks['engineering_complete']:
            raise ReferenceHeld('Reference data checks incomplete')
        current = now or datetime.now(timezone.utc)
        if current >= utc(manifest['source_review_after_utc']):
            raise ReferenceHeld('Reference source review is due')
        return manifest
    except ReferenceHeld:
        raise
    except (OSError, KeyError, TypeError, ValueError) as error:
        raise ReferenceHeld('Reference unavailable or malformed') from error


def require_review(package=PACKAGE, registry=REGISTRY, now=None):
    current = now or datetime.now(timezone.utc)
    manifest = verify(package, current)
    try:
        review = read(registry)
        person = review['reviewer']
        scope_ids = sorted(x['id'] for name in ('costs.json', 'bands.json', 'notes.json') for x in read(Path(package)/name))
        if (review['schema'] != 'l01-published-review/1' or review['decision'] != 'accepted'
                or review['revoked'] is not False or review['package_id'] != manifest['package_id']
                or review['manifest_sha256'] != digest(Path(package)/'manifest.json')
                or not isinstance(person['name'], str) or not person['name'].strip()
                or not isinstance(person['role'], str) or not person['role'].strip()
                or person['qualified_for_scope'] is not True or person['independent_of_sales'] is not True
                or review['accepted_ids'] != scope_ids or review['conditions_and_units_reviewed'] is not True
                or not isinstance(review['receipt'], str) or not review['receipt'].strip()
                or not utc(review['reviewed_at_utc']) <= current < utc(review['review_after_utc']) <= utc(manifest['source_review_after_utc'])):
            raise ReferenceHeld('Published-cost review is pending, changed, expired or revoked')
        conflicts = read(Path(package)/'conflicts.json')
        if set(review['conflict_decisions']) != {c['id'] for c in conflicts}:
            raise ReferenceHeld('Exact conflict decisions required')
        for conflict in conflicts:
            decision = review['conflict_decisions'][conflict['id']]
            encoded = json.dumps(conflict, sort_keys=True, separators=(',', ':')).encode()
            if (decision['decision'] != 'accept_proposed_reference_disposition'
                    or decision['conflict_sha256'] != hashlib.sha256(encoded).hexdigest()
                    or not decision['reason'].strip()):
                raise ReferenceHeld('Conflict disposition not accepted for this revision')
        return manifest
    except ReferenceHeld:
        raise
    except (OSError, KeyError, ValueError, TypeError, AttributeError) as error:
        raise ReferenceHeld('A genuine scoped published-cost review is required') from error


def lookup(request, *, package=PACKAGE, registry=REGISTRY, research=False, now=None):
    # No income, history, dates of care, charges, geography or commercial fields.
    if not isinstance(request, dict) or set(request) - {'year', 'ids'}:
        raise ReferenceError('Only reference year and optional entry IDs are supported')
    manifest = verify(package, now)
    if type(request.get('year')) is not int or request['year'] != manifest['year']:
        raise ReferenceHeld('No accepted reference package for the requested year')
    records = [x for name in ('costs.json', 'bands.json', 'notes.json') for x in read(Path(package)/name)]
    if 'ids' in request:
        ids = request['ids']
        if (not isinstance(ids, list) or not ids or not all(isinstance(x, str) for x in ids)
                or len(ids) != len(set(ids)) or not set(ids) <= {x['id'] for x in records}):
            raise ReferenceError('Use distinct known reference entry IDs')
        records = [x for x in records if x['id'] in ids]
    if not research:
        require_review(package, registry, now)
    qualification_ids={qid for row in records for qid in row.get('qualification_ids',[])}
    qualifications=[row for row in read(Path(package)/'notes.json') if row['id'] in qualification_ids]
    observation_ids={oid for row in records+qualifications for oid in row['observation_ids']}
    observations=[row for row in read(Path(package)/'observations.json') if row['id'] in observation_ids]
    source_ids={row['source_id'] for row in observations}
    conflict_ids={cid for row in records for cid in row['conflict_ids']}
    conflicts=[row for row in read(Path(package)/'conflicts.json') if row['id'] in conflict_ids]
    return {'schema':'l01-published-result/1', 'package_id':manifest['package_id'],
            'year':manifest['year'], 'mode':'research_pending_review' if research else 'accepted_published_reference',
            'records':records, 'qualifications':qualifications, 'observations':observations,
            'sources':[row for row in read(Path(package)/'sources.json') if row['id'] in source_ids],
            'source_conflicts':conflicts, 'personal_applicability_determined':False,
            'personal_total_available':False, 'recommendations_available':False}


def status(package=PACKAGE, registry=REGISTRY, now=None):
    state, error = 'passed', None
    try:
        manifest = verify(package, now)
    except ReferenceHeld as problem:
        state, error = 'held', str(problem)
        manifest = read(Path(package)/'manifest.json')
    accepted = False
    if state == 'passed':
        try:
            require_review(package, registry, now)
            accepted = True
        except ReferenceHeld as problem:
            error = str(problem)
    return {'package_id':manifest['package_id'], 'year':manifest['year'], 'integrity':state,
            'engineering_complete':state=='passed', 'review':'accepted_current' if accepted else 'pending_or_held',
            'consumer_reference_available':accepted, 'hold_reason':error,
            'personal_applicability_available':False, 'personal_total_available':False,
            'recommendations_available':False, 'manifest_sha256':digest(Path(package)/'manifest.json')}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['status','lookup'])
    parser.add_argument('--package', type=Path, default=PACKAGE)
    parser.add_argument('--registry', type=Path, default=REGISTRY)
    parser.add_argument('--year', type=int)
    parser.add_argument('--id', action='append')
    parser.add_argument('--research', action='store_true', help='CLI inspection only; never consumer approval')
    args = parser.parse_args()
    try:
        if args.command == 'status':
            result = status(args.package,args.registry)
        else:
            request={'year':args.year}
            if args.id is not None:
                request['ids']=args.id
            result=lookup(request,package=args.package,registry=args.registry,research=args.research)
        print(json.dumps(result,indent=2))
    except ReferenceError as error:
        print(json.dumps({'state':'held' if isinstance(error,ReferenceHeld) else 'invalid_request','reason':str(error)}))
        raise SystemExit(2)
