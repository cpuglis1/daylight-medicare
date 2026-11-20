"""D176: project approved questions onto real reports and visit-only ask receipts.

No second fact store, intent recognizer, model call or saved-profile mutation.
Only delivered questions spend the repeat allowance. Acknowledgment is not capture.
"""
import copy
from adaptive_flow import FIELD, Q, metadata
import medigap_profile

LIMIT = 2
MAX_RECEIPTS = 128
HELD = {'unknown','explicit_unknown','skipped','deferred','not sure','check later'}


def project(flow, g, r, q, required=False):
    identifier, entity = q['id'].split('.')[0], q.get('entity') or 'profile'
    fields = [f['key'] for f in q.get('fields', [])] or ['choice']
    meta = metadata(r)
    disposition = r.get('dispositions', {}).get(identifier, {}).get('state') or meta['baselineDispositions'].get(identifier)
    path = FIELD.get(identifier) or medigap_profile.FIELDS.get(identifier)
    value = flow.value(g, path) if path else None
    # A saved category without its sensitive details is not a complete answer.
    lost = (identifier=='T06' and value=='list' and not flow.value(g,'needs.providers')
        or identifier=='T07' and value=='yes' and not flow.value(g,'needs.medications')
        or identifier=='T04' and value=='month' and not flow.value(g,'coverage.requestedStartMonth'))
    report = flow.report(r, identifier)
    if entity != 'profile':
        report = next((i for i in report.get('items',[]) if i.get('entity')==entity), {})
    if identifier == 'S_AGE65':
        report = flow.value(g,'situation.age65') or {}
    states = {}
    for field in fields:
        stored = report.get(field)
        if required or q.get('reopened'):
            state = 'open'
        elif (path and value is not None and not lost) or stored is not None and stored not in ('',[]) and str(stored) not in HELD:
            state = 'reported'
        else:
            held = meta['skippedDetails'].get('.'.join((identifier,entity,field))) or disposition
            state = 'deferred' if held in {'deferred','skipped'} else 'unknown' if held in HELD else 'open'
        states[field] = state
    missing = [f for f in fields if states[f]=='open']
    return {'question_id':identifier, 'entity':entity, 'fields':states,
            'key':'|'.join((identifier,entity,','.join(sorted(missing)))),
            'open_fields':missing}


def _records():
    import conversation_records
    return conversation_records


def filter_candidates(flow, owner, g, r, candidates, ledger):
    result=[]
    editing=bool(metadata(r).get('editing'))
    by_passes=_records().pending_on(flow)   # D188: park on passes, not on times shown
    for item in candidates:
        q=item.get('question') or item
        if q.get('localCheck'):
            result.append(item); continue
        p=project(flow,g,r,q,required=bool(item.get('required') or editing))
        if not p['open_fields']:
            continue
        if by_passes:
            if not editing and _records().should_park(flow,owner,p['question_id'],ledger.get(p['key'])):
                ledger[p['key']]['parked']=True
                continue
        elif not editing and ledger.get(p['key'],{}).get('shown',0)>=LIMIT:
            ledger[p['key']]['parked']=True
            continue
        revised=copy.deepcopy(item)
        original=[f['key'] for f in q.get('fields',[])]
        if original and p['open_fields']!=original and q['id'] in Q:
            narrowed=flow.contextual_question(g,r,flow.question(q['id'],p['open_fields'],q.get('entity','profile')))
            revised['question']=narrowed
        revised['question_progress']={k:v for k,v in p.items() if k!='key'}
        revised['question_progress']['shown']=ledger.get(p['key'],{}).get('shown',0)
        result.append(revised)
    return result


def snapshot(flow, g, r, ledger):
    rows={}
    for key, receipt in ledger.items():
        p=project(flow,g,r,receipt['question'])
        states=set(p['fields'].values())
        state=('reported' if states=={'reported'} else 'addressed' if not p['open_fields'] else
               'parked' if key==p['key'] and receipt.get('parked') else 'partial' if 'reported' in states else 'open')
        row={k:v for k,v in p.items() if k not in {'key','open_fields'}}
        label=', '.join(f['label'] for f in receipt['question'].get('fields',[]) if p['fields'].get(f['key'])!='reported')
        row.update(state=state,shown=receipt['shown'],label=label or receipt['question']['question'])
        # Prefer the latest delivered scope for each item/meaning; field states
        # are refreshed from the profile on every read, never assistant prose.
        rows[(p['question_id'],p['entity'])]=row
    return list(rows.values())


def delivered(flow, owner, out, ledger):
    """Last gate, after result attachment; record only the controls actually sent."""
    g,r=out['guide'],out['record']
    q=out['assessment'].get('nextQuestion')
    if q and not q.get('localCheck'):
        item={'id':q['id'],'question':q,
              'required': bool(q.get('resolves') or q['id'].startswith('CP_'))}
        usable=filter_candidates(flow,owner,g,r,[item],ledger)
        if not usable:
            out['assessment']['nextQuestion']=None
        else:
            q=usable[0]['question'];out['assessment']['nextQuestion']=q
            if out.get('generated',{}).get('status') in {'complete','unavailable'}:
                p=project(flow,g,r,q,required=item['required'])
                canonical=(flow.contextual_question(g,r,flow.question(q['id'],[f['key'] for f in q.get('fields',[])] or None,q.get('entity','profile')))
                    if q['id'] in Q or q['id'] in medigap_profile.FIELDS else copy.deepcopy(q))
                count=0 if metadata(r).get('editing') else ledger.get(p['key'],{}).get('shown',0)
                tracked=_records().pending_on(flow)
                prior_key=_records().pending_receipt(ledger)[0] if tracked else None
                old=ledger.pop(p['key'],None) or {}
                ledger[p['key']]={'question':canonical,'shown':count+1}
                if tracked:
                    # D188: the delivered question is the one pending question; passes carry over.
                    if old.get('passes'): ledger[p['key']]['passes']=old['passes']
                    _records().mark_delivered(ledger,p['key'],ledger[p['key']],q,g,r,prior_key)
                while len(ledger)>MAX_RECEIPTS: ledger.pop(next(iter(ledger)))
    out['questionProgress']=snapshot(flow,g,r,ledger)
    unresolved=out['assessment'].setdefault('unresolvedReportedInputs',[])
    for row in out['questionProgress']:
        if row['state']=='parked' and not any(i.get('question_id')==row['question_id'] and i.get('entity')==row['entity'] for i in unresolved):
            unresolved.append({'question_id':row['question_id'],'entity':row['entity'],
                'label':row['label'],'state':'not_yet_recorded'})
