"""Complete named compound schedules and publish a reviewable frozen census.

Run after the source-blind decomposition builder. This stage preserves every
original unit, links compound CMS cost components to their complete cost
schedule, and exports canonical inventory entries plus all source lineage.
"""
from __future__ import annotations
import argparse,collections,gzip,hashlib,json,pathlib,re,shutil,sqlite3
from l03_inventory import DATA,REPO,packed,ident,load,dump,sha,rows,R7
from l03_semantic_inventory import ROOT,PACKAGE,PARENT
from l03_semantic_clauses import clean,page_context,detect_table_columns,sb_row_frames
from l03_pdf_geometry import pdf_words,bind_page_words


def require_unsealed(root):
    if (pathlib.Path(root)/'freeze.json').exists():
        raise ValueError('Sealed inventory is immutable; use a new revision/output directory')


def link_list_introducers(db,parent):
    """Bind inherited list meaning to exact source spans, not text alone."""
    old=sqlite3.connect(f'file:{parent}?mode=ro',uri=True)
    owners=dict(old.execute("select id,offering_id from source_unit where layer='carrier_passage'"))
    roles={};previous={}
    for oid,h,kind,page,text in old.execute('select offering_id,document_sha256,kind,pdf_page,text from carrier_view order by offering_id,document_sha256,kind,pdf_page'):
        key=(oid,h,kind);context=page_context(text,previous.get(key),kind);previous[key]=context
        roles[(*key,page)]=context['chapter_role']
    def scope(sid,atom):
        loc=atom['source_fragments'][0]['locator'];oid=owners[sid]
        return (oid,loc['document_sha256'],loc['kind'],roles[(oid,loc['document_sha256'],loc['kind'],loc['pdf_page'])],atom['source_column'])
    requests=[];needed=set()
    for cid,sid,p in db.execute("select id,source_id,payload from clause where json_extract(payload,'$.list_intro') is not null"):
        atom=json.loads(p)
        if not atom.get('required_unit_ids'):continue
        intro=atom['list_intro'];key=(*scope(sid,atom),intro['start'],intro['end'],clean(intro['quote']))
        needed.add(key);requests.append((cid,atom,key))
    targets={}
    for cid,sid,p in db.execute("select id,source_id,payload from clause where json_extract(payload,'$.parent_sentence') is not null"):
        atom=json.loads(p);key=(*scope(sid,atom),atom['parent_start'],atom['parent_end'],clean(atom['parent_sentence']))
        if key not in needed:continue
        refs=atom.get('parent_source_fragments',atom['source_fragments']);entry=targets.setdefault(key,{'refs':refs,'clause_ids':[],'unit_ids':set()})
        if entry['refs']!=refs:raise ValueError('Ambiguous list-introducer source spans')
        entry['clause_ids'].append(cid);entry['unit_ids'].update(atom.get('required_unit_ids',[]))
    missing=needed-set(targets)
    if missing:raise ValueError(f'{len(missing)} list introducers have no exact source parent')
    db.execute('create table if not exists list_intro_link(clause_id text primary key,payload text not null)')
    for cid,atom,key in requests:
        target=targets[key];refs=target['refs'];atom['list_intro_source_fragments']=refs;atom['list_intro_clause_ids']=sorted(target['clause_ids'])
        db.execute('update clause set payload=? where id=?',(packed(atom),cid))
        db.execute('insert or replace into list_intro_link values (?,?)',(cid,packed({'intro_clause_ids':atom['list_intro_clause_ids'],'source_fragments':refs,'quote':atom['list_intro']['quote']})))
        for uid in atom['required_unit_ids']:
            for sid in sorted({r['source_id']for r in refs}):
                obs=ident('OBS',sid,uid,'list_intro',cid)
                db.execute('insert or ignore into observation values (?,?,?,?,?,?)',(obs,uid,sid,'carrier_list_intro','required_inherited_list_context',packed({'member_clause_id':cid,'intro_clause_ids':atom['list_intro_clause_ids'],'quote':atom['list_intro']['quote'],'source_fragments':refs})))
                db.execute('insert or ignore into source_target values (?,?)',(sid,uid))
            for parent_uid in target['unit_ids']:
                if parent_uid!=uid:db.execute('insert or ignore into relationship values (?,?,?,?)',(parent_uid,uid,'explicit_list_introducer_qualifies_member',refs[0]['source_id']))
    db.execute('attach database ? as intro_parent',(str(parent),))
    db.execute("insert or ignore into lineage select b.obligation_id,o.unit_id from intro_parent.binding b join observation o on o.source_id=b.source_id where o.layer='carrier_list_intro'")
    db.execute("update root_disposition set disposition='semantic_units_enumerated',reason='Exact source statement/list-introducer evidence is linked to named semantic units; no factual acceptance inferred.' where exists(select 1 from lineage l where l.root_id=root_disposition.root_id)")
    db.commit();old.close()
    return {'list_member_clauses':len(requests),'exact_intro_source_parents':len(needed),'missing_or_ambiguous':0,'new_claims_or_conditions_created':0}


