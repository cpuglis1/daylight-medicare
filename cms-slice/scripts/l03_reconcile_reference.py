"""Read-only, explicitly partial r2 research reference. Consumer use stays held."""
import json,pathlib
from l03_reference_build import DATA,REPO,sha
from l03_reconcile import OUT,readlines

R1_PIN='84c84fb2801e3135a48bce0067afcb26cb72ea763630e3d78ecd7472efc22912'
def verify(root=OUT,expected_manifest_sha256=None):
 path=root/'package-manifest.json';b=path.read_bytes()
 if expected_manifest_sha256 is not None and sha(b)!=expected_manifest_sha256:raise ValueError('r2 manifest pin mismatch')
 m=json.loads(b)
 if m['r1_manifest_sha256']!=R1_PIN or sha((DATA/'build-r1/package-manifest.json').read_bytes())!=R1_PIN:raise ValueError('r1 pin mismatch')
 for rel,h in m['files'].items():
  p=root/rel
  if not p.is_file() or sha(p.read_bytes())!=h:raise ValueError('r2 evidence hash mismatch: '+rel)
 for rel,h in m['code_files'].items():
  p=REPO/rel
  if not p.is_file() or sha(p.read_bytes())!=h:raise ValueError('r2 code hash mismatch: '+rel)
 return m

def research_lookup(offering_id,category_code=None,root=OUT):
 verify(root)
 rows=[x for x in readlines(root/'benefit-records.jsonl.gz') if x['offering_id']==offering_id and (category_code is None or x['category_code']==category_code)]
 plans=json.loads((root/'offering-reconciliation.json').read_text());plan=next((p for p in plans if p['offering_id']==offering_id),None)
 if plan is None:raise ValueError('Unknown exact offering identity')
 return {'scope':'2026 published source research; partial, unaccepted','offering':plan,'benefit_records':rows,'personal_applicability':'not_assessed','consumer_usable':False,'comprehensive':False}

def published_lookup(*args,**kwargs):raise PermissionError('L03 r2 is partial research and has no accepted published field release')
