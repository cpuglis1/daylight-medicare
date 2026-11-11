"""Whole-population native-field, scope, database and immutable-parent checks."""
import collections,gzip,itertools,json,re,sqlite3
from l08_r4_common import ROOT,HOME,PARENT,BASE,write,filehash
from l08_r4_legacy import CITY

def main():
    failures=[];counts=collections.Counter()
    def check(ok,message):
        if not ok:failures.append(message)
    for manifest in [HOME/'execution-manifest-r1.json',HOME/'followup-r2/manifest.json',PARENT/'manifest.json']:
        for rel,meta in json.loads(manifest.read_text())['files'].items():
            p=ROOT/rel;check(p.exists()and p.stat().st_size==meta['bytes']and filehash(p)==meta['sha256'],'Parent file changed '+rel)
            counts['sealed_parent_files_rehashed']+=1
    db=sqlite3.connect('file:'+str(BASE/'providers.sqlite3')+'?mode=ro',uri=True)
    old=sqlite3.connect('file:'+str(PARENT/'providers.sqlite3')+'?mode=ro',uri=True)
    check(db.execute('PRAGMA integrity_check').fetchone()[0]=='ok','Database integrity')
    for table, in old.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name NOT LIKE '%_data' AND name NOT LIKE '%_idx' AND name NOT LIKE '%_content' AND name NOT LIKE '%_docsize' AND name NOT LIKE '%_config'"):
        n=old.execute('SELECT count(*) FROM "'+table+'"').fetchone()[0]
        nn=db.execute('SELECT count(*) FROM "'+table+'"').fetchone()[0]
        check(nn>=n if table=='sources'else nn==n,'Parent table count '+table)
        for a,b in itertools.zip_longest(old.execute('SELECT * FROM "'+table+'" ORDER BY rowid'),db.execute('SELECT * FROM "'+table+'" ORDER BY rowid LIMIT '+str(n))):
            check(a==b,'Parent row changed '+table);counts['unchanged_parent_rows_compared']+=1
    check(db.execute('SELECT count(*)FROM offerings').fetchone()[0]==72,'Pinned 72 MA offerings')
    invs={x['sha256']:x for x in json.loads((PARENT/'humana-document-inventory.json').read_text())if x['collier_geography_explicit']}
    natives={k:[json.loads(s)for s in gzip.open(ROOT/v['native_path'],'rt')]for k,v in invs.items()}
    bydoc=collections.defaultdict(list);entries={};used=collections.defaultdict(set);direct=collections.defaultdict(list)
    for s in gzip.open(BASE/'humana-entries.jsonl.gz','rt'):
        r=json.loads(s);sh=r['document_sha256'];ns=natives[sh];entries[r['id']]=r;bydoc[sh].append(r)
        names=r['name_nodes'];body=r['body_nodes'];allnodes=names+body
        check(not(used[sh]&set(allnodes)),'Overlapping entry native nodes');used[sh].update(allnodes)
        check(r['name_raw']==' '.join(ns[k]['text']for k in names),'Name field source '+r['id']);counts['native_name_values_compared']+=1
        check(all('Condensed,Bold'in ns[k]['font']['family']and ns[k]['font']['size']=='11'for k in names),'Name typography')
        check(r['body_raw']==[ns[k]['text']for k in body],'Every native body field '+r['id']);counts['native_body_values_compared']+=len(body)
        check(r['conditions_raw']==[ns[k]['text']for k in r['condition_nodes']],'Condition literal values');counts['native_condition_values_compared']+=len(r['condition_nodes'])
        check(r['condition_nodes']==[k for k in body if ns[k]['font']['size']=='10'],'Every bounded 10-point qualifier retained')
        for field,indices in [('county_raw',r['county_nodes']),('specialty_raw',r['specialty_nodes']),('section_raw',r['section_nodes'])]:
            check(r[field]==(' '.join(ns[k]['text']for k in indices)or None),'Context source '+field);counts['native_context_values_compared']+=1
        for ident in r['source_native_ids']:
            check(ns[ident['node']]['text']==ident['raw']and re.fullmatch(r'PCP#\s*'+re.escape(ident['value']),ident['raw'])is not None,'Printed ID/source suffix preserved')
            check(ident['not_unique_person_identifier']is True,'No person identity from shared PCP#');counts['source_native_ID_values_compared']+=1
        for cond in r['dated_or_acceptance_conditions']:
            check(cond['raw']==ns[cond['node']]['text']and cond['node']in body,'Dated/patient condition source');counts['dated_acceptance_values_compared']+=1
        check(r['npi']is None and r['benefit_year']==2026 and r['publication_date_raw']==invs[sh]['publication_date_raw'],'No invented NPI/year/date')
        for aid in r['direct_address_ids']:direct[aid].append(r['id'])
        stored=db.execute('SELECT fields_json FROM r4_humana_entries WHERE id=?',(r['id'],)).fetchone()
        check(stored is not None and json.loads(stored[0])==r,'Entry database/export parity');counts['entries_compared']+=1
    coverage=json.loads((BASE/'humana-normalization-accounting.json').read_text())
    for c in coverage:
        sh=c['document_sha256'];context=c['context_node_indices'];ns=natives[sh]
        check(not(used[sh]&set(context))and len(context)==len(set(context)),'Context/entry disjoint partition')
        expected={k for k,x in enumerate(ns)if x['page']in invs[sh]['modeled_pages']and 72<=x['top']<755 and any(30+136*col<=x['left']<166+136*col for col in range(4))}
        check(used[sh]|set(context)==expected,'Every modeled-column native node accounted')
        counts['native_column_nodes_accounted']+=len(expected)
    addresses={json.loads(s)['id']:json.loads(s)for s in gzip.open(PARENT/'humana-address-observations.jsonl.gz','rt')}
    seen=set();candidate_corrections=0
    for s in gzip.open(BASE/'humana-address-entry-links.jsonl.gz','rt'):
        r=json.loads(s);aid=r['address_id'];a=addresses[aid];seen.add(aid);entry=entries.get(r['entry_id'])
        check(entry is not None,'Every retained address has a bounded entry')
        check(entry is not None and a['native_city_node']in entry['body_nodes'],'Address in its owner native body')
        check(direct[aid]==[r['entry_id']],'Exactly one owning entry per parent address')
        check(r['typed_name_raw']==entry['name_raw']and r['name_kind']==entry['name_kind'],'Complete typed name link')
        check(r['original_candidate_raw']==a['fields']['name_candidate_raw'],'Parent candidate not rewritten')
        if r['typed_name_raw']!=r['original_candidate_raw']:candidate_corrections+=1
        check(json.loads(db.execute('SELECT fields_json FROM r4_address_entry_links WHERE address_id=?',(aid,)).fetchone()[0])==r,'Address link database parity')
        counts['address_entry_links_compared']+=1
    check(seen==set(addresses)and len(seen)==35220,'All 35,220 parent addresses accounted')
    # Independent topology assertions: a shared site must be from a prior,
    # same-scope organization entry. A distinct direct clinician site ends it.
    def keys(ids):return {tuple(addresses[i]['fields'][k]for k in ['street_raw','city_raw','state_raw','postal_raw'])for i in ids}
    for sh,rs in bydoc.items():
        practice=None;scope=None
        for r in rs:
            sig=(r['section_raw'],tuple(r['county_nodes']),tuple(r['specialty_nodes']))
            if sig!=scope:practice=None;scope=sig
            context=r['shared_practice_context']
            if context:
                check(practice is not None and context['entry_id']==practice['id'],'Shared-site source boundary')
                target=entries[context['entry_id']]
                check(target['name_kind']=='organization_or_practice_name'and target['direct_address_ids']==context['address_ids'],'Only printed practice sites inherited')
                check(context['name_raw']==target['name_raw'],'Practice context literal name');counts['bounded_shared_site_relations_compared']+=1
            if r['name_kind']=='organization_or_practice_name':practice=r if r['direct_address_ids']else None
            elif r['name_kind']=='credentialed_clinician_name'and practice:
                if r['direct_address_ids']and keys(r['direct_address_ids'])!=keys(practice['direct_address_ids']):practice=None
            elif r['name_kind']in['unclassified_published_name','published_specialty_heading']:practice=None
    legacy=json.loads((BASE/'legacy-unit-dispositions.json').read_text());groups=json.loads((BASE/'legacy-shared-layouts.json').read_text());needed=collections.defaultdict(set)
    for r in legacy:
        for a in r['recovered_direct_sites']:needed[r['document_sha256']].update(a['street_lines']+[a['city_line']])
    for g in groups:
        for a in g['shared_addresses']:needed[g['document_sha256']].update(a['street_lines']+a.get('city_lines',[a['city_line']]))
    lines=collections.defaultdict(dict)
    for s in gzip.open(HOME/'followup-r2/pdf-records/source-lines.jsonl.gz','rt'):
        x=json.loads(s)
        if x['index']in needed[x['source_sha256']]:lines[x['source_sha256']][x['index']]=x
    def site_check(sh,a):
        ls=lines[sh];check(a['street_raw']==' '.join(ls[k]['text']for k in a['street_lines']),'Legacy literal street')
        m=CITY.fullmatch(' '.join(ls[k]['text']for k in a.get('city_lines',[a['city_line']])))
        check(m is not None and[m[1],m[2],m[3]]==[a['city_raw'],a['state_raw'],a['postal_raw']],'Legacy city/state/ZIP incl source symbols')
        counts['legacy_site_values_compared']+=4
    gids={g['id']for g in groups};expected={r[0]for r in old.execute("SELECT id FROM pdf_records WHERE state NOT LIKE 'published_native%'")}
    check({r['parent_record_id']for r in legacy}==expected and len(legacy)==len(expected),'Every 2,660 prior exceptional unit disposition')
    for r in legacy:
        for a in r['recovered_direct_sites']:site_check(r['document_sha256'],a)
        if r['shared_layout_id']:check(r['shared_layout_id']in gids,'Shared layout foreign key')
        check(r['external_identity_match_invented']is False,'No invented legacy identity')
        check(json.loads(db.execute('SELECT fields_json FROM r4_legacy_dispositions WHERE parent_record_id=?',(r['parent_record_id'],)).fetchone()[0])==r,'Legacy disposition database parity')
        counts['legacy_units_compared']+=1
    for g in groups:
        for a in g['shared_addresses']:site_check(g['document_sha256'],a)
        check(json.loads(db.execute('SELECT fields_json FROM r4_legacy_shared_layouts WHERE id=?',(g['id'],)).fetchone()[0])==g,'Legacy group database parity');counts['shared_layouts_compared']+=1
    rows=json.loads((BASE/'public-hospital-observations.json').read_text());pages=json.loads((BASE/'public-query-pages.json').read_text())
    for r in rows:
        path=ROOT/r['source_path'];s=path.read_text();ls=s.splitlines()
        check(filehash(path)==r['source_sha256'],'Public source digest')
        check('text '+r['network_raw']in s and'Plan Year 2026'in s and'Distance: 100 mi'in s,'Guest network/year/radius scope')
        for key,loc in r['locators'].items():
            if not isinstance(loc,list):loc=[loc];vals=[r['fields'][key]]
            else:vals=r['fields'][key]
            check(len(vals)==len(loc),'Public list fields and locators have equal lengths')
            for value,l in zip(vals,loc):
                check(ls[l['line']].endswith(l['body'])and l['body'][l['span'][0]:l['span'][1]]==value,'Public modeled field/source span');counts['public_modeled_values_compared']+=1
        check(r['exact_offering_id']is None,'No ambiguous guest-to-PPO-plan join')
        check(json.loads(db.execute('SELECT fields_json FROM r4_public_observations WHERE id=?',(r['id'],)).fetchone()[0])==r,'Public database/export parity');counts['public_observations_compared']+=1
    for q in json.loads((BASE/'public-query-accounting.json').read_text()):
        ps=[p for p in pages if p['network_raw']==q['network_raw']]
        check(sorted(p['page']for p in ps)==list(range(1,q['pages']+1))and sum(p['cards']for p in ps)==q['advertised_total']==q['observations'],'Every bounded query page/result')
        check(json.loads(db.execute('SELECT fields_json FROM r4_public_query_accounting WHERE network_raw=?',(q['network_raw'],)).fetchone()[0])==q,'Query database parity')
    for p in(BASE/'acquisition/receipts').glob('*.json'):
        r=json.loads(p.read_text())
        if r.get('path'):check(filehash(ROOT/r['path'])==r['sha256']and(ROOT/r['path']).stat().st_size==r['bytes'],'Acquired HTTP bytes/hash');counts['new_HTTP_payloads_hashed']+=1
    handoff=json.loads((BASE/'wellcare-download-handoff.json').read_text());check(len(handoff['plans'])==6 and handoff['verified_direct_PDF_links']==0,'Honest Wellcare direct-file status')
    for r in handoff['plans']:
        check(r['direct_pdf_url']is None,'No invented Wellcare PDF URL')
        for e in r['route_evidence']:
            p=ROOT/e['text_path'];t=p.read_text().split('\f')[e['page']-1]
            check(filehash(p)==e['text_sha256']and t[e['span'][0]:e['span'][1]]==e['raw'],'Wellcare exact retained EOC source span');counts['Wellcare_route_source_spans_compared']+=1
    write(BASE/'validation.json',{'passed':not failures,'failures':failures,'counts':dict(counts),
      'parent_candidates_with_different_complete_bounded_name':candidate_corrections,
      'all_modeled_literal_values_source_checked':True,'identity_and_layout_classification_limits_explicit':True,
      'all_specialty_network_complete':False,'personal_participation_verified':False,'full_L08_complete':False})
    print(json.dumps({'passed':not failures,'failures':failures[:20],'counts':dict(counts),'candidate_name_corrections':candidate_corrections}))
    if failures:raise SystemExit(1)

if __name__=='__main__':main()
