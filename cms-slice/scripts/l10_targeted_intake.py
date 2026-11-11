"""Retain the eleven owner-delivered targeted filings as a new research revision."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'docs/data/l10-medigap-2026-10-28'
PACKET = BASE / 'targeted-filings-r5'
OUT = PACKET / 'build-r1'


def read(path):
    return json.loads(Path(path).read_text())


def write(path, data):
    Path(path).write_text(json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + '\n')


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def guard():
    if (OUT / 'SEALED').exists():
        raise ValueError('Preserve sealed r5; use a new revision')


def retain(item):
    case = item['case']
    matches = list((ROOT / 'plans').rglob(case + '_*.pdf'))
    if len(matches) != 1:
        raise ValueError('Expected one exact owner packet: ' + case)
    owner = matches[0]
    retained = PACKET / 'sources' / owner.name
    if retained.exists():
        assert sha(owner) == sha(retained)
    else:
        shutil.copyfile(owner, retained)
    pdf = PdfReader(retained)
    first = pdf.pages[0].extract_text()
    assert 'Filing Number: ' + case in first and 'Entire Filing' in first
    text = [p.extract_text() for p in pdf.pages]
    native = PACKET / 'text' / (owner.stem + '-pypdf.json')
    write(native, text)
    layout = PACKET / 'text' / (owner.stem + '.txt')
    subprocess.run(['pdftotext', '-layout', str(retained), str(layout)], check=True)
    assert len(layout.read_text().split('\f')[:-1]) == len(pdf.pages)
    result = {'case': case, 'owner_path': str(owner.relative_to(ROOT)),
              'retained_path': str(retained.relative_to(ROOT)), 'bytes': retained.stat().st_size,
              'sha256': sha(retained), 'pages': len(pdf.pages),
              'pypdf_text_path': str(native.relative_to(ROOT)), 'pypdf_text_sha256': sha(native),
              'poppler_text_path': str(layout.relative_to(ROOT)), 'poppler_text_sha256': sha(layout),
              'low_text_pages': [i + 1 for i, t in enumerate(text) if len(t.strip()) < 80],
              'worksheet_header_candidate_pages': [i + 1 for i, t in enumerate(text) if 'Filing Company' in t],
              'human_acceptance': None, 'consumer_release_enabled': False}
    print(json.dumps({'retained': case, 'pages': len(text), 'worksheet_candidates': len(result['worksheet_header_candidate_pages'])}), flush=True)
    return result


def intake():
    guard()
    for directory in ['sources', 'text', 'qa']:
        (PACKET / directory).mkdir(parents=True, exist_ok=True)
    if not (PACKET / 'preservation-before.json').exists():
        old = BASE / 'closeout-2026-10-29'
        protected = read(old / 'preservation.json')['protected_files_sha256']
        for path in [*old.iterdir(), BASE / 'CURRENT_CLOSEOUT.json']:
            if path.is_file():
                protected[str(path.relative_to(ROOT))] = sha(path)
        assert all(sha(ROOT / p) == wanted for p, wanted in protected.items())
        write(PACKET / 'preservation-before.json', protected)
    else:
        assert all(sha(ROOT / p) == wanted for p, wanted in read(PACKET / 'preservation-before.json').items())
    items = [r for r in read(BASE / 'gap-resolution-r4/build-r1/download-items.json') if r['tier'] == '1']
    assert len(items) == 11 and len({r['case'] for r in items}) == 11
    with ThreadPoolExecutor(max_workers=2) as pool:
        documents = sorted(pool.map(retain, items), key=lambda r: r['case'])
    guard()
    result = {'schema': 'l10-targeted-intake/1', 'received_local_date': '2026-10-29',
              'recorded_at_utc': datetime.now(timezone.utc).isoformat(), 'documents': documents,
              'targeted_packets_expected': 11, 'targeted_packets_retained': len(documents),
              'total_pages': sum(d['pages'] for d in documents), 'human_acceptance': None,
              'consumer_release_enabled': False, 'full_l10_complete': False}
    write(PACKET / 'intake.json', result)
    return {k: v for k, v in result.items() if k != 'documents'}


if __name__ == '__main__':
    print(json.dumps(intake(), indent=2))
