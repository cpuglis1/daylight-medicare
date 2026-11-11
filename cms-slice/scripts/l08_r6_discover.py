"""Retain the official CMS release catalog and identify dated enrollment/opt-out resources."""
import json
from l08_r6_common import BASE, assert_open, write
from l08_r6_http import CMSClient


def main():
    assert_open()
    catalog, receipt = CMSClient().json('https://data.cms.gov/data.json')
    titles = {'Medicare Fee-For-Service Public Provider Enrollment', 'Opt Out Affidavits'}
    datasets = [d for d in catalog.get('dataset', []) if any(
        d.get('title') == t or d.get('title', '').startswith(t + ' : ') for t in titles)]
    series = [d for d in catalog.get('datasetSeries', []) if d.get('title') in titles]
    write(BASE / 'catalog-selection.json', {'catalog_receipt': receipt,
                                           'datasets': datasets, 'series': series})
    for d in series:
        print(json.dumps({'series': d}, ensure_ascii=False), flush=True)
    for d in datasets:
        print(json.dumps(d, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
