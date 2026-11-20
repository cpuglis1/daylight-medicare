#!/usr/bin/env python3
"""D199: derive the hosted doctor/drug binding revision from the sealed r1 binding.

r1 is read, never edited. The hosted revision keeps every dataset, source, control-file
hash and STOP-ledger row of r1, and changes only:
  - purpose: fictional_invited_demo (owner approval D199; participant use stays refused)
  - control_mode: hosted_copy (the STOP ledger is a root-managed copy on the host)
  - technical_read_until_utc: the accelerator invitation's end
  - package_binding_id: r1's id, which the sealed package database still stamps
"""
import copy
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'infrastructure/daylight-data/src'))
from daylight_data.serving.binding import digest  # noqa: E402
from daylight_data.serving.pilot_foundation import HOSTED_CONTROLS, HOSTED_PURPOSE, file_hash  # noqa: E402

R1 = ROOT / 'infrastructure/daylight-data/.state/pilot-foundation-2026-r1/binding.json'
R1_ID = '2ac2a293c7753eaec759b8321a8a3968a22f7e951b628ba0a5350f881a4a4d56'
OUTPUT = ROOT / 'infrastructure/daylight-data/.state/pilot-foundation-2026-r2-hosted/binding.json'
READ_UNTIL = '2027-02-17T04:00:00+00:00'  # after the Feb 16, 2027 10:18 p.m. Eastern invitation end


def build():
    sealed = json.loads(R1.read_text())
    body = {k: v for k, v in sealed.items() if k != 'binding_id'}
    if sealed['binding_id'] != R1_ID or digest(body) != R1_ID:
        raise ValueError('The sealed r1 binding changed; stop.')
    for path, expected in sealed['controls'].items():
        if file_hash(ROOT / path) != expected:
            raise ValueError(f'Control file changed since r1: {path}')
    hosted = copy.deepcopy(body)
    policy = hosted['policy']
    policy['purpose'] = HOSTED_PURPOSE
    policy['technical_read_until_utc'] = READ_UNTIL
    policy['technical_read_until_basis'] = (
        'D199 (owner, November 19, 2026): readable for the hosted invited fictional demo until the '
        'accelerator invitation ends. Not a source review, consumer acceptance or participant release.')
    policy['acceptance'] = {**policy['acceptance'], 'participant_release': False,
                            'hosted_demo': 'D199 owner approval: invited fictional demo only'}
    hosted['control_mode'] = HOSTED_CONTROLS
    hosted['package_binding_id'] = R1_ID
    hosted['supersedes_for_hosted_demo'] = R1_ID
    hosted['source_control_snapshot'] = {
        'source_access_states': sealed['source_control_snapshot']['source_access_states']}
    binding = {'binding_id': digest(hosted), **hosted}
    OUTPUT.parent.mkdir(mode=0o700, exist_ok=True)
    raw = json.dumps(binding, indent=2, sort_keys=True) + '\n'
    if OUTPUT.exists() and OUTPUT.read_text() != raw:
        raise ValueError('A different hosted binding already exists; never overwrite.')
    OUTPUT.write_text(raw)
    return binding


if __name__ == '__main__':
    result = build()
    print(json.dumps({'binding': str(OUTPUT.relative_to(ROOT)), 'binding_id': result['binding_id'],
                      'purpose': result['policy']['purpose'], 'read_until': READ_UNTIL,
                      'stop_rows': len(result['source_control_snapshot']['source_access_states'])}))
