"""Source-layout normalization, retaining ambiguity rather than guessing identity.

Humana: all bold 11-point entry blocks in the six applicable publications,
all literal body nodes, direct sites, and bounded preceding practice context.
The preceding practice relationship is a layout association only, never a
global employment/participation assertion. Direct clinician addresses win.
"""
import collections,gzip,json,re,sqlite3
from l08_r4_common import ROOT,HOME,PARENT,BASE,write,assert_open

CITY=re.compile(r'^(.+?),\s*([A-Z]{2})\s+(\d{5}(?:-\d{4})?)$')
CREDENTIAL=re.compile(r'\b(?:MD|DO|APRN|ARNP|NP|PA|PAC|PA-C|DPM|DDS|DMD|OD|PHD|PhD|PSYD|PsyD|LCSW|LMHC|LPC|LMFT|MSW|MSN|DNP|PT|OT|OTR|AUD|AuD|DC|RD|RDN|SLP|CRNA|CNM|BCBA|CNS|FNP|FNP-C|FNP-BC|ANP|ACNP|WHNP|PNP|LCPC|LICSW|CSW|PMHNP(?: BC)?|MHC|PC|LCP|CP|LPCC|CNP|LISW|MA|SW|LMSW)\**$')

def typed_name(text):
    # Credentials alone are not a person: Dermatology Solutions PA is a group.
    if ','in text and CREDENTIAL.search(text):return 'credentialed_clinician_name'
    if re.search(r'\b(?:Health|Hospital|Medical|Medicine|Care|Clinic|Center|Centre|Group|Associates|LLC|Inc|Corp|Pharmacy|Pharmacies|Services|Institute|Dental|Vision|Optical|Rehab|Fitness|Radiology|LPG|MPG|RPS|DaVita|Dialysis|Therapy|Specialists|Surgeons|Physicians|Network|Partners|Infusion|InfusionCare|HomeCare|PLLC|LTD|Centers|Management|Dermatology|Cardiology|Oncology|Pathology|PC|PA|PL)\b',text,re.I):return 'organization_or_practice_name'
    if ','not in text and re.search(r'\b(?:MD|DO|APRN|ARNP|DPM|DDS|DMD|OD)\**$',text):return 'credentialed_clinician_name'
    return 'unclassified_published_name'

def is_name(x):
    return x['font']['size']=='11'and'Condensed,Bold'in x['font']['family']and not x['text'].startswith('* Board Certified')

def is_specialty_heading(b):
    if b['body_nodes']or','in b['name_raw']:return False
    s=b['name_raw']
    return bool(re.search(r'(?: Physician(?: \((?:PCP|Specialist)\))?| Nurse Practitioner| Nurse Specialist| Podiatrist| Therapist| Psychologist| Counselor| Social Worker| Supplier| Pathologist)$',s))or s in {
      'Nurse Practitioner','Podiatrist','Optometrist','Audiologist','Chiropractor','Registered Dietitian',
      'Psychologist','Counselor','Social Worker','Otolaryngology','Air Ambulance','Physiological Laboratory',
      'Skilled Nursing Facility','Clinical Nurse Specialist','Podiatric Assistant','Retail','Opioid Treatment Program',
      'Dentist - General Practice','Dentistry - Endodontics','Dentistry - Oral & Maxillofacial'}

def continues(a,b,raw):
    if a['page']!=b['page']or a['column']!=b['column']or not 0<b['top']-a['top']<=16:return False
    if CREDENTIAL.fullmatch(b['text'])and','in raw:return True
    if typed_name(raw)=='credentialed_clinician_name':return False
    # A second comma-name starts a distinct person even without a body line.
    if not raw.rstrip().endswith(',')and','in b['text']and re.match(r'^[A-Za-zÀ-ÿ].*,\s*[A-Za-zÀ-ÿ]',b['text']):return False
    return True

def ordered_nodes(inv):
    ns=[json.loads(s)for s in gzip.open(ROOT/inv['native_path'],'rt')]
    bypage=collections.defaultdict(list)
    for k,x in enumerate(ns):x={**x,'index':k};bypage[x['page']].append(x)
    stream=[];section=None;sec_nodes=[]
    for pg,xs in bypage.items():
        heads=[x for x in xs if x['top']<70 and'BoldItalic'in x['font']['family']and int(x['font']['size'])>=17]
        if heads:section=' '.join(x['text']for x in heads);sec_nodes=[x['index']for x in heads]
        if pg not in inv['modeled_pages']:continue
        for c in range(4):
            for x in sorted([x for x in xs if 72<=x['top']<755 and 30+136*c<=x['left']<166+136*c],key=lambda x:(x['top'],x['left'],x['node'])):
                stream.append({**x,'column':c,'section':section,'section_nodes':sec_nodes})
    return ns,stream

