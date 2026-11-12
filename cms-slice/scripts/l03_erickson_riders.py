"""Separate the five named optional dental variants from the base plan benefits."""
import json, re, zipfile
import l03_erickson_documents as d
from l03_erickson_reconcile import source_evidence, value_occurs, clean
from l03_reference_build import L02, PBP_SHA
from l03_validate import equal

RIDER_PAGES={'001':(131,135),'002':(119,123),'004':(132,136),'006':(129,133),'008':(128,132)}

def build():
    if (d.ROOT/'manifest.json').exists():raise RuntimeError('Sealed r7 is immutable')
    matrix={p['offering_id']:p for p in d.load(d.ROOT/'plan-document-matrix.json')}
    pages={(p['document_sha256'],p['pdf_page']):p for p in d.rows(d.ROOT/'new-source-pages.jsonl.gz')}
    out=[]
    with zipfile.ZipFile(L02/'acquisition-r1/raw'/PBP_SHA)as archive:
      for plan,(first,last)in RIDER_PAGES.items():
        oid=f'2026:H5652:{plan}:000';m=matrix[oid];eh=m['document_matches']['EOC']['sha256'];sbh=m['document_matches']['SB']['sha256']
        ps=[pages[(eh,n)]for n in range(first,last+1)];text='\n'.join(p['text']for p in ps)
        assert 'Section 2.1'in ps[0]['text']and 'Platinum Dental Rider'in text
        assert 'cannot be combined'in text and 'replace any'in text
        assert value_occurs(44,'USD/month',text)and value_occurs(1500,'USD/year',text)and value_occurs(50,'percent',text)
        assert re.search(r'frequency limitations',text,re.I)
        member=f'H5652-{plan}-000-2026.json';raw=archive.read(member);obj=json.loads(raw)['pbp'][0]
        packs=obj['costShareGroups']['optionalSupplementalPackages']['optionalSupplementalPackagesDetails']['optSupPackagesData'];ix=next(i for i,x in enumerate(packs)if x['optSupPkgName']=='Dental Platinum Rider');pack=packs[ix]
        base=f'/pbp/0/costShareGroups/optionalSupplementalPackages/optionalSupplementalPackagesDetails/optSupPackagesData/{ix}'
        compare=[]
        for n,b in enumerate(pack['benefitPackages']):
            cat=b['categoryCode'];bi=b['benefitPackagesInfo']
            if cat=='16b':pointer='/PlanBenefitCoverageComponent/bdMaximumAmount';expected=1500;unit='USD/year'
            elif cat.startswith('16b')and 'CopaymentComponent'in bi:pointer='/CopaymentComponent/bdCopaymentAmount';expected=0;unit='USD'
            elif cat.startswith('16c')and 'CoinsuranceComponent'in bi:pointer='/CoinsuranceComponent/bdCoinsuranceAmount';expected=50;unit='percent'
            else:continue
            actual=bi
            for part in pointer.strip('/').split('/'):actual=actual[part]
            compare.append({'category_code':cat,'expected_from_EOC':str(expected),'unit':unit,'CMS_actual':actual,'equal':equal(actual,expected),'source':{'archive_sha256':PBP_SHA,'member':member,'member_sha256':d.sha(raw),'pointer':base+f'/benefitPackages/{n}/benefitPackagesInfo'+pointer}})
        assert compare and all(x['equal']for x in compare)
        out.append({'id':oid+':r7:optional:PlatinumDental','offering_id':oid,'variant':'optional_enrolled_Platinum_Dental_Rider','base_benefits_must_not_include_this_variant':True,'replaces_base_dental':True,'cannot_add_base_and_rider_allowances':True,'monthly_additional_premium':{'value':'44','unit':'USD/month'},'shared_annual_plan_payment_maximum':{'value':'1500','unit':'USD/year','scope':'All covered preventive/diagnostic/comprehensive services; in/out-of-network share the maximum.'},'covered_preventive_diagnostic':{'value':'0','unit':'USD/copayment','qualification':'Covered services only, within annual maximum and procedure/frequency limits.'},'covered_comprehensive':{'value':'50','unit':'percent_coinsurance','qualification':'Covered services only; remaining charges after plan maximum belong to member.'},'enrollment_qualification':'Applies only after separate rider enrollment and payment. Published enrollment window/effective date/termination rules retained in full EOC passage; no individual enrollment conclusion.','network_qualification':'Out-of-network coverage exists, but provider can charge more than plan payment, including on $0-copay services. Same maximum/limitations/exclusions apply.','frequency_detail_status':'EOC names an external UHC Dental Medicare procedure guide. Full CDT-level frequency/prior-tooth-history schedule not acquired or validated; do not publish a specific procedure frequency from this record.','exclusions':'Full original EOC rider exclusion list retained in evidence, including cosmetic procedures, implants, orthodontics and unspecified procedures; not a blanket exclusion of medically covered dental in other benefits.','SB_evidence':[source_evidence(pages[(sbh,5)]),source_evidence(pages[(sbh,9 if plan=='002'else 10)])],'EOC_evidence':[source_evidence(p)for p in ps],'full_source_passage_sha256':d.sha(text.encode()),'CMS_package_source':{'archive_sha256':PBP_SHA,'member':member,'member_sha256':d.sha(raw),'pointer':base},'CMS_amount_comparisons':compare,'accepted_for_reference':False,'consumer_usable':False,'full_procedure_rider_complete':False})
    d.dump(d.ROOT/'optional-dental-rider-reconciliation.json',out)
    d.dump(d.ROOT/'optional-dental-rider-summary.json',{'offerings':len(out),'named_variants':len(out),'CMS_amount_comparisons':sum(len(x['CMS_amount_comparisons'])for x in out),'all_amounts_agree':all(c['equal']for x in out for c in x['CMS_amount_comparisons']),'external_procedure_frequency_guide_status':'not acquired/validated; optional detailed procedure claims held','full_rider_complete':False})
    return out

if __name__=='__main__':print({'riders':len(build())})
