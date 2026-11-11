"""Fixed synthetic source grid; all 25 OIR Collier ZIPs, not an all-market census."""
import json
import time
from urllib.parse import urlencode
from l10_acquire import collect, DEST

AGES = ['0-64', '65', '70', '75', '80']


def main():
    receipt = json.loads((DEST / 'choices-collier-zips.json').read_text())
    zips = json.loads((DEST / 'raw' / receipt['sha256']).read_text())
    assert len(zips) == 25 and all(z['countY_ID'] == 11 for z in zips)
    index = []
    for z in zips:
        for age in AGES:
            for sex in ['f', 'm']:
                for tobacco in ['o', 's']:
                    inputs = {'age': age, 'gender': sex, 'smoker': tobacco,
                              'zipCode': z['zipcodE_DS'], 'insuranceType': '0',
                              'plans': 'A,B,C,D,F,G,K,L,M,N,F*,G*',
                              'effectiveDate': '11/01/2026', 'groupCode': 'B'}
                    sid = f"choices-{z['zipcodE_DS']}-{age}-{sex}-{tobacco}"
                    url = 'https://choices.floir.gov/mcws/api/MCWSSearch/GetSearchResults?' + urlencode(inputs)
                    existed = (DEST / (sid + '.json')).exists()
                    if not existed:
                        time.sleep(1)
                    record = collect(sid, url, 'illustrative-2026-request', inputs)
                    payload = json.loads((DEST / 'raw' / record['sha256']).read_text())
                    if set(payload) != {'rates', 'rateDisplays'}:
                        raise ValueError('Source schema changed; stop')
                    if not all(isinstance(payload[k], list) for k in payload):
                        raise ValueError('Source schema changed; stop')
                    index.append({'receipt': sid + '.json', 'rates': len(payload['rates']),
                                  'displays': len(payload['rateDisplays'])})
                    if len(index) % 20 == 0:
                        print(json.dumps({'captures': len(index), 'expected': 500,
                                          'last_zip': z['zipcodE_DS']}), flush=True)
    (DEST / 'choices-index.json').write_text(json.dumps({
        'scope': '500 fixed synthetic scenarios: all 25 ZIPs listed by OIR for Collier, 5 ages/classes, 2 sexes, 2 tobacco states, all 12 variants, both group/individual and SELECT/standard. Requested November 1, 2026; actual filed effective dates, form and current-sale status unknown. Not a complete product or rate universe.',
        'captures': index}, indent=2, sort_keys=True) + '\n')


if __name__ == '__main__':
    main()