def complete_compound_costs(db):
    added=[];affected=set()
    for uid,oid,subject,predicate,ctx,payload in db.execute("select id,offering_id,subject,predicate,context,payload from semantic_unit where kind='condition'").fetchall():
        if predicate not in {'admission_waiver_and_copayment','admission_waiver_and_coinsurance','setting_specific_copayment'}:continue
        context=json.loads(ctx)
        signature={'offering_id':oid,'kind':'claim','subject':subject,'predicate':'member_cost_schedule','context':context}
        claim=ident('SEM',signature)
        before=db.total_changes
        db.execute('insert or ignore into semantic_unit values (?,?,?,?,?,?,?,?)',(claim,oid,'claim',subject,'member_cost_schedule',ctx,'evidence_reconciliation_pending',packed({'meaning':'Complete CMS member-cost schedule including setting/admission-qualified component; waiver/setting condition retained separately.','source_basis':'CMS_JSON','compound_condition_unit':uid})))
        if db.total_changes>before:added.append(claim)
        for sid,layer,p in db.execute('select source_id,layer,payload from observation where unit_id=?',(uid,)).fetchall():
            obs=ident('OBS',sid,claim,'whole')
            db.execute('insert or ignore into observation values (?,?,?,?,?,?)',(obs,claim,sid,layer,'required_semantic_observation',p))
            db.execute('insert or ignore into source_target values (?,?)',(sid,claim))
            db.execute('insert or ignore into lineage select root_id,? from lineage where unit_id=?',(claim,uid))
        first=db.execute('select source_id from observation where unit_id=? limit 1',(uid,)).fetchone()[0]
        db.execute('insert or ignore into relationship values (?,?,?,?)',(claim,uid,'cost_schedule_with_separate_admission_or_setting_condition',first))
        canonical=ident('CANONICAL',oid,'claim',subject,'member_cost_schedule',context)
        db.execute('insert or ignore into canonical_unit values (?,?)',(claim,canonical));affected.add(claim)
    for uid in affected:
        observations=db.execute('select source_id,layer,payload from observation where unit_id=?',(uid,)).fetchall()
        if len(observations)<2:continue
        db.execute('insert or replace into equivalence values (?,?,?,?)',(ident('EQ',uid),uid,'same_inventory_question_or_schedule; full_value_equivalence_held',packed({'observations':[{'source_id':sid,'layer':layer,'locator':json.loads(p).get('locator')}for sid,layer,p in observations],'amount_presence_used':False,'accepted_for_reference':False,'compound_schedule_completion':True})))
    db.commit()
    return {'new_cost_schedule_units':added,'affected_cost_schedules':len(affected),'original_condition_units_removed':0}


