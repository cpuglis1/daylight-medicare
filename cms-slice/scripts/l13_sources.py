"""Extract only L13 enrollment evidence; never rewrite parent artifacts."""
import json
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET
from l12_sources import PublicHTML,norm,digest,write

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'docs/data/l13-enrollment-2026-10-28'
ACQ=BASE/'acquisition-r1'

def extract():
    if (BASE/'build-r1/manifest.json').exists():raise ValueError('Sealed L13')
    (ACQ/'text').mkdir(exist_ok=True);index={}
    records=[]
    for p in sorted((ACQ/'receipts').glob('*.json')):
        r=json.loads(p.read_text());r['receipt_path']=str(p.relative_to(ROOT));records.append(r)
    records+=json.loads((BASE/'reuse-inputs.json').read_text())
    for r in records:
        index[r['id']]=r
        if r['status']!='retained':continue
        raw=ROOT/r['path'];assert digest(raw)==r['sha256'];data=raw.read_bytes()
        out=ACQ/'text'/(r['id']+'.txt')
        if data.startswith(b'%PDF'):
            text=subprocess.run(['pdftotext','-layout',str(raw),'-'],check=True,capture_output=True).stdout.decode()
            r.update(extraction_kind='native_pdf_text',pdf_pages=text.count('\f'))
        elif 'xml' in (r.get('content_type') or '') or data.lstrip().startswith(b'<?xml'):
            tree=ET.fromstring(data);sections=[{'section':n.get('N'),'text':norm(' '.join(n.itertext()))} for n in tree.iter('DIV8')]
            structured=ACQ/'text'/(r['id']+'.json');write(structured,{'sections':sections})
            text='\n'.join(x['text'] for x in sections)+'\n';r.update(extraction_kind='ecfr_xml_sections',structured_text_path=str(structured.relative_to(ROOT)))
        elif 'json' in (r.get('content_type') or ''):
            structured=ACQ/'text'/(r['id']+'.json');value=json.loads(data);write(structured,value)
            text=json.dumps(value,indent=2,sort_keys=True)+'\n';r.update(extraction_kind='public_json',structured_text_path=str(structured.relative_to(ROOT)))
        else:
            parser=PublicHTML();parser.feed(data.decode(errors='replace'));value=parser.result()
            structured=ACQ/'text'/(r['id']+'.json');write(structured,value)
            text='\n'.join(value['lines'])+'\n';r.update(extraction_kind='html_lines_tables_links',structured_text_path=str(structured.relative_to(ROOT)))
        out.write_text(text);r['text_path']=str(out.relative_to(ROOT))
    write(ACQ/'extraction-index.json',index)
    print(json.dumps({'sources':len(index),'retained':sum(x['status']=='retained' for x in index.values()),'PDF_pages':sum(x.get('pdf_pages',0) for x in index.values())}))

if __name__=='__main__':extract()
