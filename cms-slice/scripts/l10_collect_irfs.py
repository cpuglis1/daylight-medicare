"""Read-only IRFS metadata through its published search and detail endpoints.

Uses the ordinary anonymous session/CSRF mechanism. Never calls document,
challenge, comment or request endpoints. Restricted filings are not opened.
"""
from datetime import datetime, timezone
import hashlib
import http.cookiejar
import json
from pathlib import Path
import re
import time
import calendar
import argparse
from urllib.parse import urlencode
from urllib.request import build_opener, HTTPCookieProcessor, Request

from l10_acquire import DEST


class Search:
    def __init__(self):
        self.opener = build_opener(HTTPCookieProcessor(http.cookiejar.CookieJar()))
        with self.opener.open('https://irfssearch.floir.gov/', timeout=45) as r:
            html = r.read(200_000).decode()
        self.token = re.search(r'name="__RequestVerificationToken"[^>]*value="([^"]+)"', html).group(1)

    def post(self, source_id, endpoint, fields):
        target = DEST / (source_id + '.json')
        if target.exists():
            receipt = json.loads(target.read_text())
            assert receipt['inputs'] == fields
            raw = (DEST / 'raw' / receipt['sha256']).read_bytes()
            assert hashlib.sha256(raw).hexdigest() == receipt['sha256']
            return json.loads(raw)
        time.sleep(1)
        url = 'https://irfssearch.floir.gov' + endpoint
        body = urlencode({**fields, '__RequestVerificationToken': self.token}).encode()
        req = Request(url, data=body, headers={'__RequestVerificationToken': self.token,
                      'User-Agent': 'DaylightPublicEvidenceResearch/1.0',
                      'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'})
        with self.opener.open(req, timeout=60) as r:
            raw = r.read(16_000_001)
            receipt = {'source_id': source_id, 'requested_url': url, 'final_url': r.url,
                       'method': 'POST', 'kind': 'public-filing-metadata', 'inputs': fields,
                       'http_status': r.code, 'bytes': len(raw),
                       'sha256': hashlib.sha256(raw).hexdigest(), 'retries': 0,
                       'retrieved_at_utc': datetime.now(timezone.utc).isoformat()}
        (DEST / 'raw' / receipt['sha256']).write_bytes(raw)
        target.write_text(json.dumps(receipt, indent=2, sort_keys=True) + '\n')
        if len(raw) > 16_000_000:
            raise ValueError('Source size limit; stop')
        return json.loads(raw)


def criteria(year=None):
    result = {'area': 2, 'coNmSh': True, 'coNaicCoCdSh': True,
              'coNaicGrpCdSh': True, 'fileLogNumSh': True, 'fileTypeSh': True,
              'formNumSh': True, 'mktNmSh': True, 'enableProd': True,
              'selProdType': '2', 'selProdCatSh': True, 'selProdCats': [27],
              'fileDtSh': True, 'closeDtSh': True, 'selFinActSh': True,
              'effDtNewSh': True, 'effDtRenewSh': True}
    if year:
        result.update(fileDtFrom=f'{year}-01-01T00:00:00',
                      fileDtTo=f'{year}-12-31T23:59:59')
    return result


def main():
    search = Search()
    # All available filing history, not only 2026 submissions. This is a metadata
    # census and does not prove that older approved forms remain sold in 2026.
    result = search.post('irfs-medigap-all', '/Search/AdvancedSearch',
                         {'criteria': json.dumps(criteria(), separators=(',', ':'))})
    print(json.dumps({'keys': list(result), 'counts': {k: len(v) for k, v in result.items() if isinstance(v, list)}}))
    index = []
    for year in range(2001, 2027):
        sid = f'irfs-medigap-filed-{year}'
        fields = {'criteria': json.dumps(criteria(year), separators=(',', ':'))}
        annual = search.post(sid, '/Search/AdvancedSearch', fields)
        count = len(annual['Data'])
        index.append({'receipt': sid + '.json', 'row_count': count,
                      'partition': str(year), 'used': count < 1000})
        print(json.dumps({'filed_year': year, 'rows': count}), flush=True)
        # The combined backend returned 2,000 rows, but individual legacy or
        # current backend partitions can stop at 1,000. Use the lower cap.
        if count >= 1000:
            for month in range(1, 13):
                c = criteria(year)
                c.update(fileDtFrom=f'{year}-{month:02}-01T00:00:00',
                         fileDtTo=f'{year}-{month:02}-{calendar.monthrange(year, month)[1]:02}T23:59:59')
                msid = f'{sid}-{month:02}'
                monthly = search.post(msid, '/Search/AdvancedSearch',
                                      {'criteria': json.dumps(c, separators=(',', ':'))})
                n = len(monthly['Data'])
                index.append({'receipt': msid + '.json', 'row_count': n,
                              'partition': f'{year}-{month:02}', 'used': n < 1000})
                if n >= 1000:
                    raise ValueError('Monthly partition still truncated; split further before using')
    (DEST / 'irfs-index.json').write_text(json.dumps({
        'scope': 'Medicare Supplement category 27, Life & Health, all available filed years 2001–2026, including earlier filings potentially still in force. Search-category/form metadata is not current-sale or Collier applicability proof; pre-2001 unavailable. Initial all-history result reached 2,000 returned rows and is not used as a complete census.',
        'partitions': index}, indent=2, sort_keys=True) + '\n')


def details():
    search = Search()
    r = json.loads((DEST / 'irfs-medigap-filed-2026.json').read_text())
    rows = json.loads((DEST / 'raw' / r['sha256']).read_text())['Data']
    filings = {(x['AppSrc'], x['FileLogNumber'], x['FilingId']): x for x in rows}
    index = []
    for (src, fn, fid), row in sorted(filings.items()):
        sid = f'irfs-detail-{src}-{fn}'
        if row['IsRestricted']:
            index.append({'filing': fn, 'state': 'source_restricted_not_opened'})
            continue
        search.post(sid, '/Search/GetFiling', {'fn': fn, 'id': fid or '', 'src': src})
        index.append({'filing': fn, 'receipt': sid + '.json', 'state': 'public_metadata_only'})
        if len(index) % 20 == 0:
            print(json.dumps({'filing_details': len(index), 'expected': len(filings)}), flush=True)
    (DEST / 'irfs-details-index.json').write_text(json.dumps({
        'scope': 'Every unrestricted filing in the bounded 2026-filed category-27 query; metadata only, not filed rate documents or a 2026-effective universe.',
        'filings': index}, indent=2, sort_keys=True) + '\n')


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--details', action='store_true')
    args = p.parse_args()
    details() if args.details else main()