def retain_empty_amount_annotations(db):
    """A derived row with no raw amount is retained unknown, never a claim."""
    db.execute('create table if not exists retained_amount_annotation(source_id text primary key,offering_id text not null,payload text not null,disposition text not null)')
    records=[]
    for obs,uid,sid,p in db.execute("select id,unit_id,source_id,payload from observation where layer='cms_named_amount'").fetchall():
        item=json.loads(p)
        if item.get('raw')is not None and str(item['raw']).strip()!='':continue
        if db.execute('select count(*) from lineage where unit_id=?',(uid,)).fetchone()[0]:raise ValueError('Empty derived annotation unexpectedly owns a parent requirement')
        db.execute('insert or replace into retained_amount_annotation values (?,?,?,?)',(sid,item['offering_id'],p,'retained_empty_source_value_not_zero_or_No'))
        db.execute('delete from observation where id=?',(obs,));db.execute('delete from source_target where source_id=? and unit_id=?',(sid,uid))
        if db.execute('select count(*) from observation where unit_id=?',(uid,)).fetchone()[0]:raise ValueError('Empty annotation has other semantic evidence')
        db.execute('delete from canonical_unit where unit_id=?',(uid,));db.execute('delete from semantic_unit where id=?',(uid,))
        db.execute("update source_disposition set disposition='retained_empty_derived_annotation',rule='Original raw amount is blank/null; derived annotation does not create a published claim' where source_id=?",(sid,))
        records.append({'source_id':sid,'retired_unsealed_unit_id':uid,'source':item['source'],'reason':'Blank/null source; no zero/No or coverage inference.'})
    db.commit();return records


def refine_scalar_amount_roles(db):
    """Correct pure monetary fields routed through the generic JSON fallback.

    Amount fields are claims; their independent activation/application controls
    remain conditions. No source value or applicability is changed.
    """
    changes=[]
    for uid,oid,subject,predicate,context,payload in db.execute("select id,offering_id,subject,predicate,context,payload from semantic_unit where kind='condition'").fetchall():
        data=json.loads(payload);component=data.get('source_component','');leaf=component.rsplit('/',1)[-1]
        if data.get('source_basis')!='CMS_JSON'or not re.search(r'(?:Amt|Amount)$',leaf):continue
        if not re.search(r'deduct|copay|coin|premium|prm|moop|cost|benefit|coverage',leaf,re.I):continue
        data['classification_refinement']='Pure source-named monetary amount; separate activation/application predicates retained.'
        db.execute("update semantic_unit set kind='claim',payload=? where id=?",(packed(data),uid))
        canonical=ident('CANONICAL',oid,'claim',subject,predicate,json.loads(context))
        db.execute('update canonical_unit set canonical_id=? where unit_id=?',(canonical,uid))
        changes.append({'unit_id':uid,'before_kind':'condition','after_kind':'claim','source_field':component,'source_value_changed':False})
    db.commit();return changes