def normalize_document(inv,addresses):
    ns,stream=ordered_nodes(inv);sh=inv['sha256'];blocks=[];current=None;context=[];county=[];specialty=[];lastsec=None
    def finish():
        nonlocal current
        if current:
            current['name_raw']=' '.join(ns[k]['text']for k in current['name_nodes'])
            current['name_kind']=typed_name(current['name_raw']);blocks.append(current);current=None
    for x in stream:
        if x['section']!=lastsec:
            finish();lastsec=x['section'];county=[];specialty=[]
        if int(x['font']['size'])==12 and(x['text'].startswith('*')or x['top']>=710):
            context.append(x['index']);continue
        # Rotated outer-margin section tabs have a body-like top coordinate.
        # They do not end a listing continued into the next printed column.
        if int(x['font']['size'])==12 and x['text'].upper()==x['section'].upper():
            context.append(x['index']);continue
        if x['text'].endswith(' COUNTY')and'Heavy'in x['font']['family']:
            finish();county=[x['index']];specialty=[];context.append(x['index']);continue
        if 'Condensed'in x['font']['family']and int(x['font']['size'])in[12,13]:
            finish()
            # Consecutive heading lines are retained together; a new heading
            # starts after intervening source text.
            if specialty and ns[specialty[-1]]['page']==x['page']and 0<x['top']-ns[specialty[-1]]['top']<=17:specialty.append(x['index'])
            else:specialty=[x['index']]
            context.append(x['index']);continue
        if is_name(x):
            raw=' '.join(ns[k]['text']for k in current['name_nodes'])if current else''
            if current and not current['body_nodes']and continues(current['_last'],x,raw):
                current['name_nodes'].append(x['index']);current['_last']=x;continue
            finish()
            current={'id':sh+':entry:'+str(x['index']),'document_sha256':sh,'page':x['page'],'column':x['column'],
                'name_nodes':[x['index']],'body_nodes':[],'county_nodes':county[:],'specialty_nodes':specialty[:],
                'section_nodes':x['section_nodes'],'section_raw':x['section'],'_last':x}
        elif current:current['body_nodes'].append(x['index'])
        else:context.append(x['index'])
    finish()
    bynode={};previous_practice=None;signature=None;counts=collections.Counter();unused=[];heading_scope=None;local_specialty=[]
    address_by_id={a['id']:a for a in addresses}
    def site_keys(ids):
        return {tuple(address_by_id[i]['fields'][k]for k in ['street_raw','city_raw','state_raw','postal_raw'])for i in ids}
    for b in blocks:
        b.pop('_last');nodes=b['name_nodes']+b['body_nodes']
        scope=(b['section_raw'],tuple(b['county_nodes']))
        if scope!=heading_scope:local_specialty=[];heading_scope=scope
        if is_specialty_heading(b):local_specialty=b['name_nodes'];b['name_kind']='published_specialty_heading'
        if local_specialty:b['specialty_nodes']=local_specialty[:]
        for n in nodes:bynode[n]=b
        b['body_raw']=[ns[k]['text']for k in b['body_nodes']]
        b['county_raw']=' '.join(ns[k]['text']for k in b['county_nodes'])or None
        b['specialty_raw']=' '.join(ns[k]['text']for k in b['specialty_nodes'])or None
        b['direct_address_ids']=[];b['source_native_ids']=[]
        for k in b['body_nodes']:
            m=re.fullmatch(r'PCP#\s*(\S+)',ns[k]['text'])
            if m:b['source_native_ids'].append({'kind':'PCP#','value':m[1],'raw':m[0],'node':k,'not_unique_person_identifier':True})
        # Every condition is retained, including languages and repeated IDs.
        b['condition_nodes']=[k for k in b['body_nodes']if ns[k]['font']['size']=='10']
        b['conditions_raw']=[ns[k]['text']for k in b['condition_nodes']]
        b['dated_or_acceptance_conditions']=[{'raw':ns[k]['text'],'node':k}for k in b['body_nodes']
            if re.search(r'Age |Established patients|Term Date:|Effective Date:|Accepting|Medicaid Certified|Cultural Competency',ns[k]['text'],re.I)]
        b['npi']=None
    for a in addresses:
        b=bynode.get(a['native_city_node'])
        if b:b['direct_address_ids'].append(a['id'])
        else:unused.append(a['id'])
    for b in blocks:
        sig=(b['section_raw'],tuple(b['county_nodes']),tuple(b['specialty_nodes']))
        if sig!=signature:previous_practice=None;signature=sig
        b['shared_practice_context']=None;b['site_association_state']='no_explicit_site_in_bounded_entry'
        if b['name_kind']=='published_specialty_heading':b['site_association_state']='published_specialty_heading; not_a_provider_listing'
        if b['direct_address_ids']:b['site_association_state']='direct_address_in_own_published_entry'
        if b['name_kind']=='organization_or_practice_name':
            # Never borrow a site from an earlier unrelated organization.
            previous_practice=b if b['direct_address_ids']else None
        elif b['name_kind']=='credentialed_clinician_name'and previous_practice:
            b['shared_practice_context']={'entry_id':previous_practice['id'],'name_raw':previous_practice['name_raw'],
                'address_ids':previous_practice['direct_address_ids'],'state':'bounded_preceding_practice_layout; no global employment or personal participation inference'}
            if not b['direct_address_ids']:b['site_association_state']='shared_preceding_practice_site_in_same_source_section'
            elif site_keys(b['direct_address_ids'])!=site_keys(previous_practice['direct_address_ids']):
                # A later distinct clinician site ends inheritance of the
                # earlier practice site for subsequent addressless people.
                previous_practice=None
        elif b['name_kind']in['unclassified_published_name','published_specialty_heading']:previous_practice=None
        b['benefit_year']=2026;b['publication_date_raw']=inv['publication_date_raw'];b['native_path']=inv['native_path']
        b['state']='published_entry_normalized; directory expressly partial; unique person identity unasserted'
        counts['entries']+=1;counts[b['name_kind']]+=1;counts[b['site_association_state']]+=1
    # Every parent address gets a typed owner disposition, including any anchor
    # outside a bounded name entry. No original candidate is overwritten.
    associations=[]
    for a in addresses:
        b=bynode.get(a['native_city_node'])
        associations.append({'address_id':a['id'],'document_sha256':sh,'entry_id':b['id']if b else None,
          'name_kind':b['name_kind']if b else'unresolved_layout','typed_name_raw':b['name_raw']if b else None,
          'state':'bounded_source_entry_address'if b else'anchor_outside_bounded_name_entry; original retained',
          'original_candidate_raw':a['fields']['name_candidate_raw']})
    coverage={'document_sha256':sh,'source_nodes_in_modeled_columns':len(stream),
       'entry_nodes':sum(len(b['name_nodes'])+len(b['body_nodes'])for b in blocks),'context_nodes':len(context),
       'context_node_indices':context,'unassigned_address_ids':unused,**dict(counts)}
    assert coverage['entry_nodes']+coverage['context_nodes']==len(stream)
    return blocks,associations,coverage

