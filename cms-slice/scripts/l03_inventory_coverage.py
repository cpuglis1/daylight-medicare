"""Bind future reconciliation progress to the frozen r9 semantic denominator.

Coverage is not factual verification or release acceptance. Evidence readiness
cannot be inferred from an amount hit, a source count or inherited r4 approval.
"""
from __future__ import annotations
import collections,hashlib,json

STATES={'pending','conflicting','evidence_missing','awaiting_review','fully_supported'}


def inventory_digest(records):
    digest=hashlib.sha256();digest.update(b'[')
    for index,record in enumerate(sorted(records,key=lambda r:r['id'])):
        if index:digest.update(b',')
        digest.update(json.dumps(record,sort_keys=True,separators=(',',':')).encode())
    digest.update(b']')
    return digest.hexdigest()



def progress(records,dispositions,*,expected_digest):
    """Reject denominator drift and invalid coverage; missing records stay open.

    All complete evidence/interpretation/reference decisions remain separately
    reviewable records. A ledger status alone does not approve source meaning.
    """
    if inventory_digest(records)!=expected_digest:raise ValueError('Frozen inventory changed; use an exact recorded revision')
    required={r['id']:r for r in records}
    if len(required)!=len(records):raise ValueError('Duplicate inventory identity')
    supplied={}
    for d in dispositions:
        key=d['inventory_id']
        if key not in required:raise ValueError('Disposition outside exact frozen scope')
        if key in supplied:raise ValueError('Duplicate disposition for required predicate')
        row=required[key]
        if d.get('offering_id')!=row['offering_id']or d.get('kind')!=row['kind']:
            raise ValueError('Offering/kind mismatch')
        state=d.get('state')
        if state not in STATES:raise ValueError('Unknown or waived inventory state')
        if d.get('accepted_for_reference')is not False:raise ValueError('Coverage ledger cannot inherit or grant acceptance')
        if state in {'awaiting_review','fully_supported'}:
            if d.get('evidence_complete')is not True or d.get('structured_outcome')not in {'exact_agreement','agreement_through_reviewed_mapping','different_basis','supported_carrier_statement','documented_inapplicability'}:
                raise ValueError('Evidence/comparison work must actually be complete')
            if not d.get('comparison_record_id')or not d.get('source_interpretation_record_id'):
                raise ValueError('Exact structured comparison and interpretation evidence required')
        if state=='fully_supported'and (d.get('interpretation_review_complete')is not True or not d.get('interpretation_review_receipt')):
            raise ValueError('Independent interpretation review remains required')
        supplied[key]=d
    counts={kind:collections.Counter()for kind in ['claim','condition']}
    for key,r in required.items():counts[r['kind']][supplied.get(key,{}).get('state','pending')]+=1
    return {'required':{kind:sum(c.values())for kind,c in counts.items()},'states':{kind:dict(c)for kind,c in counts.items()},
            'all_evidence_work_complete':all(supplied.get(k,{}).get('state')in {'awaiting_review','fully_supported'}for k in required),
            'accepted_for_reference':False}
