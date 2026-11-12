"""Real profile adapter plus fictional sources; source selection is no coverage."""
import copy
import json
from pathlib import Path
import sys
import unittest

HERE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(HERE))
from comparison_journey import comparison_for_visit
from comparison_profile import build_comparison_profile
from comparison_evidence import canonical_sha256
from identity_journey import IdentityJourney,IdentityPurposeContract,IDENTITY_SCOPE
from natural_state import ensure_state
from test_identity_journey import Discovery,Dictionary,Providers,ProviderDiscovery,ROOT,OWNER


def response():
    template=json.loads((HERE.parent/'chat-first/cms-slice/config/profile/customer-profile.template.json').read_text())
    guide,record=copy.deepcopy(template['guide']),copy.deepcopy(template['readiness'])
    guide['stateVersion']=record['stateVersion']=10
    natural=ensure_state(record)
    values={'RC21':{'choice':'details','items':[{'entity':'doctor-1','practice':'Synthetic office','city':'Synthetic city'}]},
            'RC22':{'choice':'details','items':[{'entity':'medicine-1','name':'Synthetic same name','strength':'5 mg','form':'tablet'}]}}
    for key,value in values.items():
        record['facts'][key]={'value':value,'revision':2,'status':'reported','confirmation':'reported_by_user','source':'user_text'}
        natural['provenance']['readiness.'+key]={'method':'direct_report','status':'user_reported',
            'subject':'beneficiary','scope':'current','revision':2,'supersedesRevision':None}
    return {'guide':guide,'record':record,'assessment':{'nextQuestion':None}}


class ComparisonJourneyTests(unittest.TestCase):
    def setUp(self):
        self.response=response()
        self.profile=build_comparison_profile(self.response['guide'],self.response['record'],requested_scope=IDENTITY_SCOPE)
        self.service=IdentityJourney(Discovery(),Dictionary(),Providers(),provider_discovery=ProviderDiscovery(),
            purpose=IdentityPurposeContract.load(ROOT,internal_research=True))

    def choose(self):
        offer=self.service.drug_search(OWNER,self.profile,item_id='medicine-1')
        return self.service.confirm(OWNER,self.profile,choice_token=offer['choice_token'],
            candidate_id=offer['candidates'][0]['candidate_id'],confirmed=True)

    def test_current_selection_reaches_matching_preparation_without_coverage_or_profile_mutation(self):
        before=copy.deepcopy(self.response);self.choose()
        out=comparison_for_visit(self.service,OWNER,self.response)
        preparation=out['case_preparation']['identity_preparation']
        drug=next(row for row in preparation['assessments'] if row['kind']=='drug_product')
        self.assertEqual(drug['technical_report_association']['identity_state'],'bound')
        self.assertEqual(drug['source_state'],'requires_live_recheck')
        self.assertEqual(drug['coverage_state'],'unresolved')
        self.assertEqual(preparation['coverage_findings'],[])
        self.assertTrue(all(value['state']=='held' for value in out['authority'].values()))
        self.assertEqual(out['decision_record']['case_preparation_sha256'],canonical_sha256(out['case_preparation']))
        self.assertEqual(self.response,before);self.assertFalse(preparation['saved']);self.assertFalse(preparation['ai_context_changed'])

    def test_corrected_report_cannot_reuse_old_source_selection(self):
        self.choose();before=comparison_for_visit(self.service,OWNER,self.response)
        self.response['record']['facts']['RC22']['value']['items'][0]['strength']='10 mg'
        self.response['record']['facts']['RC22']['revision']=3
        self.response['record']['stateVersion']+=1
        self.response['record']['natural']['provenance']['readiness.RC22']['revision']=3
        after=comparison_for_visit(self.service,OWNER,self.response)
        attached=after['case_preparation']['identity_preparation']
        self.assertEqual(attached['preparation']['selected_count'],0)
        self.assertNotEqual(before['comparison_id'],after['comparison_id'])
        self.assertEqual(next(row for row in attached['assessments'] if row['kind']=='drug_product')['technical_report_association']['identity_state'],'unresolved')

    def test_foreign_visit_and_consumer_scope_never_receive_binding_refs(self):
        self.choose()
        other=comparison_for_visit(self.service,'fictional-foreign-visit-0002',self.response)
        self.assertEqual(other['case_preparation']['identity_preparation']['preparation']['bindings'],[])
        held=comparison_for_visit(IdentityJourney(),OWNER,self.response)
        self.assertEqual(held['case_preparation']['identity_preparation']['assessments'],[])
        self.assertEqual(held['case_preparation']['identity_preparation']['preparation']['bindings'],[])

    def test_forgetting_is_reflected_without_a_new_questionnaire(self):
        self.choose();self.service.forget_owner(OWNER)
        out=comparison_for_visit(self.service,OWNER,self.response)
        self.assertEqual(out['case_preparation']['identity_preparation']['preparation']['selected_count'],0)
        self.assertEqual(out['case_preparation']['identity_preparation']['preparation']['coverage_findings'],[])


if __name__=='__main__':unittest.main()
