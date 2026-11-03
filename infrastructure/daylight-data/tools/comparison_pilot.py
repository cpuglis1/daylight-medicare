#!/usr/bin/env python3
"""Build an additive, unaccepted L03 research tranche; never touch a database.

The frozen master is streamed, not expanded into SQLite or loaded into memory.
Carrier transcription inputs and CMS inputs are read separately. Their proposed
alignment is not an independent interpretation review or an accepted release.
"""
from __future__ import annotations

import argparse
from collections import Counter
from decimal import Decimal, InvalidOperation
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys
import zipfile


BASE = Path('docs/data/l03-ma-benefits-2026-10-25')
PACKET = Path('docs/data/l03-ma-benefits-2026-11-01-comparison-pilot-r10')
OFFERING = '2026:H5652:002:000'
CMS_PREFIX = '/pbp/0/planLevelCostSharing/planDeductible/planDeductibleDetails'
SB = '4da5fb8e022fde082317606d85f22bec561315c7fbf197d3b06944e9d960439d'
EOC = '7602dc081bd6d615dac7f43d3739234668e5701c5464cc89d061ac1f46ae75ba'
ARCHIVE = '65077aeb8deb6e82eaeddc8e32b2b1a810d1df2ca814a69b1d24401f4f5cbbe3'
MEMBER_SHA = 'e40e423ec93ffecbd482ecc3c707ba53654bf522ac2d58cea720799f0080d52f'
R9_FREEZE_SHA = '81e1a5f106f15db3a06a738fad0c315ec09ace99ae2908d80507904fb8df3e6d'
PAGES = {(SB, 2), (SB, 10), (EOC, 39), (EOC, 40)}
FAMILIES = ('authorization', 'referral', 'network_and_setting', 'deductible',
            'frequency_and_quantity', 'covered_days', 'shared_allowance',
            'qualification', 'exclusion', 'waiver_and_replacement')


class PilotError(ValueError):
    pass


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def file_sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def load(path):
    return json.loads(path.read_text())


def norm(text):
    # Selection support only. This is never factual equivalence or a merge key.
    return re.sub(r'[^a-z0-9]+', ' ', text.casefold()).strip()


def verify_inputs(repository):
    base = repository / BASE
    freeze = load(base / 'semantic-inventory-r9/freeze.json')
    if file_sha(base / 'semantic-inventory-r9/freeze.json') != R9_FREEZE_SHA:
        raise PilotError('Frozen r9 manifest changed')
    declared = {
        str(BASE / 'semantic-inventory-r9/freeze.json'): R9_FREEZE_SHA,
        str(BASE / 'source-reconciliation-r7/manifest.json'): '8bd8b936bb31425e885424cc6aeb74d0f1589907bae51c2c1cdf6df6f1d65dc2',
        str(BASE / 'source-reconciliation-r7/new-source-pages.jsonl.gz'): '8183750fd0749691e6ad13ba31de627ee65b6d3965290d51211e909702f08706',
        str(BASE / 'build-r1/field-dictionary.json'): 'e0fd1f22f423ab4933d5abd18abd3644e7baa98b58c4760b0f42387580960ce0',
        str(BASE / 'bounded-reference-r4/manifest.json'): 'fb163f824e35cbb52b5aa11bd520de64bd4fa5e51b574f7d3de4c3accbaab881',
        str(BASE / 'acceptance-r4/review-receipt.json'): '275be9d2b0842fce326648c27786208430b29b66b894d42ead275ce37157d892',
        str(Path('docs/data/l02-ma-availability-2026-10-25/acquisition-r1/raw') / ARCHIVE): ARCHIVE,
    }
    for name in ('master-inventory.jsonl.gz', 'inventory-binding.json', 'required-missing-evidence.json',
                 'pilot-contract.json', 'code/l03_comparison_contract.py', 'code/l03_r9_comparison.py'):
        declared[str(BASE / 'semantic-inventory-r9' / name)] = freeze['files_sha256'][name]
    for sha in (SB, EOC):
        declared[str(BASE / 'source-reconciliation-r7/acquisition/raw' / sha)] = sha
    reference = load(base / 'bounded-reference-r4/manifest.json')
    for name, expected in reference['files_sha256'].items():
        declared[str(BASE / 'bounded-reference-r4' / name)] = expected
    for name, expected in reference['code_sha256'].items():
        declared[name] = expected
    bindings = []
    for name, expected in sorted(declared.items()):
        path = repository / name
        observed = file_sha(path)
        if observed != expected:
            raise PilotError('Source pin mismatch: ' + name)
        bindings.append({'path': name, 'sha256': observed, 'bytes': path.stat().st_size})
    entries = load(base / 'bounded-reference-r4/entries.json')
    receipt = load(base / 'acceptance-r4/review-receipt.json')
    if (len(entries) != 535 or sorted(e['id'] for e in entries) != receipt['accepted_entry_ids']
            or receipt['decision'] != 'accepted' or receipt['revoked'] is not False):
        raise PilotError('Exact prior reference changed')
    return bindings


