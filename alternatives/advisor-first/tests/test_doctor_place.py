"""Search and conversation candidate contracts using a fictional directory."""
from collections import defaultdict
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch
from pathlib import Path
import sys

ROOT_SRC = Path(__file__).resolve().parents[3] / 'infrastructure' / 'daylight-data' / 'src'
if str(ROOT_SRC) not in sys.path:
    sys.path.insert(0, str(ROOT_SRC))  # the local data package (needs psycopg)
import test_natural_flow  # noqa: F401  sets the advisor import paths

from daylight_data.serving.pilot_doctors import DoctorIndex
from conversation_checks import ConversationChecks, original_medicare_evidence


def directory(*locations):
    corpus = SimpleNamespace(actors={}, sites={}, edges=defaultdict(dict), identity_conflicts={})
    for number, city in enumerate(locations):
        key = f'clinician-{number}'
        site = f'office-{number}'
        corpus.actors[key] = {'kind': 'clinician', 'names': {f'Fictional {number} Smith': {}},
                              'npis': [key], 'source': {'dataset': 'fixture'}}
        corpus.sites[site] = {'address': {
            'street': '1 Example Ave', 'city': city, 'state': 'FL',
            'postal': '341021234' if city == 'NAPLES' else '339019311',
            'published_county': None, 'regional_search_hint': True,
        }}
        corpus.edges[key][site] = {'specialties': [], 'organizations': []}
    index = DoctorIndex(corpus)
    return SimpleNamespace(search=lambda *, year, **query: index.search(**query), index=index)


class DoctorPlaceTests(TestCase):
    def question(self, *cities, name='Dr. Smith in Naples'):
        checks = ConversationChecks(None, directory(*cities), None, lambda: [])
        state = {'skipped': {}}
        with patch('socket.socket.connect', side_effect=AssertionError('Network forbidden')):
            question, result = checks.doctor_step(state, 'doctor-1', {'report': {'name': name}})
        self.assertIsNone(result)
        return question

    def test_matching_city_orders_before_other_places_and_page_is_bounded(self):
        question = self.question('FORT MYERS', 'NAPLES', 'NAPLES', 'ESTERO', 'FORT MYERS', 'ESTERO')
        rows = question['candidates']
        self.assertEqual(len(rows), 5)
        self.assertEqual([c['offices'][0]['place_match'] for c in rows], [True, True, False, False, False])
        self.assertIn('__more__', [choice['value'] for choice in question['choices']])
        self.assertEqual(rows[0]['offices'][0], {'line': '1 Example Ave', 'city': 'NAPLES', 'state': 'FL',
                                                'zip5': '34102', 'zip4': '1234', 'place_match': True})

    def test_sole_candidate_in_other_city_is_flagged(self):
        question = self.question('FORT MYERS', name='Dr. Smith in Naples, FL')
        self.assertEqual(question['candidates'], [{
            'candidate_id': 'clinician-0', 'label': 'Fictional 0 Smith',
            'offices': [{'line': '1 Example Ave', 'city': 'FORT MYERS', 'state': 'FL',
                         'zip5': '33901', 'zip4': '9311', 'place_match': False}],
        }])
        self.assertIn('__refine__', [choice['value'] for choice in question['choices']])

    def test_selecting_a_candidate_keeps_its_matching_office_first(self):
        index = directory('FORT MYERS', 'NAPLES').index
        index.corpus.edges['clinician-0']['office-1'] = index.corpus.edges['clinician-1']['office-1']
        result = index.site_page('clinician-0', 0, 'Naples')
        self.assertEqual([site['address']['city'] for site in result['sites']], ['NAPLES', 'FORT MYERS'])

    def test_original_medicare_uses_published_assignment_and_record_date(self):
        evidence = {'state': 'dated_listing', 'assignment': [{
            'individual_state': 'published_may_accept_assignment', 'group_state': 'unknown',
            'published_on': '2026-10-02',
        }]}
        self.assertEqual(original_medicare_evidence(evidence),
                         {'state': 'may_accept', 'record_date': '2026-10-02'})
        evidence['assignment'][0]['group_state'] = 'published_accepts_assignment'
        self.assertEqual(original_medicare_evidence(evidence),
                         {'state': 'accepts', 'record_date': '2026-10-02'})
        evidence['opt_out'] = [{'interval_state': 'published_interval_contains_date',
                               'catalog_modified_on': '2026-10-26'}]
        self.assertEqual(original_medicare_evidence(evidence),
                         {'state': 'unknown', 'record_date': '2026-10-26'})
