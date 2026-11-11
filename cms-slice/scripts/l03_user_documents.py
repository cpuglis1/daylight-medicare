"""Additive L03 r6 intake of owner-supplied carrier PDFs.

Original documents and approved r1-r5 evidence are immutable. OCR, passage
location, source agreement, semantic verification and owner acceptance are
distinct states. No network access, deployment or production registry writes.
"""
from __future__ import annotations
import collections, datetime, gzip, hashlib, json, pathlib, re, shutil, statistics

REPO=pathlib.Path(__file__).resolve().parents[2]
DATA=REPO/'docs/data/l03-ma-benefits-2026-10-25'
ROOT=DATA/'source-reconciliation-r6'
R1=DATA/'build-r1'; R2=DATA/'reconciliation-r2'; R3=DATA/'reconciliation-r3'
PACKAGE='L03-SOURCE-RECONCILIATION-COLLIER-2026-r6'
def sha(b):return hashlib.sha256(b).hexdigest()
def load(p):return json.loads(pathlib.Path(p).read_text())
def dump(p,v):pathlib.Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
def rows(p):
    with gzip.open(p,'rt')as f:
        yield from (json.loads(l)for l in f)
def write_rows(p,rs):
    with gzip.GzipFile(filename=str(p),mode='wb',mtime=0)as f:
        for r in rs:f.write((json.dumps(r,ensure_ascii=False)+'\n').encode())

def intake(inventory,manual_links):
    if (ROOT/'manifest.json').exists():raise RuntimeError('Sealed r6 is immutable; create a new revision.')
    ROOT.mkdir(exist_ok=True)
    raw=ROOT/'acquisition/raw';text=ROOT/'acquisition/text'
    raw.mkdir(parents=True,exist_ok=True);text.mkdir(parents=True,exist_ok=True)
    inv=load(inventory); items=inv['items']; uniq={d['sha256']:d for d in items}
    uhc=load(R2/'uhc-rendered-document-discovery.json')
    wc=load(manual_links)['offerings']; sources=[]; relations=[]
    for h,d in sorted(uniq.items()):
        aliases=[x['file_name']for x in items if x['sha256']==h]
        original=pathlib.Path(d['original_path']);assert sha(original.read_bytes())==h
        dest=raw/h
        if not dest.exists():shutil.copyfile(original,dest)
        assert sha(dest.read_bytes())==h
        isuhc=bool(re.search(r'(?:AA|UH)FL26[HLR]P',d['file_name']))
        kind='SB'if 'Summary of Benefits' in d['file_name'] or '_SB_' in d['file_name']or '_SB2026'in d['file_name']else'EOC'if 'EOC'in d['file_name']or 'Explanation of Coverage'in d['file_name']else'prior_authorization_list'if 'PAL'in d['file_name']else'formulary'
        target=[];urls=[]
        for u in uhc:
            if kind in ['SB','EOC']and u[kind].split('/')[-1]in d['file_name']:
                target.append(u['offering_id']);urls.append(u[kind])
        for w in wc:
            if kind in ['SB','EOC']and any(w[kind].split('/')[-1].replace('.ashx','.pdf').lower()in name.lower()for name in aliases):
                target.append('2026:'+w['offering_id'].replace('-',':'));urls.append(w[kind])
        if 'H1609_078'in d['file_name']and kind in ['SB','EOC']:target.append('2026:H1609:078:000')
        tp=text/(h+'.txt')
        if isuhc:
            original_text=pathlib.Path(inventory).parent/'ocr'/(h+'.txt')
            if not original_text.exists():
                od=original_text.parent/h
                if not all((od/f'{n:04d}.json.gz').exists()for n in range(1,d['pages']+1)):continue
                parts=[]
                for n in range(1,d['pages']+1):
                    with gzip.open(od/f'{n:04d}.json.gz','rt')as f:parts.append(json.load(f)['text'])
                original_text.write_text('\f'.join(parts))
            body=original_text.read_text();method='render150dpi_tesseract5_eng_psm3'
        else:body=pathlib.Path(d['text_path']).read_text();method='pdftotext_layout'
        tp.write_text(body)
        parts=body.split('\f')
        if len(parts)==d['pages']+1 and not parts[-1].strip():parts.pop()
        assert len(parts)==d['pages'],(d['file_name'],len(parts),d['pages'])
        front='\n'.join(parts[:8]); content_ok='2026'in front
        source={'id':'L03-R6-DOC-'+h[:16],'sha256':h,'path':str(dest),'text_path':str(tp),'text_sha256':sha(body.encode()),'pdf_pages':d['pages'],'document_kind':kind,'original_file_names':[x['file_name']for x in items if x['sha256']==h],'original_paths':[x['original_path']for x in items if x['sha256']==h],'origin':'owner_supplied_local_download','owner_authorization':'I downloaded these! All here! bring L03 home to completion!! /Users/cep4u/daylight/plans','received_at_utc':inv['recorded_at_utc'],'observed_official_locators':sorted(set(urls)),'official_server_bytes_independently_compared':False,'extraction_method':method,'raw_native_text_usable':not isuhc,'OCR_is_not_semantic_validation':True,'year_2026_in_front_matter':content_ok,'owning_layer':'L05'if kind=='formulary'else'L03','commercial_redistribution_rights':'not established by receipt of a local file','accepted_for_reference':False}
        assert content_ok,d['file_name']
        sources.append(source)
        for o in sorted(set(target)):
            _,c,p,s=o.split(':')
            pat=rf'{c}[\s_\-|,]*(?:Plan\s*)?{p}[\s_\-|,]*{s}'
            # Exact segment has to be visibly present, never inferred from a file name.
            identity=bool(re.search(pat,front,re.I))
            bridge=None
            identity_method='literal_front_matter_text'
            if c=='H1609'and p=='078'and not identity:
                old=next(m for m in load(R1/'plan-document-matrix.json')if m['offering_id']==o)
                plan_pattern=rf'{c}[\s_\-‑|,]+{p}'
                identity=bool(re.search(plan_pattern,front))and old['national_pbp_segments_for_contract_plan']==['000']
                bridge='Printed contract-plan + unique segment 000 in pinned 2026 PBP; segment not printed in Aetna front matter.'if identity else None
            if h=='81aff66fda861514dde87902407150cbdfa1b526810becc57e7f4aa0d1e53f99'and o=='2026:R0759:001:000'and kind=='EOC':
                identity=True;identity_method='AI_visual_read_PDF_page_1';bridge='Rendered cover visibly reads Y0066_EOC_R0759_001_000_2026_C; OCR confuses the first zero with O. Original OCR retained without global substitution.'
            relations.append({'offering_id':o,'kind':kind,'document_sha256':h,'visible_front_matter_identity_match':identity,'identity_verification_method':identity_method,'identity_pattern':pat,'segment_bridge':bridge,'visible_year_match':content_ok,'collier_present_in_document':bool(re.search(r'\bCollier\b',body,re.I)),'source_basis':'owner-supplied bytes; observed official link retained as locator, not a byte provenance assertion','state':'identity_matched_for_reconciliation'if identity else'identity_needs_visual_review','acceptance_inherited':False})
    dump(ROOT/'source-catalog.json',sources);dump(ROOT/'document-relations.json',relations)
    dump(ROOT/'owner-file-observations.json',{'recorded_at_utc':inv['recorded_at_utc'],'files':[ {k:x[k]for k in ['file_name','original_path','sha256','bytes','pages']}for x in items],'unique_bytes':len(uniq),'duplicate_files':len(items)-len(uniq)})
    def page_rows():
        for d in sources:
            for n,t in enumerate(pathlib.Path(d['text_path']).read_text().split('\f')[:d['pdf_pages']],1):
                p={'document_sha256':d['sha256'],'pdf_page':n,'text':t,'text_sha256':sha(t.encode()),'extraction_method':d['extraction_method'],'source_kind':d['document_kind']}
                if not d['raw_native_text_usable']:
                    with gzip.open(pathlib.Path(inventory).parent/'ocr'/d['sha256']/f'{n:04d}.json.gz','rt')as f:ocr=json.load(f)
                    layout=ocr_layout(ocr);p.update(layout_text=layout,layout_text_sha256=sha(layout.encode()),ocr_words=ocr['words'])
                yield p
    write_rows(ROOT/'new-source-pages.jsonl.gz',page_rows())
    return sources,relations

