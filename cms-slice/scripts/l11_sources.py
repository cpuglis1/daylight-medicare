"""Source-preserving L11 text extraction using retained evidence only."""
from html.parser import HTMLParser
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'docs/data/l11-medigap-rights-2026-10-28'
ACQ = BASE / 'acquisition-r1'


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def norm(value):
    return ' '.join(value.replace('\xa0', ' ').split())


class HTMLText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.skip = 0
        self.parts = []
        self.paragraphs = []
        self.current = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in ('script', 'style'):
            self.skip += 1
        if not self.skip and tag in ('p', 'div', 'li', 'tr', 'h1', 'h2', 'h3', 'h4', 'br'):
            self.parts.append('\n')
        if tag == 'p' and not self.skip:
            self.current = {'html_id': attrs.get('id'), 'html_class': attrs.get('class'), 'parts': []}

    def handle_endtag(self, tag):
        if tag in ('script', 'style'):
            self.skip -= 1
        if tag == 'p' and self.current is not None:
            p = self.current
            p['text'] = norm(''.join(p.pop('parts')))
            if p['text']:
                self.paragraphs.append(p)
            self.current = None
        if not self.skip and tag in ('p', 'div', 'li', 'tr', 'h1', 'h2', 'h3', 'h4'):
            self.parts.append('\n')

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)
            if self.current is not None:
                self.current['parts'].append(data)


def extract():
    if (BASE / 'build-r1' / 'manifest.json').exists():
        raise ValueError('L11 r1 is sealed; preserve extraction and use a new revision')
    (ACQ / 'text').mkdir(exist_ok=True)
    index = {}
    for receipt in sorted(ACQ.glob('*.json')):
        r = json.loads(receipt.read_text())
        if not isinstance(r, dict) or 'http_status' not in r:
            continue
        path = ACQ / 'raw' / r['sha256']
        if sha(path) != r['sha256'] or path.stat().st_size != r['bytes']:
            raise ValueError('Changed acquisition: ' + r['source_id'])
        raw = path.read_bytes()
        status = 'retained'
        if r['http_status'] != 200:
            status = 'http_failure'
        elif b'challenge-platform' in raw:
            status = 'javascript_challenge_not_source_text'
        output = ACQ / 'text' / (r['source_id'] + '.txt')
        paragraphs = None
        if status == 'retained':
            if 'pdf' in r['content_type']:
                subprocess.run(['pdftotext', '-layout', str(path), str(output)], check=True)
            elif 'msword' in r['content_type']:
                text = subprocess.check_output(['textutil', '-convert', 'txt', '-stdout', str(path)])
                output.write_bytes(text)
            elif 'xml' in r['content_type']:
                # XML source is retained exactly; flattening is for inspection.
                h = HTMLText(); h.feed(raw.decode('utf-8'))
                output.write_text('\n'.join(norm(x) for x in ''.join(h.parts).splitlines() if norm(x)) + '\n')
            elif 'html' in r['content_type']:
                h = HTMLText(); h.feed(raw.decode('utf-8', errors='replace'))
                output.write_text('\n'.join(norm(x) for x in ''.join(h.parts).splitlines() if norm(x)) + '\n')
                paragraphs = h.paragraphs
            else:
                output.write_bytes(raw)
        index[r['source_id']] = {**r, 'receipt_path': str(receipt.relative_to(ROOT)),
                                'receipt_sha256': sha(receipt), 'path': str(path.relative_to(ROOT)),
                                'content_status': status}
        if status == 'retained':
            index[r['source_id']].update(text_path=str(output.relative_to(ROOT)), text_sha256=sha(output))
            if paragraphs is not None:
                pp = ACQ / 'text' / (r['source_id'] + '-paragraphs.json')
                pp.write_text(json.dumps(paragraphs, indent=2, ensure_ascii=False) + '\n')
                index[r['source_id']]['paragraphs_path'] = str(pp.relative_to(ROOT))
    web_sections = {}
    web_origins = {}
    for capture in sorted((ACQ / 'web-cache').glob('*.txt')):
        for block in capture.read_text().split('--------------------------------------------------------------------------------'):
            match = re.search(r'https://www.flsenate.gov/Laws/Statutes/2026/([0-9.]+)', block)
            if not match:
                continue
            section = match[1]
            lines = web_sections.setdefault(section, {})
            web_origins.setdefault(section, set()).add(str(capture.relative_to(ROOT)))
            for number, text in re.findall(r'^L(\d+): ?(.*)$', block, re.M):
                if number in lines and lines[number] != text:
                    raise ValueError('Conflicting public extraction line: ' + section + '/' + number)
                lines[number] = text
    for section, lines in web_sections.items():
        sid = 'fs-' + section
        path = ACQ / 'text' / (sid + '-web-lines.json')
        lines = dict(sorted(lines.items(), key=lambda x: int(x[0])))
        path.write_text(json.dumps(lines, indent=2, ensure_ascii=False) + '\n')
        clean = ACQ / 'text' / (sid + '.txt')
        clean.write_text('\n'.join(re.sub(r'【\d+†([^】]+)】', r'\1', t) for t in lines.values()) + '\n')
        index[sid] = {'source_id': sid, 'kind': 'official-statute-public-web-extraction',
                      'requested_url': 'https://www.flsenate.gov/Laws/Statutes/2026/' + section,
                      'path': str(path.relative_to(ROOT)), 'sha256': sha(path),
                      'bytes': path.stat().st_size, 'content_status': 'retained_public_web_extraction',
                      'text_path': str(clean.relative_to(ROOT)), 'text_sha256': sha(clean),
                      'original_captures': [{'path': p, 'sha256': sha(ROOT / p)} for p in sorted(web_origins[section])],
                      'capture_limit': 'Public web text with original line locators and capture provenance; not raw origin HTML. Direct statute HTTP challenge is retained separately and was not solved.'}
    (ACQ / 'extraction-index.json').write_text(json.dumps(index, indent=2, sort_keys=True) + '\n')
    return index


if __name__ == '__main__':
    print(json.dumps({sid: s['content_status'] for sid, s in extract().items()}, indent=2))
