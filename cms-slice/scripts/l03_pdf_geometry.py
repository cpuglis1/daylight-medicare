"""Map retained PDF word coordinates to original page-view character offsets.

Coordinates partition source text only. Benefit values and CMS observations are
never inputs. Native text mismatch keeps the printed-text gutter fallback held.
"""
from __future__ import annotations
import collections,difflib,gzip,json,pathlib,re,subprocess,xml.etree.ElementTree as ET
from l03_semantic_clauses import clean


def pdf_words(path,cache):
    cache=pathlib.Path(cache)
    if cache.exists():return json.loads(gzip.decompress(cache.read_bytes()))
    run=subprocess.run(['pdftotext','-bbox',str(path),'-'],capture_output=True,check=True)
    root=ET.fromstring(run.stdout);pages=[]
    for page in root.iter():
        if not page.tag.endswith('page'):continue
        words=[]
        for word in page.iter():
            if word.tag.endswith('word')and word.text:
                words.append([float(word.get('xMin')),float(word.get('yMin')),float(word.get('xMax')),float(word.get('yMax')),word.text])
        pages.append(words)
    cache.parent.mkdir(parents=True,exist_ok=True)
    cache.write_bytes(gzip.compress(json.dumps(pages,separators=(',',':'),ensure_ascii=False).encode(),mtime=0))
    return pages


def native_line_cuts(text,words):
    """Return cuts for each physical line from matched PDF word positions."""
    if not words:return {'cuts':{},'method':'printed_text_gutter; native_page_has_no_words','matched_fraction':None}
    tokens=list(re.finditer(r'\S+',text));ordered=sorted(words,key=lambda w:(round(w[1],1),w[0]))
    keys=[clean(w[4])for w in ordered];original=[clean(m.group())for m in tokens]
    matcher=difflib.SequenceMatcher(None,original,keys,autojunk=False);mapped={};used=set()
    for match in matcher.get_matching_blocks():
        for i,j in zip(range(match.a,match.a+match.size),range(match.b,match.b+match.size)):
            mapped[i]=j;used.add(j)
    lines=text.splitlines(keepends=True);start=0;line_tokens=[]
    for line in lines:
        indices=[i for i,m in enumerate(tokens)if start<=m.start()<start+len(line)]
        line_tokens.append((start,line,indices));start+=len(line)
    by_word=collections.defaultdict(list)
    for j,w in enumerate(ordered):by_word[clean(w[4])].append(j)
    # A displaced right-column run can have a baseline a few points below the
    # left run. Match skipped words locally, retaining every original word.
    for _,line,indices in line_tokens:
        ys=sorted(ordered[mapped[i]][1]for i in indices if i in mapped)
        if not ys:continue
        y=ys[len(ys)//2]
        for i in indices:
            if i in mapped:continue
            candidates=[j for j in by_word[original[i]]if j not in used and abs(ordered[j][1]-y)<=8]
            if len(candidates)==1:mapped[i]=candidates[0];used.add(candidates[0])
    # Establish x boundaries from the actual printed cost-column header.
    header=[]
    for n,(_,line,indices)in enumerate(line_tokens[:30],1):
        if re.match(r'\s*(?:Chapter|2026\s+Evidence)',line,re.I):continue
        if not re.search(r'What\s+you\s+pay',line,re.I):continue
        for i in indices:
            if original[i].lower()=='what'and i in mapped:header.append(ordered[mapped[i]][0]-3)
        if header:break
    if not header:return {'cuts':{},'method':'no_native_printed_cost_header','matched_fraction':len(mapped)/max(1,len(tokens))}
    header=sorted(set(header));cuts={};held=[]
    for n,(offset,line,indices)in enumerate(line_tokens,1):
        if not indices:continue
        if re.match(r'\s*(?:Chapter|2026\s+Evidence|Y\d{4}|©)',line,re.I):continue
        ys=[ordered[mapped[i]][1]for i in indices if i in mapped]
        if len(ys)<len(indices)*.6 or max(ys)-min(ys)>14:
            held.append(n);continue
        line_cuts=[];complete=True
        for boundary in header:
            right=[i for i in indices if i in mapped and ordered[mapped[i]][0]>=boundary]
            left=[i for i in indices if i in mapped and ordered[mapped[i]][0]<boundary]
            if right:
                cut=tokens[min(right)].start()-offset
                if left and max(left)>min(right):complete=False;break
            else:cut=len(line.rstrip('\r\n'))
            line_cuts.append(cut)
        if complete:cuts[n]=line_cuts
        else:held.append(n)
    return {'cuts':cuts,'native_x_boundaries':header,'method':'native_PDF_word_coordinates_with_exact_view_token_binding',
            'matched_fraction':len(mapped)/max(1,len(tokens)),'fallback_lines':held}


def bind_page_words(text,native_words,document_sha256,page,ocr_directory):
    path=pathlib.Path(ocr_directory)/f"{document_sha256}-{page}.json.gz"
    if path.exists():
        ocr=json.loads(gzip.decompress(path.read_bytes()))
        result=native_line_cuts(text,ocr["words"])
        result["method"]=result["method"].replace("native_PDF_word_coordinates","OCR_word_coordinates")
        result["word_position_source"]={"method":ocr["method"],"render_sha256":ocr["render_sha256"],"tsv_sha256":ocr["tsv_sha256"]}
        return result
    return native_line_cuts(text,native_words)
