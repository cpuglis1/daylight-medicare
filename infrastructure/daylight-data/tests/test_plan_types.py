"""D96 tests use fictional evidence and isolated PostgreSQL, never guest stores."""
from copy import deepcopy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import uuid

import pytest

from daylight_data.plan_types import SCOPE, PlanTypeError
from daylight_data.plan_types.common import digest, file_sha, rate_holds
from daylight_data.plan_types.prepare import prepare, normalize, stream_items, verify_bundle
from daylight_data.plan_types.authority import validate_review, authority_holds


@pytest.fixture
def prepared(tmp_path):
    sources=[]
    def source(name,role,data,**extra):
        path=tmp_path/name
        path.write_text(json.dumps(data))
        sources.append({'path':name,'sha256':file_sha(path),'format':'array' if isinstance(data,list) else 'object',
                        'role':role,**extra})
    source('pdp.json','pdp',[{'offering_id':'2026:S9000:001:000','region':'11','fields':{
        'basic':{'value':-100,'value_encoding':'integer_cents','unit':'USD/month','basis':'basic','state':'published'},
        'supplemental':{'value':100,'value_encoding':'integer_cents','unit':'USD/month','basis':'supplemental','state':'published'},
        'total':{'value':0,'value_encoding':'integer_cents','unit':'USD/month','basis':'standard','state':'published'},
        'conditional':{'value':None,'value_encoding':'literal','unit':None,'basis':'conditional','state':'not_applicable'}}}])
    source('county.json','pdp_county',[{'fips':'12021','region':'11'}])
    source('benefits.json','document',{'year':2026,'plans':[{'variant':'G','letter':'G','high_deductible':False}],
        'cells':[{'variant':'G','benefit':'hospital','condition_ids':['c1'],'included':True}],
        'conditions':[{'id':'c1','meaning':'Fictional qualification'}]},
        children={'plans':'medigap_variant','cells':'medigap_benefit','conditions':'medigap_condition'})
    source('products.json','medigap_product_lead',[{'id':'fictional-lead','variant':'G','company_name_raw':'Fictional Carrier',
        'naic':'99999','source_group_type':'Individual Standard','select':False,'listing_ids':['listing']}])
    source('monthly.json','medigap_monthly_rate',[{'variant':'G','county_fips':'12021','rating_area':'Area 2',
        'premium_cents':12345,'payment_basis':'automatic_payment','age_band_raw':'65','personal_quote':False}])
    schedules=[];rates=[]
    for name,status,amount,start,end in [('current','APPROVED',123400,'2026-01-01','2026-12-31'),
       ('old','REPLACED',100000,'2025-01-01','2025-12-31'),('zero','APPROVED',0,None,None)]:
        schedules.append({'id':name,'fields':{'Form Number':'FICTION-G','Region':'Area 2','Issuing Carrier':'Fictional Carrier'},
            'status':status,'rate_effective_from':start,'rate_effective_through':end})
        rates.append({'id':'rate-'+name,'schedule_id':name,'source_status':status,'annual_premium_cents':amount,
            'rate_effective_from':start,'rate_effective_through':end})
    source('schedules.json','medigap_schedule',schedules)
    source('rates.json','medigap_filed_rate',rates)
    selection={'scope':SCOPE,'consumer_release':'held','parents':[],'sources':sources,'fixture_label':tmp_path.name,
        'source_policy':{'acquisition':'offline_only','source_use':'synthetic_fixture'},
        'review_due':{'L04':'2026-11-24T00:00:00+00:00','L10':'2026-11-28T00:00:00+00:00'}}
    config=tmp_path/'selection.json';config.write_text(json.dumps(selection))
    output=tmp_path/'bundle'
    manifest=prepare(tmp_path,config,output)
    return tmp_path,config,output,manifest


def test_preparation_accounts_for_qualifications_and_preserves_money(prepared):
    _,_,bundle,m=prepared
    rows=[r for s in m['sources'] for r in stream_items(bundle,s)]
    money={r['entity_key']:r.get('amount_cents') for r in rows if r['kind']=='pdp_field'}
    assert money['2026:S9000:001:000:basic']==-100
    assert money['2026:S9000:001:000:total']==0
    assert money['2026:S9000:001:000:conditional'] is None
    assert m['counts']['medigap_condition']==1 and m['counts']['medigap_benefit']==1
    monthly=next(r for r in rows if r['kind']=='medigap_monthly_rate')
    assert monthly['amount_cents']==12345
    assert 'automatic_payment_precision_and_conditions_unresolved' in monthly['holds']
    assert verify_bundle(bundle)==m


