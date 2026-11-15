"""D170 isolated real-app browser binding. No provider or database network.

Only fictional reports received in the submitted text are interpreted. Local
language is declared, generic and deliberately not a conversation-quality test.
The ordinary controller, evidence adapters, HTTP handlers and UI run unchanged.
"""
import copy
import hashlib
import json
import re
import socket
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path[:0] = [str(HERE.parent), str(ROOT / 'infrastructure/daylight-data/src')]
from server import build
from chat import ResponsesClient, ModelUnavailable
from demo_http import install
from catalog_research import CatalogResearch, CRITICAL_BENEFITS_PATH
from comparison_research import RESEARCH_SCOPE
import enrollment_flow
import conversation_planner as planner
from legacy_discussion_fixture import scripted_proposal
from conversation_checks import ConversationChecks
from situation import observations
from test_medigap_pilot import FictionalRepository as GapRepository
from test_part_d_pilot import FictionalRepository as DrugRepository
from test_drug_comparison_20261114 import FictionalDrugService

MANIFEST = {'id': 'behavioral-fictional-v5', 'year': 2026, 'language': 'local-scripted-v5',
    'positive_doctors': ['Nera Vale', 'Tomas Reed'], 'negative_doctor': 'Absent Example',
    'pharmacies': ['Harbor Pharmacy, 1 Test Lane', 'Grove Pharmacy, 2 Test Lane'],
    'medicines': ['metformin 500 mg tablet', 'levothyroxine 50 mcg tablet'],
    'unknown_product': 'insulin glargine pen',
    'sources': 'synthetic doctor, pharmacy, formulary, drug-cost and Medigap/PDP rows; retained published MA display catalog; no consumer authority',
    'outbound': 'socket.connect, connect_ex, create_connection, DNS and subprocess.Popen (including provider curl) denied',
    'stores': 'fresh temporary SQLite; no saved profile or owner visit access',
    'rate_clock': 'HTTP rate clock accelerated 100x for fictional replay only; visit TTL unchanged'}


def denied(*args, **kwargs):
    raise AssertionError('D170: outbound network forbidden')


def update(identifier, fields, quote, **extra):
    return {**dict(id=identifier, entity='profile', fields=[dict(key=k, value=v) for k, v in fields.items()],
                quote=quote, scope='current', subject='beneficiary', uncertain=False, correction=False), **extra}


