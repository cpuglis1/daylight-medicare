#!/usr/bin/env python3
"""Build the L03 2026 published-benefit research reference, offline.

Carrier corroboration and owner acceptance are separate from source capture.
No personal data, ranking, calculator or application release is implemented.
Run with a Python environment containing openpyxl.
"""
from __future__ import annotations
import argparse, collections, csv, gzip, hashlib, io, json, pathlib, re, zipfile
from decimal import Decimal, InvalidOperation

REPO = pathlib.Path(__file__).resolve().parents[2]
DATA = REPO / 'docs/data/l03-ma-benefits-2026-10-25'
L02 = REPO / 'docs/data/l02-ma-availability-2026-10-25'
PBP_SHA = '65077aeb8deb6e82eaeddc8e32b2b1a810d1df2ca814a69b1d24401f4f5cbbe3'
L02_SHA = '73815d3f5358f74666f4f9e4673949735115dff82a62a52f6ed50f3686d3a0a9'
TECH = {'pbp_a_hnumber','pbp_a_plan_identifier','segment_id','pbp_a_ben_cov','pbp_a_plan_type','orgtype','bid_id','version'}

def sha(data): return hashlib.sha256(data).hexdigest()
def dump(path, value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n')
def keycode(v):
    if isinstance(v,(float,int)) and float(v).is_integer(): return str(int(v))
    return str(v).strip()
def leaves(obj, pointer=''):
    if isinstance(obj,dict):
        for k,v in obj.items(): yield from leaves(v,pointer+'/'+k.replace('~','~0').replace('/','~1'))
    elif isinstance(obj,list):
        if not obj: yield pointer, []
        for i,v in enumerate(obj): yield from leaves(v,pointer+'/'+str(i))
    else: yield pointer,obj

def dictionary(path):
    import openpyxl
    wb=openpyxl.load_workbook(path,read_only=True,data_only=True)
    output={}; current=None
    for number,row in enumerate(wb.active.values,1):
        if number==1: continue
        file,name,typ,length,category,field_title,question,title,code,meaning,derived = row
        if typ is not None:
            current={'file':file,'name':name,'source_type':typ,'length':length,'service_category':category,
                     'field_title':field_title,'json_question':question,'title':title,'derived_category':derived,
                     'dictionary_rows':[number],'codes':{}}
            output[(file.lower(),name.lower())]=current
        elif current and (file,name)!=(current['file'],current['name']):
            raise ValueError(f'Unbound dictionary continuation row {number}')
        if current:
            if number not in current['dictionary_rows']:current['dictionary_rows'].append(number)
            if code is not None:current['codes'][keycode(code)]=meaning
    return output

def normalize(raw, definition):
    """Decode only documented exact codes; never treat blank as zero or No.

    Checkbox bit strings, unfamiliar codes, missing dictionary fields, units and
    field activation dependencies stay explicitly unresolved.
    """
    if raw is None:return {'state':'source_null','value':None,'type':'unknown'}
    if raw=='':return {'state':'source_blank','value':None,'type':'unknown'}
    if not definition:return {'state':'unmapped_field','value':raw,'type':'source_text'}
    codes=definition['codes']
    if codes:
        if raw in codes:return {'state':'decoded_code','value':codes[raw],'source_code':raw,'type':'enum'}
        pos={int(m.group(1)):meaning for code,meaning in codes.items() if (m:=re.fullmatch(r'1 in (\d+)',code))}
        if len(pos)==len(codes) and pos and set(raw)<=set('01') and len(raw)>=max(pos):
            return {'state':'decoded_position_set','value':[meaning for position,meaning in sorted(pos.items()) if raw[position-1]=='1'], 'source_code':raw,'type':'enum_set','code_basis':'CMS dictionary 1 in N; positions counted from left, one based'}
        numeric=[code for code in codes if code.isdigit() and raw.isdigit() and int(code)==int(raw)]
        if len(numeric)==1:
            return {'state':'decoded_padded_code','value':codes[numeric[0]],'source_code':raw,'dictionary_code':numeric[0],'type':'enum'}
        parts=re.split(r'[;,]',raw.rstrip(';,'))
        if (';' in raw or ',' in raw) and parts and all(x in codes for x in parts):
            return {'state':'decoded_code_set','value':[codes[x] for x in parts],'source_codes':parts,'type':'enum_set'}
        return {'state':'unresolved_code','value':raw,'type':'opaque_code'}
    if definition['source_type']=='NUM':
        try:
            n=Decimal(raw)
            if not n.is_finite():raise InvalidOperation
            label=' '.join(str(definition.get(x) or '') for x in ['field_title','title']).lower()
            unit='USD' if any(x in label for x in ['copay','premium','deductible amount','deductible amt','moop amt','oopc amt','reduction amount']) else 'percent' if any(x in label for x in ['percentage','pct','coinsurance']) else None
            # Units are a dictionary-label interpretation, not an accepted claim.
            return {'state':'typed_numeric','value':str(n),'type':'decimal','unit':unit,'unit_status':'dictionary_label_inference' if unit else 'not_resolved'}
        except InvalidOperation:return {'state':'unresolved_number','value':raw,'type':'source_text'}
    return {'state':'source_text','value':raw,'type':'string'}

def build(root=DATA):
    selection=json.loads((L02/'research-selection.json').read_text())
    if selection['sha256']!=L02_SHA:raise ValueError('Changed L02 selection needs new L03 revision')
    source=L02/'acquisition-r1/raw'/PBP_SHA
    if sha(source.read_bytes())!=PBP_SHA:raise ValueError('PBP source hash mismatch')
    offerings=json.loads((L02/'build-r5/12021/offerings.json').read_text())
    if len({x['id'] for x in offerings})!=len(offerings):raise ValueError('Duplicate offering')
    out=root/'build-r1';out.mkdir(exist_ok=True)
    if (out/'RELEASE.json').exists() and json.loads((out/'RELEASE.json').read_text()).get('accepted'):raise ValueError('Accepted revision is immutable')
    tables=root/'acquisition-r1/tables';dictfile=next(tables.glob('*.xlsx'));dd=dictionary(dictfile)
    dump(out/'field-dictionary.json',{'year':2026,'source':'CMS-PBP-2026-TABLES','member':dictfile.name,'sha256':sha(dictfile.read_bytes()),'fields':list(dd.values()),'interpretation':'Source-field dictionary, not an accepted clinical or consumer benefit model.'})
    ids={(x['contract'],x['plan'],str(int(x['segment']))):x['id'] for x in offerings}
    plan_rows=collections.defaultdict(list);field_stats=collections.defaultdict(collections.Counter);unmapped=[];states=collections.Counter();table_manifest=[]
    with gzip.open(out/'table-fields.jsonl.gz','wt',encoding='utf-8') as fieldout,gzip.open(out/'table-rows.jsonl.gz','wt',encoding='utf-8') as rawout:
        for path in sorted(tables.glob('*.txt')):
            if path.name.startswith('Readme'):continue
            b=path.read_bytes();member_sha=sha(b);text=b.decode('cp1252');reader=csv.DictReader(io.StringIO(text,newline=''),delimiter='\t')
            headers=reader.fieldnames or []
            if not {'pbp_a_hnumber','pbp_a_plan_identifier','segment_id'}<=set(headers):continue
            count=0;nonblank=0
            for ordinal,row in enumerate(reader,1):
                if None in row:raise ValueError(f'Column overflow {path.name}:{ordinal}')
                k=(row['pbp_a_hnumber'],row['pbp_a_plan_identifier'].zfill(3),str(int(row['segment_id'])))
                if k not in ids:continue
                oid=ids[k];loc={'member':path.name,'member_sha256':member_sha,'record_ordinal':ordinal}
                rawout.write(json.dumps({'offering_id':oid,'source':loc,'raw':row},ensure_ascii=False)+'\n');count+=1
                plan_rows[oid].append({'table':path.stem,'record_ordinal':ordinal,'raw':row,'member_sha256':member_sha})
                for name,raw in row.items():
                    d=dd.get((path.stem.lower(),name.lower()));n=normalize(raw,d)
                    if path.stem in ['PlanArea','PlanRegionArea']:n={'state':'retained_other_layer_L02','value':raw,'type':'source_text'}
                    states[n['state']]+=1
                    stat=field_stats[(path.stem,name)];stat['instances']+=1;stat[n['state']]+=1
                    if raw!='':nonblank+=1
                    if not d and path.stem not in ['PlanArea','PlanRegionArea']:unmapped.append({'table':path.stem,'field':name,'offering_id':oid})
                    # All fields, including blank states, remain inspectable. A blank is not an exclusion.
                    fieldout.write(json.dumps({'offering_id':oid,'source':{**loc,'field':name},'dictionary_key':[path.stem.lower(),name.lower()],
                        'normalized':n,'raw':raw,'disposition':'retained_other_layer_L02' if path.stem in ['PlanArea','PlanRegionArea'] else 'technical_metadata' if name in TECH else 'reference_interpretation_required',
                        'condition_context':{'table_row':ordinal,'activation':'source controls retained; application to this field not yet fully reviewed'},
                        'carrier_corroboration':'pending','accepted':False},ensure_ascii=False)+'\n')
            table_manifest.append({'member':path.name,'sha256':member_sha,'headers':headers,'selected_rows':count,'selected_nonblank_cells':nonblank})
    dump(out/'table-inventory.json',table_manifest)
    dump(out/'source-field-dispositions.json',[{'table':t,'field':f,**dict(c),'required':'retained technical' if f in TECH else 'interpretation and carrier comparison required when substantive/applicable'} for (t,f),c in sorted(field_stats.items())])
    dump(out/'unmapped-table-fields.json',unmapped)
    raw_plans=[];instances=[];json_shapes=collections.defaultdict(collections.Counter);leaf_count=0;category_count=collections.Counter()
    with zipfile.ZipFile(source) as z,gzip.open(out/'json-leaves.jsonl.gz','wt',encoding='utf-8') as leafout:
        for o in offerings:
            name=f"{o['contract']}-{o['plan']}-{o['segment']}-2026.json";b=z.read(name);obj=json.loads(b);p=obj['pbp'][0]
            if obj['contractYear']!=2026 or p['contractId']!=o['contract'] or str(p['planId']).zfill(3)!=o['plan'] or str(p['segmentId']).zfill(3)!=o['segment']:raise ValueError('PBP identity mismatch '+o['id'])
            raw_plans.append({'offering_id':o['id'],'archive_sha256':PBP_SHA,'member':name,'member_sha256':sha(b),'bytes':len(b),'table_rows':len(plan_rows[o['id']])})
            for pointer,value in leaves(obj):
                leaf_count+=1;shape=re.sub(r'/\d+(?=/|$)','/*',pointer)
                st='source_null' if value is None else 'source_blank' if value=='' else 'empty_array' if value==[] else 'source_value'
                json_shapes[shape][st]+=1
                leafout.write(json.dumps({'offering_id':o['id'],'member':name,'member_sha256':sha(b),'pointer':pointer,'raw':value,'state':st,'interpretation':'retained; table/JSON mapping and carrier review separate'},ensure_ascii=False)+'\n')
            for i,v in enumerate(p.get('benefitDetails',{}).get('benefitDetailsInfo',[])):
                category_count[v['categoryCode']]+=1
                instances.append({'id':o['id']+':benefitDetails:'+str(i),'offering_id':o['id'],'category_code':v['categoryCode'],'category_type_id_raw':v.get('categoryTypeId'),
                    'pbp':{'archive_sha256':PBP_SHA,'member':name,'member_sha256':sha(b),'pointer':f'/pbp/0/benefitDetails/benefitDetailsInfo/{i}'},'raw':v,
                    'network_setting':'unresolved; do not infer categoryTypeId as network','required_reference':True,'normalized_benefit_claim':None,'carrier_corroboration':'pending','accepted':False})
            for section in ['planCharacteristics','planLevelCostSharing','priorAuthorizationAndReferral','visitorTravel','costShareGroups','vbid','rx']:
                instances.append({'id':o['id']+':'+section,'offering_id':o['id'],'section':section,'pbp':{'member':name,'member_sha256':sha(b),'pointer':'/pbp/0/'+section},
                    'raw':p.get(section),'required_reference':True,'normalized_benefit_claim':None,'carrier_corroboration':'pending','accepted':False})
    dump(out/'pbp-plan-manifest.json',raw_plans)
    with gzip.open(out/'benefit-instances.jsonl.gz','wt',encoding='utf-8') as f:
        for x in instances:f.write(json.dumps(x,ensure_ascii=False)+'\n')
    dump(out/'json-schema-inventory.json',[{'pointer_shape':k,**dict(v)} for k,v in sorted(json_shapes.items())])
    dump(out/'market-manifest.json',{'market':'12021','year':2026,'l02_build':'build-r5','l02_manifest_sha256':L02_SHA,'observed_offerings':offerings,'market_complete':False,'market_completeness_owner':'L02; no acceptance inherited','benefit_record_keys':['year','contract','plan','segment','variant'],'national_source_copied_per_county':False})
    summary={'input_offerings':len(offerings),'pbp_exact_matches':len(raw_plans),'json_leaf_instances':leaf_count,'json_pointer_shapes':len(json_shapes),'source_benefit_categories':len(category_count),
             'benefit_detail_instances':sum(category_count.values()),'required_context_bundles':7*len(offerings),'raw_and_context_instances':len(instances),
             'table_members':len(table_manifest),'table_rows':sum(x['selected_rows'] for x in table_manifest),'table_field_definitions':len(field_stats),'table_field_instance_states':dict(states),
             'dictionary_definitions':len(dd),'unmapped_table_field_instances':len(unmapped),'accepted_values':0,'consumer_display_values':0,'comprehensive':False,
             'required_semantic_field_instance_denominator':None,'denominator_gap':'Source inventory is complete for selected payloads; activation, JSON/table equivalence, applicable network/condition instances and carrier-only terms still need full semantic reconciliation.'}
    dump(out/'coverage-summary.json',summary)
    print(json.dumps(summary,indent=2))
    return summary

if __name__=='__main__':build()
