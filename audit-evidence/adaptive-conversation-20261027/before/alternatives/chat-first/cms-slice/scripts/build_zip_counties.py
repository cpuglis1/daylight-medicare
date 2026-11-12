#!/usr/bin/env python3
"""Build local ZIP/county reference data from a complete HUD county-ZIP workbook.

Do not use an EUC/disaster subset: it can omit another county for the same ZIP.
Every county row is retained, including cross-state and zero-residential rows.
No address ratios select a county for a person. Runtime does not call a geocoder.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import re
from xml.etree import ElementTree as ET
from zipfile import ZipFile

NS = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'


def workbook_rows(path):
    with ZipFile(path) as archive:
        strings = []
        if 'xl/sharedStrings.xml' in archive.namelist():
            for _, item in ET.iterparse(archive.open('xl/sharedStrings.xml'), events=['end']):
                if item.tag == NS + 'si':
                    strings.append(''.join(item.itertext()))
                    item.clear()
        for _, row in ET.iterparse(archive.open('xl/worksheets/sheet1.xml'), events=['end']):
            if row.tag != NS + 'row':
                continue
            values = {}
            for cell in row.findall(NS + 'c'):
                column = re.match('[A-Z]+', cell.attrib['r']).group()
                value = cell.find(NS + 'v')
                text = value.text if value is not None else ''.join(cell.find(NS + 'is').itertext()) if cell.find(NS + 'is') is not None else ''
                values[column] = strings[int(text)] if cell.get('t') == 's' else text
            yield values
            row.clear()


def build(crosswalk, counties, source_url, period, reviewed_on):
    with counties.open(encoding='utf-8-sig', newline='') as stream:
        names = {row['GEOID']: (row['NAME'], row['USPS']) for row in csv.DictReader(stream, delimiter='|')}
    rows = iter(workbook_rows(crosswalk))
    header = {name: column for column, name in next(rows).items()}
    if not {'COUNTY', 'ZIP', 'USPS_ZIP_PREF_STATE'} <= header.keys():
        raise ValueError('Expected a complete HUD COUNTY_ZIP workbook')
    zips = {}
    for row in rows:
        county, zipcode = (str(row.get(header[k], '')).zfill(5) for k in ['COUNTY', 'ZIP'])
        if not re.fullmatch(r'\d{5}', county) or not re.fullmatch(r'\d{5}', zipcode):
            raise ValueError('Invalid county/ZIP row; refusing an incomplete map')
        name, state = names.get(county, (f'County code {county}', row.get(header['USPS_ZIP_PREF_STATE'], '')))
        zips.setdefault(zipcode, {})[county] = [county, name, state]
    if len(zips) < 30000:
        raise ValueError('Expected the complete national crosswalk, not a county subset')
    return {'period': period, 'reviewed_on': reviewed_on, 'source_url': source_url,
            'method': 'All county rows retained; ratios never choose a county.',
            'sha256': {'crosswalk': hashlib.sha256(crosswalk.read_bytes()).hexdigest(), 'counties': hashlib.sha256(counties.read_bytes()).hexdigest()},
            'zips': {z: list(values.values()) for z, values in sorted(zips.items())}}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--crosswalk', type=Path, required=True)
    parser.add_argument('--counties', type=Path, required=True)
    parser.add_argument('--source-url', required=True)
    parser.add_argument('--period', required=True)
    parser.add_argument('--reviewed-on', required=True)
    parser.add_argument('--output', type=Path, default=Path(__file__).resolve().parents[1] / 'apps/chat/zip-counties.json')
    args = parser.parse_args()
    data = build(args.crosswalk, args.counties, args.source_url, args.period, args.reviewed_on)
    args.output.write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':')) + '\n')
    print(f'{len(data["zips"])} ZIPs, {sum(len(v)>1 for v in data["zips"].values())} with multiple counties')
    print('34102:', data['zips'].get('34102'))
