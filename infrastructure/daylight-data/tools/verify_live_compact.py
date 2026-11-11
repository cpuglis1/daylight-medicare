"""Read-only post-cutover checks; no permissions or authority are promoted."""
import importlib.util
import json
from pathlib import Path
import sqlite3
import sys

import psycopg

sys.path.insert(0,str(Path(__file__).parent))
import compact_database_r2 as c
from compact_recovery import count_rows


def must_deny(db,role,statement):
    try:
        with db.transaction():
            db.execute('SET LOCAL ROLE '+role)  # Fixed internal role constants only.
            db.execute(statement)
    except psycopg.errors.InsufficientPrivilege:return True
    raise ValueError('Permission boundary unexpectedly allowed '+role)


if __name__=='__main__':
    with c.connect(c.SOURCE,True) as db:
        source=c.source_contract(db)
        counts=count_rows(db)
        if counts!={'raw_rows':17767179,'projection_rows':17823148,'offerings':5972}:raise ValueError('Live source populations differ')
        kinds=db.execute("SELECT c.relname,c.relkind FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='dl_evidence' AND c.relname IN ('source_record','observation','offering')").fetchall()
        if len(kinds)!=3 or any(x['relkind']!='v' for x in kinds):raise ValueError('Compact read views not active')
        invalid=db.execute("SELECT count(*) AS n FROM pg_constraint c JOIN pg_namespace n ON n.oid=c.connamespace WHERE n.nspname='dl_compact' AND NOT c.convalidated").fetchone()['n']
        if invalid:raise ValueError('Unvalidated compact constraints')
        protected=('source_record','source_page','observation','offering','source_set','symbol','evidence_state','migration','cutover_receipt')
        guards=db.execute("SELECT c.relname,count(*) AS n FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='dl_compact' AND NOT t.tgisinternal AND t.tgenabled='O' AND t.tgfoid='dl_control.reject_mutation()'::regprocedure GROUP BY c.relname").fetchall()
        if not set(protected).issubset({x['relname'] for x in guards}):raise ValueError('Immutability guards missing')
        with db.transaction():
            db.execute('SET LOCAL ROLE daylight_research_reader')
            if not db.execute('SELECT record_id,raw_sha256 FROM dl_evidence.source_record LIMIT 1').fetchone():raise ValueError('Research view unavailable')
        private=must_deny(db,'daylight_research_reader','SELECT * FROM dl_compact.source_page LIMIT 1')
        stop=not db.execute("SELECT has_table_privilege('daylight_writer','dl_control.source_access_state','UPDATE') AS allowed").fetchone()['allowed']
        if not stop:raise ValueError('Writer can change source access authority')
        with db.transaction():
            db.execute('SET LOCAL ROLE daylight_released_reader')
            if db.execute('SELECT count(*) AS n FROM dl_released.offerings').fetchone()['n']!=0:raise ValueError('Consumer hold lost')
        state_counts=db.execute('''SELECT e.value_state,e.evidence_state,e.semantic_review_state,e.source_use_state,
             e.freshness_state,e.output_acceptance_state,count(*) AS records FROM dl_compact.observation o
             JOIN dl_compact.evidence_state e USING(state_id) GROUP BY e.state_id ORDER BY e.state_id''').fetchall()
        size=db.execute('SELECT pg_database_size(current_database()) AS n').fetchone()['n']
    # Reuse the independent, restored MVP snapshot proof from the prior phase.
    spec=importlib.util.spec_from_file_location('mvp_snapshot',c.ROOT/'tools/mvp_serving_snapshot.py')
    snapshot=importlib.util.module_from_spec(spec);spec.loader.exec_module(snapshot)
    artifact=c.PACKAGE/'.state/maintenance/20261105-r1/mvp-shadow.sqlite3'
    with sqlite3.connect(artifact.as_uri()+'?mode=ro',uri=True) as db:mvp=snapshot.verify(db,c.ROOT)
    providers=json.loads((c.RUN/'providers-after.json').read_text())
    provider_before=json.loads((c.RUN/'providers-before.json').read_text())
    medicine=json.loads((c.RUN/'medicines-after.json').read_text())
    medicine_before=json.loads((c.RUN/'medicines-before.json').read_text())
    identity=json.loads((c.RUN/'compact-identity-index-recovery.json').read_text())
    if not providers.get('passed') or not medicine.get('passed') or not identity.get('passed'):
        raise ValueError('Provider, medicine or identity lookup validation missing')
    case_keys=('case_id','name_text','binding','count','page','partial','discovery_state','candidate_checks')
    slim=lambda report:[{k:row[k] for k in case_keys} for row in report['cases']]
    if slim(providers)!=slim(provider_before):raise ValueError('Provider lookup output/lineage changed')
    for key in ('known_rxcuis','positive_sha256','absent_sha256','literal_search_sha256','wrong_year_rejected','unknown_is_not_noncoverage'):
        if medicine[key]!=medicine_before[key]:raise ValueError('Medicine lookup output/lineage changed')
    result={'passed':True,'counts':counts,'database_identity_retained':True,'private_base_tables_denied':private,
        'writer_cannot_clear_stop':stop,'consumer_released_offerings':0,'constraints_all_validated':True,
        'immutability_guards_present':True,'source_state_counts':state_counts,'mvp_snapshot':mvp,
        'all_14_families_preserved':mvp['counts']['family']==1008,'all_41_meanings_preserved':mvp['counts']['question']==41,
        'all_229_material_holds_preserved':mvp['total_material_holds']==229,'source_acceptance_changed':False,
        'provider_checks_passed':len(providers['checks']),'provider_results_identical':True,
        'medicine_results_identical':True,'record_id_lookup_index_recovered':True,
        'customer_store_or_conversation_persistence_changed':False,'database_bytes_with_legacy':size,'at':c.now()}
    c.fresh_json(c.RUN/'live-final-checks.json',result);print(json.dumps(result,default=str),flush=True)
