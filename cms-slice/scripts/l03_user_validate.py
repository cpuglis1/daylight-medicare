"""Validate r6 source integrity, exact source pointers and conservative gates."""
import collections,datetime,json,pathlib,sys,zipfile,csv,io
import l03_user_documents as d
import l03_scoped_reference as approved
from l03_user_reference import file_sha,PARENT_R4_PIN
from l03_reference_build import L02,PBP_SHA
from l03_validate import resolve,equal

def validate():
    approved.require_review();checks=[]
    def check(name,ok,detail):
        checks.append({'name':name,'passed':bool(ok),'detail':detail})
        if not ok:raise AssertionError((name,detail))
    cat=d.load(d.ROOT/'source-catalog.json');matrix=d.load(d.ROOT/'plan-document-matrix.json');relations=d.load(d.ROOT/'document-relations.json');summary=d.load(d.ROOT/'summary.json')
    check('all_downloads_retained',len(cat)==43 and len(d.load(d.ROOT/'owner-file-observations.json')['files'])==44,'44 files, one byte-identical duplicate; 43 unique immutable PDFs')
    check('all_source_pdf_and_text_hashes',all(file_sha(x['path'])==x['sha256']and file_sha(x['text_path'])==x['text_sha256']for x in cat),'Original bytes and extracted text checked, not official server byte identity')
    check('exact_document_relations',len(relations)==42 and all(x['visible_front_matter_identity_match']and x['visible_year_match']for x in relations),'40 newly supplied SB/EOC offering slots plus two Aetna copies; R0759-001 EOC cover visually read after OCR O/0 confusion')
    check('all_offerings_preserved',len(matrix)==72 and len({x['offering_id']for x in matrix})==72 and sum(x['documented']for x in matrix)==67,'67 documented, five missing; no deleted restricted offering')
    check('missing_five_erickson_only',[x['offering_id']for x in matrix if not x['documented']]==['2026:H5652:'+p+':000'for p in ['001','002','004','006','008']],'Ten SB/EOC slots remain missing; not counted as acquired')
    counts=collections.Counter()
    for p in d.rows(d.ROOT/'new-source-pages.jsonl.gz'):
        assert d.sha(p['text'].encode())==p['text_sha256']
        if 'layout_text'in p:assert d.sha(p['layout_text'].encode())==p['layout_text_sha256']
        counts[p['document_sha256']]+=1
    check('all_new_PDF_pages_retained',counts=={x['sha256']:x['pdf_pages']for x in cat},dict(documents=len(counts),pages=sum(counts.values())))
    field_count=service_count=pa_count=0
    for filename,key,expected in [('service-reconciliation.jsonl.gz','PBP_service_records_accounted',7305),('field-dispositions.jsonl.gz','service_field_references_accounted',173124),('authorization-referral-dispositions.jsonl.gz','PA_referral_comparisons',14610)]:
        n=0
        for x in d.rows(d.ROOT/filename):
            n+=1;assert x['accepted_for_reference']is False
        check(filename,n==expected and summary[key]==expected,'Full accounting; counts do not establish semantic correctness')
    cases=d.load(d.ROOT/'source-led-comparisons.json');check('all_twenty_have_source_led_checks',len({x['offering_id']for x in cases})==20,'Named fields only; not every benefit')
    cache={};csvcache={}
    with zipfile.ZipFile(L02/'acquisition-r1/raw'/PBP_SHA)as z:
        for c in cases:
            s=c['CMS_source']
            if not s:continue
            if 'pointer'in s:
                if s['member']not in cache:
                    raw=z.read(s['member']);assert d.sha(raw)==s['member_sha256'];cache[s['member']]=json.loads(raw)
                actual=resolve(cache[s['member']],s['pointer'])
            else:
                key=(s['archive_sha256'],s['member'])
                if key not in csvcache:
                    ap=L02/'acquisition-r1/raw'/s['archive_sha256'];assert file_sha(ap)==s['archive_sha256']
                    with zipfile.ZipFile(ap)as a:raw=a.read(s['member'])
                    assert d.sha(raw)==s['member_sha256'];csvcache[key]=list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))))
                actual=csvcache[key][s['record_ordinal']-1][s['field']].strip().replace('$','').replace(',','')
            if c['CMS_actual']is None:assert actual in ['',None]
            else:assert equal(actual,c['CMS_actual'])
            assert c['source_values_equal']==(equal(actual,c['expected_from_SB'])if actual not in ['',None]else None)
    check('all_named_CMS_pointers_reproduced',True,'Independently reopened pinned JSON/CSV members and exact pointers/rows; source-value differences are retained')
    rider=d.load(d.ROOT/'rider-reference-reconciliation.json');check('rider_references_disposed',all('unclassified'not in x['classification']for x in rider),dict(collections.Counter(x['classification']for x in rider)))
    quality=d.load(d.ROOT/'second-pass-money-validation.json');check('UHC_headline_money_second_pass',len(quality)==28 and all(x['money_multiset_equal']for x in quality),'150dpi psm3 versus 300dpi psm6, 14 SBs pages 2 and 3; extraction check, not complete benefit approval')
    protected=d.load(d.DATA/'protected-before.json');changed=[p for p,h in protected.items()if file_sha(d.REPO/p)!=h]
    check('protected_L01_L02_and_UI_unchanged',len(protected)==649 and not changed,{'checked':len(protected),'changed':changed})
    check('accepted_r4_unchanged',file_sha(approved.ROOT/'manifest.json')==PARENT_R4_PIN and len(approved.lookup({'year':2026})['entries'])==535,'Actual accepted gate still returns the exact original allowlist')
    check('no_new_acceptance_or_completion_claim',summary['full_L03_complete']is False and summary['new_accepted_entries']==0,'New evidence remains research; clinical/personal costs/recommendations and deployment excluded')
    d.dump(d.ROOT/'validation.json',{'passed':True,'checked_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'checks':checks,'limitation':'Source integrity, exact named comparisons, extraction and boundary tests. This is not full semantic verification of every benefit/condition or owner approval.'})
    print(json.dumps({'passed':True,'checks':len(checks)}));return checks
def seal():
    if (d.ROOT/'manifest.json').exists():raise RuntimeError('Already sealed; use a new revision')
    codes=['l03_user_documents.py','l03_user_reconcile.py','l03_user_cases.py','l03_user_supplemental.py','l03_user_reference.py','l03_user_validate.py']
    paths=['cms-slice/scripts/'+p for p in codes]+['cms-slice/tests/test_l03_user_documents.py']
    manifest={'schema':'l03-owner-source-reconciliation/1','package_id':d.PACKAGE,'parent_accepted_r4_manifest_sha256':PARENT_R4_PIN,'files_sha256':{str(p.relative_to(d.ROOT)):file_sha(p)for p in sorted(d.ROOT.rglob('*'))if p.is_file()and p.name!='manifest.json'},'code_sha256':{p:file_sha(d.REPO/p)for p in paths},'new_evidence_accepted':False,'full_L03_complete':False}
    d.dump(d.ROOT/'manifest.json',manifest);print('manifest_sha256',file_sha(d.ROOT/'manifest.json'))
if __name__=='__main__':
    validate()
    if '--seal'in sys.argv:seal()