def carrier_pages(repository):
    """Source-only transcription: no CMS amounts or interpretations are inputs."""
    pages = {}
    path = repository / BASE / 'source-reconciliation-r7/new-source-pages.jsonl.gz'
    with gzip.open(path, 'rt') as stream:
        for line in stream:
            row = json.loads(line)
            key = row['document_sha256'], row['pdf_page']
            if key not in PAGES:
                continue
            if key in pages:
                raise PilotError('Duplicate carrier page')
            for field in ('text', 'layout_text'):
                if hashlib.sha256(row[field].encode()).hexdigest() != row[field + '_sha256']:
                    raise PilotError('Carrier page text changed')
            pages[key] = {key: value for key, value in row.items() if key != 'ocr_words'}
    if set(pages) != PAGES:
        raise PilotError('Required carrier page missing')
    return pages


def select_reason(row, pages):
    context = row['context']
    if context.get('source_section') == 'Section 1.2 Our plan deductible':
        return 'entire_frozen_EOC_deductible_section'
    if context.get('source_container', '').startswith(CMS_PREFIX + '/'):
        return 'complete_CMS_plan_deductible_schedule_and_required_controls'
    assertion = norm(row.get('detail', {}).get('assertion', ''))
    if (assertion and context.get('unresolved_scope_discriminator') == SB
            and assertion in norm(pages[(SB, 10)]['text'])):
        return 'SB_deductible_page_assertion_with_original_scope_marker_retained'
    return None


def inventory(stream, pages, expected_digest):
    """Verify the full frozen census while retaining only one offering's ledger."""
    sha = hashlib.sha256(b'[')
    prior = None
    counts, states = Counter(), Counter()
    selected, ledger = [], []
    proposition_members = {}
    for index, row in enumerate(stream):
        if prior is not None and row['id'] <= prior:
            raise PilotError('Duplicate or unsorted canonical identity')
        if row['kind'] not in {'claim', 'condition'} or row['accepted_for_reference'] is not False:
            raise PilotError('Invalid canonical kind/acceptance')
        if index:
            sha.update(b',')
        sha.update(canonical(row).encode())
        prior = row['id']
        counts[row['kind']] += 1
        states.update(row['states'])
        if row['offering_id'] != OFFERING:
            continue
        reason = select_reason(row, pages)
        scope = row['context'].get('complete_source_proposition_scope')
        if scope:
            proposition_members.setdefault(scope, []).append(row['id'])
        ledger.append({'inventory_id': row['id'], 'kind': row['kind'],
                       'frozen_record_sha256': digest(row), 'frozen_states': row['states'],
                       'tranche_selected': bool(reason), 'accepted_for_reference': False})
        if reason:
            selected.append({'record': row, 'selection_reason': reason})
    sha.update(b']')
    if sha.hexdigest() != expected_digest:
        raise PilotError('Frozen canonical inventory digest changed')
    selected_ids = {x['record']['id'] for x in selected}
    for item in selected:
        scope = item['record']['context'].get('complete_source_proposition_scope')
        if scope and not set(proposition_members[scope]) <= selected_ids:
            raise PilotError('Linked claim/condition sibling omitted from tranche')
    return selected, ledger, {'required': dict(counts), 'frozen_states': dict(states),
                              'inventory_digest': sha.hexdigest()}


def cms_source(repository):
    path = repository / 'docs/data/l02-ma-availability-2026-10-25/acquisition-r1/raw' / ARCHIVE
    with zipfile.ZipFile(path) as archive:
        member = 'H5652-002-000-2026.json'
        raw = archive.read(member)
    if hashlib.sha256(raw).hexdigest() != MEMBER_SHA:
        raise PilotError('Exact CMS offering member changed')
    return json.loads(raw)['pbp'][0]['planLevelCostSharing']['planDeductible']['planDeductibleDetails']


