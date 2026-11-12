"""Explicitly bounded L03 published-reference candidate, separate from apps.

Unknown facts cannot be accepted into existence. An actual review can approve
only the exact entries and conservative dispositions pinned to this revision.
"""
from __future__ import annotations
import datetime,json,pathlib
from l03_close_reference import verify as verify_r3
from l03_close_sources import DATA,sha

REPO=pathlib.Path(__file__).resolve().parents[2]
ROOT=DATA/'bounded-reference-r4'
REGISTRY=REPO/'cms-slice/data-sources/l03-published-reference-review.json'
R3_PIN='eafca0abbfa8cea2faec50f2de87ed33ea4669e6c684a9167698b7f66adf78cb'
LOADED_SHA=sha(pathlib.Path(__file__).read_bytes())
REQUIRED_ACKS={
 'qualified_for_this_published_reference_review':True,
 'review_independent_of_sales_incentives':True,
 'conditions_and_units_reviewed':True,
 'source_holds_remain_unresolved':True,
 'all_25_restricted_offerings_remain_visible':True,
 'no_comprehensive_benefits_or_market_claim':True,
 'no_personal_applicability_or_recommendations':True,
 'no_UI_or_deployment_approval':True,
}
class ReferenceHeld(ValueError):pass
class ReferenceError(ValueError):pass
def read(p):return json.loads(pathlib.Path(p).read_text())
def utc(s):
    d=datetime.datetime.fromisoformat(s)
    if d.tzinfo is None:raise ReferenceHeld('Review time needs timezone')
    return d.astimezone(datetime.timezone.utc)
def verify(root=ROOT):
    root=pathlib.Path(root);verify_r3(expected_manifest_sha256=R3_PIN)
    try:
        m=read(root/'manifest.json')
        if m['parent_r3_manifest_sha256']!=R3_PIN or m['schema']!='l03-bounded-manifest/1':raise ReferenceHeld('Wrong parent or schema')
        required={'scope.json','entries.json','held-claims.json','offering-status.json','dispositions.json','validation.json','review-packet.json'}
        if not required <= set(m['files_sha256']):raise ReferenceHeld('Incomplete candidate')
        for rel,h in m['files_sha256'].items():
            p=(root/rel).resolve()
            if not p.is_relative_to(root.resolve())or sha(p.read_bytes())!=h:raise ReferenceHeld('Reference bytes changed: '+rel)
        for rel,h in m['code_sha256'].items():
            p=(REPO/rel).resolve()
            if not p.is_relative_to(REPO)or sha(p.read_bytes())!=h:raise ReferenceHeld('Reference code changed: '+rel)
        if m['code_sha256']['cms-slice/scripts/l03_scoped_reference.py']!=LOADED_SHA:raise ReferenceHeld('Loaded code differs; reload needed')
        if read(root/'validation.json')['passed']is not True:raise ReferenceHeld('Validation incomplete')
        return m
    except ReferenceHeld:raise
    except (OSError,ValueError,KeyError,TypeError)as e:raise ReferenceHeld('Reference unavailable/malformed')from e
def require_review(root=ROOT,registry=REGISTRY,now=None):
    m=verify(root);current=now or datetime.datetime.now(datetime.timezone.utc)
    try:
        r=read(registry);ids=sorted(x['id']for x in read(pathlib.Path(root)/'entries.json'));ds=read(pathlib.Path(root)/'dispositions.json')
        if (r['schema']!='l03-bounded-review/1'or r['decision']!='accepted'or r['revoked']is not False or r['package_id']!=m['package_id']or r['manifest_sha256']!=sha((pathlib.Path(root)/'manifest.json').read_bytes())):raise ReferenceHeld('Exact-scope L03 review pending, changed or revoked')
        if r['accepted_entry_ids']!=ids:raise ReferenceHeld('Exact entry allowlist not accepted')
        expected={d['id']:sha(json.dumps(d,sort_keys=True,separators=(',',':')).encode())for d in ds}
        if r['accepted_dispositions']!=expected:raise ReferenceHeld('Exact six dispositions not accepted')
        if r['acknowledgements']!=REQUIRED_ACKS:raise ReferenceHeld('Review scope acknowledgements incomplete')
        if not r['reviewer_name'].strip()or not r['reviewer_role'].strip()or not r['receipt'].strip():raise ReferenceHeld('Genuine named review receipt required')
        if utc(r['reviewed_at_utc'])>current:raise ReferenceHeld('Review time is in future')
        return m
    except ReferenceHeld:raise
    except (OSError,ValueError,TypeError,KeyError,AttributeError)as e:raise ReferenceHeld('Genuine L03 review receipt missing or malformed')from e
def lookup(request,*,research=False,root=ROOT,registry=REGISTRY,now=None):
    if type(request)is not dict or set(request)-{'year','offering_id','entry_ids'}:raise ReferenceError('Only year, exact offering and optional entry IDs are permitted')
    if type(request.get('year'))is not int or request['year']!=2026:raise ReferenceError('Exact reference year 2026 required')
    m=verify(root)if research else require_review(root,registry,now)
    all_entries=read(pathlib.Path(root)/'entries.json');entries=all_entries;plans=read(pathlib.Path(root)/'offering-status.json')
    plan=None
    if 'offering_id'in request:
        plan=next((p for p in plans if p['offering_id']==request['offering_id']),None)
        if plan is None:raise ReferenceError('Unknown exact offering identity')
        entries=[e for e in entries if e['offering_id']==request['offering_id']]
    if 'entry_ids'in request:
        ids=request['entry_ids']
        if type(ids)is not list or not ids or not all(type(x)is str for x in ids)or len(ids)!=len(set(ids))or not set(ids)<={e['id']for e in entries}:raise ReferenceError('Held, unknown, wrong-plan or duplicate entry ID')
        entries=[e for e in entries if e['id']in ids]
    holds=read(pathlib.Path(root)/'held-claims.json')
    if plan is not None:holds=[h for h in holds if h['offering_id']==plan['offering_id']]
    if not research:
        holds=[{k:h[k]for k in ['issue_id','offering_id','category_code','remaining_gap_id','carrier_evidence_ids']}|{'value':None,'state':'unknown_held'}for h in holds]
        entries=[{**e,'CMS_source_fields':[{'source':s['source']}for s in e['CMS_source_fields']]}if e['kind']=='reconciliation_note'else e for e in entries]
    selected={e['id']for e in entries};selected_plans={e['offering_id']for e in entries}
    # A day-band amount cannot be detached from its endpoints and other accepted
    # source context by requesting a single scalar. Never import held facts here.
    related=[e for e in all_entries if e['offering_id']in selected_plans and e['id']not in selected and e['kind']!='reconciliation_note']
    return {'package_id':m['package_id'],'mode':'research_pending_review'if research else 'accepted_bounded_published_reference','entries':entries,'related_reference_entries':related,'offering':plan,'scope':read(pathlib.Path(root)/'scope.json'),'holds':holds,'accepted_for_reference':not research,'comprehensive':False,'personal_applicability':False,'personal_total':False,'recommendations':False,'app_deployed':False}
