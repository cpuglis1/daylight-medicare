"""Evaluator mutation tests. Invented trace evidence is NOT an application run."""
import copy
import tempfile
import unittest
from pathlib import Path
import evaluate as ev


class EvaluatorTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.base=Path(self.tmp.name)
        artifact=self.base/'observation.txt';artifact.write_text('INVENTED EVALUATOR TEST EVIDENCE; NOT AN APPLICATION RUN')
        p=ev.profile('BJ01'); self.run_data=ev.template(p,'interrupted')
        self.run_data.update(status='finished',started_at='2026-11-14T10:00:00-05:00',ended_at='2026-11-14T10:10:00-05:00')
        self.run_data['build']={'revision':'fixture','source_hashes':{'app.py':'fixture-hash'},'planner_enabled':True,'runtime_verified':True}
        # Deliberately pretend provenance solely to exercise the validator branches.
        self.run_data['artifacts']={'a':{'path':artifact.name,'sha256':ev.digest(artifact),'origin':'observed_ui'}}
        self.run_data['events']=[{'id':f'e{i}','seq':i,'beat_id':b['id'],'action':b['action'],
            'observation':'Invented observation for evaluator unit test','status':'performed','evidence_ids':['a']}
            for i,b in enumerate(p['beats'],1)]
        self.run_data['assertions']=[{'id':id,'status':'pass','event_ids':['e1'],'evidence_ids':['a'],
            'reviewer':'unit-test-only','reviewer_role':'human_reviewer','reason':'Invented judgment for evaluator branch coverage'}
            for id in ev.required_controls(p)]
        self.run_data['outcome']={'type':'goal_complete','next_action':'Test-only action','blocker':None}

    def grade(self): return ev.grade(self.run_data,self.base)
    def test_suite_valid(self): self.assertEqual(ev.validate(ev.suite()),[])
    def test_evidence_complete_branch_is_not_experience_acceptance(self):
        out=self.grade();self.assertEqual(out['status'],'goal_complete');self.assertFalse(out['experience_accepted']);self.assertEqual(len(out['quality_unreviewed']),5)
    def test_blank_run_is_not_run(self): self.assertEqual(ev.grade(ev.template(ev.profile('BJ01'),'interrupted'),self.base)['status'],'not_run')
    def test_backend_replay_cannot_complete_browser_journey(self):
        self.run_data['mode']='scripted_backend';self.assertEqual(self.grade()['status'],'incomplete_evidence')
    def test_missing_ui_evidence_blocks(self):
        self.run_data['artifacts']['a']['origin']='observed_backend';self.assertEqual(self.grade()['status'],'incomplete_evidence')
    def test_self_test_cannot_claim_journey(self):
        self.run_data['artifacts']['a']['origin']='synthetic_self_test';self.assertFalse(self.grade()['goal_complete'])
    def test_tampered_artifact_invalidates(self):
        (self.base/'observation.txt').write_text('changed');self.assertEqual(self.grade()['status'],'invalid_evidence')
    def test_artifact_cannot_escape_run(self):
        self.run_data['artifacts']['a']['path']='../outside.txt';self.assertEqual(self.grade()['status'],'invalid_evidence')
    def test_missing_beat_cannot_pass(self):
        self.run_data['events'].pop();self.assertFalse(self.grade()['goal_complete'])
    def test_blocked_beat_cannot_pass(self):
        self.run_data['events'][0]['status']='blocked';self.assertFalse(self.grade()['goal_complete'])
    def test_critical_failure_dominates(self):
        self.run_data['critical_findings']=[{'kind':'unintended_decision','event_ids':['e1'],'reason':'Fixture wrongly selects Medigap.'}]
        self.assertEqual(self.grade()['status'],'failed')
    def test_safe_blocked_is_not_goal_complete(self):
        self.run_data['outcome'].update(type='safe_blocked',blocker='Wrong source year');out=self.grade();self.assertEqual(out['status'],'safe_blocked');self.assertFalse(out['goal_complete'])
    def test_model_judgment_is_not_human_review(self):
        self.run_data['assertions'][0]['reviewer_role']='model';self.assertEqual(self.grade()['status'],'incomplete_evidence')
    def test_failed_assertion_dominates(self):
        self.run_data['assertions'][0]['status']='fail';self.assertEqual(self.grade()['status'],'failed')
    def test_suite_drift_rejected(self):
        self.run_data['suite_sha256']='different';self.assertEqual(self.grade()['status'],'invalid_evidence')
    def test_scripted_language_cannot_prove_clarity(self):
        self.run_data['quality']={'clarity':{'score':3,'reason':'Scripted nice prose','reviewer':'test','reviewer_role':'human_reviewer','evidence_ids':['a']}}
        self.assertIn('clarity',self.grade()['quality_unreviewed'])
    def test_planner_off_blocks(self):
        self.run_data['build']['planner_enabled']=False;self.assertFalse(self.grade()['goal_complete'])
    def test_reordered_events_rejected(self):
        self.run_data['events'].reverse();self.assertEqual(self.grade()['status'],'invalid_evidence')


if __name__=='__main__': unittest.main()
