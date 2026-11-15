"""Six fictional replays through D166. Scripted language, network forbidden.

Original profile text is sent in script order (not a simulation of a person
answering every question). Extra continuations are separately labelled. The
artifact reports unfinished research rather than manufacturing a plan choice.
"""
import json
import os
from pathlib import Path
import re
import unittest
from unittest.mock import patch

from test_conversation_planner import ConversationPlannerTests as Harness
import conversation_planner as planner
import enrollment_flow
from conversation_checks import ConversationChecks

ROOT = Path(__file__).resolve().parents[3]
PROFILES = json.loads((ROOT/'docs/evaluations/plan-paths-2026-11-12/profiles.json').read_text())


class Replays(unittest.TestCase):
    for name in ('payload', 'take', 'turn', 'message', 'choice', 'task', 'stage_payloads',
                 'extracted_context', 'composed_context'):
        locals()[name] = getattr(Harness, name)
    update = staticmethod(Harness.update)
    extraction = staticmethod(Harness.extraction)
    proposal = staticmethod(Harness.proposal)
    setUp = Harness.setUp

    def interpreted(self, text, pid):
        updates = []
        def add(identifier, **fields):
            updates.append(self.update(identifier, fields, text))
        if re.search(r"\b(?:I'm|I’m|I am|my|I |for me|COBRA)\b", text, re.I) and not self.flow.value(self.g, 'subject.role'):
            add('RC01', choice='someone_else' if pid == 'PP15' else 'self')
        zip_code = re.search(r'\b3410[1-8]\b', text)
        if zip_code: add('T03', zip=zip_code.group())
        if pid == 'PP07' and 'Original Medicare since July' in text or pid == 'PP15' and 'Original Medicare since 2020' in text:
            add('T05', choice='original,medigap,drug')
        if pid == 'PP12' and ('Humana HMO' in text or 'Humana Gold Plus HMO' in text): add('T05', choice='advantage')
        if 'regular employee insurance' in text: add('T05', choice='employer')
        if text == 'COBRA': add('T05', choice='cobra')
        if 'No A, no B' in text or text == 'Neither': add('RC04', choice='neither')
        if text in ('More predictable costs', 'Total cost · Predictable costs') or 'Then predictable bills.' in text:
            add('T09', choice='predictable')
            add('T10', choice='doctors,bills' if pid == 'PP13' else 'total_cost,bills')
        if text == 'Local only': add('T08', choice='local')
        # Exact, declared fixture interpretations, not hidden truth seeded into state.
        medicines = {
            'PP07': ('Metformin ER 500, two a day.', 'Metformin ER 500; Atorvastatin 40; Breyna inhaler'),
            'PP12': ('Lantus SoloStar, 20 units', 'Lantus SoloStar; Eliquis 5; Metformin 500; Atorvastatin 40'),
            'PP13': ('Eliquis 5 twice a day', 'Eliquis 5; losartan 50'),
            'PP15': ("takes five things:", 'Synthroid 50; Eliquis 5; furosemide 20; Ozempic 1 mg; vitamin D'),
            'PP09': ('Lisinopril, 10 milligrams', 'Lisinopril 10 milligrams'),
            'PP16': ('I take ozempic', 'ozempic; generic blood pressure medication')}
        needle, names = medicines[pid]
        if needle in text:
            # Keep a literal source span: normalized punctuation is not a quote.
            span = text[text.index(needle):]
            if pid == 'PP15': span = span.split('takes five things:',1)[1].split(' Which plan',1)[0].strip()
            if pid == 'PP09': span = span.split('. Dr.',1)[0]
            add('T07', text=span)
        if text == 'Metoprolol !': add('T07', text='Metoprolol')
        if 'Dr. Mark Speake is' in text: add('T06', text=text)
        if text == 'Ashley Tunkle in Naples' or text == 'Dr. Henry Biggs is my orthopedist': add('T06', text=text)
        p = planner.conservative_request(text)
        if p['purpose'] == 'none':
            p.update(purpose='review', quote=text, focus='medicines' if pid in ('PP07','PP12','PP15') else 'coverage_paths')
        # Script the semantic interpreter separately; no fact/decision is
        # asserted merely because the profile's desired outcome mentions it.
        if text in ("I'll keep my current coverage.", "I'll wait."):
            p.update(purpose='review', decision={'stance':'chosen', 'path':'wait' if 'wait' in text else 'keep_current', 'quote':text})
        return self.extraction(updates, discussion=p)

    def replay(self, pid):
        profile = next(p for p in PROFILES if p['id'] == pid)
        texts = (profile['reproduction']['inputs'] if pid == 'PP16' else
                 [profile['opening_message']] + [row['reply'] for row in profile['response_script']])
        rows = []
        for text in texts:
            out = self.message(text, extraction=self.interpreted(text, pid))
            self.assertTrue(out.get('reply'), (pid, text))
            self.assertEqual(out['conversationPlanner']['version'], planner.VERSION)
            self.assertNotEqual(out['coveragePath']['state'], 'chosen', (pid, text))
            self.assertFalse(out.get('whatsLeft'))
            row = {'input': text, 'reply': out['reply'], 'question': out['assessment'].get('nextQuestion'),
                   'planner': out['conversationPlanner'], 'cards': out.get('cards', []),
                   'enrollment': out.get('enrollment'), 'generated': out.get('generated', {}).get('status')}
            rows.append(row)
        if pid != 'PP16':
            self.assertTrue(self.flow.value(self.g, 'needs.medications'), pid)
        if pid == 'PP07':
            self.assertEqual(out['enrollment']['record']['components']['medigap'], 'keep_existing')
            self.assertEqual(out['enrollment']['record']['components']['part_d'], 'unknown')
        if pid in ('PP07','PP12','PP15'):
            self.assertIn('active', out['enrollment']['line']['status'])
        if pid == 'PP16':
            self.assertEqual(out['coveragePath']['state'], 'undecided')
            self.assertEqual(out['conversationPlanner']['plans_view'], 'paths')
            self.assertFalse(any(r['question'] and r['question']['id'] in ('MG_SEX','MG_TOBACCO') for r in rows))
        if pid == 'PP09':
            final = self.message("I'll keep my current coverage.", extraction=self.interpreted("I'll keep my current coverage.", pid))
            self.assertEqual(final['enrollment']['record']['finish'], 'keep_current')
            rows.append({'added_continuation': "I'll keep my current coverage.", 'enrollment': final['enrollment']})
        target = os.environ.get('PROFILE_REPLAY_OUTPUT')
        if target:
            Path(target).mkdir(parents=True, exist_ok=True)
            (Path(target)/(pid+'.json')).write_text(json.dumps({'profile':pid, 'scripted_language':True,
                'real_source_checks':False, 'original_inputs':len(texts), 'turns':rows}, indent=2)+'\n')

    def test_PP07(self): self.replay('PP07')
    def test_PP09(self): self.replay('PP09')
    def test_PP12(self): self.replay('PP12')
    def test_PP13(self): self.replay('PP13')
    def test_PP15(self): self.replay('PP15')
    def test_PP16(self): self.replay('PP16')

    def test_component_decisions_and_corrections(self):
        self.choice('RC01', choice='self')
        self.message("I'm keeping the Plan G.")
        self.assertEqual(enrollment_flow.journey(self.flow, self.g, self.r)['components']['medigap'], 'keep_existing')
        self.message("I'll decide on the drug plan later.")
        self.assertEqual(enrollment_flow.journey(self.flow, self.g, self.r)['components']['part_d'], 'decide_later')
        for text in ("I have a drug plan.", "If I keep Plan G, what happens?", "My friend says I'm keeping Plan G.",
                     "Should I keep Plan G?", "I want to understand Medigap."):
            self.assertEqual(planner.explicit_components(text), {})

    def test_requested_cost_review_routes_to_existing_coverage(self):
        self.choice('RC01', choice='self')
        self.choice('T03', zip='34104')
        self.choice('T05', choice='advantage')
        out = self.message('Can you put the plans in order by what my four medicines would cost?')
        self.assertEqual(out['conversationPlanner']['plans_view'], 'advantage')
        self.assertEqual(out['coveragePath']['state'], 'undecided')


if __name__ == '__main__': unittest.main()
