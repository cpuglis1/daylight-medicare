"""Cached ordinary public CMS reads with receipts, bounded pagination and no denial bypass."""
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

from l08_r6_common import BASE, assert_open, filehash, packed, write


class AccessStopped(RuntimeError):
    pass


class CMSClient:
    def __init__(self, directory=None, transport=None):
        self.directory = Path(directory or BASE / 'acquisition')
        self.transport = transport
        self.last_request = 0

    @staticmethod
    def guard(url):
        p = urlparse(url)
        if p.scheme != 'https' or p.hostname != 'data.cms.gov' or p.username or p.password:
            raise AccessStopped('Only ordinary HTTPS reads from data.cms.gov are supported')
        # The owner authorized the working Data.CMS API. The denied Provider Data
        # Catalog family remains stopped, including its SQL and alternate query routes.
        if p.path.startswith('/provider-data/'):
            raise AccessStopped('Provider Data Catalog source stop remains in force')
        if not (p.path == '/data.json' or p.path.startswith('/data-api/v1/') or
                p.path.startswith('/sites/default/files/')):
            raise AccessStopped('Undocumented CMS route requires source review')

    def get(self, url):
        self.guard(url)
        key = hashlib.sha256(url.encode()).hexdigest()
        receipt_path = self.directory / 'receipts' / (key + '.json')
        if receipt_path.exists():
            r = json.loads(receipt_path.read_text())
            if r.get('error'):
                raise AccessStopped(r['error'])
            raw = self.directory / r['raw_relative_path']
            if filehash(raw) != r['sha256']:
                raise ValueError('Cached source hash mismatch')
            return raw.read_bytes(), r
        assert_open()
        stop = self.directory / 'access-stop.json'
        if stop.exists():
            raise AccessStopped('Persisted access denial; no retry or route substitution')
        self.directory.mkdir(parents=True, exist_ok=True)
        rec = {'url': url, 'requested_at_utc': datetime.now(timezone.utc).isoformat(),
               'attempts': 1, 'method': 'GET'}
        body = b''
        client = self

        class Redirect(HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                client.guard(newurl)
                return super().redirect_request(req, fp, code, msg, headers, newurl)

        try:
            time.sleep(max(0, .2 - (time.monotonic() - self.last_request)))
            self.last_request = time.monotonic()
            if self.transport:
                body, headers = self.transport(url)
                rec.update(status=200, final_url=url, headers=headers)
            else:
                req = Request(url, headers={'Accept': '*/*',
                              'User-Agent': 'Daylight public Medicare reference research'})
                with build_opener(Redirect).open(req, timeout=45) as response:
                    self.guard(response.url)
                    rec.update(status=response.status, final_url=response.url,
                               headers={k.lower(): v for k, v in response.headers.items()
                                        if k.lower() in {'content-type', 'etag', 'last-modified', 'date'}})
                    body = response.read(100_000_001)
                    if len(body) > 100_000_000:
                        raise ValueError('CMS response exceeds 100 MB bound')
        except Exception as exc:
            rec.update(error=str(exc), error_type=type(exc).__name__, status=getattr(exc, 'code', None))
            if isinstance(exc, HTTPError):
                body = exc.read(1_000_000)
                exc.close()
            if rec['status'] in (401, 403, 429):
                write(stop, {'url': url, 'status': rec['status'], 'no_retry': True})
        if body:
            sha = hashlib.sha256(body).hexdigest()
            raw = self.directory / 'raw' / sha
            raw.parent.mkdir(exist_ok=True)
            raw.write_bytes(body)
            rec.update(sha256=sha, bytes=len(body), raw_relative_path='raw/' + sha)
        write(receipt_path, rec)
        if rec.get('error'):
            raise AccessStopped(rec['error'])
        return body, rec

    def json(self, url):
        body, rec = self.get(url)
        return json.loads(body), rec

    def download(self, url, expected_bytes, expected_sha1=None):
        """Stream a publisher-advertised bulk file without loading it into memory."""
        self.guard(url)
        if not 0 < expected_bytes < 1_000_000_000:
            raise ValueError('Invalid publisher file-size bound')
        key = hashlib.sha256(url.encode()).hexdigest()
        rp = self.directory / 'receipts' / (key + '.json')
        if rp.exists():
            rec = json.loads(rp.read_text())
            if rec.get('error'):
                raise AccessStopped(rec['error'])
            path = self.directory / rec['raw_relative_path']
            if filehash(path) != rec['sha256'] or path.stat().st_size != expected_bytes:
                raise ValueError('Cached publisher file mismatch')
            return path, rec
        assert_open()
        if (self.directory / 'access-stop.json').exists():
            raise AccessStopped('Persisted access stop')
        self.directory.mkdir(parents=True, exist_ok=True)
        rec = {'url': url, 'requested_at_utc': datetime.now(timezone.utc).isoformat(),
               'method': 'GET', 'attempts': 1, 'publisher_bytes': expected_bytes,
               'publisher_sha1': expected_sha1}
        temp = self.directory / (key + '.download')
        client = self

        class Redirect(HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                client.guard(newurl)
                return super().redirect_request(req, fp, code, msg, headers, newurl)

        try:
            request = Request(url, headers={'User-Agent': 'Daylight public Medicare reference research'})
            with build_opener(Redirect).open(request, timeout=45) as response:
                self.guard(response.url)
                h, h1, size = hashlib.sha256(), hashlib.sha1(), 0
                with temp.open('wb') as output:
                    while chunk := response.read(1024 * 1024):
                        size += len(chunk)
                        if size > expected_bytes:
                            raise ValueError('Download exceeds publisher file size')
                        output.write(chunk); h.update(chunk); h1.update(chunk)
                if size != expected_bytes or (expected_sha1 and h1.hexdigest() != expected_sha1):
                    raise ValueError('Publisher size/SHA1 mismatch')
                raw = self.directory / 'raw' / h.hexdigest()
                raw.parent.mkdir(exist_ok=True); temp.replace(raw)
                rec.update(status=response.status, final_url=response.url, bytes=size,
                           sha256=h.hexdigest(), sha1=h1.hexdigest(), raw_relative_path='raw/' + h.hexdigest(),
                           headers={k.lower(): v for k, v in response.headers.items()
                                    if k.lower() in {'content-type', 'etag', 'last-modified', 'date'}})
        except Exception as exc:
            rec.update(error=str(exc), error_type=type(exc).__name__, status=getattr(exc, 'code', None))
            if isinstance(exc, HTTPError) and exc.code in (401, 403, 429):
                write(self.directory / 'access-stop.json', {'url': url, 'status': exc.code, 'no_retry': True})
            if temp.exists():
                temp.unlink()
        write(rp, rec)
        if rec.get('error'):
            raise AccessStopped(rec['error'])
        return raw, rec


def page_url(endpoint, offset, size=5000, sort=None, filters=None):
    if not 1 <= size <= 5000 or offset < 0:
        raise ValueError('Invalid CMS page bound')
    params = [('size', str(size)), ('offset', str(offset))]
    if sort:
        params.append(('sort', sort))
    for field, value in (filters or {}).items():
        # Simple equality filter, as documented by CMS; multiple predicates use a group.
        group = 'filter[' + field + '][condition]'
        params.extend([(group + '[path]', field), (group + '[operator]', '='),
                       (group + '[value]', value)])
    return endpoint + ('&' if '?' in endpoint else '?') + urlencode(params)


def collect(client, endpoint, *, sort, expected_rows=None, filters=None,
            size=5000, max_pages=2000, row_check=None):
    """Collect a version-pinned resource; terminal empty page and exact accounting required.

    A short page is not assumed terminal: some CMS servers cap requested page sizes.
    Source rows (including exact duplicates) are retained; repeats of a whole page fail.
    Publisher totals, when available, are required to agree, rather than being overwritten.
    """
    rows, pages, signatures = [], [], set()
    offset = 0
    terminal_empty = False
    for _ in range(max_pages):
        data, rec = client.json(page_url(endpoint, offset, size, sort, filters))
        if not isinstance(data, list) or any(not isinstance(r, dict) for r in data):
            raise ValueError('Unexpected CMS data response shape')
        pages.append({'offset': offset, 'rows': len(data), 'url': rec['url'],
                      'sha256': rec['sha256']})
        if not data:
            terminal_empty = True
            break
        signature = hashlib.sha256(packed(data).encode()).hexdigest()
        if signature in signatures:
            raise ValueError('Repeated CMS page: offset may have been ignored')
        signatures.add(signature)
        if row_check:
            for r in data:
                row_check(r)
        rows.extend(data)
        offset += len(data)
        if expected_rows is not None and len(rows) > expected_rows:
            raise ValueError('CMS collection exceeds publisher total')
    if not terminal_empty:
        raise ValueError('Pagination limit reached without a terminal empty page')
    if expected_rows is not None and len(rows) != expected_rows:
        raise ValueError('CMS collection differs from publisher total')
    return rows, {'endpoint': endpoint, 'sort': sort, 'filters': filters or {},
                  'pages': pages, 'rows': len(rows), 'publisher_rows': expected_rows,
                  'terminal_empty_page': terminal_empty,
                  'publisher_total_reconciled': expected_rows is not None,
                  'complete_network_or_clinician_census_claimed': False}

