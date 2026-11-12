"""Local D86 language boundary: meaningful retrieval and grounded report proposals.

The pinned :8891 engine stays read-only. The request runner below is a local static
copy of its bounded runner with an explicit reasoning setting; budget limits stay
8000 input / 900 total output tokens, shared $1 UTC/day, with no automatic retry.
"""
import copy
import hashlib
import json
import re
import time
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from adaptive_agent import AdaptiveAgent
from adaptive_flow import Q
from chat import ModelUnavailable
from guest_profiles import ProfileError, validate_guide
from ai_budget import BudgetError
from guide_agent import INSTRUCTIONS
from situation import observations, supported_choice, timing_request

REASON_IDS = ['context','timing','coverage','learning','identity','prepare']
STOP = set('about after again also already been before could does each from have help here into just know like more need other should some that their them there these they this through want what when where which while will with would years your'.split())
TOPICS = {
 'basics':r'\bwhat is medicare(?:\s*[?.!]|$)|\bmedicare basics\b|\bhow (?:does )?medicare work',
 'parts':r'\bparts? a (?:and|&) b\b|\bparts? of medicare\b',
 'parta':r'\bpart a\b', 'partb':r'\bpart b\b',
 'advantage':r'\b(?:medicare advantage|part c)\b', 'medigap':r'\b(?:medigap|supplement)\b',
 'drugbasics':r'\b(?:part d|prescription coverage|drug coverage)\b',
 'routesintro':r'\b(?:two|different) (?:coverage )?(?:paths|routes|options)\b|original medicare.*advantage',
 'costs':r'\b(?:cost|costs|premium|premiums|copay|copays)\b',
 'dates':r'\b(?:enroll|enrollment|deadline|sign up)\b',
 'checks':r'\b(?:check|look for|compare)\b.{0,30}\bplans?\b|\b(?:ranked|ranking|source order)\b',
}