def component_comparisons(cms, spec):
    """Compare declared source components, without pretending full meaning is ready."""
    carrier = spec['carrier_transcription']
    expected_scope = {'offering_id': OFFERING, 'network': 'in_network',
                      'currency': 'USD', 'period': 'calendar_year', 'variant': 'base'}
    if any(carrier.get(key) != value for key, value in expected_scope.items()):
        raise PilotError('Wrong exact carrier identity/network/unit/period/variant')
    try:
        amount_equal = (isinstance(cms['inNetworkDedAmount'], str)
                        and Decimal(cms['inNetworkDedAmount']).is_finite()
                        and Decimal(cms['inNetworkDedAmount']) == Decimal(carrier['amount']))
    except (KeyError, InvalidOperation, ValueError):
        raise PilotError('Invalid source decimal') from None
    selected = [r['categoryCode'] for r in cms['medicareServices'] if r['inNetwork'] == '1']
    return {
        'nominal_amount': {'CMS_raw': cms['inNetworkDedAmount'], 'carrier': carrier['amount'],
                          'decimal_equal': amount_equal, 'unit': 'USD/calendar_year'},
        'selected_CMS_categories': selected,
        'proposed_carrier_category_mapping': carrier['category_mapping'],
        'category_set_equal': set(selected) == set(carrier['category_mapping']),
        'CMS_all_Medicare_services_raw': cms['innMedCovBenSlctAll'],
        'CMS_out_of_network_control_raw': cms['hasOutOfNetworkDed'],
        'carrier_out_of_network_literal': carrier['out_of_network_literal'],
        'carrier_exceptions': carrier['exceptions'],
        'no_conflict_found_in_compared_components': bool(amount_equal and set(selected) == set(carrier['category_mapping'])),
        'full_meaning_outcome': 'insufficient_evidence',
        'component_agreement_does_not_establish_semantic_equivalence': True,
        'accepted_for_reference': False,
    }


def exact_quotes(pages, spec):
    result = []
    for item in spec['quote_spans']:
        page = pages[(item['document_sha256'], item['pdf_page'])]
        lines = page['text'].splitlines()
        start, end = item['line_start'], item['line_end']
        if type(start) is not int or type(end) is not int or not 1 <= start <= end <= len(lines):
            raise PilotError('Invalid exact quote locator')
        quote = '\n'.join(lines[start - 1:end])
        if hashlib.sha256(quote.encode()).hexdigest() != item['quote_sha256']:
            raise PilotError('Exact quote/lineage changed')
        result.append({**item, 'quote': quote, 'page_text_sha256': page['text_sha256'],
                       'layout_text_sha256': page['layout_text_sha256']})
    return result


def compare_with_sealed_contract(repository, observations):
    """Call the pinned comparator honestly: unreviewed meaning must stay held."""
    directory = repository / BASE / 'semantic-inventory-r9/code'
    name = '_daylight_pilot_pinned_comparison'
    module_spec = importlib.util.spec_from_file_location(name, directory / 'l03_comparison_contract.py')
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    # The sealed r9 wrapper imports its sealed r8 dependency by this name. This
    # command is an offline producer, never imported by the running application.
    previous = sys.modules.get('l03_comparison_contract')
    sys.modules['l03_comparison_contract'] = module
    try:
        wrapper_spec = importlib.util.spec_from_file_location(name + '_r9', directory / 'l03_r9_comparison.py')
        wrapper = importlib.util.module_from_spec(wrapper_spec)
        wrapper_spec.loader.exec_module(wrapper)
        return wrapper.compare(observations['cms'], observations['carrier'])
    finally:
        if previous is None:
            sys.modules.pop('l03_comparison_contract', None)
        else:
            sys.modules['l03_comparison_contract'] = previous


