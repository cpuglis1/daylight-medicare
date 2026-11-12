"""Independent carrier-region and original-record replay, no source mutation."""
from pathlib import Path
import gzip
import hashlib
import json

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
BASE=ROOT/'docs/data/l03-ma-benefits-2026-11-02-whole-offering-r12'
CAND=BASE/'carrier-network-referral-reconciliation-r1'
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def fp(x):return hashlib.sha256(json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
checks=0
def check(x,label):
    global checks
    assert x,label
    checks+=1
for m in read(HERE/'EXPECTED_FREEZE_R1.json')['members']:
    check(sha(HERE/m['path'])==m['sha256'],'Pre-candidate expectation unchanged')
for m in read(CAND/'FREEZE_R1.json')['members']:
    p=CAND/m['path'];check(sha(p)==m['sha256'] and p.stat().st_size==m['bytes'],'Candidate unchanged')
sha_cache={}
def pinned(b):
    p=ROOT/b['path']
    if p not in sha_cache:sha_cache[p]=sha(p)
    check(sha_cache[p]==b['sha256'],'Original source/image hash')
parents=read(CAND/'SOURCE_PARENTS.json')['parents']
check(len(parents)==63 and len({x['id'] for x in parents})==63,'Exact region census')
for parent in parents:
    pinned(parent['source_binding']);pinned(parent['render_binding'])
    locator=parent['locator'];pinned(locator['ocr_tsv'])
    image=parent['render_binding'];width,height=image['pixels']
    boxes=locator['bounded_regions']
    for left,top,right,bottom in boxes:
        check(0<=left<right<=width and 0<=top<bottom<=height,'Valid source bounds')
    tsv=(ROOT/locator['ocr_tsv']['path']).read_text().splitlines()
    for word in locator['selected_words']:
        row=tsv[word['tsv_line']-1].split('\t')
        check(row[-1]==word['text'],'Exact selected source locator token')
        x,y,w,h=word['bbox_xywh'];cx,cy=x+w/2,y+h/2
        check(any(left<=cx<=right and top<=cy<=bottom for left,top,right,bottom in boxes),'Selected token remains in source region')
    check(parent['ocr_is_source_authority'] is False and parent['candidate_interpretation_accepted'] is False,'Source-pixel and acceptance boundary')
graphs=read(CAND/'SOURCE_RULE_GRAPHS.json')
ids={x['id'] for x in parents}
check(len(graphs['rules'])==36,'Rule census')
for r in graphs['rules']:
    check(set(r['source_parent_ids'])<=ids and bool(r['source_parent_ids']),'Exact source parent linkage')
    check(r['factual_acceptance'] is False and r['complete_meaning_equivalence'] is False,'Graph is not factual acceptance')
check(not graphs['automatic_precedence_edges'] and not graphs['blanket_referral_no'] and not graphs['native_code_decoder_applied'],'No automatic precedence or code transfer')
original=ROOT/'docs/data/l03-ma-benefits-2026-11-01-whole-offering-r11/source-preparation/generated-r2/offering-canonical.jsonl.gz'
lines=gzip.decompress(original.read_bytes()).decode().splitlines()
originals={x['id']:x for x in map(json.loads,lines)}
rows=[json.loads(x) for x in gzip.decompress((CAND/'lineage-audit/all-page-original-lineage.jsonl.gz').read_bytes()).decode().splitlines()]
check(len(rows)==470 and len(originals)==4675,'Exact context and required source counts')
cache={};missing=[];binding_count=0
def bindings(x):
    global binding_count
    if isinstance(x,dict):
        if 'collection_path' in x and isinstance(x.get('record'),dict):
            p=ROOT/x['collection_path']
            if p not in cache:
                a=json.loads(gzip.decompress(p.read_bytes()));cache[p]={r['record_id']:r for r in a['records']}
            check(x['record']==cache[p][x['record']['record_id']],'Complete retained native record')
            binding_count+=1
        elif 'collection_path' in x and 'record' in x:
            missing.append({k:v for k,v in x.items() if k!='record'})
        for v in x.values():bindings(v)
    elif isinstance(x,list):
        for v in x:bindings(v)
obs_relations=0
for r in rows:
    old=originals[r['original_canonical_id']]
    check(r['original_canonical_payload']==old and r['original_canonical_payload_sha256']==fp(old),'Original payload unchanged')
    line=lines[r['original_canonical_ordinal_1based']-1]
    check(hashlib.sha256(line.encode()).hexdigest()==r['original_canonical_line_without_newline_sha256'],'Original JSON line unchanged')
    check(r['canonical_kind_preserved']==old['kind'] and r['canonical_states_preserved']==old['states'],'Original kind/state')
    check(not r['new_acceptance'] and not r['meaning_verdict'],'Page context is not semantic approval')
    obs_relations+=len(r['observation_lineage']);bindings(r)
check(obs_relations==830,'Exact associated observation relationships')
out={'schema':'daylight.referral.independent-source-replay.r1','checks_passed':checks,
    'source_regions':len(parents),'source_rules':36,'original_context_records':len(rows),
    'observation_relationships':obs_relations,'retained_native_record_bindings':binding_count,
    'retained_native_collections':len(cache),'explicit_missing_lookup_bindings':missing,
    'known_effect_scope_findings':['RF-NR-R1-F01','RF-NR-R1-F02','RF-NR-R1-F03'],
    'mechanical_replay_accepts_source_meaning':False,'new_acceptance':False}
print(json.dumps(out,ensure_ascii=False,indent=2))
