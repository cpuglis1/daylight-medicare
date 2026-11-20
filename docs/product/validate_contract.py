"""Validate the documentation contract only; never imports or changes the application."""
from pathlib import Path
import json,re,sys
ROOT=Path(__file__).resolve().parent
c=json.loads((ROOT/'flow-contract.json').read_text())
errors=[]
def check(ok,msg):
    if not ok: errors.append(msg)
ids=[n['id'] for n in c['nodes']]; by={n['id']:n for n in c['nodes']}
check(len(ids)==len(set(ids)), 'Duplicate node ID')
check([p['id'] for p in c['phases']]==['P1','P2','P3','P4'],'Stable phase IDs')
check([p['label'] for p in c['phases']]==['Your goal','Your situation','Your options','Your next step'],'Stable phase labels')
required={'id','phase','kind','purpose','question','why','options','reads','writes','picture','prerequisites','validation','agent','help_context','requirements','acceptance','wireframe','teaching_prerequisites','answer_effects'}
tokens=set(c['token_rules'])
def target_ok(t):
    return t in by or (t.startswith('@') and t[1:] in c['resolvers']) or (t.startswith('TOKEN:') and t[6:] in tokens)
for n in c['nodes']:
    check(required<=n.keys(),f'{n["id"]}: missing metadata {required-n.keys()}')
    check(n['phase'] in ['P1','P2','P3','P4','preserve'],f'{n["id"]}: phase')
    check(n['global_events']=='G1',f'{n["id"]}: no G1 contract')
    opts=[o['id'] for o in n['options']]
    check(bool(opts) and len(opts)==len(set(opts)),f'{n["id"]}: duplicate/empty options')
    for o in n['options']:check(bool(o['label']) and target_ok(o['next']),f'{n["id"]}/{o["id"]}: invalid target/label')
    check(n['id'] in c['wireframe_templates'],f'{n["id"]}: no wireframe')
for name,rules in c['resolvers'].items():
    check(rules[-1]['when']=='else',f'{name}: missing terminal else')
    for r in rules:check(target_ok(r['goto']),f'{name}: invalid target {r["goto"]}')
for lesson,dest in c['lesson_defaults'].items():
    check(lesson in by and by[lesson]['kind']=='lesson',f'{lesson}: invalid lesson default')
    check(target_ok(dest),f'{lesson}: invalid default destination')
for g in ['back','edit','help','explain','know','other','skip','cancel','error','conflict','scope_unavailable','privacy','new_goal','delete','resume']:check(g in c['global_events'],f'Missing global event {g}')
# All declared inventory nodes must have human-readable wireframe coverage.
w=(ROOT/'WIREFRAMES.md').read_text(); catalogue=(ROOT/'BRANCHING_NODES.md').read_text()
for n in c['nodes']:
    check(f'| {n["id"]} | {n["wireframe"]} |' in w,f'{n["id"]}: no wireframe row')
    check(f'### {n["id"]} ·' in catalogue,f'{n["id"]}: no inventory specification')
# Evaluate declared design DSL only, never Python eval and never product/insurance policy.
def condition(expr,ctx):
    if expr=='else':return True
    if expr in ctx:return bool(ctx[expr])
    if ' OR ' in expr:return any(condition(x,ctx) for x in expr.split(' OR '))
    if ' AND ' in expr:return all(condition(x,ctx) for x in expr.split(' AND '))
    m=re.fullmatch(r'([A-Za-z0-9_.]+)(?: IN (.+)|=(.+)|>(\d+))',expr)
    if not m:return False
    key,values,equal,greater=m.groups();v=ctx.get(key,'unanswered')
    if values is not None:return bool(set(v if isinstance(v,list) else [str(v)]) & set(values.split(',')))
    if greater is not None:return isinstance(v,(int,float)) and v>int(greater)
    expected={'true':True,'false':False}.get(equal,equal)
    return v==expected

