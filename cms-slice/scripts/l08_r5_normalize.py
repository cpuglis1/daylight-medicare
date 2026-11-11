"""Normalize the complete printed medical listing population, with source locators.

No inferred NPI, live panel status, or provider relationship period. Publisher
images are interpreted only through exact color+mask assets and the legend.
Pharmacy/index pages remain retained but do not change the accepted L07 data.
"""
import collections,gzip,json,re,sqlite3,unicodedata
from l08_r5_common import ROOT,HOME,PARENT,BASE,write,digest,assert_open

SECTIONS={'Primary Care Providers (PCP)','Walk-In Clinics','Specialty Providers','Behavioral Health','Hospitals','Vision','Additional Benefits','Other Services'}
PID=re.compile(r'^Provider ID:\s*(\d+)$')
CITY=re.compile(r"^([A-Za-z][A-Za-z .’'\-/]+),\s*([A-Z]{2})\s+(\d{5}(?:-\d{4})?)$")
PHONE=re.compile(r'^\(?\d{3}\)?[ -]\d{3}-\d{4}(?:.*)?$')
STREET=re.compile(r'^(?:\d+[A-Za-z0-9]*(?:\s|,)|P\.?\s?O\.?\s+Box\b|One\s|Two\s)',re.I)
HOURS=re.compile(r'^(?:(?:Mon(?:day)?|Tue(?:sday)?|Wed(?:nesday)?|Thu(?:rsday)?|Fri(?:day)?|Sat(?:urday)?|Sun(?:day)?)\b|24\s*(?:hours?|hrs?|/7)|By App|Call for)',re.I)
ICON_MAP={
 'f71d5ed4e73c0e165807a9aa4c7699b7a68ef5827a672fdf228884bfa55515eb':'wheelchair_access',
 'bb7d26681f28ca391fbc1cacb6ab9f43ec2cbd01312d535784f67870b5f7246b':'public_transportation_access',
 'c120194bd04d80d49b93816e879f4d2d82ead0ec674360d992db26a83258ff5f':'cultural_competency_training_complete',
 '1dec621f54cd34b383c0af10f09df861fceee78f5f635a3e9149e884d744e966':'phone_and_video_consultations',
 'be8c343eb71c499d4468b7c61a8b797f73e2c15776b516611a85c95e302b237c':'accepts_Medicaid',
 '84744882ac3d64669f92a1c6caeb3a2bf81d0d85b7c7a1bf28cb7af59e62e5cc':'board_certified',
 '318d4bd164d2c43ca359d6138feaa19e15c87f5a7db6f2409f78aaee3cade95f':'not_accepting_new_patients',
}
LEGEND={
 'wheelchair_access':'Indicates provider has wheelchair access',
 'public_transportation_access':'Accessible by Public Transportation',
 'cultural_competency_training_complete':'Indicates provider has completed cultural competency training',
 'phone_and_video_consultations':'Indicates Provider Offers Phone and Video Consultations (Telehealth)',
 'accepts_Medicaid':'Indicates provider accepts Medicaid','board_certified':'Indicates provider is board certified',
 'not_accepting_new_patients':'Indicates provider is not accepting new patients'}

def norm(s):return re.sub(r'[^a-z0-9]','',unicodedata.normalize('NFKC',s).lower())
def load_native(inv):return [json.loads(s)for s in gzip.open(ROOT/inv['native_path'],'rt')]

