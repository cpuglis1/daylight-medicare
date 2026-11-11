"""Offline research lookup for L03 r6; accepted r4 production gate is untouched."""
import hashlib,json,pathlib
from l03_user_documents import ROOT,REPO,PACKAGE,load,rows
import l03_scoped_reference as approved
PARENT_R4_PIN='fb163f824e35cbb52b5aa11bd520de64bd4fa5e51b574f7d3de4c3accbaab881'
def file_sha(p):
    h=hashlib.sha256()
    with pathlib.Path(p).open('rb')as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()
def verify(root=ROOT,expected_manifest_sha256=None):
    root=pathlib.Path(root);manifest=root/'manifest.json'
    if expected_manifest_sha256 and file_sha(manifest)!=expected_manifest_sha256:raise ValueError('r6 manifest pin mismatch')
    m=load(manifest)
    if m['package_id']!=PACKAGE:raise ValueError('Wrong research package')
    if m['parent_accepted_r4_manifest_sha256']!=PARENT_R4_PIN:raise ValueError('Wrong accepted parent')
    if file_sha(approved.ROOT/'manifest.json')!=PARENT_R4_PIN:raise ValueError('Accepted parent changed')
    approved.require_review()
    for rel,h in m['files_sha256'].items():
        p=(root/rel).resolve()
        if not p.is_relative_to(root.resolve()):raise ValueError('Unsafe evidence path')
        if not p.is_file()or file_sha(p)!=h:raise ValueError('r6 evidence hash mismatch: '+rel)
    for rel,h in m['code_sha256'].items():
        p=(REPO/rel).resolve()
        if not p.is_relative_to(REPO)or file_sha(p)!=h:raise ValueError('r6 code hash mismatch: '+rel)
    return m
def research_lookup(offering_id,root=ROOT):
    verify(root);root=pathlib.Path(root)
    plan=next((p for p in load(root/'plan-document-matrix.json')if p['offering_id']==offering_id),None)
    if plan is None:raise ValueError('Unknown exact 2026 offering, including segment')
    service=[s for s in rows(root/'service-reconciliation.jsonl.gz')if s['offering_id']==offering_id]
    chart=[s for s in rows(root/'carrier-chart-rows.jsonl.gz')if s['offering_id']==offering_id]
    return {'package_id':PACKAGE,'offering':plan,'PBP_services':service,'carrier_source_native_rows':chart,
       'source_led_comparisons':[x for x in load(root/'source-led-comparisons.json')if x['offering_id']==offering_id],
       'condition_packet':next((p for p in load(root/'plan-condition-packets.json')if p['offering_id']==offering_id),None),
       'accepted_for_reference':False,'consumer_usable':False,'full_L03_complete':False,
       'scope':'Published 2026 source comparison research; preserves exact carrier conditions and unknowns. No personal applicability, prices, totals or recommendation.'}
def published_lookup(*args,**kwargs):
    raise PermissionError('r6 new evidence is not accepted; use the separately accepted exact r4 reference only')
