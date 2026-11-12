"""Independent saved-graph checks; no app import or database connection."""
from pathlib import Path
import hashlib
import itertools
import json

ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent
BASE=ROOT/'docs/data/l03-ma-benefits-2026-11-02-whole-offering-r12'
OLD=BASE/'carrier-network-referral-reconciliation-r1'
NEW=BASE/'carrier-network-referral-reconciliation-r2'

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p): return json.loads(p.read_text())
def truth(node, facts):
    op=node['op']
    if op=='predicate': return facts.get(node['text'])
    if op=='NOT':
        v=truth(node['arg'], facts)
        return None if v is None else not v
    vals=[truth(n,facts) for n in node['args']]
    if op=='AND': return False if False in vals else None if None in vals else True
    if op=='OR': return True if True in vals else None if None in vals else False
    raise AssertionError(op)

def effects(rule,facts):
    if truth(rule['when'],facts) is not True: return set()
    out=set()
    for branch in rule['branches']:
        if truth(branch['when'],facts) is True: out.update(branch['effect_indexes'])
    return out

def verify():
    checks=0
    def check(v):
        nonlocal checks
        assert v
        checks+=1
    for p in [OLD/'FREEZE_R1.json', NEW/'FREEZE_R2.json', HERE/'EXPECTED_FREEZE_R2.json']:
        for m in load(p)['members']:
            q=p.parent/m['path']
            check(q.is_file() and q.stat().st_size==m['bytes'] and sha(q)==m['sha256'])
    old=load(OLD/'SOURCE_RULE_GRAPHS.json'); new=load(NEW/'SOURCE_RULE_GRAPHS_R2.json')
    a={r['id']:r for r in old['rules']}; b={r['id']:r for r in new['rules']}
    check(list(a)==list(b) and len(a)==36)
    check({k:v for k,v in old.items() if k!='rules'}=={k:v for k,v in new.items() if k!='rules'})
    check([i for i in a if a[i]!=b[i]]==['NR10','NR15','NR34'])
    assets=load(NEW/'EFFECTIVE_ASSET_MANIFEST_R2.json')
    for value in assets.values():
        if isinstance(value,dict) and 'path' in value:
            q=ROOT/value['path']
            check(q.is_file() and q.stat().st_size==value['bytes'] and sha(q)==value['sha256'])
    retained=load(NEW/'RETAINED_HOLDS_AND_LINEAGE_STATUS_R2.json')
    prior=load(OLD/'TENSIONS_AND_NEXT_ACTIONS.json')
    check(retained['source_holds']==[x for x in prior['holds'] if x['id']!='T08'])
    check(retained['referral_state']=='unknown' and retained['outcome']=='insufficient_evidence')
    for i in a:
        if i not in ['NR10','NR15','NR34']: check(a[i]==b[i])
    parents={r['id'] for r in load(OLD/'SOURCE_PARENTS.json')['parents']}
    for i in ['NR10','NR15','NR34']:
        r=b[i]; check(r['factual_acceptance'] is False and r['complete_meaning_equivalence'] is False)
        check(r['branch_effect_binding']['mode']=='exhaustive')
        check(r['branch_effect_binding']['unbound_effects']==[])
        check(r['branch_effect_binding']['consumer_runtime_inference'] is False)
        indexes=[j for branch in r['branches'] for j in branch['effect_indexes']]
        check(sorted(indexes)==list(range(len(r['effects']))))
        for branch in r['branches']:
            check(set(branch['source_parent_ids'])<=parents)
    # All three-valued combinations of the four printed exceptions and parent scope.
    r=b['NR15']; names=[x['text'] for x in r['effects'][0]['predicate']['args']]
    cases15=0
    for scope in [True,False,None]:
        for values in itertools.product([True,False,None],repeat=4):
            facts=dict(zip(names,values));facts['OON care in most cases']=scope
            check((1 in effects(r,facts))==(scope is True and all(v is False for v in values)))
            cases15+=1
    # Paid/unpaid/cost disputes exercise distinct request versus reimbursement routes.
    payment=[
      ({'OON provider sent bill':True,'member thinks plan should pay bill':True}, {2}, 'unpaid bill; coverage not adjudicated'),
      ({'covered services':True,'OON provider':True,'member already paid for covered services':True}, {0,1}, 'already-paid covered OON service'),
      ({'covered services':True,'OON provider':True,'member already paid for covered services':False,'OON provider sent bill':True,'member thinks plan should pay bill':True}, {0,2}, 'covered unpaid OON bill'),
      ({'covered medical services':True,'member received bill for full covered-service cost':True}, {3}, 'full-cost bill request without payment'),
      ({'covered medical services':True,'member paid more than plan cost sharing':True}, {3}, 'overpaid request'),
      ({'covered medical services':False,'member received bill for full covered-service cost':True}, set(), 'uncovered bill is not a guaranteed plan payment'),
      ({'OON provider sent bill':True,'member thinks plan should pay bill':False}, set(), 'no forwarding request condition'),
    ]
    for f,want,label in payment:
        f=dict(f);f['covered-service payment procedure']=True
        check(effects(b['NR10'],f)==want)
    # Payment notice and documentation have no advance-permission predicate.
    common={'clinical research study participation':True,'participates in Medicare-approved study':True,'study services are covered':True}
    notice='member tells plan that member is in qualified clinical trial'
    paid='member paid more than IN cost sharing'
    docs='documentation showing paid cost sharing supplied'
    medicare='Medicare has paid its share of covered study services'
    trials=[
      ({}, {0}, 'Medicare share independent of plan notice'),
      ({notice:True}, {0,1}, 'notice has no advance deadline'),
      ({notice:True,paid:True}, {0,1,3}, 'documentation required before claimed refund'),
      ({notice:True,paid:True,docs:True}, {0,1,2,3}, 'already-paid documented difference'),
      ({notice:True,medicare:True,docs:True}, {0,1,5}, 'after-Medicare documented plan difference'),
      ({notice:False,paid:True,docs:True,medicare:True}, {0}, 'no unnotified noncoverage fact inferred'),
      ({'study not approved by Medicare':True,'participates in Medicare-approved study':False}, {6}, 'explicit nonapproval only'),
      ({'study not approved by Medicare':None,'participates in Medicare-approved study':None}, set(), 'missing approval is unknown'),
      ({'chooses participation in Medicare-qualified clinical trial':True}, {0,7}, 'advance notice encouraged separately'),
    ]
    for f,want,label in trials:
        facts=common|f
        check(effects(b['NR34'],facts)==want)
    return {'schema':'daylight.referral.correction-independent-replay.r2','checks_passed':checks,'all_243_ternary_exception_cases_passed':cases15,'independent_payment_cases':len(payment),'independent_trial_cases':len(trials),'unchanged_rules':33,'changed_rules':['NR10','NR15','NR34'],'new_acceptance':False,'source_truth_from_checker':False,'database_connection':False}

if __name__=='__main__':print(json.dumps(verify(),indent=2,sort_keys=True))
