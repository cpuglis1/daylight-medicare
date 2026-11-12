"""Recover Aetna's explicitly shared name-block/site layout from retained pages.

The output is a source layout association, not a new person identity match or
an inference that every employee of a group participates at every practice.
"""
import gzip,json,re,sqlite3
from l08_r3_common import BASE,PARENT,write,assert_open

def main():
    assert_open();db=sqlite3.connect('file:'+str(PARENT/'followup-r2/providers.sqlite3')+'?mode=ro',uri=True)
    rs=[json.loads(x[0])for x in db.execute("select fields_json from pdf_records where family='aetna'")]
    sh=rs[0]['document_sha256'];lines=[]
    for line in gzip.open(PARENT/'followup-r2/pdf-records/source-lines.jsonl.gz','rt'):
        x=json.loads(line)
        if x['source_sha256']==sh:lines.append(x)
    assert all(x['index']==i for i,x in enumerate(lines))
    def name(x):return any(p['font']=='5'for p in x['parts'])
    def footer(x):return x['text'].startswith(('* Accepts Medicaid','§ Self-Designated','Before you make an appointment','your network.','rezo ou.'))
    units=[];i=0
    while i<len(lines):
        if not name(lines[i]):i+=1;continue
        start=i;i+=1
        while i<len(lines)and name(lines[i]):i+=1
        endnames=i
        while i<len(lines)and not name(lines[i])and not any(p['font']=='13'for p in lines[i]['parts']):i+=1
        body=lines[endnames:i]
        # Only bounded name runs with at least two credentialed printed names.
        # Preserve all lines without guessing each wrapped person's identity.
        raw=' '.join(x['text']for x in lines[start:endnames])
        creds=re.findall(r'\b(?:MD|MS|MC|MSN|MSW|LCSW|DO|PSYD|PHD|MED|LPC|AUD|NP|PA|DPM|DDS|DMD)\b',raw)
        if len(creds)<2 or endnames-start<3:continue
        if any(re.search(r'Provider ID:|Primary Care ID:',x['text'])for x in body):continue
        addresses=[]
        for j,x in enumerate(body):
            m=re.fullmatch(r'(.+?),\s*([A-Z]{2})\s+(\d{5}(?:-\d{4})?)',x['text'])
            if not m:continue
            preceding=[]
            for y in reversed(body[:j]):
                if footer(y):continue
                if y['text']=='or'or re.match(r'^\(\d{3}\)',y['text'])or ', FL 'in y['text']or'Provider Speaks:'in y['text']:break
                preceding.insert(0,y)
                if re.match(r'^\d+\s+\D',y['text']):break
            if not preceding or not re.match(r'^\d+\s+\D',preceding[0]['text']):continue
            phones=[y for y in body[j+1:j+3]if re.match(r'^\(\d{3}\)',y['text'])]
            addresses.append({'street_raw':' '.join(y['text']for y in preceding),'city_raw':m[1],'state_raw':m[2],'postal_raw':m[3],
                              'phone_raw':phones[0]['text']if phones else None,
                              'street_lines':[y['index']for y in preceding],'city_line':x['index'],'phone_line':phones[0]['index']if phones else None})
        if not addresses:continue
        covered=[]
        for r in rs:
            if r['addresses']or r.get('partial_addresses'):continue
            if r['name_source_lines']and set(r['name_source_lines'])<=set(range(start,endnames)):covered.append(r['id'])
        if not covered:continue
        units.append({'id':sh+':shared-name-block:'+str(start),'document_sha256':sh,'name_lines':list(range(start,endnames)),
                      'name_block_raw':[x['text']for x in lines[start:endnames]],'native_body_lines':list(range(endnames,i)),
                      'source_pages':sorted({x['page']for x in lines[start:i]}),'shared_addresses':addresses,
                      'parent_context_units':covered,'has_Collier_city_candidate':any(a['city_raw']in ['Naples','Immokalee','Marco Island','Ave Maria']for a in addresses),
                      'state':'published_shared_name_block_and_site; exact native layout association; individual identities not inferred',
                      'evidence_source':'followup-r2/pdf-records/source-lines.jsonl.gz','scope':'Original directory exact-plan applicability only; no participation transferred to other plans'})
    write(BASE/'published-shared-group-sites.json',units)
    write(BASE/'internal-association-summary.json',{'shared_name_blocks':len(units),'parent_context_units_with_explicit_shared_site':len({i for u in units for i in u['parent_context_units']}),
      'Collier_city_candidate_blocks':sum(x['has_Collier_city_candidate']for x in units),
      'Collier_city_candidate_parent_units':len({i for u in units if u['has_Collier_city_candidate']for i in u['parent_context_units']}),
      'all_parent_data_unchanged':True,'no_NPI_or_unique_person_invented':True})
    print((BASE/'internal-association-summary.json').read_text())

if __name__=='__main__':main()
