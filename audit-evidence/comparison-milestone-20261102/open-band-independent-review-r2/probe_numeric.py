"""Independent exact-number regression and immutable schema-delta replay."""
from pathlib import Path
import contextlib
import copy
from decimal import Decimal
import hashlib
import io
import json
import runpy
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
with contextlib.redirect_stdout(io.StringIO()):
    namespace=runpy.run_path(str(HERE/'probe_candidate.py'))
model=namespace['model'];fixture=namespace['fixture'];identity=namespace['identity']
candidate=namespace['CANDIDATE']
digit_guard=sys.get_int_max_str_digits()
rows=[]

def check_pair(name, left, right, setter, expected):
    a,b=fixture('cms'),fixture('carrier')
    setter(a,left);setter(b,right)
    before=copy.deepcopy((a,b))
    result=model.compare(a,b,expected_identity=identity)
    ok=result['outcome']==expected and not result['accepted_for_reference'] and (a,b)==before
    rows.append({'case':name,'expected':expected,'actual':result['outcome'],
                 'differences':result['differences'],'pass':ok,'inputs_unchanged':(a,b)==before})

band=lambda o,v:o['boundaries']['day_bands'][0].update(amount=v)
check_pair('huge integer one-unit distinction',10**400,10**400+1,band,'conflict')
check_pair('huge text one-unit distinction',str(10**400),str(10**400+1),band,'conflict')
p='1.00000000000000000000000000001';q='1.00000000000000000000000000002'
check_pair('29th-digit distinction',p,q,band,'conflict')
for left,right in [('7','7.00000'),('7e0','0.7e1'),('-0','0.000e-20'),
                    ('0.1000000000000000001','0.100000000000000000100000')]:
    check_pair('exact decimal equivalence '+left+' / '+right,left,right,band,'exact_agreement')
for key in ['amount','minimum','maximum','percentage']:
    check_pair('shared-budget '+key,p,q,
               lambda o,v,k=key:o.update(shared_budgets=[{'id':'ROOT-SYNTHETIC-BUDGET',k:v}]),'conflict')
    check_pair('generic quantity '+key,p,q,
               lambda o,v,k=key:o['boundaries'].update(quantity={k:v}),'conflict')
check_pair('generic frequency percentage',p,q,
           lambda o,v:o['boundaries'].update(frequency={'percentage':v}),'conflict')
check_pair('exception maximum',p,q,lambda o,v:o.update(exceptions=[{'maximum':v}]),'conflict')

huge=10**10000
def huge_dates(o,start):
    o['boundaries']['day_bands']=[{'begin':start,'end':start+4,'amount':'7','unit':'USD/day'},
                                 {'begin':start+5,'end':start+9,'amount':'0','unit':'USD/day'}]
    o['boundaries']['schedule_scope'].update(start_day=start,terminal_end=start+9)
check_pair('matching dates with10**10000 (in-memory synthetic only)',huge,huge,huge_dates,'exact_agreement')
check_pair('matching monetary10**10000 (in-memory synthetic only)',huge,huge,band,'exact_agreement')
check_pair('monetary10**10000 one-unit distinction',huge,huge+1,band,'conflict')

# No float/context normalization: cross-check values against exact Decimal
# equality over an independently chosen small deterministic lexical population.
lexical=['0','-0','0.0000','1','1.00','10e-1','0.1','1e-1',p,q,
         '123456789012345678901234567890.00','123456789012345678901234567891',
         '7.125','7125e-3','1e+400','10e+399']
canonical_checks=0
for a in lexical:
    for b in lexical:
        expected=Decimal(a)==Decimal(b)
        actual=model.canonical({'amount':a})==model.canonical({'amount':b})
        assert actual==expected,(a,b)
        canonical_checks+=1

sealed=ROOT/'docs/data/l03-ma-benefits-2026-10-25/semantic-inventory-r9/comparison-record.schema.json'
schema=json.loads(sealed.read_text())
delta=json.loads((candidate/'schema_delta.json').read_text())
for op in delta:
    parts=[v.replace('~1','/').replace('~0','~') for v in op['path'].split('/')[1:]]
    target=schema
    for part in parts[:-1]:target=target[int(part)] if isinstance(target,list) else target[part]
    part=parts[-1]
    if isinstance(target,list):
        if part=='-':target.append(copy.deepcopy(op['value']))
        elif op['op']=='replace':target[int(part)]=copy.deepcopy(op['value'])
        else:target.insert(int(part),copy.deepcopy(op['value']))
    else:target[part]=copy.deepcopy(op['value'])
assert schema==json.loads((candidate/'comparison-record.schema.json').read_text())
assert hashlib.sha256((candidate/'comparison-record.schema.json').read_bytes()).hexdigest()==hashlib.sha256((candidate.parent/'open-band-comparison-contract-r1/comparison-record.schema.json').read_bytes()).hexdigest()
assert digit_guard==sys.get_int_max_str_digits()
assert all(x['pass'] for x in rows)
print(json.dumps({'numeric_comparison_scenarios':len(rows),'passed':sum(x['pass'] for x in rows),
                  'exact_decimal_equality_cross_checks':canonical_checks,
                  'schema_delta_operations_replayed':len(delta),'r1_r2_storage_schema_identical':True,
                  'integer_string_limit_unchanged':True,'results':rows,
                  'real_source_records_changed':False,'source_acceptance':False,'writes_performed':False},indent=2))
