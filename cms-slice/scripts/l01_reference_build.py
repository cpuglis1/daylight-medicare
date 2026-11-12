"""Build the bounded 2026 published-cost reference from retained official evidence.

No network calls, personal calculations, registry writes or source restriction
changes. The prior broad r1 remains immutable. New years need new source inputs.
"""
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
from html.parser import HTMLParser
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT/'docs/data/l01-national-2026/r1'
OUT = ROOT/'docs/data/l01-national-2026/published-reference-r1'
REGISTRY = ROOT/'cms-slice/data-sources/l01-published-reference-review.json'


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def object_sha(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,ensure_ascii=False,sort_keys=True)+'\n')


class HTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables=[];self.table=None;self.row=None;self.cell=None;self.text=[];self.skip=0

    def handle_starttag(self,tag,attrs):
        if tag in {'script','style'}:self.skip+=1
        if self.skip:return
        if tag=='table':self.table=[]
        if tag=='tr' and self.table is not None:self.row=[]
        if tag in {'th','td'} and self.row is not None:self.cell=[]

    def handle_endtag(self,tag):
        if tag in {'script','style'}:self.skip=max(0,self.skip-1)
        if self.skip:return
        if tag in {'th','td'} and self.cell is not None:
            self.row.append(' '.join(' '.join(self.cell).split()));self.cell=None
        elif tag=='tr' and self.row is not None:self.table.append(self.row);self.row=None
        elif tag=='table' and self.table is not None:self.tables.append(self.table);self.table=None

    def handle_data(self,data):
        if not self.skip:
            self.text.append(data)
            if self.cell is not None:self.cell.append(data)


def cents(value):
    return int(Decimal(value.replace('$','').replace(',','').strip())*100)


def bounds(text):
    amounts=[cents(x) for x in re.findall(r'\$[\d,]+(?:\.\d+)?',text)]
    lower=text.lower()
    if len(amounts)==1 and lower.startswith('less'):
        return None,False,amounts[0],True
    if len(amounts)==1 and lower.startswith('greater than or equal'):
        return amounts[0],True,None,False
    if len(amounts)==2 and lower.startswith('greater than'):
        return amounts[0],False,amounts[1],'less than or equal' in lower
    raise ValueError('Unrecognized published income range: '+text)