def ocr_layout(r):
    """Make columns inspectable without substituting OCR for original pixels."""
    grouped=collections.defaultdict(list)
    for w in r['words']:grouped[(w['block_num'],w['par_num'],w['line_num'])].append(w)
    recognized=[{'y':statistics.median(w['top']+w['height']/2 for w in ws),'words':ws}for ws in grouped.values()]
    lines=[]
    # Keep recognized words in the same line before aligning parallel columns.
    # Individual ascenders/descenders must not split a heading such as Home
    # health agency care or move its middle word into the next row.
    for g in sorted(recognized,key=lambda z:z['y']):
        near=[z for z in lines if abs(z['y']-g['y'])<8]
        if near:min(near,key=lambda z:abs(z['y']-g['y']))['words'].extend(g['words'])
        else:lines.append(g)
    scale=9.0;out=[]
    for z in sorted(lines,key=lambda z:z['y']):
        line=''
        for w in sorted(z['words'],key=lambda w:w['left']):
            col=round(w['left']/scale);line+=' '*max(1,col-len(line))+w['text']
        out.append(line)
    return '\n'.join(out)

def shared_wellcare_view(text,oid):
    """Keep label + exact plan column. A single-plan assistance table stays whole."""
    target=oid.split(':')[2];ls=text.splitlines();matches=[]
    for l in ls:
        found=list(re.finditer(r'H1032,\s*Plan\s+(\d{3}),\s*000',l))
        if len(found)>1:matches=found;break
    if not matches:return text,{'shared_plan_columns':False,'other_columns_removed':False}
    chosen=next((i for i,m in enumerate(matches)if m.group(1)==target),None)
    if chosen is None:return '',{'shared_plan_columns':True,'exact_plan_absent':True}
    starts=[m.start()for m in matches];a=starts[chosen];b=starts[chosen+1]if chosen+1<len(starts)else None;label_end=starts[0]
    view='\n'.join(l[:label_end].rstrip()+' | '+l[a:b].rstrip()for l in ls)
    return view,{'shared_plan_columns':True,'selected_plan':target,'selected_column':chosen+1,'plan_header_positions':starts,'other_columns_removed':True,'full_original_page_retained':True}

if __name__=='__main__':
    import argparse
    a=argparse.ArgumentParser();a.add_argument('inventory',type=pathlib.Path);a.add_argument('manual_links',type=pathlib.Path);args=a.parse_args()
    s,r=intake(args.inventory,args.manual_links)
    print(json.dumps({'sources_ready':len(s),'document_relations':len(r),'identity_gaps':[x for x in r if not x['visible_front_matter_identity_match']]}))
