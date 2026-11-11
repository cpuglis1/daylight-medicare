#!/usr/bin/env python3
"""Retain native directory listing units, identifiers, addresses and qualifiers.

Record fields carry exact XML text-node locators. Publisher identifiers and NPI
anchors delimit records; Aetna's explicitly bold listing names delimit its units.
No name/address matching supplies a missing NPI or a personal coverage promise.
"""
from collections import Counter
import gzip
import json
from pathlib import Path
import re
import subprocess
import xml.etree.ElementTree as ET
from l08_r2_common import BASE as FOLLOWUP, PARENT as BASE, ROOT, digest, write

OUT=FOLLOWUP/'pdf-records'
XML=BASE/'pdf-records-r1'
CITY=re.compile(r"^([A-Za-z][A-Za-z .’'\-]+),\s*([A-Z]{2})\s+(\d{5}(?:-\d{4})?)$")
NPI=re.compile(r'\bNPI\s*(?:#|:)?\s*(\d{10})\b')
PID=re.compile(r'\bID#\s*([A-Z0-9]+)')


def street_start(text):
    """Recognize printed street forms without removing their native symbols."""
    s=re.sub(r'^[⁰¹²³⁴⁵⁶⁷⁸⁹]+\s*','',text).strip()
    if re.fullmatch(r'\d+,?\s+(?:Ste|Suite|Unit)\b.*',s,re.I):return False
    numeric=bool(re.match(r'^\d+[A-Za-z0-9-]*(?:\s|[, -])',s)and re.search(r'[A-Za-z]',s))
    return numeric or bool(re.match(r'^P\.?O\.?\s*Box|^Virtual|^Tele|^Mobile Provider|^One\s|^Us\s+Hwy\s*\d',s,re.I))


