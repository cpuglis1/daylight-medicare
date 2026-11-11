"""Literal card normalization and complete bounded guest-query accounting."""
import ast,collections,json,re
from l08_r4_common import ROOT,PARENT,BASE,write,digest,assert_open

# Reuse the sealed, pure source-reader functions without their acquisition
# module's mutable OUT binding or any parent build side effects.
def load_pure(path,name,namespace):
    tree=ast.parse(path.read_text());fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef)and n.name==name)
    exec(compile(ast.Module(body=[fn],type_ignores=[]),str(path),'exec'),namespace)
    return namespace[name]

ax_nodes=load_pure(ROOT/'cms-slice/scripts/l08_r3_aetna.py','ax_nodes',{'re':re})

def parse(path,network):
    code=(ROOT/'cms-slice/scripts/l08_r3_public.py').read_text()
    fn=next(n for n in ast.parse(code).body if isinstance(n,ast.FunctionDef)and n.name=='humana')
    segment=ast.get_source_segment(code,fn).replace("'FL Medicare HMO'",'(network)').replace('Hospitals; FL Medicare HMO;', 'Hospitals; '+network+';')
    env={'re':re,'ROOT':ROOT,'digest':digest,'ax_nodes':ax_nodes,'network':network}
    exec(compile(segment,'retained-r3-humana-reader-with-explicit-selected-network','exec'),env)
    rs,q=env['humana'](path)
    for r in rs:
        r['exact_offering_id']=None
        r['state']='published_2026_selected_network_query; exact_PPO_offering_crosswalk_held'
    q['network_raw']=network
    return rs,q

def main():
    assert_open();rows=[];pages=[];queries=[]
    for slug,network in [('ppo','Medicare PPO'),('honor','Humana Honor PPO')]:
        subset=[];qs=[]
        for p in sorted((BASE/'ui').glob('humana-'+slug+'-hospitals-100mi-page*.ax.txt')):
            rs,q=parse(p,network);subset+=rs;qs.append(q)
        total=next(iter({q['advertised_total']for q in qs}));expected=(total+19)//20
        assert {q['page']for q in qs}==set(range(1,expected+1))
        assert sum(q['cards']for q in qs)==total
        keys=[(r['fields']['name_raw'],r['fields'].get('street_raw'),r['fields'].get('city_raw'),r['fields'].get('postal_raw'))for r in subset]
        duplicate_counts=collections.Counter(keys)
        queries.append({'network_raw':network,'benefit_year':2026,'category':'Hospitals','radius_miles':100,
            'origin':'selected Collier County centroid; not a Naples ZIP','advertised_total':total,
            'observations':len(subset),'pages':len(qs),'same_name_site_duplicate_occurrences':sum(v-1 for v in duplicate_counts.values()),
            'without_published_street':sum('street_raw'not in r['fields']for r in subset),
            'complete_for_this_query_only':True,'complete_all_specialty_county_network':False,'exact_PPO_plan_join_accepted':False})
        rows+=subset;pages+=qs
    write(BASE/'public-hospital-observations.json',rows);write(BASE/'public-query-pages.json',pages);write(BASE/'public-query-accounting.json',queries)
    print(json.dumps(queries))

if __name__=='__main__':main()
