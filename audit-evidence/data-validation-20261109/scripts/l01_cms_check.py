import json,sys
root='docs/data/l01-national-2026/published-reference-r1/'
costs={r['id']:r for r in json.load(open(root+'costs.json'))}
bands={r['id']:r for r in json.load(open(root+'bands.json'))}
# CMS 2026 fact sheet (Nov 14, 2025), values in cents
cms_costs={'a_premium_full':56500,'a_premium_reduced':31100,'a_deductible':173600,'hospital_61_90':43400,'hospital_reserve':86800,'snf_21_100':21700,'b_premium':20290,'b_deductible':28300,'immuno_premium':12160}
fails=[];n=0
for k,v in cms_costs.items():
    n+=1
    got=costs[k]['value']
    if got!=v: fails.append(('cost',k,got,v))
# brackets: (lower, upper, upper_inclusive) individual / joint
ind=[(None,10900000,True),(10900000,13700000,True),(13700000,17100000,True),(17100000,20500000,True),(20500000,50000000,False),(50000000,None,None)]
jnt=[(None,21800000,True),(21800000,27400000,True),(27400000,34200000,True),(34200000,41000000,True),(41000000,75000000,False),(75000000,None,None)]
mfs=[(None,10900000,True),(10900000,39100000,False),(39100000,None,None)]
adj={'full_b':[0,8120,20290,32460,44630,48700],'immuno_b':[0,8110,20270,32430,44590,48650],'part_d':[0,1450,3750,6040,8330,9100]}
tot={'full_b':[20290,28410,40580,52750,64920,68990],'immuno_b':[12160,20270,32430,44590,56750,60810],'part_d':[None]*6}
mfs_idx=[0,4,5]
def chk(bid,lo,hi,hi_inc,a,t):
    global n
    n+=1
    r=bands.get(bid)
    if r is None: fails.append(('band missing',bid)); return
    probs=[]
    if r['lower_cents']!=lo: probs.append(('lower',r['lower_cents'],lo))
    if r['upper_cents']!=hi: probs.append(('upper',r['upper_cents'],hi))
    if hi is not None and r['upper_inclusive']!=hi_inc: probs.append(('upper_inclusive',r['upper_inclusive'],hi_inc))
    if hi is None and lo is not None and r['lower_inclusive']!=True: probs.append(('lower_inclusive',r['lower_inclusive'],True))
    if lo is not None and hi is not None and r['lower_inclusive']!=False: probs.append(('lower_inclusive',r['lower_inclusive'],False))
    if r['adjustment_cents']!=a: probs.append(('adjustment',r['adjustment_cents'],a))
    if r['published_total_cents']!=t: probs.append(('total',r['published_total_cents'],t))
    if probs: fails.append((bid,probs))
for ctx in ('full_b','immuno_b','part_d'):
    for i,(lo,hi,inc) in enumerate(ind): chk(f'L01-IRMAA-{ctx}-individual-{i}',lo,hi,inc,adj[ctx][i],tot[ctx][i])
    for i,(lo,hi,inc) in enumerate(jnt): chk(f'L01-IRMAA-{ctx}-joint-{i}',lo,hi,inc,adj[ctx][i],tot[ctx][i])
    for j,(lo,hi,inc) in enumerate(mfs):
        i=mfs_idx[j]; chk(f'L01-IRMAA-{ctx}-separate_together-{j}',lo,hi,inc,adj[ctx][i],tot[ctx][i])
extra=set(bands)-{b for b in bands if b.startswith('L01-IRMAA-')}
print('checked',n,'values/rows; fails',len(fails)); [print(f) for f in fails]
print('band rows in file',len(bands),'unexpected',extra)
# internal: base+adj==total
bad=[b for b,r in bands.items() if r['published_total_cents'] is not None and r['base_cents']+r['adjustment_cents']!=r['published_total_cents']]
print('base+adjustment!=total:',bad)
