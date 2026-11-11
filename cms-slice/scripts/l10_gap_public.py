"""Published group source observations, kept distinct from filed/personal rates."""
from collections import Counter
from decimal import Decimal
import json
from pathlib import Path
import re
from html.parser import HTMLParser

import pdfplumber
from pypdf import PdfReader

from l10_gap_sources import ROOT, WORK, read, write, sha

PUB=WORK/'public-sources'
OUT=WORK/'build-r1'
AGES=['<65','65-69','70-74','75-79','80+']
PAIR=r'Issue Age\s*(<65|65-69|70-74|75-79|80\+)\s*(\$[\d,]+\.\d{2})\s*(\$[\d,]+\.\d{2})'
TRIPLE=PAIR+r'\s*(\$[\d,]+\.\d{2})'


def html_text(raw):
    class Text(HTMLParser):
        def __init__(self):super().__init__();self.skip=0;self.parts=[]
        def handle_starttag(self,tag,attrs):
            if tag in ['script','style']:self.skip+=1
        def handle_endtag(self,tag):
            if tag in ['script','style']:self.skip=max(0,self.skip-1)
        def handle_data(self,data):
            if not self.skip:self.parts.append(data)
    parser=Text();parser.feed(raw.decode('utf-8',errors='replace'))
    return ' '.join(' '.join(parser.parts).split())


def cents(raw):return int(Decimal(raw.replace('$','').replace(',',''))*100)


