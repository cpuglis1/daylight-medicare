#!/usr/bin/env python3
"""Retain ordinary public source responses for the additive L07 local closeout."""
import argparse
import json
from pathlib import Path

from l04_acquire import put, write
from l05_acquire import request

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'docs/data/l07-pharmacy-networks-2026-10-27'
OUT = BASE / 'closeout-r1'


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--url', required=True)
    p.add_argument('--label', required=True)
    a = p.parse_args()
    OUT.mkdir(exist_ok=True)
    (OUT / 'raw').mkdir(exist_ok=True)
    if (OUT / 'SEALED').exists():
        raise ValueError('Closeout evidence is sealed')
    index = OUT / 'sources.json'
    sources = json.loads(index.read_text()) if index.exists() else []
    old = next((r for r in sources if r['requested_url'] == a.url), None)
    if old:
        print(json.dumps(old)); return
    body, receipt = request(a.url, OUT)
    receipt.update(put(OUT, body), label=a.label)
    sources.append(receipt)
    write(index, sources)
    print(json.dumps(receipt))


if __name__ == '__main__':
    main()
