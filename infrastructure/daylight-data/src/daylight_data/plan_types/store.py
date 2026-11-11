"""Additive PostgreSQL load and bounded research reads. No legacy migrations."""
from collections import Counter
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import time

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from . import SCOPE, PlanTypeError
from .common import canonical, code_binding, digest, file_sha, public_research_row, runtime_binding
from .prepare import stream_items, verify_bundle

SCHEMA = Path(__file__).with_name("schema.sql")
COLUMNS = ("item_id","kind","entity_key","source_pointer","payload_sha256","payload",
           "cms_offering_id","county_fips","region","variant","company_name","naic",
           "policy_form","rating_area","schedule_key","source_status","effective_from",
           "effective_through","amount_cents","unit","basis","value_state","holds","conditions")
KINDS = {"pdp_offering","pdp_field","pdp_county","pdp_restriction","medigap_variant",
         "medigap_benefit","medigap_condition","medigap_product_lead","medigap_listing",
         "medigap_insurer","medigap_illustration","medigap_monthly_rate","medigap_schedule",
         "medigap_filed_rate","research_item","source_document"}


def connect(dsn, *, readonly=False):
    return psycopg.connect(dsn, autocommit=True, connect_timeout=5, row_factory=dict_row,
        options="-c statement_timeout=30000 -c lock_timeout=1000 -c idle_in_transaction_session_timeout=60000"+
                (" -c default_transaction_read_only=on" if readonly else ""))


def install(connection):
    """Only create the new schema, or verify its exact retained SQL digest."""
    if connection.info.server_version // 10000 not in {17,18}:
        raise PlanTypeError("UNSUPPORTED_POSTGRES_MAJOR")
    with connection.transaction():
        connection.execute("SELECT pg_advisory_xact_lock(962026)")
        exists = connection.execute("SELECT to_regnamespace('dl_plan_types') AS schema").fetchone()["schema"]
        if exists:
            row = connection.execute("SELECT sha256 FROM dl_plan_types.schema_revision WHERE singleton").fetchone()
            if not row or row["sha256"] != file_sha(SCHEMA):
                raise PlanTypeError("SERVING_SCHEMA_REVISION_MISMATCH")
        else:
            connection.execute(SCHEMA.read_text())
            connection.execute("INSERT INTO dl_plan_types.schema_revision(sha256) VALUES(%s)",(file_sha(SCHEMA),))


def load(connection, bundle):
    manifest = verify_bundle(bundle)
    build = manifest["build_id"]
    started = time.monotonic()
    connection.execute("SELECT pg_advisory_lock(962027)")
    try:
        with connection.transaction():
            existing = connection.execute("SELECT manifest FROM dl_plan_types.build WHERE build_id=%s",(build,)).fetchone()
            if existing and existing["manifest"] != manifest:
                raise PlanTypeError("EXISTING_BUILD_BINDING_MISMATCH")
            if not existing:
                connection.execute("INSERT INTO dl_plan_types.build(build_id,manifest) VALUES(%s,%s)",(build,Jsonb(manifest)))
        for source in manifest["sources"]:
            with connection.transaction():
                done = connection.execute("SELECT * FROM dl_plan_types.checkpoint WHERE build_id=%s AND source_id=%s",
                                          (build,source["source_id"])).fetchone()
                if done:
                    actual = connection.execute("SELECT count(*) AS n FROM dl_plan_types.item WHERE build_id=%s AND source_id=%s",
                                                (build,source["source_id"])).fetchone()["n"]
                    if done["item_count"] != source["item_count"] or actual != done["item_count"] or done["stream_sha256"] != source["stream_sha256"]:
                        raise PlanTypeError("CHECKPOINT_ACCOUNTING_MISMATCH")
                    continue
                connection.execute("INSERT INTO dl_plan_types.source(build_id,source_id,source_path,artifact_sha256,metadata) VALUES(%s,%s,%s,%s,%s)",
                    (build,source["source_id"],source["path"],source["sha256"],Jsonb(source)))
                with connection.cursor().copy("COPY dl_plan_types.item(build_id,source_id,"+",".join(COLUMNS)+") FROM STDIN") as copy:
                    for item in stream_items(bundle,source):
                        values = [Jsonb(item[c],dumps=canonical) if c in {"payload","conditions"} else item.get(c) for c in COLUMNS]
                        copy.write_row([build,source["source_id"],*values])
                connection.execute("INSERT INTO dl_plan_types.checkpoint(build_id,source_id,item_count,stream_sha256) VALUES(%s,%s,%s,%s)",
                    (build,source["source_id"],source["item_count"],source["stream_sha256"]))
        counts = {r["kind"]:r["n"] for r in connection.execute(
            "SELECT kind,count(*) AS n FROM dl_plan_types.item WHERE build_id=%s GROUP BY kind",(build,))}
        if counts != manifest["counts"]:
            raise PlanTypeError("COMPLETE_BUILD_ACCOUNTING_MISMATCH")
        # Every filed cell must link to exactly one exact schedule; never prefix-match forms.
        links = connection.execute("""SELECT count(*) AS bad FROM dl_plan_types.item r
          WHERE r.build_id=%s AND r.kind='medigap_filed_rate' AND
          (SELECT count(*) FROM dl_plan_types.item s WHERE s.build_id=r.build_id
             AND s.kind='medigap_schedule' AND s.entity_key=r.schedule_key)<>1""",(build,)).fetchone()["bad"]
        if links:
            raise PlanTypeError("MISSING_OR_AMBIGUOUS_SCHEDULE_LINK")
        with connection.transaction():
            connection.execute("INSERT INTO dl_plan_types.completion(build_id,counts) VALUES(%s,%s) ON CONFLICT DO NOTHING",(build,Jsonb(counts)))
        return {"build_id":build,"counts":counts,"elapsed_seconds":time.monotonic()-started,"consumer_release":"held"}
    finally:
        connection.execute("SELECT pg_advisory_unlock(962027)")


