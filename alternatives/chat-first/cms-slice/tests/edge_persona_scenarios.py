"""Additional fictional edge profiles P6–P10. Test data, never deployed."""
import copy
import json
from types import SimpleNamespace
from persona_scenarios import message, update, item


def tagged(text, **kwargs):
    return message(text, **kwargs)


P6_START=tagged('Help me prepare my Medicare transition. I have COBRA, want coverage in January 2027, and that insurance ends December 2026.',task='timing',updates=[update('RC01',choice='self'),update('T04',choice='month',month='2027-01'),update('T05',choice='cobra'),update('RC11',coverageEnd='2026-12')])
P6_AMBIGUOUS=tagged('I think that insurance ends January 2027, but I am not certain.',updates=[update('RC11',coverageEnd='2027-01')],uncertain=True)
P6_CORRECT=tagged('Correction: that insurance ends February 2027.',updates=[update('RC11',coverageEnd='2027-02')],correction=True)
P8_SIDE=tagged('What is Medicare Advantage?',task='learn',mode='answer')
P8_SIDE['scriptedOutput']['fact_ids']=['advantage']
P8_LEARN=tagged('I want to just learn for now.',task='learn')
P8_DRUG=tagged('Help me prepare my prescription cost.',task='drug_pricing')
P8_RETURN=tagged('Help me compare my coverage.',task='compare')
P9_START=tagged('I am helping my mother prepare a Medicare transition. She has COBRA, wants coverage in January 2027, and her insurance ends December 2026.',task='timing',updates=[update('RC01',choice='someone'),update('T04',choice='month',month='2027-01'),update('T05',choice='cobra'),update('RC11',coverageEnd='2026-12')])
P9_HELPER=tagged('I have current-job insurance, but that is my coverage; my mother still has COBRA.',updates=[update('T05',choice='employer')])
P9_HELPER['scriptedOutput']['updates'][0]['subject']='learner'
P9_SWITCH=tagged('Switch to my coverage instead of my mother; I have current-job insurance.',task='compare',updates=[update('RC01',choice='self'),update('T05',choice='employer')])
P10_SAME=tagged('Help me prepare my prescription cost. I take Example Med 5 mg tablets and Example Med 10 mg tablets.',task='drug_pricing',updates=[update('RC01',choice='self'),item('RC22','new',name='Example Med',strength='5 mg',form='tablets'),item('RC22','new',name='Example Med',strength='10 mg',form='tablets')])
P10_DISTINCT=tagged('Help me prepare my prescription cost. I take Example Alpha 5 mg tablets and Example Beta 10 mg tablets.',task='drug_pricing',updates=[update('RC01',choice='self'),item('RC22','new',name='Example Alpha',strength='5 mg',form='tablets'),item('RC22','new',name='Example Beta',strength='10 mg',form='tablets')])
P10_FILL1=tagged('For Example Alpha: 30 tablets, 30 days, Example Pharmacy in Naples, retail.',updates=[item('RC23','medicine-1',quantity='30 tablets',daysSupply='30',pharmacy='Example Pharmacy in Naples',channel='retail')])
P10_FILL2=tagged('For Example Beta: 60 tablets, 30 days, Example Pharmacy in Naples, retail.',updates=[item('RC23','medicine-2',quantity='60 tablets',daysSupply='30',pharmacy='Example Pharmacy in Naples',channel='retail')])
P10_AMBIGUOUS=tagged('Change it to 90 days.',updates=[update('RC23',daysSupply='90')])

MESSAGES=[P6_START,P6_AMBIGUOUS,P6_CORRECT,P8_SIDE,P8_LEARN,P8_DRUG,P8_RETURN,P9_START,P9_HELPER,P9_SWITCH,P10_SAME,P10_DISTINCT,P10_FILL1,P10_FILL2,P10_AMBIGUOUS]
PROFILES=[
 {'id':'P6','name':'Conflicting dates and explicit correction','goal':'Keep an uncertain replacement pending, preserve the old date on reject, update only the target on correction.'},
 {'id':'P7','name':'Mostly unknown answers','goal':'Stop repeated intake, retain unknowns as missing, and permit explicit samples without claiming readiness.'},
 {'id':'P8','name':'Side question and changing goals','goal':'Preserve the active task for education; switch only on an explicit goal change and reuse the original coverage/date facts on return.'},
 {'id':'P9','name':'Mother and helper have different coverage','goal':'Keep the mother’s records separate and reject helper/recipient changes that would merge two people.'},
 {'id':'P10','name':'Same medicine name, different strengths','goal':'Keep both medicines distinct and require an actual item binding for an ambiguous fill change.'}
]


def install(server):
    # A scripted transport exercises the real adapter and controller without a key.
    outputs={s['action']['message']:s['scriptedOutput']for s in MESSAGES}
    def transport(payload):
        text=json.loads(payload['input'][0]['content'])['submitted_text']
        if text not in outputs:raise AssertionError('Unscripted edge message: '+text)
        return {'output':[{'content':[{'type':'output_text','text':json.dumps(copy.deepcopy(outputs[text]))}]}],'usage':{'input_tokens':10,'output_tokens':10}}
    server.adaptive.fixture=False;server.adaptive.agent.enabled=True
    server.adaptive.agent.client=SimpleNamespace(available=True,model='synthetic',transport=transport)
