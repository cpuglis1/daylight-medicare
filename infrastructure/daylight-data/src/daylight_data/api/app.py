from __future__ import annotations
import base64
from decimal import Decimal
import hashlib
import hmac
import json
from typing import Annotated, Literal
from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field
from psycopg_pool import ConnectionPool
from daylight_data.database import read_transaction
from daylight_data.settings import Settings


class Query(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    benefit_year: Literal[2026]
    derivation_id: str=Field(pattern='^[0-9a-f]{64}$')
    entity_type: str=Field(pattern='^[a-z_]{1,64}$')
    offering_id: str | None=Field(default=None,pattern=r'^2026:[A-Z]\d{4}:\d{3}:\d{3}$')
    county_fips: str | None=Field(default=None,pattern=r'^12\d{3}$')
    page_size: int=Field(default=100,ge=1,le=100)
    cursor: str | None=Field(default=None,max_length=4096)


def _encode(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),default=str).encode()


def create_app(settings: Settings) -> FastAPI:
    if len(settings.service_token)<32 or len(settings.cursor_secret)<32:
        raise ValueError('Separate >=32-character service token and cursor secret are required')
    if settings.service_token==settings.cursor_secret:
        raise ValueError('Service token and cursor secret must differ')
    from contextlib import asynccontextmanager
    pool=ConnectionPool(settings.database_url,min_size=1,max_size=4,open=False,
                        kwargs={'autocommit':True,'connect_timeout':5},timeout=5)
    @asynccontextmanager
    async def lifespan(app):
        pool.open(wait=True,timeout=5)
        with pool.connection() as connection:
            if connection.info.server_version//10000 not in {17,18}:
                raise RuntimeError('Unsupported PostgreSQL major')
        try:
            yield
        finally:
            pool.close()
    app=FastAPI(title='Daylight private 2026 evidence preflight',version='0.1.0',lifespan=lifespan)
    bearer=HTTPBearer(auto_error=False)
    def authorized(credentials: HTTPAuthorizationCredentials | None=Depends(bearer)):
        if credentials is None or len(credentials.credentials)>4096 or not hmac.compare_digest(credentials.credentials.encode(),settings.service_token.encode()):
            raise HTTPException(401,'Service authentication required')
        return hashlib.sha256(credentials.credentials.encode()).hexdigest()

    @app.get('/health')
    def health():
        return {'service':'daylight-data','status':'alive','consumer_release':'held'}

    @app.get('/ready',dependencies=[Depends(authorized)])
    def ready():
        with pool.connection() as connection:
            connection.execute('SELECT 1')
        return {'database':'reachable','scope_year':2026,'new_acceptance':False}

    @app.post('/v1/offerings/query',dependencies=[Depends(authorized)])
    def consumer_held(query: Query):
        raise HTTPException(503,'EXACT_RELEASE_AND_ORIGINAL_AUTHORITY_REPLAY_REQUIRED')

    @app.post('/internal/evidence/query')
    def evidence(query: Query,principal=Depends(authorized)):
        scope=query.model_dump(exclude={'cursor'})
        request_hash=hashlib.sha256(_encode([scope,principal,'internal_research'])).hexdigest()
        last=''
        if query.cursor:
            try:
                payload,signature=query.cursor.split('.')
                expected=hmac.new(settings.cursor_secret.encode(),payload.encode(),hashlib.sha256).hexdigest()
                if not hmac.compare_digest(signature,expected):
                    raise ValueError()
                decoded=json.loads(base64.urlsafe_b64decode(payload))
                if decoded['request_hash']!=request_hash:
                    raise ValueError()
                last=decoded['last_id']
                if not isinstance(last,str) or len(last)>2048:
                    raise ValueError()
            except (ValueError,KeyError,TypeError):
                raise HTTPException(400,'Invalid or scope-mismatched cursor')
        with pool.connection() as connection,read_transaction(connection,settings.statement_timeout_ms):
            connection.execute('SET LOCAL ROLE daylight_research_reader')
            row=connection.execute("""SELECT s.layer_id,s.source_use_state FROM dl_control.derivation d JOIN dl_control.source_snapshot s USING(snapshot_id)
                                      WHERE d.derivation_id=%s""",(query.derivation_id,)).fetchone()
            if row is None:
                raise HTTPException(404,'Unknown exact derivation')
            if row[1] not in {'internal_research_permitted','synthetic_fixture'}:
                raise HTTPException(403,'SOURCE_USE_REVIEW_REQUIRED')
            rows=connection.execute("""SELECT entity_id,offering_id,county_fips,amount,amount_unit,amount_basis,amount_period,
              value_state,evidence_state,semantic_review_state,source_use_state,freshness_state,output_acceptance_state,
              conditions,fields,source_table,source_row_ordinal FROM dl_evidence.observation
              WHERE derivation_id=%s AND entity_type=%s AND (benefit_year IS NULL OR benefit_year=%s)
              AND (%s::text IS NULL OR offering_id=%s) AND (%s::text IS NULL OR county_fips=%s)
              AND entity_id>%s ORDER BY entity_id LIMIT %s""",(query.derivation_id,query.entity_type,query.benefit_year,
               query.offering_id,query.offering_id,query.county_fips,query.county_fips,last,query.page_size+1)).fetchall()
        names=['entity_id','offering_id','county_fips','amount','amount_unit','amount_basis','amount_period',
               'value_state','evidence_state','semantic_review_state','source_use_state','freshness_state','output_acceptance_state',
               'conditions','fields','source_table','source_row_ordinal']
        observations=[{k:(str(v) if isinstance(v,Decimal) else v) for k,v in zip(names,item)} for item in rows[:query.page_size]]
        cursor=None
        if len(rows)>query.page_size:
            payload=base64.urlsafe_b64encode(_encode({'request_hash':request_hash,'last_id':rows[query.page_size-1][0]})).decode()
            cursor=payload+'.'+hmac.new(settings.cursor_secret.encode(),payload.encode(),hashlib.sha256).hexdigest()
        return {'contract_version':'daylight-evidence/preflight-1','scope':{'benefit_year':2026},
                'derivation_id':query.derivation_id,'layer_id':row[0],'output_kind':'internal_source_research',
                'source_use_state':'original_source_policy_applies_not_newly_reviewed',
                'personal_recommendation_available':False,'observations':observations,'next_cursor':cursor,
                'consumer_release':'held','unresolved_checks':['ORIGINAL_AUTHORITY_REPLAY_REQUIRED']}
    return app


def build_app():
    return create_app(Settings.from_env())
