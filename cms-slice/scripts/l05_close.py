#!/usr/bin/env python3
"""Add dated condition evidence and explicit units without rewriting the CMS base."""
import argparse
import base64
from collections import Counter,defaultdict
from contextlib import closing
from decimal import Decimal
import gzip
import hashlib
from html import unescape
import json
from pathlib import Path
import re
import sqlite3
import subprocess
import unicodedata

from l05_reference import verify
from l05_close_extract import key

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'docs/data/l05-drug-coverage-2026-10-25'
CLOSE=BASE/'closeout-r1'
PACKAGE=BASE/'build-r3'
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def packed(x):return json.dumps(x,sort_keys=True,separators=(',',':'))
def dump(p,x):p.write_text(json.dumps(x,indent=2,sort_keys=True)+'\n')
def norm(x):return ' '.join(re.findall(r'[a-z0-9]+',unicodedata.normalize('NFKC',x).lower()))


def sections(doc,text):
    """Preserve complete source ranges; remove only known repeated page furniture."""
    pages=text.split('\f');starts=[]
    for page_no,page in enumerate(pages,1):
        if doc['family']=='Humana':
            m=re.search(r'(?m)^\s*([^\n]{2,150})\n\s*(?:PA Criteria\s+Criteria Details|Criteria Details\b)',page)
            if m:
                title=m[1].strip();start=m.start(1)
                if title.lower() not in ['prior authorization criteria','step therapy criteria']:starts.append((page_no,start,title))
        else:
            m=re.search(r'(?m)^\s*([^\n]{2,150})\n\s*Products Affected\b',page)
            if m:starts.append((page_no,m.start(1),m[1].strip()))
    result=[]
    for i,(page,start,title) in enumerate(starts):
        end_page,end_offset,_=starts[i+1] if i+1<len(starts) else (len(pages),len(pages[-1]),'')
        body=pages[page-1][start:end_offset] if end_page==page else '\f'.join([pages[page-1][start:]]+pages[page:end_page-1]+[pages[end_page-1][:end_offset]])
        # Index pages are retained in the full document, not made clinical text.
        body=re.split(r'\f\s*(?:INDEX|Index)\b',body)[0]
        cleaned=[]
        for line in body.splitlines():
            if re.match(r'^\s*(?:Y0040_|Y0114_|\d{7}MUMENMUB|\d+\s*$)',line):continue
            if re.match(r'^\s*(?:2026 (?:FREEDOM|OPTIMUM) (?:Prior Authorization|Step Therapy) Criteria|EFFECTIVE DATE\s+\d)',line):continue
            cleaned.append(line)
        content=' '.join(' '.join(cleaned).split())
        product_text=body.split('PA Criteria',1)[0].split('Details',1)[0]
        result.append({'section_id':doc['id']+':'+str(page)+':'+str(start),'document_id':doc['id'],'title':title,
                       'pdf_page_start':page,'page_char_start':start,'pdf_page_end':end_page,'page_char_end':end_offset,
                       'full_text':body,'text_sha256':hashlib.sha256(body.encode()).hexdigest(),
                       'comparison_text':content,'comparison_sha256':hashlib.sha256(content.encode()).hexdigest(),
                       'printed_product_scope':title if doc['family']=='Humana' else product_text})
    return result


