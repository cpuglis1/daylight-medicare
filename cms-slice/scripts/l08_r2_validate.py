#!/usr/bin/env python3
"""Whole-population source/projection validation for the additive L08 follow-up."""
from collections import Counter,defaultdict
import gzip
import hashlib
from itertools import groupby,zip_longest
import json
import re
import sqlite3
import xml.etree.ElementTree as ET
from l08_r2_common import BASE,PARENT,ROOT,write,digest
from l08_r2_normalize import ax_nodes,HS_MARKERS,ERICKSON_CODES,AETNA_MARKERS


def sha(path):
    h=hashlib.sha256()
    with path.open('rb')as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()


def main():
    db=sqlite3.connect('file:'+str(BASE/'providers.sqlite3')+'?mode=ro',uri=True)
    parent=sqlite3.connect('file:'+str(PARENT/'build-r1/providers.sqlite3')+'?mode=ro',uri=True)
    counts=Counter();failures=[];checks=[]
    def check(name,ok,detail=None):
        checks.append({'name':name,'passed':bool(ok),'detail':detail})
        if not ok:failures.append(name)
    old_manifest=json.loads((PARENT/'execution-manifest-r1.json').read_text())
    for path,item in old_manifest['files'].items():
        if sha(ROOT/path)!=item['sha256']or(ROOT/path).stat().st_size!=item['bytes']:failures.append('Parent changed '+path)
        counts['sealed_parent_files_rehashed']+=1
    check('All sealed parent evidence and code retain their original bytes',not any(x.startswith('Parent changed ')for x in failures))
    check('Parent whole-captured-field validation passed',json.loads((PARENT/'build-r1/validation.json').read_text())['passed'])
    for table in ['sources','observations','entities','locations','roles','offerings','plan_networks','relationships','hospitals','directory_documents','plan_documents','directory_pages','directory_identifiers','source_conflicts']:
        a=parent.execute('SELECT *FROM '+table+' ORDER BY rowid');b=db.execute('SELECT *FROM '+table+' ORDER BY rowid');ok=True
        for left,right in zip_longest(a,b):
            if left!=right:ok=False;break
            counts['unchanged_parent_rows_compared']+=1
        check('Preserved validated parent table '+table,ok)
    for f in(BASE/'acquisition/receipts').glob('*.json'):
        r=json.loads(f.read_text())
        if r.get('path'):
            p=ROOT/r['path']
            if sha(p)!=r['sha256']or p.stat().st_size!=r['bytes']:failures.append('New source bytes '+r['id'])
            counts['new_http_responses_hashed']+=1
    check('All newly retained HTTP responses match their receipts',not any(x.startswith('New source bytes ')for x in failures))
    node_cache={};seen=set();records={}
    for line in gzip.open(BASE/'aetna-records.jsonl.gz','rt'):
        r=json.loads(line);records[r['id']]=r;path=r['source_path']
        if path not in node_cache:
            text=(ROOT/path).read_text();node_cache[path]={n['id']:n for n in ax_nodes(text)}
            if digest((ROOT/path).read_bytes())!=r['source_sha256']:failures.append('AX hash '+path)
            counts['public_ax_snapshots_hashed']+=1
        ns=node_cache[path];ok=True
        for key,loc in r['locators'].items():
            if loc.get('mode')=='join_nodes':value=loc['separator'].join(ns[k]['body']for k in loc['ax_nodes'])
            else:
                n=ns[loc['ax_node']];ok&=n['line']==loc['text_line']and n['body']==loc['body'];value=n['body'][slice(*loc['span'])]
            ok&=r['fields'][key]==value;counts['aetna_modeled_values_compared']+=1
        ok&=r['fields']['personal_participation_guaranteed']is False
        raw=db.execute('SELECT fields_json FROM aetna_query_observations WHERE id=?',(r['id'],)).fetchone()
        ok&=bool(raw)and json.loads(raw[0])==r
        if not ok:failures.append('AX modeled field '+r['id'])
        seen.add(r['id']);counts['aetna_records_compared']+=1
    check('Every new Aetna modeled string agrees with its exact source node/span and SQLite export',not any(x.startswith(('AX hash ','AX modeled field '))for x in failures)and len(seen)==db.execute('SELECT count(*)FROM aetna_query_observations').fetchone()[0])
    accounting=json.loads((BASE/'aetna-query-accounting.json').read_text())
    check('All ten Aetna bounded queries have every page and exact advertised card counts',len(accounting)==10 and all(q['pagination_complete']and q['card_count_agrees']for q in accounting))
    check('Bounded Aetna queries do not become full-county/all-specialty roster claims',all(not q['full_county_geographic_proof']and not q['all_specialty_roster_complete']and not q['all_locations_expanded']for q in accounting))
    for r in json.loads((BASE/'aetna-identity-resolution.json').read_text()):
        if r['state'].startswith('identity supplemented'):
            f=records[r['record_id']]['fields'];ok=bool(r['source_npi_observations'])
            for sid in r['source_npi_observations']:
                sf=records[sid]['fields'];ok&=sf['npi']==r['resolved_npi']and all(sf.get(k)==f.get(k)for k in ['publisher_provider_id','street_raw','city','state','postal_code'])
            if not ok:failures.append('Aetna identity join '+r['record_id'])
            counts['aetna_missing_npi_identity_resolutions_checked']+=1
    check('Supplemented Aetna identities use exact publisher ID and same site, without inheriting participation',not any(x.startswith('Aetna identity join ')for x in failures))
    # The old exception population is pinned independently of the new parser.
    old_summaries=json.loads((PARENT/'pdf-records-r1/summary.json').read_text());wanted=defaultdict(dict)
    for d in old_summaries:
        for x in d['unassigned_city_state_postal_lines']:wanted[d['document_sha256']][x['line']]=x
    old_frag_keys={};old_source_nodes={};old_held=[]
    for line in gzip.open(PARENT/'pdf-records-r1/records.jsonl.gz','rt'):
        r=json.loads(line)
        if r['state']=='held_multiple_identifiers_in_listing_unit':old_held.append(r)
    held_ranges=defaultdict(list)
    for r in old_held:held_ranges[r['document_sha256']].append(r)
    held_tokens=defaultdict(set)
    for line in gzip.open(PARENT/'pdf-records-r1/source-lines.jsonl.gz','rt'):
        r=json.loads(line);sh=r['source_sha256'];i=r['index'];key=(sh,r['page'],tuple(p['node']for p in r['parts']))
        if i in wanted[sh]:old_frag_keys[key]={'document':sh,**wanted[sh][i]}
        if 'NPI'in r['text']or'Provider ID:'in r['text']:
            for old in held_ranges.get(sh,[]):
                if old['native_line_range'][0]<=i<old['native_line_range'][1]:
                    for value in old.get('native_identifiers',[]):
                        if value in r['text']:held_tokens[old['id']].add((key,value))
    new_token_records=defaultdict(set);fragment_outcomes={};site_records={}
    line_groups=groupby((json.loads(x)for x in gzip.open(BASE/'pdf-records/source-lines.jsonl.gz','rt')),key=lambda r:r['source_sha256'])
    record_groups=groupby((json.loads(x)for x in gzip.open(BASE/'normalized-pdf-records.jsonl.gz','rt')),key=lambda r:r['document_sha256'])
    for(sh,rows),(rsh,rs)in zip(line_groups,record_groups):
        if sh!=rsh:raise ValueError('Stream order differs')
        lines=list(rows);parts={};line_keys={}
        for i,r in enumerate(lines):
            if r['index']!=i or r['text']!=' '.join(p['text']for p in r['parts']):failures.append('Native line '+sh+':'+str(i))
            key=(sh,r['page'],tuple(p['node']for p in r['parts']));line_keys[i]=key
            for p in r['parts']:parts[(p['page'],p['node'])]=p
        counts['new_native_lines_compared']+=len(lines)
        actual_nodes=0
        for _,page in ET.iterparse(PARENT/'pdf-records-r1'/(sh+'.xml'),events=['end']):
            if page.tag!='page':continue
            pn=int(page.attrib['number'])
            for n,node in enumerate(page.findall('text')):
                expected=parts.get((pn,n))
                if expected:
                    if ''.join(node.itertext()).strip()!=expected['text']or float(node.attrib['left'])!=expected['x']or float(node.attrib['top'])!=expected['y']or node.attrib['font']!=expected['font']:failures.append('XML part '+sh+':'+str(pn)+':'+str(n))
                    actual_nodes+=1
            page.clear()
        if actual_nodes!=len(parts):failures.append('XML part population '+sh)
        counts['original_xml_nodes_compared']+=actual_nodes
        for r in rs:
            ok=r['provider_display_raw']==(' '.join(lines[i]['text']for i in r['name_source_lines'])or None)
            if r['identifier']:
                ix=r['identifier_source_line'];ok&=r['identifier']in lines[ix]['text'];new_token_records[(line_keys[ix],r['identifier'])].add(r['id'])
            for occurrence in r['native_identifier_occurrences']:
                ix=occurrence['source_line'];ok&=occurrence['value']==lines[ix]['text'][slice(*occurrence['span'])]
                new_token_records[(line_keys[ix],occurrence['value'])].add(r['id']);counts['native_identifier_occurrences_compared']+=1
            for a in r['addresses']:
                ids=a['source_line_indices'];ok&=a['street_raw']==' '.join(lines[i]['text']for i in ids['street'])
                city=' '.join(lines[i]['text']for i in ids.get('city_state_postal_lines',[ids['city_state_postal']]))
                ok&=city.split()==(a['city']+', '+a['state']+' '+a['postal_code']).split()
                ok&=a['contact_lines_raw']==[lines[i]['text']for i in ids['contacts']]
                key=line_keys[ids['city_state_postal']]
                if key in old_frag_keys:fragment_outcomes[key]={'state':'recovered_normalized_source_address','new_record_id':r['id']}
                counts['pdf_addresses_compared']+=1
            for q in r['published_qualifiers']:
                if q['kind']=='published_symbol':
                    p=parts[(q['page'],q['source_node'])];ok&=q['value_raw']in p['text']and p['font']==q['font']
                    if r['family']=='healthspring':ok&=q['meaning']==HS_MARKERS[(p['font'],q['value_raw'])]
                    elif r['family']=='erickson':ok&=q['meaning']==ERICKSON_CODES[q['value_raw']]
                    elif r['family']=='aetna':ok&=q['meaning']==AETNA_MARKERS[q['value_raw']]
                else:ok&=q['value_raw']==' '.join(lines[i]['text']for i in q['source_lines'])
                counts['published_qualifier_values_compared']+=1
            for p in r['partial_addresses']:
                ok&=p['city_state_postal_raw']==lines[p['source_line']]['text']and p['context_raw']==[lines[i]['text']for i in p['context_source_lines']]
                key=line_keys[p['source_line']]
                if key in old_frag_keys:fragment_outcomes[key]={'state':'published_partial_or_nonstandard_address_explicitly_retained','new_record_id':r['id']}
                counts['partial_address_values_compared']+=1
            raw=db.execute('SELECT fields_json FROM pdf_records WHERE id=?',(r['id'],)).fetchone();ok&=bool(raw)and json.loads(raw[0])==r
            if not ok:failures.append('PDF modeled value '+r['id'])
            # Retain only the sparse site-resolution identity fields, not another
            # complete copy of every listing in validator memory.
            pcids={m[1]for q in r['published_qualifiers']if q['kind']=='primary_care_id'for m in [re.search(r'Primary Care ID:\s*(\d+)',q['value_raw'])]if m}
            if r['family']=='aetna':site_records[r['id']]={'document':sh,'publisher_id':r['identifier'],'pcids':pcids,'addresses':r['addresses']}
            counts['pdf_listing_units_compared']+=1
    check('Every new PDF line component matches original extraction coordinates and text',not any(x.startswith(('Native line ','XML part '))for x in failures))
    check('Every normalized PDF name, ID, address, contact, qualifier and partial address agrees with its retained source',not any(x.startswith('PDF modeled value ')for x in failures)and counts['pdf_listing_units_compared']==db.execute('SELECT count(*)FROM pdf_records').fetchone()[0])
    held_accounting=[]
    for old in old_held:
        tokens=held_tokens[old['id']];missing=[{'source_key':key,'identifier':value}for key,value in tokens if not new_token_records.get((key,value))]
        ok=bool(tokens)and not missing
        held_accounting.append({'parent_record_id':old['id'],'parent_source_identifiers':old.get('native_identifiers'),'source_identifier_occurrences':len(tokens),'all_exact_identifier_nodes_resolved':ok,'missing':missing,'new_record_ids':sorted({rid for token in tokens for rid in new_token_records.get(token,[])})})
    write(BASE/'parent-599-identifier-dispositions.json',held_accounting)
    check('All 599 original multi-identifier exceptions retain every exact ID source node in disaggregated records',len(held_accounting)==599 and all(x['all_exact_identifier_nodes_resolved']for x in held_accounting))
    frags=[]
    for key,old in old_frag_keys.items():frags.append({**old,**fragment_outcomes.get(key,{'state':'retained_context_fragment; no association invented'})})
    write(BASE/'parent-509-address-dispositions.json',frags)
    check('All 509 original address exceptions accounted for without data loss',len(frags)==509)
    for rid,state,raw in db.execute('SELECT *FROM pdf_site_resolution'):
        r=json.loads(raw)
        if r['resolved_site']:
            base=site_records[rid];sites=[];ok=True
            for sid in r['source_record_ids']:
                sf=site_records[sid];ok&=base['document']==sf['document']and base['publisher_id']==sf['publisher_id']and base['pcids']==sf['pcids'];sites.extend({k:a[k]for k in ['street_raw','city','state','postal_code']}for a in sf['addresses'])
            ok&=bool(sites)and all(x==r['resolved_site']for x in sites)
            if not ok:failures.append('PDF repeated site join '+rid)
            counts['same_document_exact_identity_site_resolutions_compared']+=1
    check('Reprinted-site resolutions require exact same document, publisher ID, primary-care ID and a unique identical site',not any(x.startswith('PDF repeated site join ')for x in failures))
    identities=json.loads((BASE/'registry-identity-evidence.json').read_text())
    for r in identities:
        source=json.loads((ROOT/r['source_path']).read_bytes())
        if r['native']not in source.get('results',[])or str(r['native']['number'])!=r['npi']:failures.append('Registry identity source '+r['npi'])
        counts['new_registry_identity_observations_compared']+=1
    check('Naples rehabilitation identity is actually returned by the registry at the Naples street',any(r['npi']=='1790432490'and r['native']['basic']['organization_name']=='ENCOMPASS HEALTH REHABILITATION HOSPITAL OF NAPLES, LLC'and any(a.get('address_1')=='14305 COLLIER BLVD'and a.get('city')=='NAPLES'for a in r['native']['addresses'])for r in identities))
    check('All registry identity fields agree with their exact source objects',not any(x.startswith('Registry identity source ')for x in failures))
    check('Every hospital-plan cell remains accounted for',db.execute('SELECT count(*)FROM hospital_plan_matrix').fetchone()[0]==17*72)
    for hid,pid,state,raw in db.execute('SELECT *FROM hospital_plan_matrix'):
        for e in json.loads(raw):
            if e.get('source')!='Aetna exact selected 2026 plan public directory':continue
            r=records[e['record_id']]
            if r['offering_id']!=pid or r['fields']!=e['published_fields']or r['fields']['personal_participation_guaranteed']:failures.append('Campus exact plan join '+hid+pid)
            counts['new_hospital_plan_source_observations_compared']+=1
    check('All new hospital observations retain exact selected plans and native fields',not any(x.startswith('Campus exact plan join ')for x in failures))
    check('Existing rehabilitation publisher-NPI conflict remains visible',db.execute("SELECT count(*)FROM source_conflicts WHERE id='REHAB-NPI-1497333017'").fetchone()[0]==1)
    resolution=json.loads((BASE/'rehabilitation-identity-resolution.json').read_text())
    stored=db.execute('SELECT fields_json FROM r2_source_conflict_resolutions WHERE id=?',(resolution['id'],)).fetchone()
    check('Current facility identity resolution is stored with its complete independent evidence',bool(stored)and json.loads(stored[0])==resolution and resolution['identity_sources']['official_registry']in identities and resolution['canonical_npi']=='1790432490'and not resolution['Erickson_participation_inherited_from_Aetna'])
    licensed=json.loads(db.execute("SELECT fields_json FROM hospitals WHERE id='AHCA:458386'").fetchone()[0])
    check('Resolved rehabilitation identity matches the licensed legal owner',resolution['identity_sources']['AHCA_license']==licensed and licensed['Owner'].upper()==resolution['identity_sources']['official_registry']['native']['basic']['organization_name'])
    for oid in resolution['identity_sources']['exact_Aetna_directory_record_ids']:
        f=records[oid]['fields']
        if f.get('npi')!='1790432490'or f.get('street_raw')!='14305 Collier Blvd':failures.append('Rehabilitation corroboration '+oid)
    resolved_rows=db.execute("SELECT *FROM hospital_plan_matrix WHERE hospital_id='AHCA:458386'AND offering_id LIKE '2026:H5652:%'").fetchall()
    resolution_ok=len(resolved_rows)==5
    for hid,pid,state,raw in resolved_rows:
        evidence=json.loads(raw);old=parent.execute('SELECT state,evidence_json FROM hospital_plan_matrix WHERE hospital_id=?AND offering_id=?',(hid,pid)).fetchone()
        resolution_ok&=state=='published_directory_lists_campus'and old[0]=='held_identifier_conflict'and all(e in evidence for e in json.loads(old[1]))
        resolution_ok&=any(e.get('identity_resolution_id')==resolution['id']and e.get('canonical_npi')=='1790432490'for e in evidence)
    check('Five campus identity holds resolved using original Erickson listing evidence; erroneous source NPI remains preserved',resolution_ok and not any(x.startswith('Rehabilitation corroboration ')for x in failures))
    for r in json.loads((BASE/'suite-only-identity-supplements.json').read_text()):
        source=next(x for x in identities if x['npi']==r['npi']and x['source_id']==r['source_id'])
        if r['registry_practice_addresses']!=[a for a in source['native']['addresses']if a.get('address_purpose')=='LOCATION']or r['exact_directory_location_or_participation_inferred_from_registry_alone']:failures.append('Suite identity supplement '+r['npi'])
    check('Suite-only entries retain registry addresses separately without inventing directory street or participation',not any(x.startswith('Suite identity supplement ')for x in failures))
    for r in json.loads((BASE/'source-quality-holds.json').read_text()):
        native=json.loads(db.execute('SELECT native_json FROM observations WHERE id=?',(r['source_observation'],)).fetchone()[0]);address=native.get('address')
        if not(r['published_address']==address or isinstance(address,list)and r['published_address']in address)or r['correction_invented']:failures.append('Geography quality hold '+r['source_observation'])
    check('Contradictory publisher geography is retained and held without silent correction',not any(x.startswith('Geography quality hold ')for x in failures))
    check('Failed targeted lookups never become out-of-network claims',all(x['participation_conclusion']=='unknown'for x in json.loads((BASE/'targeted-detail-failures.json').read_text())))
    check('SQLite integrity',db.execute('PRAGMA integrity_check').fetchone()[0]=='ok')
    summary=json.loads((BASE/'summary.json').read_text());check('Comprehensiveness and consumer-release holds remain explicit',not summary['comprehensive_layer_complete']and not summary['consumer_release_enabled'])
    result={'schema':'l08-followup-validation/2','passed':not failures,'counts':dict(counts),'checks':checks,'failures':failures[:100],
        'unexplained_modeled_value_mismatches':len(failures),'parent_address_dispositions':dict(Counter(x['state']for x in frags)),
        'all_specialty_roster_completeness_established':False,'personal_participation_verified':False}
    write(BASE/'validation.json',result);print(json.dumps({k:v for k,v in result.items()if k!='checks'},indent=2))
    db.close();parent.close()
    if failures:raise SystemExit(1)


if __name__=='__main__':main()