def native_lines(xml, family):
    lines=[];fontspec={}
    for event,page in ET.iterparse(xml,events=['end']):
        if page.tag!='page':continue
        width=float(page.attrib['width']);height=float(page.attrib['height']);pn=int(page.attrib['number'])
        cols=4 if family in ['healthspring','aetna'] else 3
        # Text columns occupy the same bounded content area as the verified render.
        left=width*(0.058 if family=='aetna'else 0.075 if family=='erickson'else 0.03)
        right=width*(0.93 if family=='erickson'else 0.97)
        step=(right-left)/cols
        if family=='erickson':
            # Facing pages shift the three columns. Infer that page's origin
            # from actual NPI/city field starts, rather than merging columns.
            step=width*0.274
            starts=[float(e.attrib['left'])%step for e in page.findall('text')
                    if NPI.search(''.join(e.itertext()))or CITY.fullmatch(''.join(e.itertext()).strip())]
            if starts:
                buckets=Counter(round(v/5)*5 for v in starts);origin=buckets.most_common(1)[0][0]
                near=sorted(v for v in starts if abs(v-origin)<=5);left=near[len(near)//2]
        groups=[[]for _ in range(cols)]
        for f in page.findall('fontspec'):fontspec[f.attrib['id']]=dict(f.attrib)
        for i,e in enumerate(page.findall('text')):
            text=''.join(e.itertext()).strip()
            if not text:continue
            x=float(e.attrib['left']);y=float(e.attrib['top']);h=float(e.attrib['height'])
            top=height*(0.05 if family=='healthspring'else 0.04 if family=='erickson'else 0.07 if family=='aetna'else 0.04)
            bottom=height*(0.86 if family=='aetna'else 0.91 if family in['healthspring','erickson']else 0.945)
            if not(top<=y<bottom)or x>=right:continue
            col=max(0,min(cols-1,int((x-left+(2 if family=='erickson'else step*0.04))/step)))
            groups[col].append({'page':pn,'column':col+1,'node':i,'text':text,'x':x,'y':y,'height':h,'bold':e.find('b')is not None,'font':e.attrib['font']})
        for col,g in enumerate(groups):
            g.sort(key=lambda e:(e['y'],e['x']));merged=[]
            for e in g:
                if merged and abs(e['y']-merged[-1]['y'])<=3.1:
                    merged[-1]['parts'].append(e);merged[-1]['text']+=' '+e['text'];merged[-1]['bold']|=e['bold']
                else:merged.append({'page':pn,'column':col+1,'y':e['y'],'height':e['height'],'text':e['text'],'bold':e['bold'],'parts':[e]})
            lines.extend(merged)
        page.clear()
    return lines


def main():
    OUT.mkdir(exist_ok=True);summaries=[]
    with gzip.open(OUT/'records.jsonl.gz','wt')as records_out,gzip.open(OUT/'source-lines.jsonl.gz','wt')as lines_out:
        for d in json.loads((BASE/'document-index-r1/documents.json').read_text()):
            family=d['label'].split()[0].lower();family='freedom'if family=='freedom'else family
            xml=XML/(d['source_sha256']+'.xml')
            if not xml.exists():subprocess.run(['/opt/homebrew/bin/pdftohtml','-q','-xml','-i','-hidden',str(ROOT/d['source_path']),str(xml)],check=True)
            lines=native_lines(xml,family)
            for i,line in enumerate(lines):
                line['index']=i;lines_out.write(json.dumps({'source_sha256':d['source_sha256'],**line},ensure_ascii=False)+'\n')
            anchors=[]
            if family=='aetna':
                # Every printed provider ID has its own preceding bold name,
                # including group headers. Do not absorb group IDs into doctors.
                names={}
                consumed=set()
                for i,line in enumerate(lines):
                    s=line['text']
                    if i in consumed or line['page']<29 or not line['bold']or not any(p['font']=='5'for p in line['parts'])or re.match(r'^(Provider ID|Primary Care ID|Provider Speaks)',s):continue
                    name_indices=[i]
                    for j in range(i+1,min(i+6,len(lines))):
                        nxt=lines[j];prev=lines[j-1]
                        continuation=(nxt['page']==prev['page']and nxt['column']==prev['column']and nxt['y']-prev['y']<=prev['height']*1.6)or(prev['y']>900 and nxt['y']<160)
                        if not continuation or not nxt['bold']or not any(p['font']=='5'for p in nxt['parts'])or re.match(r'^(Provider ID|Primary Care ID|Provider Speaks)',nxt['text']):break
                        name_indices.append(j);consumed.add(j)
                    joined=' '.join(lines[k]['text']for k in name_indices)
                    if re.search(r'[A-Za-z]',joined)and not CITY.fullmatch(s):
                        names[i]={'at':i,'start':i,'end':name_indices[-1],'kind':'source_listing_anchor','value':None,'name_indices':name_indices}
                for i,line in enumerate(lines):
                    m=re.match(r'^Provider ID:\s*(\d+)',line['text'])
                    if not m or line['page']<29:continue
                    start=i
                    while start>0 and i-start<5:
                        p=lines[start-1]
                        if not p['bold']or not any(x['font']=='5'for x in p['parts'])or re.match(r'^(Provider ID:|Primary Care ID:)',p['text']):break
                        start-=1
                    # Merge the preceding name anchor with its printed ID,
                    # while retaining standalone group headers as separate units.
                    previous=[k for k in names if start<=k<i]
                    for k in previous:del names[k]
                    names[start]={'at':i,'start':start,'end':i-1,'kind':'publisher_provider_id','value':m[1],'name_indices':list(range(start,i))}
                anchors=sorted(names.values(),key=lambda a:a['start'])
            elif family=='healthspring':
                for i,line in enumerate(lines):
                    s=line['text'];parts=[p for p in line['parts']if p['font']=='34']
                    # Left-aligned name rows; county and specialty boxes are centered.
                    expected_x=[27,247,468,688][line['column']-1]
                    left_aligned=parts and abs(min(p['x']for p in parts)-expected_x)<=5
                    name_indices=[i]
                    if s.rstrip().endswith(',')and i+1<len(lines):
                        nxt=lines[i+1]
                        if nxt['page']==line['page']and nxt['column']==line['column']and any(p['font']=='34'for p in nxt['parts']):name_indices.append(i+1)
                    joined=' '.join(lines[k]['text']for k in name_indices)
                    person=bool(re.match(r"^[A-Z][A-Za-z .’'\-]*,\s*[A-Z]",joined))
                    facility=bool(re.search(r'\b(?:hospital|clinic|medical center|health center|laborator|imaging)\b',s,re.I))
                    if line['page']<19 or line['page']>=2149 or not left_aligned or not(person or facility):continue
                    if anchors and i==anchors[-1]['end']+1 and line['column']==lines[anchors[-1]['start']]['column']and line['page']==lines[anchors[-1]['start']]['page']:
                        anchors[-1]['end']=i
                    else:anchors.append({'at':i,'start':i,'end':name_indices[-1],'kind':'source_listing_anchor','value':None,'name_indices':name_indices})
            else:
                pattern=PID if family in ['freedom','optimum']else NPI
                for i,line in enumerate(lines):
                    match=pattern.search(line['text'])
                    if match:
                        start=i
                        if family=='erickson':
                            mainfont=lambda z:max(z['parts'],key=lambda t:len(t['text']))['font']
                            namefont=mainfont(lines[i-1])if i else None
                            while start>0 and i-start<3:
                                prev=lines[start-1];cur=lines[start]
                                if prev['column']!=line['column']or prev['page']!=line['page']or cur['y']-prev['y']>prev['height']*1.6:break
                                if mainfont(prev)!=namefont:break
                                if re.search(r'NPI|License|Language|Hours:|Group:|Affiliations:|^\d|^Web|\bFL\b',prev['text']):break
                                start-=1
                        anchors.append({'at':i,'start':start,'end':i,'kind':'publisher_provider_id'if pattern==PID else'npi','value':match.group(1)})
            assigned_cities=set();records=0;noaddresses=0;nativeids=[]
            for n,a in enumerate(anchors):
                if family in ['erickson','aetna','healthspring']:
                    start=a['start'];end=anchors[n+1]['start']if n+1<len(anchors)else len(lines)
                    if family=='healthspring':end=min(end,next((i for i in range(start,end)if lines[i]['page']>=2149),end))
                else:start=anchors[n-1]['at']+1 if n else 0;end=a['at']+1
                block=lines[start:end]
                name_lines=[]
                if family in ['erickson','aetna','healthspring']:name_lines=list(range(a['start'],a['at']if family in ['erickson','aetna']else a['end']+1))
                if family=='aetna':name_lines=a['name_indices']
                if family=='healthspring':name_lines=a.get('name_indices',name_lines)
                else:
                    for ix in range(start,end):
                        s=lines[ix]['text']
                        if ','in s and not CITY.fullmatch(s)and not re.search(r'^(Language|Cultural|Ethnicity|P:|F:)',s):name_lines=[ix];break
                addresses=[]
                for ix in range(start,end):
                    line=lines[ix];city_indices=[ix];m=CITY.fullmatch(line['text'])
                    if not m and ix+1<end and lines[ix+1]['page']==line['page']and lines[ix+1]['column']==line['column']:
                        m=CITY.fullmatch(line['text']+' '+lines[ix+1]['text'])
                        if m:city_indices.append(ix+1)
                    if not m:continue
                    street=[]
                    for k in range(ix-1,max(start-1,ix-5),-1):
                        prior=lines[k]
                        if re.search(r'^(NPI|ID#|P:|Language|Cultural|Ethnicity|Hours:|Web Address:|Medical Group:|Hospital Affiliations:)',prior['text']):break
                        if prior['text'].strip()in['(cont.)','COLLIER','CHARLOTTE','LEE','HENDRY','MANATEE','SARASOTA']:continue
                        street.insert(0,k)
                        if street_start(prior['text']):break
                    if not street or not street_start(lines[street[0]]['text']):continue
                    contacts=[]
                    for k in range(city_indices[-1]+1,min(end,city_indices[-1]+3)):
                        s=lines[k]
                        if s['page']==line['page']and s['column']==line['column']and re.search(r'\d{3}[- )]+\d{3}[- ]\d{4}',s['text']):contacts.append(k)
                    addresses.append({'street_raw':' '.join(lines[k]['text']for k in street),'city':m[1],'state':m[2],'postal_code':m[3],
                                      'contact_lines_raw':[lines[k]['text']for k in contacts],
                                      'source_line_indices':{'street':street,'city_state_postal':ix,'city_state_postal_lines':city_indices,'contacts':contacts}})
                    assigned_cities.add(ix)
                if not name_lines and addresses:
                    # Facility listings often have no comma. Retain their native
                    # display lines immediately before the first street, keeping
                    # section labels out of the name field when explicitly generic.
                    stop=addresses[0]['source_line_indices']['street'][0]
                    generic={'HOSPITAL','HOSPITALS','Hospitals','SKILLED NURSING FACILITY','Skilled Nursing Facilities',
                             'PHARMACIES','Pharmacies','COMMUNITY/RETAIL PHARMACY','CLINIC PHARMACY','VISION','INDEPENDENT PROVIDER',
                             'PRIMARY CARE PHYSICIANS','SPECIALISTS','(cont.)'}
                    candidates=[i for i in range(max(start,stop-4),stop)if lines[i]['text'].strip()not in generic and not re.search(r'^(Language|Cultural|Ethnicity|ID#|NPI|P:|F:)',lines[i]['text'])]
                    name_lines=candidates[-3:]
                nativeids.append(a['value']);noaddresses+=not bool(addresses);records+=1
                row={'id':'r2:'+d['source_sha256']+':'+str(n+1),'document_sha256':d['source_sha256'],'family':family,
                     'benefit_year':2026,'publication_date_text':d['published_date_text'],'identifier_kind':a['kind'],'identifier':a['value'],
                     'identifier_source_line':a['at']if a['value']else None,
                     'provider_display_raw':' '.join(lines[k]['text']for k in name_lines)or None,'name_source_lines':name_lines,
                     'native_line_range':[start,end],'anchor_page':lines[a['at']]['page'],'addresses':addresses,
                     'conditions':'Full native listing lines and directory legends retained; symbols and practice/group restrictions not discarded',
                     'state':'published_native_listing; personal applicability unknown'}
                if family=='healthspring':
                    npi_rows=[(ix,NPI.search(lines[ix]['text']))for ix in range(start,end)if NPI.search(lines[ix]['text'])]
                    ids={m.group(1)for ix,m in npi_rows}
                    if len(ids)==1:
                        row.update(identifier_kind='npi',identifier=next(iter(ids)),identifier_source_line=npi_rows[0][0])
                    elif len(ids)>1:row.update(state='held_multiple_identifiers_in_listing_unit',native_identifiers=sorted(ids))
                if family=='aetna':
                    idrows=[(ix,re.search(r'^Provider ID:\s*(\d+)',lines[ix]['text']))for ix in range(start,end)if re.search(r'^Provider ID:\s*(\d+)',lines[ix]['text'])]
                    ids={m.group(1)for ix,m in idrows}
                    if len(ids)==1:row.update(identifier_kind='publisher_provider_id',identifier=next(iter(ids)),identifier_source_line=idrows[0][0])
                    elif len(ids)>1:row.update(state='held_multiple_identifiers_in_listing_unit',native_identifiers=sorted(ids))
                row['listing_domain']='pharmacy_or_other_identifier'if a['kind']=='publisher_provider_id'and a['value']and not a['value'].startswith('P')else'medical_or_supplemental_provider'
                if not addresses:row['state']='source_name_or_identifier_mention_without_normalized_location'
                row['revision']='followup-r2'
                row['source_name_line_semantics']='Publisher-native name/group line; identity and practice membership not inferred from name alone'
                records_out.write(json.dumps(row,ensure_ascii=False)+'\n')
            # Every unassigned candidate address remains visible. This is an
            # extraction exception, never evidence of absent network participation.
            unassigned=[{'line':i,'page':l['page'],'text':l['text']}for i,l in enumerate(lines)if CITY.fullmatch(l['text'])and i not in assigned_cities and not(family=='healthspring'and l['page']>=2149)]
            summary={'label':d['label'],'document_sha256':d['source_sha256'],'family':family,'native_lines':len(lines),'records':records,
                     'unique_publisher_identifiers':len(set(v for v in nativeids if v)), 'records_without_parsed_street_address':noaddresses,
                     'parsed_address_observations':len(assigned_cities),'unassigned_city_state_postal_lines':unassigned,
                     'all_published_fields_semantically_structured':False}
            summaries.append(summary);print(d['label'],'records',records,'addresses',len(assigned_cities),'unassigned',len(unassigned),'noaddress',noaddresses,flush=True)
    write(OUT/'summary.json',summaries)


if __name__=='__main__':main()