def test_changed_input_and_existing_output_are_rejected(prepared):
    root,config,bundle,_=prepared
    with pytest.raises(FileExistsError):prepare(root,config,bundle)
    (root/'pdp.json').write_text('[]')
    with pytest.raises(PlanTypeError,match='HASH'):prepare(root,config,root/'new')
    assert not (root/'new').exists()


def test_changed_bundle_code_or_scope_cannot_load(prepared):
    _,_,bundle,m=prepared
    stream=bundle/m['sources'][0]['stream'];stream.write_bytes(b'changed bytes')
    with pytest.raises(PlanTypeError,match='STREAM_CHANGED'):verify_bundle(bundle)
    m['scope']['reference_year']=2027
    (bundle/'manifest.json').write_text(json.dumps(m))
    with pytest.raises(PlanTypeError,match='BINDING'):verify_bundle(bundle)


def test_prepared_bundle_is_readable_without_original_source_paths(prepared):
    root,_,bundle,m=prepared
    for spec in m['sources']:
        (root/spec['path']).rename(root/(spec['path']+'.unavailable'))
    assert verify_bundle(bundle)['build_id']==m['build_id']
    assert sum(1 for s in m['sources'] for _ in stream_items(bundle,s))==sum(m['counts'].values())


@pytest.mark.parametrize('value',[True,1.5,'100'])
def test_money_requires_exact_integer_cents(value):
    with pytest.raises(PlanTypeError,match='INTEGER_CENTS'):
        list(normalize({'source_id':'fixture'},'/0','pdp',{'offering_id':'2026:S9000:001:000','region':'11',
            'fields':{'premium':{'value_encoding':'integer_cents','value':value,'state':'published'}}}))


def test_replaced_zero_unknown_period_and_wrong_year_never_become_rates():
    row={'kind':'medigap_filed_rate','amount_cents':0,'source_status':'REPLACED',
         'effective_from':None,'effective_through':None}
    assert set(rate_holds(row))=={'source_zero_meaning_unresolved','unapproved_or_replaced_source','approved_rate_period_unresolved'}
    with pytest.raises(PlanTypeError):rate_holds(row,'2027-01-01')


def review_fixture(manifest,gate='source_use'):
    receipt={'schema':'daylight-plan-type-review/1','build_id':manifest['build_id'],'scope':SCOPE,
        'code_sha256':digest(manifest['code']),'source_bindings_sha256':digest(manifest['sources']),
        'capability':'pdp_reference','gate':gate,'decision':'accepted','consumer_release_enabled':False,
        'reviewer':{'actor':'fictional-reviewer','qualified_for_scope':True,'independent_of_sales':True},
        'reviewed_at_utc':'2026-11-06T00:00:00+00:00','expires_at_utc':'2026-11-23T00:00:00+00:00',
        'dispositions':['Fictional published-reference fixture only']}
    trust={'fictional-reviewer':{'gates':['source_use','method','output'],'capabilities':['pdp_reference']}}
    return receipt,trust


def test_review_replay_binds_source_code_scope_trusted_actor_and_time(prepared):
    m=prepared[3];now=datetime(2026,11,6,12,tzinfo=timezone.utc)
    receipt,trust=review_fixture(m)
    assert validate_review(receipt,m,trust,now=now)==receipt
    for field,value in [('build_id','f'*64),('code_sha256','f'*64),('decision','publish'),('consumer_release_enabled',True)]:
        changed={**receipt,field:value}
        with pytest.raises(PlanTypeError):validate_review(changed,m,trust,now=now)
    with pytest.raises(PlanTypeError):validate_review(receipt,m,{},now=now)
    with pytest.raises(PlanTypeError):validate_review(receipt,m,trust,now=datetime(2026,11,24,tzinfo=timezone.utc))
    events=[]
    for n,gate in enumerate(('source_use','method','output')):
        r,_=review_fixture(m,gate)
        events.append({'event_id':n,'build_id':m['build_id'],'capability':'pdp_reference','gate':gate,
            'decision':'accepted','expires_at':r['expires_at_utc'],'original_authority':{'original_replayed':True,'receipt':r}})
    assert authority_holds(m,'pdp_reference',events,now=now)==['CONSUMER_DISPLAY_DISABLED_PENDING_DATA_APPROVAL']
    events.append({**events[0],'event_id':10,'decision':'revoked'})
    assert 'SOURCE_USE_APPROVAL_REQUIRED' in authority_holds(m,'pdp_reference',events,now=now)