def reconcile_same_source_amounts(db):
    """A normalized annotation of the very same pinned field is not a new claim."""
    db.execute('create table if not exists source_identity_alias(alias_unit_id text primary key,target_unit_id text not null,pinned_source_id text not null,locator text not null,decision text not null)')
    def key(oid,src):return (oid,src.get('member'),src.get('member_sha256'),src.get('pointer'),src.get('record_ordinal'),src.get('field'))
    named=[];wanted=set()
    for uid,p in db.execute("select unit_id,payload from observation where layer='cms_named_amount'"):
        item=json.loads(p)
        if 'pointer'not in item['source']:continue
        k=key(item['offering_id'],item['source']);named.append((uid,k,item));wanted.add(k)
    native=collections.defaultdict(set)
    for uid,sid,oid,p in db.execute("select o.unit_id,o.source_id,u.offering_id,o.payload from observation o join semantic_unit u on u.id=o.unit_id where o.layer='cms_json' and u.kind='claim'"):
        item=json.loads(p);k=key(oid,item['locator'])
        if k in wanted:native[k].add((uid,sid))
    merged=[];held=[]
    for uid,k,item in named:
        targets=native.get(k,set());target_ids={u for u,_ in targets}
        if len(target_ids)!=1:
            held.append({'unit_id':uid,'source':item['source'],'decision':'No unique same-field financial question; preserve separately.'});continue
        target,sid=sorted(targets)[0]
        canonical=db.execute('select canonical_id from canonical_unit where unit_id=?',(target,)).fetchone()[0]
        db.execute('update canonical_unit set canonical_id=? where unit_id=?',(canonical,uid))
        decision='Same exact offering/member hash/JSON pointer; normalized annotation is not an additional published claim. All source/basis/qualification annotations remain retained; no factual agreement inferred.'
        db.execute('insert or replace into source_identity_alias values (?,?,?,?,?)',(uid,target,sid,packed(item['source']),decision))
        db.execute('insert or replace into equivalence values (?,?,?,?)',(ident('EQ',uid),uid,'same_pinned_field; all_scope_annotations_retained',packed({'target_unit_id':target,'pinned_source_id':sid,'locator':item['source'],'amount_presence_used':False,'accepted_for_reference':False})))
        merged.append({'alias_unit_id':uid,'target_unit_id':target,'pinned_source_id':sid})
    db.commit();return {'same_source_field_aliases':merged,'non_equivalences_retained':held,'factual_equivalence_approved':False}


def reconcile_question_scopes(db):
    """Known CMS authorization/referral questions share one exact scope.

    This reconciles inventory questions only. Different stored answers, selector
    interpretations or source qualifiers remain unverified and fully retained.
    """
    db.execute('create table if not exists question_scope_alias(unit_id text primary key,canonical_id text not null,family text not null,scope text not null)')
    groups=collections.defaultdict(list)
    for uid,oid,kind,subject,predicate,ctx,payload in db.execute("select id,offering_id,kind,subject,predicate,context,payload from semantic_unit where kind='condition'"):
        context=json.loads(ctx);data=json.loads(payload)
        if len(context.get('service_ids',[]))!=1:continue
        family=data.get('family')
        if data.get('source_basis')=='CMS_JSON':
            family='authorization'if predicate=='Authorization required for this benefit?'else'referral'if predicate=='Referral required for this benefit?'else None
        if family not in {'authorization','referral'}:continue
        if data.get('source_basis')!='CMS_JSON':
            norms=[json.loads(p).get('normalized',{}).get('type')for p, in db.execute("select payload from observation where unit_id=? and layer='cms_table'",(uid,)).fetchall()]
            if not norms or any(n not in {'enum','enum_set','opaque_code'}for n in norms):continue
        scope={'offering_id':oid,'kind':kind,'subject':subject,'context':context,'question_family':family}
        canonical=ident('CMS_QUESTION',scope);groups[canonical].append((uid,family,scope))
    merged=[]
    for canonical,members in groups.items():
        if len(members)<2:continue
        for uid,family,scope in members:
            db.execute('update canonical_unit set canonical_id=? where unit_id=?',(canonical,uid))
            db.execute('insert or replace into question_scope_alias values (?,?,?,?)',(uid,canonical,family,packed(scope)))
        merged.append({'canonical_id':canonical,'unit_ids':[m[0]for m in members],'family':members[0][1],'scope':members[0][2],'inventory_question_equivalence_only':True,'factual_agreement':False})
    db.commit();return merged


