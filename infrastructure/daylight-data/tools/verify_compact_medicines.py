"""Read-only identity/lookup invariance audit using retained public drug data."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

PACKAGE=Path(__file__).resolve().parents[1]
ROOT=PACKAGE.parents[1]
sys.path.insert(0,str(PACKAGE/'src'))
from daylight_data.serving.identity import identity_repository_from_env
from daylight_data.serving.drug_candidates import candidate_repository_from_env
from daylight_data.serving.binding import ResearchServingError


def canonical_hash(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()


def audit(output):
    dsn='host='+str(PACKAGE/'.state/socket')+' port=55485 dbname=daylight_research_2026_r2 user=cep4u'
    exact=identity_repository_from_env(repository_root=ROOT,dsn=dsn)
    discovery=candidate_repository_from_env(repository_root=ROOT,dsn=dsn)
    started=time.monotonic()
    with exact._read() as (db,_):
        rows=db.execute("SELECT fields->>'rxcui' AS rxcui,fields->>'drug_name' AS name FROM dl_evidence.observation WHERE derivation_id=%s AND entity_type='drug_product' ORDER BY source_row_ordinal LIMIT 2",(exact.binding.selections['drug_identity']['derivation_id'],)).fetchall()
    if len(rows)!=2:raise ValueError('Retained public dictionary unavailable')
    positive=exact.lookup_rxcuis([x['rxcui'] for x in rows])
    absent=exact.lookup_rxcuis(['9999999999'])
    named=discovery.search(rows[0]['name'][:160])
    if not all(x['state']=='exact_id_candidate' for x in positive['matches']):raise ValueError('Known public identity lost')
    if absent['candidates'] or absent['matches'][0]['state']!='not_observed_in_selected_dictionary':raise ValueError('Unknown drug semantics changed')
    if not any(x['identity']['rxcui']==rows[0]['rxcui'] for x in named['candidates']):raise ValueError('Literal discovery lost')
    for result in (positive,absent,named):
        if result.get('consumer_release') is not False or result.get('automatic_profile_binding') is not False:
            raise ValueError('Identity result promoted')
        if not all(x['state']=='held' for x in result['authority'].values()):raise ValueError('Consumer authority changed')
    try:exact.lookup_rxcuis([rows[0]['rxcui']],year=2027)
    except ResearchServingError:pass
    else:raise ValueError('Wrong-year request accepted')
    result={'passed':True,'fixture_kind':'retained_public_dictionary_no_customer_inputs','known_rxcuis':[x['rxcui'] for x in rows],
       'positive_sha256':canonical_hash(positive),'absent_sha256':canonical_hash(absent),'literal_search_sha256':canonical_hash(named),
       'wrong_year_rejected':True,'unknown_is_not_noncoverage':True,'all_consumer_purposes_held':True,
       'automatic_binding':False,'seconds':time.monotonic()-started,'new_acceptance':False}
    with output.open('x') as f:json.dump(result,f,indent=2);f.write('\n')
    print(json.dumps(result),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True,type=Path)
    audit(p.parse_args().output)