def select_research(connection, build_id, reason):
    if not isinstance(reason,str) or not reason.strip():
        raise PlanTypeError("SELECTION_REASON_REQUIRED")
    with connection.transaction():
        connection.execute("SELECT pg_advisory_xact_lock(962028)")
        if connection.execute("""SELECT 1 FROM dl_plan_types.stop_event e WHERE e.build_id=%s
          OR e.source_id IN (SELECT source_id FROM dl_plan_types.source WHERE build_id=%s) LIMIT 1""",(build_id,build_id)).fetchone():
            raise PlanTypeError("SOURCE_STOP")
        connection.execute("INSERT INTO dl_plan_types.selection_event(build_id,reason) VALUES(%s,%s)",(build_id,reason))


class Repository:
    """Developer source inspection only; caller must hold the dedicated reader role."""
    def __init__(self, factory, expected_build_id, *, timeout_ms=5000):
        if not callable(factory) or not isinstance(expected_build_id,str) or len(expected_build_id)!=64 or not 1<=timeout_ms<=30000:
            raise PlanTypeError("INVALID_REPOSITORY_CONFIGURATION")
        self.factory, self.expected = factory, expected_build_id
        self.timeout_ms = timeout_ms

    @contextmanager
    def read(self):
        with self.factory() as connection, connection.transaction():
            connection.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            connection.execute("SET LOCAL ROLE daylight_plan_research_reader")
            connection.execute("SELECT set_config('statement_timeout',%s,true)",(str(self.timeout_ms),))
            row = connection.execute("SELECT build_id,manifest FROM dl_plan_types.active_research").fetchone()
            if not row or row["build_id"]!=self.expected:
                raise PlanTypeError("STALE_OR_UNSELECTED_BUILD")
            manifest = row["manifest"]
            if (digest({k:v for k,v in manifest.items() if k!='build_id'})!=self.expected
                    or manifest["scope"]!=SCOPE or manifest["code"]!=code_binding()
                    or manifest['runtime']!=runtime_binding()):
                raise PlanTypeError("RUNTIME_BINDING_MISMATCH")
            stops = connection.execute("""SELECT event_id,source_id,reason FROM dl_plan_types.stop_event e
              WHERE e.build_id=%s OR e.source_id IN
                (SELECT source_id FROM dl_plan_types.source WHERE build_id=%s) ORDER BY event_id""",
              (self.expected,self.expected)).fetchall()
            if stops:
                raise PlanTypeError("SOURCE_STOP")
            yield connection, manifest

    def query(self, request, *, after=""):
        allowed={"reference_year","county_fips","kind","entity_key","page_size","on_date","intended_use"}
        if (not isinstance(request,dict) or set(request)-allowed or request.get("reference_year")!=2026
                or type(request.get("reference_year")) is not int or request.get("county_fips")!='12021'
                or request.get("intended_use")!='developer_source_inspection' or request.get("kind") not in KINDS):
            raise PlanTypeError("UNSUPPORTED_RESEARCH_REQUEST")
        limit=request.get("page_size",20)
        if type(limit) is not int or not 1<=limit<=100 or not isinstance(after,str) or len(after)>64:
            raise PlanTypeError("INVALID_PAGE_BOUND")
        kind, key = request["kind"], request.get("entity_key")
        if key is not None and (not isinstance(key,str) or not 1<=len(key)<=512):
            raise PlanTypeError("INVALID_ENTITY_KEY")
        if kind=='medigap_filed_rate' and key is None:
            raise PlanTypeError("EXACT_RATE_ID_REQUIRED")
        if request.get("on_date") is not None:
            from .common import exact_date
            if kind!='medigap_filed_rate' or not exact_date(request["on_date"]).startswith('2026-'):
                raise PlanTypeError("UNSUPPORTED_RESEARCH_DATE")
        with self.read() as (connection,manifest):
            where = "i.build_id=%s AND i.kind=%s AND i.item_id>%s"
            params=[self.expected,kind,after]
            if key is not None:
                where += " AND i.entity_key=%s"; params.append(key)
            if kind.startswith('pdp_') and kind!='pdp_county':
                where += """ AND EXISTS(SELECT 1 FROM dl_plan_types.item c
                  JOIN dl_plan_types.item p ON p.build_id=c.build_id AND p.region=c.region
                  AND p.kind='pdp_offering' AND p.cms_offering_id=i.cms_offering_id
                  WHERE c.build_id=i.build_id AND c.kind='pdp_county' AND c.county_fips='12021')"""
            if kind=='pdp_county':
                where += " AND i.county_fips='12021'"
            rows=connection.execute("SELECT i.*,s.source_path,s.artifact_sha256 FROM dl_plan_types.item i JOIN dl_plan_types.source s USING(build_id,source_id) WHERE "+where+" ORDER BY i.item_id LIMIT %s",(*params,limit+1)).fetchall()
            if kind=='medigap_filed_rate':
                for row in rows:
                    schedules=connection.execute("SELECT payload,policy_form,rating_area,company_name FROM dl_plan_types.item WHERE build_id=%s AND kind='medigap_schedule' AND entity_key=%s LIMIT 2",(self.expected,row["schedule_key"])).fetchall()
                    if len(schedules)!=1:
                        raise PlanTypeError("MISSING_OR_AMBIGUOUS_SCHEDULE_LINK")
                    row["schedule"]=schedules[0]
            page=rows[:limit]
            now=datetime.now(timezone.utc).isoformat()
            return {"contract":"collier-plan-types/1","build_id":self.expected,"scope":dict(SCOPE),
                    "output_kind":"developer_source_inspection","consumer_release":"held",
                    "source_use_state":"original_source_policy_applies_not_newly_reviewed",
                    "personal_quote":False,"personal_recommendation_available":False,
                    "all_market_complete":False,
                    "county_meaning":("published_PDP_region_relationship" if kind.startswith('pdp_') else
                        "Collier_research_context_not_confirmed_product_or_rate_applicability"),
                    "source_policy":manifest["source_policy"],
                    "review_due":manifest["review_due"],
                    "source_review_due":now>=min(manifest["review_due"].values()),
                    "unresolved_checks":["SOURCE_USE_REVIEW_REQUIRED","METHOD_REVIEW_REQUIRED","EXACT_OUTPUT_APPROVAL_REQUIRED"],
                    "records":[public_research_row(r,request.get("on_date")) for r in page],
                    "next_after":page[-1]["item_id"] if len(rows)>limit else None}

    def status(self):
        from .authority import CAPABILITIES, authority_holds
        with self.read() as (connection,manifest):
            events=connection.execute('SELECT * FROM dl_plan_types.review_event WHERE build_id=%s ORDER BY event_id',(self.expected,)).fetchall()
            return {'build_id':self.expected,'scope':dict(SCOPE),'counts':manifest['counts'],
                'consumer_release':'held','review_events':len(events),
                'authority':{c:authority_holds(manifest,c,events) for c in sorted(CAPABILITIES)}}
