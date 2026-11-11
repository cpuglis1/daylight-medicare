"""Retain complete EOC chart rows and conditions for all 47 documented offerings.

Section boundaries use observed standard EOC service headings, not money tokens.
Text remains source-native. Shared section association is not child-benefit
corroboration. Every original page is hash-addressed and retained in r1.
"""
import collections,gzip,json,pathlib,re
from l03_reference_build import DATA,sha,dump
from l03_reconcile import OUT,R1,readlines,writelines

HEADINGS={
'abdominal_aortic':'Abdominal aortic aneurysm screening',
'acupuncture':'Acupuncture',
'ambulance':'Ambulance services',
'annual_wellness':'Annual wellness visit',
'blood':'Blood',
'bone_mass':'Bone mass measurement',
'cardiac_rehab':'Cardiac rehabilitation',
'cardiovascular_behavior':'Cardiovascular disease',
'cardiovascular_screen':'Cardiovascular screening',
'cervical_screen':'Cervical and vaginal cancer screening',
'chiropractic':'Chiropractic',
'colorectal_screen':'Colorectal cancer screening',
'dental':'Dental services',
'depression_screen':'Depression screening',
'diabetes_screen':'Diabetes screening',
'diabetes_training':'Diabetes self-management',
'diabetes_supplies':'Diabetes monitoring supplies',
'dme':'Durable medical equipment',
'emergency':'Emergency care',
'fitness':'Fitness',
'hearing':'Hearing services',
'hepatitis_c':'Hepatitis C screening',
'hiv':'HIV screening',
'home_health':'Home health agency care',
'home_infusion':'Home infusion therapy',
'hospice':'Hospice care',
'immunizations':'Immunizations',
'inpatient':'Inpatient hospital care',
'inpatient_mental':'Inpatient services in a psychiatric hospital',
'inpatient_noncovered':'Inpatient stay: Covered services',
'lung_screen':'Lung cancer screening',
'mammography':'Mammography screening',
'nutrition':'Medical nutrition therapy',
'mpp':'Medicare Diabetes Prevention Program',
'obesity':'Obesity screening',
'opioid':'Opioid treatment program',
'outpatient_diagnostics':'Outpatient diagnostic tests',
'outpatient_hospital':'Outpatient hospital services',
'observation':'Outpatient hospital observation',
'outpatient_mental':'Outpatient mental health care',
'outpatient_rehab':'Outpatient rehabilitation services',
'outpatient_substance':'Outpatient substance abuse services',
'outpatient_substance2':'Outpatient substance use',
'outpatient_surgery':'Outpatient surgery',
'partial_hospital':'Partial hospitalization',
'physician':'Physician/Practitioner services',
'podiatry':'Podiatry services',
'prostate_screen':'Prostate cancer screening',
'prosthetics':'Prosthetic',
'pulmonary_rehab':'Pulmonary rehabilitation',
'renal':'Services to treat kidney disease',
'sti_screen':'Sexually transmitted infections',
'snf':'Skilled nursing facility',
'smoking':'Smoking and tobacco use cessation',
'exercise_pad':'Supervised exercise therapy',
'transport':'Transportation',
'urgent':'Urgently needed services',
'vision':'Vision care',
'welcome':'Welcome to Medicare',
'partb_drugs':'Medicare Part B',
'meals':'Home delivered meals',
'meals2':'Meal benefit',
'otc':'Over-the-counter',
'pers':'Personal emergency response',
'support':'In-home support',
'glaucoma':'Glaucoma screening',
'wig':'Wigs',
'weight':'Weight management',
'caregiver':'Support for caregivers',
'home_safety':'Home and bathroom safety',
'palliative':'Palliative',
}
CAT_SECTION={
'1a':['inpatient'],'1a1':['inpatient'],'1b':['inpatient_mental'],'2':['snf'],
'3':['cardiac_rehab','pulmonary_rehab','outpatient_rehab'],'3-1':['cardiac_rehab'],'3-2':['cardiac_rehab'],'3-3':['pulmonary_rehab'],'3-4':['exercise_pad'],
'4a':['emergency'],'4b':['urgent'],'4c':['emergency','urgent','ambulance'],'4c1':['emergency'],'4c2':['urgent'],'4c3':['ambulance'],
'5a':['partial_hospital'],'5b':['partial_hospital'],'6':['home_health'],'7a':['physician'],'7b':['chiropractic'],'7b1':['chiropractic'],'7c':['outpatient_rehab'],'7d':['physician'],'7e':['outpatient_mental'],'7e1':['outpatient_mental'],'7e2':['outpatient_mental'],'7f':['podiatry'],'7g':['physician'],'7h':['outpatient_mental'],'7h1':['outpatient_mental'],'7h2':['outpatient_mental'],'7i':['outpatient_rehab'],'7j':['physician'],'7k':['opioid'],
'8a':['outpatient_diagnostics'],'8a1':['outpatient_diagnostics'],'8a2':['outpatient_diagnostics'],'8b':['outpatient_diagnostics'],'8b1':['outpatient_diagnostics'],'8b2':['outpatient_diagnostics'],'8b3':['outpatient_diagnostics'],
'9a1':['outpatient_hospital','outpatient_surgery'],'9a2':['observation'],'9b':['outpatient_surgery'],'9c':['outpatient_substance','outpatient_substance2'],'9c1':['outpatient_substance','outpatient_substance2'],'9c2':['outpatient_substance','outpatient_substance2'],'9d':['blood'],
'10a':['ambulance'],'10a1':['ambulance'],'10a2':['ambulance'],'10b1':['transport'],
'11a':['dme'],'11b':['prosthetics'],'11b1':['prosthetics'],'11b2':['prosthetics'],'11c':['diabetes_supplies','diabetes_training'],'11c1':['diabetes_supplies','diabetes_training'],'11c2':['diabetes_supplies','diabetes_training'],'12':['renal'],
'13a':['acupuncture'],'13b':['otc'],'13c':['meals','meals2'],
'14a':['annual_wellness','welcome','immunizations','abdominal_aortic','bone_mass','cardiovascular_behavior','cardiovascular_screen','cervical_screen','colorectal_screen','depression_screen','diabetes_screen','hepatitis_c','hiv','lung_screen','mammography','obesity','prostate_screen','sti_screen','smoking'],
'14b':['physician'],'14c4':['fitness'],'14c8':['home_safety'],'14c11':['pers'],'14c15':['wig'],'14c16':['weight'],'14c21':['support'],'14c22':['caregiver'],'14d':['renal'],
'14e1':['glaucoma','vision'],'14e2':['diabetes_training'],'14e4':['prostate_screen'],'14e5':['welcome'],
'15':['partb_drugs'],'15-1':['partb_drugs'],'15-2':['partb_drugs'],'15-3':['partb_drugs']}
for cat in ['16a','16b','16c']+[f'16b{i}' for i in range(1,7)]+[f'16c{i}' for i in range(1,11)]:CAT_SECTION[cat]=['dental']
for cat in ['17a','17a1','17a2','17b']+[f'17b{i}' for i in range(1,6)]:CAT_SECTION[cat]=['vision']
for cat in ['18a','18a1','18a2','18b','18c']+[f'18b{i}' for i in range(1,5)]:CAT_SECTION[cat]=['hearing']