def model(inv,imgs):
    ns=load_native(inv);byp=collections.defaultdict(list)
    for k,x in enumerate(ns):byp[x['page']].append({**x,'index':k})
    imagepage=collections.defaultdict(list)
    for i,x in enumerate(imgs):imagepage[x['page']].append({**x,'image_index':i})
    legend={}
    for flag,text in LEGEND.items():
        found=[k for k,x in enumerate(ns)if x['page']==7 and norm(x['text'])==norm(text)]
        assert len(found)==1,(flag,found)
        legend[flag]={'page':7,'native_node':found[0],'raw':ns[found[0]]['text']}
    stream=[];page_scope=[];headers=[];section_conditions=collections.defaultdict(list)
    for pg,xs in byp.items():
        hs=[x for x in xs if x['top']<50 and x['font']['size']=='18']
        section=' '.join(x['text']for x in hs)
        if section not in SECTIONS:continue
        county=[x for x in xs if x['top']>=80 and x['bold']and x['font']['size']=='14'and x['font']['color']=='#ffffff']
        total=[x for x in xs if re.fullmatch(r'Total Listings:\s*\d+',x['text'])]
        assert len(total)==1 and len(county)==1,(pg,section,county,total)
        top=county[0]['top']+18
        intro=[x['index']for x in xs if 60<x['top']<county[0]['top']-10 and not x['text'].startswith(('Total Listings:','See icon guide'))]
        section_conditions[section]+=intro
        scope={'page':pg,'section_raw':section,'section_nodes':[x['index']for x in hs],'county_raw':county[0]['text'],'body_top':top,
             'county_node':county[0]['index'],'advertised_total':int(total[0]['text'].split(':')[1]),'total_node':total[0]['index']}
        page_scope.append(scope)
        for col,(lo,hi)in enumerate([(40,217.5),(217.5,395.5),(395.5,580)]):
            events=[{'kind':'text','top':x['top'],'left':x['left'],'native':x,'scope':scope,'column':col}for x in xs if top<=x['top']<731 and lo<=x['left']<hi]
            events += [{'kind':'image','top':x['geometry']['top'],'left':x['geometry']['left'],'image':x,'scope':scope,'column':col}for x in imagepage[pg]if top<=x['geometry']['top']<731 and lo<=x['geometry']['left']<hi]
            stream+=sorted(events,key=lambda e:(e['top'],e['kind']=='image',e['left']))
    records=[];context=[];image_context=[];current=None;specialty=[];lastscope=None;lasthead=None
    def finish():
        nonlocal current
        if current:
            current['name_raw']=' '.join(ns[k]['text']for k in current['name_nodes']);records.append(current);current=None
    for e in stream:
        scope=e['scope'];sig=(scope['section_raw'],scope['county_raw'])
        if sig!=lastscope:
            if lastscope is not None and scope['section_raw']!=lastscope[0]:finish()
            specialty=[];lastscope=sig;lasthead=None
        if e['kind']=='image':
            if current:current['image_indices'].append(e['image']['image_index'])
            else:image_context.append(e['image']['image_index'])
            continue
        x=e['native'];n=x['index']
        if x['bold']and x['font']['size']=='14':
            continued_incomplete=current and current['page']!=x['page']and not any(CITY.fullmatch(ns[k]['text'])for k in current['body_nodes'])
            if not continued_incomplete and not re.search(r'\bcont\.$',x['text']):finish()
            if lasthead and lasthead['page']==x['page']and lasthead['column']==e['column']and 0<x['top']-lasthead['top']<=18:specialty.append(n)
            else:specialty=[n]
            lasthead={**x,'column':e['column']};context.append(n);continue
        is_name=x['bold']and x['font']['size']=='12'and x['font']['family']=='Calibri'
        if is_name:
            if current and not current['body_nodes']:
                prior=ns[current['name_nodes'][-1]]
                if prior['page']==x['page']and current['column']==e['column']and prior['left']==x['left']and 0<x['top']-prior['top']<=17:
                    current['name_nodes'].append(n);continue
            finish()
            current={'id':inv['sha256']+':listing:'+str(n),'document_sha256':inv['sha256'],'page':x['page'],'column':e['column'],
                'name_nodes':[n],'body_nodes':[],'image_indices':[],'section_raw':scope['section_raw'],'section_nodes':scope['section_nodes'],
                'county_raw':scope['county_raw'],'county_node':scope['county_node'],'specialty_nodes':specialty[:],
                'benefit_year':2026,'published_as_of':inv['published_as_of'],'npi':None,'provider_relationship_period':None,
                'personal_participation_verified':False}
        elif current:current['body_nodes'].append(n)
        else:context.append(n)
        if not(x['bold']and x['font']['size']=='14'):lasthead=None
    finish()
    for r in records:
        body=r['body_nodes'];r['body_raw']=[ns[k]['text']for k in body];r['specialty_raw']=' '.join(ns[k]['text']for k in r['specialty_nodes'])or None
        r['section_conditions']=[{'raw':ns[k]['text'],'node':k,'page':ns[k]['page']}for k in section_conditions[r['section_raw']]]
        ids=[{'value':PID.fullmatch(ns[k]['text'])[1],'raw':ns[k]['text'],'node':k}for k in body if PID.fullmatch(ns[k]['text'])]
        r['publisher_identifiers']=ids;r['publisher_provider_id']=ids[0]['value']if len(ids)==1 else None
        r['state']='published_provider_site_listing; no personal participation guarantee'if len(ids)==1 else'published_name_block; identifier_missing_or_ambiguous'
        r['gender_raw']=[{'raw':ns[k]['text'],'node':k}for k in body if ns[k]['text'].startswith('Gender:')]
        r['phones_raw']=[{'raw':ns[k]['text'],'node':k}for k in body if PHONE.fullmatch(ns[k]['text'])]
        r['websites_raw']=[{'raw':ns[k]['text'],'node':k}for k in body if re.match(r'^(?:https?://|www\.)',ns[k]['text'],re.I)]
        r['hours_raw']=[{'raw':ns[k]['text'],'node':k}for k in body if HOURS.match(ns[k]['text'])]
        r['PCMH_raw']=[{'raw':ns[k]['text'],'node':k}for k in body if ns[k]['text']=='PCMH']
        r['tiers_raw']=[{'raw':ns[k]['text'],'node':k}for k in body if re.fullmatch(r'Tier\s*[12]',ns[k]['text'])]
        r['addresses']=[];firststreet=None
        for j,k in enumerate(body):
            value=ns[k]['text'];citynodes=[k];m=CITY.fullmatch(value)
            if not m and re.search(r',\s*[A-Z]{2}$',value)and j+1<len(body)and ns[body[j+1]]['page']==ns[k]['page']:
                joined=value+' '+ns[body[j+1]]['text'];m=CITY.fullmatch(joined)
                if m:citynodes.append(body[j+1])
            if not m:continue
            street=[]
            for prev in reversed(body[max(0,j-4):j]):
                t=ns[prev]['text']
                if PID.fullmatch(t)or PHONE.fullmatch(t)or t.startswith(('Gender:','Language:','Languages:'))or HOURS.match(t):break
                street.insert(0,prev)
                if STREET.match(t):break
            if not street or not STREET.match(ns[street[0]]['text']):street=[]
            if street and firststreet is None:firststreet=street[0]
            r['addresses'].append({'street_raw':' '.join(ns[i]['text']for i in street)or None,'city_raw':m[1],'state_raw':m[2],'postal_raw':m[3],
                 'street_nodes':street,'city_nodes':citynodes,'city_line_raw':' '.join(ns[i]['text']for i in citynodes),
                 'state':'literal_source_site'if street else'city_only_source_or_unresolved_street'})
        before=[]
        if firststreet is not None:
            stop=body.index(firststreet)
            for k in body[:stop]:
                t=ns[k]['text']
                if PID.fullmatch(t)or t.startswith('Gender:')or re.fullmatch(r'Tier\s*[12]',t):continue
                before.append(k)
        r['practice_raw']=' '.join(ns[k]['text']for k in before)or None;r['practice_nodes']=before
        languages=[]
        for j,k in enumerate(body):
            if not re.match(r'^Languages?:',ns[k]['text']):continue
            nodes=[k]
            for nxt in body[j+1:]:
                t=ns[nxt]['text']
                if HOURS.match(t)or PHONE.fullmatch(t)or STREET.match(t)or CITY.fullmatch(t)or re.match(r'^(?:https?://|www\.|PCMH|Gender:|Provider ID:|Tier)',t):break
                nodes.append(nxt)
            languages.append({'raw':' '.join(ns[x]['text']for x in nodes),'nodes':nodes})
        r['languages_raw']=languages
        r['published_icons']=[]
        for i in r['image_indices']:
            x=imgs[i];flag=ICON_MAP.get(x['asset_key'])
            r['published_icons'].append({'image_index':i,'asset_key':x['asset_key'],'flag':flag,'legend':legend.get(flag),
                 'state':'published_symbol_present'if flag else'uninterpreted_source_image_retained'})
        # Lack of a symbol is not evidence of a negative fact or open panel.
        r['symbol_flags']={flag:True if any(x['flag']==flag for x in r['published_icons'])else None for flag in LEGEND}
        consumed=set(r['practice_nodes'])|{x['node']for field in ['publisher_identifiers','gender_raw','phones_raw','websites_raw','hours_raw','PCMH_raw','tiers_raw']for x in r[field]}
        consumed|={k for a in r['addresses']for k in a['street_nodes']+a['city_nodes']}
        consumed|={k for l in r['languages_raw']for k in l['nodes']}
        r['other_source_text']=[{'raw':ns[k]['text'],'node':k}for k in body if k not in consumed]
        r['physical_Collier_verified_from_city_alone']=False
        r['printed_Collier_county_heading']=r['county_raw'].lower()=='collier'
    pids={x['index']for e in stream if e['kind']=='text'and PID.fullmatch((x:=e['native'])['text'])}
    allpids={k for k,x in enumerate(ns)if PID.fullmatch(x['text'])and x['page']!=7}
    assert pids==allpids,('Unaccounted publisher IDs outside medical pages',inv['sha256'],sorted(allpids-pids))
    totals=[]
    for section in sorted(SECTIONS):
        scopes=[s for s in page_scope if s['section_raw']==section]
        rr=[r for r in records if r['section_raw']==section]
        vals=sorted({s['advertised_total']for s in scopes})
        totals.append({'section_raw':section,'advertised_totals':vals,'listing_blocks':len(rr),'identifier_occurrences':sum(len(r['publisher_identifiers'])for r in rr),
             'exact_total_agreement':vals==[len(rr)],'source_total_nodes':[s['total_node']for s in scopes]})
    return records,{'document_sha256':inv['sha256'],'medical_pages':[s['page']for s in page_scope],'page_scopes':page_scope,
        'medical_text_nodes':sum(e['kind']=='text'for e in stream),'medical_images':sum(e['kind']=='image'for e in stream),
        'context_nodes':context,'image_context_indices':image_context,'publisher_ID_population':len(allpids),'totals':totals,
        'listing_blocks':len(records),'Collier_heading_listing_blocks':sum(r['printed_Collier_county_heading']for r in records),'legend':legend}