def sources(plans):
    old=read(BASE/'supplemental-r1/source-manifest.json')['sources'];new=read(CLOSE/'acquisition/source-manifest.json')['sources'];src=old|new
    decoded={r['id']:r for r in read(CLOSE/'decoded-archive-documents.json')}
    old_docs=read(BASE/'condition-assessment-r1/documents.json');docs={};checks=Counter()
    full_ids=['humana-plus5-2026-PA','humana-plus5-2026-ST','humana-csnp-2026-PA','humana-csnp-2026-ST','humana-supernational-2026-PA','humana-supernational-2026-ST','humana-basic-2026-PA','humana-basic-2026-ST','humana-value-2026-PA','humana-value-2026-ST','humana-premier-2026-PA','humana-premier-2026-ST','healthspring-2026-PA','healthspring-2026-ST','freedom-2026-PA','freedom-2026-ST','optimum-2026-PA','optimum-2026-ST']
    archive_ids=['archive-humana-plus5-PA-20260821']+[k for k in new if k.startswith('archive-copy-')]
    specs={k:{'kind':k.rsplit('-',1)[-1],'full_criteria':True} for k in full_ids}
    for k in archive_ids:specs[k]={'kind':('PA' if k=='archive-humana-plus5-PA-20260821' else new[k]['original_source_id'].rsplit('-',1)[-1]),'full_criteria':True}
    for k in ['florida-blue-medicare-forms-2026-formulary-fbm2600.pdf','florida-blue-medicare-forms-2026-formulary-fbm2601.pdf','humana-26408-formulary','aetna-fl-2026-formulary','aetna-fl-2026-changes']:
        specs[k]={'kind':'change_notice' if k.endswith('changes') else 'formulary','full_criteria':False}
    for k in new:
        if k.startswith('prime-2026-PA-'):specs[k]={'kind':'PA_questionnaire','full_criteria':False}
    for k in ['aetna-2026-PA','aetna-2026-ST']:specs[k]={'kind':'out_of_scope_Illinois_FIDE_candidate','full_criteria':False}
    # Original retained HealthSpring formulary is reused at its original path.
    hsc=next(d for d in old_docs if d['source_id']=='reused-healthspring-26099-formulary')
    src[hsc['source_id']]={'path':hsc['path'],'sha256':hsc['sha256'],'text_path':hsc['full_text_path'],'text_sha256':hsc['full_text_sha256'],'requested_url':hsc['url'],'status':'captured'}
    specs[hsc['source_id']]={'kind':'formulary','full_criteria':False}
    plan_links=read(CLOSE/'prime-plan-source-links.json');prime_scope=defaultdict(set);prime_labels=defaultdict(set)
    for group in plan_links:
        for link in group['links']:
            prime_scope[link['url']].update(group['offering_ids']);prime_labels[link['url']].add(link['product_label'])
    all_sections=[];bound={}
    for ident,spec in specs.items():
        original=src[ident];s={**original,**decoded.get(ident,{})}
        raw,text=ROOT/s['path'],ROOT/s['text_path']
        if sha(raw)!=s['sha256'] or sha(text)!=s['text_sha256']:raise ValueError('Changed document: '+ident)
        original_bytes=(ROOT/original['path']).read_bytes()
        if ident in archive_ids:
            expected=original.get('archive_digest')
            if not expected:
                rows=read(ROOT/new['archive-humana-plus5-PA-september-index']['path'])
                expected=next(r[2] for r in rows[1:] if r[0]==original['archive_timestamp'])
            if base64.b32encode(hashlib.sha1(original_bytes).digest()).decode().rstrip('=')!=expected:raise ValueError('Archived content differs from CDX digest')
            checks['archive_CDX_payload_digest']+=1
        extracted=subprocess.run(['pdftotext','-layout',str(raw),'-'],check=True,capture_output=True).stdout
        if hashlib.sha256(extracted).hexdigest()!=s['text_sha256']:raise ValueError('Full PDF re-extraction differs: '+ident)
        checks['complete_PDF_reextraction']+=1;body=extracted.decode();pages=body.split('\f')
        if not pages[-1].strip():pages.pop()
        header=body[:2500];form=re.search(r'Formulary ID\s*0*(\d{5})\s+Version\s+(\d+)',header,re.I)
        dm=re.search(r'(?:Effective|Last Updated:?)\s*(\d{1,2})/(\d{1,2})/(2026)',header,re.I)
        if not dm:dm=re.search(r'updated on\s*(\d{1,2})/(\d{1,2})/(2026)',header,re.I)
        date=f'{dm[3]}-{int(dm[1]):02}-{int(dm[2]):02}' if dm else None
        base_id=original.get('original_source_id',ident)
        family='Humana' if base_id.startswith('humana') else 'HealthSpring' if base_id.startswith('healthspring') else 'Freedom' if base_id.startswith('freedom') else 'Optimum' if base_id.startswith('optimum') else 'Prime/Florida Blue' if ident.startswith('prime-2026-PA') or ident.startswith('florida-blue') else 'Aetna' if ident.startswith('aetna') else 'HealthSpring'
        scope=[]
        if spec['full_criteria']:
            if family=='Humana':
                if not form:raise ValueError('Humana criteria missing explicit formulary identity')
                scope=[p['offering_id'] for p in plans if p['parent']=='Humana Inc.' and p['formulary_id']==form[1].zfill(8)]
            elif family=='HealthSpring':scope=[p['offering_id'] for p in plans if p['parent']=='Health Care Service Corporation']
            else:scope=[p['offering_id'] for p in plans if p['offering_id'].split(':')[1]==('H5427' if family=='Freedom' else 'H5594')]
        elif spec['kind']=='PA_questionnaire':scope=sorted(prime_scope[original['requested_url']])
        doc={'id':ident,**spec,'family':family,'scope_offering_ids':scope,'formulary_id':form[1].zfill(8) if form else None,'formulary_version':form[2] if form else None,
             'declared_date':date,'archive_timestamp':original.get('archive_timestamp'),'original_source_id':original.get('original_source_id'),
             'path':s['path'],'sha256':s['sha256'],'full_text_path':s['text_path'],'full_text_sha256':s['text_sha256'],
             'source_url':original['requested_url'],'source_delivery_path':original['path'],'source_delivery_sha256':original['sha256'],
             'page_count':len(pages),'page_sha256':[hashlib.sha256(page.encode()).hexdigest() for page in pages],
             'printed_product_labels':sorted(prime_labels[original['requested_url']]) if spec['kind']=='PA_questionnaire' else [],
             'historical_snapshot_asserted':False,'personal_approval_inferred':False}
        if spec['kind']=='PA_questionnaire' and not re.search(r'PRESCRIBER\s+FAX\s+FORM',header,re.I):raise ValueError('Inspect unexpected Prime document type: '+ident)
        if spec['full_criteria']:all_sections.extend(sections(doc,body))
        docs[ident]=doc
        for file in [raw,text,ROOT/original['path']]:bound[str(file.relative_to(ROOT))]=sha(file)
    return docs,all_sections,bound,checks