def build(out=OUT):
    out=Path(out)
    if REGISTRY.exists():
        actual=read(REGISTRY)
        if (actual.get('decision')!='pending' or actual.get('reviewed_at_utc')
                or actual.get('receipt')) and out.resolve()==OUT.resolve():
            raise ValueError('Reviewed reference is frozen; create a new revision')
    legacy_sources={s['id']:s for s in read(BASE/'sources.json')}
    texts={};parsers={};sources={};observations=[];checks=[]
    evidence_files={}

    def source(sid):
        if sid not in sources:
            old=legacy_sources[sid]
            assert old['status']=='acquired'
            raw=BASE/old['artifact'];extracted=BASE/old['extracted_artifact']
            assert sha(raw)==old['sha256']
            text=extracted.read_text()
            if old['media_type']=='text/html':
                parser=HTML();parser.feed(text);parsers[sid]=parser
                text=' '.join(' '.join(parser.text).split())
            texts[sid]=text
            sources[sid]={k:old.get(k) for k in ('id','url','actual_title','publisher','retrieved_at_utc','publication_date','sha256','status','media_type','access_record')}
            sources[sid].update(raw_path=str(raw.relative_to(ROOT)),extracted_path=str(extracted.relative_to(ROOT)),
                                extracted_sha256=sha(extracted),role='official_published_evidence',
                                temporal_note='Annual 2026 column only' if sid in {'CMS-ANNUAL','CMS-MM14279','FR-A-DEDUCT','FR-A-PREMIUM','FR-B'} else 'Continuing section qualification; exact section dates retained for owner review')
            evidence_files[str(raw.relative_to(ROOT))]=sha(raw)
            evidence_files[str(extracted.relative_to(ROOT))]=sha(extracted)
        return texts[sid]

    def evidence(sid,needle,length=450,interpretation=None,occurrence='last'):
        text=source(sid)
        start=text.rfind(needle) if occurrence=='last' else text.find(needle)
        if start<0:raise ValueError('Missing source anchor '+sid+': '+needle)
        oid=f'REF-OBS-{len(observations)+1:03}'
        observations.append({'id':oid,'source_id':sid,'snapshot_sha256':sources[sid]['sha256'],
            'locator':('PDF page '+str(text[:start].count('\f')+1) if '\f' in text else 'HTML text')+f'; extracted characters {start}-{min(len(text),start+length)}',
            'excerpt':text[start:start+length],'interpretation':interpretation})
        return oid

    def check(cid,condition,detail):
        checks.append({'id':cid,'passed':bool(condition),'detail':detail})

    annual=source('CMS-ANNUAL');mm=source('CMS-MM14279')
    legacy_facts={f['id']:f for f in read(BASE/'facts.json')}
    costs=[]
    def cost(oid,label,kind,value,period,basis,condition,refs,**extra):
        costs.append({'id':oid,'label':label,'kind':kind,'value':value,'period':period,'cost_basis':basis,
            'currency':'USD' if kind in {'money','prescription_cap'} else None,
            'unit':'USD cents' if kind=='money' else 'fraction of stated cost basis' if kind=='rate' else 'pints or equivalent units' if kind=='quantity' else 'typed formula with USD-cent cap' if kind=='prescription_cap' else 'coverage boundary without fixed amount',
            'conditions':condition,'observation_ids':refs,'conflict_ids':[],**extra})

    anchors={
        'a_premium_full':('Part A base premium (BP): $565 a month','Full Part A monthly premium'),
        'a_premium_reduced':('$311 a month','Reduced Part A monthly premium'),
        'a_deductible':('Part A deductible: $1,736','Part A inpatient deductible'),
        'hospital_61_90':('$434 a day for days 61','Hospital days 61 through 90'),
        'hospital_reserve':('$868 a day','Available hospital lifetime reserve day'),
        'snf_21_100':('$217 a day','Covered SNF days 21 through 100'),
        'b_premium':('Part B standard premium: $202.90','Standard full Part B monthly premium'),
        'b_deductible':('Part B deductible: $283 a year','Part B annual deductible'),
        'immuno_premium':('Part B immunosuppressive drug coverage only premium: $121.60','Limited immunosuppressive-only Part B premium'),
        'b_coinsurance':('Part B coinsurance: 20%','Ordinary Part B coinsurance'),
    }
    for oid,(anchor,label) in anchors.items():
        old=legacy_facts[oid]
        refs=[evidence('CMS-MM14279',anchor,180)]
        if oid=='a_deductible':refs.append(evidence('GENERAL-COSTS','10.1 - Inpatient Hospital Deductible',1250))
        if oid=='b_coinsurance':refs.append(evidence('GENERAL-COSTS','20.3 - Part B Coinsurance',1300))
        cost(oid,label,'rate' if oid=='b_coinsurance' else 'money',old['value'],old['period'],old['cost_basis'],old['conditions'],refs,
             coverage_context=old['coverage_context'])
        if oid=='a_deductible':costs[-1]['conflict_ids']=['L01-G09']
        if oid=='b_coinsurance':
            costs[-1]['conditions']='Ordinary applicable physician/supplier services after the deductible, usually 20% of the Medicare-approved amount. Facility and service-specific exceptions differ; this is not a universal billing rule.'
    cost('a_premium_free','Premium-free Part A category','money',0,'month','published premium category',
         'Published premium-free category; eligibility is not determined by this reference.',
         [evidence('CMS-MM14279','Most people age 65 and older',480)],coverage_context='part_a')
    cost('hospital_1_60','Hospital days 1 through 60 daily coinsurance','money',0,'covered_day','daily Part A coinsurance only',
         'Covered first 60 days in a benefit period; the separate inpatient deductible still applies. This is not a zero hospital bill.',
         [evidence('CMS-ANNUAL','covers beneficiaries',320,occurrence='first'),evidence('CMS-MM14279','During a spell of illness',690)],
         day_range={'first':1,'last':60},coverage_context='part_a')
    cost('hospital_after_covered_days','Hospital care after covered benefit/reserve days','coverage_boundary',None,'day','no remaining Part A covered inpatient days',
         'Beyond the covered 90-day schedule and any available elected lifetime reserve days, this schedule provides no further Part A covered days. All charges may be due subject to other coverage and liability protections; no personal bill is determined.',
         [evidence('MANUAL-DURATION','A. Inpatient Hospital Benefit Days',660),evidence('MANUAL-RESERVE','10.1 - Effect of Reserve Days on Guarantee of Payment Provision',1350)],coverage_context='part_a')
    cost('snf_1_20','Covered SNF days 1 through 20 daily coinsurance','money',0,'covered_day','daily Part A SNF coinsurance only',
         'Covered SNF benefit days 1–20; qualification, coverage and other services are not determined here.',
         [evidence('GENERAL-COSTS','10.2.1 - Inpatient Services',1150)],day_range={'first':1,'last':20},coverage_context='part_a')
    cost('snf_after_100','SNF care after day 100 in the benefit period','coverage_boundary',None,'day','outside covered Part A extended-care day schedule',
         'The Part A SNF day schedule ends after 100 covered days per benefit period. All charges may be due subject to other coverage/protections; no actual personal liability is determined.',
         [evidence('MANUAL-DURATION','B. Posthospital Extended Care Days',700)],day_range={'first':101,'last':None},coverage_context='part_a')
    costs_by_id={x['id']:x for x in costs}
    costs_by_id['hospital_61_90']['day_range']={'first':61,'last':90}
    costs_by_id['hospital_reserve']['day_range']={'first':91,'last':150}
    costs_by_id['hospital_reserve']['lifetime_reserve_days_maximum']=60
    costs_by_id['snf_21_100']['day_range']={'first':21,'last':100}

    home=evidence('MANUAL-HOME','60.4 - Coinsurance, Copayments, and Deductibles',1350)
    for oid,label in [('home_services_base','Covered home-health services base cost sharing'),('home_dme_rate','Home-health durable medical equipment coinsurance'),('home_npwt_rate','Disposable negative-pressure wound therapy coinsurance')]:
        old=legacy_facts[oid]
        cost(oid,label,old['value_type'],old['value'],old['period'],old['cost_basis'],old['conditions'],[home],coverage_context='home_health')
    cost('home_osteoporosis_rate','Covered home-health osteoporosis drug coinsurance','rate',{'numerator':20,'denominator':100},'service','published fee schedule basis in manual section 60.4',
         'Covered Part B home-health osteoporosis drug; the applicable Part B deductible also applies. Reference to the published base rate only; drug-specific payment adjustments/pricing are outside this reference.',[home],coverage_context='home_health')
    hospice=evidence('MANUAL-HOSPICE','30 - Coinsurance',3100)
    cost('hospice_services_base','Covered hospice services base cost sharing','money',0,'covered_service','covered hospice benefit other than specified coinsurance',
         'Reference base for covered elected hospice services; palliative prescription and inpatient respite coinsurance are separate. Unrelated care, separately billed services and residential room/board are not a blanket zero-cost promise.',[hospice],coverage_context='hospice')
    for oid,label in [('hospice_drug_cap','Hospice home-care palliative prescription coinsurance'),('hospice_respite_rate','Hospice inpatient respite coinsurance')]:
        old=legacy_facts[oid]
        cost(oid,label,'prescription_cap' if oid=='hospice_drug_cap' else 'rate',old['value'],old['period'],old['cost_basis'],old['conditions'],[hospice],coverage_context='hospice')
    costs[-1]['reference_cap']={'basis':'inpatient deductible for the year the hospice coinsurance period began','linked_cost_id':'a_deductible','current_year_amount_only_if_period_started_in':2026,'period_definition':'from election until the end of the first 14 consecutive days without an election'}
    cost('hospice_inpatient_drugs','Related hospice drugs during general inpatient/respite care','money',0,'prescription','hospice-related prescription coinsurance',
         'No related-drug coinsurance in general inpatient or respite hospice care; the distinct respite-service coinsurance remains applicable.',[hospice],coverage_context='hospice')
    cost('blood_deductible_units','Combined A/B blood deductible quantity','quantity',3,'calendar_year','pints of whole blood or equivalent packed red-cell units',
         'First three pints/units combined across A and B, subject to replacement and other exceptions; processing/administration is not this deductible. This quantity is not a dollar price.',
         [evidence('GENERAL-COSTS','20.5 - Blood Deductibles (Part A and Part B)',1150),evidence('GENERAL-COSTS','20.5.4.1 - Replacement of Blood',1800)],coverage_context='parts_a_b')
    cost('immuno_deductible','Annual deductible for immunosuppressive-only Part B','money',28300,'calendar_year','published deductible for all Part B beneficiaries',
         'Limited immunosuppressive-only Part B context; annual Part B deductible applies. Eligibility and individual liability are not determined.',
         [evidence('FR-B','deductible for 2026 is $283.00 for',450,occurrence='first'),evidence('CMS-MM14279','Part B deductible: $283 a year',150)],coverage_context='immuno_b')

    # All 45 bands are independently re-read from the six CMS IRMAA tables.
    # The first HTML table is the separate Part A cost table.
    tables=parsers['CMS-ANNUAL'].tables
    bands=[];table_rows=[]
    table_specs=[(1,'full_b',False),(2,'immuno_b',False),(3,'full_b',True),(4,'immuno_b',True),(5,'part_d',False),(6,'part_d',True)]
    for ti,context,separate in table_specs:
        for ri,row in enumerate(tables[ti],1):
            if not row or not row[0].lower().startswith(('less than','greater than')):continue
            source_row={'source_id':'CMS-ANNUAL','table_index_0_based':ti,'row_1_based':ri,'cells':row,'output_ids':[]}
            for col,filing in ([(0,'separate_together')] if separate else [(0,'individual'),(1,'joint')]):
                low,li,high,hi=bounds(row[col]);prefix=f'L01-IRMAA-{context}-{filing}-'
                ordinal=sum(b['id'].startswith(prefix) for b in bands)
                oid=prefix+str(ordinal)
                oi=f'REF-OBS-CMS-T{ti}-R{ri}'
                if not any(x['id']==oi for x in observations):
                    observations.append({'id':oi,'source_id':'CMS-ANNUAL','snapshot_sha256':sources['CMS-ANNUAL']['sha256'],
                        'locator':f'HTML table index {ti} (zero based), row {ri} (one based)','excerpt':' | '.join(row),'interpretation':None})
                adj=cents(row[-1] if context=='part_d' else row[-2]);total=None if context=='part_d' else cents(row[-1])
                conflicts=[]
                if context in {'full_b','immuno_b'} and filing=='separate_together' and ordinal in {1,2}:conflicts.append('L01-G04')
                if context=='full_b' and filing=='separate_together' and ordinal==2:conflicts.append('L01-G03')
                bands.append({'id':oid,'coverage_context':context,'filing_status':filing,
                    'filing_status_note':'Individual-return table as published; exact filing/living-arrangement selection is outside this reference' if filing=='individual' else 'Joint return' if filing=='joint' else 'Married separate return, lived together at any time during the tax year',
                    'lower_cents':low,'lower_inclusive':li,'upper_cents':high,'upper_inclusive':hi,
                    'adjustment_cents':adj,'base_cents':None if context=='part_d' else 20290 if context=='full_b' else 12160,
                    'published_total_cents':total,'currency':'USD','income_unit':'USD cents','period':'month',
                    'tax_return_basis':{'normal_year':2024,'fallback_year':2023,'type':'published_reference_not_personal_determination'},
                    'observation_ids':[oi],'conflict_ids':conflicts})
                source_row['output_ids'].append(oid)
            table_rows.append(source_row)

    notes=[]
    def note(oid,label,text,refs):
        notes.append({'id':oid,'label':label,'text':text,'observation_ids':refs,'conflict_ids':[]})
    note('NOTE-A-CATEGORIES','Published Part A premium categories',
         'The free, reduced and full premium categories are reference categories. Work/relationship entitlement and individual premium selection are outside L01.',
         [evidence('CMS-ANNUAL','Enrollees age 65 and older',1100,occurrence='first'),evidence('CMS-MM14279','Most people age 65 and older',500)])
    note('NOTE-PERIODS','Deductible and day periods',
         'Part A inpatient deductible is per benefit period, not per calendar year. Day coinsurance follows the year services occur; the reference does not reconstruct a person’s stays or reserve history. Part B deductible is annual and is not reduced merely because coverage lasts less than a full year.',
         [evidence('GENERAL-COSTS','10.1 - Inpatient Hospital Deductible',1300),evidence('GENERAL-COSTS','Even though an individual',680)])
    note('NOTE-B-EXCEPTIONS','Ordinary Part B rate qualifications',
         'The ordinary Part B rate is a baseline for applicable covered services after the deductible. Some preventive/laboratory and other services have waivers or different cost sharing, and facility payment bases can differ. This reference does not model every service-specific bill.',
         [evidence('GENERAL-COSTS','20.3 - Part B Coinsurance',1250),evidence('GENERAL-COSTS','20.4 - Exceptions to Annual Deductible and Coinsurance',1450)])
    note('NOTE-IMMUNO','Limited benefit versus full Part B',
         'The immunosuppressive-only premium and bands describe a limited benefit, not full medical Part B coverage. The coverage qualification is retained; personal entitlement selection is outside L01.',
         [evidence('CMS-ANNUAL','Beginning in 2023',550,occurrence='first')])
    note('NOTE-TAX-BASIS','2026 premium year and tax-return basis',
         'The retained SSA 2026 tables state normally 2024 MAGI, or 2023 if 2024 is unavailable. This is source metadata, not automatic selection of a person’s return, redetermination or billed premium.',
         [evidence('SSA-POMS-TABLE','If MAGI in 2024 (or 2023 if 2024 is not available)',200,occurrence='first'),
          evidence('SSA-POMS-SEPARATE','SSA requests MAGI information',1500,occurrence='first')])
    note('NOTE-SEPARATE','Separate-return living-arrangement qualification',
         'The special married-separate tables apply to those who lived together at any time in the tax year. The lived-apart-all-year route and official determination are separate qualifications; L01 publishes labeled tables without choosing one for a person.',
         [evidence('CMS-ANNUAL','Premiums for high-income beneficiaries with full Part B',550,occurrence='first'),evidence('SSA-LIVED-APART','A. Policy',1600,occurrence='first')])
    note('NOTE-COMPONENTS','Published premiums and separate components',
         'Published premiums precede personal protections, assistance, penalties and official adjustment decisions. Part D IRMAA is added to its separately sourced plan premium; a Part B published total already includes its adjustment. L13 owns penalties; no annualization, eligibility decision or personal total is provided here.',
         [evidence('CMS-ANNUAL','These individuals will pay',500,occurrence='first'),evidence('SSA-HOLD-HARMLESS','A. VSMI general policy',1800,occurrence='first')])
    note('NOTE-HOME-HOSPICE','Home-health and hospice cost-sharing qualifications',
         'Home-health base cost sharing has equipment, disposable NPWT and covered osteoporosis-drug exceptions with distinct bases. Hospice prescription coinsurance uses an approved schedule approximating 5%, capped at $5; respite is 5% with a period-start-year deductible cap. Unrelated care and room/board are not included in a blanket zero-cost statement.',
         [home,hospice,evidence('MANUAL-HOSPICE','Medicare services for a condition completely unrelated',350,occurrence='first')])

    year_fields={'premium_year':2026,'effective_from':'2026-01-01','effective_until':'2027-01-01',
                 'version':'2026-published-r1','personal_applicability_determined':False}
    for row in costs+bands+notes:row.update(year_fields)
    for row in costs:
        row['qualification_ids']=['NOTE-HOME-HOSPICE'] if row['coverage_context'] in {'home_health','hospice'} else ['NOTE-PERIODS']
        if 'premium' in row['id']:row['qualification_ids']=['NOTE-COMPONENTS']
        if row['id'].startswith('a_premium'):row['qualification_ids'].append('NOTE-A-CATEGORIES')
        if row['coverage_context']=='immuno_b':row['qualification_ids'].append('NOTE-IMMUNO')
        if row['id']=='b_coinsurance':row['qualification_ids'].append('NOTE-B-EXCEPTIONS')
    for row in bands:
        row['qualification_ids']=['NOTE-TAX-BASIS','NOTE-SEPARATE','NOTE-COMPONENTS']
        if row['coverage_context']=='immuno_b':row['qualification_ids'].append('NOTE-IMMUNO')
    conflicts=read(BASE/'conflicts.json')
    for c in conflicts:
        c['scope']='Published reference source disposition only; no personal determination'
        c['review_status']='pending_owner_review'
    source('FR-A-DEDUCT');source('FR-A-PREMIUM');source('SSA-POMS-TABLE')
    # Original disagreement evidence is retained, not silently replaced by agreement.
    for c in conflicts:
        for sid in {'L01-G03':['FR-B'],'L01-G04':['FR-B','FR-B-METADATA'],'L01-G09':['DCF-59106','FR-A-DEDUCT']}[c['id']]:source(sid)
    evidence_files[str((BASE/'ssa-rendered-observation.json').relative_to(ROOT))]=sha(BASE/'ssa-rendered-observation.json')
    evidence_files[str((BASE/'conflicts.json').relative_to(ROOT))]=sha(BASE/'conflicts.json')

    expected=read(ROOT/'cms-slice/tests/fixtures/l01-published-2026-expectations.json')
    for path in [BASE/'facts.json',BASE/'bands.json',BASE/'sources.json',ROOT/'cms-slice/tests/fixtures/l01-published-2026-expectations.json']:
        evidence_files[str(path.relative_to(ROOT))]=sha(path)
    costmap={x['id']:x for x in costs}
    for oid,want in expected['cost_values'].items():
        check('VALUE-'+oid,costmap[oid]['value']==want,'Separately source-transcribed expected reference value; not independent human acceptance')
    check('COST-DENOMINATOR',set(costmap)==set(expected['cost_values']),'Required cost IDs fixed independently of extraction success')
    check('BAND-DENOMINATOR',len(bands)==45,'Three coverage contexts; individual/joint six levels and separate three levels')
    check('CMS-ROWS',len(table_rows)==27,'All six CMS annual IRMAA tables, 27 data rows, expanded to 45 labeled records')
    legacy_bands={x['id']:x for x in read(BASE/'bands.json')}
    keys=('lower_cents','lower_inclusive','upper_cents','upper_inclusive','adjustment_cents','published_total_cents')
    for b in bands:
        check('TRANSCRIPTION-'+b['id'],all(b[k]==legacy_bands[b['id']][k] for k in keys),'Independent parser versus retained earlier transcription; not independent human review')
        if b['coverage_context']!='part_d':check('NO-DOUBLE-COUNT-'+b['id'],b['base_cents']+b['adjustment_cents']==b['published_total_cents'],'Published B total equals base plus adjustment once')
    boundary_cases=[]
    for context in ('full_b','immuno_b','part_d'):
        for filing in ('individual','joint','separate_together'):
            group=[b for b in bands if b['coverage_context']==context and b['filing_status']==filing]
            expected_edges=expected['income_edges_dollars'][filing]
            expected_adjustments=expected['adjustments_cents'][context]
            expected_adjustments=expected_adjustments if filing!='separate_together' else [expected_adjustments[i] for i in (0,4,5)]
            for i,b in enumerate(group):
                check('EXPECTED-BAND-'+b['id'],b['adjustment_cents']==expected_adjustments[i],'Amounts transcribed separately from the CMS annual tables')
            def matches(income):
                return [b for b in group if (b['lower_cents'] is None or income>b['lower_cents'] or income==b['lower_cents'] and b['lower_inclusive']) and (b['upper_cents'] is None or income<b['upper_cents'] or income==b['upper_cents'] and b['upper_inclusive'])]
            for j,edge in enumerate(expected_edges):
                # All but the final top boundary remain in the lower band at equality.
                for offset in (-1,0,1):
                    income=edge*100+offset
                    wanted=j if offset<0 or offset==0 and j<len(expected_edges)-1 else j+1
                    found=matches(income)
                    passed=len(found)==1 and found[0]['id']==group[wanted]['id']
                    boundary_cases.append({'context':context,'filing':filing,'edge_dollars':edge,'offset_cents':offset,'expected_band':group[wanted]['id'],'passed':passed})
            check('PARTITION-'+context+'-'+filing,len(matches(-1))==1 and len(matches(0))==1 and len(matches(10**14))==1,'Unbounded first/last published bands; no income intake or personal selection is exposed')
    check('SOURCE-BOUNDARIES',all(x['passed'] for x in boundary_cases),'All independently specified income edges at minus one cent, equality and plus one cent')
    obs_ids={o['id'] for o in observations}
    check('EXACT-EVIDENCE',all(x['observation_ids'] and set(x['observation_ids'])<=obs_ids for x in costs+bands+notes),'Every cost/band/note has an exact source observation')
    check('ZERO-IS-EXPLICIT',all(costmap[x]['value']==0 for x in expected['zero_cost_ids']),'Zero entries distinct from missing amounts and uncovered-day boundaries')
    check('BOUNDARY-NONVALUES',all(costmap[x]['kind']=='coverage_boundary' and costmap[x]['value'] is None for x in ('hospital_after_covered_days','snf_after_100')),'Beyond-benefit statements are not a fixed amount or personal bill')
    check('LIMITED-BENEFIT',costmap['immuno_premium']['coverage_context']=='immuno_b' and costmap['immuno_deductible']['coverage_context']=='immuno_b','Limited benefit remains separate from full B')
    check('NOTE-DENOMINATOR',{x['id'] for x in notes}==set(expected['note_ids']),'Required qualifications fixed independently of extraction')
    check('QUALIFICATION-LINKS',all(row['qualification_ids'] and set(row['qualification_ids'])<=set(expected['note_ids']) for row in costs+bands),'Every cost and band carries its relevant published qualifications, including tax-year evidence')

    scope={'schema':'l01-published-scope/1','requirement':'D76','year':2026,
       'title':'Published federal Medicare cost reference','geography':'National federal reference reused by Collier, Florida',
       'included':['Published A/B premium categories, deductibles and ordinary cost-sharing schedule','Covered hospital/SNF zero-cost ranges and exhaustion boundaries','Published home-health/hospice cost-sharing amounts and necessary qualifications','All full-B, immunosuppressive-only B and D IRMAA filing-status tables, units, inequalities and tax-year metadata'],
       'excluded':['Choosing applicability for a person','Enrollment and penalty rules (L13)','Full service-specific claims or coverage engine','Personal stay, annual premium or total-cost calculations','Plan premiums, Medigap, drug prices, assistance eligibility and other layers','Frontend redesign, default-demo activation and recommendation release'],
       'denominator_policy':'New explicit owner-authorized reference scope; preserve the broad r1 inventory and its gaps unchanged. Missing required entries fail rather than shrinking this inventory.',
       'source_policy':'Official primary publication evidence for every entry; secondary comparisons where available, with limitations shown. No invented requirement to acquire every source in the earlier 33-document broad inventory.',
       'reviewer_assignment':'Owner volunteered in this chat; identity, scope qualification and genuine final decision remain to be supplied.'}
    inventory={'schema':'l01-published-inventory/1','cost_ids':list(expected['cost_values']),'band_ids':[x['id'] for x in bands],'note_ids':expected['note_ids'],'exclusions_with_owner':['L13 penalty rates/logic','Personal billing/eligibility and cross-layer totals','Technical managed-care deductible pro-rata amounts are source-preserved administrative context, not personal premiums/deductible installments']}
    dispositions={'schema':'l01-source-dispositions/1','annual_irmaa_rows':table_rows,
       'annual_part_a_table':{'disposition':'2026 column modeled in costs; 2025 column retained as historical source, never substituted'},
       'mm14279':{'included':'A/B base costs and limited immunosuppressive premium; amounts, units and day ranges',
          'L13_excluded_rows':['Part A base premium with 10% surcharge','Part A reduced premium with 10% surcharge','Enrollment penalty explanation'],
          'administrative_context_not_personal_amounts':{'pro_rata_first_month_cents':19117,'pro_rata_second_month_cents':9183,'basis':'MM14279 p3 and General Information chapter3 section20.2; managed-care assumed-deductible accounting, not a reduced personal annual deductible'}},
       'general_manual':{'modeled_sections':['10.1','10.2.1','20.2 period qualification','20.3 ordinary rate basis','20.4 exception qualification','20.5 blood quantity/replacement'],
          'excluded':'Old-year amount columns and full service-specific claims implementation'},
       'medicare_gov_stop':'Preserved; no new requests. Earlier missing booklet/cost-page/cost-sheet sources remain missing in broad r1.',
       'ssa_denial':'Preserved; no new requests. Retained POMS artifacts are used with their own exact hashes.',
       'secondary_comparison_limits':['CMS has explicit $0 base Part D adjustments. The retained POMS high-income table omits those base rows; primary-source verification is recorded, not mislabeled independent numerical corroboration.','Home-health/hospice primary manual sections are exact; no second independent publication is claimed.','The current CMS Payment Systems webpage is marked FY2027 and is not substituted as 2026 evidence.']}
    results={'schema':'l01-published-checks/1','checks':checks,'passed':sum(c['passed'] for c in checks),'failed':sum(not c['passed'] for c in checks),
             'income_boundary_cases':boundary_cases,'income_boundaries_passed':sum(c['passed'] for c in boundary_cases),
             'engineering_complete':all(c['passed'] for c in checks),'human_review_performed':False}
    packet={'schema':'l01-published-review-packet/1','scope':scope,'costs':costs,'bands':bands,'notes':notes,'conflicts':conflicts,
       'review_instructions':'Review the exact source comparisons and units/conditions, make the three proposed source-disposition decisions, and provide a genuine scoped receipt. Owner assignment is not a signature. Technical checks do not establish reviewer qualification or independence.'}
    payloads={'scope.json':scope,'inventory.json':inventory,'costs.json':costs,'bands.json':bands,'notes.json':notes,
       'observations.json':observations,'sources.json':list(sources.values()),'conflicts.json':conflicts,
       'source-dispositions.json':dispositions,'checks.json':results,'review-packet.json':packet}
    for name,payload in payloads.items():write(out/name,payload)
    manifest={'schema':'l01-published-manifest/1','package_id':'L01-PUBLISHED-US-2026-r1','year':2026,'revision':1,
       'effective_from':'2026-01-01','effective_until':'2027-01-01','source_review_after_utc':'2026-11-24T00:00:00+00:00',
       'files_sha256':{name:sha(out/name) for name in payloads},'evidence_sha256':evidence_files,
       'code_sha256':{name:sha(ROOT/'cms-slice/scripts'/name) for name in ('l01_reference.py','l01_reference_build.py')},
       'status':'engineering_complete_pending_owner_review' if results['engineering_complete'] else 'engineering_incomplete'}
    write(out/'manifest.json',manifest)
    review={'schema':'l01-published-review/1','package_id':manifest['package_id'],'manifest_sha256':sha(out/'manifest.json'),
       'decision':'pending','reviewer':{'name':'','role':'','qualified_for_scope':None,'independent_of_sales':None},
       'accepted_ids':sorted(x['id'] for x in costs+bands+notes),'conditions_and_units_reviewed':False,
       'reviewed_at_utc':None,'review_after_utc':None,'receipt':'','revoked':False,
       'conflict_decisions':{c['id']:{'conflict_sha256':object_sha(c),'decision':'pending','reason':''} for c in conflicts},
       'note':'Template only; building never installs or creates actual human acceptance.'}
    write(out/'review-template.json',review)
    coverage={'scope':'D76 published reference only','costs_required':len(expected['cost_values']),'costs_present':len(costs),
       'bands_required':45,'bands_present':len(bands),'qualification_notes_required':len(expected['note_ids']),'qualification_notes_present':len(notes),
       'entries_with_exact_source_observations':len(costs+bands+notes),'engineering_complete':results['engineering_complete'],
       'checks_passed':results['passed'],'checks_required':len(checks),'boundary_cases_passed':results['income_boundaries_passed'],
       'boundary_cases_required':len(boundary_cases),'conflict_decisions_pending':len(conflicts),'human_acceptance':'pending',
       'consumer_reference_available':False,'personal_calculations_available':False,'earlier_broad_inventory':'151 obligations / 81 outstanding unchanged; discovered section230 remains a broad service-inventory finding outside this scoped reference'}
    write(out/'coverage.json',coverage)
    print(json.dumps(coverage,indent=2))
    if results['failed']:raise ValueError('Reference checks failed; inspect checks.json')
    return coverage


if __name__=='__main__':
    build()