def interpret(text, context):
    reports = {p['id']: p.get('value') for p in context.get('reports', [])}
    role = reports.get('guide.subject.role')
    updates = []
    def add(identifier, **fields):
        updates.append(update(identifier, fields, text, correction=bool(re.search(r'(?i)\b(?:actually|not |correct|instead|checked|more.*than)\b', text))))
    helper_detour = role == 'someone' and re.search(r'\b(?:I am 43|I’m 43|I live in Virginia)\b', text)
    if not role:
        if re.search(r'(?i)\b(?:mother|mom)\b', text): add('RC01', choice='someone')
        elif re.search(r"(?i)\b(?:I|my|me)\b", text): add('RC01', choice='self')
    if not helper_detour:
        z = re.search(r'\b3410[1-8]\b', text)
        if z: add('T03', zip=z.group())
        y = re.search(r'(?i)(?:for|compare.*for) (2027)\b', text)
        if y: add('RC03', year=y.group(1))
        coverage = []
        if re.search(r'(?i)\b(?:have|has) original medicare', text): coverage.append('original')
        if re.search(r'(?i)\b(?:have|has|keeping|keep) (?:my |a )?plan g\b|\b(?:my|mom has.*) plan g\b', text): coverage.append('medigap')
        if re.search(r'(?i)\b(?:have|has|separate|standalone) (?:a )?drug plan\b', text): coverage.append('drug')
        if re.search(r'(?i)\b(?:my (?:advantage|hmo)|it is a medicare advantage|have a medicare advantage)', text): coverage.append('advantage')
        if re.search(r'(?i)\b(?:this is|have|on) cobra\b', text): coverage.append('cobra')
        if re.search(r'(?i)\bcurrent employer.*(?:group|insurance)', text): coverage.append('employer')
        if coverage: add('T05', choice=','.join(coverage))
        if re.search(r'(?i)\b(?:have|has) (?:parts )?a and b\b|\bboth a and b have been active', text): add('RC04', choice='both')
        age = re.search(r'(?i)\b(?:am|is|she is) (6[4-9]|7[0-4])\b', text)
        if age: add('MG_AGE', choice=age.group(1))
        if re.search(r'(?i)\bmale\b', text): add('MG_SEX', choice='Male')
        if re.search(r'(?i)\bfemale\b', text): add('MG_SEX', choice='Female')
        if re.search(r'(?i)\b(?:do not|don.t|never) (?:use|used) tobacco', text): add('MG_TOBACCO', choice='Non-Tobacco')
        if re.search(r'(?i)\b(?:keeping .*doctor|both doctors|doctors.*more than price)', text): add('T10', choice='doctors')
        if re.search(r'(?i)\blowest total cost\b', text): add('T10', choice='total_cost')
        if re.search(r'(?i)\bI (?:want|prefer) (?:low monthly|the lowest premium)\b', text): add('T09', choice='lower_monthly')
        if re.search(r'(?i)\bflexibility matters more\b', text) and (
                reports.get('guide.needs.travel') or any(p.get('id') == 'guide.needs.travel'
                    and p.get('status') == 'reported' for p in context.get('known', []))):
            add('T10', choice='travel')
        if 'four months' in text: add('T08', choice='elsewhere_us')
        names = re.findall(r'Dr\. (?:Nera Vale|Tomas Reed|Absent Example)(?: at [^.;?]+)?', text)
        if names: add('T06', text='; '.join(names))
        if '10 Test Lane' in text and not names and 'Tomas' in text:
            updates.append(update('RC21', {'city':'10 Test Lane in Naples'}, text, entity='doctor-2', correction=True))
        meds = [m for m in ('metformin', 'levothyroxine', 'insulin glargine', 'apixaban') if re.search(r'(?i)\b' + m + r'\b', text)]
        if meds and re.search(r'(?i)\b(?:take|takes|medicine|metformin is)\b', text):
            # Preserve the supplied list wording; joining names with invented
            # punctuation is not an exact supported quote for a multi-item list.
            named = re.search(r'(?i)\btakes?\s+([^.,]+)', text)
            add('T07', text=named.group(1) if named and len(meds)>1 else meds[0])
        for index, med in enumerate(meds, 1):
            strength = '500 mg' if med == 'metformin' else '50 mcg' if med == 'levothyroxine' else '5 mg' if med == 'apixaban' else None
            if strength and strength in text:
                entity = 'medicine-'+str(index) if reports.get('guide.needs.medications') else 'new'
                updates.append(update('RC22', {'name':med, 'strength':strength, 'form':'tablet'}, text, entity=entity))
        pharmacy = re.search(r'(Harbor|Grove) Pharmacy(?: at)?(?:,)? (\d+ Test Lane)', text)
        if pharmacy and ('30' in text or 'Actually' in text):
            fields = {'pharmacy':pharmacy.group(0)}
            if re.search(r'(?i)\bretail\b', text): fields['channel']='retail'
            if '30' in text: fields.update(quantity='30 tablets', daysSupply='30')
            updates.append(update('RC23', fields, text, entity='medicine-1' if reports.get('guide.needs.medications') else 'new', correction='Actually' in text))
        if re.search(r'(?i)\bno (?:help|assistance) with drug costs', text): add('RC18', choice='none')
        if re.search(r'(?i)\bno medicines\b', text): add('T07', choice='no')
        if '240 employees' in text: add('RC10', choice='yes')
        if 'no HSA' in text: add('RC14', choice='no')
    situations = [dict(kind=k, subject='beneficiary', scope='current', quote=text, uncertain=False,
                      correction='not November' in text, month=v.get('month'), year=v.get('year'),
                      status=v.get('status',''), when=v.get('when',''))
                  for k, v in observations(text, role).items()] if not helper_detour else []
    return dict(updates=updates, requests=[], fact_ids=[], situation_proposals=situations, goal_quote='',
                agenda={'concerns':[], 'priorityReason':{}},
                education_request={'kind':'none','concept_ids':[],'quote':''}, discussion=scripted_proposal(text))


