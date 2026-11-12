"""Meaningful population, ambiguity, date, source-scope and tampering checks."""
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'cms-slice/scripts'))
from l05_close_aliases import alias_key
from l05_close_reference import lookup,verify
from l05_close_validate import validate

CLOSE=ROOT/'docs/data/l05-drug-coverage-2026-10-25/closeout-r1'
PACKAGE=CLOSE/'build-r5'
def read(p):return json.loads(p.read_text())
def rows(p):
    with gzip.open(p,'rt') as f:return [json.loads(l) for l in f]


class L05ConditionCloseout(unittest.TestCase):
    def test_full_population_audit_and_base_preservation(self):
        r=read(CLOSE/'build-r5-validation.json')
        self.assertTrue(r['passed']);self.assertEqual(r['failed'],0)
        self.assertEqual((r['plans_checked'],r['documents_checked'],r['criterion_sections_checked']),(71,138,4864))
        self.assertEqual(r['PA_ST_source_contexts_checked'],24518)
        self.assertEqual(r['quantity_contexts_checked'],37675)
        self.assertEqual(r['carrier_unit_rows'],3211)
        self.assertEqual(r['preservation_mismatches'],[])
        verify(PACKAGE)

    def test_complete_rules_and_questionnaires_have_different_states(self):
        plans=read(PACKAGE/'plans.json');c=Counter(p['condition_source_state'] for p in plans)
        self.assertEqual(c,{'full_dated_documents_available':33,'source_access_STOP':25,'applicable_complete_criteria_not_located':7,'questionnaires_available_complete_approval_rules_not_established':6})
        docs=read(PACKAGE/'documents.json');self.assertEqual(sum(d['kind']=='PA_questionnaire' for d in docs),104)
        for d in docs:
            if d['kind']=='PA_questionnaire':self.assertFalse(d['full_criteria'])
            if d['kind']=='out_of_scope_Illinois_FIDE_candidate':self.assertFalse(d['scope_offering_ids'])
        self.assertFalse(read(PACKAGE/'coverage.json')['full_L05_condition_reference_complete'])

    def test_aetna_explicit_mL_is_supported_and_blue_pens_are_not_renamed(self):
        data=rows(PACKAGE/'quantity-units.jsonl.gz')
        aetna=next(r for r in data if r['rxcui']=='1551300' and r['formulary_id']=='00026010')
        self.assertEqual(aetna['unit'],'mL');self.assertEqual(aetna['quantity_amount_raw'],'2')
        blue=next(r for r in data if r['rxcui']=='1551300' and r['formulary_id']=='00026252')
        self.assertIsNone(blue['unit']);self.assertEqual(blue['quantity_amount_raw'],'2')
        self.assertTrue(any(r['amount']=='4' and r['unit']=='pens' and r['days']==28 for r in blue['other_dated_carrier_limits']))

    def test_alias_rules_preserve_strength_route_and_device_ambiguity(self):
        self.assertEqual(alias_key('aripiprazole solution 1mg/ml'),alias_key('aripiprazole 1 MG/ML Oral Solution'))
        self.assertNotEqual(alias_key('drugA 1mg/ml'),alias_key('drugA 1mg/0.5ml'))
        self.assertNotEqual(alias_key('drugA 10mg drugB 20mg'),alias_key('drugA 20mg drugB 10mg'))
        self.assertNotEqual(alias_key('drugA 1mg topical solution'),alias_key('drugA 1mg oral solution'))
        self.assertNotEqual(alias_key('drugA 1mg capsule'),alias_key('drugA 1mg delayed release capsule'))
        self.assertNotEqual(alias_key('drugA 1mg auto-injector'),alias_key('drugA 1mg prefilled syringe'))
        aliases=read(CLOSE/'quantity-alias-matches.json')
        self.assertEqual(aliases['query_states']['ambiguous'],26)

    def test_archived_and_current_text_are_never_silently_backdated(self):
        comparisons=rows(PACKAGE/'criteria-comparisons.jsonl.gz')
        self.assertEqual(len(comparisons),1665)
        self.assertTrue(all(r['September_continuity_inferred'] is False for r in comparisons))
        self.assertEqual(sum(r['comparison_state']=='same_published_text_at_both_observations' for r in comparisons),1331)
        self.assertTrue(any(r['comparison_state']=='published_text_changed' for r in comparisons))
        for d in read(PACKAGE/'documents.json'):self.assertFalse(d['historical_snapshot_asserted'])

    def test_runtime_preserves_exact_drug_and_shows_the_appropriate_sources(self):
        a=lookup(PACKAGE,{'year':2026,'offering_id':'2026:H5521:033:000','rxcui':'1551300'})
        self.assertEqual(a['matches'][0]['quantity_unit_evidence']['unit'],'mL')
        b=lookup(PACKAGE,{'year':2026,'offering_id':'2026:S5904:002:000','rxcui':'1551300'})
        self.assertEqual(b['condition_source_state'],'questionnaires_available_complete_approval_rules_not_established')
        self.assertTrue(any(d['kind']=='PA_questionnaire' for d in b['dated_condition_documents']))
        self.assertFalse(any(d['full_criteria'] for d in b['dated_condition_documents']))
        self.assertFalse(b['personal_price_available']);self.assertFalse(b['recommendations_available'])
        self.assertTrue(all(link['offering_id']=='2026:S5904:002:000' for r in b['drug_condition_references'] for link in r['plan_links']))

    def test_personal_commercial_wrong_year_and_unknown_segment_fail(self):
        good={'year':2026,'offering_id':'2026:H5521:033:000','rxcui':'1551300'}
        for bad in [{**good,'diagnosis':'test'},{**good,'commission':10},{**good,'year':2027},{**good,'offering_id':'2026:H5521:033:999'}]:
            with self.subTest(request=bad),self.assertRaises(ValueError):lookup(PACKAGE,bad)

    def test_rehashed_wrong_units_lost_rule_text_wrong_dates_and_scope_fail(self):
        with tempfile.TemporaryDirectory() as name:
            clone=Path(name)/'faults';shutil.copytree(PACKAGE,clone)
            unit_rows=rows(clone/'quantity-units.jsonl.gz');next(r for r in unit_rows if r['state']=='explicit_carrier_unit_matched')['unit']='invented pens'
            section_rows=rows(clone/'criteria-sections.jsonl.gz');section_rows[0]['full_text']=section_rows[0]['full_text'][:-12];section_rows[0]['text_sha256']=hashlib.sha256(section_rows[0]['full_text'].encode()).hexdigest()
            compare_rows=rows(clone/'criteria-comparisons.jsonl.gz');compare_rows[0]['September_continuity_inferred']=True
            for file,data in [('quantity-units.jsonl.gz',unit_rows),('criteria-sections.jsonl.gz',section_rows),('criteria-comparisons.jsonl.gz',compare_rows)]:
                with gzip.open(clone/file,'wt') as f:
                    for r in data:f.write(json.dumps(r)+'\n')
            docs=read(clone/'documents.json');docs[0]['declared_date']='1900-01-01';next(d for d in docs if d['kind']=='out_of_scope_Illinois_FIDE_candidate')['scope_offering_ids']=['2026:H5521:033:000'];(clone/'documents.json').write_text(json.dumps(docs))
            m=read(clone/'manifest.json');m['files']={n:hashlib.sha256((clone/n).read_bytes()).hexdigest() for n in m['files']};(clone/'manifest.json').write_text(json.dumps(m))
            result=validate(clone);self.assertFalse(result['passed'])
            self.assertTrue({'every_quantity_unit_state_and_no_guessing','every_full_criterion_source_range','every_declared_date_against_full_source_header','out_of_scope_Aetna_candidate_rejected','all_before_after_states_no_backdating'}<=set(result['failure_examples']),result['failure_examples'])


if __name__=='__main__':unittest.main()