def clean(s):return re.sub(r'\s+',' ',s.replace('‑','-').replace('’',"'")).strip(' *•\t')

def extract(doc,pages):
 rows=[];current=None;chartpages=[];preamble=[]
 patterns=[(key,re.compile('^'+re.escape(clean(label)),re.I)) for key,label in HEADINGS.items()]
 for pg in pages:
  text=pg['text'];ls=text.splitlines()
  if not (re.search(r'Chapter\s*4[. ]',text,re.I) and re.search(r'Medical Benefits Chart|Benefits Chart',text,re.I)):continue
  if not re.search(r'Covered Service|Services that are|What you pay',text,re.I):continue
  chartpages.append(pg['pdf_page'])
  costcol=next((l.lower().index('what you pay') for l in ls if 'what you pay' in l.lower()),None)
  if costcol is None:costcol=next((l.lower().index('what you') for l in ls if 'what you' in l.lower()),None)
  for lineno,line in enumerate(ls,1):
   s=clean(line);left=clean(line[:costcol]) if costcol and costcol>25 else s
   # Heading must start the service column. A cross-reference in body text
   # cannot create a new row. Continuations keep the same source service.
   label=next((key for key,pat in patterns if pat.match(left)),None)
   is_heading=label is not None and len(line)-len(line.lstrip())<10 and len(left)<115
   if is_heading:
    if current and current['section']==label and ('continued' in left.lower()):pass
    else:
     if current:rows.append(current)
     current={'id':doc['sha256']+':chart:'+str(len(rows)),'document_sha256':doc['sha256'],'section':label,'source_heading':left,'fragments':[],'source_native':True,'consumer_corroborated':False}
   frag={'pdf_page':pg['pdf_page'],'line':lineno,'page_text_sha256':pg['text_sha256'],'text':line}
   if current:current['fragments'].append(frag)
   else:preamble.append(frag)
 if current:rows.append(current)
 for row in rows:
  text='\n'.join(f['text'] for f in row['fragments']);row['pages']=sorted({f['pdf_page'] for f in row['fragments']});row['text_sha256']=sha(text.encode())
  row['condition_tags']=[tag for tag,pat in [('authorization',r'prior author|preauthor|precertif'),('referral',r'referral'),('network',r'in.network|out.of.network|network provider'),('deductible',r'deductible'),('frequency_or_period',r'per year|each year|every year|per month|each month|every two|every three|every 2|every 3|per quarter|calendar year|once|twice'),('limits',r'limited|limit|maximum|up to|unlimited'),('qualification',r'eligible|eligibility|qualif|chronic|medical necessity|medically necessary'),('waiver_or_exception',r'waiv|unless|except|if you|if the'),('exclusions',r'not cover|excluded|exclusion|not included') ] if re.search(pat,text,re.I)]
 return {'document_sha256':doc['sha256'],'chart_pages':chartpages,'preamble':preamble,'rows':rows}