def resolve(dest,ctx,current=None):
    seen=set()
    while dest.startswith('@'):
        name=dest[1:]
        if name in seen:raise AssertionError(f'Resolver cycle {seen} -> {name}')
        seen.add(name)
        dest=next(r['goto'] for r in c['resolvers'][name] if condition(r['when'],ctx))
    if dest.startswith('TOKEN:'):
        token=dest[6:]
        if token=='lessonDefault':return resolve(c['lesson_defaults'][current],ctx,current)
        return ctx.get('token.'+token,dest)
    return dest

# Boundary and exemplar decision assertions, separate from application tests.
cases=[
 ('learn entry','@start_route',{'goal':'learn'},'L00'),
 ('browse entry','@start_route',{'goal':'compare'},'O00'),
 ('review no recipient','@start_route',{'goal':'review'},'A02'),
 ('new personal','@personal_entry',{'recipient':'self','novice_requires_parts':True},'L00'),
 ('completed personal avoids loop','@personal_entry',{'recipient':'self','personalContextReady':True},'O03'),
 ('voluntary knowledge first storage','@after_knowledge',{'privacy.choice_not_recorded':True},'A05'),
 ('comfortable browse','@after_knowledge',{'goal':'compare'},'O00'),
 ('A/B coverage','@after_enrollment',{'goal':'review','enrollment':'ab'},'C03'),
 ('B-only distinct','@after_enrollment',{'goal':'review','enrollment':'b_only'},'C03'),
 ('enrollment unknown','@after_enrollment',{'goal':'learn','enrollment':'unknown'},'J00'),
 ('job goal','@after_enrollment',{'goal':'job','enrollment':'ab'},'J00'),
 ('keep coverage','@after_change',{'change':'keep'},'F00'),
 ('replace','@after_change',{'change':'replace'},'O00'),
 ('add','@after_change',{'change':'add'},'O00'),
 ('unknown review','@after_change',{'change':'unknown'},'N00'),
 ('job prepare','@after_transition',{'jobTask':'prepare'},'F00'),
 ('job undecided','@after_transition',{'jobTask':'unknown'},'F00'),
 ('job compare','@after_transition',{'jobTask':'compare'},'N00'),
 ('multiple priorities','@after_priorities',{'priorityCount':2},'N05'),
 ('doctor check','@after_priority_order',{'priority':['doctors']},'N06'),
 ('supplement timing return','@after_part_b',{'compareKind':'medigap'},'O11'),
 ('confirmed knowledge','@confirmed_return',{'proposal.context':'knowledge','privacy.choice_not_recorded':True},'A05'),
 ('unknown goal safe choice','@unknown_return',{'proposal.context':'goal','privacy.choice_not_recorded':True},'A05'),
 ('lesson queue','@after_lesson',{'lessonQueue':'remaining','token.nextLesson':'L03'},'L03'),
 ('lesson exact return','@after_lesson',{'lessonReturn':'set','token.lessonReturn':'C00'},'C00'),
]
for label,dest,ctx,expected in cases:
    try:check(resolve(dest,ctx)==expected,f'{label}: expected {expected}, got {resolve(dest,ctx)}')
    except Exception as exc:errors.append(f'{label}: {exc}')
# Default education path and all lesson branch targets are defined.
for lesson in c['lesson_defaults']:
    try:check(target_ok(resolve('@after_lesson',{},lesson)),f'{lesson}: invalid default resolution')
    except Exception as exc:errors.append(f'{lesson}: {exc}')
# File-only links inside this document package. Repo authority links checked at installation.
for f in ROOT.glob('*.md'):
    for raw in re.findall(r'\]\(([^)]+)\)',f.read_text()):
        target=raw.split('#')[0]
        if target and not re.match(r'https?://|mailto:|tel:',target):
            p=(f.parent/target)
            if '..' not in Path(target).parts:check(p.exists(),f'{f.name}: broken local link {target}')
if errors:
    print('\n'.join('ERROR '+e for e in errors));sys.exit(1)
print(f'PASS: {len(ids)} nodes, {sum(len(n["options"]) for n in c["nodes"])} option/system transitions, {len(c["resolvers"])} resolvers, {len(cases)} decision assertions, all node wireframes and local package links. Documentation consistency only; no app/insurance/security certification.')
