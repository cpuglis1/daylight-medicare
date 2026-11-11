"""Exhaustive dispositions and further native-layout recovery for r2 PDF units."""
import collections,gzip,json,re,sqlite3
from l08_r4_common import ROOT,HOME,PARENT,BASE,write,assert_open

CITY=re.compile(r"^([A-Za-z][A-Za-z .’'\-]+),\s*([A-Z]{2})\s+(\d{5}(?:-\d{4})?)(?:\s*[⁰¹²³⁴⁵⁶⁷⁸⁹†‡*]+)?$")
CREDS=re.compile(r'\b(?:MD|MS|MC|MSN|MSW|LCSW|DO|PSYD|PHD|MED|LPC|AUD|NP|PA|DPM|DDS|DMD|APRN|ARNP|BSN|OD)\b')

def main():
    assert_open();db=sqlite3.connect('file:'+str(PARENT/'providers.sqlite3')+'?mode=ro',uri=True)
    records=[json.loads(s)for s, in db.execute("SELECT fields_json FROM pdf_records WHERE state NOT LIKE 'published_native%'")]
    aetna=[json.loads(s)for s, in db.execute("SELECT fields_json FROM pdf_records WHERE family='aetna'")]
    sh=aetna[0]['document_sha256'];lines=[];needed=collections.defaultdict(set)
    for r in records:
        lo,hi=r['native_line_range'];needed[r['document_sha256']].update(range(max(0,lo-4),hi+4))
    selected=collections.defaultdict(dict)
    for s in gzip.open(HOME/'followup-r2/pdf-records/source-lines.jsonl.gz','rt'):
        x=json.loads(s);doc=x['source_sha256'];n=x['index']
        if doc==sh:lines.append(x)
        if n in needed[doc]:selected[doc][n]=x
    assert all(x['index']==i for i,x in enumerate(lines))
    groups=[];byrecord={};r3groups=json.loads((PARENT/'published-shared-group-sites.json').read_text())
    for g in r3groups:
        groups.append({**g,'revision':'r4_retained_r3_source_layout'})
        for rid in g['parent_context_units']:byrecord[rid]=g['id']
    # Two credentialed name lines are a valid explicit shared name block too.
    i=0
    def name(x):return any(p['font']=='5'for p in x['parts'])
    while i<len(lines):
        if not name(lines[i]):i+=1;continue
        start=i;i+=1
        while i<len(lines)and name(lines[i]):i+=1
        end=i
        while i<len(lines)and not name(lines[i])and not any(p['font']=='13'for p in lines[i]['parts']):i+=1
        body=lines[end:i];raw=' '.join(x['text']for x in lines[start:end])
        if len(CREDS.findall(raw))<2:continue
        if any(re.search(r'Provider ID:|Primary Care ID:',x['text'])for x in body):continue
        covered=[r['id']for r in aetna if not r['addresses']and not r.get('partial_addresses')and r['name_source_lines']and set(r['name_source_lines'])<=set(range(start,end))and r['id']not in byrecord]
        if not covered:continue
        addresses=[]
        for j,x in enumerate(body):
            m=CITY.fullmatch(x['text'])
            if not m:continue
            street=[]
            for y in reversed(body[:j]):
                if y['text']=='or'or re.match(r'^\(\d{3}\)',y['text'])or ', FL 'in y['text']or'Provider Speaks:'in y['text']:break
                street.insert(0,y)
                if re.match(r'^\d+\s+\D',y['text']):break
            if not street or not re.match(r'^\d+\s+\D',street[0]['text']):continue
            addresses.append({'street_raw':' '.join(y['text']for y in street),'city_raw':m[1],'state_raw':m[2],'postal_raw':m[3],
                 'street_lines':[y['index']for y in street],'city_line':x['index']})
        if not addresses:continue
        g={'id':sh+':shared-name-block:'+str(start),'document_sha256':sh,'name_lines':list(range(start,end)),
            'name_block_raw':[x['text']for x in lines[start:end]],'native_body_lines':list(range(end,i)),
            'source_pages':sorted({x['page']for x in lines[start:i]}),'shared_addresses':addresses,'parent_context_units':covered,
            'state':'published_shared_name_block_and_site; individual identity not inferred','revision':'new_r4_two_name_block'}
        groups.append(g)
        for rid in covered:byrecord[rid]=g['id']
    # Aetna also prints group IDs followed by a bounded list of person IDs.
    # Retain the site's exact shared layout only when that group run contains
    # one distinct literal address. Do not merge the people's publisher IDs.
    def org(r):
        raw=r.get('provider_display_raw')or''
        return bool(re.search(r'Group|Associates|LLC|Inc\b|Medical|Clinic|Health|Center|Hospital',raw,re.I))and not(','in raw and CREDS.search(raw))
    run=[]
    def flush(run):
        if not run or not org(run[0]):return
        start,end=run[0]['native_line_range'][0],run[-1]['native_line_range'][1]
        # A publisher specialty boundary ends a practice run.
        if any(any(p['font']=='13'for p in lines[k]['parts'])for k in range(start,end)):return
        addrs=[a for r in run for a in r['addresses']]
        keys={(a['street_raw'],a['city'],a['state'],a['postal_code'])for a in addrs}
        if len(keys)!=1:return
        covered=[r['id']for r in run if not r['addresses']and not r.get('partial_addresses')and r['id']not in byrecord]
        if not covered:return
        a=addrs[0];loc=a['source_line_indices']
        g={'id':sh+':identified-practice-run:'+str(start),'document_sha256':sh,'name_lines':run[0]['name_source_lines'],
           'name_block_raw':[r.get('provider_display_raw')for r in run],
           'native_body_lines':list(range(start,end)),'source_pages':sorted({lines[k]['page']for k in range(start,end)}),
           'shared_addresses':[{'street_raw':a['street_raw'],'city_raw':a['city'],'state_raw':a['state'],'postal_raw':a['postal_code'],
             'street_lines':loc['street'],'city_line':loc['city_state_postal'],
             'city_lines':loc.get('city_state_postal_lines',[loc['city_state_postal']])}],
           'parent_context_units':covered,'member_listing_ids':[r['id']for r in run],
           'state':'bounded_published_practice_run_with_one_distinct_printed_site; source layout only; each publisher ID retained',
           'revision':'new_r4_identified_practice_layout'}
        groups.append(g)
        for rid in covered:byrecord[rid]=g['id']
    for r in sorted(aetna,key=lambda r:r['native_line_range'][0]):
        if org(r):flush(run);run=[r]
        elif run:run.append(r)
    flush(run)
    dispositions=[];counts=collections.Counter()
    for r in records:
        doc=r['document_sha256'];ls=selected[doc];lo,hi=r['native_line_range'];recovered=[]
        for k in range(lo,hi):
            x=ls[k];m=CITY.fullmatch(x['text'])
            if not m:continue
            street=[]
            for j in range(k-1,max(lo-1,k-5),-1):
                t=ls[j]['text']
                if re.search(r'^(ID#|NPI|Language|P:|F:|Provider ID|Primary Care ID)',t):break
                street.insert(0,j)
                if re.match(r'^(?:[⁰¹²³⁴⁵⁶⁷⁸⁹]+\s*)?\d+[A-Za-z]?\s+[A-Za-z]',t):break
            if not street or not re.match(r'^(?:[⁰¹²³⁴⁵⁶⁷⁸⁹]+\s*)?\d+[A-Za-z]?\s+[A-Za-z]',ls[street[0]]['text']):continue
            recovered.append({'street_raw':' '.join(ls[j]['text']for j in street),'city_raw':m[1],'state_raw':m[2],'postal_raw':m[3],
                'street_lines':street,'city_line':k,'city_line_raw':x['text'],'trailing_symbol_retained':x['text']!=m[1]+', '+m[2]+' '+m[3]})
        if r['id']in byrecord:state='explicit_shared_source_layout_site'
        elif recovered:state='direct_site_recovered_from_native_lines'
        elif r.get('addresses'):state='native_full_address_already_present'
        elif r.get('partial_addresses'):state='source_partial_site_retained; no_unique_full_site_in_this_unit'
        elif r['family']=='aetna'and org(r):state='published_group_header; no_unique_bounded_site_proved'
        elif r['family']=='aetna':state='source_name_or_identifier_entry; no_unique_bounded_site_proved'
        elif r['listing_domain']=='pharmacy_or_other_identifier':state='nonmedical_identifier_context; not_an_L08_clinician_gap'
        else:state='source_context_fragment; no_unique_bounded_site_proved'
        # Correct the blanket numeric-ID domain label for Aetna only where a
        # printed clinical section explicitly supports the domain.
        sections=[q['value_raw']for q in r.get('published_qualifiers',[])if q['kind']=='source_section_heading_raw']
        domain=r['listing_domain']
        if r['family']=='aetna'and sections and not any(re.search(r'Pharmac',s,re.I)for s in sections):domain='published_clinical_or_supplemental_section'
        out={'parent_record_id':r['id'],'document_sha256':doc,'family':r['family'],'parent_state':r['state'],
             'parent_domain':r['listing_domain'],'source_section_raw':sections,'domain_disposition':domain,
             'native_line_range':[lo,hi],'shared_layout_id':byrecord.get(r['id']),'recovered_direct_sites':recovered,
             'state':state,'external_identity_match_invented':False}
        dispositions.append(out);counts[state]+=1
    write(BASE/'legacy-shared-layouts.json',groups);write(BASE/'legacy-unit-dispositions.json',dispositions)
    write(BASE/'legacy-normalization-summary.json',{'all_prior_nonstandard_units_accounted':len(records),'state_counts':dict(counts),
        'shared_source_layouts':len(groups),'parent_units_with_shared_site':len(byrecord),
        'new_shared_site_units_over_r3':len(byrecord)-len({r for g in r3groups for r in g['parent_context_units']}),
        'Aetna_domain_dispositions_corrected':sum(x['parent_domain']!=x['domain_disposition']for x in dispositions),
        'original_values_unchanged':True,'source_partials_not_silently_completed':True})
    print((BASE/'legacy-normalization-summary.json').read_text())

if __name__=='__main__':main()
