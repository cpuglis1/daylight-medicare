"""Read-only actual dictionary + explicitly fictional identity-choice audit.

The fixture mirrors public source labels to exercise the technical association;
it is not a customer confirmation, clinical match or live guest journey.
"""
import argparse
import copy
from datetime import datetime, timezone
import getpass
import hashlib
import json
from pathlib import Path
import secrets
import sys
import time

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
sys.path[:0] = [str(HERE), str(HERE/'tests'), str(ROOT/'infrastructure/daylight-data/src')]
from identity_resolution import DrugIdentityChoices, IdentityResolutionError
from comparison_evidence import canonical_sha256
from daylight_data.serving.drug_candidates import candidate_repository_from_env
from daylight_data.serving.identity import identity_repository_from_env
from test_comparison_methods import profile, fact, NAME, STRENGTH, SCOPE


def main(output):
    if output.exists():
        raise ValueError('Preserve existing receipt; choose a new output path.')
    dsn = ('host=' + str(ROOT/'infrastructure/daylight-data/.state/socket') +
           ' port=55485 dbname=daylight_research_2026_r2 user=' + getpass.getuser())
    repository = identity_repository_from_env(repository_root=ROOT, dsn=dsn)
    discovery = candidate_repository_from_env(repository_root=ROOT, dsn=dsn)
    checks = []
    def check(name, passed):
        checks.append({'name':name,'passed':bool(passed)})
        if not passed:raise AssertionError(name)
    started=time.perf_counter()
    owner=secrets.token_hex(32)
    try:
        source=repository.lookup_rxcuis(['1000048'],year=2026)
        candidate=source['candidates'][0]
        check('exact_retained_product_candidate',candidate['identity_grain']=='drug_product_concept'
              and candidate['identity_detail_state']=='source_details_present')
        found=discovery.search(candidate['identity']['drug_name'],limit=20)
        lexical=next((row for row in found['candidates'] if row['candidate_id']==candidate['candidate_id']),None)
        check('literal_name_discovery_preserves_exact_candidate',lexical is not None
              and lexical['identity']['rxcui']=='1000048'
              and lexical['lineage']==candidate['lineage'])
        check('discovery_is_not_confirmation',found['operator_only'] is True
              and lexical['lexical_occurrence_is_not_identity_or_dose_equivalence'] is True
              and lexical['automatic_profile_binding'] is False)
        case=profile()
        # Explicitly source-mirroring synthetic reports, never real user data.
        for leaf,key in [('name','drug_name'),('strength','ingredient_strength_description'),('form','dose_form')]:
            fact(case,'readiness.facts.RC22.value.items[].'+leaf,'medicine-1')['value']=candidate['identity'][key]
        case['profile_binding'].pop('normalized_sha256',None)
        case['profile_binding']['normalized_sha256']=canonical_sha256(case)
        before=copy.deepcopy(case)
        service=DrugIdentityChoices(repository)
        offer=service.offer(owner,case,item_id='medicine-1',rxcuis=[lexical['identity']['rxcui']],scope=SCOPE)
        check('source_snapshot_and_raw_parent_preserved',offer['source_binding']['snapshot_id']==source['binding']['snapshot_id']
              and offer['candidates'][0]['lineage']==candidate['lineage'])
        try:service.confirm(owner,case,choice_token=offer['choice_token'],candidate_id=candidate['candidate_id'])
        except IdentityResolutionError:check('no_automatic_confirmation',True)
        else:check('no_automatic_confirmation',False)
        result=service.confirm(owner,case,choice_token=offer['choice_token'],candidate_id=candidate['candidate_id'],confirmed=True)
        check('explicit_fictional_selection_only',result['choice_state']=='explicitly_selected_source_identity'
              and result['binding']['entity_id']==candidate['candidate_id'])
        check('reports_not_backfilled_or_changed',case==before and not result['profile_reports_changed'])
        check('source_permission_not_inferred',result['source_access_registration']['state']=='unregistered'
              and not result['source_access_registration']['absence_is_permission']
              and not result['source_release_changed'])
        check('no_clinical_coverage_or_consumer_promotion',result['personal_output_state']=='held'
              and not result['coverage_verified'] and not result['clinical_equivalence_inferred']
              and result['reported_details_consistency']=='requires_separate_reconciliation')
        fact(case,STRENGTH,'medicine-1')['ref']['report_revision']+=1
        try:service.confirm(owner,case,choice_token=offer['choice_token'],candidate_id=candidate['candidate_id'],confirmed=True)
        except IdentityResolutionError:check('changed_report_invalidates_choice',True)
        else:check('changed_report_invalidates_choice',False)
        service.forget_owner(owner)
        case=before
        try:service.confirm(owner,case,choice_token=offer['choice_token'],candidate_id=candidate['candidate_id'],confirmed=True)
        except IdentityResolutionError:check('forget_removes_visit_receipt',True)
        else:check('forget_removes_visit_receipt',False)
        value={'schema':'actual-source-fictional-choice-audit/1','observed_at':datetime.now(timezone.utc).isoformat(),
            'passed':all(check['passed'] for check in checks),'checks':checks,
            'elapsed_ms':round((time.perf_counter()-started)*1000,3),
            'fixture_kind':'explicitly_fictional_source_mirroring_reports_not_customer_confirmation',
            'source_binding':source['binding'],'source_candidate_id':candidate['candidate_id'],
            'discovery_source_binding':found['binding'],
            'source_raw_sha256':candidate['lineage']['raw_sha256'],
            'source_access_registration':source['source_access_registration'],
            'postgres_writes':0,'actual_guest_store_access':False,'paid_ai_calls':0,
            'http_or_ui_integrated':False,'new_acceptance':False,'consumer_release':False,
            'code_sha256':{str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest()
                for path in [HERE/'identity_resolution.py',HERE/'tests/test_identity_resolution.py',
                    HERE/'tools/check_identity_choice.py',ROOT/'infrastructure/daylight-data/src/daylight_data/serving/identity.py',
                    ROOT/'infrastructure/daylight-data/src/daylight_data/serving/drug_candidates.py']}}
        output.parent.mkdir(parents=True,exist_ok=True)
        output.write_text(json.dumps(value,indent=2)+'\n')
        print(json.dumps({'passed':value['passed'],'checks':len(checks),'elapsed_ms':value['elapsed_ms'],'receipt':str(output)}))
    finally:repository.close();discovery.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    main(parser.parse_args().output.resolve())
