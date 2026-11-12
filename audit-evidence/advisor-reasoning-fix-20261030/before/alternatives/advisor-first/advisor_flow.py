"""Bounded narrative planning, staged reports and revision-bound preparation.

No original engine, source acceptance, customer store or privacy policy is changed.
The model selects reviewed concepts and a permitted move; it cannot author findings.
"""
import copy
import hashlib
import json
import re
import secrets
import time
from datetime import datetime
from zoneinfo import ZoneInfo
from adaptive_flow import AdaptiveConversation, metadata, FIELD, Q, LABELS
from adaptive_agent import AdaptiveAgent
from guest_profiles import ProfileError
from chat import ModelUnavailable

REASONS = {
    'context':'Let’s work through what matters for your situation.',
    'timing':'Let’s keep your coverage dates separate so you can see what still needs checking.',
    'coverage':'Let’s understand your current coverage before considering a change.',
    'learning':'Let’s start with the part you want to understand.',
    'identity':'Let’s make sure we’re discussing the right person or item.',
    'prepare':'We can organize what you know and the questions still open.',
}
SHORT = {'T01':'What would you like help with?', 'RC01':'Who is this for?',
    'T04':'When would you like Medicare coverage to start?', 'T05':'What health insurance do you have now?',
    'T06':'Are there doctors or hospitals you want to keep?', 'T07':'Which prescriptions should we include?',
    'T08':'Will you need routine care away from home?', 'RC11':'When do the job and its insurance end?'}
GOALS = [['learn','Understand Medicare'],['compare','Find coverage'],['review','Review my coverage'],['unresolved','Something else']]
ROW_LABELS={'T01':'Your goal','T02':'Explanation preference','T03':'Home or reference ZIP',
    'T04':'Preferred Medicare start','T05':'Current health insurance','T06':'Doctors to include',
    'T07':'Prescriptions to include','T08':'Care away from home','T09':'Cost preference','T10':'Priorities',
    'RC01':'Who this is for','RC09':'Work insurance','RC11':'Work and insurance end dates',
    'RC21':'Doctor or hospital details','RC22':'Medicine details','RC23':'Prescription fill details'}

def fingerprint(g,r):
    return hashlib.sha256(json.dumps([g,r],sort_keys=True,separators=(',',':')).encode()).hexdigest()

class NarrativeAgent(AdaptiveAgent):
    instructions = AdaptiveAgent.instructions + '''
D86 narrative planning: the opening asks what has the person thinking about Medicare.
Recognize an initial life situation as intent when clear: retirement/job insurance ending means timing preparation, helping a parent identifies the beneficiary, curiosity can mean learn. Do not require a category choice after a clear story.
Choose move_id ONLY from narrative.eligibleMoves. Pick a useful move for this request, including explain or prepare rather than always asking another field. reason_id is a short grounding category, not insurance advice. No authored insurance prose or private reasoning is displayed.
For a continuation, leave task and task_quote empty unless the person explicitly changes their task. Every nonempty task_quote and report quote must be copied EXACTLY from the latest message. Preserve tentative dates as uncertain, never invent precision.
Use fact_ids when a short relevant concept would help the initial situation, even if mode report. At most one concept, except an explicit path-comparison question. Do not give the entire Medicare map to a newcomer.
The server stages all report changes for the person to review before using them. A request to recommend/enroll does not expand tools or authority.
'''

    def context(self,guide):
        value=super().context(guide)
        value['narrative']=copy.deepcopy(getattr(self.local,'narrative',{}))
        return value

    def output_schema(self,facts,eligible):
        spec=super().output_schema(facts,eligible)
        moves=getattr(self.local,'narrative',{}).get('eligibleMoves',['ask'])
        spec['properties'].update(move_id={'type':'string','enum':moves},reason_id={'type':'string','enum':list(REASONS)})
        spec['required'] += ['move_id','reason_id']
        return spec

    def validate_output(self,value,message,guide,facts,eligible,owner):
        value=copy.deepcopy(value)
        move=value.pop('move_id',None);reason=value.pop('reason_id',None)
        if move not in getattr(self.local,'narrative',{}).get('eligibleMoves',[]) or reason not in REASONS:
            raise ModelUnavailable('The suggested next step could not be checked. Your words are still here.')
        # A redundant current-task declaration is not a task change. Do not reject
        # an otherwise valid continuation merely for an unnecessary empty quote.
        current=getattr(self.local,'turn_context',{}).get('task')
        if value.get('task')==current and not value.get('task_quote','').strip():value['task']=''
        result=super().validate_output(value,message,guide,facts,eligible,owner)
        self.local.decision={'move':move,'reason':reason}
        self.local.concept_ids=list(result.get('fact_ids',[]))
        return result

