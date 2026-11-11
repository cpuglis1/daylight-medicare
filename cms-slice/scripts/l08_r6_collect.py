"""Acquire pinned CMS releases, all five enrollment tables, and complete API comparisons."""
import csv
import gzip
import json
from collections import Counter
from pathlib import Path

from l08_r6_common import BASE, REFERENCE_DATE, assert_open, csv_encoding, packed, write
from l08_r6_http import CMSClient, collect


def release(selection, title):
    candidates = [d for d in selection['datasets'] if d['title'].startswith(title + ' : ')
                  and '2026-' in d['title'] and d.get('modified', '') <= REFERENCE_DATE]
    if not candidates:
        raise ValueError('No eligible dated 2026 release: ' + title)
    chosen = max(candidates, key=lambda d: d['title'].split(' : ')[1])
    if chosen['title'].split(' : ')[1] > REFERENCE_DATE:
        raise ValueError('Future release')
    apis = [x for x in chosen['distribution'] if x.get('format') == 'API' and x.get('description') != 'latest']
    if len(apis) != 1:
        raise ValueError('No unique version-specific CMS endpoint')
    return chosen, apis[0]


def main():
    assert_open()
    client = CMSClient()
    selection = json.loads((BASE / 'catalog-selection.json').read_text())
    releases, sources = {}, {}
    for key, title in [('enrollment', 'Medicare Fee-For-Service Public Provider Enrollment'),
                       ('optout', 'Opt Out Affidavits')]:
        chosen, api = release(selection, title)
        viewer, vr = client.json(api['accessURL'].rsplit('/data', 1)[0] + '/data-viewer?size=1')
        resources, rr = client.json(api['resourcesAPI'])
        dictionary, dr = client.json(api['describedBy']['downloadURL'])
        meta = viewer['meta']
        if not meta.get('success') or not isinstance(meta.get('total_rows'), int):
            raise ValueError('Missing publisher row total')
        releases[key] = {'catalog_entry': chosen, 'api': api, 'viewer': viewer,
                         'viewer_receipt': vr, 'resources': resources, 'resources_receipt': rr,
                         'dictionary': dictionary, 'dictionary_receipt': dr}
        write(BASE / 'releases.json', releases)
        primary = 'https://data.cms.gov' + meta['data_file_url']
        for resource in resources['data']:
            name = resource['name']
            url = resource['downloadURL']
            if key == 'enrollment':
                kinds = [('Additional NPIs Sub-File Q4 2026', 'additional_npis'),
                         ('Reassignment Sub-File Q4 2026', 'reassignment'),
                         ('Address Sub-File Q4 2026', 'practice_locations'),
                         ('Secondary Specialty Sub-File Q4 2026', 'secondary_specialty')]
                kind = next((k for n, k in kinds if name == n), None)
                if url == primary:
                    kind = 'enrollment'
            else:
                kind = 'optout' if url == primary else None
            if kind or ('Dictionary' in name or 'Methodology' in name) and url.endswith('.pdf'):
                path, receipt = client.download(url, resource['fileSize'],
                    meta['data_file_meta_data'].get('csvFileSHA1') if url == primary else None)
                source_key = kind or key + ('_dictionary_pdf' if 'Dictionary' in name else '_methodology_pdf')
                sources[source_key] = {'resource': resource, 'receipt': receipt,
                                       'path': str(path), 'release_family': key}
                write(BASE / 'sources.json', sources)
                print('Retained ' + source_key, flush=True)
        if key == 'enrollment':
            filters = {'STATE_CD': 'FL'}
            sort = 'ENRLMT_ID'
            expected = None  # compared to the full national CSV after pagination
        else:
            filters = None
            sort = 'NPI'
            expected = meta['total_rows']

        def row_check(r):
            if set(r) != set(meta['headers']):
                raise ValueError('Unexpected source schema')
            if key == 'enrollment' and r['STATE_CD'] != 'FL':
                raise ValueError('CMS ignored Florida filter')

        rows, accounting = collect(client, api['accessURL'], sort=sort,
                                   expected_rows=expected, filters=filters, row_check=row_check)
        # Independent, all-field API-versus-publisher-file comparison. No ID-only
        # reconciliation or deduplication can hide missing/mutated source records.
        csv_counts = Counter()
        n = 0
        encoding = csv_encoding(Path(sources[key]['path']))
        with open(sources[key]['path'], encoding=encoding, newline='') as f:
            reader = csv.DictReader(f)
            if set(reader.fieldnames) != set(meta['headers']):
                raise ValueError('CSV/API schemas differ')
            for r in reader:
                n += 1
                if None in r:
                    raise ValueError('Malformed CSV source row')
                if key == 'optout' or r['STATE_CD'] == 'FL':
                    csv_counts[packed(r)] += 1
        if n != meta['total_rows']:
            raise ValueError('Publisher CSV count differs from API metadata')
        api_counts = Counter(packed(r) for r in rows)
        if csv_counts != api_counts:
            raise ValueError('Whole-population API/CSV field mismatch')
        accounting.update(national_csv_rows=n, csv_encoding=encoding, csv_comparison_rows=sum(csv_counts.values()),
                          whole_population_all_field_multiset_comparison_passed=True)
        with gzip.open(BASE / (key + '-api.jsonl.gz'), 'wt', encoding='utf-8') as out:
            for r in rows:
                out.write(packed(r) + '\n')
        write(BASE / (key + '-api-accounting.json'), accounting)
        print(key + ': API/CSV agree for ' + str(len(rows)) + ' records', flush=True)


if __name__ == '__main__':
    main()