def run():
 catalog={x['sha256']:x for x in json.loads((R1/'carrier-document-catalog.json').read_text())};matrix=json.loads((R1/'plan-document-matrix.json').read_text());byhash=collections.defaultdict(list)
 for p in readlines(R1/'carrier-pages.jsonl.gz'):byhash[p['document_sha256']].append(p)
 extracted={};index=[];conditions=[]
 for m in matrix:
  d=m['document_matches']['EOC']
  if d['status']!='matched_for_research':continue
  h=d['sha256']
  if h not in extracted:extracted[h]=extract(catalog[h],byhash[h])
  e=extracted[h]
  index.append({'offering_id':m['offering_id'],'document_sha256':h,'chart_pages':e['chart_pages'],'rows':len(e['rows']),'sections':sorted({r['section'] for r in e['rows']}),'extraction_status':'complete_retained_chart_page_scan; heading association not field approval'})
  for r in e['rows']:
   conditions.append({'offering_id':m['offering_id'],**r})
 writelines(OUT/'carrier-chart-rows.jsonl.gz',conditions);dump(OUT/'carrier-chart-inventory.json',index)
 # Every service record receives a chart-row binding or an explicit gap.
 rowmap=collections.defaultdict(list)
 for r in conditions:rowmap[(r['offering_id'],r['section'])].append(r['id'])
 links=[]
 for r in readlines(OUT/'benefit-records.jsonl.gz'):
  sections=CAT_SECTION.get(r['category_code'],[]);ids=[i for s in sections for i in rowmap[(r['offering_id'],s)]]
  links.append({'benefit_record_id':r['id'],'offering_id':r['offering_id'],'category_code':r['category_code'],'EOC_chart_row_ids':ids,'binding':'service_family_not_all_child_fields' if ids else 'no_exact_chart_heading_binding','required_disposition':'source_native_conditions_attached; every flat claim requires field decision','accepted':False})
 writelines(OUT/'benefit-chart-bindings.jsonl.gz',links)
 stats={'documented_offerings_scanned':len(index),'distinct_EOCs':len(extracted),'chart_pages_scanned':sum(len(x['chart_pages']) for x in index),'source_native_chart_rows':len(conditions),'service_records_with_chart_family_binding':sum(bool(x['EOC_chart_row_ids']) for x in links),'full_semantic_corroboration_from_heading_association':0}
 dump(OUT/'chart-summary.json',stats);print(json.dumps(stats,indent=2));return stats
if __name__=='__main__':run()
