"""Bounded public-source capture. One request per URL; no crawler or retries.

Run once in a new revision directory. Failed/challenged sources stay excluded.
The extracted text is evidence, never instructions or automatic accepted facts.
"""
import hashlib
import subprocess
from html.parser import HTMLParser
import json
from pathlib import Path
from datetime import datetime, timezone
import urllib.request
import urllib.error

ROOT = Path(__file__).resolve().parent


class Text(HTMLParser):
    def __init__(self):
        super().__init__()
        self.skip = 0
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in {'script', 'style', 'noscript'}:
            self.skip += 1
        if tag in {'p', 'li', 'h1', 'h2', 'h3', 'h4', 'br', 'div', 'tr'}:
            self.parts.append('\n')

    def handle_endtag(self, tag):
        if tag in {'script', 'style', 'noscript'}:
            self.skip = max(0, self.skip - 1)

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)

    def text(self):
        return '\n'.join(' '.join(line.split()) for line in ''.join(self.parts).splitlines() if line.strip()) + '\n'


def main():
    manifest = ROOT / 'sources.json'
    if manifest.exists():
        raise SystemExit('Revision already captured. Create a new revision; do not overwrite evidence.')
    (ROOT / 'raw').mkdir(exist_ok=True)
    (ROOT / 'text').mkdir(exist_ok=True)
    sources = json.loads((ROOT / 'source-inputs.json').read_text())
    for row in sources:
        row['checked_at'] = datetime.now(timezone.utc).isoformat()
        row['status'] = 'unavailable'
        req = urllib.request.Request(row['url'], headers={'User-Agent': 'Daylight-public-source-review/1.0'})
        try:
            with urllib.request.urlopen(req, timeout=35) as response:
                content = response.read()
                row.update(http_status=response.status, final_url=response.geturl(),
                           content_type=response.headers.get('Content-Type', ''),
                           last_modified=response.headers.get('Last-Modified'))
            is_pdf = 'application/pdf' in row['content_type'] or content.startswith(b'%PDF-')
            raw_path = 'raw/' + row['id'] + ('.pdf' if is_pdf else '.html')
            text_path = 'text/' + row['id'] + '.txt'
            (ROOT / raw_path).write_bytes(content)
            if is_pdf:
                text = subprocess.check_output(['pdftotext', '-layout', str(ROOT / raw_path), '-']).decode('utf-8')
            else:
                parser = Text()
                parser.feed(content.decode('utf-8', errors='replace'))
                text = parser.text()
            challenged = any(s in text.lower() for s in ('verify you are human', 'access denied', 'just a moment...'))
            row['status'] = 'stop_challenge' if challenged else 'captured'
            (ROOT / text_path).write_text(text)
            row.update(raw_path=raw_path, text_path=text_path, bytes=len(content),
                       sha256=hashlib.sha256(content).hexdigest(),
                       text_sha256=hashlib.sha256(text.encode()).hexdigest())
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            row.update(error=str(error), http_status=getattr(error, 'code', None))
            if getattr(error, 'code', None) in {401, 403, 429}:
                row['status'] = 'stop_http'
        print(row['id'], row['status'], row.get('http_status'), flush=True)
        # Preserve completed work even if a later request is interrupted.
        manifest.write_text(json.dumps(sources, indent=2) + '\n')


if __name__ == '__main__':
    main()