def build(out):
    if out.exists():raise ValueError('Immutable closeout output exists')
    verify(PACKAGE);plans=read(PACKAGE/'plans.json');identities={r['rxcui']:r for r in read(PACKAGE/'identities.json')}
    docs,blocks,bound,checks=sources(plans)
    # An exact unchanged block proves the two publications agree, not that no
    # unobserved intermediate revision ever existed.
    per_doc=defaultdict(lambda:defaultdict(list))
    for b in blocks:
        title=norm(b['title']);per_doc[b['document_id']][title].append(b)
    comparisons=[]
    for ident,d in docs.items():
        if not d['archive_timestamp']:continue
        current=d['original_source_id'];before=per_doc[ident];after=per_doc[current]
        for title in sorted(set(before)|set(after)):
            aa,bb=before.get(title,[]),after.get(title,[]);a=aa[0] if len(aa)==1 else None;b=bb[0] if len(bb)==1 else None
            state='ambiguous_duplicate_heading' if len(aa)>1 or len(bb)>1 else 'same_published_text_at_both_observations' if a and b and a['comparison_sha256']==b['comparison_sha256'] else 'published_text_changed' if a and b else 'only_in_earlier_capture' if a else 'only_in_later_capture'
            comparisons.append({'archived_document_id':ident,'current_document_id':current,'normalized_title':title,'before_section_ids':[v['section_id'] for v in aa],'after_section_ids':[v['section_id'] for v in bb],'comparison_state':state,'September_continuity_inferred':False})
    statements=read(CLOSE/'quantity-statements-r2.json');nlm=read(CLOSE/'identity-acquisition/source-manifest.json')['sources'];aliases=read(CLOSE/'quantity-alias-matches.json')['matches'];statement_codes={};query_evidence={}
    for st in statements:
        matches={}
        for query in st['query_products']:
            source=nlm.get('rxnorm-normalized-'+key(query));codes=[]
            if source and source['status']=='captured':
                if sha(ROOT/source['path'])!=source['sha256']:raise ValueError('Changed identity response')
                codes=read(ROOT/source['path']).get('idGroup',{}).get('rxnormId',[])
            choices=[]
            if len(codes)==1:choices.append((codes[0],source))
            if query in aliases:
                a=aliases[query];qid='NLM-public-RRF-'+key(query)
                choices.append((a['rxcui'],{'id':qid,'query_name':query,'kind':'NLM_public_RRF_alias','alias_evidence':a,'archive_manifest':'docs/data/l05-drug-coverage-2026-10-25/closeout-r1/bulk-acquisition/source-manifest.json'}))
            if not choices or len({c for c,s in choices})!=1:continue
            code,source=choices[0]
            if code not in identities:continue
            if ' - ' in st['product_label']:
                printed_brand=st['product_label'].split(' - ',1)[0]
                if norm(identities[code].get('related_brand',''))!=norm(printed_brand):continue
            matches[code]=source['id'];query_evidence[source['id']]=source
        statement_codes[st['statement_id']]=matches
    by_product=defaultdict(list);alternatives=defaultdict(dict);unit_doc_forms=set()
    for st in statements:
        for form in st['formulary_ids']:
            unit_doc_forms.add(form)
            for code,query_id in statement_codes[st['statement_id']].items():
                by_product[(form,code,Decimal(st['amount']),st['days'])].append((st,query_id));alternatives[(form,code)][st['statement_id']]=(st,query_id)
    units=[];unit_stats=Counter();unit_by_row={};row_needs=[]
    with closing(sqlite3.connect('file:'+str(PACKAGE/'inventory.sqlite3')+'?mode=ro',uri=True)) as db:
        for table,ordinal,raw_json in db.execute('SELECT table_name,ordinal,raw_json FROM drug_rows WHERE json_extract(modeled_json,\'$.QUANTITY_LIMIT_YN.value\')=1 ORDER BY table_name,ordinal'):
            raw=json.loads(raw_json);candidates=by_product.get((raw.get('FORMULARY_ID'),raw['RXCUI'],Decimal(raw['QUANTITY_LIMIT_AMOUNT']),int(raw['QUANTITY_LIMIT_DAYS'])),[]) if table=='basic' else []
            values={s['unit'] for s,q in candidates}
            state='explicit_carrier_unit_matched' if len(values)==1 else 'conflicting_carrier_units' if len(values)>1 else 'unit_not_bound_to_exact_CMS_row'
            unit_stats[state]+=1
            other=[{'statement_id':s['statement_id'],'source_id':s['source_id'],'amount':s['amount'],'unit':s['unit'],'days':s['days'],'NLM_query_source_id':q,'document_date':docs[s['source_id']]['declared_date']} for s,q in alternatives.get((raw.get('FORMULARY_ID'),raw['RXCUI']),{}).values() if Decimal(s['amount'])!=Decimal(raw['QUANTITY_LIMIT_AMOUNT']) or s['days']!=int(raw['QUANTITY_LIMIT_DAYS'])]
            unresolved_reason=None if len(values)==1 else 'explicit_units_conflict' if len(values)>1 else 'no_applicable_explicit_unit_document_held' if raw.get('FORMULARY_ID') not in unit_doc_forms else 'carrier_publishes_different_number_or_period; conversion_or_date_reconciliation_required' if other else 'printed_product_not_uniquely_linked_or_not_in_held_edition; retained_text_is_not_missing_data'
            record={'table':table,'source_row':ordinal,'rxcui':raw['RXCUI'],'formulary_id':raw.get('FORMULARY_ID'),'quantity_amount_raw':raw['QUANTITY_LIMIT_AMOUNT'],'quantity_days_raw':raw['QUANTITY_LIMIT_DAYS'],'unit':next(iter(values)) if len(values)==1 else None,'state':state,
                    'evidence':[{'statement_id':s['statement_id'],'source_id':s['source_id'],'NLM_query_source_id':q,'document_date':docs[s['source_id']]['declared_date']} for s,q in candidates],
                    'unresolved_reason':unresolved_reason,'other_dated_carrier_limits':other,
                    'validity':'Unit copied from the dated carrier statement for the exact RxCUI/amount/days; the September CMS row has no unit column. No earlier unit or personal supply conversion is inferred.'}
            units.append(record);unit_by_row[(table,ordinal)]=record
        matrix=[]
        for p in plans:
            ident=p['offering_id'];current={k:[d['id'] for d in docs.values() if d['full_criteria'] and not d['archive_timestamp'] and d['kind']==k and ident in d['scope_offering_ids']] for k in ['PA','ST']}
            earlier={k:[d['id'] for d in docs.values() if d['full_criteria'] and d['archive_timestamp'] and d['kind']==k and ident in d['scope_offering_ids']] for k in ['PA','ST']}
            questions=[d['id'] for d in docs.values() if d['kind']=='PA_questionnaire' and ident in d['scope_offering_ids']]
            state='full_dated_documents_available' if current['PA'] and current['ST'] else 'questionnaires_available_complete_approval_rules_not_established' if questions else 'source_access_STOP' if p['parent'] in ['UnitedHealth Group, Inc.','Centene Corporation'] else 'applicable_complete_criteria_not_located'
            ql_rows=[u for u in units if u['formulary_id']==p['formulary_id']]
            matrix.append({'offering_id':ident,'name':p['name'],'parent':p['parent'],'formulary_id':p['formulary_id'],'formulary_version':p['formulary_version'],'condition_source_state':state,'current_dated_criteria':current,'earlier_dated_criteria':earlier,'prescriber_questionnaires':questions,'QL_rows_with_carrier_unit':sum(u['state']=='explicit_carrier_unit_matched' for u in ql_rows),'CMS_snapshot_backdating_assumed':False,'clinical_approval':False})
        # Enumerate every PA/ST source context. A full scoped booklet remains
        # useful evidence even when an automatic named-section locator is absent.
        by_plan={p['offering_id']:p for p in matrix};by_form=defaultdict(list);by_pair=defaultdict(list);section_index=defaultdict(lambda:defaultdict(list))
        for p in plans:by_form[p['formulary_id']].append(p['offering_id']);by_pair[tuple(p['offering_id'].split(':')[1:3])].append(p['offering_id'])
        for block in blocks:section_index[block['document_id']][norm(block['title'].split(' - ',1)[0])].append(block['section_id'])
        for table,ordinal,fact,code,form,contract,number in db.execute('''SELECT g.table_name,g.ordinal,g.missing_fact,d.rxcui,d.formulary_id,d.contract_id,d.plan_id FROM condition_gaps g JOIN drug_rows d ON g.table_name=d.table_name AND g.ordinal=d.ordinal WHERE g.missing_fact IN ('prior_authorization_criteria','step_therapy_criteria') ORDER BY g.table_name,g.ordinal,g.missing_fact'''):
            kind='PA' if fact=='prior_authorization_criteria' else 'ST';identity=identities[code];aliases_for_drug={norm(identity.get('related_brand',''))}
            ingredient=identity.get('ingredient_strength_description','');aliases_for_drug.add(norm(re.split(r'\d',ingredient,1)[0].strip()));aliases_for_drug.discard('')
            linked=[]
            for ident in by_form[form] if table=='basic' else by_pair[(contract,number)]:
                p=by_plan[ident];current=p['current_dated_criteria'][kind];earlier=p['earlier_dated_criteria'][kind]
                named=sorted({sid for d in current+earlier for alias in aliases_for_drug for sid in section_index[d].get(alias,[])})
                questions=[d for d in p['prescriber_questionnaires'] if any(norm(label) in aliases_for_drug for label in docs[d]['printed_product_labels'])]
                linked.append({'offering_id':ident,'kind':kind,'current_full_document_ids':current,'earlier_full_document_ids':earlier,'named_section_locator_candidates':named,'matching_questionnaire_ids':questions,'source_state':'full_scoped_text_available' if current else p['condition_source_state'],'locator_state':'named_heading_candidate; full_text_must_be_read' if named else 'scoped_document_reference_only; no_exact_automatic_heading_match','September_continuity_asserted':False,'personal_approval':False})
            row_needs.append({'table':table,'source_row':ordinal,'rxcui':code,'formulary_id':form,'fact':fact,'kind':kind,'plan_links':linked})
    out.mkdir()
    dump(out/'documents.json',list(docs.values()));dump(out/'plans.json',matrix);dump(out/'quantity-statements.json',statements);dump(out/'quantity-code-mapping.json',statement_codes);dump(out/'quantity-query-evidence.json',query_evidence)
    def jsonlines(name,rows):
        with (out/name).open('wb') as f,gzip.GzipFile(filename='',fileobj=f,mode='wb',mtime=0) as z:
            for r in rows:z.write((packed(r)+'\n').encode())
    jsonlines('criteria-sections.jsonl.gz',blocks);jsonlines('criteria-comparisons.jsonl.gz',comparisons);jsonlines('quantity-units.jsonl.gz',units)
    jsonlines('condition-reference-links.jsonl.gz',row_needs)
    dump(out/'coverage.json',{'schema':'l05-closeout-coverage/1','base_CMS_package':'build-r3','base_CMS_inventory_unchanged':True,'target_plans':len(plans),'documents':len(docs),'PDF_pages_retained':sum(d['page_count'] for d in docs.values()),'full_criteria_current_documents':sum(d['full_criteria'] and not d['archive_timestamp'] for d in docs.values()),'full_criteria_earlier_documents':sum(d['full_criteria'] and bool(d['archive_timestamp']) for d in docs.values()),'criteria_sections':len(blocks),'criteria_comparison_states':dict(Counter(c['comparison_state'] for c in comparisons)),'plan_source_states':dict(Counter(p['condition_source_state'] for p in matrix)),'PA_ST_source_contexts_accounted':len(row_needs),'PA_ST_plan_reference_links':sum(len(r['plan_links']) for r in row_needs),'quantity_rows_accounted':len(units),'quantity_states':dict(unit_stats),'unresolved_unit_reasons':dict(Counter(u['unresolved_reason'] for u in units if u['unresolved_reason'])),'explicit_unit_statements_retained':len(statements),'source_checks':dict(checks),'full_L05_condition_reference_complete':False,'consumer_release_enabled':False,'personal_approval_or_price_available':False})
    inputs=[PACKAGE/'manifest.json',PACKAGE/'inventory.sqlite3',CLOSE/'acquisition/source-manifest.json',CLOSE/'identity-acquisition/source-manifest.json',CLOSE/'quantity-statements-r2.json',CLOSE/'quantity-alias-matches.json',CLOSE/'bulk-acquisition/source-manifest.json',ROOT/read(CLOSE/'bulk-acquisition/source-manifest.json')['path'],CLOSE/'decoded-archive-documents.json',CLOSE/'prime-plan-source-links.json',BASE/'supplemental-r1/source-manifest.json']
    for source in nlm.values():
        if source.get('status')=='captured':bound[source['path']]=sha(ROOT/source['path'])
    for source in read(CLOSE/'acquisition/source-manifest.json')['sources'].values():
        if source.get('status')=='captured':bound[source['path']]=sha(ROOT/source['path'])
    bound.update({str(f.relative_to(ROOT)):sha(f) for f in inputs})
    code=[ROOT/'cms-slice/scripts'/n for n in ['l05_close.py','l05_close_extract.py','l05_close_acquire.py','l05_close_validate.py','l05_close_reference.py','l05_close_aliases.py','l05_close_bulk.py']]
    dump(out/'manifest.json',{'schema':'l05-closeout-build/1','inputs':bound,'code':{str(f.relative_to(ROOT)):sha(f) for f in code},'files':{f.name:sha(f) for f in out.iterdir() if f.is_file()},'base_manifest_sha256':sha(PACKAGE/'manifest.json'),'actual_human_acceptance':None,'consumer_release_enabled':False})
    return read(out/'coverage.json')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);a=p.parse_args();print(json.dumps(build(a.out.resolve()),indent=2))
