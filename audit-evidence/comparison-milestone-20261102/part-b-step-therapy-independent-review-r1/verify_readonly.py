"""Replay only saved policy acquisition provenance; no network or database calls."""
from pathlib import Path
import hashlib,json,re,struct,subprocess,shutil
ROOT=Path(__file__).resolve().parents[3]
P=Path(__file__).resolve().parent
C=ROOT/'docs/data/l03-ma-benefits-2026-11-02-whole-offering-r12/part-b-step-therapy-source-followup-r1'
def h(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):return json.loads(p.read_text())
def verify():
    checks=0
    def check(v):
        nonlocal checks
        assert v
        checks+=1
    for f in [C/'FREEZE_R1.json',P/'EXPECTED_FREEZE_R1.json']:
        for row in load(f)['members']:
            q=f.parent/row['path'];check(q.stat().st_size==row['bytes']);check(h(q)==row['sha256'])
    data=load(C/'SOURCE_LOCATOR_STATUS_R1.json')
    for version,count,number,date in zip(data['versions'],[26,23],['IAP.001.28','IAP.001.31'],['2026-01-01','2026-10-01']):
        pdf=C/version['local_path']
        info=subprocess.run([shutil.which('pdfinfo'),str(pdf)],capture_output=True,text=True,check=True).stdout
        check(int(re.search(r'^Pages:\s+(\d+)',info,re.M).group(1))==count)
        check(version['policy_number']==number and version['printed_effective_date']==date)
        check(version['bytes']==pdf.stat().st_size and version['sha256']==h(pdf))
        check(version['ordinary_public_request'] is True and version['status']==200)
    for row in load(C/'ORIGINAL_SOURCE_LOCATORS_R1.json'):
        q=ROOT/row['path'];b=q.read_bytes();check(h(q)==row['sha256'])
        size=list(struct.unpack('>II',b[16:24]));check(size==row['image_dimensions'])
        a,b,c,d=row['pixel_bbox'];w,ht=size;check(0<=a<c<=w and 0<=b<d<=ht)
    renders=load(P/'INDEPENDENT_RENDER_REPLAY_R1.json')
    check(renders['all_byte_equal'] is True and len(renders['pages'])==5)
    for row in renders['pages']:
        q=ROOT/row['path'];check(h(q)==row['sha256']);check(q.read_bytes()==(C/q.name).read_bytes())
    check(data['prior_r2_source_questions_changed']==0)
    check(data['source_acceptance'] is False and data['canonical_adoption'] is False)
    check(data['personal_drug_decision'] is False and data['app_database_runtime_writes']==0)
    return {'schema':'daylight.part-b-step-therapy.independent-acquisition-replay.r1','checks_passed':checks,'fresh_render_pages_byte_equal':5,'exact_source_locator_regions':7,'new_acceptance':False,'drug_criteria_interpreted':False,'network_or_database_call':False}
if __name__=='__main__':print(json.dumps(verify(),indent=2,sort_keys=True))