def main():
    assert_open();invs=json.loads((BASE/'document-inventory.json').read_text());images=collections.defaultdict(list)
    for s in gzip.open(BASE/'image-occurrences.jsonl.gz','rt'):
        r=json.loads(s);images[r['document_sha256']].append(r)
    db=sqlite3.connect('file:'+str(PARENT/'providers.sqlite3')+'?mode=ro',uri=True)
    targets=[{'offering_id':r[0],'name':r[1]}for r in db.execute("SELECT id,name FROM offerings WHERE id LIKE '2026:H1032:%'")];assert len(targets)==6
    bindings=[];accounts=[];counts=collections.Counter();examples=[]
    with gzip.open(BASE/'wellcare-records.jsonl.gz','wt')as out:
        for inv in invs:
            text=(ROOT/inv['text_path']).read_text().split('\f')[0]
            for name in inv['cover_plan_names']:
                matches=[t for t in targets if t['name']==name];assert len(matches)==1,(name,matches)
                matches[0]=dict(matches[0]);binding={**matches[0],'document_sha256':inv['sha256'],'source_plan_name':name,'cover_page':1,
                    'name_span':list(re.search(re.escape(name),text).span()),'Collier_span':list(re.search(r'\bCollier\b',text).span()),
                    'benefit_year':2026,'published_as_of':inv['published_as_of'],'CMS_ID_printed_in_directory':False,
                    'state':'same-year exact printed plan name and explicit Collier scope; unique offering in pinned Collier L02 inventory; CMS ID bridged, not printed',
                    'partial_network_reference':True,'personal_participation_verified':False}
                bindings.append(binding)
            rs,acct=model(inv,images[inv['sha256']]);accounts.append(acct)
            for r in rs:
                out.write(json.dumps(r,ensure_ascii=False)+'\n');counts['listing_blocks']+=1;counts['publisher_ID_occurrences']+=len(r['publisher_identifiers'])
                counts['source_sites']+=len(r['addresses']);counts['Collier_heading_listing_blocks']+=r['printed_Collier_county_heading']
                if not r['addresses']:counts['no_source_address_in_bounded_listing']+=1
                for a in r['addresses']:
                    if a['street_raw']is None:counts['unresolved_source_street']+=1
                for k,val in r['symbol_flags'].items():
                    if val:counts['symbol_'+k]+=1
                counts['uninterpreted_medical_images']+=sum(x['flag']is None for x in r['published_icons'])
                if r['state'].startswith('published_name_block'):counts['missing_or_ambiguous_publisher_identifier']+=1
    assert {b['offering_id']for b in bindings}=={t['offering_id']for t in targets}
    write(BASE/'plan-directory-bindings.json',bindings);write(BASE/'extraction-accounting.json',accounts)
    write(BASE/'normalization-summary.json',dict(counts,unique_directories=4,target_offerings=len(bindings),whole_network_complete=False,
        all_source_header_totals_reconciled=all(t['exact_total_agreement']for a in accounts for t in a['totals'])))
    write(BASE/'icon-legend-mapping.json',{'asset_to_flag':ICON_MAP,'legend_meanings':LEGEND,'interpretation':'True denotes printed symbol; null means not indicated. No open-panel, no-access or non-Medicaid negative inferred from a missing symbol.',
        'QA':'render/actual-mask-QA.png; render/wellcare-legend.png','hard_mask_required':True})
    print((BASE/'normalization-summary.json').read_text(),flush=True)
    print(json.dumps([{'doc':a['document_sha256'][:8],'totals':[{k:v for k,v in t.items()if k!='source_total_nodes'}for t in a['totals']if not t['exact_total_agreement']]}for a in accounts if any(not t['exact_total_agreement']for t in a['totals'])]),flush=True)

if __name__=='__main__':main()
