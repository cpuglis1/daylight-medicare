"""Independent synthetic fixtures for the expectations sealed before code review."""
from pathlib import Path
import copy
import hashlib
import importlib.util
import json
import sys
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
CANDIDATE=ROOT/'docs/data/l03-ma-benefits-2026-11-02-whole-offering-r12/open-band-comparison-contract-r1'
spec=importlib.util.spec_from_file_location('independently_probed_open_band',CANDIDATE/'open_band_comparison.py')
model=importlib.util.module_from_spec(spec);spec.loader.exec_module(model)
expected={x['id']:x for x in json.loads((HERE/'EXPECTED_CASES.json').read_text())['cases']}
identity={'year':2026,'contract':'H5652','plan':'002','segment':'000',
          'geography':'ROOT SYNTHETIC geography','geographic_variant':'ROOT SYNTHETIC pinned variant'}
rule_text='ROOT SYNTHETIC: this stay satisfies published conditions X and Y; no personal determination.'

def fixture(side, *, opened=False):
    evidence_id=side+'-ROOT-SYNTHETIC-EVIDENCE'
    review_id=side+'-ROOT-SYNTHETIC-REVIEW'
    conditions={f:{'state':'documented_inapplicable','assertion':'ROOT SYNTHETIC explicit inapplicability '+f,
                   'obligation_ids':[side+'-ROOT-'+f],'evidence_ids':[evidence_id],
                   'interpretation_review_id':review_id} for f in model.CONDITION_FAMILIES}
    conditions['covered_days'].update(state='asserted',assertion=rule_text)
    evidence={'id':evidence_id,'source_sha256':'c'*64,'side':side,'interpretation_review_id':review_id}
    if side=='cms':evidence.update(member='ROOT-SYNTHETIC.json',pointer='/root/synthetic/ordinary')
    else:evidence.update(pdf_page=9,passage_sha256='d'*64,location={'line_start':4,'line_end':9},
                         headers=['ROOT SYNTHETIC covered inpatient row'],footnotes=[])
    end=90
    rules=[]
    if opened:
        end={'state':'unbounded','covered_stay_rule_id':side+'-ROOT-RULE',
             'evidence_ids':[evidence_id],'interpretation_review_id':review_id}
        rules=[{'id':side+'-ROOT-RULE','source_statement_kind':'explicit_unlimited_covered_stay',
                'predicate':rule_text,'condition_obligation_ids':conditions['covered_days']['obligation_ids'],
                'evidence_ids':[evidence_id],'interpretation_review_id':review_id}]
    result={'identity':copy.deepcopy(identity),'service':{'category':'1a','subtype':'ROOT SYNTHETIC category type 1'},
            'context':{'network':'in_network','setting':'ROOT SYNTHETIC inpatient',
                       'population':'ROOT SYNTHETIC nominal','assistance_basis':'nominal'},
            'cost':{'kind':'copayment','amount':{'state':'schedule_defined'},'range_basis':'ROOT complete ordered schedule'},
            'unit':{'currency_or_percentage':'USD','denominator':'day','period':'admission'},
            'boundaries':{'day_bands':[{'begin':1,'end':5,'amount':'7.00','unit':'USD/day'},
                                       {'begin':6,'end':end,'amount':'0','unit':'USD/day'}],
                          'quantity':'ROOT SYNTHETIC conditional covered days','frequency':'each admission','reset':'each admission',
                          'schedule_scope':{'state':'complete','start_day':1,
                                            'terminal_end':{'state':'unbounded'} if opened else 90,
                                            'evidence_ids':[evidence_id],'interpretation_review_id':review_id}},
            'conditions':conditions,'exceptions':[],
            'variant':{'kind':'base','identifier':'ROOT SYNTHETIC base','enrollment_basis':'ROOT SYNTHETIC plan enrollment','effective_period':'2026'},
            'shared_budgets':[],'evidence':[evidence],'covered_stay_rules':rules}
    return result

results=[]
def run(case_id, change=None, *, opened=False, both=False, extra=None):
    a,b=fixture('cms',opened=opened),fixture('carrier',opened=opened)
    if change:
        change(b)
        if both:change(a)
    try:
        answer=model.compare(a,b,expected_identity=identity,**(extra or {}))
        ok=answer['outcome'] in expected[case_id]['permitted_result'] and answer['accepted_for_reference'] is False
        results.append({'case_id':case_id,'pass':ok,'outcome':answer['outcome'],
                        'differences':answer['differences'],'readiness_errors':answer['readiness_errors']})
    except Exception as e:
        results.append({'case_id':case_id,'pass':False,'exception':type(e).__name__,'message':str(e)})

run('FINITE')
run('DECIMAL',lambda x:x['boundaries']['day_bands'][0].update(amount='7'))
run('OPEN-COMPLETE',opened=True)
def finite999(x):
    x['boundaries']['day_bands'][-1]['end']=999
    x['boundaries']['schedule_scope']['terminal_end']=999
    x['covered_stay_rules']=[]
run('RAW999',finite999,opened=True)
def unknown_end(x,state):
    x['boundaries']['day_bands'][-1]['end']={'state':state,'reason':'ROOT SYNTHETIC source limitation'}
    x['boundaries']['schedule_scope']['terminal_end']={'state':state,'reason':'ROOT SYNTHETIC source limitation'}
