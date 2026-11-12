"""Read-only r3 research interface with prior-version and current manifest pins."""
import json,pathlib
from l03_close_sources import R1,R2,R3,sha
from l03_close_validate import R2_PIN,REPO
from l03_reconcile_reference import verify as verify_r2

def verify(root=R3,expected_manifest_sha256=None):
    verify_r2(expected_manifest_sha256=R2_PIN)
    b=(root/'package-manifest.json').read_bytes()
    if expected_manifest_sha256 is not None and sha(b)!=expected_manifest_sha256:raise ValueError('r3 manifest pin mismatch')
    m=json.loads(b)
    if m['r2_manifest_sha256']!=R2_PIN:raise ValueError('r2 parent pin mismatch')
    for rel,h in m['files'].items():
        p=root/rel
        if not p.is_file()or sha(p.read_bytes())!=h:raise ValueError('r3 evidence hash mismatch: '+rel)
    for rel,h in m['code_files'].items():
        p=REPO/rel
        if not p.is_file()or sha(p.read_bytes())!=h:raise ValueError('r3 code hash mismatch: '+rel)
    return m
def research_lookup(offering_id,root=R3):
    verify(root)
    p=next((x for x in json.loads((R1/'plan-document-matrix.json').read_text())if x['offering_id']==offering_id),None)
    if p is None:raise ValueError('Unknown exact offering identity')
    a=[r for r in json.loads((root/'amount-issue-decisions.json').read_text())if r['offering_id']==offering_id]
    return {'offering':p,'amount_decisions':a,'source_gap_groups':[x for x in a if x['remaining_gap_id']],'consumer_usable':False,'accepted':False,'comprehensive':False,'scope':'Published 2026 L03 research reference; bounded comparisons and explicit holds, human acceptance pending'}
def published_lookup(*args,**kwargs):raise PermissionError('L03 r3 has unresolved source claims and no accepted field release')