def source_projection(fragments, pages):
    """Reconstruct exact frozen quotation/parent spans from sealed page text."""
    parts = []
    for fragment in fragments:
        locator = fragment['locator']
        page = pages[(locator['document_sha256'], locator['pdf_page'])]
        body = page['layout_text']
        if hashlib.sha256(body.encode()).hexdigest() != locator['view_sha256']:
            raise PilotError('Native carrier view mismatch')
        lines = body.splitlines()
        a, b = locator['line_start'], locator['line_end']
        if not 1 <= a <= b <= len(lines):
            raise PilotError('Native passage line range invalid')
        passage = '\n'.join(lines[a - 1:b])
        if hashlib.sha256(passage.encode()).hexdigest() != locator['passage_sha256']:
            raise PilotError('Native passage hash mismatch')
        start, end = fragment['start'], fragment['end']
        if not 0 <= start < end <= len(passage):
            raise PilotError('Native source character range invalid')
        parts.append(passage[start:end])
    return re.sub(r'\s+', ' ', '\n'.join(parts)).strip()


def native_lineage(repository, selected, pages, cms):
    """Validate already captured read-only receipts; this function opens no DB."""
    directory = repository / PACKET / 'native-lineage'
    result, bindings = {}, []
    source_sha = load(repository / BASE / 'semantic-inventory-r9/freeze.json')['files_sha256']['inventory.sqlite3.gz']
    for subdirectory in ('r2', 'clauses-r1'):
        receipt_path = directory / subdirectory / 'LOOKUP_RECEIPT.json'
        receipt = load(receipt_path)
        if receipt['new_acceptance'] is not False or receipt.get('database_or_source_mutated') is not False:
            raise PilotError('Native lookup is not read-only held evidence')
        bindings.append({'path': str(receipt_path.relative_to(repository)), 'sha256': file_sha(receipt_path)})
        for name, declared in receipt['artifacts'].items():
            path = receipt_path.parent / name
            if file_sha(path) != declared['sha256']:
                raise PilotError('Native lookup artifact changed')
            records = []
            for envelope in load(path):
                if (envelope['has_more'] or envelope['new_acceptance'] or envelope.get('missing_ids')
                        or name != 'native_relationships.json' and 'missing_ids' not in envelope):
                    raise PilotError('Native lookup incomplete')
                if (envelope['binding']['accepted_release_id'] is not None
                        or len(envelope['authority']) != 6
                        or any(a['state'] != 'held' for a in envelope['authority'].values())):
                    raise PilotError('Native lookup cannot grant authority')
                records.extend(envelope['records'])
            if len(records) != declared['records']:
                raise PilotError('Native lookup count changed')
            for record in records:
                raw = json.dumps(record['raw_payload'], sort_keys=True, separators=(',', ':'), ensure_ascii=False)
                if hashlib.sha256(raw.encode()).hexdigest() != record['raw_sha256']:
                    raise PilotError('Native raw payload hash mismatch')
                if record['original_path'] != str(BASE / 'semantic-inventory-r9/inventory.sqlite3.gz'):
                    raise PilotError('Wrong native source parent')
                if record['artifact_sha256'] != source_sha:
                    raise PilotError('Wrong frozen native source hash')
            result[name] = records
            bindings.append({'path': str(path.relative_to(repository)), 'sha256': declared['sha256']})
    observations = {r['raw_payload']['id']: r for r in result['native_observations.json']}
    sources = {r['raw_payload']['source_id']: r for r in result['native_sources.json']}
    clauses = {r['raw_payload']['id']: json.loads(r['raw_payload']['payload']) for r in result['native_clauses.json']}
    expected_obs = {i for entry in selected for i in entry['record']['observation_ids']}
    expected_sources = {i for entry in selected for i in entry['record']['source_ids']}
    representations = {i for entry in selected for i in entry['record']['representation_ids']}
    if set(observations) != expected_obs or set(sources) != expected_sources:
        raise PilotError('Native IDs differ from exact canonical scope')
    for entry in selected:
        row = entry['record']
        for identifier in row['observation_ids']:
            raw = observations[identifier]['raw_payload']
            if raw['unit_id'] not in row['representation_ids'] or raw['source_id'] not in row['source_ids']:
                raise PilotError('Canonical/native representation lineage mismatch')
    cms_values, intro_quotes = 0, 0
    for record in observations.values():
        raw = record['raw_payload']
        payload = json.loads(raw['payload'])
        if raw['layer'] == 'carrier_clause':
            quote = clauses[payload['clause_id']]['quote']
            if hashlib.sha256(quote.encode()).hexdigest() != payload['quote_sha256']:
                raise PilotError('Observation/clause quote binding mismatch')
        elif raw['layer'] == 'carrier_list_intro':
            if source_projection(payload['source_fragments'], pages) != re.sub(r'\s+', ' ', payload['quote']).strip():
                raise PilotError('Inherited list qualifier changed')
            intro_quotes += 1
        elif raw['layer'] == 'cms_json':
            locator = payload['locator']
            if (locator['archive_sha256'] != ARCHIVE or locator['member_sha256'] != MEMBER_SHA
                    or not locator['pointer'].startswith(CMS_PREFIX + '/')):
                raise PilotError('Wrong exact CMS source locator')
            value = cms
            for part in locator['pointer'][len(CMS_PREFIX) + 1:].split('/'):
                value = value[int(part)] if isinstance(value, list) else value[part]
            if value != payload['raw']:
                raise PilotError('Native CMS observation differs from original JSON')
            cms_values += 1
    for atom in clauses.values():
        for field, expected in [('source_fragments', atom['quote']), ('parent_source_fragments', atom['parent_sentence'])]:
            if source_projection(atom[field], pages) != re.sub(r'\s+', ' ', expected).strip():
                raise PilotError('Exact assertion/logical parent does not reconstruct')
        if not set(atom['required_unit_ids']) <= representations:
            raise PilotError('Required clause child omitted')
    for record in result['native_relationships.json']:
        raw = record['raw_payload']
        if raw['parent_id'] not in representations or raw['child_id'] not in representations:
            raise PilotError('Required relationship endpoint omitted')
    return {'passed': True, 'observations': len(observations), 'sources': len(sources),
            'clauses_and_logical_parents_reconstructed': len(clauses),
            'relationship_edges_preserved': len(result['native_relationships.json']),
            'CMS_original_pointer_values_verified': cms_values, 'inherited_list_quotes_reconstructed': intro_quotes,
            'bindings': bindings, 'condition_semantics_verified': False,
            'interpretation_review_complete': False, 'new_acceptance': False}, bindings