def transport(payload):
    sent = json.loads(payload['input'][0]['content'])
    if payload['text']['format']['name'] == 'daylight_guide_commands':
        value = interpret(sent['submitted_text'], sent['confirmed_context'])
    else:
        ctx = sent['resolved_context']
        if 'force a local failure' in json.dumps(sent).lower():
            raise ModelUnavailable('Declared offline generation failure')
        move = next(iter(sent['question_candidates']), {})
        evidence = next((e for e in ctx.get('evidence', []) if e.get('id') in ('original','costs','medigap','routesintro')), None)
        value = dict(reply=evidence['summary'] if evidence else 'The reported details stay available while we work through the open checks.',
                     question_target=move.get('id'), question=move.get('question',{}).get('question',''),
                     report_refs=[], evidence_refs=[evidence['id']] if evidence else [],
                     education={'purpose':'advance','updates':[],'visual':'none'},
                     agenda_update={'current_concern':'','pause':False})
    return {'status':'completed','model':'gpt-5.4','service_tier':'default',
            'usage':{'input_tokens':0,'output_tokens':0,'total_tokens':0,'input_tokens_details':{'cached_tokens':0}},
            'output':[{'content':[{'type':'output_text','text':json.dumps(value)}]}]}


class Gap(GapRepository):
    def query(self, **body):
        out = super().query(**body)
        original = copy.deepcopy(out['records'][0])
        for variant in ('HDG', 'N'):
            row = copy.deepcopy(original)
            row.update(id=variant, variant=variant, monthly_cents=5000 if variant == 'HDG' else 10000)
            out['records'].append(row)
        return out


class Drugs(FictionalDrugService):
    def products(self, refs, **query):
        text = json.dumps(query).lower()
        if 'insulin' in text: return []
        return [{'rxcui':'999002' if 'levothyroxine' in text else '861007',
                 'name':'Levothyroxine 50 mcg tablet' if 'levothyroxine' in text else 'Metformin 500 mg tablet',
                 'type':'SCD','route':'oral','strength_description':'50 mcg' if 'levothyroxine' in text else '500 mg','form':'tablet'}]
    def outlets(self, refs, **query):
        return [dict(npi='999000000'+str(i), address_id=name, zip='34103', aliases=[name+' Pharmacy'],
                     name='Fictional '+name+' Pharmacy', address={'street':str(i)+' Test Lane','city':'Naples','state':'FL','postal':'34103'})
                for i, name in enumerate(('Harbor','Grove'),1)]
    def formulary_matrix(self, medicines):
        rows = {k.replace('S9999','S9000'):v for k,v in super().formulary_matrix(medicines).items()}
        for med in rows['2026:S9000:009:000']['medicines']: med['state'] = 'not_listed'
        return rows
    def pharmacy(self, refs, plan, selection):
        if plan.endswith(':009:000'): return {'status':'unknown'}, {}
        return super().pharmacy(refs, plan, selection)


class Doctors:
    def __init__(self, plans): self.plans = plans
    def search(self, name, **kwargs):
        found = 'Nera' if 'nera' in name.lower() else 'Tomas' if 'tomas' in name.lower() else None
        candidates = []
        if found:
            for i in range(2 if found == 'Tomas' else 1):
                label = 'Dr. '+found+(' Vale' if found == 'Nera' else ' Reed')
                candidates.append(dict(candidate_id=found+str(i),label=label,kind='clinician',site_count=1,
                    source_npis=[found+str(i)],office_previews=[self.address(found+str(i))]))
        return {'candidates':candidates, 'next_offset':None}
    def address(self, identifier):
        return {'street':'20 Test Lane' if identifier == 'Tomas1' else '10 Test Lane' if identifier == 'Tomas0' else '1 Test Lane',
                'city':'Fort Myers' if identifier == 'Tomas1' else 'Naples','state':'FL','postal':'34103'}
    def sites(self, candidate_id, **kwargs):
        return {'sites':[{'site_id':candidate_id+'-office','address':self.address(candidate_id)}], 'next_offset':None}
    def network_matrix(self, candidate_id, site_id, intended):
        return {'original_medicare':{'state':'dated_listing','assignment':[{'individual_state':'published_accepts_assignment',
                    'group_state':'unknown','published_on':'2026-11-14'}]},
                'plans':{p['offering_id']:{'name':p['name'],'state':'listed' if i%3==0 else 'not_listed' if i%3==1 else 'unknown',
                    'membership':'in_network' if i%3==0 else None,'observations':[{'observed_on':'2026-11-14'}]}
                    for i,p in enumerate(self.plans)}}


