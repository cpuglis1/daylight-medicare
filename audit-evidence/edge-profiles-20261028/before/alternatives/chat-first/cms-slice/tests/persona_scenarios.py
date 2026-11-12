"""Five fictional personas, explicit branch variants, and scripted model outputs.

Only test tooling imports this file. It is never deployed or used by live AI.
"""
import copy
import json
from types import SimpleNamespace


def choice(id, **fields):
    return {'action': {'type': 'choice', 'id': id, 'fields': fields}}


def message(text, *, task='', updates=(), requests=(), mode='report', uncertain=False, correction=False):
    output = {'mode': mode, 'task': task, 'task_quote': text if task else '',
              'requests': [{'id': id, 'quote': text} for id in requests],
              'updates': [{'id': id, 'fields': [{'key': k, 'value': v} for k, v in fields.items()],
                           'entity': entity, 'quote': text, 'scope': scope, 'subject': 'beneficiary',
                           'uncertain': uncertain, 'correction': correction}
                          for id, fields, entity, scope in updates],
              'fact_ids': [], 'reflection': '', 'confirmation': ''}
    return {'action': {'type': 'message', 'message': text}, 'scriptedOutput': output}


def update(id, **fields):
    return (id, fields, 'profile', 'current')


def item(id, entity, **fields):
    return (id, fields, entity, 'current')


def expect(step, id=None, fields=None):
    step['expectedNext'] = id
    if fields is not None: step['expectedFields'] = fields
    return step


