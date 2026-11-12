"""Retain all owner files, unique PDF bytes, complete text and XML geometry."""
import collections,gzip,json,re,shutil,subprocess,xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
from l08_r5_common import ROOT,HOME,PARENT,BASE,write,digest,filehash,assert_open

def extract(x):
    sh=x['sha256'];src=ROOT/x['path'];tp=BASE/'text'/(sh+'.txt');xp=BASE/'xml'/(sh+'.xml')
    info=subprocess.check_output(['pdfinfo',str(src)],text=True)
    subprocess.run(['pdftotext','-layout',str(src),str(tp)],check=True,capture_output=True)
    subprocess.run(['pdftohtml','-xml','-hidden','-zoom','1',str(src),str(xp)],check=True,capture_output=True)
    pages=int(re.search(r'^Pages:\s+(\d+)',info,re.M)[1]);texts=tp.read_text().split('\f');assert len(texts)==pages+1 and not texts[-1].strip()
    fonts={};nodes=[];images=[];pc=0
    for _,page in ET.iterparse(xp,events=['end']):
        if page.tag!='page':continue
        pc+=1;pn=int(page.attrib['number'])
        for f in page.findall('fontspec'):fonts[f.attrib['id']]=dict(f.attrib)
        for j,e in enumerate(page.findall('text')):
            t=''.join(e.itertext()).strip()
            if t:nodes.append({'page':pn,'node':j,'text':t,'top':float(e.attrib['top']),'left':float(e.attrib['left']),
                 'width':float(e.attrib['width']),'height':float(e.attrib['height']),'font':fonts[e.attrib['font']],
                 'bold':e.find('b')is not None,'italic':e.find('i')is not None})
        for j,e in enumerate(page.findall('image')):
            p=__import__('pathlib').Path(e.attrib['src'])
            if not p.is_absolute():p=xp.parent/p.name
            images.append({'page':pn,'node':j,'attributes':dict(e.attrib),'path':str(p.relative_to(ROOT)),
                'sha256':filehash(p),'bytes':p.stat().st_size})
        page.clear()
    assert pc==pages
    native=BASE/'native'/(sh+'.jsonl.gz')
    with gzip.open(native,'wt')as out:
        for n in nodes:out.write(json.dumps(n,ensure_ascii=False)+'\n')
    with gzip.open(xp.with_suffix('.xml.gz'),'wb')as out:out.write(xp.read_bytes())
    xp.unlink()
    cover=texts[0];names=[t.strip()for t in cover.splitlines()if t.strip().startswith('Wellcare')and not t.strip().startswith(('Wellcare Member','Wellcare By'))]
    match=re.search(r'This directory is current as of (\d{2}/\d{2}/2026)',cover);assert match
    assert re.match(r'\s*2026\b',cover)and'Collier'in cover and'Medicare Advantage Plan'in cover
    x.update(pages=pages,benefit_year=2026,published_as_of=match[1],cover_plan_names=names,
       text_path=str(tp.relative_to(ROOT)),text_sha256=filehash(tp),xml_path=str(xp.with_suffix('.xml.gz').relative_to(ROOT)),
       xml_sha256=filehash(xp.with_suffix('.xml.gz')),native_path=str(native.relative_to(ROOT)),native_sha256=filehash(native),native_nodes=len(nodes),
       image_objects=images,source_partial_explicit=bool(re.search(r'more providers(?: and\s+pharmacies)?\s+available.*?not listed in this directory',' '.join(texts[:4]),re.S)),
       printed_CMS_ID_mentions=sorted(set(re.findall(r'\bH\d{4}[-_ ]\d{3}\b','\f'.join(texts)))),pdfinfo=info)
    return x

def main():
    assert_open()
    for d in ['intake','text','xml','native','render']:(BASE/d).mkdir(exist_ok=True)
    owners=[];unique={}
    for p in sorted((ROOT/'plans').glob('509*')):
        if p.suffix.lower()!='.pdf':continue
        sh=filehash(p);assert p.read_bytes()[:5]==b'%PDF-'
        target=BASE/'intake'/p.name;shutil.copyfile(p,target)
        owners.append({'owner_path':str(p),'retained_path':str(target.relative_to(ROOT)),'filename':p.name,'sha256':sh,'bytes':p.stat().st_size,
            'received_at_utc':datetime.now(timezone.utc).isoformat(),'origin':'owner_supplied_download','official_server_bytes_independently_compared':False})
        unique.setdefault(sh,{'sha256':sh,'path':str(target.relative_to(ROOT)),'owner_filenames':[]})['owner_filenames'].append(p.name)
    assert len(owners)==6 and len(unique)==4
    write(BASE/'owner-file-observations.json',owners)
    inv=list(ThreadPoolExecutor(max_workers=2).map(extract,unique.values()));write(BASE/'document-inventory.json',inv)
    write(BASE/'authorization.json',{'owner_request':'Wellfare downloaded. in the path, look for 509 prefix to help narrow down. nice job',
       'continued_scope':'L08 published 2026 Collier provider directories; local intake, normalization and validation; no UI, recommendations or source-stop retry',
       'owner_input_directory':'/Users/cep4u/daylight/plans','date':'2026-10-28','duplicate_files_retained':True,'source_acceptance_inherited':False})
    print(json.dumps({'owner_files':len(owners),'unique_PDFs':len(inv),'pages':sum(x['pages']for x in inv),'native_nodes':sum(x['native_nodes']for x in inv),
        'documents':[{'file':x['owner_filenames'][0],'pages':x['pages'],'names':x['cover_plan_names'],'partial':x['source_partial_explicit'],'images':len(x['image_objects'])}for x in inv]}),flush=True)

if __name__=='__main__':main()
