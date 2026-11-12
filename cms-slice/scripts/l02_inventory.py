#!/usr/bin/env python3
"""National L02 research inventory. Immutable, offline, whole-population builds.

Raw evidence stays in hashed archives. Row ordinals/JSON members/cell ranges bind
normalized records to the original bytes. No economics, customer facts or AI.
"""
import argparse
from collections import Counter, defaultdict
import csv
from datetime import date
import io
import json
from pathlib import Path
import re
import resource
import sqlite3
import time
import xml.etree.ElementTree as ET
import zipfile
import cms_slice as cms

REPO=cms.ROOT.parent
SPEC=REPO/'docs/data/l02-ma-availability-2026-10-25'
VERSION='l02-parser-v1'
POLICY='l02-scope-v1'
CLAIM='l02-published-observation-v1'
IN_SCOPE={'MA','MA-PD','SNP'}
AREA_COLUMNS=['Contract ID','Organization Name','Organization Type','Plan Type','Partial','EGHP','SSA','FIPS','County','State','Notes']
FORBIDDEN=re.compile(r'commission|compensation|payout|appointment|referral|conversion|lifetime.?value|lead.?score|revenue|sponsor',re.I)

def canonical(value): return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False)
def digest(value): return cms.sha256(canonical(value).encode())
def clean_economic_fields(fields):
 if any(FORBIDDEN.search(str(k)) for k in fields): raise cms.SourceError('Commercial field rejected at ingestion boundary')
def key_id(year,contract,plan,segment): return ':'.join(cms.identity(year,contract,plan,segment))
def rows_csv(raw, columns):
 r=csv.DictReader(io.StringIO(raw.decode('utf-8-sig'),newline=''))
 clean_economic_fields(r.fieldnames or [])
 if r.fieldnames!=columns: raise cms.SourceError('Unreviewed source layout')
 for ordinal,row in enumerate(r,2):yield ordinal,row
def landscape_row(row,year,schema):
 clean_economic_fields(row)
 if None in row or any(v is None for v in row.values()):raise cms.SourceError('Malformed CSV row')
 key=key_id(*(row[c] for c in cms.KEY_COLUMNS))
 if key.split(':')[0]!=year:raise cms.SourceError('Mixed/wrong source benefit year')
 cp='ContractPlanID' if 'ContractPlanID' in row else 'Contract Plan ID'
 cps='ContractPlanSegmentID' if 'ContractPlanSegmentID' in row else 'Contract Plan Segment ID'
 if row[cp]!=row['Contract ID']+'_'+row['Plan ID'] or row[cps]!=row[cp]+'_'+row['Segment ID']:raise cms.SourceError('Composite ID conflict')
 for field,values in schema['flags'].items():
  if row[field] not in values:raise cms.SourceError('Unreviewed restriction code: '+field)
 if row['Contract Category Type'] not in schema['categories'] or row['Plan Type'] not in schema['plan_types']:raise cms.SourceError('Unreviewed category/type')
 route='L02' if row['Contract Category Type'] in IN_SCOPE else 'L04' if row['Contract Category Type']=='PDP' else 'L14'
 if int(row['Plan ID'])>=800:route='employer_group_out_of_scope'
 return key,route

