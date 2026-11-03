"""Mechanical source preparation cannot remove obligations or establish meaning."""
import copy
import gzip
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import whole_offering as w


def unit(identifier, kind='claim', *, group='fixture', scope=None, service=None):
    return {'id':identifier,'offering_id':w.OFFERING,'kind':kind,
        'accepted_for_reference':False,'states':['evidence_reconciliation_pending'],
        'subject':group,'predicate':'Fictional assertion only',
        'detail':{'source_basis':'fixture'},
        'context':{'complete_source_proposition_scope':scope,
                   'service_ids':[service] if service else []},
        'representation_ids':['SEM-'+identifier],'observation_ids':['OBS-'+identifier],
        'source_ids':['SRC-'+identifier]}


class FakeNative:
    """Fictional bounded transport; no production connection or source replay."""
    def __init__(self, *, missing=False, corrupt=False, change_snapshot=False, multiple_relation_sources=False):
        self.calls=[];self.missing=missing;self.corrupt=corrupt;self.change_snapshot=change_snapshot
        self.multiple_relation_sources=multiple_relation_sources

    def lookup(self, kind, ids, *, after_ordinal=0):
        self.calls.append((kind,list(ids),after_ordinal))
        raw=[]
        if kind=='native_relationships':
            raw=[{'parent_id':ids[0],'child_id':ids[0],'relation':'fixture:link','source_id':'SRC-fixture'}]
            if self.multiple_relation_sources:raw.append({**raw[0],'source_id':'SRC-second-source'})
        elif kind=='native_observations':
            raw=[{'id':i,'layer':'carrier_clause','payload':json.dumps({'clause_id':'CLAUSE-fixture'})} for i in ids]
        else:
            raw=[{('source_id' if kind=='native_sources' else 'id'):i} for i in ids]
        if self.missing and kind=='native_sources':raw=[]
        records=[{'raw_payload':row,'artifact_sha256':'fixture:source',
            'original_path':str(w.BASE/'semantic-inventory-r9/inventory.sqlite3.gz'),
            'raw_sha256':hashlib.sha256(json.dumps(row,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()}
            for row in raw]
        if self.corrupt and records:records[0]['raw_sha256']='wrong'
        return {'binding':{'snapshot_id':'changed' if self.change_snapshot and len(self.calls)>1 else 'fixture:snapshot',
                           'accepted_release_id':None},'new_acceptance':False,
                'authority':{'fixture:purpose':{'state':'held'}},'records':records,
                'has_more':False,'next_after_ordinal':None,'source_query':'SELECT fixture only',
                'query_parameters':ids}


class WholeOfferingTests(unittest.TestCase):
    def test_census_keeps_full_canonical_records_states_and_missing_ids(self):
        rows=[unit('A'),unit('B','condition')]
        rows[1]['states']=['required_evidence_missing']
        original=copy.deepcopy(rows)
        kept,audit,ids=w.census(iter(rows),expected_digest=w.digest(rows),enforce_counts=False)
        self.assertEqual(kept,original);self.assertEqual(rows,original)
        self.assertEqual(audit['offering_required'],{'claim':1,'condition':1})
        self.assertEqual(audit['missing_ids'],['B'])
        self.assertEqual(ids['representation_ids'],['SEM-A','SEM-B'])
        self.assertFalse(audit['whole_offering_pilot_complete'])
        self.assertEqual(audit['new_accepted'],0);self.assertEqual(audit['new_awaiting_review'],0)

    def test_deletion_reordering_changed_acceptance_and_denominator_fail(self):
        rows=[unit('A'),unit('B','condition')];expected=w.digest(rows)
        for changed in (rows[:1],list(reversed(rows)),[rows[0],rows[0]]):
            with self.assertRaises(w.WholeOfferingError):
                w.census(iter(changed),expected_digest=expected,enforce_counts=False)
        altered=copy.deepcopy(rows);altered[0]['accepted_for_reference']=True
        with self.assertRaises(w.WholeOfferingError):
            w.census(iter(altered),expected_digest=w.digest(altered),enforce_counts=False)
        with self.assertRaises(w.WholeOfferingError):
            w.census(iter(rows),expected_digest=expected,enforce_counts=True)

    def test_inpatient_candidates_preserve_complete_proposition_siblings_without_mapping(self):
        service=w.OFFERING+':benefitDetails:0'
        rows=[unit('A',scope='shared',service=service),unit('B','condition',scope='shared'),
              unit('C',group='Published service family: inpatient'),unit('D',service='other')]
        out=w.inpatient_scope(rows,[{'service_id':service,'category_code':'1a'}])
        self.assertEqual(out['canonical_ids'],['A','B','C'])
        self.assertEqual(out['counts'],{'claim':2,'condition':1})
        self.assertEqual(out['full_meaning_outcome'],'insufficient_evidence')
        self.assertEqual(out['cross_source_equivalence'],'not_established')
        self.assertFalse(out['accepted_for_reference'])

    def test_exclusive_outputs_are_reproducible_and_never_replace_existing_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            one,two=Path(directory)/'one.gz',Path(directory)/'two.gz'
            self.assertEqual(w.write_new(one,{'fixture':None},compressed=True),
                             w.write_new(two,{'fixture':None},compressed=True))
            before=one.read_bytes()
            with self.assertRaises(FileExistsError):w.write_new(one,{'changed':True},compressed=True)
            self.assertEqual(one.read_bytes(),before)
            self.assertEqual(json.loads(gzip.decompress(before)),{'fixture':None})

    def test_native_batches_are_bounded_and_clause_requests_derive_from_observations(self):
        ids={'observation_ids':['OBS-'+str(n) for n in range(205)],
             'source_ids':['SRC-fixture'],'representation_ids':['SEM-fixture']}
        native=FakeNative()
        with tempfile.TemporaryDirectory() as directory:
            result=w.hydrate(Path(directory),Path(directory),ids,'fixture:source',native=native)
            self.assertTrue((Path(directory)/'NATIVE_LOOKUP_RECEIPT.json').exists())
        self.assertTrue(all(1<=len(batch)<=100 for _,batch,_ in native.calls))
        self.assertEqual(result['unique_counts']['native_observations'],205)
        self.assertEqual(result['unique_counts']['native_clauses'],1)
        self.assertEqual(result['clause_ids'],['CLAUSE-fixture'])
        self.assertFalse(result['semantic_verification']);self.assertFalse(result['new_acceptance'])

    def test_missing_ids_raw_corruption_and_snapshot_change_cannot_report_complete_hydration(self):
        ids={'observation_ids':['OBS-fixture'],'source_ids':['SRC-fixture'],
             'representation_ids':['SEM-fixture']}
        for native in (FakeNative(missing=True),FakeNative(corrupt=True),FakeNative(change_snapshot=True)):
            with self.subTest(native=native.__dict__):
                with tempfile.TemporaryDirectory() as directory:
                    with self.assertRaises(w.WholeOfferingError):
                        w.hydrate(Path(directory),Path(directory),ids,'fixture:source',native=native)
                    self.assertFalse((Path(directory)/'NATIVE_LOOKUP_RECEIPT.json').exists())

    def test_relationship_source_identity_is_part_of_native_primary_key(self):
        ids={'observation_ids':['OBS-fixture'],'source_ids':['SRC-fixture'],
             'representation_ids':['SEM-fixture']}
        with tempfile.TemporaryDirectory()as directory:
            result=w.hydrate(Path(directory),Path(directory),ids,'fixture:source',
                             native=FakeNative(multiple_relation_sources=True))
        self.assertEqual(result['unique_counts']['native_relationships'],2)

    def test_exact_native_id_does_not_substitute_for_correct_canonical_source_binding(self):
        rows=[unit('A')]
        ids={key:rows[0][key] for key in ('observation_ids','source_ids','representation_ids')}
        for index,identifier in enumerate(w.REQUIREMENT_SOURCE_IDS):
            missing=unit('MISSING-'+str(index),'condition')
            missing.update(source_ids=[identifier],observation_ids=[])
            missing['states']=['required_evidence_missing'];rows.append(missing)
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(w.WholeOfferingError,'Canonical/native'):
                w.hydrate(Path(directory),Path(directory),ids,'fixture:source',
                          native=FakeNative(),canonical_rows=rows)
            self.assertFalse((Path(directory)/'NATIVE_LOOKUP_RECEIPT.json').exists())

    def test_requirement_extension_rejects_wrong_offering_unknown_or_unfrozen_ids_before_query(self):
        native=FakeNative()
        exact=next(iter(w.REQUIREMENT_SOURCE_IDS))
        cases=[([exact],set(),w.OFFERING),([exact],w.REQUIREMENT_SOURCE_IDS,'2026:H5652:004:000'),
               (['SOURCE_REQUIREMENT-unfrozen'],w.REQUIREMENT_SOURCE_IDS,w.OFFERING),
               (['SRC-other'],w.REQUIREMENT_SOURCE_IDS,w.OFFERING)]
        for requested,allowed,offering in cases:
            with self.assertRaises(w.WholeOfferingError):
                w.requirement_lookup(native,requested,allowed=allowed,offering_id=offering)
        self.assertEqual(native.calls,[])

    @staticmethod
    def comparison_inputs():
        band={'bdDayInterval1CopaymentAmount':'375.00','bdDayInterval1BeginDay':'1',
              'bdDayInterval1EndDay':'7','bdDayInterval2CopaymentAmount':'0.00',
              'bdDayInterval2BeginDay':'8','bdDayInterval2EndDay':'90'}
        acute={'TierCopaymentComponent':{'bdCopaymentTier1DayIntervalStay':band,
            'bdCopaymentAmountYesNo':'1','bdCopaymentTier1YesNo':'2','bdCopaymentTier1Amt':'0.00'},
            'CostShareABPOSComponent':{'bdCoinsAmt':'40'},
            'InpatientHospitalAcuteBenefitPeriodComponent':{'period':'3'},
            'PriorAuthorizationReferralNmBenefitComponent':{'authorization':'1','referral':'2'}}
        extra={'AdditionalDays1a1Component':{'bdTierCopayment':{'bdCopaymentTier1DayIntervalStay':{
            'begin':'91','end':'999','amount':'0.00'}},'bdUnlimitedAdditionalDays':{'bdBenefitUnlimitedYesNo':'1'}}}
        document={'contractYear':2026,'pbp':[{'contractId':'H5652','planId':'002','segmentId':0,
            'benefitDetails':{'benefitDetailsInfo':[{'categoryCode':'1a','benefitDetails':acute},
                                                  {'categoryCode':'1a1','benefitDetails':extra}]}}]}
        source_bands=[{'begin_day':1,'end_day':7,'amount':'375','basis':'per_day','currency':'USD'},
                      {'begin_day':8,'end_day':None,'amount':'0','basis':'per_day','currency':'USD'}]
        producer={'offering_id':w.OFFERING,'observations':[
            {'id':identifier,'typed':{'in_network_bands':copy.deepcopy(source_bands),
                'out_of_network':{'amount':'40','unit':'percent','basis':'per_stay'}}}
            for identifier in ('producer:sb-inpatient-row','producer:eoc-in-network-schedule',
                               'producer:eoc-out-of-network-schedule')]}
        expected_bands=[{'day_start':1,'day_end':7,'amount':'375.00'},
                        {'day_start':8,'day_end':None,'amount':'0.00'}]
        fresh={'offering':{'offering_id':w.OFFERING,'year':2026},'observations':[
            {'id':prefix+'-INPATIENT-'+suffix,'network':network,'structure':{
                'unit':'per day'if suffix=='IN'else'percent','currency':'USD',
                'bands':copy.deepcopy(expected_bands),'amount':'40'}}
            for prefix in ('SB','EOC')for suffix,network in [('IN','in-network'),('OUT','out-of-network')]]}
        return document,producer,fresh

    def test_component_equality_keeps_90_999_unlimited_controls_and_all_meaning_holds(self):
        args=self.comparison_inputs();original=copy.deepcopy(args)
        out=w.inpatient_components(*args)
        self.assertEqual(args,original)
        self.assertEqual(len(out['checks']),6)
        later=out['later_days_control_review']
        self.assertEqual(later['acute_second_band_end_raw'],'90')
        self.assertEqual(later['additional_day_band_raw']['end'],'999')
        self.assertEqual(later['unlimited_additional_days_raw']['bdBenefitUnlimitedYesNo'],'1')
        self.assertIsNone(later['reviewed_CMS_carrier_mapping'])
        self.assertTrue(later['source_codes_not_converted_to_personal_cap_or_infinity'])
        self.assertEqual(out['full_meaning_outcome'],'insufficient_evidence')
        self.assertEqual(out['new_awaiting_review'],0);self.assertEqual(out['new_accepted'],0)

    def test_component_comparison_rejects_wrong_network_units_missing_bands_and_nonfinite(self):
        changes=[lambda d,p,f:f['observations'][0].update(network='out-of-network'),
                 lambda d,p,f:f['observations'][0]['structure'].update(unit='per stay'),
                 lambda d,p,f:p['observations'][0]['typed']['in_network_bands'].pop(),
                 lambda d,p,f:p['observations'][0]['typed']['in_network_bands'][0].update(amount='NaN'),
                 lambda d,p,f:d['pbp'][0]['benefitDetails']['benefitDetailsInfo'].pop(),
                 lambda d,p,f:d.update(contractYear=2027)]
        for change in changes:
            args=self.comparison_inputs();change(*args)
            with self.assertRaises(w.WholeOfferingError):w.inpatient_components(*args)

    def test_disagreeing_component_is_retained_instead_of_forced_into_agreement(self):
        args=self.comparison_inputs()
        args[0]['pbp'][0]['benefitDetails']['benefitDetailsInfo'][0]['benefitDetails'][
            'TierCopaymentComponent']['bdCopaymentTier1DayIntervalStay']['bdDayInterval1CopaymentAmount']='376.00'
        out=w.inpatient_components(*args)
        check=next(row for row in out['checks']if row['check']=='CMS_first_day_band')
        self.assertFalse(check['decimal_amount_equal'])
        self.assertEqual(out['full_meaning_outcome'],'insufficient_evidence')


if __name__=='__main__':unittest.main()
