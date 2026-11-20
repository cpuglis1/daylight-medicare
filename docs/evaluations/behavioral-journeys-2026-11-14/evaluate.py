#!/usr/bin/env python3
"""Offline suite validation and evidence grading. No app, network or model calls.

Judgments are explicit human review, not inferred from nonempty replies or turns.
The tool checks evidence completeness; it cannot prove a reviewer is correct.
"""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
UI_KINDS = {'jump_ahead','open_side_chat','return','inspect_details','backtrack','switch_path_view',
            'draft_navigation','refresh','expiry'}
CONTROL_IDS = {'goal','answer_first','retention','decision_control','evidence_integrity',
               'finish_honesty','navigation','correction'}
QUALITY_IDS = {'clarity','effort','continuity','control','useful_finish'}
CRITICAL = {'invented_result','unsupported_recommendation','wrong_subject','stale_result',
            'unintended_decision','false_enrollment','unauthorized_transmission','source_stop_ignored'}


def read(path):
    return json.loads(Path(path).read_text())


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def suite():
    return read(HERE/'profiles.json')


def validate(spec):
    errors=[]
    def need(condition, message):
        if not condition: errors.append(message)
    need(spec.get('fictional_only') is True, 'Suite must be fictional-only')
    rows=spec.get('profiles',[])
    need(len(rows)==12, 'Expected twelve authored profiles')
    need(len({p['id'] for p in rows})==len(rows), 'Duplicate profile ID')
    for p in rows:
        for key in ('name','goal','opening','private_facts','primary_behavior','coverage_context',
                    'disclosure_policy','decision_policy','finish','evidence_dependency','variants'):
            need(bool(p.get(key)), f"{p['id']}: missing {key}")
        ids=[b['id'] for b in p['beats']]
        need(len(set(ids))==len(ids), f"{p['id']}: duplicate beat")
        need(any(b['kind']=='finish' for b in p['beats']), f"{p['id']}: no finish")
        need(any(b['kind'] in UI_KINDS for b in p['beats']), f"{p['id']}: no UI behavior")
        for b in p['beats']:
            need(all(b.get(k) for k in ('when','action','expect','if_unavailable')), f"{b['id']}: incomplete branch")
            need(set(b['required_in']) <= {'direct','interrupted'}, f"{b['id']}: invalid variant")
        need(p['budget']['user_actions_soft']<p['budget']['user_actions_hard'],f"{p['id']}: bad budget")
    return errors


def profile(id):
    return next(p for p in suite()['profiles'] if p['id']==id)


def required_controls(p):
    return CONTROL_IDS - (set() if any(b['kind']=='correction' for b in p['beats']) else {'correction'})


def template(p,variant):
    return {'format':'behavioral-run-v1','profile':p['id'],'variant':variant,
        'suite_sha256':digest(HERE/'profiles.json'),'fictional_only':True,
        'status':'not_started','mode':'offline_browser','build':{'revision':None,'source_hashes':{},
            'planner_enabled':None,'runtime_verified':False},
        'evidence_mode':'synthetic','language_mode':'scripted','started_at':None,'ended_at':None,
        'artifacts':{},'events':[], 'assertions':[], 'critical_findings':[],
        'quality':{},'outcome':{'type':'incomplete','next_action':None,'blocker':None},
        'required_beats':[b['id'] for b in p['beats'] if variant in b['required_in']],
        'required_assertions':sorted(required_controls(p)),
        'notes':'Blank capture contract. This is not a run or a passing result.'}