def xlsx_rows(raw,member):
 """Read source cell values preserving string-encoded plan IDs and sheet locators."""
 ns={'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
 with zipfile.ZipFile(io.BytesIO(raw)) as z:
  strings=[''.join(n.itertext()) for n in ET.fromstring(z.read('xl/sharedStrings.xml')).findall('m:si',ns)]
  for row in ET.fromstring(z.read(member)).findall('m:sheetData/m:row',ns):
   cells={}
   for c in row:
    col=re.sub(r'\d','',c.attrib['r']);v=c.findtext('m:v','',ns)
    if c.attrib.get('t')=='s':v=strings[int(v)]
    cells[col]=v
   yield int(row.attrib['r']),cells

def geography():
 old=cms.load_json(cms.ROOT/'data-sources/release.json')['artifacts']['counties']
 path=cms.ROOT/old['path']
 if cms.file_hash(path)!=old['sha256']:raise cms.SourceError('Geography hash mismatch')
 with zipfile.ZipFile(path) as z:
  raw=z.read(old['member']);reader=csv.DictReader(io.StringIO(raw.decode()),delimiter='|')
  names={};counties={}
  for r in reader:
   n=re.sub(r' (County|Parish|Borough|Census Area|Municipio|Municipality)$','',r['NAME'])
   names.setdefault((r['USPS'],n),set()).add(r['GEOID']);counties[r['GEOID']]={'state':r['USPS'],'name':r['NAME']}
 return names,counties,{**old,'member_sha256':cms.sha256(raw)}

def source_path(acq,spec):
 path=Path(spec.get('local_path','')) if spec.get('local_path') else acq/'raw'/spec['sha256']
 if not path.is_file() or path.stat().st_size!=spec['bytes'] or cms.file_hash(path)!=spec['sha256']:raise cms.SourceError('Source bytes/hash mismatch: '+str(path))
 return path

def export(db,path,sql,args=()):
 cursor=db.execute(sql,args)
 with path.open('w',newline='') as f:
  writer=csv.writer(f);writer.writerow([x[0] for x in cursor.description]);writer.writerows(cursor)

def status_at(actions,on_date):
 """Actions affect only their own dimension and exact effective interval.

 An unended penalty never becomes suspension. Release requires a target action ID;
 missing/contradictory effective evidence stays unresolved. No event means unknown.
 """
 day=date.fromisoformat(on_date);state=defaultdict(list);byid={a['id']:a for a in actions}
 released=set()
 for a in actions:
  if a.get('kind')=='release' and a.get('effective_from') and date.fromisoformat(a['effective_from'])<=day:
   if a.get('releases') in byid:released.add(a['releases'])
 for a in actions:
  if a['id'] in released or a['kind']=='release':continue
  start=a.get('effective_from');end=a.get('effective_to')
  if not start:state['unresolved'].append(a['id']);continue
  if date.fromisoformat(start)>day or (end and day>date.fromisoformat(end)):continue
  state[a['kind']].append(a['id'])
 return dict(state) or {'enrollment_status':'unknown'}

def build(acquisition,out,year='2026',scopes=('12021','12071','36061'),supplement=None):
 start=time.monotonic();acq=Path(acquisition).resolve();out=Path(out).resolve()
 code_hash=cms.file_hash(__file__);schema_hash=cms.file_hash(SPEC/'schemas.json');helper_hash=cms.file_hash(cms.__file__)
 if out.exists():raise cms.SourceError('Immutable build directory already exists')
 manifest=cms.load_json(acq/'source-manifest.json');schema=cms.load_json(SPEC/'schemas.json')['years'][year]
 if manifest['sources']['landscape'].get('benefit_year')!=year:raise cms.SourceError('Manifest benefit year mismatch')
 # Verify every referenced artifact before creating any apparently usable output.
 paths={k:source_path(acq,s) for k,s in manifest['sources'].items() if s.get('sha256')}
 if supplement:
  supplement=Path(supplement).resolve();sm=cms.load_json(supplement/'source-manifest.json')
  for s in sm['sources']:
   if s['status']=='acquired':
    if cms.file_hash(supplement/'raw'/s['sha256'])!=s['sha256'] or cms.file_hash(supplement/'extracted'/(s['sha256']+'.txt'))!=s['extracted_sha256']:raise cms.SourceError('Supplemental evidence hash mismatch')
  manifest['supplemental']={'path':str(supplement),'manifest_sha256':cms.file_hash(supplement/'source-manifest.json'),'interpretation_sha256':cms.file_hash(SPEC/'supplemental-interpretation.json'),'sources':sm}
 names,counties,geo=geography()
 if any(s not in counties for s in scopes):raise cms.SourceError('Unknown county FIPS')
 out.mkdir(parents=True);db=sqlite3.connect(out/'inventory.sqlite3');db.row_factory=sqlite3.Row
 (out/'code').mkdir()
 for filename in ['l02_inventory.py','l02_service.py','l02_refresh.py','cms_slice.py']:(out/'code'/filename).write_bytes((Path(__file__).parent/filename).read_bytes())
 (out/'code/schemas.json').write_bytes((SPEC/'schemas.json').read_bytes())
 db.executescript('''
 CREATE TABLE offerings(id TEXT PRIMARY KEY,year TEXT,contract TEXT,plan TEXT,segment TEXT,category TEXT,route TEXT,parent TEXT,legal_name TEXT,marketing TEXT,name TEXT,plan_type TEXT,drug TEXT,snp TEXT,snp_type TEXT,sanction TEXT,restriction_raw TEXT,locator TEXT);
 CREATE TABLE areas(id INTEGER PRIMARY KEY,offering_id TEXT,contract TEXT,county_fips TEXT,state TEXT,county TEXT,grain TEXT,extent TEXT,source TEXT,locator TEXT,raw_json TEXT);
 CREATE INDEX county_idx ON areas(county_fips,source); CREATE INDEX offering_idx ON areas(offering_id);
 CREATE INDEX contract_county_idx ON areas(contract,county_fips,source);
 CREATE TABLE ledger(source TEXT,ordinal INTEGER,offering_id TEXT,route TEXT,state TEXT,county TEXT,county_fips TEXT,disposition TEXT);
 CREATE TABLE quarantine(source TEXT,locator TEXT,offering_id TEXT,state TEXT,county TEXT,reason TEXT,raw_json TEXT);
 CREATE TABLE secondary(source TEXT,id TEXT,contract TEXT,plan TEXT,segment TEXT,classification TEXT,raw_json TEXT,locator TEXT,PRIMARY KEY(source,id));
 CREATE TABLE differences(source TEXT,direction TEXT,offering_id TEXT,county_fips TEXT,field TEXT,primary_value TEXT,secondary_value TEXT,impact TEXT,disposition TEXT);
 CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT);
 ''')
 accounting={};members={};schema_report={};categories=Counter();seen=set()
 with zipfile.ZipFile(paths['landscape']) as z:
  n=next(n for n in z.namelist() if n.endswith('.csv'));raw=z.read(n);members['landscape']={'member':n,'sha256':cms.sha256(raw)}
  readme=next(n for n in z.namelist() if n.lower().endswith('.txt'));(out/'landscape-readme.txt').write_bytes(z.read(readme))
  total=quarantined=0
  for ordinal,row in rows_csv(raw,schema['columns']):
   total+=1;key=None
   locator=canonical({'source':'landscape','member':n,'record_ordinal':ordinal,'member_sha256':members['landscape']['sha256']})
   try:
    key,route=landscape_row(row,year,schema)
    obs=(key,row['State Territory Abbreviation'],row['County Name'])
    if obs in seen:raise cms.SourceError('Duplicate offering/geography within landscape snapshot')
    seen.add(obs)
    matches=names.get(obs[1:],set());fips=next(iter(matches)) if len(matches)==1 else None
    if row['County Name']=='All Counties':extent='statewide_published'
    elif 'Regional PPO' in row['Plan Type']:extent='regional_county_published_extent_unverified'
    else:extent='county_published_extent_unverified'
    if fips is None and row['County Name']!='All Counties':extent='unmapped_geography'
    fields=['Special Needs Plan (SNP) Indicator','SNP Type','SNP Institutional Type','SNP Institutional Category','Dual Eligible SNP (D-SNP) Integration Status','D-SNP Applicable Integrated Plan (AIP) Identifier','Chronic or Disabling Condition SNP (C-SNP) Condition Type','Medicare Zero-Dollar Cost Sharing D-SNP']
    record=(key,year,row['Contract ID'],row['Plan ID'],key.split(':')[3],row['Contract Category Type'],route,row['Parent Organization Name'],row['Contract Name'],row['Organization Marketing Name'],row['Plan Name'],row['Plan Type'],row['Part D Coverage Indicator'],row['Special Needs Plan (SNP) Indicator'],row['SNP Type'],row['Sanctioned Plan'],canonical({c:row.get(c) for c in fields}),locator)
    old=db.execute('SELECT * FROM offerings WHERE id=?',(key,)).fetchone()
    if old and tuple(old)[:-1]!=record[:-1]:
     db.execute('INSERT INTO differences VALUES(?,?,?,?,?,?,?,?,?)',('landscape','conflict',key,fips,'offering_fields',canonical(dict(old)),canonical(row),'material','R06 review; retained both raw observations'))
    db.execute('INSERT OR IGNORE INTO offerings VALUES('+','.join('?' for _ in record)+')',record)
    db.execute('INSERT INTO areas VALUES(NULL,?,?,?,?,?,?,?,?,?,?)',(key,row['Contract ID'],fips,obs[1],obs[2],'offering',extent,'landscape',locator,canonical({'segment_raw':row['Segment ID'],'MA Region Code':row['MA Region Code'],'MA Region':row['MA Region']})))
    db.execute('INSERT INTO ledger VALUES(?,?,?,?,?,?,?,?)',('landscape',ordinal,key,route,obs[1],obs[2],fips,'parsed'))
    categories[(row['Contract Category Type'],row['Plan Type'],route)]+=1
   except cms.SourceError as e:
    quarantined+=1;db.execute('INSERT INTO quarantine VALUES(?,?,?,?,?,?,?)',('landscape',locator,key,row.get('State Territory Abbreviation'),row.get('County Name'),str(e),canonical(row)))
    db.execute('INSERT INTO ledger VALUES(?,?,?,?,?,?,?,?)',('landscape',ordinal,key,'investigate',row.get('State Territory Abbreviation'),row.get('County Name'),None,'quarantined'))
  accounting['landscape']={'raw':total,'parsed':total-quarantined,'quarantined':quarantined}
 schema_report['landscape']=schema
 # Contract observations stay contract-grain, including employer-only/partial/blank nationwide notes.
 if 'contract-area' in paths:
  with zipfile.ZipFile(paths['contract-area']) as z:
   n=next(n for n in z.namelist() if n.endswith('.csv'));raw=z.read(n);members['contract-area']={'member':n,'sha256':cms.sha256(raw)}
   (out/'contract-area-readme.txt').write_bytes(z.read(next(n for n in z.namelist() if n.endswith('.txt'))))
   total=q=0
   for ordinal,r in rows_csv(raw,AREA_COLUMNS):
    total+=1;loc=canonical({'source':'contract-area','member':n,'record_ordinal':ordinal})
    if r['Partial'] not in {'','*'} or r['EGHP'] not in {'','*'} or (r['FIPS'] and not re.fullmatch(r'\d{5}',r['FIPS'])):
     q+=1;db.execute('INSERT INTO quarantine VALUES(?,?,?,?,?,?,?)',('contract-area',loc,None,r.get('State'),r.get('County'),'unreviewed geography/flag',canonical(r)));continue
    db.execute('INSERT INTO areas VALUES(NULL,?,?,?,?,?,?,?,?,?,?)',(None,r['Contract ID'],r['FIPS'] or None,r['State'],r['County'],'contract','partial' if r['Partial']=='*' else 'contract_county_only','contract-area',loc,canonical(r)))
   accounting['contract-area']={'raw':total,'parsed':total-q,'quarantined':q}
 # Every PBP payload is inspected, not just names or the successfully joined subset.
 if 'pbp' in paths:
  with zipfile.ZipFile(paths['pbp']) as z:
   total=q=0
   for n in sorted(z.namelist()):
    if n.endswith('/'):continue
    total+=1;raw=z.read(n);loc=canonical({'source':'pbp','member':n,'member_sha256':cms.sha256(raw)})
    try:
     d=json.loads(raw)
     if set(d)!={'contractYear','section','pbp'} or len(d['pbp'])!=1:raise cms.SourceError('Unreviewed PBP root/cardinality')
     p=d['pbp'][0];key=key_id(d['contractYear'],p['contractId'],p['planId'],p['segmentId'])
     if key.split(':')[0]!=year or cms.member_for(tuple(key.split(':')))!=n:raise cms.SourceError('PBP payload/filename/year conflict')
     c=p['planCharacteristics'];selected={k:c.get(k) for k in ['planName','planDeleted','planSegmentDeleted','isEmployerOnlyPlan','isOfferRx','isSnp','snpType','geographicName','segmentName','lastUpdatedAt']}
     db.execute('INSERT INTO secondary VALUES(?,?,?,?,?,?,?,?)',('pbp',key,p['contractId'],p['planId'],key.split(':')[3],c.get('snpType'),canonical(selected),loc))
    except (ValueError,KeyError,TypeError,sqlite3.IntegrityError) as e:
     q+=1;db.execute('INSERT INTO quarantine VALUES(?,?,?,?,?,?,?)',('pbp',loc,None,None,None,str(e),raw.decode('utf-8',errors='replace')[:2000]))
   accounting['pbp']={'raw':total,'parsed':total-q,'quarantined':q}
 if 'snp' in paths:
  with zipfile.ZipFile(paths['snp']) as z:
   n=next(n for n in z.namelist() if n.endswith('.xlsx'));raw=z.read(n);sheet='xl/worksheets/sheet6.xml';total=q=0
   rr=list(xlsx_rows(raw,sheet));headers=[rr[0][1].get(chr(65+i),'') for i in range(16)]
   if headers[:5]!=['Contract Number','Contract Name','Organization Type','Plan ID','SEGMENT_ID']:raise cms.SourceError('SNP layout changed')
   schema_report['snp']={'member':n,'worksheet':sheet,'headers':headers,'notes':'Employer-only plans omitted; Under-11 aggregated; enrollment absence cannot establish unavailable.'}
   for ordinal,cells in rr[1:]:
    total+=1;r={headers[i]:cells.get(chr(65+i),'') for i in range(16)};loc=canonical({'source':'snp','member':n,'worksheet':sheet,'row':ordinal})
    try:
     key=key_id(year,r['Contract Number'],r['Plan ID'],r['SEGMENT_ID'])
     db.execute('INSERT INTO secondary VALUES(?,?,?,?,?,?,?,?)',('snp',key,r['Contract Number'],r['Plan ID'],key.split(':')[3],r['Special Needs Plan Type'],canonical(r),loc))
    except (ValueError,sqlite3.IntegrityError) as e:
     q+=1;db.execute('INSERT INTO quarantine VALUES(?,?,?,?,?,?,?)',('snp',loc,None,None,None,str(e),canonical(r)))
   accounting['snp']={'raw':total,'parsed':total-q,'quarantined':q}
 # Whole national directional differences. Secondary-only is not silently promoted or assigned a county.
 for source in ['pbp','snp']:
  for r in db.execute('SELECT s.* FROM secondary s LEFT JOIN offerings o ON o.id=s.id WHERE s.source=? AND o.id IS NULL',(source,)).fetchall():
   db.execute('INSERT INTO differences VALUES(?,?,?,?,?,?,?,?,?)',(source,'secondary_only',r['id'],None,'identity',None,r['raw_json'],'suspected addition; geography/population unverified','R06 investigate; not availability'))
  condition="o.route='L02'"+ (" AND o.snp='Yes'" if source=='snp' else '')
  for r in db.execute('SELECT o.* FROM offerings o LEFT JOIN secondary s ON s.id=o.id AND s.source=? WHERE '+condition+' AND s.id IS NULL',(source,)).fetchall():
   db.execute('INSERT INTO differences VALUES(?,?,?,?,?,?,?,?,?)',(source,'primary_only',r['id'],None,'identity','landscape',None,'missing corroboration; retains offering','R06 investigate; not poor fit'))
  for r in db.execute('SELECT o.id,o.drug,o.snp,o.snp_type,s.raw_json FROM offerings o JOIN secondary s ON o.id=s.id WHERE s.source=?',(source,)).fetchall():
   other=json.loads(r['raw_json'])
   pairs=[('Part D','drug',other.get('isOfferRx')),('SNP','snp',other.get('isSnp'))] if source=='pbp' else [('SNP type','snp_type',other.get('Special Needs Plan Type'))]
   for field,col,value in pairs:
    if value is not None and r[col]!=value:db.execute('INSERT INTO differences VALUES(?,?,?,?,?,?,?,?,?)',(source,'conflict',r['id'],None,field,r[col],value,'material classification conflict','R06 review'))
 for r in db.execute("SELECT DISTINCT a.offering_id,a.county_fips,a.contract FROM areas a JOIN offerings o ON o.id=a.offering_id WHERE a.source='landscape' AND o.route='L02'").fetchall():
  match=db.execute("SELECT count(*) FROM areas WHERE source='contract-area' AND contract=? AND county_fips=?",(r['contract'],r['county_fips'])).fetchone()[0]
  if not match:db.execute('INSERT INTO differences VALUES(?,?,?,?,?,?,?,?,?)',('contract-area','primary_only',r['offering_id'],r['county_fips'],'contract_county','landscape',None,'contract geography missing or different date','R06 review; no inferred absence'))
 db.execute('INSERT INTO metadata VALUES(?,?)',('year',year));db.commit()
 cms.write_json(out/'source-manifest.json',manifest);cms.write_json(out/'geography-manifest.json',geo);cms.write_json(out/'schema-report.json',schema_report)
 policy={'version':POLICY,'year':year,'population':'individual MA/MA-PD/SNP; MSA retained L02 with L14 detail','source_snapshot':'2026-09-02' if year=='2026' else '2026-09-30','county_scopes':list(scopes),'scoped_counties':{s:counties[s] for s in scopes},'denominator_review':None,'enrollment_status':'unknown; annual sanction flag not complete status','personal_applicability':'not_assessed','permitted_use':'pending R07','commercial_inputs':[],'source_omissions':['employer plan IDs >=800','Part B only','National PACE','2026 MMP demonstration ended per README'],'geography_extent':'landscape county observation; contract-grain crosscheck cannot establish full offering/segment extent'}
 cms.write_json(out/'scope-policy.json',policy);cms.write_json(out/'row-accounting.json',accounting)
 cms.write_json(out/'population-routing.json',[{'category':k[0],'plan_type':k[1],'route':k[2],'rows':v} for k,v in sorted(categories.items())])
 export(db,out/'offerings.csv','SELECT * FROM offerings ORDER BY id')
 export(db,out/'service-areas.csv','SELECT * FROM areas ORDER BY source,id')
 export(db,out/'scope-ledger.csv','SELECT * FROM ledger ORDER BY ordinal')
 export(db,out/'quarantine.csv','SELECT * FROM quarantine ORDER BY source,locator')
 export(db,out/'source-differences.csv','SELECT * FROM differences ORDER BY source,direction,offering_id,county_fips,field')
 export(db,out/'secondary-observations.csv','SELECT * FROM secondary ORDER BY source,id')
 export(db,out/'restrictions.csv','SELECT id,snp,snp_type,sanction,restriction_raw,locator FROM offerings ORDER BY id')
 for county in scopes:scope_report(db,out,year,county,policy,accounting,manifest)
 if supplement:integrate_supplement(out,supplement,year,scopes)
 db.close()
 files={str(p.relative_to(out)):cms.file_hash(p) for p in sorted(out.rglob('*')) if p.is_file()}
 if cms.file_hash(__file__)!=code_hash or cms.file_hash(SPEC/'schemas.json')!=schema_hash or cms.file_hash(cms.__file__)!=helper_hash:raise cms.SourceError('Transformation changed during build; partial artifacts held without manifest')
 binding={'parser_version':VERSION,'policy_version':POLICY,'claim_version':CLAIM,'year':year,'source_manifest_sha256':cms.file_hash(out/'source-manifest.json'),'geography_sha256':digest(geo),'schema_sha256':schema_hash,'code_sha256':code_hash,'transformation_dependencies':{'cms_slice.py':helper_hash},'outputs':files}
 cms.write_json(out/'build-manifest.json',binding)
 cms.write_json(out/'performance.json',{'wall_seconds':round(time.monotonic()-start,3),'peak_rss_host_units':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'rss_units':'bytes on macOS; KiB on Linux','source_bytes':sum(p.stat().st_size for p in paths.values()),'output_bytes':sum(p.stat().st_size for p in out.rglob('*') if p.is_file()),'reviewer_minutes':None})
 return binding

def integrate_supplement(out,supplement,year,scopes):
 interpretation=cms.load_json(SPEC/'supplemental-interpretation.json');sources=cms.load_json(supplement/'source-manifest.json');byid={s['id']:s for s in sources['sources']}
 # Interpretation is explicit and inspectable; matching tokens is a mechanical
 # assertion, not an independent expert signature or an insurance rule.
 for c in interpretation['carrier_checks']:
  source=byid[c['source_id']]
  text=re.sub(r'\s+',' ',(supplement/'extracted'/(source['sha256']+'.txt')).read_text())
  if source['sha256']!=c['source_sha256'] or any(t not in text for t in c['required_tokens']):raise cms.SourceError('Carrier evidence interpretation no longer matches bytes')
 cms.write_json(out/'supplemental-manifest.json',sources)
 cms.write_json(out/'status-observations.json',interpretation['status_observations'])
 cms.write_json(out/'carrier-observations.json',interpretation['carrier_checks'])
 cms.write_json(out/'access-holds.json',interpretation['access_holds'])
 for county in scopes:
  folder=out/county;records=cms.load_json(folder/'offerings.json');worklist=cms.load_json(folder/'carrier-worklist.json');work={r['offering_id']:r for r in worklist};exact=plan_only=identity_only=0
  for r in records:
   checks=[c for c in interpretation['carrier_checks'] if c['year']==year and c['contract']==r['contract'] and c['plan']==r['plan'] and (c['segment'] is None or c['segment']==r['segment'])]
   r['carrier_evidence']=checks;r['carrier_match']=any(c['segment']==r['segment'] and county in c['county_fips'] and c['claim_scope']=='exact_identity_and_published_county' for c in checks)
   if r['carrier_match']:exact+=1
   elif any(county in c['county_fips'] for c in checks):plan_only+=1
   elif checks:identity_only+=1
   r['status_evidence']=[s for s in interpretation['status_observations'] if r['contract'] in s['contracts'] and year=='2026']
   work[r['id']]['observations']=checks;work[r['id']]['official_carrier_matches']=int(r['carrier_match']);work[r['id']]['status']='exact published county observation; acceptance held' if r['carrier_match'] else 'plan-level/identity-only observation; exact area/segment pending' if checks else 'missing exact document; retained'
  cms.write_json(folder/'offerings.json',records);cms.write_json(folder/'carrier-worklist.json',worklist)
  report=cms.load_json(folder/'completeness-report.json');report['source_reconciliation'].update(official_carrier_matches=exact,official_carrier_plan_only_county_observations=plan_only,official_carrier_identity_only_observations=identity_only)
  report['supplemental_limits']=interpretation['limitations'];cms.write_json(folder/'completeness-report.json',report)
  gaps=cms.load_json(folder/'gap-register.json')
  for number,finding,owner,cap in [(16,'UHC official route HTTP 403; host stopped','R07_source_owner','carrier_corroboration'),(17,'Wellcare terms restrict systematic database collection/commercial reuse; no further collection','R07_rights_owner','carrier_corroboration'),(18,'Elevance initial proposed suspension later did not take effect; incomplete historical timeline remains','R06_status_reviewer','historical_open_to_enroll_claim')]:
   gaps.append({'id':f'L02-G{number}','status':'open','finding':finding,'affected_scope':{'year':year,'county_fips':county},'affected_offering_ids':[r['id'] for r in records if (number==16 and r['parent']=='UnitedHealth Group, Inc.') or (number==17 and r['parent']=='Centene Corporation') or (number==18 and r['status_evidence'])],'blocking_capability':cap,'proposed_owner_role':owner,'assigned_owner':None,'next_action':'Review exact supplemental receipts and source/date/rights limits before promotion.','resolution_receipt':None})
  cms.write_json(folder/'gap-register.json',gaps)
  with (folder/'review-packet.md').open('a') as f:f.write(f'\nSupplemental evidence: {exact} exact identity/published-county carrier observations; {plan_only} plan-level county observations with segment unresolved; {identity_only} identity-only records. These are mechanically inspected, not independently accepted. UHC HTTP 403 STOP and Wellcare systematic-use restrictions are retained.\n\nThe Elevance proposed suspension and later completion notice are preserved as history; the later notice says the sanctions would not take effect. Neither the initial summary date nor later closure establishes general enrollment availability. See status-observations.json in the build root and L02-G18.\n')

def scope_report(db,out,year,county,policy,accounting,manifest):
 folder=out/county;folder.mkdir()
 base=" FROM offerings o JOIN areas a ON o.id=a.offering_id WHERE a.source='landscape' AND a.county_fips=? AND o.route='L02'"
 records=[dict(r) for r in db.execute('SELECT DISTINCT o.*'+base+' ORDER BY o.id',(county,))];ids={r['id'] for r in records};contracts={r['contract'] for r in records}
 for r in records:
  r['pbp_match']=bool(db.execute("SELECT 1 FROM secondary WHERE source='pbp' AND id=?",(r['id'],)).fetchone())
  r['snp_match']=bool(db.execute("SELECT 1 FROM secondary WHERE source='snp' AND id=?",(r['id'],)).fetchone()) if r['snp']=='Yes' else None
  r['carrier_match']=False;r['inventory']='observed';r['geography']='county_published_extent_unverified';r['enrollment_status']='unknown';r['personal_applicability']='not_assessed';r['release']='research_only'
 cms.write_json(folder/'offerings.json',records)
 export(db,folder/'offerings.csv','SELECT DISTINCT o.*'+base+' ORDER BY o.id',(county,))
 # Contract-only entries stay visible but are not turned into plan candidates.
 contract_only=[dict(r) for r in db.execute("SELECT * FROM areas WHERE source='contract-area' AND county_fips=? ORDER BY contract,id",(county,)) if r['contract'] not in contracts]
 cms.write_json(folder/'contract-only-observations.json',contract_only)
 diff=[dict(r) for r in db.execute('SELECT * FROM differences ORDER BY source,direction,offering_id') if r['offering_id'] in ids and (r['county_fips'] is None or r['county_fips']==county)]
 cms.write_json(folder/'source-differences.json',diff)
 carrier=[{'child_source_id':'P26-N01:'+r['id']+':availability:r1','offering_id':r['id'],'parent':r['parent'],'marketing':r['marketing'],'status':'exact year/segment/service-area document check pending','assigned_owner':None,'proposed_owner_role':'R08 source/domain reviewer','official_carrier_matches':0} for r in records]
 cms.write_json(folder/'carrier-worklist.json',carrier)
 gap_def=[
 ('2026 population unknown','data_engineering_then_R06','complete_market_claim','Review pinned landscape population and independently establish denominator.'),
 ('Schemas inspected; use review pending','R07_source_owner','consumer_redisplay','Accept exact source use and material code interpretation.'),
 ('Offering/segment extent unresolved','R06_geography_reviewer','address_availability','Resolve partial/regional and any contract versus offering extent.'),
 ('Effective-dated status history incomplete','R06_status_reviewer','open_to_enroll','Review carried-forward sanctions/releases/terminations; annual No is not open.'),
 ('Every-carrier exact document corroboration incomplete','R08_carrier_source_owner','verified_availability','Complete the per-offering carrier worklist without dropping missing records.'),
 ('Plan Finder collection STOP retained','R07_source_owner','independent_corroboration','Resolve authorized source access externally; no bypass.'),
 ('SNP personal qualification not assessed','L12_L13_domain_owners','personal_eligibility','Accept qualification rules and verification; user report is separate.'),
 ('Dated geography and ambiguous postal mapping','data_engineering_R06','precise_residency','Review 2025 Census/HUD mapping and source-specific changed codes.'),
 ('Legacy hard-coded consumer data isolated','engineering_then_R06','consumer_inventory','Use separately scoped receipt; new service must not inherit old acceptance.'),
 ('Independent acceptance absent','founder_and_independent_reviewer','consumer_claims','Assign qualified reviewer; sign exact build/claim/scope receipt.'),
 ('Cross-layer recommendation dependencies held','L03_L05_L08_L13_owners','recommendations','Accept benefits, networks, drugs/costs and personal rules separately.'),
 ('Multi-scope engineering exercised; expansion acceptance pending','engineering_then_R06','consumer_expansion','Review each county/year separately; measure real operations and reviewer effort.'),
 ('SNP source suppresses small enrollment and omits employer plans','R06','negative_availability_claim','Do not treat enrollment absence as unavailable; investigate source differences.'),
 ('Contract-only plausible scope remains unassigned to offerings','R06','complete_market_claim','Disposition contract-only records and employer/Cost/PACE categories without fabricating plans.'),
 ('PBP-only identities have unknown geography/population','R06','complete_market_claim','Investigate national secondary-only identities; no county expansion by contract.'),
 ]
 gaps=[{'id':f'L02-G{i:02d}','status':'open','finding':f,'affected_scope':{'year':year,'county_fips':county},'affected_offering_ids':sorted(ids) if i not in {6,14,15} else [],'blocking_capability':cap,'next_action':act,'proposed_owner_role':owner,'assigned_owner':None,'resolution_receipt':None,'source_locators':['../source-manifest.json','source-differences.json','carrier-worklist.json']} for i,(f,owner,cap,act) in enumerate(gap_def,1)]
 cms.write_json(folder/'gap-register.json',gaps)
 counts=Counter(d['direction'] for d in diff);n=len(ids);snp=sum(r['snp']=='Yes' for r in records)
 cms.write_json(folder/'field-matrix.json',[{'offering_id':r['id'],'identity':'published','population':'published; independent review pending','geography':'extent_unverified','drug_snp':'published','pbp':'exact_identity_match' if r['pbp_match'] else 'missing','carrier':'missing_exact_check','enrollment_status':'unknown','personal_applicability':'not_assessed'} for r in records])
 report={'report_schema_version':'l02-completeness-v1','report_kind':'measured_research_execution','scope':{**policy,'county_fips':county,'evidence_as_of':'source-specific snapshots; not current status'},'denominator':{'status':'unknown','expected_offering_count':None,'review_receipt':None,'limitation':'Enumerated pinned landscape, not independently verified market.'},'source_row_accounting':accounting,'identity_accounting':{'distinct_offerings':n,'distinct_contracts':len(contracts),'distinct_legal_organizations':len({r['legal_name'] for r in records}),'distinct_parent_organizations':len({r['parent'] for r in records}),'distinct_marketing_names':len({r['marketing'] for r in records}),'distinct_offering_geographies':n,'supported_offerings':0,'unresolved_offerings':n,'identity_accounting_percentage':None,'carrier_corroboration_percentage':None,'geography_verification_percentage':None,'plausible_extra_offerings':None,'contract_only_observations':len(contract_only)},'observed_classification_counts':{'MA_only':sum(r['drug']=='No' for r in records),'MA_PD':sum(r['drug']=='Yes' for r in records),'SNP_overlapping':snp,'sanction_flag_yes':sum(r['sanction']=='Yes' for r in records),'regional_overlapping':sum('Regional' in r['plan_type'] for r in records)},'source_reconciliation':{'cms_pbp_identity_matches':sum(r['pbp_match'] for r in records),'cms_snp_identity_matches':sum(r['snp_match'] is True for r in records),'official_carrier_matches':0,'differences':dict(counts),'contract_grain_limit':'contract match never expands offering availability','national_secondary_only_artifact':'../source-differences.csv','unresolved_material_differences':len(diff)},'dimensions':{'identity':'published; payload/filename checked','population_classification':'source codes checked; review pending','service_area_extent':'unresolved','snp_and_other_restrictions':'published, not qualification','enrollment_status_and_dates':'unknown','permitted_use':'pending','freshness':'mixed source periods; consumer stale/current status unaccepted'},'gates':{'G01':'held; denominator/extent unresolved','G02':'held; allowed use pending, Plan Finder STOP','G03':'held; status/freshness/conflicts','G04':'pending independent acceptance','G05':'research service only; consumer held','G06':'held; L02 cannot release recommendations'},'conclusion':{'research_inventory_status':'enumerated_from_pinned_landscape','comprehensive_inventory':False,'consumer_inventory_accepted':False,'personal_recommendations_accepted':False,'supported_capabilities':['offline_research_inventory','developer_read_model'],'limitations':['Accounted records are not verified availability.','No completeness percentage while denominator unknown.','Enrollment absence cannot establish unavailable.','No personal data, eligibility, ranking or sample replacement.']},'gap_register_artifact':'gap-register.json'}
 cms.write_json(folder/'completeness-report.json',report)
 cms.write_json(folder/'query-manifest.json',{'predicate':base,'parameters':[county],'inventory_ids':sorted(ids),'scope_exclusions':[dict(r) for r in db.execute("SELECT DISTINCT o.id,o.route,o.category,o.plan_type FROM offerings o JOIN areas a ON o.id=a.offering_id WHERE a.county_fips=? AND o.route!='L02' ORDER BY o.id",(county,))],'negative_search':{'Cost_or_MSA_observed':[r['id'] for r in records if r['plan_type']=='MSA'],'claim':'Only source-specific observation, no proof of market absence.'}})
 (folder/'review-packet.md').write_text(f'# L02 {year} / {county} research review\n\n{n} distinct landscape offering identities; {len(contracts)} contracts. Verified availability: 0. Expected market count: unknown.\n\nR06: review population, geography, restrictions and all directional exceptions in source-differences.json. Contract-only observations do not create plan candidates.\n\nR07: exact use/access review remains open; Medicare.gov STOP preserved. R08: carrier-worklist.json has every observed offering. No reviewer, review date or acceptance is invented. See gap-register.json for all 12 initial gaps and additional findings.\n\nG01-G06 remain held for consumer claims. Research service/replay is usable; no recommendation, pricing, provider, drug, personal qualification or enrollment claim is released.\n')

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--acquisition',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--supplement',type=Path);p.add_argument('--year',choices=['2026','2027'],default='2026');p.add_argument('--counties',nargs='+',default=['12021','12071','36061']);a=p.parse_args()
 result=build(a.acquisition,a.out,a.year,a.counties,a.supplement);print(canonical({'year':result['year'],'outputs':len(result['outputs']),'build':str(a.out)}))
