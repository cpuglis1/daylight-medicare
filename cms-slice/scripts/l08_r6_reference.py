"""Source-qualified Original Medicare lookup, separate from MA network participation."""
import argparse
import json
import sqlite3
from datetime import date

from l08_r6_common import BASE, REFERENCE_DATE


def assignment_state(value):
    return {'Y': 'published_accepts_assignment', 'M': 'published_may_accept_assignment',
            '': 'unknown_not_published'}.get(value, 'unknown_unrecognized_source_code')


def enrollment_state(code):
    prefix = code.split('-')[0]
    if prefix == '33':
        return 'published_ordering_referring_only_enrollment'
    if prefix in {'00', '12', '14', '30', '53'}:
        return 'published_approved_billing_enrollment_in_extract'
    return 'published_enrollment_unclassified_type'


def optout_state(start, end, reference_date=REFERENCE_DATE):
    """Keep dates literal; boundary cases and malformed intervals require interpretation."""
    try:
        a, b, d = date.fromisoformat(start), date.fromisoformat(end), date.fromisoformat(reference_date)
    except (ValueError, TypeError):
        return 'unknown_invalid_or_missing_source_date'
    if a > b:
        return 'held_reversed_source_interval'
    if d == a or d == b:
        return 'source_interval_boundary_review'
    if a < d < b:
        return 'published_optout_interval_contains_reference_date'
    return 'published_interval_does_not_contain_reference_date'


def lookup(connection, npi):
    if len(npi) != 10 or not npi.isdigit():
        raise ValueError('NPI must be a literal 10-digit identifier')
    connection.row_factory = sqlite3.Row
    observations = [dict(x) for x in connection.execute(
        'SELECT * FROM observations WHERE npi=? ORDER BY source_id,source_row', (npi,))]
    ids = {x['enrollment_id'] for x in observations if x['enrollment_id']}
    related = []
    for eid in sorted(ids):
        related.extend(dict(x) for x in connection.execute(
            "SELECT * FROM observations WHERE enrollment_id=? AND source_id IN "
            "('enrollment','practice_locations','secondary_specialty','additional_npis') ORDER BY source_id,source_row", (eid,)))
    for x in observations + related:
        x['fields'] = json.loads(x.pop('fields_json'))
        f = x['fields']
        if x['source_id'] == 'clinicians':
            x['clinician_assignment_state'] = assignment_state(f['ind_assgn'])
            x['group_assignment_state'] = assignment_state(f['grp_assgn'])
        if x['source_id'] == 'enrollment':
            x['enrollment_state'] = enrollment_state(f['PROVIDER_TYPE_CD'])
        if x['source_id'] == 'optout':
            x['interval_state'] = optout_state(f['Optout Effective Date'], f['Optout End Date'])
    # Source reassignments are billing relationships, not individual-site or MA
    # network membership. Keep their endpoints separately labeled in the lookup.
    edges=[]
    if connection.execute("SELECT count(*) FROM sqlite_master WHERE name='reassignments'").fetchone()[0]:
        seen=set()
        for eid in sorted(ids):
            for row,a,b in connection.execute('SELECT source_row,reassigning_id,receiving_id FROM reassignments '
                                              'WHERE reassigning_id=? OR receiving_id=?',(eid,eid)):
                if row not in seen:
                    seen.add(row)
                    edges.append({'source_row':row,'reassigning_id':a,'receiving_id':b,
                                  'meaning':'published_billing_reassignment_not_site_or_MA_network_membership'})
    overlap = any(x['source_id']=='clinicians' for x in observations) and any(
        x['source_id']=='optout' and x.get('interval_state')=='published_optout_interval_contains_reference_date'
        for x in observations)
    clinical_ids={x['enrollment_id']for x in observations if x['source_id']=='clinicians'}
    enrolled_ids={x['enrollment_id']for x in observations+related if x['source_id']=='enrollment'}
    return {'npi': npi, 'direct_source_observations': observations,
            'related_enrollment_observations': related,
            'published_billing_reassignments':edges,
            'participation_resolution':'held_assignment_optout_source_overlap' if overlap else 'published_reference_only_personal_participation_unverified',
            'unmatched_clinician_enrollment_ids':sorted(clinical_ids-enrolled_ids),
            'county_membership_verified':False,
            'no_match_means': 'unknown_in_this_source_and_geographic_selection',
            'no_personal_coverage_or_appointment_guarantee': True,
            'MA_network_participation_established': False}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--npi', required=True)
    a = p.parse_args()
    db = sqlite3.connect('file:' + str(BASE / 'original-medicare.sqlite3') + '?mode=ro', uri=True)
    print(json.dumps(lookup(db, a.npi), indent=2, ensure_ascii=False))
