"""Expose actual cross-source differences without turning them into eligibility decisions."""
import json
import sqlite3

from l08_r6_common import BASE, assert_open, write


def main():
    assert_open()
    db=sqlite3.connect('file:'+str(BASE/'original-medicare.sqlite3')+'?mode=ro',uri=True)
    db.row_factory=sqlite3.Row
    unmatched=[dict(r) for r in db.execute('''SELECT a.enrollment_id,a.npi,count(*) AS listing_rows
          FROM assignments a WHERE NOT EXISTS(SELECT 1 FROM enrollment_status e WHERE e.enrollment_id=a.enrollment_id)
          GROUP BY a.enrollment_id,a.npi ORDER BY a.enrollment_id,a.npi''')]
    overlaps=[]
    for row in db.execute('''SELECT DISTINCT a.npi,p.source_row,p.start_raw,p.end_raw
        FROM assignments a JOIN optout_periods p ON a.npi=p.npi
        WHERE p.state='published_optout_interval_contains_reference_date' ORDER BY a.npi,p.source_row'''):
        r=dict(row)
        r['clinician_assignment_observations']=[dict(x) for x in db.execute(
            'SELECT source_row,enrollment_id,individual_raw,group_raw FROM assignments WHERE npi=?',(r['npi'],))]
        r['enrollment_observations']=[dict(x) for x in db.execute(
            'SELECT source_row,enrollment_id,provider_type_raw,state FROM enrollment_status WHERE npi=?',(r['npi'],))]
        r['disposition']='retain_both_sources; current_Original_Medicare_participation_unresolved; no_positive_personal_claim'
        overlaps.append(r)
    write(BASE/'unmatched-clinician-enrollments.json',{
        'unique_enrollment_ids':len({r['enrollment_id'] for r in unmatched}),
        'listing_rows':sum(r['listing_rows'] for r in unmatched),'records':unmatched,
        'meaning':'The clinician archive and September 29 enrollment extract have different populations/timing. Missing ID is not evidence of ineligibility, termination or extraction loss. All national enrollment source rows were searched, with all relevant main/additional-NPI links retained.',
        'closure_for_positive_current_enrollment_claim':'Exact newer dated enrollment evidence or source clarification; preserve unknown while unavailable.'})
    write(BASE/'assignment-optout-overlaps.json',{'unique_NPIs':len({r['npi'] for r in overlaps}),
        'records':overlaps,'meaning':'Same NPI appears in the published clinician/assignment archive and in a published opt-out interval spanning the reference date. Claims lookback/publication timing and source definitions differ. No source is silently overwritten; no automated positive participation determination is made.'})
    summary={
        'Florida_clinician_listing_rows':db.execute("SELECT count(*) FROM observations WHERE source_id='clinicians'").fetchone()[0],
        'Florida_distinct_clinician_NPIs':db.execute("SELECT count(DISTINCT npi) FROM observations WHERE source_id='clinicians'").fetchone()[0],
        'Florida_addressed_optout_rows':db.execute("SELECT count(*) FROM observations WHERE source_id='optout' AND state_raw='FL'").fetchone()[0],
        'unmatched_clinician_enrollment_ids':len({r['enrollment_id'] for r in unmatched}),
        'unmatched_clinician_listing_rows':sum(r['listing_rows'] for r in unmatched),
        'assignment_optout_overlapping_NPIs':len({r['npi'] for r in overlaps}),
        'orphan_reassignment_edges':db.execute("SELECT count(*) FROM reassignments r WHERE NOT EXISTS(SELECT 1 FROM enrollment_status e WHERE e.enrollment_id=r.reassigning_id) OR NOT EXISTS(SELECT 1 FROM enrollment_status e WHERE e.enrollment_id=r.receiving_id)").fetchone()[0],
        'assignment_raw_counts':[dict(r) for r in db.execute('SELECT individual_raw,group_raw,count(*) AS rows FROM assignments GROUP BY 1,2')],
        'optout_period_states':[dict(r) for r in db.execute('SELECT state,count(*) AS rows FROM optout_periods GROUP BY 1')],
        'billing_enrollment_states':[dict(r) for r in db.execute('SELECT state,count(*) AS rows FROM enrollment_status GROUP BY 1')],
        'city_search_examples':[dict(r) for r in db.execute("SELECT upper(city_raw) AS city,count(*) AS listing_rows FROM observations WHERE source_id='clinicians' AND upper(city_raw) IN ('NAPLES','MARCO ISLAND','IMMOKALEE','AVE MARIA','FORT MYERS','BONITA SPRINGS','ESTERO') GROUP BY 1 ORDER BY 2 DESC")],
        'city_search_examples_are_not_county_membership_proof':True,
        'all_distinct_provider_counts_are_source_and_selection_scoped':True}
    write(BASE/'case-summary.json',summary)
    print(json.dumps({k:v for k,v in summary.items() if not isinstance(v,list)}),flush=True)


if __name__=='__main__':
    main()