class NarrativeAgent(AdaptiveAgent):
    instructions = AdaptiveAgent.instructions + '''
D86 corrected situation reasoning:
Separate life circumstances from current health insurance, the requested task,
desired coverage timing, actual Medicare enrollment, and verified findings.
Already retired is NOT retiree health coverage and is NOT a job ending now.
Retiring soon is NOT an insurance end date. Turning 65 is NOT already enrolled.
A birthday month is NOT a requested coverage start; preserve its unknown year.
An initial age-65/enrollment story can focus on timing, without calling it a work transition.
Past retirement alone does not establish a timing task. Ask about current insurance
before asking someone already retired for a preferred coverage start.
Every categorical report must be entailed by its exact quote, not merely associated
with a word in it. Omit unsupported categories. Record explicit self/helper scope.
Use the full question_catalog for purpose, dependency and cannotInfer distinctions.
These 41 IDs are conditional capabilities, not a questionnaire to complete.
Use no fact_ids for a life report without an actual educational question. An empty
retrieval is legitimate: do not attach the closest unrelated teaching block.
Choose move_id only from narrative.eligibleMoves and reason_id from its enum.
No authored insurance prose, arbitrary tools or personal eligibility findings.
For continuations, leave task/task_quote empty unless explicitly changing focus.
Examples:
"I've been retired for years and turn 65 in November" -> beneficiary self,
timing focus; NO retiree coverage, NO job end, NO desired coverage start.
"My retiree insurance is through my former employer" -> explicit current retiree coverage.
"I have Parts A and B through my Advantage plan" -> A/B status and Advantage;
do NOT add Original Medicare as a separate current delivery arrangement.
"This is for my mom. I am retired" -> do not record the helper's retirement as hers.
'''

    def __init__(self,*args,reasoning_effort='none',**kwargs):
        super().__init__(*args,**kwargs)
        if reasoning_effort not in {'none','low','medium'}:raise ValueError('Unsupported reasoning setting.')
        self.reasoning_effort=reasoning_effort
        self.definitions=[{'id':q['id'],'question':q['question'],'options':q.get('choices',[]),'fields':q['fieldNames']} for q in Q.values()]
        self.catalog=[{'id':q['id'],'purpose':q['capabilities'],'dependency':q['dependencies'],
            'requiredWhen':q['requiredness'],'cannotInfer':{
                'T04':'Desired start is not birthday, insurance end or actual Medicare start.',
                'T05':'Current insurance only. Retired does not imply retiree insurance. A/B entitlement does not identify delivery.',
                'RC04':'Actual A/B enrollment, not age or a future plan.',
                'RC05':'Actual Part B effective date, not desired start or birthday.',
                'RC06':'Reported age/basis is not verified eligibility.',
                'RC09':'Whose actual insurance, not employment status alone.',
                'RC11':'Job and insurance ends separately; no date from retirement alone.',
                'RC16':'Exact stated episode; intended future start is not actual history.'
            }.get(q['id'],'Explicit scoped report only; unknown does not establish a negative or verified result.')} for q in Q.values()]

    def context(self,guide):
        context=super().context(guide)
        context['question_catalog']=self.catalog
        context['narrative']=copy.deepcopy(getattr(self.local,'narrative',{}))
        # Only public question semantics are added. Prior sensitive values/history
        # are deliberately not attached by this change.
        if context.get('activeQuestion'):
            context['activeQuestion']['question']=Q[context['activeQuestion']['id']]['question']
        return context

    def retrieve(self,message,node):
        educational=bool(re.search(r'\?|\b(?:what|how|why|explain|tell me|difference|help me understand)\b',message,re.I))
        if not educational:return []
        ids=[id for id,pattern in TOPICS.items() if re.search(pattern,message,re.I)]
        words=set(re.findall(r'[a-z]{4,}',message.lower()))-STOP
        if not ids:
            ranked=[]
            for id,fact in self.facts.items():
                terms=set(re.findall(r'[a-z]{4,}',(fact['title']+' '+fact['question']).lower()))-STOP
                score=len(words & terms)
                if score>=2:ranked.append((score,id))
            ids=[id for _,id in sorted(ranked,reverse=True)[:3]]
        if re.search(r'\b(?:that|it|those)\b',message,re.I) and not ids:
            ids=getattr(self.local,'turn_context',{}).get('lastFactIds',[])[:1]
        return [self.facts[id] for id in dict.fromkeys(ids) if id in self.facts][:3]

    def output_schema(self,facts,eligible):
        spec=super().output_schema(facts,eligible)
        if not facts:spec['properties']['fact_ids']={'type':'array','items':{'type':'string'},'maxItems':0}
        spec['properties'].update(move_id={'type':'string','enum':getattr(self.local,'narrative',{}).get('eligibleMoves',['ask'])},reason_id={'type':'string','enum':REASON_IDS})
        spec['required']+=['move_id','reason_id']
        return spec

    def validate_output(self,value,message,guide,facts,eligible,owner):
        value=copy.deepcopy(value);move=value.pop('move_id',None);reason=value.pop('reason_id',None)
        if move not in getattr(self.local,'narrative',{}).get('eligibleMoves',[]) or reason not in REASON_IDS:
            raise ModelUnavailable('The proposed next step could not be checked. Your words are still here.')
        current=getattr(self.local,'turn_context',{}).get('task')
        if value.get('task')==current and not value.get('task_quote','').strip():value['task']=''
        result=super().validate_output(value,message,guide,facts,eligible,owner)
        active=getattr(self.local,'turn_context',{}).get('activeQuestion')
        clean=[];rejected=[]
        for update in result['updates']:
            id=update['id'].split('.')[0];values={f['key']:f['value'] for f in update['fields']}
            if id=='T05' and ',' in values.get('choice',''):
                supported=[choice for choice in values['choice'].split(',') if supported_choice(id,choice,update['quote'],active)]
                if supported and len(supported)<len(values['choice'].split(',')):
                    update=copy.deepcopy(update)
                    next(f for f in update['fields'] if f['key']=='choice')['value']=values['choice']=','.join(supported)
                    rejected.append(id)
            valid=supported_choice(id,values.get('choice',''),update['quote'],active)
            if id=='RC09' and update['scope']!='current':valid=False
            birthday=bool(re.search(r'\b(?:turn(?:ing)? 65|birthday)\b',update['quote'],re.I))
            desired=bool(re.search(r'\b(?:want|need|prefer|would like|plan for)\s+(?:(?:my|new|the)\s+)?(?:medicare|coverage|part b)\b.{0,40}\b(?:start|begin|in|from|then|that month)\b',update['quote'],re.I))
            actual=bool(re.search(r'\b(?:started|began|took effect|became effective|has been active)\b',update['quote'],re.I))
            if id=='T04' and birthday and not desired:valid=False
            if id=='RC05' and (birthday or re.search(r'\b(?:want|need|plan|hope|intend|will start|will begin)\b',update['quote'],re.I)) and not actual:valid=False
            if valid:clean.append({**update,'id':id})
            else:rejected.append(id)
        result['updates']=clean
        if result['task']=='timing' and current!='timing' and not timing_request(message):result['task']='';result['task_quote']=''
        # The server derives only narrowly explicit life observations; arbitrary
        # narrative text or model-authored summaries are never persisted.
        role=guide['fields'].get('subject.role',{}).get('value')
        self.local.observations=observations(message,role)
        if self.local.observations and not current and not result['task'] and 'age65' in self.local.observations:
            result['task']='timing';result['task_quote']=message
        self.local.decision={'move':move,'reason':reason};self.local.rejected=rejected
        self.local.concept_ids=list(result['fact_ids']) if result['mode']=='answer' else []
        return result

    def run(self,owner,message,guide,eligible,request_id,emit=lambda *x:None):
        validate_guide(guide,self.contract)
        if not isinstance(message,str) or not 1<=len(message.strip())<=1200:raise ProfileError('Use 1–1200 characters.')
        if re.search(r'\b\d{3}-\d{2}-\d{4}\b',message):raise ProfileError('Remove ID numbers before asking.')
        eligible=[x for x in eligible if x in self.nodes][:12]
        if not eligible:eligible=[guide['flow']['node']]
        key=(owner,request_id);signature=hashlib.sha256(json.dumps([message,guide['stateVersion'],self.context(guide),eligible],sort_keys=True).encode()).hexdigest()
        with self.lock:
            self.cache={k:v for k,v in self.cache.items() if v['expires']>time.time()};self.pending={k:v for k,v in self.pending.items() if v['expires']>time.time()}
            cached=self.cache.get(key)
            if cached:
                if cached['signature']!=signature:raise ProfileError('Request key already used.',409)
                return cached['result']
            if key in self.active:raise ProfileError('This request is still running. Retry after it finishes.',409)
            if not self.enabled or not self.client.available:raise ModelUnavailable('Live AI is not enabled. Use manual answers or reviewed explanations; your guide is unchanged.')
            if self.max_calls is not None and self.calls>=self.max_calls:raise ModelUnavailable('The configured live-request budget is reached. Manual guidance remains available.')
            self.active.add(key)
        reservation=None;completed_response=None
        # A local two-stage caller can reserve the whole turn before either
        # request. The pinned shared runner is unchanged; never reserve twice.
        budget_stage=getattr(self.local,'budget_stage',None)
        if budget_stage and budget_stage.budget is not self.budget:
            raise BudgetError('The turn reservation belongs to another budget.')
        try:
            if not self.budget and not self.client.transport:raise BudgetError('A persistent daily AI budget is required.')
            if self.budget and not budget_stage:
                status=self.budget.summary(self.client.model)
                if not status['canRequest']:raise BudgetError(status['reason'])
            emit('status',{'message':'Finding reviewed teaching and the current task…'})
            facts=self.retrieve(message,guide['flow']['node']);spec=self.output_schema(facts,eligible)
            output_limit=getattr(self,'max_output_tokens',900)
            payload={'model':self.client.model,'instructions':getattr(self,'instructions',INSTRUCTIONS),'input':[{'role':'user','content':json.dumps({'submitted_text':message,'confirmed_context':self.context(guide),'current_node':guide['flow']['node'],'eligible_tasks':[{'id':x,'question':self.nodes[x]['question']} for x in eligible],'reviewed_facts':facts,'field_rules':self.field_rules()},ensure_ascii=False)}],'store':False,'max_output_tokens':output_limit,'reasoning':{'effort':self.reasoning_effort},'tools':[],'text':{'format':{'type':'json_schema','name':'daylight_guide_commands','strict':True,'schema':spec}},'stream':True,'service_tier':'default'}
            raw=json.dumps(payload).encode()
            if len(raw)>getattr(self,'max_input_bytes',24000):raise ProfileError('This request is too large for the configured test budget.')
            with self.lock:
                if self.max_calls is not None and self.calls>=self.max_calls:raise ModelUnavailable('The live-request budget is reached.')
                if self.budget:
                    count=self.count_tokens(self.client,payload)
                    if budget_stage:
                        budget_stage.check_input(count);reservation=budget_stage.key
                    else:reservation=self.budget.reserve(count,output_limit,self.client.model)
                if self.on_call:self.on_call(len(raw),output_limit)
                self.calls+=1
            emit('status',{'message':'Daylight is preparing a grounded response…'})
            if self.client.transport:
                if budget_stage:budget_stage.issued()
                result=self.client.transport(payload);completed_response=result;self.usage.append(result.get('usage',{}));text=''.join(c.get('text','') for o in result.get('output',[]) for c in o.get('content',[]) if c.get('type')=='output_text')
            else:
                request=Request('https://api.openai.com/v1/responses',data=raw,headers={'Authorization':'Bearer '+self.client.key,'Content-Type':'application/json'},method='POST');text='';complete=False;count=0
                if budget_stage:budget_stage.issued()
                with urlopen(request,timeout=40) as response:
                    for line in response:
                        if len(line)>200000:raise ModelUnavailable('The response exceeded its bound.')
                        if not line.startswith(b'data: '):continue
                        event=json.loads(line[6:]);kind=event.get('type')
                        if kind=='response.output_text.delta':
                            text+=event.get('delta','');count+=1
                            if len(text)>20000:raise ModelUnavailable('The response exceeded its bound.')
                            if count%12==0:emit('status',{'message':'Checking the response before showing it…'})
                        elif kind=='response.completed':
                            complete=True;completed_response=event.get('response',{});self.usage.append(completed_response.get('usage',{}))
                        elif kind in {'response.failed','response.incomplete','error'}:raise ModelUnavailable('The model could not finish. Your guide is unchanged.')
                if not complete:raise ModelUnavailable('The response ended early. Your guide is unchanged.')
            if self.budget:
                self.budget.settle(reservation,completed_response)
                if budget_stage:budget_stage.settled()
            answer=self.validate_output(json.loads(text),message,guide,facts,eligible,owner)
            with self.lock:
                if len(self.cache)>100:self.cache.clear()
                self.cache[key]={'signature':signature,'result':answer,'expires':time.time()+600}
            return answer
        except (HTTPError,URLError,TimeoutError,json.JSONDecodeError,KeyError,TypeError) as error:raise ModelUnavailable('Live AI could not complete this request. Retry or use the manual guide; your details are unchanged.') from error
        finally:
            if budget_stage:budget_stage.finish()
            elif reservation:self.budget.uncertain(reservation)
            with self.lock:self.active.discard(key)
