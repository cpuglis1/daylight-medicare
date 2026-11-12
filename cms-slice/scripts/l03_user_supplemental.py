"""Named Wellcare supplemental benefit checks, read from exact SB/EOC pages.

These are carrier statements, not an inferred personal allowance or an assertion
that every PBP child field is equivalent. The 240/242 neighbor columns are never
used for Collier's 241/243 offerings.
"""
import collections, json, pathlib, re
import l03_user_documents as d
from l03_user_reconcile import source_evidence, value_occurs

# plan: hearing per ear/year + SB/EOC pages; dental annual cap + pages;
# combined routine eyewear annual cap + pages; monthly shared wallet + pages.
FACTS={
 '198':[(1000,9,64),(None,11,58),(100,12,97),(None,23,None)],
 '199':[(500,9,65),(3000,11,58),(200,12,98),(20,23,100)],
 '202':[(1000,8,69),(5000,10,62),(400,11,105),(50,22,106)],
 '239':[(1000,7,52),(5000,9,45),(200,10,85),(35,15,86)],
 '241':[(1500,9,68),(5000,12,60),(400,13,102),(101,27,104)],
 '243':[(1500,9,66),(4000,12,58),(400,13,101),(160,23,103)],
}
def build():
    if (d.ROOT/'manifest.json').exists():raise RuntimeError('Sealed r6 is immutable')
    cat={x['sha256']:x for x in d.load(d.ROOT/'source-catalog.json')};matrix={x['offering_id']:x for x in d.load(d.ROOT/'plan-document-matrix.json')}
    pages={(p['document_sha256'],p['pdf_page']):p for p in d.rows(d.ROOT/'new-source-pages.jsonl.gz')}
    sb={(p['offering_id'],p['source_evidence']['pdf_page']):p for p in d.rows(d.ROOT/'SB-exact-plan-pages.jsonl.gz')}
    types=[('hearing_aid_allowance_per_ear','USD/ear/year','hearing aids','At most two non-implantable hearing aids each year, per-ear cap; costs over the cap are the member responsibility. Participating hearing provider and PA conditions remain attached. Warranty and batteries are included as stated, not a separate cash allowance.'),('routine_comprehensive_dental_plan_payment_maximum','USD/year','Dental','Maximum plan payment for covered comprehensive dental services; preserve service-specific copays, procedure/frequency limits, exclusions and network. A missing annual cap does not mean all dental services are unlimited or free.'),('shared_routine_eyewear_allowance','USD/year','eyewear','One combined routine eyewear budget for its listed lenses/frames/contacts, not a fresh allowance for each item. Costs above the cap are the member responsibility. Medicare-covered post-cataract eyewear is separate and cannot use this routine cap to increase its benefit.'),('shared_Spendables_allowance','USD/month','Spendables','One shared card budget for listed OTC/dental/vision/hearing uses. Unused monthly amounts roll forward and expire at plan-year end. Expanded food/utilities/gas/home/rent uses require the stated SSBCI qualification; no individual eligibility is inferred and no second allowance is added.')]
    out=[]
    for plan,facts in FACTS.items():
        o='2026:H1032:'+plan+':000';m=matrix[o]
        if not m['documented']:continue
        for spec,(amount,sn,en)in zip(types,facts):
            name,unit,anchor,meaning=spec
            if amount is None:continue # no arbitrary numeric representation of absence/no cap
            s=sb[(o,sn)];e=pages[(m['document_matches']['EOC']['sha256'],en)]
            assert value_occurs(amount,unit,s['text']),(o,name,'SB value')
            assert value_occurs(amount,unit,e['text']),(o,name,'EOC value')
            assert anchor.lower()in e['text'].lower(),(o,name,'exact EOC service')
            out.append({'id':o+':r6:supplemental:'+name,'offering_id':o,'field':name,'value':str(amount),'unit':unit,'SB_evidence':s['source_evidence'],'EOC_evidence':source_evidence(e),'SB_exact_plan_column':s['column_binding'],'interpretation':meaning,'comparison':'AI read exact SB and EOC named service/amount/period; full source conditions attached','CMS_same_field_equivalence_claim':False,'accepted_for_reference':False,'consumer_usable':False})
    d.dump(d.ROOT/'supplemental-source-led-checks.json',out)
    return out
if __name__=='__main__':
    x=build();print(json.dumps({'named_supplemental_checks':len(x),'offering_count':len({r['offering_id']for r in x})}))
