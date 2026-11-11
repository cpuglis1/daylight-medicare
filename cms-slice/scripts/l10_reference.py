"""Exact, bounded research access; no personal premium or recommendation API."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'docs/data/l10-medigap-2026-10-28'
LOADED_SHA = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


class ReferenceHeld(ValueError): pass


def sha(p):
    with Path(p).open('rb') as f: return hashlib.file_digest(f, 'sha256').hexdigest()


def load(p): return json.loads(Path(p).read_text())


def verify(package):
    package = Path(package).resolve()
    try:
        m = load(package / 'manifest.json')
        if m['schema'] != 'l10-build/1' or m['year'] != 2026 or m['county_fips'] != '12021' or m['human_acceptance'] is not None or m['consumer_release_enabled'] is not False or m['full_l10_complete'] is not False or m['research_only'] is not True:
            raise ReferenceHeld('Unsupported or promoted reference')
        if (package / 'SEALED').read_text().strip() != sha(package / 'manifest.json'): raise ReferenceHeld('Changed seal')
        required = {'sources.json', 'standardized-benefits.json', 'carrier-table-observations.json', 'filing-metadata.jsonl',
                    'filing-details.json', 'illustrations.jsonl', 'insurer-catalog.json', 'source-listings.json',
                    'product-form-leads.json', 'required-coverage-ledger.json',
                    'product-discovery-map.json', 'source-anomalies.json',
                    'gaps.json', 'coverage.json', 'before-after.json', 'inventory.sqlite3'}
        if set(m['files_sha256']) != required: raise ReferenceHeld('Incomplete reference')
        if set(m['code_sha256']) != {'cms-slice/scripts/' + n for n in ['l10_acquire.py', 'l10_collect_choices.py', 'l10_collect_irfs.py', 'l10_build.py', 'l10_validate.py', 'l10_reference.py']}: raise ReferenceHeld('Incomplete implementation binding')
        for rel, expected in m['files_sha256'].items():
            p = (package / rel).resolve()
            if not p.is_relative_to(package) or sha(p) != expected: raise ReferenceHeld('Changed package')
        for group in ['input_sha256', 'code_sha256']:
            for rel, expected in m[group].items():
                p = (ROOT / rel).resolve()
                if not p.is_relative_to(ROOT) or sha(p) != expected: raise ReferenceHeld('Changed source/input/implementation')
        if m['code_sha256']['cms-slice/scripts/l10_reference.py'] != LOADED_SHA: raise ReferenceHeld('Stale loaded implementation')
        for r in load(package / 'sources.json').values():
            p = (ROOT / r['path']).resolve()
            if not p.is_relative_to(ROOT) or sha(p) != r['sha256'] or p.stat().st_size != r['bytes']: raise ReferenceHeld('Changed source bytes')
        validation = load(package.parent / (package.name + '-validation.json'))
        if validation['schema'] != 'l10-independent-validation/1' or validation['passed'] is not True or validation['manifest_sha256'] != sha(package / 'manifest.json') or validation['choices_scenarios_checked'] != 500 or validation['standardized_cells_checked'] != 108 or validation['carrier_table_cells_checked'] != 680 or validation['unexplained_modeled_value_mismatches'] != 0:
            raise ReferenceHeld('Independent exact-build validation required')
        return m
    except ReferenceHeld: raise
    except (OSError, ValueError, KeyError, TypeError) as e: raise ReferenceHeld('Missing or malformed evidence') from e


def lookup(request, package=None, *, research=False):
    allowed = {'year', 'county_fips', 'kind', 'zip', 'company_names', 'variants', 'offset', 'limit'}
    if not isinstance(request, dict) or set(request) - allowed: raise ValueError('Only source identity/geography and bounded research fields are supported')
    if type(request.get('year')) is not int or request['year'] != 2026 or request.get('county_fips', '12021') != '12021': raise ReferenceHeld('Only 2026 Collier scope is supported')
    if research is not True: raise ReferenceHeld('Research only; source-use, R15 and exact acceptance remain pending')
    offset, limit = request.get('offset', 0), request.get('limit', 100)
    if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 250: raise ValueError('Integer offset and limit 1..250 required')
    if package is None:
        selection = load(BASE / 'CURRENT_REFERENCE.json'); package = ROOT / selection['package']
        if sha(Path(package) / 'manifest.json') != selection['manifest_sha256'] or sha(Path(package).parent / (Path(package).name + '-validation.json')) != selection['validation_sha256']: raise ReferenceHeld('Changed selected reference')
    package = Path(package).resolve(); m = verify(package)
    kind = request.get('kind', 'listings')
    if kind not in ['products', 'listings', 'benefits', 'carrier_tables', 'insurers']: raise ValueError('Unsupported research collection')
    companies = {x['company_name_raw'] for x in load(package / 'insurer-catalog.json')}
    variants = {'A', 'B', 'C', 'D', 'F', 'F*', 'G', 'G*', 'K', 'L', 'M', 'N'}
    for key, valid in [('company_names', companies), ('variants', variants)]:
        if key in request:
            v = request[key]
            if not isinstance(v, list) or not v or any(type(x) is not str for x in v) or len(v) != len(set(v)) or not set(v) <= valid: raise ReferenceHeld('Unknown/duplicate identity filter')
    if 'zip' in request and (type(request['zip']) is not str or request['zip'] not in {z for x in load(package / 'source-listings.json') for z in x['observed_zips']}): raise ReferenceHeld('Unsupported source ZIP')
    # Do not silently ignore filters that have no defined meaning for a collection.
    if kind != 'listings' and 'zip' in request: raise ValueError('ZIP filter is defined only for observed listings')
    if kind == 'benefits' and 'company_names' in request: raise ValueError('Standardized benefits do not establish a company product')
    if kind == 'insurers' and 'variants' in request: raise ValueError('Company filing leads do not establish plan letters')
    if kind == 'products':
        rows = load(package / 'product-discovery-map.json')['products']
        rows = [x for x in rows if ('variants' not in request or x['variant'] in request['variants']) and ('company_names' not in request or x['company_name_raw'] in request['company_names'])]
    elif kind == 'listings':
        rows = load(package / 'source-listings.json')
        rows = [x for x in rows if ('zip' not in request or request['zip'] in x['observed_zips']) and ('variants' not in request or x['variant'] in request['variants']) and ('company_names' not in request or x['source_listing_key']['companY_NM'] in request['company_names'])]
    elif kind == 'benefits':
        data = load(package / 'standardized-benefits.json'); rows = data['cells']
        rows = [x for x in rows if 'variants' not in request or x['variant'] in request['variants']]
    elif kind == 'carrier_tables':
        rows = load(package / 'carrier-table-observations.json')
        if 'company_names' in request and request['company_names'] != ['BLUE CROSS & BLUE SHIELD OF FLORIDA, INC.']: raise ReferenceHeld('No table evidence for requested company combination')
        rows = [x for x in rows if 'variants' not in request or x['variant'] in request['variants']]
    else:
        rows = load(package / 'insurer-catalog.json')
        rows = [x for x in rows if 'company_names' not in request or x['company_name_raw'] in request['company_names']]
    if not rows: raise ReferenceHeld('No exact supported source join; unknown is not absence or poor fit')
    return {'scope': '2026 Collier L10 published/source-observed research; no complete all-market or personal quote claim',
            'research_only': True, 'consumer_release_enabled': False, 'human_acceptance': None,
            'manifest_sha256': sha(package / 'manifest.json'), 'kind': kind, 'total': len(rows),
            'records': rows[offset:offset+limit], 'next_offset': offset+limit if offset+limit < len(rows) else None,
            'conditions': load(package / 'standardized-benefits.json')['conditions'] if kind == 'benefits' else [],
            'source_review_overdue': datetime.now(timezone.utc) >= datetime.fromisoformat(m['source_review_after_utc']),
            'limits': load(package / 'gaps.json')['limits']}


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--package', type=Path); p.add_argument('--research', action='store_true')
    p.add_argument('--kind', default='listings'); p.add_argument('--zip'); args = p.parse_args()
    request = {'year': 2026, 'kind': args.kind}
    if args.zip: request['zip'] = args.zip
    print(json.dumps(lookup(request, args.package, research=args.research), indent=2, ensure_ascii=False))