SCENARIOS = [
 {'id': 'P1', 'name': 'Current-job transition', 'persona': 1, 'steps': [
    expect(message('Help me prepare my Medicare transition.', task='timing'), 'T04'),
    expect(message('1226'), 'T05'),
    expect(choice('T05', choice='employer'), 'RC09'),
    expect(choice('RC09', choice='spouse_job'), 'RC11', ['jobEnd','coverageEnd']),
    expect(message('The job ends November 2026. I do not know when that insurance ends.', updates=[update('RC11', jobEnd='2026-11', coverageEnd='unknown')]))]},
 {'id': 'P1-payer', 'name': 'Current-job payer-order variant', 'persona': 1, 'steps': [
    expect(message('Help me prepare my Medicare transition and check payer order for my current-job insurance. My job and insurance are ongoing.', task='timing', requests=['payer_order'], updates=[update('RC01',choice='self'), update('T04',choice='already'), update('T05',choice='employer'), update('RC09',choice='my_job'), update('RC11',jobEnd='ongoing',coverageEnd='ongoing')]), 'RC04'),
    expect(choice('RC04', choice='both'), 'RC06'),
    expect(choice('RC06', choice='age65'), 'RC10'),
    expect(choice('RC10', choice='yes')),
    expect(message('Correction: I first qualified through disability before 65.', updates=[update('RC06',choice='disability')], correction=True), 'RC10'),
    expect(choice('RC10', choice='no')),
    expect(message('I also want to check HSA timing; contributions are still being made.', requests=['hsa'], updates=[update('RC14',choice='yes')]))]},
 {'id': 'P2', 'name': 'COBRA transition', 'persona': 2, 'steps': [
    expect(message('Help me prepare my Medicare transition. I have COBRA and want coverage in January 2027.', task='timing', updates=[update('RC01',choice='self'), update('T04',choice='month',month='2027-01'), update('T05',choice='cobra')]), 'RC11', ['coverageEnd']),
    expect(message('December 2026')),
    expect(message('Please check my drug gap and how switching could affect my spouse.', task='timing', requests=['drug_gap','coverage_change']), 'RC12'),
    expect(choice('RC12', choice='yes'), 'RC13'),
    expect(choice('RC13', choice='unknown')),
    expect(message('I am moving in December 2026; that is the event I want checked.', task='timing', requests=['event','residence_change'], updates=[update('RC08',choice='move',eventDate='2026-12')]))]},
 {'id': 'P2-browse', 'name': 'Public browse / all-unknown variant', 'persona': 2, 'steps': [
    expect(message('I only want to browse published plan information.', task='browse'), 'T03'),
    expect(message('34102'), 'RC03'),
    expect(message('2026'))]},
 {'id': 'P3', 'name': 'Advantage member exploring Medigap', 'persona': 3, 'steps': [
    expect(message('I want to explore Medigap after leaving my Advantage plan.', task='medigap', requests=['medigap','leaving_advantage']), 'RC01'),
    expect(choice('RC01', choice='self'), 'T03'),
    expect(message('34102'), 'T04'),
    expect(choice('T04', choice='already'), 'T05'),
    expect(choice('T05', choice='advantage'), 'RC04'),
    expect(choice('RC04', choice='both'), 'RC05', ['month']),
    expect(message('October 2020'), 'RC16', ['start','priorMedigap']),
    expect(message('That Advantage episode began January 2026.', updates=[update('RC16',start='2026-01')]), 'RC16', ['priorMedigap']),
    expect(choice('RC16', priorMedigap='no')),
    expect(message('The plan-ending notice is the Medigap event I want checked.', updates=[update('RC15',event='plan-ending notice')]))]},
 {'id': 'P3-replacement', 'name': 'Current Medigap / ambiguity variant', 'persona': 3, 'steps': [
    expect(message('I want a Medigap review. I have Original Medicare and Medigap, live in 34102, already have Medicare, and Part B began October 2020.', task='medigap', updates=[update('RC01',choice='self'),update('T03',zip='34102'),update('T04',choice='already'),update('T05',choice='original,medigap'),update('RC04',choice='both'),update('RC05',month='2020-10')])) ,
    expect(message('I am keeping my existing Medigap policy while comparing options.', requests=['replacing_medigap'], updates=[update('RC17',choice='keep')])) ,
    expect(message('That current arrangement might be Original Medicare.', updates=[update('RC07',choice='original')], uncertain=True)),
    expect({'action': {'type':'confirm'}}),
    expect(message('Correction: I want more predictable costs, and doctors and total cost matter most.', updates=[update('T09',choice='predictable'),update('T10',choice='doctors,total_cost')], correction=True))]},
 {'id': 'P4', 'name': 'Doctors and several prescriptions', 'persona': 4, 'steps': [
    expect(message('Help me check my doctors.', task='providers'), 'RC01'),
    expect(choice('RC01',choice='self'), 'T06'),
    expect(message('Dr. Rivera at Example Clinic; Dr. Lee at Example Hospital')),
    expect(message('Dr. Rivera is at Example Clinic in Naples, FL; Dr. Lee is at Example Hospital in Tampa, FL.', updates=[item('RC21','doctor-1',practice='Example Clinic',city='Naples, FL'),item('RC21','doctor-2',practice='Example Hospital',city='Tampa, FL')])) ,
    expect(message('Help me check my prescription coverage.', task='drug_coverage'), 'T07'),
    expect(message('Example One 5 mg tablet; Example Two 10 mg capsule.', updates=[update('T07',text='Example One 5 mg tablet; Example Two 10 mg capsule.'),item('RC22','medicine-1',name='Example One',strength='5 mg',form='tablet'),item('RC22','medicine-2',name='Example Two',strength='10 mg',form='capsule')])) ,
    expect(message('Help me prepare my prescription costs, including adjusted costs.', task='drug_pricing', requests=['personal_pricing','adjusted_costs']), 'RC23', ['quantity','daysSupply','pharmacy','channel']),
    expect(message('For Example One: 30 tablets, 30 days, Example Pharmacy in Naples, retail.', updates=[item('RC23','medicine-1',quantity='30 tablets',daysSupply='30',pharmacy='Example Pharmacy in Naples',channel='retail')]), 'RC23'),
    expect(message('For Example Two: 60, 30 days, Example Pharmacy in Naples, retail.', updates=[item('RC23','medicine-2',quantity='60',daysSupply='30',pharmacy='Example Pharmacy in Naples',channel='retail')]), 'RC23', ['quantity']),
    expect(message('capsules', updates=[item('RC23','medicine-2',quantity='capsules')]), 'RC18'),
    expect(choice('RC18',choice='medicaid,extra_help')),
    expect(message('Correction: Example One is a 10 mg tablet.', updates=[item('RC22','medicine-1',name='Example One',strength='10 mg',form='tablet')], correction=True), 'RC23'),
    expect({'action': {'type':'defer','id':'RC23'}}),
    expect(message('Example Two is filled at a pharmacy, not a clinic.', updates=[update('RC24',choice='pharmacy')]))]},
 {'id': 'P4-unknown', 'name': 'Partial medicine identity / no price intake variant', 'persona': 4, 'steps': [
    expect(message('Help me prepare my prescription cost. Example Three is a tablet but I do not know the strength.', task='drug_pricing', updates=[update('RC01',choice='self'),item('RC22','medicine-1',name='Example Three',form='tablet',strength='unknown')]))]},
 {'id': 'P5', 'name': 'Caregiver, military coverage, travel and budget', 'persona': 5, 'steps': [
    expect(choice('T01',choice='compare'), 'RC01'),
    expect(choice('RC01',choice='someone'), 'T04'),
    expect(choice('T04',choice='already'), 'T05'),
    expect(choice('T05',choice='military'), 'T03'),
    # Filled at runtime from the held ZIP reference: a real multiple-county ZIP.
    {'ambiguousCounty': True},
    expect(choice('T06',choice='none'), 'T07'),
    expect(choice('T07',choice='no'), 'T08'),
    expect(choice('T08',choice='elsewhere_us'), 'RC20'),
    expect(message('Routine care is needed in Tampa, Florida.', updates=[update('RC20',location='Tampa, Florida')])) ,
    expect(message('We want to organize payer-order questions for that military coverage.', task='timing', requests=['payer_order']), 'RC04'),
    expect(choice('RC04',choice='both'), 'RC06'),
    expect(choice('RC06',choice='age65'), 'RC26'),
    expect(choice('RC26',choice='tfl')),
    expect(message('We want to explore a monthly budget of $200.', task='costs', updates=[update('RC25',amount='$200')]), 'RC25', ['includes']),
    expect(choice('RC25',includes='premiums_and_care')),
    expect(message('The person receives Medicaid and Extra Help benefits.', updates=[update('RC18',choice='medicaid'),update('RC18',choice='extra_help')])) ,
    expect(message('We want to understand Special Needs Plans. A plan letter says program confirmation is pending.', task='snp', requests=['snp'], updates=[update('RC19',choice='details',qualification='program confirmation is pending')])) ,
    expect(message('The person has a refill interruption and wants human help.', requests=['continuity'], updates=[update('RC27',choice='human')])) ,
    expect(message('I am new to Medicare and want more explanation.', updates=[update('T02',choice='new')]))]}
]


def install_scripted_transport(server, virtual_pacing=False):
    if virtual_pacing:
        # Private fixture clock only: replay one message per ten virtual seconds.
        # Production rate policy is unchanged and covered by its existing suite.
        import itertools
        import guide_server
        ticks=itertools.count(0,10)
        guide_server.time=SimpleNamespace(monotonic=lambda:next(ticks))
    outputs = {step['action']['message']: step.get('scriptedOutput') for case in SCENARIOS for step in case['steps']
               if step.get('action',{}).get('type') == 'message' and step.get('scriptedOutput')}
    def transport(payload):
        message = json.loads(payload['input'][0]['content'])['submitted_text']
        if message not in outputs: raise AssertionError('Unscripted synthetic message: ' + message)
        return {'output':[{'content':[{'type':'output_text','text':json.dumps(copy.deepcopy(outputs[message]))}]}],
                'usage':{'input_tokens':10,'output_tokens':10}}
    flow = server.adaptive
    flow.fixture = False
    flow.agent.enabled = True
    flow.agent.client = SimpleNamespace(available=True,model='synthetic',transport=transport)
    return flow
