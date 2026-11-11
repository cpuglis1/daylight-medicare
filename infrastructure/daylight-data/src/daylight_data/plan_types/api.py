"""Private research API. No profile input, arbitrary SQL or consumer enable flag."""
from collections import Counter
from contextlib import asynccontextmanager
import base64
import hashlib
import hmac
import json
import os
import time
from typing import Literal

from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, ConfigDict, Field
from psycopg.conninfo import conninfo_to_dict
from psycopg_pool import ConnectionPool
from psycopg.rows import dict_row

from . import PlanTypeError
from .common import canonical, digest
from .store import Repository


class Query(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    reference_year: Literal[2026]
    county_fips: Literal['12021']
    intended_use: Literal['developer_source_inspection']
    kind: Literal['pdp_offering','pdp_field','pdp_county','pdp_restriction','medigap_variant',
        'medigap_benefit','medigap_condition','medigap_product_lead','medigap_listing',
        'medigap_insurer','medigap_illustration','medigap_monthly_rate','medigap_schedule',
        'medigap_filed_rate','research_item','source_document']
    entity_key: str | None=Field(default=None,min_length=1,max_length=512)
    on_date: str | None=Field(default=None,pattern=r'^2026-\d{2}-\d{2}$')
    page_size: int=Field(default=20,ge=1,le=100)
    cursor: str | None=Field(default=None,max_length=4096)


def create_app(repository, token, cursor_secret, *, lifespan=None):
    if min(len(token),len(cursor_secret))<32 or token==cursor_secret:
        raise PlanTypeError("SEPARATE_SERVICE_AND_CURSOR_SECRETS_REQUIRED")
    app=FastAPI(title='Daylight Collier plan-type research',version='1',lifespan=lifespan)
    bearer=HTTPBearer(auto_error=False)
    counters=Counter()
    def authorized(credentials: HTTPAuthorizationCredentials | None=Depends(bearer)):
        if credentials is None or len(credentials.credentials)>4096 or not hmac.compare_digest(credentials.credentials.encode(),token.encode()):
            raise HTTPException(401,'Service authentication required')
        return hashlib.sha256(token.encode()).hexdigest()

    @app.get('/health')
    def health():
        return {'status':'alive','consumer_release':'held'}

    @app.get('/internal/plan-types/ready',dependencies=[Depends(authorized)])
    def ready():
        try:
            return repository.status()
        except PlanTypeError as error:
            raise HTTPException(503,str(error))

    @app.get('/internal/plan-types/metrics',dependencies=[Depends(authorized)])
    def metrics():
        return dict(counters)

    @app.post('/v1/plan-types/query',dependencies=[Depends(authorized)])
    def consumer_held(query: Query):
        counters['consumer_held']+=1
        raise HTTPException(503,'CONSUMER_DISPLAY_DISABLED_PENDING_EXACT_DATA_APPROVAL')

    @app.post('/internal/research/plan-types/query')
    def query_sources(query: Query,principal=Depends(authorized)):
        request=query.model_dump(exclude={'cursor'},exclude_none=True)
        binding=digest([request,principal,repository.expected])
        after=''
        if query.cursor:
            try:
                encoded, signature=query.cursor.split('.')
                if not hmac.compare_digest(signature,hmac.new(cursor_secret.encode(),encoded.encode(),hashlib.sha256).hexdigest()):
                    raise ValueError()
                decoded=json.loads(base64.urlsafe_b64decode(encoded))
                if decoded['binding']!=binding:
                    raise ValueError()
                after=decoded['after']
            except (ValueError,KeyError,TypeError):
                raise HTTPException(400,'INVALID_OR_STALE_CURSOR')
        start=time.monotonic()
        try:
            result=repository.query(request,after=after)
        except PlanTypeError as error:
            counters['held_or_invalid']+=1
            raise HTTPException(503 if any(x in str(error) for x in ('BINDING','STOP','UNSELECTED')) else 422,str(error))
        counters['research_queries']+=1
        counters['query_milliseconds_total']+=round((time.monotonic()-start)*1000)
        result['next_cursor']=None
        if result['next_after']:
            encoded=base64.urlsafe_b64encode(canonical({'binding':binding,'after':result['next_after']}).encode()).decode()
            result['next_cursor']=encoded+'.'+hmac.new(cursor_secret.encode(),encoded.encode(),hashlib.sha256).hexdigest()
        result['verification_receipt']=digest({'request':request,'build_id':repository.expected,
            'items':[(r['item_id'],r['payload_sha256']) for r in result['records']],
            'consumer_release':'held'})
        return result
    return app


def build_app():
    """Explicit config only. Remote targets require certificate-verified TLS."""
    dsn=os.environ['DAYLIGHT_PLAN_TYPES_DATABASE_URL']
    target=os.environ['DAYLIGHT_PLAN_TYPES_EXPECTED_DATABASE']
    build=os.environ['DAYLIGHT_PLAN_TYPES_BUILD_ID']
    info=conninfo_to_dict(dsn)
    if info.get('dbname')!=target or info.get('service') or info.get('hostaddr'):
        raise PlanTypeError('EXPLICIT_DATABASE_TARGET_REQUIRED')
    if not info.get('host','').startswith('/') and info.get('sslmode')!='verify-full':
        raise PlanTypeError('REMOTE_TLS_VERIFY_FULL_REQUIRED')
    pool=ConnectionPool(dsn,min_size=1,max_size=4,open=False,timeout=5,
        kwargs={'autocommit':True,'row_factory':dict_row,
                'connect_timeout':5,'options':'-c default_transaction_read_only=on -c statement_timeout=5000'})
    @asynccontextmanager
    async def lifespan(app):
        pool.open(wait=True,timeout=5)
        try:
            with pool.connection() as connection:
                if connection.info.server_version//10000 not in {17,18} or connection.execute('SELECT current_database()').fetchone()['current_database']!=target:
                    raise PlanTypeError('DATABASE_TARGET_MISMATCH')
            yield
        finally:
            pool.close()
    return create_app(Repository(pool.connection,build),os.environ['DAYLIGHT_PLAN_TYPES_SERVICE_TOKEN'],
                      os.environ['DAYLIGHT_PLAN_TYPES_CURSOR_SECRET'],lifespan=lifespan)