run('NOT-STATED',lambda x:unknown_end(x,'source_not_stated'),opened=True,both=True)
run('UNKNOWN',lambda x:unknown_end(x,'unknown'),opened=True,both=True)
run('NULL',lambda x:x['boundaries']['day_bands'][-1].update(end=None),opened=True)
run('RULE-MISSING',lambda x:x.update(covered_stay_rules=[]),opened=True)
run('RULE-UNBOUND',lambda x:x['covered_stay_rules'][0].update(condition_obligation_ids=['ROOT-unbound']),opened=True)
def different_rule(x):
    text='ROOT SYNTHETIC different condition Z'
    x['covered_stay_rules'][0]['predicate']=text
    x['conditions']['covered_days']['assertion']=text
run('RULE-DIFFERENT',different_rule,opened=True)
run('RULE-UNKNOWN',lambda x:x['covered_stay_rules'][0].update(predicate='unknown'),opened=True,both=True)
def append_after_open(x):
    x['boundaries']['day_bands'].append({'begin':10,'end':12,'amount':'0','unit':'USD/day'})
    x['boundaries']['schedule_scope']['terminal_end']=12
run('LAST-BAND',append_after_open,opened=True)
def omit_later(x):
    x['boundaries']['day_bands'].pop()
    x['boundaries']['schedule_scope']['terminal_end']=5
    x['covered_stay_rules']=[]
run('LATER-ZERO',omit_later,opened=True)
run('GAP',lambda x:x['boundaries']['day_bands'][1].update(begin=7))
run('OVERLAP',lambda x:x['boundaries']['day_bands'][1].update(begin=5))
run('REVERSE',lambda x:x['boundaries']['day_bands'][1].update(end=4))
run('BOOLEAN-DAY',lambda x:x['boundaries']['day_bands'][0].update(begin=True))
run('AMOUNT-CHANGE',lambda x:x['boundaries']['day_bands'][1].update(amount='3'),opened=True)
for value in ['NaN','Infinity','-Infinity']:
    run('NONFINITE-AMOUNT',lambda x,v=value:x['boundaries']['day_bands'][0].update(amount=v),opened=True)
run('DAY-VS-STAY',lambda x:x['unit'].update(denominator='stay'),opened=True)
run('NETWORK',lambda x:x['context'].update(network='out_of_network'),opened=True)
run('CURRENCY',lambda x:x['unit'].update(currency_or_percentage='percentage'),opened=True)
run('RESET',lambda x:x['boundaries'].update(reset='Medicare benefit period'),opened=True)
run('PARTIAL-ANCHOR',lambda x:x['cost'].update(amount='375'),opened=True,both=True)
run('SCHEDULE-SCOPE',lambda x:x['boundaries'].pop('schedule_scope'),opened=True)
run('NATIVE-CATEGORIES',lambda x:x['service'].update(category='1a1',subtype='ROOT SYNTHETIC category type 2'),opened=True)
for family in model.CONDITION_FAMILIES:
    run('MISSING-CONDITION',lambda x,f=family:x['conditions'].pop(f),opened=True)
run('MISSING-EVIDENCE',lambda x:x['evidence'][0].pop('footnotes'),opened=True)
for key,value in [('year',2027),('plan','001'),('segment','001')]:
    run('WRONG-IDENTITY',lambda x,k=key,v=value:x['identity'].update({k:v}),opened=True)
run('SCOPE-PLACEHOLDER',lambda x:x['context'].update(network='source_default_network'),opened=True,both=True)
run('ARBITRARY-MAPPING',lambda x:x['boundaries'].update(reset='different reset'),opened=True,
    extra={'mapping':'ROOT-MADE-UP','mapping_registry':{'ROOT-MADE-UP':{'review_decision':'accepted_mapping'}}})
results.append({'case_id':'NO-ACCEPTANCE','pass':all(x.get('outcome') is not None for x in results),
                'assertion':'Every result above checked accepted_for_reference is false.'})

# Supplemental robustness probes were selected after reading this code, not
# part of the pre-code expected set. Report crashes separately from that set.
robustness=[]
for target in ['begin','end','amount']:
    a,b=fixture('cms'),fixture('carrier')
    b['boundaries']['day_bands'][0][target]=10**400
    try:
        r=model.compare(a,b,expected_identity=identity)
        robustness.append({'target':target,'exception':None,'outcome':r['outcome']})
    except Exception as e:
        robustness.append({'target':target,'exception':type(e).__name__,'message':str(e)})
covered={x['case_id'] for x in results}
assert covered==set(expected), sorted(set(expected)-covered)
print(json.dumps({'producer_freeze_sha256':hashlib.sha256((CANDIDATE/'FREEZE_R1.json').read_bytes()).hexdigest(),
                  'pre_code_expected_cases':len(expected),'independent_scenarios':len(results),
                  'passed':sum(x['pass'] for x in results),'failures':[x for x in results if not x['pass']],
                  'results':results,'post_code_supplemental_robustness':robustness,
                  'factual_source_acceptance':False,'writes_performed':False},indent=2))
