#!/usr/bin/env python3
"""Extract explicit QL statements and exact-name lookup work from retained PDFs."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import unicodedata
from urllib.parse import urlencode

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'docs/data/l05-drug-coverage-2026-10-25'


def read(p):return json.loads(p.read_text())
def dump(p,x):p.write_text(json.dumps(x,indent=2,sort_keys=True)+'\n')
def key(s):return hashlib.sha256(s.encode()).hexdigest()[:20]


def products(label):
    """Expand only an explicit comma-separated list of same-unit strengths."""
    label=' '.join(unicodedata.normalize('NFKC',label).split())
    strength=r'\d+(?:\.\d+)?\s*(?:mcg|mg|gm|g|units?)(?:\s*/\s*\d*(?:\.\d+)?\s*(?:ml|g|mg|act))?'
    m=re.fullmatch(r'(.+?)\s+('+strength+r')(\s*,\s*'+strength+r')+',label,re.I)
    if m:
        strengths=re.findall(strength,label[len(m[1]):],re.I)
        return [m[1]+' '+s for s in strengths]
    result=[label]
    # Carrier rows can explicitly provide both a brand and its generic expression.
    # Query the printed brand with the printed form/strength, without inventing either.
    if ' - ' in label:
        brand,generic=label.split(' - ',1)
        form=re.search(r'\b(?:tab|tablet|cap|capsule|soln|solution|susp|suspension|inj|injection|aerosol|cream|gel|patch|powder)\b',generic,re.I)
        if form:result.append(brand+' '+generic[form.start():])
    # Remove a parenthetical brand annotation only when the surrounding generic
    # product expression remains complete. It is an alias query, not substitution.
    if re.search(r'\((?:generic|base equiv)',label,re.I):
        result.append(re.sub(r'\s*\((?:generic|base equiv)[^)]*\)','',label,flags=re.I))
    return list(dict.fromkeys(result))


def extract(document,source,forms):
    text=(ROOT/source['text_path']).read_text();pages=text.split('\f');rows=[]
    for page_no,page in enumerate(pages,1):
        lines=page.splitlines();header=next((l for l in lines if re.search(r'Drug\s+name',l,re.I) and re.search(r'Drug\s+tier',l,re.I) and 'Requirements' in l),None)
        if not header:continue
        tier_col=re.search(r'Drug\s+tier',header,re.I).start();req_col=header.index('Requirements')
        current=None
        for line_no,line in enumerate(lines,1):
            left=line[:tier_col].strip();tier=line[tier_col:req_col].strip();right=line[req_col:].strip()
            flexible=re.fullmatch(r'\s*(.+?)\s{2,}([1-6])(?:\s{2,}(.*)|\s*)',line)
            if flexible:left,tier,right=flexible[1].strip(),flexible[2],flexible[3] or ''
            if re.fullmatch(r'[1-6]',tier) and left:
                current={'source_id':document,'pdf_page':page_no,'line_start':line_no,'line_end':line_no,'product_label':left,'tier':tier,'limit_text':right,'raw_lines':[line],'formulary_ids':forms};rows.append(current)
            elif current and left and (re.search(r'\d',left) or re.match(r'^(?:ml\b|release|extended|delayed|hydrochloride|sodium|capsule|tablet|suspension|solution|inhalation|inject|oral|acetate|powder)\b',left,re.I)) and not re.search(r'Updated|You can find|Note:|2026 B2|^page\b|\bFormulary\b',left,re.I):
                current['product_label']+=' '+left;current['limit_text']+=' '+right;current['raw_lines'].append(line);current['line_end']=line_no
            elif current and not left and right and 'QL' in current['limit_text']:
                current['limit_text']+=' '+right;current['raw_lines'].append(line);current['line_end']=line_no
    output=[]
    for r in rows:
        # The unit is copied only from the carrier's own explicit statement.
        matches=re.findall(r'QL\s*\(\s*(\d+(?:\.\d+)?)\s+([A-Za-z][A-Za-z .-]*?)\s*(?:/|per)\s*(\d+)\s+days?\s*\)',r['limit_text'],re.I)
        if len(matches)!=1:continue
        amount,unit,days=matches[0]
        norm={'mls':'mL','ml':'mL','ea':'each','gm':'g','gms':'g','grams':'g','tablets':'tablets','capsules':'capsules','patches':'patches','units':'units','syringes':'syringes','pens':'pens','vials':'vials','inhalers':'inhalers','packets':'packets','doses':'doses'}.get(unit.strip().lower())
        if norm is None:continue
        # Retain the complete contiguous span, including blank/context lines.
        r['raw_lines']=pages[r['pdf_page']-1].splitlines()[r['line_start']-1:r['line_end']]
        output.append({**r,'statement_id':document+':'+str(r['pdf_page'])+':'+str(r['line_start']),'amount':amount,'unit':norm,'unit_raw':unit.strip(),'days':int(days),'query_products':products(r['product_label'])})
    return output


def prepare(out,suffix=''):
    old=read(BASE/'supplemental-r1/source-manifest.json')['sources'];new=read(out/'acquisition/source-manifest.json')['sources']
    specs=[('florida-blue-medicare-forms-2026-formulary-fbm2600.pdf',['00026252']),('florida-blue-medicare-forms-2026-formulary-fbm2601.pdf',['00026250','00026422']),('aetna-fl-2026-formulary',['00026010'])]
    statements=[]
    for ident,forms in specs:statements.extend(extract(ident,(new|old)[ident],forms))
    queries=sorted({p for r in statements for p in r['query_products']})
    entries=[{'id':'rxnorm-normalized-'+key(p),'url':'https://rxnav.nlm.nih.gov/REST/rxcui.json?'+urlencode({'name':p,'search':'1','allsrc':'0'}),'query_name':p,'match_mode':'NLM normalized identity search; approximate search=9 prohibited'} for p in queries]
    dump(out/('quantity-statements'+suffix+'.json'),statements);dump(out/('identity-query-entries'+suffix+'.json'),entries)
    return {'explicit_unit_statements':len(statements),'unique_exact_concept_queries':len(entries),'statements_by_source':dict(Counter(r['source_id'] for r in statements))}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);p.add_argument('--suffix',default='');a=p.parse_args();print(json.dumps(prepare(a.out.resolve(),a.suffix),indent=2))
