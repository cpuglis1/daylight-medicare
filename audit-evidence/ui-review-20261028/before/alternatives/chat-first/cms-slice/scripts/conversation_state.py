"""Bounded tab-supplied state and nullable strict model deltas; no persistence."""
import copy
import re
from chat import schema
import cms_slice as cms

ENUMS={'helping':['self','someone_else','unknown'],'familiarity':['new','some','comfortable','unknown'],'pace':['explain','brief','unknown'],'path':['learn','review_current','see_plans','unknown']}
TERMS=['original_medicare','advantage','medigap','part_d','snp']
METRICS=['monthly_premium','medical_limit','drug_deductible']
UNSCORED=['doctors','medicines','dental','vision','hearing','travel','annual_cost']
PLAN_PATTERN=r'[HRS]\d{4}-\d{3}-\d{3}-2027'
CONTEXT_FIELDS=['zip','county','medicare','timing','drugs','hearing','vision','dental']

def strings(limit=120, count=9, choices=None):
    item={'type':'string','maxLength':limit}
    if choices is not None: item['enum']=choices
    return {'type':'array','items':item,'maxItems':count}

SCREEN=schema({'view':{'type':'string','enum':['none','catalog','plan','comparison','education']},'category':{'type':['string','null'],'enum':['all','MA-PD','MA','PDP','SNP',None]},'sorted_by':strings(choices=METRICS,count=3),'unscored':strings(choices=UNSCORED,count=7),'plan_ids':strings(limit=22,count=3)})
SELECTIONS=schema({'plan_ids':strings(limit=22,count=3),'rxcuis':strings(limit=8,count=15),'pharmacy_npi':{'type':['string','null'],'maxLength':10}})
FIELDS={**{k:{'type':'string','enum':v} for k,v in ENUMS.items()},'reason':{'type':['string','null'],'maxLength':240},'priorities':strings(),'current_coverage':{'type':['string','null'],'maxLength':240},'terms_explained':strings(choices=TERMS,count=5),'open_question':{'type':['string','null'],'maxLength':300},'on_screen':SCREEN,'selections':SELECTIONS,'coverage_context':schema({k:{'type':['string','null'],'maxLength':100} for k in CONTEXT_FIELDS})}
DEFAULT={**{k:'unknown' for k in ENUMS},'reason':None,'priorities':[],'current_coverage':None,'terms_explained':[],'open_question':None,'on_screen':{'view':'none','category':None,'sorted_by':[],'unscored':[],'plan_ids':[]},'selections':{'plan_ids':[],'rxcuis':[],'pharmacy_npi':None},'coverage_context':{k:None for k in CONTEXT_FIELDS}}

def nullable(spec):
    spec=copy.deepcopy(spec)
    types=spec['type'] if isinstance(spec['type'],list) else [spec['type']]
    spec['type']=list(dict.fromkeys(types+['null']))
    if 'enum' in spec and None not in spec['enum']:spec['enum'].append(None)
    if spec.get('properties'):
        spec['properties']={k:nullable(v) for k,v in spec['properties'].items()}
    return spec

UPDATE_SCHEMA=schema({k:nullable(v) for k,v in FIELDS.items()})

def validate(value,spec):
    types=spec['type'] if isinstance(spec['type'],list) else [spec['type']]
    kind='null' if value is None else 'object' if isinstance(value,dict) else 'array' if isinstance(value,list) else 'string' if isinstance(value,str) else 'invalid'
    if kind not in types:raise cms.SourceError('Invalid conversation state type')
    if 'enum' in spec and value not in spec['enum']:raise cms.SourceError('Unknown conversation state value')
    if kind=='string' and len(value)>spec.get('maxLength',300):raise cms.SourceError('Conversation state is too long')
    if kind=='array':
        if len(value)>spec.get('maxItems',15):raise cms.SourceError('Invalid conversation state list')
        for item in value:validate(item,spec['items'])
        if len(set(value))!=len(value):raise cms.SourceError('Invalid conversation state list')
    if kind=='object':
        if set(value)-set(spec['properties']):raise cms.SourceError('Unknown conversation state field')
        for key,item in value.items():validate(item,spec['properties'][key])

def normalized(value=None):
    value={} if value is None else value
    validate(value,schema(FIELDS))
    result=copy.deepcopy(DEFAULT)
    for key,item in value.items():
        if key in {'on_screen','selections','coverage_context'}:result[key].update(item)
        else:result[key]=copy.deepcopy(item)
    for pid in result['selections']['plan_ids']+result['on_screen']['plan_ids']:
        if not re.fullmatch(PLAN_PATTERN,pid):raise cms.SourceError('Invalid selected plan')
    for code in result['selections']['rxcuis']:
        if not re.fullmatch(r'[1-9]\d{0,7}',code):raise cms.SourceError('Invalid medicine choice')
    npi=result['selections']['pharmacy_npi']
    if npi is not None and not re.fullmatch(r'\d{10}',npi):raise cms.SourceError('Invalid pharmacy choice')
    zip_code=result['coverage_context']['zip']
    if zip_code is not None and not re.fullmatch(r'\d{5}',zip_code):raise cms.SourceError('Invalid ZIP')
    return result

def changed(value,current):
    validate(value,UPDATE_SCHEMA)
    # on_screen and explicit product identities are controlled by user actions.
    delta={k:v for k,v in value.items() if v is not None and k not in {'on_screen','selections'}}
    for key in ['coverage_context']:
        if key in delta:delta[key]={**current[key],**{k:v for k,v in delta[key].items() if v is not None}}
    normalized({**current,**delta})
    return {k:v for k,v in delta.items() if v!=current.get(k)}
