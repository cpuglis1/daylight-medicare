"""Correct static catalog path reconstruction and bound workbook claims.

No SAS/VBA is executed. This candidate changes static research metadata only;
runtime transformations and semantic authority require separate exact review.
"""
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import itertools
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
PACKET = ROOT / 'docs/data/l03-ma-benefits-2026-11-02-whole-offering-r12'
BASE = PACKET / 'native-format-authority-research-r1'
OUT = PACKET / 'native-format-catalog-correction-r2'
sha = lambda body: hashlib.sha256(body).hexdigest()


def main():
    if OUT.exists():
        raise ValueError('Preserve earlier revisions.')
    freeze = json.loads((BASE / 'FREEZE_NATIVE_FORMAT_AUTHORITY_RESEARCH_R1.json').read_text())
    for entry in freeze['files']:
        body = (BASE / entry['path']).read_bytes()
        assert sha(body) == entry['sha256'] and len(body) == entry['bytes']
    old_catalog = json.loads((BASE / 'OFFICIAL_SIMPLE_CATS_CROSSWALK_CATALOG.json').read_text())
    maps = {row['DSNAME'].lower(): row for row in json.loads(
        (BASE / 'extracted-cms-code/PARTC_AUTOMAP.TXT').read_text())['DATASETS']}
    inverse = defaultdict(set)
    rename_lines = defaultdict(list)
    for number, line in enumerate((BASE / 'extracted-cms-code/SHORTEN.TXT').read_text().splitlines(), 1):
        names = re.findall(r'"""([^\"]+)""', line)
        if len(names) == 2:
            inverse[names[1]].add(names[0])
            rename_lines[names[1]].append(number)
    ambiguous = {key: sorted(value) for key, value in inverse.items() if len(value) > 1}
    catalog = []
    for old in old_catalog['branches']:
        source = BASE / old['source_file']
        assert sha(source.read_bytes()) == old['module_sha256']
        aliases = {alias.lower(): table.lower() for table, alias in re.findall(
            r'jsonlib\.(\w+)\s+AS\s+(\w+)', source.read_text(), re.I)}
        table_name = aliases.get(old['sas_source_table_alias'].lower(), old['sas_source_table_alias'].lower())
        table = maps[table_name]
        variables = [v for v in table['VARIABLES'] if v['NAME'].lower() == old['native_leaf_field'].lower()]
        assert len(variables) == 1
        variable = variables[0]
        parts = variable['PATH'].strip('/').split('/')
        assert parts[0] == 'root'
        possibilities = [sorted(inverse.get(part, {part})) for part in parts[1:]]
        paths = ['/' + '/'.join(path) for path in itertools.product(*possibilities)]
        row = {k: value for k, value in old.items() if k != 'sas_automap_native_path'}
        row.update({'historical_r1_record_sha256': sha(json.dumps(old, sort_keys=True,
            separators=(',', ':'), ensure_ascii=False).encode()),
            'historical_r1_single_inverse_path': old['sas_automap_native_path'],
            'sas_automap_table': table['DSNAME'], 'sas_automap_variable': variable,
            'original_native_path_alternatives': paths,
            'shorten_line_refs': {part: rename_lines[part] for part in parts[1:] if part in inverse},
            'ambiguous_shortened_segments': {part: sorted(inverse[part]) for part in parts[1:] if len(inverse.get(part, {part})) > 1},
            'path_reconstruction_status': 'all_inverse_paths_preserved',
            'single_inverse_is_authority': False,
            'scope_limit': 'An exact alternative path/category/type match remains a candidate. Complete component discrimination and downstream transformations are separately reviewed.'})
        catalog.append(row)
    assert len(catalog) == 939
    path_changes = [{'branch_id': row['evidence_id'],
        'before': row['historical_r1_single_inverse_path'],
        'after_alternatives': row['original_native_path_alternatives']}
        for row in catalog if row['original_native_path_alternatives'] != [row['historical_r1_single_inverse_path']]]

    corrected = {}
    changed_rows = []
    counts = {}
    for packet, filename in [
        ('residual', 'CURRENT_504_OBSERVATION_STATIC_BRANCH_PROBE.json'),
        ('clinical', 'CLINICAL_392_STATIC_BRANCH_PROBE.json'),
        ('dental', 'DENTAL_327_NATIVE_OBSERVATION_STATIC_BRANCH_PROBE.json')]:
        original = json.loads((BASE / filename).read_text())
        rows = []
        for ordinal, old in enumerate(original['records'], 1):
            generic = '/' + '/'.join(part for part in old['pointer'].split('/') if part and not part.isdigit())
            context = old.get('native_service_context', old.get('native_enclosing_scope', {}))
            matches = [branch for branch in catalog if generic in branch['original_native_path_alternatives']
                and context.get('categoryCode') in branch['category_codes']
                and (branch['category_type_id'] is None or context.get('categoryTypeId') == branch['category_type_id'])]
            ids = [branch['evidence_id'] for branch in matches]
            assert set(old['exact_path_category_type_branch_ids']) <= set(ids)
            row = {k: value for k, value in old.items() if k not in ['exact_path_category_type_branch_ids', 'status']}
            row.update({'historical_r1_exact_branch_ids': old['exact_path_category_type_branch_ids'],
                'exact_all_inverse_path_category_type_branch_ids': ids,
                'ambiguous_inverse_branch_ids': [branch['evidence_id'] for branch in matches if branch['ambiguous_shortened_segments']],
                'status': 'literal_source_candidate_requires_complete_projection_review' if ids else
                    'no_exact_simple_CATS_candidate;other_source_routes_not_excluded',
                'decoded_meaning': None, 'accepted_for_reference': False})
            rows.append(row)
            if old['exact_path_category_type_branch_ids'] != ids:
                changed_rows.append({'packet': packet, 'record_ordinal': ordinal,
                    'pointer': old['pointer'], 'observation_id': old.get('observation_id'),
                    'before': old['exact_path_category_type_branch_ids'], 'after': ids})
        corrected[filename] = {'schema': 'daylight.cms-static-branch-probe.v2',
            'historical_input_path': str((BASE / filename).relative_to(ROOT)),
            'historical_input_sha256': sha((BASE / filename).read_bytes()),
            'records': rows, 'total_observations': len(rows), 'decoded_meanings_assigned': 0,
            'canonical_changes': 0, 'new_acceptance': False}
        counts[packet] = {'before': sum(bool(row['exact_path_category_type_branch_ids']) for row in original['records']),
            'after': sum(bool(row['exact_all_inverse_path_category_type_branch_ids']) for row in rows),
            'total': len(rows)}
    assert counts == {'residual': {'before': 10, 'after': 10, 'total': 504},
        'clinical': {'before': 144, 'after': 147, 'total': 392},
        'dental': {'before': 36, 'after': 36, 'total': 327}}
    assert len(changed_rows) == 3 and all(row['packet'] == 'clinical' for row in changed_rows)

    native_path = ROOT / 'docs/data/l03-ma-benefits-2026-11-01-whole-offering-r11/source-preparation/generated-r2/CMS-native-member.json'
    native_bytes = native_path.read_bytes()
    # Reasoned replay of the literal string precondition only. This is not a
    # workbook run or a replacement of the retained source with reformatted data.
    normalized = ''.join(line.replace(' : ', ':').replace('\n', '').replace('\r', '')
        .replace('\t', '').replace(': ', ':') for line in native_bytes.decode().splitlines())
    needles = ['"contractId":"H5652","planId":"002","segmentId":' + suffix
        for suffix in ['0', '"0', '"000']]
    assert not any(needle in normalized for needle in needles)
    workbook = {'schema': 'daylight.literal-workbook-input-precondition.v1',
        'source_path': str((BASE / 'extracted-cms-vba/S4_PBP.bas').relative_to(ROOT)),
        'source_sha256': sha((BASE / 'extracted-cms-vba/S4_PBP.bas').read_bytes()),
        'native_path': str(native_path.relative_to(ROOT)), 'native_sha256': sha(native_bytes),
        'preprocessing_source_lines': [252, 253], 'lookup_source_lines': [288, 289],
        'tested_lookup_fragments': needles, 'literal_concatenated_lookup_found': False,
        'actual_workbook_executed': False, 'original_json_reformatted_or_replaced': False,
        'interpretation': 'The source supplies conditional POS extraction intent; this does not prove that its literal file reader accepts the retained space-indented native member. The 63 semantic object selections are not a successful workbook execution receipt.',
        'structural_POS_intent_controls': 63, 'global_boOutOfNetwork_decoder_established': False,
        'new_acceptance': False}
    OUT.mkdir()

    def write(name, value):
        with (OUT / name).open('x') as handle:
            json.dump(value, handle, indent=2); handle.write('\n')

    write('CORRECTED_SIMPLE_CATS_CATALOG.json', {'schema': 'daylight.cms-2026-oopc-static-branch-catalog.v2',
        'parent_catalog_sha256': sha((BASE / 'OFFICIAL_SIMPLE_CATS_CROSSWALK_CATALOG.json').read_bytes()),
        'branches': catalog, 'inverse_ambiguities': ambiguous, 'global_decoder': False,
        'downloaded_programs_executed': False, 'new_acceptance': False})
    for name, value in corrected.items():
        write(name, value)
    write('WORKBOOK_INPUT_PRECONDITION.json', workbook)
    write('CORRECTION_ACCOUNTING.json', {'schema': 'daylight.cms-static-catalog-corrections.v1',
        'observed_at': datetime.now(timezone.utc).isoformat(), 'original157_frozen_members_unchanged': True,
        'catalog_branches_before_after': [939, 939], 'all_inverse_paths_retained': True,
        'exact_changed_catalog_path_records': path_changes,
        'ambiguous_aliases': ambiguous, 'exact_changed_probe_rows': changed_rows,
        'candidate_match_counts': counts, 'original_denominator_before_after': [4675, 4675],
        'decoded_meanings_assigned': 0, 'canonical_adoptions': 0, 'new_acceptance': False,
        'whole_offering_complete': False, 'consumer_release': False,
        'producer_script_path': str(Path(__file__).relative_to(ROOT)),
        'producer_script_sha256': sha(Path(__file__).read_bytes())})
    print(json.dumps({'branches': len(catalog), 'changed_probe_records': len(changed_rows),
        'candidate_match_counts': counts, 'decoded_meanings_assigned': 0}))


if __name__ == '__main__':
    main()
