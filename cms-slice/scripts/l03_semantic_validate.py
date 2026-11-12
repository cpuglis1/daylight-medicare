"""Read-only exhaustive validation of semantic inventory lineage/provenance.

These checks verify coverage, segmentation, semantic predicate bookkeeping and
freeze integrity. They do not independently adjudicate benefit interpretation.
"""
from __future__ import annotations
import argparse,collections,csv,hashlib,io,json,pathlib,re,sqlite3,zipfile
from l03_inventory import REPO,load,sha


def validate(path,parent,root=None):
    db=sqlite3.connect(f'file:{path}?mode=ro',uri=True)
    old=sqlite3.connect(f'file:{parent}?mode=ro',uri=True)
    checks=[]
    def check(name,ok,detail=None):checks.append({'name':name,'passed':bool(ok),'detail':detail})
    check('SQLite structural integrity',db.execute('pragma integrity_check').fetchone()[0]=='ok')
    old_ids={x[0]for x in old.execute('select id from offering')}
    new_ids={x[0]for x in db.execute('select distinct offering_id from semantic_unit')}
    check('Exact 72 offering identities',new_ids==old_ids and len(new_ids)==72)
    parent_sources={r[0]for r in old.execute('select id from source_unit')}
    dispositions={r[0]for r in db.execute('select source_id from source_disposition')}
    check('Every parent source field/passage is classified',parent_sources<=dispositions,
          {'missing':len(parent_sources-dispositions),'additional_named_sources':len(dispositions-parent_sources)})
    check('No unclassified carrier clauses or unnamed retention rules',db.execute("select count(*) from clause where kind not in ('claim','condition','retained_administration','retained_structure','retained_layout') or trim(rule)='' or rule is null").fetchone()[0]==0)
    roots={r[0]for r in old.execute('select id from obligation')}
    check('Every original root retained',roots=={r[0]for r in db.execute('select root_id from root_disposition')})
    check('No orphan semantic observations',db.execute('''select count(*) from observation o left join semantic_unit u on u.id=o.unit_id where u.id is null''').fetchone()[0]==0)
    check('Every required unit has exact observation or named missing-source predicate',db.execute('''select count(*) from semantic_unit u where not exists(select 1 from observation o where o.unit_id=u.id)''').fetchone()[0]==0)
    check('Every canonical identity retains its unit',db.execute('''select count(*) from semantic_unit u left join canonical_unit c on c.unit_id=u.id where c.unit_id is null''').fetchone()[0]==0)
    check('No invalid state or release acceptance',db.execute("select count(*) from semantic_unit where state not in ('evidence_reconciliation_pending','required_evidence_missing','preserved_source_conflict')").fetchone()[0]==0)
    check('All 153 historical holds retained',db.execute("select count(*) from work_obligation where kind='preserved_conflict'").fetchone()[0]==153)
    check('Every historical hold has field-specific semantic lineage',db.execute("select count(*) from work_obligation w where kind='preserved_conflict' and not exists(select 1 from lineage l where l.root_id=w.id)").fetchone()[0]==0)
    # All offering/source identities are checked independently of the builder's
    # identifier calculation, against the parent source locators.
    identity_errors=[];source_owners={sid:oid for sid,oid in old.execute('select id,offering_id from source_unit')}
    for oid,sid in db.execute('select distinct u.offering_id,o.source_id from observation o join semantic_unit u on u.id=o.unit_id'):
        if sid in source_owners and oid!=source_owners[sid]:identity_errors.append([sid,oid])
    check('Observation provenance cannot cross offering identity',not identity_errors,identity_errors[:5])
    word_errors=[];range_errors=[];coverage_errors=[];condition_errors=[];intro_errors=[];checked_intros=0;checked_clauses=0;checked_chars=0
    for oid in sorted(old_ids):
        texts={sid:json.loads(p)['text']for sid,p in old.execute("select id,payload from source_unit where offering_id=? and layer='carrier_passage'",(oid,))}
        covered={sid:bytearray(len(t))for sid,t in texts.items()}
        def project(refs,cover=False):
            pieces=[]
            for ref in refs:
                sid,a,b=ref['source_id'],ref['start'],ref['end']
                if sid not in texts or not (0<=a<b<=len(texts.get(sid,''))):
                    range_errors.append([sid,a,b]);continue
                pieces.append(texts[sid][a:b])
                if cover:covered[sid][a:b]=b'\x01'*(b-a)
            return re.sub(r'\s+',' ','\n'.join(pieces)).strip()
        query='''select c.id,c.source_id,c.unit_id,c.kind,c.payload from clause c
                 join source_disposition s on s.source_id=c.source_id
                 where c.source_id in (select source_id from source_target t join semantic_unit u on u.id=t.unit_id where u.offering_id=?)'''
        # Structural-only sources have no source_target, so select by original
        # source identity through an explicit temporary table as well.
        db.execute('create temp table if not exists current_source(id text primary key)')
        db.execute('delete from current_source');db.executemany('insert into current_source values (?)',[(sid,)for sid in texts])
        for cid,sid,uid,kind,p in db.execute('select id,source_id,unit_id,kind,payload from clause where source_id in (select id from current_source)'):
            atom=json.loads(p);checked_clauses+=1
            if atom.get('physical_header'):
                refs=[{'source_id':sid,'start':a,'end':b}for a,b in atom['source_character_ranges']]
                actual=project(refs,True)
            else:
                actual=project(atom['source_fragments'])
                parent_text=project(atom.get('parent_source_fragments',atom['source_fragments']),True)
                if parent_text!=re.sub(r'\s+',' ',atom['parent_sentence']).strip():word_errors.append([cid,'logical_parent'])
            if actual!=re.sub(r'\s+',' ',atom['quote']).strip():word_errors.append([cid,'assertion'])
            if kind in {'claim','condition'}:
                ids=atom.get('required_unit_ids',[])
                families=set(atom.get('condition_families',[]))
                found=set()
                for unit in ids:
                    row=db.execute('select kind,payload from semantic_unit where id=?',(unit,)).fetchone()
                    if not row:condition_errors.append([cid,'missing_child']);continue
                    data=json.loads(row[1])
                    if row[0]=='condition':found.add(data.get('condition_family'))
                if not families<=found:condition_errors.append([cid,sorted(families-found)])
                if not ids:condition_errors.append([cid,'no_required_child'])
                if atom.get('list_intro'):
                    checked_intros+=1;refs=atom.get('list_intro_source_fragments',[])
                    if not refs or project(refs)!=re.sub(r'\s+',' ',atom['list_intro']['quote']).strip():intro_errors.append([cid,'missing_or_changed_intro_source_quote'])
                    required_sources={r['source_id']for r in refs}
                    for unit in ids:
                        found={r[0]for r in db.execute("select source_id from observation where unit_id=? and layer='carrier_list_intro'",(unit,))}
                        if not required_sources<=found:intro_errors.append([cid,unit,'inherited_qualification_has_no_source_observation'])
        for sid,text in texts.items():
            missing=''.join(ch for i,ch in enumerate(text)if not ch.isspace()and not covered[sid][i])
            checked_chars+=sum(not ch.isspace()for ch in text)
            if missing:coverage_errors.append([sid,missing[:120]])
    check('Every source assertion and logical parent reconstructs exactly',not word_errors,{'clauses':checked_clauses,'errors':word_errors[:5]})
    check('Every passage/cell character range is valid',not range_errors,range_errors[:5])
    check('100% nonblank carrier source characters have assertion/context/support dispositions',not coverage_errors,{'characters':checked_chars,'gaps':len(coverage_errors),'examples':coverage_errors[:8]})
    check('Each material condition family is its own required predicate',not condition_errors,{'errors':len(condition_errors),'examples':condition_errors[:5]})
    check('Every inherited list qualification has exact source spans and linked observations',not intro_errors,{'list_member_clauses':checked_intros,'errors':len(intro_errors),'examples':intro_errors[:5]})
    # Canonical aliases may erase a geometric column label only with a fully
    # specified network; all material context, source antecedents and wording
    # must remain identical. This is not an amount-equivalence test.
    identity_aliases={a:(t,s,json.loads(l))for a,t,s,l in db.execute('select alias_unit_id,target_unit_id,pinned_source_id,locator from source_identity_alias')}
    identity_errors=[]
    for alias,(target,sid,locator)in identity_aliases.items():
        a=db.execute("select u.offering_id,u.kind,o.payload from semantic_unit u join observation o on o.unit_id=u.id where u.id=? and o.layer='cms_named_amount'",(alias,)).fetchone()
        b=db.execute("select u.offering_id,u.kind,o.payload from semantic_unit u join observation o on o.unit_id=u.id where u.id=? and o.layer='cms_json' and o.source_id=?",(target,sid)).fetchone()
        if not a or not b or a[:2]!=b[:2]or a[1]!='claim':identity_errors.append([alias,'scope_or_source']);continue
        x=json.loads(a[2])['source'];y=json.loads(b[2])['locator']
        if any(x.get(k)!=y.get(k)for k in ['member','member_sha256','pointer']):identity_errors.append([alias,'different_pinned_field'])
        if x!=locator:identity_errors.append([alias,'changed_annotation_locator'])
        ids=db.execute('select canonical_id from canonical_unit where unit_id in (?,?)',(alias,target)).fetchall()
        if len({r[0]for r in ids})!=1:identity_errors.append([alias,'canonical_target'])
    check('Normalized aliases bind the very same pinned field, never matching prices',not identity_errors,{'aliases':len(identity_aliases),'errors':identity_errors[:5]})
    question_aliases={u:(c,f,json.loads(s))for u,c,f,s in db.execute('select unit_id,canonical_id,family,scope from question_scope_alias')}
    question_errors=[]
    for uid,(canonical,family,scope)in question_aliases.items():
        r=db.execute('select offering_id,kind,subject,context,payload,predicate from semantic_unit where id=?',(uid,)).fetchone()
        data=json.loads(r[4]);declared=data.get('family')
        if data.get('source_basis')=='CMS_JSON':declared='authorization'if r[5]=='Authorization required for this benefit?'else'referral'if r[5]=='Referral required for this benefit?'else None
        if r[1]!='condition'or declared!=family or scope!={'offering_id':r[0],'kind':r[1],'subject':r[2],'context':json.loads(r[3]),'question_family':family}:question_errors.append(uid)
    check('CMS question equivalences bind the exact service/network/variant context',not question_errors,{'member_units':len(question_aliases),'errors':question_errors[:5]})
    alias_errors=[];alias_groups=0
    for canonical,n in db.execute('select canonical_id,count(*) from canonical_unit group by canonical_id having count(*)>1'):
        signatures=[];alias_groups+=1
        member_ids={r[0]for r in db.execute('select unit_id from canonical_unit where canonical_id=?',(canonical,))}
        identity_group=bool(member_ids&set(identity_aliases))
        question_group=member_ids<=set(question_aliases)and len({json.dumps(question_aliases[u][2],sort_keys=True)for u in member_ids})==1
        for oid,kind,subject,predicate,context in db.execute('select u.offering_id,u.kind,u.subject,u.predicate,u.context from semantic_unit u join canonical_unit c on u.id=c.unit_id where c.canonical_id=?',(canonical,)):
            ctx=json.loads(context)
            if ctx.get('network')=='network_not_explicit_in_clause':alias_errors.append([canonical,'unknown_network'])
            ctx.pop('source_column',None)
            signatures.append(json.dumps([oid,kind,subject,predicate,ctx],sort_keys=True))
        if len(set(signatures))!=1 and not identity_group and not question_group:alias_errors.append([canonical,'material_difference'])
        if identity_group and not all(t in member_ids for a,(t,_,_)in identity_aliases.items()if a in member_ids):alias_errors.append([canonical,'missing_same_field_target'])
    check('Canonical equivalences preserve full material scope',not alias_errors,{'groups':alias_groups,'errors':alias_errors[:5]})
    named_amounts=load(REPO/'docs/data/l03-ma-benefits-2026-10-25/build-r1/normalized-amount-observations.json')
    stored=[json.loads(x[0])for x in db.execute("select payload from observation where layer='cms_named_amount'")]
    stored.extend(json.loads(x[0])for x in db.execute('select payload from retained_amount_annotation'))
    encode=lambda x:json.dumps(x,sort_keys=True,separators=(',',':'))
    check('All 1,014 named plan amounts retained exactly',collections.Counter(map(encode,named_amounts))==collections.Counter(map(encode,stored))and len(stored)==1014)
    landscape=[x for x in named_amounts if 'record_ordinal'in x['source']]
    archive=REPO/'docs/data/l02-ma-availability-2026-10-25/acquisition-r1/raw'/landscape[0]['source']['archive_sha256']
    landscape_errors=[]
    with zipfile.ZipFile(archive)as source:
        content=source.read(landscape[0]['source']['member'])
        if hashlib.sha256(content).hexdigest()!=landscape[0]['source']['member_sha256']:landscape_errors.append('member_hash')
        wanted=collections.defaultdict(list)
        for item in landscape:wanted[item['source']['record_ordinal']].append(item)
        for ordinal,row in enumerate(csv.DictReader(io.StringIO(content.decode('utf-8-sig'))),1):
            for item in wanted.get(ordinal,[]):
                identity=':'.join(['2026',row['Contract ID'],row['Plan ID'].zfill(3),row['Segment ID'].zfill(3)])
                if identity!=item['offering_id']or row['Contract Year']!='2026'or row['State Territory Abbreviation']!='FL'or row['County Name'].lower()!='collier'or row[item['source']['field']]!=item['raw']:landscape_errors.append([ordinal,item['field']])
    check('504 Landscape amount/applicability observations rederived from original pinned Collier rows',not landscape_errors,landscape_errors[:5])
    check('No unnamed claim or empty predicate',db.execute("select count(*) from semantic_unit where trim(subject)='' or trim(predicate)='' or kind not in ('claim','condition')").fetchone()[0]==0)
    check('11 supplemental definitions remain required unknowns',db.execute("select count(*) from semantic_unit where predicate='Exact published carrier definition, included service subtypes and qualifications' and state='required_evidence_missing'").fetchone()[0]==11)
    check('72 amendment obligations remain required unknowns',db.execute("select count(*) from semantic_unit where predicate='Exact applicable amendment, effective interval and affected clauses, or evidenced absence' and state='required_evidence_missing'").fetchone()[0]==72)
    if root:
        root=pathlib.Path(root)
        binding=load(root/'inventory-binding.json');digest=hashlib.sha256();digest.update(b'[');seen_ids=set();record_count=0;kind_counts=collections.Counter();previous=None
        import gzip
        with gzip.open(root/'master-inventory.jsonl.gz','rt')as stream:
            for line in stream:
                record=json.loads(line)
                if record_count:digest.update(b',')
                digest.update(json.dumps(record,sort_keys=True,separators=(',',':')).encode())
                if record['id']in seen_ids:identity_errors.append([record['id'],'duplicate_export'])
                if previous and previous>=record['id']:identity_errors.append([record['id'],'export_order'])
                previous=record['id'];seen_ids.add(record['id']);record_count+=1;kind_counts[record['kind']]+=1
        digest.update(b']')
        expected={r[0]for r in db.execute('select distinct canonical_id from canonical_unit')}
        check('Export is the exact frozen canonical denominator',seen_ids==expected and record_count==len(expected)and record_count==binding['required_record_count']and digest.hexdigest()==binding['inventory_digest'],{'records':record_count,'kinds':dict(kind_counts),'digest':digest.hexdigest()})
        bad=[]
        for name,expected in load(pathlib.Path(root)/'inputs.json').items():
            p=REPO/name
            if not p.exists()or sha(p)!=expected:bad.append(name)
        check('Pinned inputs and sealed parent revisions unchanged',not bad,bad[:10])
    db.close();old.close()
    return {'passed':all(x['passed']for x in checks),'checks':checks,'purpose':'Inventory completeness/provenance; zero new verified or accepted benefit facts.'}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--inventory',required=True);p.add_argument('--parent',required=True);p.add_argument('--root')
    a=p.parse_args();print(json.dumps(validate(a.inventory,a.parent,a.root),indent=2))