@pytest.fixture(scope='module')
def database():
    dsn=os.environ.get('DAYLIGHT_DATA_TEST_DSN')
    if not dsn:pytest.skip('Explicit local test database DSN required')
    from psycopg import sql
    from psycopg.conninfo import conninfo_to_dict,make_conninfo
    from daylight_data.plan_types.store import connect,install
    info=conninfo_to_dict(dsn)
    if not info.get('dbname','').endswith('_test') or not info.get('host','').startswith('/'):
        raise RuntimeError('Only explicitly selected local test targets allowed')
    name='daylight_plan_'+uuid.uuid4().hex+'_test'
    with connect(dsn) as admin:
        admin.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
        target=make_conninfo(dsn,dbname=name)
        try:
            with connect(target) as c:install(c)
            yield target
        finally:
            admin.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(name)))


@pytest.fixture
def loaded(database,prepared):
    from daylight_data.plan_types.store import connect,load,select_research,Repository
    bundle,m=prepared[2:]
    with connect(database) as c:
        result=load(c,bundle)
        assert result['counts']==m['counts']
        select_research(c,m['build_id'],'Fictional test only')
    return database,Repository(lambda:connect(database,readonly=True),m['build_id']),prepared


def request(kind,**extra):
    return {'reference_year':2026,'county_fips':'12021','intended_use':'developer_source_inspection','kind':kind,**extra}


def test_postgres_load_resume_and_pdp_geography_join(loaded):
    from daylight_data.plan_types.store import connect,load
    dsn,repo,prepared=loaded
    with connect(dsn) as c:again=load(c,prepared[2])
    assert again['counts']==prepared[3]['counts']
    rows=repo.query(request('pdp_offering'))['records']
    assert len(rows)==1 and rows[0]['cms_offering_id']=='2026:S9000:001:000'
    assert len(repo.query(request('pdp_field'))['records'])==4
    assert repo.query(request('pdp_offering'))['consumer_release']=='held'


def test_partial_source_rolls_back_and_exact_resume_finishes(database,prepared,monkeypatch):
    import daylight_data.plan_types.store as store
    original=store.stream_items
    bundle,m=prepared[2:]
    def interrupted(path,source):
        for n,row in enumerate(original(path,source)):
            if source['path']=='benefits.json' and n==1:
                raise RuntimeError('Fictional interrupted source')
            yield row
    monkeypatch.setattr(store,'stream_items',interrupted)
    with store.connect(database) as c:
        with pytest.raises(RuntimeError,match='interrupted'):store.load(c,bundle)
        assert c.execute('SELECT count(*) AS n FROM dl_plan_types.completion WHERE build_id=%s',(m['build_id'],)).fetchone()['n']==0
        assert c.execute('SELECT count(*) AS n FROM dl_plan_types.checkpoint WHERE build_id=%s',(m['build_id'],)).fetchone()['n']==2
        assert c.execute("SELECT count(*) AS n FROM dl_plan_types.item WHERE build_id=%s AND kind='medigap_benefit'",(m['build_id'],)).fetchone()['n']==0
        monkeypatch.setattr(store,'stream_items',original)
        assert store.load(c,bundle)['counts']==m['counts']


def test_incomplete_build_cannot_be_selected_or_marked_complete(database,prepared):
    import psycopg
    from psycopg.types.json import Jsonb
    from daylight_data.plan_types.store import connect,select_research
    m=prepared[3]
    with connect(database) as c:
        c.execute('INSERT INTO dl_plan_types.build(build_id,manifest) VALUES(%s,%s)',(m['build_id'],Jsonb(m)))
        with pytest.raises(psycopg.Error,match='incomplete'):
            with c.transaction():c.execute('INSERT INTO dl_plan_types.completion(build_id,counts) VALUES(%s,%s)',(m['build_id'],Jsonb(m['counts'])))
        with pytest.raises(psycopg.errors.ForeignKeyViolation):select_research(c,m['build_id'],'Fictional incomplete')


def test_postgres_rate_lookup_keeps_source_grid_and_personal_scope_separate(loaded):
    _,repo,_=loaded
    current=repo.query(request('medigap_filed_rate',entity_key='rate-current',on_date='2026-02-01'))['records'][0]
    assert current['supported_rate_cents']==123400 and not current['personal_quote']
    assert current['county_fips'] is None and current['schedule']['policy_form']=='FICTION-G'
    old=repo.query(request('medigap_filed_rate',entity_key='rate-old',on_date='2026-02-01'))['records'][0]
    assert old['supported_rate_cents'] is None and 'outside_sourced_rate_period' in old['holds']
    zero=repo.query(request('medigap_filed_rate',entity_key='rate-zero'))['records'][0]
    assert zero['amount_cents']==0 and zero['supported_rate_cents'] is None
    for changes in ({'county_fips':'12001'},{'reference_year':2027},{'commission':100},{'profile':{}},{'page_size':True}):
        with pytest.raises(PlanTypeError):repo.query({**request('pdp_offering'),**changes})
    with pytest.raises(PlanTypeError,match='EXACT_RATE_ID'):repo.query(request('medigap_filed_rate'))


