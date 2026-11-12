"""Independent exact-delta replay; reads saved artifacts only."""
from pathlib import Path
import hashlib,json
ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent
BASE=ROOT/'docs/data/l03-ma-benefits-2026-11-02-whole-offering-r12'
OLD=BASE/'structured-annual-wellness-comparison-r1'
NEW=BASE/'structured-annual-wellness-comparison-r2'
def load(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def differences(a,b,path=''):
    if type(a)!=type(b):return [path]
    if isinstance(a,dict):
        if a.keys()!=b.keys():return [path]
        return [p for k in a for p in differences(a[k],b[k],path+'/'+k)]
    if isinstance(a,list):
        if len(a)!=len(b):return [path]
        return [p for i,(x,y) in enumerate(zip(a,b)) for p in differences(x,y,path+'/'+str(i))]
    return [] if a==b else [path]
def verify():
    checks=0
    def check(value):
        nonlocal checks
        assert value
        checks+=1
    for f in [OLD/'FREEZE_R1.json',NEW/'FREEZE_R2.json',HERE/'EXPECTED_FREEZE_R2.json']:
        for member in load(f)['members']:
            q=f.parent/member['path']
            check(q.stat().st_size==member['bytes']);check(sha(q)==member['sha256'])
    a=load(OLD/'COMPARISON_RECORDS_R1.json');b=load(NEW/'COMPARISON_RECORDS_R2.json')
    paths=differences(a,b)
    check(paths==['/0/id','/0/carrier/exceptions/0/scope','/1/id','/1/carrier/exceptions/0/scope'])
    for old,new in zip(a,b):
        check(new['id']==old['id'].replace('AWV-R1-','AWV-R2-'))
        check(new['accepted_for_reference'] is False and new['outcome']==old['outcome'])
        check(new['inventory_root_ids']==old['inventory_root_ids'])
        check(new['carrier']['conditions']==old['carrier']['conditions'])
        check(new['cms']==old['cms'])
        text=new['carrier']['exceptions'][0]['scope']
        for fragment in ['covered at no cost under Original Medicare','AND a network provider is used','treated OR monitored','copayment WILL APPLY','separate tests MAY']:
            check(fragment in text)
    check('Retained IN source context only' in b[1]['carrier']['exceptions'][0]['scope'])
    check('OON concurrent-service pricing remains unresolved' in b[1]['carrier']['exceptions'][0]['scope'])
    d1=load(OLD/'DIMENSION_COMPARISON_AND_HOLDS.json');d2=load(NEW/'DIMENSION_COMPARISON_AND_HOLDS_R2.json')
    dp=differences(d1,d2)
    check(dp==['/dimensions/6/carrier_by_network/in_network/0/scope','/dimensions/6/carrier_by_network/out_of_network/0/scope','/holds/5/question'])
    for i,network in enumerate(['in_network','out_of_network']):
        check(d2['dimensions'][6]['carrier_by_network'][network][0]['scope']==b[i]['carrier']['exceptions'][0]['scope'])
    check(len(d2['holds'])==8 and all(h['state']=='held' for h in d2['holds']))
    assets=load(NEW/'EFFECTIVE_ASSET_MANIFEST_R2.json')
    check(len(assets['inherited_unchanged_assets'])==44)
    for member in assets['effective_comparison_assets']+assets['inherited_unchanged_assets']+assets['superseded_only_within_this_new_candidate']:
        q=ROOT/member['path'];check(sha(q)==member['sha256']);check(q.stat().st_size==member['bytes'])
    check(assets['original_dependencies']==608 and assets['proposed_children']==13)
    check(assets['authoritative_or_adopted_changes']==0 and assets['factual_acceptance'] is False)
    return {'schema':'daylight.annual-wellness.independent-correction-replay.r2','checks_passed':checks,'record_changed_paths':paths,'dimension_changed_paths':dp,'inherited_assets_replayed':44,'findings_corrected_in_new_view':['AWV-R1-F01'],'new_acceptance':False,'source_meaning_from_checker':False,'database_or_network_connection':False}
if __name__=='__main__':print(json.dumps(verify(),indent=2,sort_keys=True))
