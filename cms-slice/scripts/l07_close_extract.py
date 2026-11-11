#!/usr/bin/env python3
"""Extract exact NPI/address observations from the dated carrier PDF, by column.

This collects evidence only. It does not import the carrier's network, costs,
hours, services or preferred status into any CMS plan.
"""
from collections import Counter
import json
from pathlib import Path
import re
import subprocess
import tempfile
import xml.etree.ElementTree as ET

from l04_acquire import write
from l07_acquire import file_hash

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'docs/data/l07-pharmacy-networks-2026-10-27'
OUT = BASE / 'closeout-r1'
NS = {'x': 'http://www.w3.org/1999/xhtml'}


def norm(value):
    words = {'ROAD':'RD','BOULEVARD':'BLVD','STREET':'ST','DRIVE':'DR','TRAIL':'TRL',
             'LANE':'LN','PARKWAY':'PKWY','PLAZA':'PLZ','AVENUE':'AVE','HIGHWAY':'HWY',
             'COURT':'CT','CIRCLE':'CIR','TERRACE':'TER','BYPASS':'BYP','ROOM':'RM',
             'SAINT':'ST','FORT':'FT','HARBOUR':'HARBOR','NORTH':'N','SOUTH':'S','EAST':'E','WEST':'W',
             'SUITE':'STE','NORTHEAST':'NE','NORTHWEST':'NW','SOUTHEAST':'SE','SOUTHWEST':'SW'}
    value = value.upper()
    for word, abbr in words.items(): value = re.sub(r'\b'+word+r'\b', abbr, value)
    return re.sub('[^A-Z0-9]', '', value)


def extract():
    if (OUT/'SEALED').exists():raise ValueError('Closeout evidence is sealed')
    sources = json.loads((OUT / 'sources.json').read_text())
    source = next(r for r in sources if r['label']=='2026 Florida AmeriHealth pharmacy directory')
    codes = next(r for r in sources if r['label']=='Census official county FIPS reference')
    county_codes = {}
    for line in (ROOT / codes['path']).read_text().splitlines()[1:]:
        s = line.split('|')
        if s[0]=='FL': county_codes[norm(s[4])] = s[1]+s[2]
    exceptions = json.loads((BASE / 'location-build-r3/exceptions.json').read_text())
    targets = {r['npi'] for r in exceptions}
    observations, county, page_index = [], None, 0
    with tempfile.TemporaryDirectory() as temp:
        xml = Path(temp) / 'words.xml'
        subprocess.run(['pdftotext','-bbox-layout',str(ROOT/source['path']),str(xml)],check=True,stderr=subprocess.DEVNULL)
        for _, page in ET.iterparse(xml, events=['end']):
            # Iterate only complete page elements; the document is small enough
            # to retain their XML until the parser closes the page.
            if page.tag != '{'+NS['x']+'}page': continue
            page_index += 1
            columns = [[], [], []]
            for line in page.findall('.//x:line', NS):
                # Poppler sometimes merges a line across two printed columns.
                # Partition the words, never the full line, by printed column.
                pieces = [[], [], []]
                for word in line.findall('x:word', NS):
                    x, y = float(word.attrib['xMin']), float(word.attrib['yMin'])
                    if not 70 <= y <= 724: continue
                    pieces[0 if x < 210 else 1 if x < 405 else 2].append(word)
                for c, words in enumerate(pieces):
                    if not words: continue
                    bbox = [min(float(w.attrib[k]) for w in words) for k in ['xMin','yMin']]
                    bbox += [max(float(w.attrib[k]) for w in words) for k in ['xMax','yMax']]
                    columns[c].append({'text':' '.join(''.join(w.itertext()) for w in words),'bbox':bbox})
            for ci, lines in enumerate(columns,1):
                lines.sort(key=lambda r:(r['bbox'][1],r['bbox'][0]))
                for i, line in enumerate(lines):
                    header = re.search(r'^(.+? COUNTY), ([A-Z]{2})(?:\s|$)', line['text'])
                    if header:
                        county = {'text':line['text'],'county_label':header[1],'state':header[2],
                                  'page':page_index,'column':ci,'bbox':line['bbox']}
                    n = re.fullmatch(r'NPI:\s*(\d{10})',line['text'])
                    if not n or n[1] not in targets: continue
                    following = lines[i+1:i+9]
                    # Narrow columns sometimes put the ZIP alone on the next
                    # printed line. Preserve both source boxes in one city field.
                    for k in range(len(following)-1):
                        first,second=following[k:k+2]
                        if re.fullmatch(r'.+, [A-Z]{2}',first['text']) and re.fullmatch(r'\d{5}(?:\d{4}|-\d{4})?',second['text']):
                            merged={'text':first['text']+' '+second['text'],
                                'bbox':[min(first['bbox'][0],second['bbox'][0]),first['bbox'][1],
                                        max(first['bbox'][2],second['bbox'][2]),second['bbox'][3]],
                                'wrapped_source_lines':[first,second]}
                            following=following[:k]+[merged]+following[k+2:]
                            break
                    city_position = next((k for k,r in enumerate(following) if re.fullmatch(r'.+, [A-Z]{2} \d{5}(?:\d{4}|-\d{4})?',r['text'])),None)
                    if city_position is None: continue
                    city_line = following[city_position]['text']
                    city, state, zipcode = re.fullmatch(r'(.+), ([A-Z]{2}) (\d{5}(?:\d{4}|-\d{4})?)',city_line).groups()
                    street_lines = following[:city_position]
                    if not street_lines or not re.match(r'(?:#\s*)?\d',street_lines[0]['text']): continue
                    phone_line = following[city_position+1] if city_position+1<len(following) else None
                    phone = phone_line['text'] if phone_line and re.fullmatch(r'\(?\d{3}\)?[ -]\d{3}-\d{4}',phone_line['text']) else None
                    county_fips = county_codes.get(norm(county['county_label'])) if county and county['state']=='FL' and county['page']==page_index else None
                    observations.append({'npi':n[1],'page':page_index,'column':ci,'npi_line':line,
                        'street_lines':street_lines,'city_line':following[city_position],
                        'phone_line':phone_line if phone else None,'phone':phone,
                        'street':' '.join(r['text'] for r in street_lines),'city':city,'state':state,'postal_code':zipcode,
                        'county_header':county,'county_fips':county_fips,'source':source,
                        'directory_updated_date':'2026-09-21','document_plan':'H6378-001',
                        'use':'Identity/address/county corroboration only; no plan-network inference.'})
            page.clear()
    write(OUT/'directory-observations.json',observations)
    result = {'PDF_pages':page_index,'observations':len(observations),'distinct_exception_NPIs':len({r['npi'] for r in observations}),
              'counties':dict(Counter(r['county_fips'] or 'unresolved' for r in observations)),
              'source_sha256':source['sha256'],'code_sha256':file_hash(Path(__file__))}
    write(OUT/'extraction.json',result)
    print(json.dumps(result,indent=2))


if __name__ == '__main__': extract()