class AdvisorConversation(AdaptiveConversation):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        old=self.agent
        facts={'facts':list(self.facts.values())}
        self.agent=NarrativeAgent(self.contract,facts,client=old.client,enabled=old.enabled,
            max_calls=None,budget=old.budget,count_tokens=old.count_tokens,definitions=old.definitions)
        self.reviews={};self.advisor_cache={};self.authorizations={}

    def question(self,id,fields=None,entity='profile',text=None):
        q=super().question(id,fields,entity,text)
        if not text:q['question']=SHORT.get(id,q['question'])
        if id=='T01':q['choices']=GOALS
        if q['why']=='This missing detail can help prepare the specific check you requested.':q['why']=''
        if id=='RC01':q['why']=''
        if id=='RC09':q['question']='Whose job is this health insurance through?'
        if id=='T04':q['why']='Your preferred start can differ from when your current insurance ends.'
        if id=='RC11':
            keys=[field['key'] for field in q['fields']]
            if len(keys)==2:q['question']='When do the job and its insurance end?'
            elif keys==['coverageEnd']:q['question']='When does that work insurance end?'
            elif keys==['jobEnd']:q['question']='When does that job end?'
            q['why']='Your job and health insurance can end on different dates.'
            for field in q['fields']:
                field['label']='Month and year' if len(q['fields'])==1 else {'jobEnd':'Job end','coverageEnd':'Work insurance end'}.get(field['key'],field['label'])
        return q

    def assess(self,guide,record,edit=None):
        a=super().assess(guide,record,edit)
        task=a['task'];q=a['nextQuestion']
        moves=['ask','explain','prepare'] if q else ['explain','prepare']
        if not task:moves=['ask','explain','prepare']
        a['narrative']={'opener':not task and not metadata(record).get('editing'),
            'eligibleMoves':moves,'action':'prepare','actionLabel':'Prepare my next steps',
            'capabilityVersion':'D86-preparation-v1','visual':self.visual(guide,record),
            'reason':REASONS['timing' if task=='timing' else 'learning' if task=='learn' else 'coverage' if task in {'compare','review'} else 'context'],
            'suggestedCheck':'timing' if task in {'compare','review'} and 'employer' in (self.value(guide,'coverage.current') or []) else None}
        return a

    def visual(self,g,r):
        m=metadata(r);seen=m['journey']['learningSeen']
        if m['task']=='timing':
            return {'kind':'timeline','title':'Your coverage timeline','items':[
                ['Job ends',self.report(r,'RC11').get('jobEnd') or 'Still open'],
                ['Work insurance ends',self.report(r,'RC11').get('coverageEnd') or 'Still open'],
                ['Preferred Medicare start',self.value(g,'coverage.requestedStartMonth') or 'Still open']]}
        if any(x in seen for x in ['routesintro','options','original','advantage','medigap']):return {'kind':'routes','title':'Two coverage paths'}
        if any(x in seen for x in ['parts','parta','partb']):return {'kind':'parts','title':'Original Medicare'}
        return {'kind':'basics','title':'A place to start'}

    def rows(self,g,r):
        rows=[]
        for id,key in FIELD.items():
            field=g['fields'].get(key)
            if field:
                value='unknown' if field['status']=='unknown' else 'deferred' if field['status']=='skipped' else field['value']
                if id=='T04' and value=='month':continue
                if id=='T06' and value=='list' and self.value(g,'needs.providers'):continue
                if id=='T07' and value=='yes' and self.value(g,'needs.medications'):continue
                choices=dict(self.question(id).get('choices',[]))
                if isinstance(value,list):value=', '.join(choices.get(x,x) for x in value)
                elif isinstance(value,str):value=choices.get(value,value)
                if id=='T01' and metadata(r)['task']=='timing':value='Organize a work-to-Medicare transition'
                rows.append({'id':id,'label':ROW_LABELS.get(id,Q[id]['question']),'value':value,'status':field['status']})
        for key,label in [('coverage.requestedStartMonth','Preferred coverage start'),('needs.providers','Doctors and hospitals'),('needs.medications','Prescriptions')]:
            if key in g['fields']:rows.append({'id':next((i for i,k in FIELD.items() if i=={'coverage.requestedStartMonth':'T04','needs.providers':'T06','needs.medications':'T07'}[key]),''),'label':label,'value':g['fields'][key]['value'],'status':g['fields'][key]['status']})
        county=g['fields'].get('comparison.scope.county')
        if county and isinstance(county['value'],dict):
            rows.append({'id':'RC02','label':'County and state','value':', '.join(str(county['value'].get(k,'')) for k in ['name','state']),'status':county['status']})
        for id,f in r['facts'].items():
            value=copy.deepcopy(f['value'])
            if len(value)>1 and value.get('choice') in {'dates','details','partial','amount'}:value.pop('choice')
            choices=dict(Q.get(id,{}).get('choices',[]))
            if value.get('choice') in choices:value['choice']=choices[value['choice']]
            if set(value)=={'choice'}:value=value['choice']
            rows.append({'id':id,'label':ROW_LABELS.get(id,Q[id]['question']),'value':value,'status':'stale' if f.get('stale') else 'reported'})
        for item in super().assess(g,r)['unresolvedReportedInputs']:
            if not (item['id'] in FIELD and any(row['id']==item['id'] and row['status'] in {'unknown','deferred','skipped'} for row in rows)):
                rows.append({'id':item['id'],'label':item['label'],'value':item['state'],'status':item['state']})
        return rows

    def response(self,g,r,reply='',**extras):
        return {'guide':copy.deepcopy(g),'record':copy.deepcopy(r),'assessment':self.assess(g,r),
            'reply':reply,'facts':[],'pendingId':None,'pendingUpdates':[],
            'metrics':{'llmCalls':0,'synthetic':self.fixture},'personalRecommendation':False,
            'reportedRows':self.rows(g,r),**extras}

    def stage(self,owner,g,r,candidate,kind='form',facts=None):
        token=secrets.token_urlsafe(24)
        self.reviews[token]={'owner':owner,'before':fingerprint(g,r),'guide':copy.deepcopy(candidate['guide']),
            'record':copy.deepcopy(candidate['record']),'expires':time.time()+600,'kind':kind}
        before={(x['id'],x['label']):x for x in self.rows(g,r)}
        changes=[x for x in self.rows(candidate['guide'],candidate['record']) if before.get((x['id'],x['label']))!=x]
        return self.response(g,r,'Here’s what I understood.' if kind=='interpretation' else 'Review the details you entered.',
            review={'token':token,'kind':kind,'rows':changes,'label':'Use these details'},facts=facts or [],
            metrics=candidate.get('metrics',{'llmCalls':0,'synthetic':self.fixture}))

    def turn(self,owner,payload):
        if not isinstance(payload,dict) or set(payload)-{'guide','record','action','requestId','aiConsent','pendingId'} or not re.fullmatch(r'[A-Za-z0-9-]{10,80}',str(payload.get('requestId',''))):
            raise ProfileError('Use a current conversation request.')
        g,r=self.validate(payload['guide'],payload['record']);action=payload.get('action',{})
        if not isinstance(action,dict):raise ProfileError('Use a supported action.')
        key=(owner,payload['requestId']);sig=hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()
        with self.lock:
            self.advisor_cache={k:v for k,v in self.advisor_cache.items() if v['expires']>time.time()}
            self.reviews={k:v for k,v in self.reviews.items() if v['expires']>time.time()}
            if key in self.advisor_cache:
                old=self.advisor_cache[key]
                if old['signature']!=sig:raise ProfileError('This request key belongs to another action.',409)
                return copy.deepcopy(old['response'])
            # Serialize one owner's stateful review/actions; model calls are also
            # bounded globally by the inherited HTTP service semaphore.
            if any(k[0]==owner for k in self.active):raise ProfileError('Your previous request is still running. Your work is preserved.',409)
        kind=action.get('type')
        if kind in {'accept_review','discard_review','run_preparation'}:
            if set(action)!={'type','token'}:raise ProfileError('Use the current review action.')
            with self.lock:
                proposal=self.reviews.get(action['token'])
                if not proposal or proposal['owner']!=owner or proposal['before']!=fingerprint(g,r):
                    raise ProfileError('Your details changed or this review expired. Review them again before continuing.',409)
                if kind=='discard_review':out=self.response(g,r,'Your previous information is unchanged.')
                elif kind=='accept_review':
                    if proposal['kind']=='preparation':raise ProfileError('Confirm the named preparation action.')
                    cg,cr=self.validate(proposal['guide'],proposal['record'])
                    out=self.response(cg,cr,self.grounded_summary(cg,cr))
                    if proposal.get('focus')=='prepare':out['assessment']['narrative']['focus']='prepare'
                else:
                    if proposal['kind']!='preparation':raise ProfileError('Review the preparation action first.')
                    out=self.response(g,r,'Your next steps are prepared.',preparation=self.prepare(g,r))
                self.reviews.pop(action['token'],None)
        elif kind=='stage':
            if set(action)-{'type','id','fields','entity'}:raise ProfileError('Use only the active form fields.')
            current=self.assess(g,r)['nextQuestion']
            if not current or action.get('id')!=current['id'] or action.get('entity','profile')!=current['entity']:
                raise ProfileError('This form is no longer current. Your draft is preserved.',409)
            fields=action.get('fields',{})
            if not isinstance(fields,dict) or not fields or any(not isinstance(v,str) or not v.strip() for v in fields.values()):raise ProfileError('Enter what you know, or mark a missing detail unknown.')
            candidate=super().turn(owner,{**payload,'action':{**action,'type':'choice'}})
            out=self.stage(owner,g,r,candidate)
        elif kind=='review_preparation':
            if set(action)!={'type'}:raise ProfileError('Use the preparation review action.')
            token=secrets.token_urlsafe(24)
            self.reviews[token]={'owner':owner,'before':fingerprint(g,r),'guide':g,'record':r,'kind':'preparation','expires':time.time()+600}
            out=self.response(g,r,'Review what your next steps will use.',review={'token':token,'kind':'preparation','rows':self.rows(g,r),'label':'Prepare my next steps'})
        elif kind=='resume':
            metadata(r)['editing']=''
            out=self.response(g,r)
        elif kind=='read_concept':
            if set(action)!={'type','id'} or action.get('id') not in self.facts:raise ProfileError('Choose a reviewed explanation.')
            fact=self.facts[action['id']]
            if fact['id'] not in metadata(r)['journey']['learningSeen']:metadata(r)['journey']['learningSeen'].append(fact['id'])
            r['stateVersion']+=1
            out=self.response(g,r,facts=[fact])
        elif kind=='suggest_check':
            if set(action)!={'type','id'} or self.assess(g,r)['narrative']['suggestedCheck']!=action.get('id'):raise ProfileError('That check is not available for this situation.')
            metadata(r)['task']='timing';metadata(r)['preparing']=True;r['stateVersion']+=1
            out=self.response(g,r,REASONS['timing'])
        elif kind=='start':out=self.response(g,r)
        else:
            unknown_question=None
            if kind in {'unknown','defer'}:
                unknown_question=self.assess(g,r)['nextQuestion']
                if not unknown_question or action.get('id')!=unknown_question['id']:raise ProfileError('Use the current question when leaving a detail open.')
                disposition='unknown' if kind=='unknown' else 'deferred'
                fields={f['key']:disposition for f in unknown_question['fields']} or {'choice':disposition}
                payload={**payload,'action':{'type':'choice','id':unknown_question['id'],'entity':unknown_question['entity'],'fields':fields}}
            self.agent.local.narrative={'eligibleMoves':self.assess(g,r)['narrative']['eligibleMoves']}
            self.agent.local.decision=None
            self.agent.local.concept_ids=[]
            try:out=super().turn(owner,payload)
            finally:self.agent.local.narrative={}
            decision=getattr(self.agent.local,'decision',None)
            if unknown_question:
                cg,cr=out['guide'],out['record'];id=unknown_question['id']
                if id in FIELD:
                    self.invalidate(cr,FIELD[id])
                    for related in {'T04':['coverage.requestedStartMonth'],'T06':['needs.providers'],'T07':['needs.medications']}.get(id,[]):
                        if related in cg['fields']:cg['fields'][related]['status']='unknown'
                        self.invalidate(cr,related)
                elif not unknown_question['fields'] and id in cr['facts']:
                    cr['facts'][id]['stale']=True
                    if id=='RC01' and 'subject.role' in cg['fields']:cg['fields']['subject.role']['status']='unknown'
                if id=='T01':metadata(cr)['task']='learn'
                cr['stateVersion']+=1
                out['assessment']=self.assess(cg,cr)
                out['reply']='We’ll keep that open and work with what you know.'
            if kind=='message' and decision and not out.get('facts'):
                out['facts']=[self.facts[id] for id in getattr(self.agent.local,'concept_ids',[])]
                for fact in out['facts']:
                    if fact['id'] not in metadata(out['record'])['journey']['learningSeen']:
                        metadata(out['record'])['journey']['learningSeen'].append(fact['id'])
                        out['record']['stateVersion']+=1
            if kind=='message':
                candidate=copy.deepcopy(out)
                if candidate.get('pendingUpdates'):
                    for update in candidate['pendingUpdates']:self.apply(candidate['guide'],candidate['record'],update,'confirmed_agent_interpretation')
                    self.pending.pop(candidate.get('pendingId'),None)
                # Choosing a learning topic or requested work is navigation.
                # Personal reports still require their own inline review.
                prior=[row for row in self.rows(g,r) if row['id']!='T01']
                proposed=[row for row in self.rows(candidate['guide'],candidate['record']) if row['id']!='T01']
                changed=prior!=proposed
                if changed:out=self.stage(owner,g,r,candidate,'interpretation',out.get('facts'))
            out['reportedRows']=self.rows(out['guide'],out['record'])
            if decision:
                out['planner']={'move':decision['move'],'reason':REASONS[decision['reason']],'validated':True}
                if not out.get('review'):
                    out['reply']=REASONS[decision['reason']]
                    if decision['move']=='prepare':out['assessment']['narrative']['focus']='prepare'
                elif decision['move']=='prepare':self.reviews[out['review']['token']]['focus']='prepare'
            if kind=='choice' and action.get('id')=='T01':
                out['reply']='Tell me a little about what you’d like to work through.' if metadata(out['record'])['task'] not in {'learn',''} else ''
            if kind=='refresh':out['reply']=''
        with self.lock:
            if len(self.advisor_cache)>128:self.advisor_cache.pop(next(iter(self.advisor_cache)))
            self.advisor_cache[key]={'signature':sig,'response':copy.deepcopy(out),'expires':time.time()+600}
        return out

    def grounded_summary(self,g,r):
        task=metadata(r)['task']
        if task=='timing':
            bits=[]
            dates=self.report(r,'RC11')
            if dates.get('jobEnd'):bits.append('job ends '+dates['jobEnd'])
            if dates.get('coverageEnd'):bits.append('work insurance ends '+dates['coverageEnd'])
            desired=self.value(g,'coverage.requestedStartMonth')
            if desired:bits.append('preferred coverage start '+desired)
            if bits:return 'Your reported timeline: '+ '; '.join(bits)+'.'
        return 'I’ll use these reported details and keep anything unknown open.'

    def prepare(self,g,r):
        assessment=self.assess(g,r);rows=self.rows(g,r)
        lines=['Your Medicare next steps','Prepared '+datetime.now(ZoneInfo('America/New_York')).strftime('%B %d, %Y'),'','Your reported information']
        for row in rows:lines.append(row['label']+': '+self.print_value(row['value']))
        if not rows:lines.append('No personal information provided. You can start with Medicare basics.')
        lines += ['', 'What to check next']
        task=metadata(r)['task']
        if task=='timing':lines += ['Ask the benefits office to confirm the exact job and health insurance end dates.','Ask which Medicare enrollment steps apply to the confirmed dates and your actual coverage history.','Ask how a change would affect anyone else on the work insurance.']
        elif task in {'drug_coverage','drug_pricing'}:lines += ['Confirm each medicine’s exact name, strength and form.','For a price question, confirm quantity with units, days supply and the exact pharmacy.','Check the exact plan year and restrictions before relying on a coverage or cost answer.']
        elif task=='providers':lines += ['Confirm the exact doctor, practice and office location.','Check the exact plan and year with both the office and the plan.']
        elif task=='medigap':lines += ['Confirm actual Part B and prior coverage dates.','Check applicable buying or return rules and actual policy availability before making a change.']
        else:lines += ['Understand Original Medicare with optional drug and supplement coverage, and Medicare Advantage.','Compare costs, provider access, restrictions and future flexibility.','Keep your current coverage as a baseline if you already have coverage.']
        if assessment['nextQuestion']:lines += ['Still open: '+assessment['nextQuestion']['question']]
        for row in assessment['unresolvedReportedInputs']:lines.append('Still open: '+row['label']+' ('+row['state']+')')
        lines += ['', 'Scope','This is a preparation checklist using your reports. It is not verified eligibility, an enrollment deadline, a personal price or a plan recommendation. No outside party was contacted.']
        return {'id':secrets.token_urlsafe(18),'kind':'preparation','status':'prepared',
            'inputDigest':fingerprint(g,r),'guideRevision':g['stateVersion'],'recordRevision':r['stateVersion'],
            'capabilityVersion':'D86-preparation-v1','createdAt':time.time(),'text':'\n'.join(lines)}

    @staticmethod
    def print_value(value):
        if isinstance(value,dict):return '; '.join(LABELS.get(k,k)+': '+AdvisorConversation.print_value(v) for k,v in value.items() if k not in {'entity'})
        if isinstance(value,list):return ', '.join(AdvisorConversation.print_value(x) for x in value)
        if isinstance(value,str) and re.fullmatch(r'\d{4}-\d{2}(?:-\d{2})?',value):
            fmt='%Y-%m-%d' if len(value)==10 else '%Y-%m'
            return datetime.strptime(value,fmt).strftime('%B %d, %Y' if len(value)==10 else '%B %Y')
        return str(value)
