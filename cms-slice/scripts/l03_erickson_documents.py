"""Additive r7 owner document intake; never rewrites sealed r1-r6 evidence."""
from __future__ import annotations
import datetime, gzip, pathlib, re, shutil
from l03_user_documents import sha, load, dump, rows, write_rows, ocr_layout, shared_wellcare_view

REPO=pathlib.Path(__file__).resolve().parents[2]
DATA=REPO/'docs/data/l03-ma-benefits-2026-10-25'
ROOT=DATA/'source-reconciliation-r7'
R1=DATA/'build-r1'; R2=DATA/'reconciliation-r2'; R3=DATA/'reconciliation-r3'
R6=DATA/'source-reconciliation-r6'
PACKAGE='L03-SOURCE-RECONCILIATION-COLLIER-2026-r7'
LOCATORS={
 '001':('signature-summary-en.pdf','signature-eoc-en.pdf'),
 '002':('LibNoRx-summary-en.pdf','LibertyNoRx-eoc-en.pdf'),
 '004':('champion-summary-en.pdf','champion-eoc-en.pdf'),
 '006':('freedom-summary-en.pdf','freedom-eoc-en.pdf'),
 '008':('liberty-summary-en.pdf','liberty-eoc-en.pdf'),
}

def intake(inventory):
    if (ROOT/'manifest.json').exists():raise RuntimeError('Sealed r7 is immutable')
    ROOT.mkdir(exist_ok=True)
    raw=ROOT/'acquisition/raw';textdir=ROOT/'acquisition/text'
    raw.mkdir(parents=True,exist_ok=True);textdir.mkdir(parents=True,exist_ok=True)
    inv=load(inventory);sources=load(R6/'source-catalog.json');relations=load(R6/'document-relations.json')
    added_pages=[]
    for item in inv['items']:
        h=item['sha256'];original=pathlib.Path(item['original_path'])
        assert sha(original.read_bytes())==h
        match=re.search(r'H5652(\d{3})000_(SB|EOC)_',item['file_name']);assert match,item['file_name']
        plan,kind=match.groups();oid=f'2026:H5652:{plan}:000'
        dest=raw/h
        if not dest.exists():shutil.copyfile(original,dest)
        assert sha(dest.read_bytes())==h
        pages=[]
        for n in range(1,item['pages']+1):
            with gzip.open(pathlib.Path(inventory).parent/'ocr'/h/f'{n:04d}.json.gz','rt')as f:p=__import__('json').load(f)
            assert p['document_sha256']==h and p['pdf_page']==n
            layout=ocr_layout(p)
            pages.append({'document_sha256':h,'pdf_page':n,'text':p['text'],'text_sha256':sha(p['text'].encode()),'layout_text':layout,'layout_text_sha256':sha(layout.encode()),'ocr_words':p['words'],'extraction_method':p['method'],'source_kind':kind})
        body='\f'.join(p['text']for p in pages);tp=textdir/(h+'.txt');tp.write_text(body)
        cover='\n'.join(p['text']for p in pages[:8]);identity=bool(re.search(rf'H5652[\s_\-]*{plan}[\s_\-]*000',cover))
        year='2026'in pages[0]['text'];assert identity and year,(oid,kind)
        sources.append({'id':'L03-R7-DOC-'+h[:16],'sha256':h,'path':str(dest),'text_path':str(tp),'text_sha256':sha(body.encode()),'pdf_pages':len(pages),'document_kind':kind,'original_file_names':[item['file_name']],'original_paths':[str(original)],'origin':'owner_supplied_local_download','received_at_utc':inv['recorded_at_utc'],'observed_official_locators':['https://media.ericksonliving.com/ea/2026/Plans/'+LOCATORS[plan][kind=='EOC']],'official_server_bytes_independently_compared':False,'extraction_method':'render150dpi_tesseract5_eng_psm3','raw_native_text_usable':False,'OCR_is_not_semantic_validation':True,'year_2026_in_front_matter':year,'owning_layer':'L03','accepted_for_reference':False})
        relations.append({'offering_id':oid,'kind':kind,'document_sha256':h,'visible_front_matter_identity_match':identity,'identity_verification_method':'rendered_OCR_front_matter; original_pixels_retained','visible_year_match':year,'collier_present_in_document':bool(re.search(r'\bCollier\b',body,re.I)),'geography_basis':'Exact national H5652 plan/segment and pinned L02 Collier membership; do not infer open enrollment or residence eligibility.','source_basis':'owner-supplied bytes; official locator is not a byte identity assertion','state':'identity_matched_for_reconciliation','acceptance_inherited':False})
        added_pages.extend(pages)
    assert len(sources)==53 and len({d['sha256']for d in sources})==53
    dump(ROOT/'source-catalog.json',sources);dump(ROOT/'document-relations.json',relations)
    old=load(R6/'owner-file-observations.json')
    dump(ROOT/'owner-file-observations.json',{'recorded_at_utc':inv['recorded_at_utc'],'files':old['files']+[{k:x[k]for k in ['file_name','original_path','sha256','bytes','pages']}for x in inv['items']],'unique_bytes':len(sources),'duplicate_files':1,'prior_evidence_manifest_sha256':sha((R6/'manifest.json').read_bytes())})
    write_rows(ROOT/'new-source-pages.jsonl.gz',__import__('itertools').chain(rows(R6/'new-source-pages.jsonl.gz'),added_pages))
    return sources,relations

if __name__=='__main__':
    import sys
    s,r=intake(pathlib.Path(sys.argv[1]));print({'sources':len(s),'relations':len(r)})
