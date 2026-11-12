"""Locate exact AUTOMAP variable references beyond the simple-CATS catalog.

Static text census only: it neither executes the downloaded programs nor judges
guards, runtime behavior, enum meanings or complete mapping authority.
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
RESEARCH = PACKET / 'native-format-authority-research-r1'
OUT = PACKET / 'native-format-remainder-census-r1'
sha = lambda data: hashlib.sha256(data).hexdigest()


def main():
    if OUT.exists():
        raise ValueError('Preserve earlier census revisions.')
    bindings = []

    def read(path):
        data = path.read_bytes()
        bindings.append({'path': str(path.relative_to(ROOT)), 'sha256': sha(data)})
        return data

    inverse = defaultdict(set)
    for line in read(RESEARCH / 'extracted-cms-code/SHORTEN.TXT').decode().splitlines():
        names = re.findall(r'"""([^\"]+)""', line)
        if len(names) == 2:
            inverse[names[1]].add(names[0])
    automap = json.loads(read(RESEARCH / 'extracted-cms-code/PARTC_AUTOMAP.TXT'))
    variables = defaultdict(list)
    for table in automap['DATASETS']:
        for variable in table['VARIABLES']:
            parts = variable['PATH'].strip('/').split('/')
            assert parts[0] == 'root'
            paths = ['/' + '/'.join(path) for path in itertools.product(
                *[sorted(inverse.get(part, {part})) for part in parts[1:]])]
            for path in paths:
                variables[path].append({'table': table['DSNAME'], 'field': variable['NAME'],
                    'automap_variable': variable, 'all_inverse_path_alternatives': paths})

    # This includes token occurrences in comments: they remain mere text leads.
    uses = defaultdict(list)
    for module in sorted((RESEARCH / 'extracted-cms-code').glob('JSON_IMPORT_PBP*.SAS')):
        text = read(module).decode()
        aliases = {alias.lower(): table.lower() for table, alias in
            re.findall(r'jsonlib\.(\w+)\s+AS\s+(\w+)', text, re.I)}
        for line_number, line in enumerate(text.splitlines(), 1):
            for match in re.finditer(r'\b(\w+)\.(\w+)\b', line):
                alias, field = match.groups()
                table = aliases.get(alias.lower())
                if table:
                    entry = {'module': str(module.relative_to(ROOT)),
                        'module_sha256': sha(module.read_bytes()), 'line': line_number,
                        'source_text': line, 'table_alias': alias, 'field_token': field}
                    if entry not in uses[(table, field.lower())]:
                        uses[(table, field.lower())].append(entry)

    native_path = ROOT / 'docs/data/l03-ma-benefits-2026-11-01-whole-offering-r11/source-preparation/generated-r2/CMS-native-member.json'
    native = json.loads(read(native_path))

    def at(pointer):
        value = native
        for part in pointer.strip('/').split('/'):
            value = value[int(part)] if isinstance(value, list) else value[part]
        return value

    records = []
    for packet, filename in [
        ('residual', 'CURRENT_504_OBSERVATION_STATIC_BRANCH_PROBE.json'),
        ('clinical', 'CLINICAL_392_STATIC_BRANCH_PROBE.json'),
        ('dental', 'DENTAL_327_NATIVE_OBSERVATION_STATIC_BRANCH_PROBE.json')]:
        probes = json.loads(read(RESEARCH / filename))['records']
        for ordinal, probe in enumerate(probes, 1):
            pointer = probe['pointer']
            raw = probe['raw'] if 'raw' in probe else probe['native_raw']
            assert at(pointer) == raw
            generic = '/' + '/'.join(part for part in pointer.split('/') if part and not part.isdigit())
            mapped = variables.get(generic, [])
            exact_references = []
            for variable in mapped:
                exact_references.append({**variable, 'all_module_token_references':
                    uses.get((variable['table'].lower(), variable['field'].lower()), [])})
            simple = probe['exact_path_category_type_branch_ids']
            token_count = sum(len(entry['all_module_token_references']) for entry in exact_references)
            status = ('existing_simple_CATS_catalog_candidate' if simple else
                'other_module_token_lead_requires_guard_and_projection_review' if token_count else
                'AUTOMAP_path_present_without_module_token_reference' if mapped else
                'no_exact_AUTOMAP_path_in_retained_Part_C_model')
            records.append({'packet': packet, 'probe_record_ordinal': ordinal,
                'observation_id': probe.get('observation_id'), 'canonical_id': probe.get('canonical_id'),
                'canonical_source_assessment_bindings': probe.get('canonical_source_assessment_bindings'),
                'pointer': pointer, 'raw': raw, 'raw_replayed_against_original': True,
                'generic_path': generic, 'original_simple_CATS_branch_ids': simple,
                'exact_AUTOMAP_variables_and_text_leads': exact_references,
                'status': status, 'decoded_meaning': None,
                'semantic_mapping_established_by_census': False})
    assert len(records) == 1223
    OUT.mkdir()
    payload = {'schema': 'daylight.cms-native-source-reference-census.v1',
        'observed_at': datetime.now(timezone.utc).isoformat(), 'inputs': bindings,
        'module_count': 22, 'records': records,
        'counts': {packet: dict(Counter(row['status'] for row in records if row['packet'] == packet))
            for packet in ['residual', 'clinical', 'dental']},
        'scope': 'Exact native-path/AUTOMAP table+field token leads across all 22 retained modules. A token reference is not an executable mapping or evidence of semantic agreement.',
        'unmatched_catalog_is_not_authority_absence': True,
        'source_programs_executed': False, 'new_acceptance': False,
        'original_canonical_changes': 0, 'consumer_release': False}
    with (OUT / 'SOURCE_REFERENCE_CENSUS.json').open('x') as handle:
        json.dump(payload, handle, indent=2); handle.write('\n')
    print(json.dumps({'records': len(records), 'counts': payload['counts']}))


if __name__ == '__main__':
    main()