def build(out=None):
    out=Path(out) if out is not None else OUT
    if (out/'SEALED').exists():raise ValueError('Sealed revision')
    observations=[];conditions=[]
    def add(doc,group,page,plan,age,zone,raw,unit,row):
        path=PUB/'documents'/doc
        observations.append({'id':f'{group}:p{page}:r{row}:plan{plan}:zone{zone}',
            'source_pdf':str(path.relative_to(ROOT)),'source_sha256':sha(path),'source_page':page,
            'group':group,'plan_letter_raw':plan,'issue_age_band_raw':age,'zone':zone,
            'amount_raw':raw,'amount_cents':cents(raw),'unit':unit,'published_document_year':2026,
            'filed_rate_approval_period':None,'policy_form':None,'personal_quote':False,
            'group_eligibility':'conditional_source_rules_not_a_personal_determination',
            'consumer_release_enabled':False,'acceptance':'pending'})
    path=PUB/'documents/fsrbc-cigna-rates-2026.pdf'
    text=PdfReader(path).pages[0].extract_text();rows=re.findall(PAIR,text);assert len(rows)==15
    for ri,(age,left,right) in enumerate(rows):
        assert age==AGES[ri%5]
        plan=['F','G','N'][ri//5]
        for zone,amount in [('FL_330_334',left),('FL_except_330_334',right)]:
            add(path.name,'FSRBC_Cigna_proposal',1,plan,age,zone,amount,'not_explicitly_labeled_in_proposal',ri)
    path=PUB/'documents/orange-county-retiree-guide-2026.pdf'
    with pdfplumber.open(path) as pdf:
        tables=pdf.pages[42].extract_tables()
        for ti,zone in enumerate(['FL_except_330_334','FL_330_334']):
            table=tables[ti];assert table[0]==['Age Bracket*','Plan G','Plan F','Plan N']
            for ri,row in enumerate(table[1:]):
                assert row[0]=='Issue Age '+AGES[ri]
                for ci,plan in enumerate(['G','F','N']):
                    add(path.name,'Orange_County_retirees',43,plan,AGES[ri],zone,row[ci+1],'USD/month',ri+5*ti)
    path=PUB/'documents/fsrbc-annual-enrollment-2026.pdf'
    text=PdfReader(path).pages[24].extract_text();rows=re.findall(TRIPLE,text);assert len(rows)==4
    assert '2026 Monthly Premiums' in text
    for ri,(age,*amounts) in enumerate(rows):
        assert age==AGES[ri+1]
        for plan,amount in zip(['G','N','F'],amounts):
            add(path.name,'FSRBC_HealthSpring_guide',25,plan,age,'FL_except_330_334',amount,'USD/month',ri)

    def condition(doc,page,excerpt,meaning):
        path=PUB/'documents'/doc;text=PdfReader(path).pages[page-1].extract_text()
        assert ' '.join(excerpt.split()) in ' '.join(text.split())
        conditions.append({'id':f'group-condition-{len(conditions)+1}','source_pdf':str(path.relative_to(ROOT)),
            'source_sha256':sha(path),'page':page,'excerpt':excerpt,'meaning':meaning,
            'personal_applicability':'not_determined','consumer_release_enabled':False,'acceptance':'pending'})
    condition('fsrbc-cigna-rates-2026.pdf',2,'Cigna Healthcare retains the right to decline to offer coverage.',
              'The document is a group-specific proposal, not a binding consumer offer or filed rate approval.')
    condition('fsrbc-cigna-rates-2026.pdf',2,'The rates do not advance with age.',
              'Source issue-age statement; preserve separately from enrollment-age guide wording.')
    condition('fsrbc-annual-enrollment-2026.pdf',25,'Available to Manatee, Orange and Osceola',
              'This group route is district-restricted; Collier residence alone does not establish eligibility.')
    condition('fsrbc-annual-enrollment-2026.pdf',25,'2026 Part B Deductibles have not been published by CMS at the time this document was created',
              'Retain the guide but do not promote its explicitly older benefit constants into the accepted 2026 federal reference.')
    condition('fsrbc-annual-enrollment-2026.pdf',3,'65 and older',
              'Guide audience is age-restricted. Under-65 proposal rows are retained without inferring eligibility.')
    condition('orange-county-retiree-guide-2026.pdf',5,'Orange County employees meeting certain requirements and their eligible covered dependents',
              'Employer retiree/eligible-dependent route; not a generally available individual product.')
    condition('orange-county-retiree-guide-2026.pdf',43,'you must also elect a Cigna RX Medicare (PDP) Plan (High or low).',
              'Published group pairing condition only; no automatic personal plan combination or PDP rule approval.')
    condition('orange-county-retiree-guide-2026.pdf',43,'You will retain the age bracket you first enrolled with Cigna Surround, unless you change plans.',
              'Preserve exact group age-basis qualification.')
    write(out/'group-rate-observations.json',observations);write(out/'group-conditions.json',conditions)
    comparisons=[]
    def compare_groups(a,b):
        left={(r['plan_letter_raw'],r['issue_age_band_raw'],r['zone']):r for r in observations if r['group']==a}
        right={(r['plan_letter_raw'],r['issue_age_band_raw'],r['zone']):r for r in observations if r['group']==b}
        for key in sorted(left.keys()&right.keys()):
            x,y=left[key],right[key]
            comparisons.append({'left_id':x['id'],'right_id':y['id'],'same_amount':x['amount_cents']==y['amount_cents'],
                'left_cents':x['amount_cents'],'right_cents':y['amount_cents'],
                'meaning':'Amount-only comparison; group/account/form identity and unit applicability are not inherited',
                'groups_merged':False,'personal_quote':False})
    compare_groups('FSRBC_Cigna_proposal','Orange_County_retirees')
    compare_groups('FSRBC_Cigna_proposal','FSRBC_HealthSpring_guide')
    write(out/'group-comparisons.json',comparisons)

    # Current published pages are separate evidence, never assigned a 2026
    # coverage period from the date of this research.
    public_claims=[]
    def html_claim(sid,excerpt,values):
        receipt=read(PUB/(sid+'.json'));raw=(PUB/'raw'/receipt['sha256']).read_bytes()
        text=html_text(raw)
        assert ' '.join(excerpt.split()) in text,(sid,excerpt)
        public_claims.append({'source_id':sid,'source_sha256':receipt['sha256'],'source_url':receipt['requested_url'],
            'excerpt':excerpt,'values':values,'source_scope':'Current published page captured October 28; exact 2026 coverage period not established',
            'current_or_future_sale':'not_determined','acceptance':'pending','consumer_release_enabled':False})
    html_claim('everence-florida-public','you must have a relationship with a Mennonite or Anabaptist church or church organization.',
               {'published_membership_condition':'Mennonite or Anabaptist church/organization relationship'})
    html_claim('everence-florida-public','Plan A is 2185084, Plan F is 2185085, Plan G is 2185020, Plan L is 2185086.',
               {'form_codes':{'A':'2185084','F':'2185085','G':'2185020','L':'2185086'}})
    html_claim('wps-policy-forms-public','EPIC_FL_PlanA_1710, EPIC_FL_PlanC_1710, EPIC_FL_PlanF_1710, EPIC_FL_PlanG_1710, EPIC_FL_PlanK_1710, EPIC_FL_PlanL_1710, EPIC_FL_PlanN_1710.',
               {'form_codes':{p:f'EPIC_FL_Plan{p}_1710' for p in ['A','C','F','G','K','L','N']}})
    html_claim('americo-medsup-public','FL – AFL500-A, AFL500-F, AFL500-G, AFL500-N;',
               {'form_codes':{p:'AFL500-'+p for p in ['A','F','G','N']}})
    html_claim('usaa-florida-public','MSM93848FL 06-10 (Plan A), MSM93849FL 06-10 (Plan F), MSM98372FL 06-15 (Plan N), MSM98995FL 09-18 (Plan G).',
               {'form_codes':{'A':'MSM93848FL 06-10','F':'MSM93849FL 06-10','N':'MSM98372FL 06-15','G':'MSM98995FL 09-18'}})
    write(out/'carrier-published-claims.json',public_claims)

    questionnaire=PUB/'documents/physicians-life-fl-household-questionnaire.pdf'
    qt=' '.join(PdfReader(questionnaire).pages[0].extract_text().split())
    qclaims=[]
    for excerpt,meaning in [
        ('This form is only for use with Physicians Life Medicare Supplement plans issued in 2019 or later.',
         'Published form applicability; exact current policy/2026 continuation still needs its filing evidence.'),
        ('Do you reside in the same household with any other person who owns a Medicare Supplement policy from Physicians Life Insurance Company or Physicians Mutual Insurance Company?',
         'First published household criterion; no customer answer inferred.'),
        ('If yes, do you reside with less than four other Medicare-eligible adults?',
         'Second published household criterion; questionnaire requires YES to both questions.'),
        ('Upon approval, the discount will become effective on the monthly renewal date following receipt of this request.',
         'Source approval/timing condition; amount, underwriting and personal eligibility not inferred.')]:
        assert excerpt in qt
        qclaims.append({'source_pdf':str(questionnaire.relative_to(ROOT)),'source_sha256':sha(questionnaire),
            'page':1,'excerpt':excerpt,'meaning':meaning,'discount_percent':None,
            'exact_2026_applicability':'unaccepted_pending_exact_form_and_period_join','personal_quote':False,'acceptance':'pending'})
    write(out/'published-discount-questionnaire.json',qclaims)

    companies={'everence-florida-public':'EVERENCE ASSOCIATION, INC.',
               'wps-policy-forms-public':'EPIC LIFE INSURANCE COMPANY',
               'americo-medsup-public':'AMERICO FINANCIAL LIFE AND ANNUITY INSURANCE COMPANY',
               'usaa-florida-public':'USAA LIFE INSURANCE COMPANY'}
    crosswalk=[];metadata=[]
    for line in (WORK.parent/'build-r2/filing-metadata.jsonl').open():
        n=json.loads(line)
        if n['source_native']['CoNm'] in companies.values():metadata.append(n)
    for claim in public_claims:
        for plan,form in claim['values'].get('form_codes',{}).items():
            exact=[{'row_id':r['id'],'case':r['source_native']['FileLogNumber'],'form_raw':r['source_native']['FormNum']}
                   for r in metadata if r['source_native']['CoNm']==companies[claim['source_id']] and r['source_native']['FormNum']==form]
            nearby=[{'row_id':r['id'],'case':r['source_native']['FileLogNumber'],'form_raw':r['source_native']['FormNum']}
                    for r in metadata if r['source_native']['CoNm']==companies[claim['source_id']] and r['source_native']['FormNum'] and
                    r['source_native']['FormNum']!=form and re.sub(r'\s+','',r['source_native']['FormNum']).startswith(re.sub(r'\s+','',form))]
            crosswalk.append({'company':companies[claim['source_id']],'source_id':claim['source_id'],
                'plan_letter_published':plan,'form_code_published':form,'exact_metadata_matches':exact,
                'prefix_or_spacing_candidates_not_equivalent':nearby,'actual_2026_period':None,
                'source_scope':claim['source_scope'],'acceptance':'pending'})
    write(out/'carrier-form-crosswalk.json',crosswalk)
    return {'group_observations':len(observations),'group_conditions':len(conditions),
            'amount_comparisons':len(comparisons),'amount_comparison_counts':dict(Counter(c['same_amount'] for c in comparisons)),
            'current_carrier_claims':len(public_claims),'published_questionnaire_conditions':len(qclaims),
            'published_form_crosswalk_entries':len(crosswalk)}


if __name__=='__main__':print(json.dumps(build(),indent=2))
