"""Source-led r2 examples, authored from exact SB pages read in this review.

These expectations do not read CMS to obtain expected amounts. A passed case
applies only to the named field/band and qualifiers, never to an entire plan.
"""
import collections,json,pathlib,re,zipfile
from l03_reference_build import DATA,L02,PBP_SHA,sha,dump,leaves
from l03_validate import equal,resolve

R=DATA/'build-r1';O=DATA/'reconciliation-r2'
# key: SB PDF page, INN annual MOOP, combined annual MOOP (None=not asserted),
# first INN hospital day-band amount/end; None=flat/conditional handling below.
SOURCE_EXPECTATIONS={
'H1035-019':(3,6750,None,345,7),'H1035-045':(3,4200,None,310,7),
'H1036-217':(4,3800,None,180,5),'H1036-278':(4,4400,None,200,7),'H1036-285':(5,3400,None,None,None),'H1036-290':(4,6700,None,225,5),'H1036-310':(5,3300,None,125,6),'H1036-311':(5,3300,None,125,6),'H1036-314':(5,3400,None,None,None),'H1036-340':(5,9250,None,None,None),
'H1609-027':(3,3300,None,190,6),'H1609-056':(4,9250,None,175,6),'H1609-078':(4,9250,None,None,None),
'H5216-072':(5,5600,9100,400,7),'H5216-257':(5,6000,8000,350,6),'H5216-304':(5,4700,8900,425,4),'H5216-393':(5,6750,6750,400,7),'H5216-394':(6,4900,8950,None,None),'H5216-452':(5,6750,6750,400,7),'H5216-467':(5,6750,10100,350,7),
'H5410-047':(4,1500,None,None,None),'H5410-055':(4,4500,None,150,5),'H5410-060':(3,6750,None,320,7),
'H5427-078':(6,500,None,None,None),'H5427-082':(5,3400,None,195,5),'H5427-083':(5,3400,None,195,5),'H5427-087':(6,500,None,None,None),'H5427-091':(5,2750,None,75,7),'H5427-105':(5,3400,None,195,5),
'H5434-002':(3,6750,10100,350,7),'H5434-042':(3,6750,10100,385,7),'H5434-045':(3,6750,10100,385,7),
'H5521-033':(3,6750,10100,420,7),'H5521-272':(3,5500,10100,290,6),'H5521-306':(3,6750,10100,425,7),'H5521-710':(3,6750,10100,425,7),
'H5594-016':(6,500,None,None,None),'H5594-017':(6,500,None,None,None),'H5594-034':(5,6800,None,225,7),'H5594-035':(5,6800,None,225,7),
'H7617-108':(5,6750,10100,350,7),'H7617-109':(5,4700,8900,425,4),'H7617-111':(5,6750,6750,400,7),'H7617-112':(5,6750,6750,400,7),
'R5826-005':(4,6700,10000,250,7),'R5826-018':(4,7550,10000,275,7),'R5826-074':(4,7550,10500,625,3)}
HOSP_PAGES={'H1035-019':4,'H1035-045':4,'H1609-056':5,'H5410-047':5,'H5410-055':5,'H5410-060':4,'H5216-393':6,'H5216-452':6,'H7617-111':6,'H7617-112':6}
COMBINED_DEDUCTIBLES={'H5216-393':500,'H5216-452':290,'H7617-111':500,'H7617-112':290,'R5826-005':750,'R5826-018':1300,'R5826-074':1300}
OON_BANDS={'H5216-072':(495,27),'H5216-257':(450,27),'H5216-304':(495,27),'H5216-393':(400,7),'H5216-452':(400,7),'H5216-467':(450,7),'H7617-108':(450,7),'H7617-109':(495,27),'H7617-111':(400,7),'H7617-112':(400,7),'R5826-018':(315,7),'R5826-074':(725,14),'H5434-002':(200,27),'H5434-045':(495,27)}