def main():
    MANIFEST['fixture_files'] = {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
        for p in [Path(__file__), HERE/'test_medigap_pilot.py', HERE/'test_part_d_pilot.py', HERE/'test_drug_comparison_20261114.py']}
    for attr in ('connect', 'connect_ex'): setattr(socket.socket, attr, denied)
    socket.create_connection = socket.getaddrinfo = denied
    subprocess.Popen = denied
    import guide_server
    guide_server.time = SimpleNamespace(monotonic=lambda: time.monotonic()*100)
    # Prove the provider boundary is denied, without emitting network traffic.
    try: socket.create_connection(('api.openai.com',443))
    except AssertionError: pass
    else: raise AssertionError('Network guard did not engage')
    try: subprocess.Popen(['curl', 'https://api.openai.com'])
    except AssertionError: pass
    else: raise AssertionError('Provider subprocess guard did not engage')
    with tempfile.TemporaryDirectory(prefix='daylight-behavioral-') as directory:
        catalog = CatalogResearch(critical_benefits_path=CRITICAL_BENEFITS_PATH)
        rows = catalog.query(RESEARCH_SCOPE)['plans']
        service = build(0, fixture=True, database=Path(directory)/'guest.sqlite3', local_demo=True,
                        client=ResponsesClient(key='synthetic',model='gpt-5.4',transport=transport),
                        research_catalog=catalog, medigap_repository=Gap(), part_d_repository=DrugRepository())
        service.adaptive.fixture = False
        service.adaptive.agent.enabled = True
        service.adaptive.model_agents = {'gpt-5.4':service.adaptive.agent}
        extract = service.adaptive.agent.extract
        def traced_extract(*args, **kwargs):
            out = extract(*args, **kwargs)
            if out.get('rejected_updates'): print('FICTIONAL REJECTIONS '+json.dumps(out['rejected_updates']),flush=True)
            return out
        service.adaptive.agent.extract = traced_extract
        enrollment_flow.enable(service.adaptive); planner.enable(service.adaptive)
        service.adaptive.conversation_checks = ConversationChecks(service.adaptive,Doctors(rows),Drugs(),lambda:[])
        install(service, binding={'database':'ephemeral-fictional','snapshot_id':MANIFEST['id']},fixture=True,conversation_checks=True)
        base = service.RequestHandlerClass
        class Handler(base):
            def do_POST(self):
                if self.path == '/__test__/expire':
                    if not self.validate_request(): return
                    body = self.body()
                    chain = body.get('continuation','').split('.')[0]
                    owners = [o for o,c in service.adaptive.current_chain.items() if c == chain]
                    for (owner, _), entry in service.adaptive.turn_journal.items():
                        if owner in owners: entry['expires'] = 0
                    return self.respond(200, {'expired':len(owners)})
                return super().do_POST()
            def respond(self, code, value, *args, **kwargs):
                if self.path == '/api/status' and isinstance(value, dict): value = {**value,'offline_test_manifest':MANIFEST}
                return super().respond(code,value,*args,**kwargs)
        service.RequestHandlerClass = Handler
        target = Path(sys.argv[1])
        target.write_text(json.dumps({'url':'http://127.0.0.1:'+str(service.server_port),'manifest':MANIFEST}))
        print(target.read_text(), flush=True)
        service.serve_forever()


if __name__ == '__main__': main()
