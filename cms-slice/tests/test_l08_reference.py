"""Safety contracts for published provider-reference collection and identity."""
import json
import sys
from pathlib import Path
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import l08_build as build
import l08_collect as collect


class L08ReferenceTests(unittest.TestCase):
    def test_actual_year_and_segment_control_plan_join(self):
        plan={'identifier':[{'value':'H1045028000'}],'period':{'start':'2026-01-01'}}
        self.assertEqual(build.exact_offering_ids(plan),{'2026:H1045:028:000'})
        plan['period']['start']='2027-01-01'
        self.assertEqual(build.exact_offering_ids(plan),set())
        plan={'identifier':[{'value':'H1036-217-000-2026'}],'period':{'start':'2027-01-01'}}
        self.assertEqual(build.exact_offering_ids(plan),set())

    def test_product_names_do_not_invent_cms_ids(self):
        self.assertEqual(build.exact_offering_ids({'name':'BlueMedicare Select (PPO)',
            'period':{'start':'2026-01-01'},'identifier':[{'value':'BMPPO-2026'}]}),set())

    def test_reference_namespace_and_locations_stay_distinct(self):
        self.assertNotEqual(build.refkey('a.example','Practitioner/123'),build.refkey('b.example','Practitioner/123'))
        self.assertEqual(build.refkey('a.example','https://b.example/fhir/Location/456'),'b.example/Location/456')
        self.assertNotEqual(build.refkey('a.example','Location/one'),build.refkey('a.example','Location/two'))

    def test_http200_operation_outcome_is_not_empty_directory(self):
        job={'id':'test','url':'https://public.example/PractitionerRole','type':'PractitionerRole'}
        with patch.object(collect,'acquire',return_value={'id':'test','sha256':'x'}),patch.object(collect,'body',return_value=json.dumps({
                'resourceType':'OperationOutcome','issue':[{'severity':'error','diagnostics':'Unsupported filter'}]}).encode()),patch.object(collect,'write'):
            result=collect.crawl(job)
        self.assertFalse(result['complete'])
        self.assertIn('OperationOutcome',result['error'])

    def test_included_resource_limit_is_not_complete_roster(self):
        job={'id':'test','url':'https://public.example/PractitionerRole','type':'PractitionerRole'}
        result={'resourceType':'Bundle','entry':[{'resource':{'resourceType':'OperationOutcome','issue':[
            {'severity':'error','code':'too-costly','details':{'text':'include limit reached'}}]}}]}
        with patch.object(collect,'acquire',return_value={'id':'test','sha256':'x'}),patch.object(collect,'body',return_value=json.dumps(result).encode()),patch.object(collect,'write'):
            observed=collect.crawl(job)
        self.assertFalse(observed['complete'])
        self.assertIn('include limit',observed['error'])


if __name__=='__main__':unittest.main()