def build(repository, spec):
    implementation_sha = file_sha(Path(__file__))
    bindings = verify_inputs(repository)
    pages = carrier_pages(repository)
    master = repository / BASE / 'semantic-inventory-r9/master-inventory.jsonl.gz'
    expected = load(repository / BASE / 'semantic-inventory-r9/inventory-binding.json')
    with gzip.open(master, 'rt') as stream:
        selected, ledger, census = inventory((json.loads(line) for line in stream), pages, expected['inventory_digest'])
    if census['required'] != {'claim': 143505, 'condition': 249065}:
        raise PilotError('Global denominator changed')
    offering = Counter(row['kind'] for row in ledger)
    missing = [r['inventory_id'] for r in ledger if 'required_evidence_missing' in r['frozen_states']]
    if dict(offering) != {'claim': 1778, 'condition': 2897} or len(missing) != 16:
        raise PilotError('Whole-offering denominator changed')
    if [x['record']['id'] for x in selected] != spec['selected_canonical_ids']:
        raise PilotError('Exact selected tranche changed')
    cms = cms_source(repository)
    lineage, native_bindings = native_lineage(repository, selected, pages, cms)
    bindings.extend(native_bindings)
    comparison = component_comparisons(cms, spec)
    comparison['sealed_complete_meaning_comparator'] = compare_with_sealed_contract(repository, spec['structured_observations'])
    if comparison['sealed_complete_meaning_comparator']['outcome'] != 'insufficient_evidence':
        raise PilotError('Unreviewed source interpretation cannot close meaning')
    if not comparison['no_conflict_found_in_compared_components']:
        raise PilotError('Named source component mismatch; preserve for investigation')
    accounting = {'global_before': census, 'global_after': census,
                  'offering_id': OFFERING, 'offering_before': dict(offering), 'offering_after': dict(offering),
                  'selected_tranche': dict(Counter(x['record']['kind'] for x in selected)),
                  'outside_tranche': dict(offering - Counter(x['record']['kind'] for x in selected)),
                  'missing_evidence_ids_unchanged': missing,
                  'new_fully_supported': 0, 'new_awaiting_review': 0, 'new_accepted': 0,
                  'offering_meaning_reconciliation_pending': sum('evidence_reconciliation_pending' in r['frozen_states'] for r in ledger),
                  'offering_internal_pending_outside_prepared_tranche': sum(
                      'evidence_reconciliation_pending' in r['frozen_states'] and not r['tranche_selected'] for r in ledger),
                  'whole_offering_pilot_complete': False, 'all_21_representatives_complete': False,
                  'inventory_additions': [], 'inventory_removals': [], 'inventory_merges': [],
                  'frozen_inventory_scope_change': False, 'accepted_r4_entry_count_unchanged': 535}
    dispositions = [{'inventory_id': x['record']['id'], 'offering_id': OFFERING,
                     'kind': x['record']['kind'], 'state': 'pending', 'evidence_complete': False,
                     'comparison_record_id': spec['packet_id'] + ':selective-deductible',
                     'source_interpretation_record_id': spec['packet_id'] + ':proposed-source-interpretation',
                     'interpretation_review_complete': False, 'accepted_for_reference': False,
                     'work_completed': ['frozen_identity_bound', 'structured_source_preparation'],
                     'remaining': ['complete_linked_source_meaning', 'independent_interpretation_review', 'exact_release_review']}
                    for x in selected]
    outputs = {'input-bindings.json': bindings, 'inventory-accounting.json': accounting,
               'offering-ledger.json': ledger, 'selected-canonical.json': selected,
               'source-excerpts.json': exact_quotes(pages, spec), 'CMS-native-deductible.json': cms,
               'structured-comparison.json': {**comparison, 'condition_logic': spec['condition_logic'],
                   'structured_observations': spec['structured_observations'],
                   'condition_family_review': spec['condition_family_review'],
                   'interpretation_review_complete': False},
               'proposed-dispositions.json': dispositions}
    outputs['native-lineage-validation.json'] = lineage
    dictionary = load(repository / BASE / 'build-r1/field-dictionary.json')
    names = {'pbp_d_inn_deduct_yn', 'pbp_d_inn_deduct_partb_yn', 'pbp_d_inn_deduct_amt',
             'pbp_d_inn_deduct_bens', 'pbp_d_inn_deduct_m_yn', 'pbp_d_inn_deduct_m_cats',
             'pbp_d_inn_deduct_nm_yn', 'pbp_d_oon_deduct_yn', 'pbp_d_comb_deduct_yn'}
    outputs['CMS-dictionary-context.json'] = {key: dictionary[key] for key in ('source', 'member', 'sha256')}
    outputs['CMS-dictionary-context.json']['fields'] = [r for r in dictionary['fields'] if r['name'] in names]
    for binding in bindings:
        if file_sha(repository / binding['path']) != binding['sha256']:
            raise PilotError('Input changed during preparation')
    if file_sha(Path(__file__)) != implementation_sha:
        raise PilotError('Producer changed during execution')
    outputs['validation.json'] = {'passed': True, 'scope': 'technical preparation only',
        'checks': ['all_input_hashes', 'complete_frozen_inventory_digest', 'full_392570_census',
                   'whole_offering_4675_and_missing16', 'exact_tranche_allowlist', 'source_quote_line_hashes',
                   'full_native_CMS_schedule_retained', 'nominal_decimal_and_six_category_components',
                   'sealed_comparator_insufficient', 'no_status_or_acceptance_promotion',
                   'all_selected_proposition_siblings_retained', 'exact_prior_r4_allowlist',
                   'exact_native_lineage_and_source_quote_reconstruction'],
        'implementation_sha256': implementation_sha, 'spec_canonical_sha256': digest(spec),
        'output_sha256': {name: digest(value) for name, value in outputs.items()},
        'accepted_for_reference': False, 'full_pilot_complete': False}
    return outputs


def write_outputs(output, values, repository):
    resolved = output.resolve()
    if resolved.is_relative_to((repository / BASE).resolve()):
        raise PilotError('Output cannot be a sealed L03 parent')
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    for name, value in values.items():
        with (output / name).open('x') as stream:
            json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
            stream.write('\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository', type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument('--spec', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    repository = args.repository.resolve()
    spec = load(args.spec or repository / PACKET / 'pilot-spec.json')
    values = build(repository, spec)
    write_outputs(args.output, values, repository)
    print(json.dumps({'passed': True, 'selected': len(values['selected-canonical.json']),
                      'new_accepted': 0, 'full_pilot_complete': False}))


if __name__ == '__main__':
    main()
