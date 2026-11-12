#!/usr/bin/env python3
"""Whole-population comparison of L08 modeled/exported fields with retained sources."""
from collections import Counter,defaultdict
from functools import lru_cache
import gzip
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import xml.etree.ElementTree as ET
from l08_acquire import BASE,OUT,ROOT,write
from l08_build import exact_offering_ids,networks,npi,refkey


def sha(path):
    h=hashlib.sha256()
    with path.open('rb')as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()


def leaf_count(x):
    if isinstance(x,(list,dict)):return sum(leaf_count(v)for v in(x.values()if isinstance(x,dict)else x))
    return 1


def main():
    b=BASE/'build-r1';db=sqlite3.connect('file:'+str(b/'providers.sqlite3')+'?mode=ro',uri=True)
    checks=[];failures=[];counts=Counter()
    def check(name,ok,details=None):
        checks.append({'name':name,'passed':bool(ok),'details':details})
        if not ok:failures.append(name)
    # Original bytes, including errors/login responses, remain separately retained.
    for f in(OUT/'receipts').glob('*.json'):
        r=json.loads(f.read_text())
        if r.get('path'):
            path=ROOT/r['path'];ok=path.is_file()and sha(path)==r['sha256']and path.stat().st_size==r['bytes']
            if not ok:failures.append('receipt hash '+r['id'])
            counts['source_receipts_hashed']+=1
    check('Every retained response matches its recorded bytes/hash',not any(x.startswith('receipt hash')for x in failures))
    sources={r[0]:dict(zip(['id','url','sha256','path','retrieved'],r))for r in db.execute('SELECT *FROM sources')}
    @lru_cache(maxsize=8)
    def packet(sid):return json.loads((ROOT/sources[sid]['path']).read_bytes())
    def pointer(x,path):
        for token in path.split('/')[1:]if path else[]:x=x[int(token)]if isinstance(x,list)else x[token]
        return x
    for oid,ek,typ,sid,ptr,fields,native,number in db.execute('SELECT *FROM observations ORDER BY source_id'):
        original=pointer(packet(sid),ptr);n=json.loads(native);f=json.loads(fields)
        ok=n==original and all(k in original and v==original[k]for k,v in f.items())and leaf_count(f)==number
        if not ok:failures.append('modeled source fields '+oid)
        counts['fhir_observations_compared']+=1;counts['fhir_modeled_leaf_values_compared']+=number
    check('Every FHIR modeled value and native object agrees with its exact source pointer',not any(x.startswith('modeled source')for x in failures))
    export_ids=set()
    for line in gzip.open(b/'resources.jsonl.gz','rt'):
        r=json.loads(line);row=db.execute('SELECT entity_key,type,source_id,pointer,fields_json,native_json,modeled_leaf_count FROM observations WHERE id=?',(r['id'],)).fetchone()
        ok=row and row[:4]==(r['entity_key'],r['type'],r['source_id'],r['pointer'])and json.loads(row[4])==r['fields']and json.loads(row[5])==r['native']and row[6]==r['modeled_leaf_count']
        if not ok:failures.append('FHIR export '+r['id'])
        export_ids.add(r['id'])
    check('SQLite and portable FHIR export have all the same records and modeled information',len(export_ids)==db.execute('SELECT count(*)FROM observations').fetchone()[0]and not any(x.startswith('FHIR export')for x in failures))
    expected={x['id']for x in json.loads((BASE/'plan-source-matrix.json').read_text())}
    actual={r[0]for r in db.execute('SELECT id FROM offerings')}
    check('All 72 pinned 2026 Collier offerings retained, including MA-only',actual==expected and len(actual)==72)
    check('Offering categories remain MA/SNP medical scope',db.execute("SELECT count(*)FROM offerings WHERE id LIKE '2026:S%'").fetchone()[0]==0)
    # Every derived role preserves its actual source references, dates and qualifiers.
    for ek,oid,pk,org,locs,nets,specialty,period,qualifiers in db.execute('SELECT *FROM roles'):
        native=json.loads(db.execute('SELECT native_json FROM observations WHERE id=?',(oid,)).fetchone()[0])
        ok=json.loads(specialty)==native.get('specialty')and json.loads(period)==native.get('period')
        q=json.loads(qualifiers);ok&=all(k in native and v==native[k]for k,v in q.items())
        if not ok:failures.append('role fields '+ek)
        counts['derived_role_records_checked']+=1
    check('Every modeled role specialty/period/condition retains the native value',not any(x.startswith('role fields')for x in failures))
    # Validate the relational projections as well as the copied source fields.
    for ek,typ,oid,npis,names,status,period in db.execute('SELECT *FROM entities'):
        native=json.loads(db.execute('SELECT native_json FROM observations WHERE id=?',(oid,)).fetchone()[0])
        ok=typ==native['resourceType'] and json.loads(npis)==npi(native) and json.loads(names)==native.get('name') and json.loads(status)=={k:native[k]for k in ['status','active']if k in native} and json.loads(period)==native.get('period')
        if not ok:failures.append('entity projection '+ek)
        counts['entity_projections_checked']+=1
    for ek,oid,name,address,telecom,position in db.execute('SELECT *FROM locations'):
        native=json.loads(db.execute('SELECT native_json FROM observations WHERE id=?',(oid,)).fetchone()[0])
        if not all(json.loads(value)==native.get(field)for value,field in [(name,'name'),(address,'address'),(telecom,'telecom'),(position,'position')]):failures.append('location projection '+ek)
        counts['location_projections_checked']+=1
    joins=defaultdict(list)
    for pid,nk,oid,reference,resolved,state,reason in db.execute('SELECT *FROM plan_networks'):
        native=json.loads(db.execute('SELECT native_json FROM observations WHERE id=?',(oid,)).fetchone()[0]);ref=json.loads(reference)
        host=db.execute('SELECT entity_key FROM observations WHERE id=?',(oid,)).fetchone()[0].split('/')[0]
        exact=pid in exact_offering_ids(native)
        ok=ref in native.get('network',[]) and nk==refkey(host,ref.get('reference','')) and (exact or state=='held_product_to_CMS_crosswalk')
        if resolved:ok&=db.execute('SELECT entity_key FROM observations WHERE id=?',(resolved,)).fetchone()[0]==nk
        if not ok:failures.append('plan network source '+pid+' '+str(nk))
        joins[(pid,nk)].append(state);counts['plan_network_references_checked']+=1
    role_sources={}
    for ek,oid,pk,org,locs,nets,specialty,period,qualifiers in db.execute('SELECT *FROM roles'):
        native=json.loads(db.execute('SELECT native_json FROM observations WHERE id=?',(oid,)).fetchone()[0]);host=ek.split('/')[0]
        provider=native.get('practitioner',{})if native['resourceType']=='PractitionerRole'else native.get('participatingOrganization',native.get('organization',{}))
        source_pk=refkey(host,provider.get('reference',''));source_locs=[refkey(host,l['reference'])for l in native.get('location',[])if l.get('reference')]
        source_nets=[refkey(host,n['reference'])for n in networks(native)if n.get('reference')]
        ok=pk==source_pk and org==refkey(host,native.get('organization',{}).get('reference','')) and json.loads(locs)==source_locs and json.loads(nets)==source_nets
        if not ok:failures.append('role source references '+ek)
        role_sources[ek]=(oid,source_pk,set(source_locs or [None]),set(source_nets))
    for pid,rk,oid,pk,lk,nk,state,reason in db.execute('SELECT *FROM relationships'):
        role=role_sources[rk];join_states=joins.get((pid,nk),[])
        ok=oid==role[0] and pk==role[1] and lk in role[2] and nk in role[3] and any(s!='excluded_nonmedical_network'for s in join_states)
        if state=='source_listed_observation':
            ok&='source_medical_network_reference'in join_states and db.execute('SELECT 1 FROM entities WHERE entity_key=?',(pk,)).fetchone()is not None and db.execute('SELECT 1 FROM locations WHERE entity_key=?',(lk,)).fetchone()is not None
        if not ok:failures.append('relationship source references '+rk)
        counts['relationship_source_references_checked']+=1
    check('All entity, location and role references match their exact native objects',not any(x.startswith(('entity projection ','location projection ','role source references '))for x in failures))
    check('All plan/network references have exact source identifiers or an explicit held crosswalk',not any(x.startswith('plan network source ')for x in failures))
    check('Every derived relationship is supported by actual source references; nonmedical networks do not leak into medical joins',not any(x.startswith('relationship source references ')for x in failures))
    del role_sources
    for line in gzip.open(BASE/'document-index-r1/pages.jsonl.gz','rt'):
        r=json.loads(line);row=db.execute('SELECT text,text_sha256 FROM directory_pages WHERE document_sha256=?AND page=?',(r['source_sha256'],r['page'])).fetchone()
        if not(row and row==(r['text'],r['text_sha256'])and hashlib.sha256(r['text'].encode()).hexdigest()==r['text_sha256']):failures.append('PDF page '+r['source_sha256']+':'+str(r['page']))
        counts['complete_pdf_pages_checked']+=1
    check('Every complete PDF page/export agrees with the database',counts['complete_pdf_pages_checked']==10205 and not any(x.startswith('PDF page')for x in failures))
    pages={}
    for doc,page,text in db.execute('SELECT document_sha256,page,text FROM directory_pages'):pages[(doc,page)]=text
    rawpages={}
    idcursor=iter(db.execute('SELECT document_sha256,page,kind,value,projection,span_json FROM directory_identifiers ORDER BY rowid'))
    for line in gzip.open(BASE/'document-index-r1/identifiers.jsonl.gz','rt'):
        r=json.loads(line);doc=r['source_sha256'];projection=r['projection']
        if projection=='raw':
            if doc not in rawpages:rawpages[doc]=(BASE/'document-index-r1'/(doc+'.raw.txt')).read_text().split('\f')
            text=rawpages[doc][r['page']-1]
        else:text=pages[(doc,r['page'])]
        row=next(idcursor,None);expected=(doc,r['page'],r['kind'],r['value'],projection)
        if not(row and row[:5]==expected and json.loads(row[5])==r['span']and text[slice(*r['span'])]==r['value']):failures.append('PDF identifier '+doc+':'+str(r['page']))
        counts['pdf_identifier_contact_observations_checked']+=1
    check('Every indexed NPI, publisher ID and phone occurrence reconciles to its exact projection/span',next(idcursor,None)is None and not any(x.startswith('PDF identifier ')for x in failures))
    # A source line includes every contributing XML node. Address/name values
    # are checked across the entire extracted listing population, not samples.
    lines_by_doc=defaultdict(list)
    for line in gzip.open(BASE/'pdf-records-r1/source-lines.jsonl.gz','rt'):
        r=json.loads(line);lines_by_doc[r['source_sha256']].append(r)
    for doc,lines in lines_by_doc.items():
        expected_nodes={}
        for i,line in enumerate(lines):
            if line['index']!=i or line['text']!=' '.join(p['text']for p in line['parts']):failures.append('native line '+doc+':'+str(i))
            counts['pdf_source_lines_checked']+=1
            for part in line['parts']:expected_nodes[(part['page'],part['node'])]=part
        seen_nodes=0
        for event,page in ET.iterparse(BASE/'pdf-records-r1'/(doc+'.xml'),events=['end']):
            if page.tag!='page':continue
            pn=int(page.attrib['number'])
            for i,node in enumerate(page.findall('text')):
                expected=expected_nodes.get((pn,i))
                if expected:
                    ok=''.join(node.itertext()).strip()==expected['text']and float(node.attrib['left'])==expected['x']and float(node.attrib['top'])==expected['y']and node.attrib['font']==expected['font']
                    if not ok:failures.append('PDF XML source node '+doc+':'+str(pn)+':'+str(i))
                    seen_nodes+=1
            page.clear()
        if seen_nodes!=len(expected_nodes):failures.append('PDF XML node count '+doc)
        counts['pdf_original_xml_nodes_compared']+=seen_nodes
    check('Every indexed PDF line component matches its exact extraction node and coordinates',not any(x.startswith('PDF XML')for x in failures))
    record_ids=set()
    stream=iter(gzip.open(BASE/'pdf-records-r1/records.jsonl.gz','rt'))
    for line in stream:
        r=json.loads(line);ls=lines_by_doc[r['document_sha256']];ok=True
        name=' '.join(ls[i]['text']for i in r['name_source_lines'])or None
        ok&=name==r['provider_display_raw']
        if r['identifier']is not None:
            src=ls[r['identifier_source_line']]['text'];ok&=r['identifier']in src
        start,end=r['native_line_range'];ok&=0<=start<end<=len(ls)
        for a in r['addresses']:
            ids=a['source_line_indices'];street=' '.join(ls[i]['text']for i in ids['street'])
            city=' '.join(ls[i]['text']for i in ids.get('city_state_postal_lines',[ids['city_state_postal']]))
            ok&=street==a['street_raw']and city.split()==(a['city']+', '+a['state']+' '+a['postal_code']).split()
            ok&=[ls[i]['text']for i in ids['contacts']]==a['contact_lines_raw']
            ok&=all(start<=i<end for i in ids['street']+ids.get('city_state_postal_lines',[ids['city_state_postal']])+ids['contacts'])
            counts['pdf_address_records_checked']+=1
        stored=db.execute('SELECT fields_json FROM pdf_records WHERE id=?',(r['id'],)).fetchone()
        ok&=bool(stored)and json.loads(stored[0])==r
        if not ok:failures.append('PDF listing source fields '+r['id'])
        record_ids.add(r['id']);counts['native_pdf_listing_records_checked']+=1
    check('Every modeled PDF listing name/identifier/address/contact field retains its exact native source-line value',not any(x.startswith('PDF listing source')for x in failures))
    check('All PDF listing exports and SQLite records reconcile',len(record_ids)==db.execute('SELECT count(*)FROM pdf_records').fetchone()[0])
    check('All 17 active hospital entries and seven Collier entries retained',db.execute('SELECT count(*)FROM hospitals').fetchone()[0]==17 and db.execute("SELECT count(*)FROM hospitals WHERE county='Collier'").fetchone()[0]==7)
    profile_receipts={r['id']:r for r in [json.loads(f.read_text())for f in(OUT/'receipts').glob('*.json')]}
    for hid,county,name,sid,ptr,fields,addresses in db.execute('SELECT *FROM hospitals'):
        response=(ROOT/profile_receipts[sid]['path']).read_text();pos=response.index('const profilelist =')+len('const profilelist =')
        payload,end=json.JSONDecoder().raw_decode(response[pos:].lstrip());groups={x[0]['LABEL']:x[1:]for x in payload};native=groups['FacilityDetails'][0];modeled=json.loads(fields)
        ok=county==native['County']and name==native['Name']and all(native.get(k)==v for k,v in modeled.items())and json.loads(addresses)==groups['AddressResults']
        if not ok:failures.append('hospital fields '+hid)
        counts['hospital_profile_records_compared']+=1;counts['hospital_profile_modeled_leaf_values']+=leaf_count(modeled)+leaf_count(json.loads(addresses))
    check('Every modeled hospital/license/date/location field matches its official source',not any(x.startswith('hospital fields ')for x in failures))
    check('All hospital-plan cells retained with unknowns explicit',db.execute('SELECT count(*)FROM hospital_plan_matrix').fetchone()[0]==17*72)
    check('Missing search results never become a negative participation claim',db.execute("SELECT count(*)FROM hospital_plan_matrix WHERE state NOT IN ('unknown_no_exact_campus_plan_evidence','published_directory_lists_campus','held_identifier_conflict')").fetchone()[0]==0)
    conflicts=json.loads((b/'hospital-identity-conflicts.json').read_text())
    check('Greenville/Naples identifier conflict remains held',bool(conflicts)and all(e['hospital_id']=='AHCA:458386'for e in conflicts[0]['directory_records']))
    check('Research database integrity',db.execute('PRAGMA integrity_check').fetchone()[0]=='ok')
    # Pin and recheck prior references instead of mutating their selection or data.
    protected=json.loads((BASE/'reuse-r1/protected-inputs.json').read_text());unique_pdfs=len(protected)
    protected.update(json.loads((BASE/'protected-before.json').read_text()))
    for path,expected_sha in protected.items():
        if sha(ROOT/path)!=expected_sha:failures.append('protected '+path)
    check('All reused SB/EOC PDFs and prior selected references retain their original bytes',not any(x.startswith('protected ')for x in failures),{'unique_pdfs_checked':unique_pdfs,'other_protected_references':len(protected)-unique_pdfs})
    db.close()
    report={'schema':'l08-captured-field-validation/1','passed':not failures,'checks':checks,'counts':dict(counts),
            'unexplained_modeled_value_mismatches':len([x for x in failures if not x.startswith('protected ')]),
            'failures':failures[:100],'full_roster_completeness_established':False,'personal_coverage_verified':False,
            'scope':'All captured modeled projections and exports; source truth conflicts and missing rosters are separate explicit holds'}
    write(b/'validation.json',report);print(json.dumps({k:v for k,v in report.items()if k!='checks'},indent=2))
    if failures:raise SystemExit(1)


if __name__=='__main__':main()