def test_postgres_privileges_immutability_and_no_forged_actor(loaded):
    import psycopg
    from daylight_data.plan_types.store import connect
    dsn,_,prepared=loaded;build=prepared[3]['build_id']
    with connect(dsn) as c:
        for role,statement in [
            ('daylight_plan_research_reader','INSERT INTO dl_plan_types.selection_event(build_id,reason) VALUES(%s,\'forged\')'),
            ('daylight_plan_loader','INSERT INTO dl_plan_types.review_event(build_id,capability,gate,decision,receipt_sha256,original_authority,expires_at) VALUES(%s,\'pdp_reference\',\'output\',\'accepted\',repeat(\'a\',64),\'{}\',now()+interval \'1 day\')'),
            ('daylight_plan_publisher','INSERT INTO dl_plan_types.selection_event(build_id,reason,actor) VALUES(%s,\'forged\',\'other\')')]:
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                with c.transaction():
                    c.execute('SET LOCAL ROLE '+role);c.execute(statement,(build,))
        with pytest.raises(psycopg.Error,match='immutable'):
            with c.transaction():c.execute('UPDATE dl_plan_types.build SET manifest=manifest WHERE build_id=%s',(build,))
        with pytest.raises(psycopg.Error,match='sealed'):
            with c.transaction():
                c.execute('INSERT INTO dl_plan_types.source(build_id,source_id,source_path,artifact_sha256,metadata) VALUES(%s,\'extra\',\'extra\',repeat(\'a\',64),\'{}\')',(build,))


def test_authenticated_api_rejects_personal_inputs_cursor_tamper_and_consumer_use(loaded):
    from fastapi.testclient import TestClient
    from daylight_data.plan_types.api import create_app
    _,repo,_=loaded
    token='fictional-test-token-'+'a'*32;secret='fictional-cursor-secret-'+'b'*32
    headers={'Authorization':'Bearer '+token}
    with TestClient(create_app(repo,token,secret)) as client:
        q=request('pdp_field',page_size=1)
        assert client.post('/internal/research/plan-types/query',json=q).status_code==401
        first=client.post('/internal/research/plan-types/query',json=q,headers=headers)
        assert first.status_code==200 and first.json()['next_cursor']
        cursor=first.json()['next_cursor']
        second=client.post('/internal/research/plan-types/query',json={**q,'cursor':cursor},headers=headers)
        assert second.status_code==200 and first.json()['records']!=second.json()['records']
        for changes in ({'page_size':2},{'entity_key':'other'},{'cursor':cursor+'a'}):
            assert client.post('/internal/research/plan-types/query',json={**q,'cursor':cursor,**changes},headers=headers).status_code==400
        assert client.post('/internal/research/plan-types/query',json={**q,'profile':{'name':'Fictional'}},headers=headers).status_code==422
        assert client.post('/v1/plan-types/query',json=q,headers=headers).status_code==503
        assert client.get('/internal/plan-types/ready',headers=headers).json()['consumer_release']=='held'


def test_stop_invalidates_existing_research_and_selected_release(loaded):
    from daylight_data.plan_types.store import connect,select_research
    dsn,repo,prepared=loaded;build=prepared[3]['build_id']
    with connect(dsn) as c:c.execute('INSERT INTO dl_plan_types.stop_event(build_id,reason) VALUES(%s,\'Fictional STOP\')',(build,))
    with pytest.raises(PlanTypeError,match='SOURCE_STOP'):repo.query(request('pdp_offering'))
    with connect(dsn) as c:
        with pytest.raises(PlanTypeError,match='SOURCE_STOP'):select_research(c,build,'retry')


def test_source_stop_follows_same_source_into_new_build(database,prepared):
    from daylight_data.plan_types.store import connect,load,select_research,Repository
    root,config,bundle,first=prepared
    changed=json.loads(config.read_text());changed['fixture_label']+='-new-build'
    config.write_text(json.dumps(changed))
    second_bundle=root/'second-bundle'
    second=prepare(root,config,second_bundle)
    with connect(database) as c:
        load(c,bundle);load(c,second_bundle)
        select_research(c,second['build_id'],'Fictional later build')
        c.execute('INSERT INTO dl_plan_types.stop_event(build_id,source_id,reason) VALUES(%s,%s,\'Fictional source STOP\')',
                  (first['build_id'],first['sources'][0]['source_id']))
        with pytest.raises(PlanTypeError,match='SOURCE_STOP'):select_research(c,second['build_id'],'retry in new build')
    repo=Repository(lambda:connect(database,readonly=True),second['build_id'])
    with pytest.raises(PlanTypeError,match='SOURCE_STOP'):repo.query(request('pdp_offering'))
