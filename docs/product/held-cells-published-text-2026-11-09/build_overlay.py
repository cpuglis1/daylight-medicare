"""Build the DQ-31 held-cell overlay: CMS published text for r13 held benefit cells.

Inputs (all already in the repository):
  - r13 display candidate (base catalog, sha-pinned)
  - CMS Plan Finder benefit summary, file dated Dec 23, 2025 (MPF)
  - CMS CY2026 Landscape 202609 (for premium and Part D deductible cells)
Output: a candidate overlay. Nothing here is loaded by the app.
"""
import csv, hashlib, html, io, json, re, sys, zipfile, collections
from pathlib import Path

REPO = Path(sys.argv[1]); OUT = Path(sys.argv[2])
R13 = REPO / 'docs/product/recommendation-scope-2026-11-04-r13/display-candidate.json'
MPF_XLSX = REPO / 'docs/data/mpf-benefit-summary-2026-11-04-r1/source/MPF_BenefitSummary_CY2026_12232025.xlsx'
LAND_ZIP = REPO / 'docs/data/l02-ma-availability-2026-10-25/acquisition-r1/raw/75f2797b510449fc0d376bbbbeb3c129f6091a697555281559ca28e6e4b8d882'
LAND_MEMBER = 'CY2026_Landscape_202609/CY2026_Landscape_202609.csv'
CONFLICT_CODES = {'MPF_PBP_CHARGE_DIFFERENCE', 'CARRIER_CMS_COST_SHARE_CONFLICT',
                  'RETAINED_SOURCE_CONFLICT', 'PREMIUM_BASIS_CONFLICT'}
MPF_FIELDS = {
    'medical_deductible': ('Health plan deductible', None, False),
    'medical_maximums': ('Maximum out-of-pocket enrollee responsibility (does not include prescription drugs)', None, False),
    'primary_care_in_network': ('Doctor visits', 'Primary', True),
    'specialist_in_network': ('Doctor visits', 'Specialist', True),
    'hospital_in_network': ('Inpatient hospital coverage', None, True),
    'emergency': ('Emergency care/urgent care', 'Emergency', False),
    'urgent': ('Emergency care/urgent care', 'Urgent care', False),
}
LABEL_MPF = 'As shown on Medicare.gov (CMS Plan Finder benefit summary, file dated Dec 23, 2025)'
LABEL_LAND = 'As published by CMS (CY2026 Landscape, September 2026)'

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def clean(v):
    s = re.sub(r'(?i)<br\s*/?>', '; ', str(v))
    s = html.unescape(re.sub(r'<[^>]+>', ' ', s))
    s = re.sub(r'\s*;\s*(;\s*)*', '; ', s).strip(' ;')
    return re.sub(r'\s+', ' ', s).strip()

def load_mpf(keys):
    import openpyxl
    ws = openpyxl.load_workbook(MPF_XLSX, read_only=True).worksheets[0]
    it = ws.iter_rows(values_only=True); hdr = next(it); rows = collections.defaultdict(list)
    for i, row in enumerate(it, start=2):
        rec = dict(zip(hdr, row))
        try:
            key = (str(rec['Contract_ID']).strip(), str(int(rec['Plan_ID'])).zfill(3), str(int(rec['Segment_ID'])).zfill(3))
        except (TypeError, ValueError):
            continue
        if key in keys:
            rec['_row'] = i; rows[key].append(rec)
    return rows

def load_landscape(keys):
    raw = zipfile.ZipFile(LAND_ZIP).read(LAND_MEMBER)
    out = {}
    for r in csv.DictReader(io.StringIO(raw.decode('latin-1'))):
        r = {k.lstrip('﻿').lstrip('ï»¿'): v for k, v in r.items()}
        if r['County Name'].strip() == 'Collier' and r['State Territory Abbreviation'] == 'FL':
            key = (r['Contract ID'], r['Plan ID'].zfill(3), r['Segment ID'].zfill(3))
            if key in keys: out[key] = r
    return out, hashlib.sha256(raw).hexdigest()

