"""Reproduce r7 source comparisons and preserve the accepted reference gate."""
import collections,csv,datetime,gzip,io,json,pathlib,shutil,zipfile
import l03_erickson_documents as d
import l03_scoped_reference as accepted
from l03_erickson_reference import file_sha, PARENT_R4_PIN
from l03_reference_build import L02,PBP_SHA
from l03_validate import resolve,equal

PARENT_R6_PIN='27615e5ac4e9d21f20b136498bc842b7746db75ab80c0001a365ac16a6ecf161'

def validate():
    checks=[]
    def check(name,ok,detail):
        checks.append({'name':name,'passed':bool(ok),'detail':detail})
        if not ok:raise AssertionError((name,detail))
    from l03_user_reference import verify as verify_r6
    verify_r6(expected_manifest_sha256=PARENT_R6_PIN)
    check('sealed_r6_data_and_code_unchanged',True,PARENT_R6_PIN)
    accepted.require_review()
    cat=d.load(d.ROOT/'source-catalog.json');matrix=d.load(d.ROOT/'plan-document-matrix.json');relations=d.load(d.ROOT/'document-relations.json');summary=d.load(d.ROOT/'summary.json')
    check('owner_files_retained',len(cat)==53 and len(d.load(d.ROOT/'owner-file-observations.json')['files'])==54,'54 filenames, 53 distinct PDF byte identities; one duplicate retained as an observation')
    check('all_document_and_text_hashes',all(file_sha(x['path'])==x['sha256']and file_sha(x['text_path'])==x['text_sha256']for x in cat),'Original owner-supplied bytes and extracted text; official locator is not asserted to be official byte identity')
    check('exact_front_matter_relations',len(relations)==52 and all(x['visible_front_matter_identity_match']and x['visible_year_match']for x in relations),'Prior 42 observations plus ten Erickson documents with visible 2026 contract/plan/segment')
    check('SB_EOC_slots_complete_for_working_input',len(matrix)==72 and len({x['offering_id']for x in matrix})==72 and all(x['documented']and not x['missing_document_kinds']for x in matrix),'144/144 SB/EOC offering slots; this is document coverage, not full benefit corroboration or an L02 market certification')
    counts=collections.Counter()
    for p in d.rows(d.ROOT/'new-source-pages.jsonl.gz'):
        assert d.sha(p['text'].encode())==p['text_sha256']
        if 'layout_text'in p:assert d.sha(p['layout_text'].encode())==p['layout_text_sha256']
        counts[p['document_sha256']]+=1
    check('all_user_PDF_pages_retained',counts=={x['sha256']:x['pdf_pages']for x in cat}and sum(counts.values())==6385,{'documents':len(counts),'pages':sum(counts.values())})
    for filename,expected in [('service-reconciliation.jsonl.gz',7305),('field-dispositions.jsonl.gz',173124),('authorization-referral-dispositions.jsonl.gz',14610)]:
        n=0
        for x in d.rows(d.ROOT/filename):n+=1;assert x['accepted_for_reference']is False
        check(filename,n==expected,'Full accounting; not a completeness or semantic correctness assertion')
    cases=d.load(d.ROOT/'erickson-source-led-comparisons.json');riders=d.load(d.ROOT/'optional-dental-rider-reconciliation.json')
    check('source_led_Erickson_case_inventory',len(cases)==177 and len({c['offering_id']for c in cases})==5,'177 named SB transcriptions including selective deductible, distinct OON MOOP and hospital charge-band endpoints')
    cache={};csvcache={};n=0
    with zipfile.ZipFile(L02/'acquisition-r1/raw'/PBP_SHA)as archive:
        for c in cases:
            s=c.get('CMS_source')
            if not s:continue
            if 'pointer'in s:
                if s['member']not in cache:
                    raw=archive.read(s['member']);assert d.sha(raw)==s['member_sha256'];cache[s['member']]=json.loads(raw)
                actual=resolve(cache[s['member']],s['pointer'])
            else:
                key=(s['archive_sha256'],s['member'])
                if key not in csvcache:
                    ap=L02/'acquisition-r1/raw'/s['archive_sha256'];assert file_sha(ap)==s['archive_sha256']
                    with zipfile.ZipFile(ap)as a:raw=a.read(s['member'])
                    assert d.sha(raw)==s['member_sha256'];csvcache[key]=list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))))
                actual=csvcache[key][s['record_ordinal']-1][s['field']].strip().replace('$','').replace(',','')
            assert equal(actual,c['CMS_actual'])and c['CMS_value_equal']==equal(actual,c['value']);n+=1
        for rider in riders:
            for c in rider['CMS_amount_comparisons']:
                s=c['source'];actual=resolve(cache[s['member']],s['pointer'])
                assert equal(actual,c['CMS_actual'])and equal(actual,c['expected_from_EOC'])
    check('exact_CMS_source_reproduction',n==133 and all(c['CMS_value_equal']is not False for c in cases),'133 exact pointer/CSV checks agree; 44 named carrier statements make no CMS equivalence claim')
    check('optional_dental_variants_separate',len(riders)==5 and all(r['replaces_base_dental']and r['cannot_add_base_and_rider_allowances']and r['base_benefits_must_not_include_this_variant']for r in riders),'Five separately purchased variants; 75 exact CMS dental amount checks agree. External procedure frequencies remain held.')
    chart=list(d.rows(d.ROOT/'carrier-chart-rows.jsonl.gz'));ends={r['offering_id']:min(p['pdf_page']for p in r['EOC_evidence'])for r in riders}
    check('optional_rider_not_in_base_medical_chart',all(max(r['pages'])<ends[r['offering_id']]for r in chart if r['offering_id']in ends),'No base medical row may inherit the rider cost column or dental exclusions')
    q=d.load(d.ROOT/'second-pass-money-validation.json')
    check('Erickson_SB_money_second_pass',len(q)==45 and all(x['money_multiset_equal']for x in q),'150dpi psm3 versus 300dpi psm6, five SBs pages 2-10; extraction check, not independent complete semantic review')
    dictionary=d.load(d.R1/'field-dictionary.json')['fields'];entry=next(f for f in dictionary if f['file']=='pbp_b14_preventive'and f['name']=='pbp_b14c_bendesc_ihss')
    check('mandatory_supplemental_code_not_No',entry['codes']['2']=='Mandatory','Do not delete a missing source heading by interpreting inNetworkOptionSelected=2 as No; the cross-format AMO source says Mandatory')
    protected=d.load(d.DATA/'protected-before.json');changed=[p for p,h in protected.items()if file_sha(d.REPO/p)!=h]
    check('protected_L01_L02_UI_unchanged',len(protected)==649 and not changed,{'checked':len(protected),'changed':changed})
    check('accepted_r4_unchanged',file_sha(accepted.ROOT/'manifest.json')==PARENT_R4_PIN and len(accepted.lookup({'year':2026})['entries'])==535,'Accepted exact allowlist still has 535 entries; no new inherited acceptance')
    check('honest_full_scope_status',summary['full_L03_complete']is False and summary['new_accepted_entries']==0,'Document acquisition is complete for the 72 inputs; remaining exact amount/condition/source-definition work is explicit')
    result={'passed':True,'checked_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'checks':checks,'limitation':'Source integrity, bounded source-led comparisons and regression boundaries. Does not certify every benefit field or independently approve new evidence.'}
    d.dump(d.ROOT/'validation.json',result);print(json.dumps({'passed':True,'checks':len(checks)}));return result

def seal():
    if (d.ROOT/'manifest.json').exists():raise RuntimeError('Already sealed; create a new revision')
    codes=['l03_erickson_documents.py','l03_erickson_reconcile.py','l03_erickson_cases.py','l03_erickson_riders.py','l03_erickson_reference.py','l03_erickson_validate.py']
    paths=['cms-slice/scripts/'+p for p in codes]+['cms-slice/tests/test_l03_erickson.py']
    manifest={'schema':'l03-owner-source-reconciliation/2','package_id':d.PACKAGE,'parent_accepted_r4_manifest_sha256':PARENT_R4_PIN,'parent_r6_manifest_sha256':PARENT_R6_PIN,'files_sha256':{str(p.relative_to(d.ROOT)):file_sha(p)for p in sorted(d.ROOT.rglob('*'))if p.is_file()and p.name!='manifest.json'},'code_sha256':{p:file_sha(d.REPO/p)for p in paths},'new_evidence_accepted':False,'full_L03_complete':False}
    d.dump(d.ROOT/'manifest.json',manifest);print('manifest_sha256',file_sha(d.ROOT/'manifest.json'))

if __name__=='__main__':
    import sys
    validate()
    if '--seal'in sys.argv:seal()