def export_geometry(parent,root,cache):
    require_unsealed(root)
    old=sqlite3.connect(f'file:{parent}?mode=ro',uri=True)
    index={x['document_sha256']:x['source']for x in load(PARENT/'source-index.json')}
    chart_pages=set()
    for row in rows(R7/'carrier-chart-rows.jsonl.gz'):
        for fragment in row['fragments']:chart_pages.add((row['offering_id'],fragment['source_page']['document_sha256'],fragment['pdf_page']))
    owners={oid:json.loads(payload).get('parent')for oid,payload in old.execute('select id,payload from offering')}
    word_documents={};counts=collections.Counter();records=[];layout_families={}
    for oid,h,kind,p,text in old.execute('select offering_id,document_sha256,kind,pdf_page,text from carrier_view order by offering_id,document_sha256,kind,pdf_page'):
        g=detect_table_columns(text)
        is_chart=(oid,h,p)in chart_pages
        if not is_chart:
            if kind=='SB':
                roles=g['roles'];method='SB_full_source_rows'
                if set(roles)=={'in_network','out_of_network'}:method='SB_full_rows_with_separate_printed_network_questions'
                elif g['boundaries']:method='SB_financial_rows_with_source_default_network'
                family=(owners[oid],kind,method,tuple(roles))
                item=layout_families.setdefault(family,{'owner_parent':owners[oid],'kind':kind,'method':method,'printed_column_roles':roles,'page_views':0,'examples':[]})
                item['page_views']+=1
                if len(item['examples'])<3:item['examples'].append({'offering_id':oid,'document_sha256':h,'pdf_page':p})
                if g['boundaries']:records.append({'offering_id':oid,'document_sha256':h,'kind':kind,'pdf_page':p,'printed_header':g,'coordinate_binding':{'method':method,'cuts':{},'amount_to_network_binding_verified':False},'printed_financial_row_frames':sb_row_frames(text,g)})
            continue
        if not g['boundaries']:
            counts['full_source_text_no_printed_cost_column_header']+=1
            records.append({'offering_id':oid,'document_sha256':h,'kind':kind,'pdf_page':p,'printed_header':g,'coordinate_binding':{'method':'full_source_text_no_printed_cost_column_header','cuts':{}}})
            continue
        if h not in word_documents:word_documents[h]=pdf_words(index[h]['path'],pathlib.Path(cache)/(h+'.json.gz'))
        n=bind_page_words(text,word_documents[h][p-1],h,p,root/'ocr-word-coordinates');counts[n['method']]+=1
        records.append({'offering_id':oid,'document_sha256':h,'kind':kind,'pdf_page':p,'printed_header':g,'coordinate_binding':n})
        origin='OCR_word_coordinates'if n.get('word_position_source')else'native_or_retained_text_geometry'
        family=(owners[oid],kind,origin,tuple(g['roles']))
        item=layout_families.setdefault(family,{'owner_parent':owners[oid],'kind':kind,'method':origin,'printed_column_roles':g['roles'],'page_views':0,'examples':[]})
        item['page_views']+=1
        if len(item['examples'])<3:item['examples'].append({'offering_id':oid,'document_sha256':h,'pdf_page':p})
    with gzip.open(root/'page-geometry.jsonl.gz','wt')as f:
        for x in records:f.write(packed(x)+'\n')
    destination=root/'native-word-coordinates';destination.mkdir(exist_ok=True)
    for h in word_documents:shutil.copyfile(pathlib.Path(cache)/(h+'.json.gz'),destination/(h+'.json.gz'))
    dump(root/'geometry-summary.json',{'methods':dict(counts),'chart_page_views':len(chart_pages),'SB_header_scope_page_views':sum(r['kind']=='SB'for r in records),'source_geometry_records':len(records),'meaning':'Source projection and audit context; native mismatch/OCR interpretation remains held for later verification.'})
    dump(root/'layout-family-registry.json',{'purpose':'Observed layout strata for the later whole-offering pilot, not benefit-verification counts. Prose/contents and linked supplemental assertions remain in the full source census.','families':list(layout_families.values())})
    old.close()