def grade(run,base):
    p=profile(run['profile']); variant=run['variant']
    required={b['id'] for b in p['beats'] if variant in b['required_in']}
    errors=[]; pending=[]
    if run.get('format')!='behavioral-run-v1': errors.append('Wrong trace format')
    if variant not in ('direct','interrupted'): errors.append('Unknown variant')
    if run.get('fictional_only') is not True: errors.append('Only fictional traces are permitted')
    if run.get('suite_sha256')!=digest(HERE/'profiles.json'): errors.append('Suite hash mismatch; use matching version')
    artifacts=run.get('artifacts',{})
    valid={}
    for id,a in artifacts.items():
        path=Path(a.get('path',''))
        # Artifact references are bounded to the run directory, never arbitrary user files.
        resolved=(base/path).resolve()
        if path.is_absolute() or not resolved.is_relative_to(base.resolve()):
            errors.append(f'{id}: artifact outside run directory'); continue
        if not resolved.is_file() or not a.get('sha256') or digest(resolved)!=a['sha256']:
            errors.append(f'{id}: missing/changed artifact'); continue
        if a.get('origin') not in ('observed_ui','observed_backend','review_notes','synthetic_self_test'):
            errors.append(f'{id}: unknown evidence origin'); continue
        valid[id]=a
    events=run.get('events',[]); event_by_id={e['id']:e for e in events}
    if len(events)!=len(event_by_id): errors.append('Duplicate event IDs')
    if [e.get('seq') for e in events] != list(range(1,len(events)+1)): errors.append('Event sequence missing/reordered')
    beats={b['id']:b for b in p['beats']}
    blocked_beats=[]
    reached=set(); ui_observed=set()
    for e in events:
        beat=e.get('beat_id')
        if beat and beat not in beats: errors.append(f"{e['id']}: unknown beat")
        if not e.get('action') or not e.get('observation'): errors.append(f"{e['id']}: action or observation absent")
        if e.get('status') not in ('performed','blocked','not_triggered'):
            errors.append(f"{e['id']}: invalid execution status")
        if beat in required and e.get('status')!='performed': blocked_beats.append(beat)
        refs=e.get('evidence_ids',[])
        if not refs or any(x not in valid for x in refs): pending.append(f"{e['id']}: missing event evidence")
        else:
            reached.add(beat)
            if any(valid[x]['origin']=='observed_ui' for x in refs): ui_observed.add(beat)
    missing=required-reached
    if missing: pending.append('Unobserved required beats: '+', '.join(sorted(missing)))
    missing_ui={bid for bid in required if beats[bid]['kind'] in UI_KINDS}-ui_observed
    if missing_ui: pending.append('UI evidence missing: '+', '.join(sorted(missing_ui)))
    judgments={}; failed=[]
    for a in run.get('assertions',[]):
        id=a['id']
        if id in judgments: errors.append(f'Duplicate assertion {id}'); continue
        judgments[id]=a
        if id not in required_controls(p): errors.append(f'Unknown assertion {id}')
        refs=a.get('evidence_ids',[]); ev=a.get('event_ids',[])
        evidenced=bool(refs and ev and a.get('reason') and a.get('reviewer')) and all(x in valid for x in refs) and all(x in event_by_id for x in ev)
        if not evidenced or a.get('reviewer_role') not in ('human_owner','human_reviewer'):
            pending.append(f'{id}: needs evidence-linked human review')
        elif a.get('status')=='fail': failed.append(id)
        elif a.get('status')!='pass': pending.append(f'{id}: unresolved')
    pending += [f'{id}: no judgment' for id in sorted(required_controls(p)-judgments.keys())]
    critical=[]
    for f in run.get('critical_findings',[]):
        if f.get('kind') not in CRITICAL: errors.append('Unknown critical finding')
        if not f.get('reason') or not f.get('event_ids') or any(e not in event_by_id for e in f.get('event_ids',[])):
            errors.append('Critical finding needs event-linked rationale')
        critical.append(f.get('kind'))
    quality={}; quality_pending=[]
    for id in sorted(QUALITY_IDS):
        q=run.get('quality',{}).get(id,{})
        if (not (id=='clarity' and run.get('language_mode')!='natural_owner') and type(q.get('score')) is int and 0<=q['score']<=3 and q.get('reason') and q.get('reviewer')
                and q.get('reviewer_role') in ('human_owner','human_reviewer')
                and q.get('evidence_ids') and all(r in valid for r in q['evidence_ids'])):
            quality[id]=q['score']
        else: quality_pending.append(id)
    build=run.get('build',{})
    if not (build.get('revision') and build.get('source_hashes') and build.get('planner_enabled') is True
            and build.get('runtime_verified') is True): pending.append('Runtime/planner/build identity not verified')
    if not any(a['origin']=='observed_ui' for a in valid.values()): pending.append('No observed UI evidence for this journey')
    if run.get('mode') not in ('offline_browser','manual_owner'): pending.append('Backend-only or scripted transport cannot prove the visible journey')
    if any(a['origin']=='synthetic_self_test' for a in valid.values()): pending.append('Evaluator self-test evidence is not an app run')
    if run.get('status')!='finished': pending.append('Run not finished')
    if not run.get('started_at') or not run.get('ended_at'): pending.append('Run timestamps missing')
    outcome=run.get('outcome',{}); finish=outcome.get('type')
    if finish not in ('goal_complete','safe_blocked','incomplete'): errors.append('Invalid outcome type')
    if finish!='incomplete' and not outcome.get('next_action'): pending.append('Useful next action missing')
    if finish=='safe_blocked' and not outcome.get('blocker'): pending.append('Blocker missing')
    if blocked_beats and finish=='goal_complete': pending.append('Required behaviors blocked: '+', '.join(blocked_beats))
    if errors: status='invalid_evidence'
    elif critical or failed: status='failed'
    elif run.get('status')=='not_started': status='not_run'
    elif pending: status='incomplete_evidence'
    elif finish=='safe_blocked': status='safe_blocked'
    elif finish=='goal_complete': status='goal_complete'
    else: status='incomplete'
    return {'profile':p['id'],'variant':variant,'status':status,
        'goal_complete':status=='goal_complete','experience_accepted':False,
        'quality_scores':quality,'quality_unreviewed':quality_pending,
        'errors':errors,'pending':pending,'failed_assertions':failed,'critical_findings':critical,
        'observed_required_beats':len(required & reached),'required_beats':len(required),
        'user_actions':len(events),'soft_action_budget':p['budget']['user_actions_soft'],
        'budget_exceeded':len(events)>p['budget']['user_actions_soft'],
        'scope':'Evidence completeness and recorded review only. No automatic owner acceptance, clinical judgment, or app execution.'}


def main():
    cli=argparse.ArgumentParser(description=__doc__)
    sub=cli.add_subparsers(dest='command',required=True)
    sub.add_parser('validate')
    new=sub.add_parser('new-run'); new.add_argument('profile'); new.add_argument('--variant',choices=('direct','interrupted'),default='interrupted');new.add_argument('--output',required=True)
    score=sub.add_parser('score');score.add_argument('run');score.add_argument('--output')
    args=cli.parse_args()
    if args.command=='validate':
        errors=validate(suite()); result={'suite':suite()['suite'],'profiles':len(suite()['profiles']),'variants':24,'errors':errors,'status':'invalid' if errors else 'valid','journeys_run':0}
    elif args.command=='new-run':
        result=template(profile(args.profile),args.variant)
    else: result=grade(read(args.run),Path(args.run).resolve().parent)
    text=json.dumps(result,indent=2,ensure_ascii=False)+'\n'
    if getattr(args,'output',None):
        path=Path(args.output); path.parent.mkdir(parents=True,exist_ok=True)
        if args.command=='new-run' and path.exists(): cli.error('Refusing to overwrite an existing run')
        path.write_text(text)
    else: print(text,end='')
    return 1 if result.get('errors') or result.get('status') in ('invalid_evidence','failed') else 0


if __name__=='__main__': raise SystemExit(main())
