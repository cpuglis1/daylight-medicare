#!/usr/bin/env python3
"""Validate and version a connector capture before projecting it into the vault."""
import argparse
import json
from pathlib import Path
import re
from sync import ROOT, VAULT_NAME, atomic, digest, dump, safe_target


def stage(root, kind, capture):
    if kind not in {'drive', 'chatgpt'}:
        raise ValueError('Capture kind must be drive or chatgpt')
    metadata = capture.get('metadata', {})
    identifier = metadata.get('id', '')
    if not re.fullmatch(r'[A-Za-z0-9_-]{10,200}', identifier):
        raise ValueError('Invalid source identifier')
    if not metadata.get('title') or not capture.get('fetched_at'):
        raise ValueError('Capture needs a title and timestamp')
    if kind == 'drive':
        if 'response' not in capture or not metadata.get('url') or capture.get('method') not in {'native_document', 'readable_fetch'}:
            raise ValueError('Incomplete Drive capture')
    else:
        if not isinstance(capture.get('pages'), list) or not capture['pages']:
            raise ValueError('Chat capture needs every returned message page')
        if any(p.get('nextCursor') or p.get('page', {}).get('nextCursor') for p in capture['pages'][-1:]):
            raise ValueError('Chat capture has unread older pages')
        if not any('turns' in p for p in capture['pages']):
            raise ValueError('Chat capture has no message page')
    system = Path(root) / VAULT_NAME / '.knowledge-imports'
    target = safe_target(system, f'{kind}/{identifier}.json')
    serialized = json.dumps(capture, ensure_ascii=False, indent=2) + '\n'
    if target.exists():
        old = target.read_bytes()
        if old == serialized.encode():
            return {'source_id': f'{kind}:{identifier}', 'status': 'unchanged'}
        atomic(system / 'capture-history' / kind / identifier / (digest(old) + '.json'), old)
    atomic(target, serialized)
    return {'source_id': f'{kind}:{identifier}', 'status': 'staged'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('kind', choices=['drive', 'chatgpt'])
    parser.add_argument('capture', type=Path)
    parser.add_argument('--root', type=Path, default=ROOT)
    args = parser.parse_args()
    print(json.dumps(stage(args.root, args.kind, json.loads(args.capture.read_text())), indent=2))
