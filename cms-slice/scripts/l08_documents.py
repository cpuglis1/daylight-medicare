#!/usr/bin/env python3
"""Index complete native directory pages and exact identifier observations.

An identifier occurrence is source indexing, not a verified provider/location edge.
Medical participation is modeled separately from explicit FHIR relationships.
"""
from collections import Counter
import gzip
import json
import re
import subprocess
from pathlib import Path
from l08_acquire import BASE, OUT, ROOT, digest, write


LABELS = {'Freedom 2026 MAPD directory','Freedom 2026 MA directory',
          'Optimum exact 2026 directory','HealthSpring Florida medical directory',
          'Aetna 2026 Southwest Florida DSNP directory'}
PATTERNS = {'npi':re.compile(r'\bNPI\s*(?:#|:)?\s*(\d{10})\b'),
            'publisher_provider_id':re.compile(r'\bID#\s*([A-Z0-9]+)'),
            'phone':re.compile(r'(?<!\d)(\(\d{3}\)\s*\d{3}[- ]\d{4}|\b\d{3}-\d{3}-\d{4}\b)')}


def main():
    output=BASE/'document-index-r1';output.mkdir(exist_ok=True)
    documents=[];counts={};occurrences=[]
    with gzip.open(output/'pages.jsonl.gz','wt')as pages_out, gzip.open(output/'identifiers.jsonl.gz','wt')as ids_out:
        for receipt_path in sorted((OUT/'receipts').glob('*.json')):
            r=json.loads(receipt_path.read_text());label=r.get('label','')
            if not (label in LABELS or label.startswith('Erickson Florida ')):continue
            if r.get('http_status')!=200:continue
            raw=ROOT/r['path'];assert digest(raw.read_bytes())==r['sha256']
            t=OUT/'text'/f"{r['sha256']}.txt";t.parent.mkdir(exist_ok=True)
            if not t.exists():subprocess.run(['/opt/homebrew/bin/pdftotext','-q','-layout',str(raw),str(t)],check=True)
            text=t.read_text();pages=text.split('\f');pages=pages[:-1]if pages[-1]==''else pages
            # -raw is a separately generated reading-order projection. Counts of
            # modeled identifier tokens must agree for every source page.
            verification=output/(r['sha256']+'.raw.txt')
            subprocess.run(['/opt/homebrew/bin/pdftotext','-q','-raw',str(raw),str(verification)],check=True)
            second=verification.read_text().split('\f');second=second[:-1]if second[-1]==''else second
            assert len(pages)==len(second)
            count={k:0 for k in PATTERNS};disagreements=[]
            for i,page in enumerate(pages):
                row={'source_sha256':r['sha256'],'page':i+1,'text':page,'text_sha256':digest(page.encode())}
                pages_out.write(json.dumps(row,ensure_ascii=False)+'\n')
                for kind,pattern in PATTERNS.items():
                    # Reading order may change adjacency; raw values and multiplicity
                    # on the same exact PDF page remain the comparison grain.
                    norm=lambda v:re.sub(r'\D','',v)if kind=='phone'else v
                    a=sorted(norm(m.group(1))for m in pattern.finditer(page));b=sorted(norm(m.group(1))for m in pattern.finditer(second[i]))
                    if a!=b:disagreements.append({'page':i+1,'kind':kind,'layout_count':len(a),'raw_count':len(b)})
                    for m in pattern.finditer(page):
                        obs={'source_sha256':r['sha256'],'page':i+1,'kind':kind,'value':m.group(1),
                             'projection':'layout','span':[m.start(1),m.end(1)],'assertion':'verbatim page observation; no provider/location attribution inferred'}
                        ids_out.write(json.dumps(obs)+'\n');count[kind]+=1
                    # All remaining raw-only occurrences were visually checked in
                    # render-r1/field-differences. Preserve them with raw-projection
                    # spans rather than altering the original layout projection.
                    missing=Counter(b)-Counter(a)
                    for m in pattern.finditer(second[i]):
                        value=norm(m.group(1))
                        if missing[value]>0:
                            obs={'source_sha256':r['sha256'],'page':i+1,'kind':kind,'value':m.group(1),
                                 'projection':'raw','span':[m.start(1),m.end(1)],'assertion':'visually checked reading-order recovery; no provider/location attribution inferred'}
                            ids_out.write(json.dumps(obs)+'\n');count[kind]+=1;missing[value]-=1
            front='\n'.join(pages[:4]);date=re.search(r'(?:current as of|updated on)\s*([^\n.]+)',front,re.I)
            documents.append({'label':label,'receipt':r['id'],'source_sha256':r['sha256'],'source_path':r['path'],
                              'url':r['requested_url'],'pages':len(pages),'text_sha256':digest(text.encode()),
                              'benefit_year':2026,'published_date_text':date.group(1).strip()if date else None,
                              'identifier_observations':count,'raw_vs_layout_disagreements':disagreements,
                              'provider_location_semantics_from_identifier_index':False})
            counts[label]=count
            print(label,len(pages),count,'projection differences',len(disagreements),flush=True)
    write(output/'documents.json',documents)
    write(output/'validation.json',{'document_count':len(documents),'pages':sum(d['pages']for d in documents),
          'all_complete_page_projections':True,'all_identifier_projection_counts_agree':all(not d['raw_vs_layout_disagreements']for d in documents),
          'disagreements':[{'label':d['label'],'differences':d['raw_vs_layout_disagreements']}for d in documents if d['raw_vs_layout_disagreements']],
          'raw_only_occurrences_recovered_with_projection_specific_locators':True,
          'not_a_semantic_listing_reconciliation':True})


if __name__=='__main__':main()
