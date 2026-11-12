"""Source-preserving L12 extraction and explicit prior-evidence reuse."""
from html.parser import HTMLParser
import hashlib
import json
from pathlib import Path
import re
import subprocess
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'docs/data/l12-help-with-costs-2026-10-28'
ACQ=BASE/'acquisition-r1'


def norm(s):return ' '.join(s.split())
def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,x):Path(p).write_text(json.dumps(x,indent=2,sort_keys=True)+'\n')


class PublicHTML(HTMLParser):
    def __init__(self):
        super().__init__();self.parts=[];self.skip=0;self.tables=[];self.table_stack=[]
        self.row=None;self.cell=None;self.heading='';self.hparts=None;self.links=[];self.link=None
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if tag in ['script','style','noscript']:self.skip+=1
        if self.skip:return
        if tag in ['p','div','li','br','tr','td','th','h1','h2','h3','h4','h5']:self.parts.append('\n')
        if tag in ['h1','h2','h3','h4','h5']:self.hparts=[]
        if tag=='table':
            t={'table_one_based':len(self.tables)+1,'preceding_heading':self.heading,'rows':[]}
            self.tables.append(t);self.table_stack.append(t)
        if tag=='tr' and self.table_stack:self.row=[]
        if tag in ['td','th'] and self.row is not None:self.cell=[]
        if tag=='a':self.link={'url':attrs.get('href'),'parts':[]}
    def handle_endtag(self,tag):
        if tag in ['script','style','noscript']:
            self.skip=max(0,self.skip-1);return
        if self.skip:return
        if tag in ['h1','h2','h3','h4','h5'] and self.hparts is not None:
            self.heading=norm(''.join(self.hparts));self.hparts=None
        if tag in ['td','th'] and self.cell is not None:
            self.row.append(norm(''.join(self.cell)));self.cell=None
        if tag=='tr' and self.row is not None:
            if any(self.row) and self.table_stack:self.table_stack[-1]['rows'].append(self.row)
            self.row=None
        if tag=='table' and self.table_stack:self.table_stack.pop()
        if tag=='a' and self.link is not None:
            self.link['text']=norm(''.join(self.link.pop('parts')));self.links.append(self.link);self.link=None
        if tag in ['p','div','li','tr','td','th','h1','h2','h3','h4','h5']:self.parts.append('\n')
    def handle_data(self,data):
        if self.skip:return
        self.parts.append(data)
        if self.cell is not None:self.cell.append(data)
        if self.hparts is not None:self.hparts.append(data)
        if self.link is not None:self.link['parts'].append(data)
    def result(self):
        return {'lines':[norm(x) for x in ''.join(self.parts).splitlines() if norm(x)],
                'tables':self.tables,'links':self.links}


def extract():
    if (BASE/'build-r1/manifest.json').exists():raise ValueError('Sealed revision')
    (ACQ/'text').mkdir(exist_ok=True);index={}
    for p in sorted((ACQ/'receipts').glob('*.json')):
        r=json.loads(p.read_text());r['receipt_path']=str(p.relative_to(ROOT));index[r['id']]=r
        if r['status']!='retained':continue
        raw=ROOT/r['path']
        if digest(raw)!=r['sha256']:raise ValueError('Changed raw evidence')
        data=raw.read_bytes()
        if r.get('content_type','').startswith('application/msword'):
            text=subprocess.run(['textutil','-convert','txt','-stdout',str(raw)],check=True,capture_output=True).stdout.decode()
            out=ACQ/'text'/(r['id']+'.txt');out.write_text(text)
            r['text_path']=str(out.relative_to(ROOT));r['extraction_kind']='word_textutil'
        elif 'xml' in r.get('content_type',''):
            tree=ET.fromstring(data);sections=[]
            for node in tree.iter('DIV8'):
                sections.append({'section':node.get('N'),'heading':norm(''.join(node.find('HEAD').itertext())) if node.find('HEAD') is not None else '',
                                 'text':norm(' '.join(node.itertext()))})
            out=ACQ/'text'/(r['id']+'.json');write(out,{'sections':sections})
            plain=ACQ/'text'/(r['id']+'.txt');plain.write_text('\n'.join(s['text'] for s in sections)+'\n')
            r['structured_text_path']=str(out.relative_to(ROOT));r['text_path']=str(plain.relative_to(ROOT));r['extraction_kind']='ecfr_xml_sections'
        elif data.startswith(b'%PDF'):
            text=subprocess.run(['pdftotext','-layout',str(raw),'-'],check=True,capture_output=True).stdout.decode()
            out=ACQ/'text'/(r['id']+'.txt');out.write_text(text)
            r['text_path']=str(out.relative_to(ROOT));r['pdf_pages']=len(text.split('\f'))-1
            r['extraction_kind']='native_pdf_text'
            if r['id']=='dcf-a9-current':
                image=ACQ/'text/dcf-a9-current.png'
                subprocess.run(['pdftoppm','-f','1','-l','1','-r','200','-singlefile','-png',str(raw),str(image.with_suffix(''))],check=True,capture_output=True)
                ocr=subprocess.run(['tesseract',str(image),'stdout','-l','eng','--psm','6'],check=True,capture_output=True).stdout.decode()
                op=ACQ/'text/dcf-a9-current-ocr.txt';op.write_text(ocr)
                r['ocr_path']=str(op.relative_to(ROOT));r['render_path']=str(image.relative_to(ROOT))
                r['ocr_method']='pdftoppm200dpi_tesseract_eng_psm6; native font mapping is corrupt; visual review required'
        else:
            parser=PublicHTML();parser.feed(raw.read_text(errors='replace'));result=parser.result()
            out=ACQ/'text'/(r['id']+'.json');write(out,result)
            r['structured_text_path']=str(out.relative_to(ROOT));r['extraction_kind']='html_lines_tables_links'
            plain=ACQ/'text'/(r['id']+'.txt');plain.write_text('\n'.join(result['lines'])+'\n');r['text_path']=str(plain.relative_to(ROOT))
    # Reuse exact already-acquired DCF bytes without altering L01.
    parent=ROOT/'docs/data/l01-national-2026/r1';sid='dcf-a91-reused'
    original=parent/'raw/1670dac404ea9281b69829088315b76f904708d65f255fb3afe81708cd14274e'
    receipt=parent/'acquisitions/2026-10-25T174341.733456+0000/DCF-59106.json'
    r=json.loads(receipt.read_text())
    if digest(original)!=r['sha256']:raise ValueError('Changed L01 source')
    output=ACQ/'text'/f'{sid}.txt'
    fresh=subprocess.run(['pdftotext','-layout',str(original),'-'],check=True,capture_output=True).stdout.decode()
    output.write_text(fresh)
    index[sid]={'id':sid,'url':r['url'],'status':'retained','path':str(original.relative_to(ROOT)),
                'sha256':r['sha256'],'bytes':original.stat().st_size,'receipt_path':str(receipt.relative_to(ROOT)),
                'text_path':str(output.relative_to(ROOT)),'pdf_pages':1,'reused_from':'L01 historical broad inventory',
                'retrieved_at_utc':r['retrieved_at_utc'],'extraction_kind':'native_pdf_text'}
    write(ACQ/'extraction-index.json',index)
    print(json.dumps({'sources':len(index),'retained':sum(s['status']=='retained' for s in index.values()),
                      'pdf_pages':sum(s.get('pdf_pages',0) for s in index.values())}))


if __name__=='__main__':extract()
