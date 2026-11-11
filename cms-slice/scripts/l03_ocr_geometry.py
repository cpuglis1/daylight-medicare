"""Recover word boxes for image-backed chart pages without CMS values."""
from __future__ import annotations
import argparse,concurrent.futures,csv,gzip,hashlib,io,json,os,pathlib,subprocess
from l03_inventory import DATA,load,rows,packed


def ocr_page(source,page,destination):
    destination=pathlib.Path(destination);h=source['sha256'];out=destination/f'{h}-{page}.json.gz'
    if out.exists():return json.loads(gzip.decompress(out.read_bytes()))
    command=['pdftoppm','-f',str(page),'-l',str(page),'-r','150','-singlefile','-png',source['path']]
    picture=subprocess.run(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True).stdout
    env={**os.environ,'OMP_THREAD_LIMIT':'1'}
    command2=['tesseract','stdin','stdout','-l','eng','--psm','3','tsv']
    tsv=subprocess.run(command2,input=picture,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env,check=True).stdout
    words=[]
    for row in csv.DictReader(io.StringIO(tsv.decode()),delimiter='\t'):
        text=row.get('text','').strip()
        if not text:continue
        x,y,w,hg=[float(row[k])*72/150 for k in ['left','top','width','height']]
        words.append([x,y,x+w,y+hg,text])
    record={'document_sha256':h,'pdf_page':page,'method':'render150dpi_tesseract5_eng_psm3_tsv',
            'render_sha256':hashlib.sha256(picture).hexdigest(),'tsv_sha256':hashlib.sha256(tsv).hexdigest(),
            'render_command':command,'ocr_command':command2,'words':words,'expected_CMS_amounts_provided':False}
    destination.mkdir(parents=True,exist_ok=True)
    out.write_bytes(gzip.compress(packed(record).encode(),mtime=0))
    (destination/f'{h}-{page}.tsv.gz').write_bytes(gzip.compress(tsv,mtime=0))
    return record


def batch(geometry,destination,workers=6):
    sources={x['document_sha256']:x['source']for x in load(DATA/'inventory-r8/source-index.json')}
    tasks=set()
    for row in rows(geometry):
        if row['coordinate_binding']['method']=='no_native_printed_cost_header':tasks.add((row['document_sha256'],row['pdf_page']))
    errors=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers)as pool:
        pending={pool.submit(ocr_page,sources[h],page,destination):(h,page)for h,page in sorted(tasks)}
        for done,future in enumerate(concurrent.futures.as_completed(pending),1):
            try:future.result()
            except Exception as e:errors.append([pending[future],str(e)])
            if done%25==0:print(f'OCR word-position pages {done}/{len(tasks)}; errors {len(errors)}',flush=True)
    return {'unique_pages':len(tasks),'errors':errors,'workers':workers}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--geometry',type=pathlib.Path,required=True);p.add_argument('--destination',type=pathlib.Path,required=True);p.add_argument('--workers',type=int,default=6)
    a=p.parse_args();print(json.dumps(batch(a.geometry,a.destination,a.workers),indent=2))