r13_bytes = R13.read_bytes(); r13 = json.loads(r13_bytes)
plans = [p['display_candidate'] for p in r13['plans']]
keys = {tuple(p['offering_id'].split(':')[1:]) for p in plans}
mpf = load_mpf(keys); land, land_member_sha = load_landscape(keys)
cells = []; counts = collections.Counter()
for p in plans:
    key = tuple(p['offering_id'].split(':')[1:])
    conflict_plan = any(CONFLICT_CODES & set(b['reason_codes']) for b in p['benefits'].values())
    for field, b in p['benefits'].items():
        if b['state'] != 'held':
            continue
        cell = {'offering_id': p['offering_id'], 'plan_name': p['name'], 'field': field,
                'r13_state': 'held', 'r13_reason_codes': b['reason_codes']}
        if field in MPF_FIELDS:
            cat, svc, in_network_only = MPF_FIELDS[field]
            rows = [r for r in mpf[key] if r['Category Name'] == cat and (svc is None or r['Service_Desc'] == svc)
                    and (not in_network_only or r['Network_Description'] in (None, 'In-Network'))]
            texts = [{'network': r['Network_Description'], 'text': clean(r['Cost_Share']),
                      'source_text': None if r['Cost_Share'] is None else str(r['Cost_Share']),
                      'prior_authorization': r['Authorization_Flag'], 'referral': r['Referral_Flag'],
                      'limits_apply': r['Limit_Flag'], 'source_ref': f"mpf_rows/{r['_row']}"} for r in rows]
            label = LABEL_MPF
        else:
            lr = land[key]
            if field == 'plan_premium':
                texts = [{'network': None, 'text': f"Part C {lr['Part C Premium'].strip()}; Part D {lr['Part D Total Premium'].strip()}; consolidated {lr['Monthly Consolidated Premium (Part C + D)'].strip()}",
                          'source_ref': f"landscape/{'-'.join(key)}/premium columns"}]
            elif field == 'part_d_deductible':
                no_ded = lr['Offers Drug Tier with No Part D Deductible'].strip()
                texts = [{'network': None, 'text': lr['Annual Part D Deductible Amount'].strip() + ('; some drug tiers have no deductible' if no_ded.lower().startswith('y') else ''),
                          'source_text': {'Annual Part D Deductible Amount': lr['Annual Part D Deductible Amount'], 'Offers Drug Tier with No Part D Deductible': lr['Offers Drug Tier with No Part D Deductible']},
                          'source_ref': f"landscape/{'-'.join(key)}/Annual Part D Deductible Amount"}]
            else:
                raise SystemExit(f'unmapped field {field}')
            label = LABEL_LAND
        if not texts or not all(t['text'] for t in texts):
            raise SystemExit(f'NO SOURCE TEXT {key} {field}')
        if conflict_plan:
            cell.update(proposed_state='remains_held', proposed_reason='SOURCES_DIFFER_LICENSED_CONFIRMATION_REQUIRED (DQ-32)')
        else:
            cell.update(proposed_state='published_text_candidate', display_label=label)
        cell['published_text'] = texts
        counts[cell['proposed_state']] += 1
        cells.append(cell)

overlay = {
    'schema': 'held-cells-published-text/1',
    'created': '2026-11-09',
    'status': 'candidate_not_loaded',
    'decision_required': 'Owner decision (DQ-31). D92 keeps all r13 material holds; this overlay changes nothing until a new catalog revision adopts it and the publication gate accepts it.',
    'base_catalog': {'path': str(R13.relative_to(REPO)), 'sha256': hashlib.sha256(r13_bytes).hexdigest()},
    'sources': {
        'mpf_benefit_summary': {'path': str(MPF_XLSX.relative_to(REPO)), 'sha256': sha(MPF_XLSX), 'file_date': '2025-12-23'},
        'landscape': {'path': str(LAND_ZIP.relative_to(REPO)), 'sha256': sha(LAND_ZIP), 'member': LAND_MEMBER, 'member_sha256': land_member_sha},
    },
    'rule': 'Each r13 held cell shows the CMS published text verbatim (markup removed), labeled with its source and date. Cells on plans whose sources conflict stay held (DQ-32). Computed cost examples are untouched and stay held.',
    'counts': {'r13_held_cells': len(cells), **counts},
    'cells': cells,
}
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(overlay, indent=1, ensure_ascii=False) + '\n')
print(json.dumps(overlay['counts']), 'conflict plans:', sorted({c['offering_id'] for c in cells if c['proposed_state'] == 'remains_held'}))