def run():
 m=json.loads((R/'plan-document-matrix.json').read_text());mx={x['offering_id']:x for x in m};c={d['sha256']:d for d in json.loads((R/'carrier-document-catalog.json').read_text())};rows=[];amounts=json.loads((R/'normalized-amount-observations.json').read_text());offerings={x['id']:x for x in json.loads((R/'market-manifest.json').read_text())['observed_offerings']}
 with zipfile.ZipFile(L02/'acquisition-r1/raw'/PBP_SHA) as z:
  for cp,(page,moop,comb,rate,end) in SOURCE_EXPECTATIONS.items():
   oid='2026:'+cp.replace('-',':')+':000';member=cp+'-000-2026.json';b=z.read(member);obj=json.loads(b);p=obj['pbp'][0];doc=c[mx[oid]['document_matches']['SB']['sha256']];pgs=pathlib.Path(doc['text_path']).read_text().split('\f')
   qual=['Published plan reference only. No personal cost determination.','MOOP is annual medical cost sharing; premiums and Part D are outside the medical MOOP where stated.','Retain the complete SB and EOC for service-specific conditions and exclusions.']
   if mx[oid]['parent']=='Elevance Health, Inc.' or cp.startswith('H1035'):qual.append('Shared SB: use the column headed with this exact contract-plan, including its county grouping; adjacent values do not apply.')
   if any(s in mx[oid]['name'] for s in ['D-SNP','Dual','Medi-Medi']):qual.append('Published cost sharing can depend on Medicaid assistance category; zero assistance-protected cost and base cost are distinct. No assistance eligibility inferred.')
   def add(field,expected,pointer,pdfpage,additional=None):
    actual=resolve(obj,pointer);text=pgs[pdfpage-1]
    rows.append({'id':oid+':r2:'+field,'offering_id':oid,'field':field,'expected_from_SB':str(expected),'actual_CMS':actual,'equal':equal(actual,expected),'unit':'USD' if not field.endswith(('begin_day','end_day')) else 'day','source':{'member':member,'member_sha256':sha(b),'pointer':pointer},'carrier_evidence':{'document_sha256':doc['sha256'],'url':doc['url'],'pdf_page':pdfpage,'text_sha256':sha(text.encode())},'qualifications':qual+(additional or []),'status':'AI_source_compared_exact_field_review_pending','accepted':False})
   moops=[(path,v) for path,v in leaves(obj) if (path.endswith('/inNWMoopAmount') or path.endswith('/meclInnMoopAmount')) and v not in [None,'']]
   if len(moops)!=1:raise ValueError('Ambiguous INN MOOP '+oid)
   add('INN_annual_medical_MOOP',moop,moops[0][0],page)
   if comb is not None:
    a=[(path,v) for path,v in leaves(obj) if path.endswith(('/combinedMoopAmount','/meclCombMoopAmount')) and v not in [None,'']]
    if len(a)!=1:raise ValueError('Ambiguous combined MOOP '+oid)
    add('combined_annual_medical_MOOP',comb,a[0][0],page,['Combined in/out-of-network is a single combined limit, not a separate allowance or an amount to add to INN MOOP.'])
   ix=next(i for i,x in enumerate(p['benefitDetails']['benefitDetailsInfo']) if x['categoryCode']=='1a' and x['categoryTypeId']==1)
   hp=HOSP_PAGES.get(cp,page);base=f'/pbp/0/benefitDetails/benefitDetailsInfo/{ix}/benefitDetails/'
   if rate is not None:
    pre=base+'TierCopaymentComponent/bdCopaymentTier1DayIntervalStay/'
    for fld,exp,src in [('INN_hospital_band1_amount',rate,'bdDayInterval1CopaymentAmount'),('INN_hospital_band1_begin_day',1,'bdDayInterval1BeginDay'),('INN_hospital_band1_end_day',end,'bdDayInterval1EndDay'),('INN_hospital_band2_amount',0,'bdDayInterval2CopaymentAmount'),('INN_hospital_band2_begin_day',end+1,'bdDayInterval2BeginDay'),('INN_hospital_band2_end_day',90,'bdDayInterval2EndDay')]:
     add(fld,exp,pre+src,hp,['Cost bands are per day; covered inpatient days and benefit-period rules are separate. An ending day of 90 is not a coverage cap.'])
   else:
    expected=1000 if cp=='H5216-394' else 0
    add('INN_hospital_PBP_base_stay_copayment',expected,base+'TierCopaymentComponent/bdCopaymentTier1Amt',hp,['For H5216-394 the SB has $0 or $1,000 per admission depending on assistance; $1,000 is the PBP base copayment, not a personal amount.'] if cp=='H5216-394' else ['Compare the base copayment field only; amount zero does not remove deductible, eligibility, referral or authorization conditions.'])
   if cp in OON_BANDS:
    am,ed=OON_BANDS[cp];pre=base+'CostShareABComponent/bdCopaymentDayIntervalStay/'
    # Exact source node is explicit OON hospital cost-share, not categoryTypeId.
    for fld,exp,src in [('OON_hospital_band1_amount',am,'bdDayInterval1CopaymentAmount'),('OON_hospital_band1_begin_day',1,'bdDayInterval1BeginDay'),('OON_hospital_band1_end_day',ed,'bdDayInterval1EndDay'),('OON_hospital_band2_amount',0,'bdDayInterval2CopaymentAmount'),('OON_hospital_band2_begin_day',ed+1,'bdDayInterval2BeginDay'),('OON_hospital_band2_end_day',90,'bdDayInterval2EndDay')]:
     add(fld,exp,pre+src,hp,['OON hospital band; any applicable plan deductible, waiver and authorization/network rules remain attached, including the explicit OON deductible for Blue Select.'])
   if cp in COMBINED_DEDUCTIBLES:
    add('combined_annual_medical_deductible',COMBINED_DEDUCTIBLES[cp],'/pbp/0/planLevelCostSharing/lppoRppoDeductible/lppoRppoDeductibleDetails/otherTypeDedAmount',page,['Combined medical deductible. The service exclusions on this SB page and source service-selection controls must remain attached; do not apply this deductible to every service.'])
   premium={'H5216-394':'4.80','H5410-047':'4.80','H5410-055':'4.80','H5434-002':'153.70','H5434-045':'58.20','R5826-005':'184','R5826-018':'42','R5826-074':'41'}.get(cp,'0')
   fact=next(a for a in amounts if a['offering_id']==oid and a['field']=='consolidated_premium')
   if offerings[oid]['drug']=='No':
    fact=next(a for a in amounts if a['offering_id']==oid and a['field']=='part_c_premium')
    qual.append('MA-only: compare the published plan premium to Part C. The absent consolidated C+D source field stays absent; it is not converted to zero.')
   if cp in ['H5410-047','H5410-055']:
    pd=c[mx[oid]['document_matches']['EOC']['sha256']];pp=10;pt=pathlib.Path(pd['text_path']).read_text().split('\f')[pp-1]
   else:pd=doc;pp=page;pt=pgs[pp-1]
   rows.append({'id':oid+':r2:published_gross_consolidated_premium','offering_id':oid,'field':'published_gross_consolidated_premium','expected_from_carrier':premium,'actual_CMS':fact['value'],'equal':equal(fact['value'],premium),'unit':'USD/month','source':fact['source'],'carrier_evidence':{'document_sha256':pd['sha256'],'url':pd['url'],'pdf_page':pp,'text_sha256':sha(pt.encode())},'qualifications':qual+['Gross consolidated C+D plan premium, separate from federal Part B. Extra Help and other assistance can change the member amount. Never substitute the SB assistance-qualified $0 for the gross premium.','HealthSpring 047/055 EOC page 10 states gross $4.80 and a separate LIS rider; Humana 394 SB states $0 or up to $4.80 depending on Extra Help.'],'status':'AI_source_compared_exact_field_review_pending','accepted':False})
 for r in rows:
  if not r['equal']:r['status']='basis_difference_held_for_review'
 dump(O/'source-led-comparison-ledger.json',rows)
 summary={'source_led_checks':len(rows),'offering_count':len(SOURCE_EXPECTATIONS),'agreements':sum(x['equal'] for x in rows),'differences':sum(not x['equal'] for x in rows),'scope':'Only named premium, medical MOOP/deductible and inpatient cost/day fields with listed qualifications; not all benefits or final approval.'}
 dump(O/'source-led-comparison-summary.json',summary);print(json.dumps(summary,indent=2));return rows
if __name__=='__main__':run()