def main():
    assert_open();invs=json.loads((PARENT/'humana-document-inventory.json').read_text())
    addresses=collections.defaultdict(list)
    for s in gzip.open(PARENT/'humana-address-observations.jsonl.gz','rt'):
        a=json.loads(s);addresses[a['document_sha256']].append(a)
    totals=collections.Counter();account=[]
    with gzip.open(BASE/'humana-entries.jsonl.gz','wt')as out,gzip.open(BASE/'humana-address-entry-links.jsonl.gz','wt')as links:
        for inv in invs:
            if not inv['collier_geography_explicit']:continue
            blocks,associations,cov=normalize_document(inv,addresses[inv['sha256']]);account.append(cov)
            for b in blocks:out.write(json.dumps(b,ensure_ascii=False)+'\n')
            for a in associations:links.write(json.dumps(a,ensure_ascii=False)+'\n')
            for k,v in cov.items():
                if isinstance(v,int):totals[k]+=v
    write(BASE/'humana-normalization-accounting.json',account)
    write(BASE/'humana-normalization-summary.json',dict(totals,documents=6,address_dispositions=sum(len(v)for v in addresses.values()),
       unassigned_addresses=sum(len(c['unassigned_address_ids'])for c in account),source_scope='all retained modeled-column nodes; front matter and name index remain in full parent pages',
       unique_clinician_count=None,personal_participation_verified=False))
    print((BASE/'humana-normalization-summary.json').read_text())

if __name__=='__main__':main()
