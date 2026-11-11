#!/usr/bin/env python3
"""Controlled exact alias linking from NLM's public RxNorm/FDA name rows.

No approximate string distance, strength conversion, salt removal or code remap.
An unqualified printed injection can match only a globally unique injectable
presentation alias. A qualified pen/syringe name never widens its device scope.
"""
import argparse
from collections import defaultdict,Counter
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
import unicodedata
import zipfile

ROOT=Path(__file__).resolve().parents[2]


def alias_key(name,general_injection=False):
    s=unicodedata.normalize('NFKC',name).lower()
    s=re.sub(r'\b(?:in|per)\b','/',s)
    s=re.sub(r'\b(?:pen[- ]?injector|auto[- ]?injector|autoinjector)\b',' autoinjector ',s)
    s=re.sub(r'\b(?:prefilled syringe|pre-filled syringe|pref syr)\b',' prefilledsyringe ',s)
    s=re.sub(r'\b(?:24\s*(?:hr|hour)|24hr)\b',' form24h ',s)
    s=re.sub(r'\b(?:12\s*(?:hr|hour)|12hr)\b',' form12h ',s)
    for short,long in [('hcl','hydrochloride'),('hbr','hydrobromide'),('tabs','tablet'),('tab','tablet'),('tablets','tablet'),('caps','capsule'),('cap','capsule'),('capsules','capsule'),('soln','solution'),('susp','suspension'),('inj','injectable'),('injection','injectable'),('injections','injectable'),('er','extended release'),('xr','extended release'),('dr','delayed release')]:s=re.sub(r'\b'+short+r'\b',long,s)
    # Route omission is allowed only for oral products; other routes remain explicit.
    s=re.sub(r'\boral\b','',s)
    forms=[]
    for word in ['autoinjector','prefilledsyringe','injectable','tablet','capsule','solution','suspension','cream','ointment','gel','patch','powder','extended','delayed','release','form24h','form12h']:
        if re.search(r'\b'+word+r'\b',s):forms.append(word);s=re.sub(r'\b'+word+r'\b',' ',s)
    if set(forms)&{'autoinjector','prefilledsyringe','injectable'}:
        forms=[f for f in forms if f!='solution']
        if general_injection:forms=[f for f in forms if f not in ['autoinjector','prefilledsyringe','injectable']]+['injectable']
    s=re.sub(r'\s*/\s*','/',s);s=re.sub(r'(\d)\s+(mg|mcg|ml|gm|g|units?)(?=\b)',r'\1\2',s)
    # Preserve ingredient/strength order and every numeric-unit pair.
    s=' '.join(re.findall(r'[a-z0-9.%/]+',s))
    return s+' || '+' '.join(sorted(set(forms)))


def build(base):
    statements=json.loads((base/'quantity-statements-r2.json').read_text());queries={q for s in statements for q in s['query_products']}
    query_keys={q:alias_key(q,bool(re.search(r'\binjection\b',q,re.I)) and not re.search(r'auto|pen|syringe',q,re.I)) for q in queries}
    wanted=set(query_keys.values());manifest=json.loads((base/'bulk-acquisition/source-manifest.json').read_text());path=ROOT/manifest['path']
    if hashlib.md5(path.read_bytes()).hexdigest()!=manifest['published_md5']:raise ValueError('Changed NLM public archive')
    names=defaultdict(lambda:defaultdict(list));types=set();rows=0;source_kinds=Counter()
    with zipfile.ZipFile(path) as z:
        member='rrf/RXNCONSO.RRF'
        with z.open(member) as f:
            for raw in f:
                r=raw.decode('utf-8').rstrip('\r\n').split('|')
                if r[11]=='RXNORM' and r[12] in ['SCD','SBD','GPCK','BPCK'] and r[16]=='N':types.add(r[0])
        with z.open(member) as f:
            for ordinal,raw in enumerate(f,1):
                rows+=1;r=raw.decode('utf-8').rstrip('\r\n').split('|')
                if r[0] not in types or r[1]!='ENG' or r[11] not in ['RXNORM','MTHSPL'] or r[16]!='N':continue
                source_kinds[r[11]]+=1
                for k in {alias_key(r[14]),alias_key(r[14],True)}&wanted:
                    if len(names[k][r[0]])<3:names[k][r[0]].append({'rxcui':r[0],'record_ordinal':ordinal,'RXAUI':r[7],'SAB':r[11],'TTY':r[12],'name':r[14],'raw_fields':r})
    matches={};states=Counter()
    for q,k in query_keys.items():
        codes=names.get(k,{})
        states['unique' if len(codes)==1 else 'ambiguous' if codes else 'unmatched']+=1
        if len(codes)==1:
            code=next(iter(codes));matches[q]={'rxcui':code,'normalization_key':k,'matched_alias_rows':codes[code],'match_rule':'unique controlled NLM/FDA alias; exact strength/order retained; no approximate search'}
    result={'schema':'l05-NLM-alias-links/1','archive_sha256':manifest['sha256'],'member':member,'national_RRF_rows_accounted':rows,'matching_product_types':['SCD','SBD','GPCK','BPCK'],'eligible_alias_rows_by_source':dict(source_kinds),'query_states':dict(states),'matches':matches}
    (base/'quantity-alias-matches.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    return {'national_RRF_rows':rows,'queries':len(query_keys),'states':dict(states)}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--base',type=Path,required=True);a=p.parse_args();print(json.dumps(build(a.base.resolve()),indent=2))