def export_inventory(path,root,parent=None):
    require_unsealed(root)
    db=sqlite3.connect(path)
    if parent:dump(root/'list-introducer-evidence.json',link_list_introducers(db,parent))
    elif db.execute("select count(*) from clause where json_extract(payload,'$.list_intro') is not null").fetchone()[0]:
        raise ValueError('Exact parent inventory is required to bind inherited list-introducer evidence')
    db.execute('create index if not exists lineage_unit on lineage(unit_id)')
    retained=retain_empty_amount_annotations(db)
    if retained or not(root/'retained-empty-amount-annotations.json').exists():dump(root/'retained-empty-amount-annotations.json',retained)
    compound=complete_compound_costs(db)
    if compound['new_cost_schedule_units']or not(root/'compound-schedule-completion.json').exists():dump(root/'compound-schedule-completion.json',compound)
    refined=refine_scalar_amount_roles(db)
    if refined or not(root/'scalar-amount-role-refinement.json').exists():dump(root/'scalar-amount-role-refinement.json',refined)
    dump(root/'source-identity-equivalences.json',reconcile_same_source_amounts(db))
    dump(root/'question-scope-equivalences.json',reconcile_question_scopes(db))
    counts=dict(db.execute('select u.kind,count(distinct c.canonical_id) from semantic_unit u join canonical_unit c on u.id=c.unit_id group by u.kind'))
    by_offering=[]
    for oid, in db.execute('select distinct offering_id from semantic_unit order by offering_id'):
        by_offering.append({'offering_id':oid,'required':dict(db.execute('select u.kind,count(distinct c.canonical_id) from semantic_unit u join canonical_unit c on u.id=c.unit_id where u.offering_id=? group by u.kind',(oid,))),
            'states':dict(db.execute('select u.state,count(distinct c.canonical_id) from semantic_unit u join canonical_unit c on u.id=c.unit_id where u.offering_id=? group by u.state',(oid,)))})
    dump(root/'offering-inventory.json',by_offering)
    aliases={r[0]for r in db.execute('select alias_unit_id from source_identity_alias')}
    digest=hashlib.sha256();digest.update(b'[');record_index=0
    with gzip.open(root/'master-inventory.jsonl.gz','wt')as f:
        for canonical, in db.execute('select distinct canonical_id from canonical_unit order by canonical_id'):
            reps=db.execute('select u.id,u.offering_id,u.kind,u.subject,u.predicate,u.context,u.state,u.payload from semantic_unit u join canonical_unit c on u.id=c.unit_id where c.canonical_id=? order by u.id',(canonical,)).fetchall()
            reps.sort(key=lambda r:(r[0]in aliases,r[0]))
            first=reps[0];source_ids=set();observation_ids=[];root_ids=set()
            for uid,*_ in reps:
                for obs,sid in db.execute('select id,source_id from observation where unit_id=?',(uid,)):observation_ids.append(obs);source_ids.add(sid)
                root_ids.update(r[0]for r in db.execute('select root_id from lineage where unit_id=?',(uid,)))
            record={'id':canonical,'offering_id':first[1],'kind':first[2],'subject':first[3],'predicate':first[4],
                'context':json.loads(first[5]),'states':sorted({r[6]for r in reps}),'detail':json.loads(first[7]),
                'representation_ids':[r[0]for r in reps],'source_ids':sorted(source_ids),'observation_ids':sorted(observation_ids),
                'prior_root_ids':sorted(root_ids),'work_policy_id':first[2].upper(),'accepted_for_reference':False}
            f.write(packed(record)+'\n')
            if record_index:digest.update(b',')
            digest.update(json.dumps(record,sort_keys=True,separators=(',',':')).encode());record_index+=1
    digest.update(b']')
    dump(root/'inventory-binding.json',{'algorithm':'SHA256 of all canonical records sorted by ID, compact sorted-key JSON array','required_record_count':record_index,'inventory_digest':digest.hexdigest(),'new_acceptance_inherited':False})
    summary={'package_id':PACKAGE,'offerings':72,'required_claims':counts['claim'],'required_conditions':counts['condition'],
        'required_total':sum(counts.values()),'stored_semantic_representations':db.execute('select count(*) from semantic_unit').fetchone()[0],
        'canonical_aliases':db.execute('select count(*)-count(distinct canonical_id) from canonical_unit').fetchone()[0],
        'carrier_clause_dispositions':dict(db.execute('select kind,count(*) from clause group by kind')),
        'source_equivalence_dispositions':dict(db.execute('select decision,count(*) from equivalence group by decision')),
        'source_dispositions':dict(db.execute('select disposition,count(*) from source_disposition group by disposition')),
        'states':dict(db.execute('select u.state,count(distinct c.canonical_id) from semantic_unit u join canonical_unit c on u.id=c.unit_id group by u.state')),
        'preserved_historical_work':dict(db.execute('select kind,count(*) from work_obligation group by kind')),
        'permitted_unmodeled_extras':0,'unclassified_source_passages':0,'new_verified_claims':0,'new_accepted_entries':0,
        'milestone_1_complete':False,'semantic_inventory_frozen':False}
    dump(root/'denominator.json',summary);db.execute('analyze');db.commit();db.close()
    return summary


