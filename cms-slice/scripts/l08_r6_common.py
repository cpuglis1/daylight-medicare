"""Additive CMS Original Medicare reference; preceding L08 revisions are read-only."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HOME = ROOT / 'docs/data/l08-provider-networks-2026-10-27'
BASE = HOME / 'original-medicare-r6'
PARENT = HOME / 'wellcare-r5'
OWNER = ROOT / 'plans/doctors-clinicians_2026-10-15'
REFERENCE_DATE = '2026-10-28'


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + '\n')


def packed(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'))


def filehash(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def assert_open():
    if (BASE / 'SEALED').exists():
        raise ValueError('Sealed r6; use a new revision for changes')


def csv_encoding(path):
    """Strict decoding only: retain bytes and declare legacy CMS encodings explicitly."""
    for encoding in ('utf-8-sig', 'cp1252'):
        try:
            with path.open(encoding=encoding) as stream:
                while stream.read(1024 * 1024):
                    pass
            return encoding
        except UnicodeDecodeError:
            continue
    raise ValueError('Unresolved source encoding: ' + str(path))

