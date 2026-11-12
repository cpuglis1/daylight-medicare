"""Read-only public-source audit for literal L08 name discovery."""
from datetime import datetime, timezone
import getpass
import hashlib
import json
from pathlib import Path
import sys
import time
import argparse

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'infrastructure/daylight-data/src'))
from daylight_data.serving.provider_candidates import provider_candidate_repository_from_env, _label
from daylight_data.serving.provider_identity import provider_repository_from_env


def main(output):
    if output.exists():raise ValueError('Preserve the earlier audit; select a new output path.')
    dsn=('host='+str(ROOT/'infrastructure/daylight-data/.state/socket')+
         ' port=55485 dbname=daylight_research_2026_r2 user='+getpass.getuser())
    source=provider_repository_from_env(repository_root=ROOT,dsn=dsn)
    discovery=provider_candidate_repository_from_env(repository_root=ROOT,dsn=dsn)
    checks=[];cases=[]
    def check(name,ok):
        checks.append({'name':name,'passed':bool(ok)})
        if not ok:raise AssertionError(name)
    def search(case_id,text,**kwargs):
        start=time.perf_counter();out=discovery.search(text,**kwargs)
        cases.append({'case_id':case_id,'name_text':text,'elapsed_ms':round((time.perf_counter()-start)*1000,3),
            'binding':out['binding'],'count':out['candidate_count'],'page':out['page'],
            'partial':out['partial'],'discovery_state':out['discovery_state'],
            'candidate_checks':[{'candidate_id':row['candidate_id'],'entity_key':row['entity_key'],
                'label':row['label'],'type':row['source_native_fields']['type'],
                'lineage':row['lineage'],'locator_verified':bool(row['source_observation_locator']
                    and row['source_observation_locator']['raw_parent_verified']),
                'identity_detail_state':row['identity_detail_state']}
                for row in out['candidates']]})
        check(case_id+'_all_purposes_held',all(value['state']=='held' for value in out['authority'].values()))
        check(case_id+'_operator_only_no_auto_binding',out['operator_only'] and not out['consumer_release']
            and not out['automatic_profile_binding'])
        check(case_id+'_no_coverage_or_city_inference',out['network_status']=='not_evaluated'
            and out['partial']['reported_city_not_filtered'])
        return out
    started=time.perf_counter()
    try:
        exact=source.lookup(npi='1922013515')
        entity=exact['entity_candidates'][0]
        public_label=_label(entity['source_native_fields']['name']).split(' / ')[0]
        # Deliberately source-mirroring PUBLIC names, not customer profile data.
        query=' '.join(public_label.split()[:6])[:160]
        first=search('known_public_entity',query)
        check('known_entity_preserved',any(candidate['entity_key']==entity['source_native_fields']['entity_key']
              for candidate in first['candidates']))
        title=search('leading_title_discovery_only','Dr. '+query)
        check('title_not_identity_inference',title['requested']['leading_title_omitted_for_discovery_only']==['Dr.']
              and {c['candidate_id'] for c in title['candidates']}=={c['candidate_id'] for c in first['candidates']})
        broad=search('source_order_page_one','Health',limit=2)
        if broad['page']['has_more']:
            later=search('source_order_page_two','Health',limit=2,
                after_ordinal=broad['page']['next_after_ordinal'],expected_snapshot_id=broad['binding']['snapshot_id'])
            check('pages_do_not_repeat',set(c['candidate_id'] for c in broad['candidates']).isdisjoint(
                c['candidate_id'] for c in later['candidates']))
        for key,text in [('literal_percent','%'),('literal_underscore','_'),('literal_exclamation','!')]:
            out=search(key,text)
            check(key+'_only_literal_names',all(text in json.dumps(c['source_native_fields']['name']) for c in out['candidates']))
        absent=search('fictional_absent_name','ZZZ-FICTIONAL-NO-MATCH-20261102')
        check('absent_is_scoped_unknown',not absent['candidates']
              and absent['discovery_state']=='not_observed_in_selected_literal_query')
        report={'schema':'daylight.actual-provider-literal-discovery.v1',
            'observed_at':datetime.now(timezone.utc).isoformat(),'passed':all(c['passed'] for c in checks),
            'checks':checks,'cases':cases,'elapsed_ms':round((time.perf_counter()-started)*1000,3),
            'fixture_kind':'public_source_name_mirroring_no_customer_data',
            'source_access_registration':first['source_access_registration'],
            'postgres_writes':0,'schema_writes':0,'real_guest_profile_reads':False,'paid_ai_calls':0,
            'consumer_release':False,'new_acceptance':False,
            'code_sha256':{str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest() for path in
                [ROOT/'infrastructure/daylight-data/src/daylight_data/serving/provider_candidates.py',
                 ROOT/'infrastructure/daylight-data/tests/test_research_provider_candidates.py',Path(__file__).resolve()]}}
        output.parent.mkdir(parents=True,exist_ok=True)
        with output.open('x') as handle:json.dump(report,handle,indent=2);handle.write('\n')
        print(json.dumps({'passed':report['passed'],'checks':len(checks),'cases':len(cases),
            'elapsed_ms':report['elapsed_ms'],'output':str(output)}))
    finally:source.close();discovery.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    main(parser.parse_args().output.resolve())