def export_audit_sample(path,parent,root):
    require_unsealed(root)
    db=sqlite3.connect(f'file:{path}?mode=ro',uri=True)
    old=sqlite3.connect(f'file:{parent}?mode=ro',uri=True)
    owners=dict(old.execute("select id,offering_id from source_unit where layer='carrier_passage'"))
    companies={oid:json.loads(payload).get('parent')for oid,payload in old.execute('select id,payload from offering')}
    geometry={(r['offering_id'],r['document_sha256'],r['pdf_page']):r for r in rows(root/'page-geometry.jsonl.gz')}
    samples={};counts=collections.Counter()
    for cid,sid,kind,rule,payload in db.execute('select id,source_id,kind,rule,payload from clause'):
        counts[rule]+=1;oid=owners[sid];keys=[('rule',rule)]
        if kind in {'claim','condition'}:keys.append(('contract_kind',oid.split(':')[1],kind))
        atom=None
        if kind in {'claim','condition'}:
            atom=json.loads(payload);loc=atom['source_fragments'][0]['locator']
            g=geometry.get((oid,loc['document_sha256'],loc['pdf_page']))
            if g:keys.append(('layout',companies[oid],loc['kind'],g['coordinate_binding']['method'],','.join(g['printed_header']['roles'])))
        for key in keys:
            selected=samples.setdefault(key,[])
            if len(selected)<2 or cid<selected[-1][0]:
                if atom is None:atom=json.loads(payload)
                record={'clause_id':cid,'offering_id':oid,'kind':kind,'rule':rule,'quote':atom['quote'],
                    'parent_sentence':atom.get('parent_sentence'),'source_fragments':atom.get('source_fragments'),
                    'physical_header':atom.get('physical_header'),'condition_families':atom.get('condition_families'),'list_intro':atom.get('list_intro')}
                selected.append((cid,record));selected.sort();del selected[2:]
    dump(root/'classification-audit-sample.json',{'selection':'Two lowest stable clause IDs per rule, contract/kind and observed carrier/layout stratum. Internal source-backed inventory review; not independent benefit truth or a whole-offering comparison pilot.',
        'rule_counts':dict(counts),'sample':[{'stratum':list(k),'records':[r for _,r in v]}for k,v in sorted(samples.items())]})
    db.close();old.close()


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--inventory',required=True);p.add_argument('--root',type=pathlib.Path,default=ROOT)
    p.add_argument('--parent',required=True);p.add_argument('--geometry-cache');a=p.parse_args();a.root.mkdir(parents=True,exist_ok=True)
    if a.geometry_cache:export_geometry(a.parent,a.root,a.geometry_cache)
    print(json.dumps(export_inventory(a.inventory,a.root,a.parent),indent=2))
