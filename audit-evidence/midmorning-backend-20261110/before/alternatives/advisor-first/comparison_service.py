"""Private comparison view over the existing advisor records.

No store, model call, public catalog, or acceptance promotion lives here. The
conversation owns input validation/ownership and remains the question router.
"""
from __future__ import annotations

import copy
import logging

from comparison_profile import build_comparison_profile
from comparison_engine import build_comparison
from comparison_evidence import PURPOSES, canonical_sha256
from comparison_case import prepare_case


LOGGER = logging.getLogger(__name__)
SERVICE_VERSION = 'advisor-comparison-service-20261101-r2'
PUBLIC_HOLD_CODES = frozenset({
    'EXACT_RELEASE_REQUIRED', 'POLICY_NOT_ACCEPTED', 'SOURCE_MISSING',
    'ITEM_IDENTITY_UNRESOLVED', 'CONDITION_UNRESOLVED', 'BASELINE_INCOMPLETE',
    'DEPENDENCY_STALE', 'COMPARISON_UNAVAILABLE',
})


def _held_authority(reason):
    return {purpose: {'state': 'held', 'authority_refs': [],
                      'accepted_release_id': None, 'reason_codes': [reason]}
            for purpose in PURPOSES}


class ComparisonService:
    def __init__(self, *, evidence_source=None):
        # This is a server dependency, never a field supplied by an HTTP client.
        self.evidence_source = evidence_source

    def evaluate(self, guide, record, *, next_question=None, generated_at=None,
                 requested_scope=None):
        profile = build_comparison_profile(guide, record, requested_scope=requested_scope)
        result = build_comparison(
            profile, evidence_source=self.evidence_source,
            generated_at=generated_at,
            eligible_questions=[copy.deepcopy(next_question)] if next_question else [],
        )
        result['service_version'] = SERVICE_VERSION
        result['case_preparation'] = prepare_case(profile, result)
        result['binding']['case_method_version'] = result['case_preparation']['method_version']
        digest = canonical_sha256({'structural_comparison': result['comparison_id'],
            'binding': result['binding'], 'case_preparation': result['case_preparation'],
            'service_version': SERVICE_VERSION})
        result['comparison_id'] = 'comparison:' + digest
        result['decision_record_ref'] = 'decision:' + digest
        result['decision_record']['case_preparation_sha256'] = canonical_sha256(result['case_preparation'])
        return result

    def attach(self, response, *, historical=False, replay=False):
        """Rebind after capture/composition and on replay, without model work."""
        assessment = response['assessment']
        previous = response.get('comparison') or {}
        try:
            comparison = self.evaluate(
                response['guide'], response['record'],
                next_question=assessment.get('nextQuestion'),
                generated_at=previous.get('generated_at'),
            )
        except (ValueError, TypeError, KeyError, RuntimeError, OSError):
            # A failed optional derived view cannot discard an accepted report.
            # Logs contain a fixed diagnostic only, never the exception payload.
            LOGGER.warning('Daylight comparison unavailable code=COMPARISON_UNAVAILABLE')
            comparison = {
                'service_version': SERVICE_VERSION,
                'status': 'unavailable',
                'accepted_release_id': None,
                'binding': {'accepted_release_id': None},
                'authority': _held_authority('COMPARISON_UNAVAILABLE'),
                'findings': [], 'tradeoffs': [], 'next_question': None,
                'work_items': [{'type': 'comparison_service_review',
                                'status': 'proposed_not_started',
                                'reason_codes': ['COMPARISON_UNAVAILABLE']}],
            }
        changed_on_replay = bool(replay and previous and previous != comparison)
        if historical or changed_on_replay:
            # An old turn remains a capture receipt; its derived conclusions
            # cannot be presented as a current comparison after a later turn.
            comparison = copy.deepcopy(comparison)
            comparison['status'] = 'stale_binding'
            comparison['findings'] = []
            comparison['tradeoffs'] = []
            comparison['next_question'] = None
            comparison['authority'] = _held_authority('DEPENDENCY_STALE')
            comparison['superseded_comparison_ref'] = previous.get('comparison_id')
            comparison['comparison_id'] = None
            comparison['decision_record_ref'] = None
            trace = comparison.setdefault('decision_record', {})
            trace['selection'] = None
            trace['finding_dependencies'] = {}
            comparison['case_preparation'] = {
                'state': 'stale', 'baseline_reports': [], 'assessments': [],
                'declared_constraints': [], 'declared_scenarios': [],
                'personal_output_state': 'held', 'reason_codes': ['DEPENDENCY_STALE']}
            comparison['research'] = {'state': 'stale', 'retained_identity_count': None,
                                      'consumer_evaluated_count': 0}
            trace.pop('case_preparation_sha256', None)
            comparison.setdefault('validity', {}).update(
                state='stale_profile' if historical else 'stale_evidence_or_method',
                reason_codes=['DEPENDENCY_STALE'])
        if historical or changed_on_replay:
            response['reply'] = ''
            assessment['nextQuestion'] = None
            assessment['intakePaused'] = True
            assessment['conversationOpen'] = True
            response.pop('advisor', None)
            response['facts'] = []
            response['notice'] = 'Your information is preserved. This comparison needs a fresh check.'
            response['generated'] = {'status': 'unavailable', 'retryable': False,
                                     'code': 'comparison_stale'}
        response['comparison'] = comparison
        return response

    @staticmethod
    def context_status(comparison):
        """Public capability markers only; no extra profile values or trace.

        The full owner-bound response is for the service/browser. Existing
        natural-context permissions still determine every personal model value.
        """
        codes = set()
        for item in comparison.get('work_items', []):
            codes.update(code for code in item.get('reason_codes', [])
                         if code in PUBLIC_HOLD_CODES)
        return {
            'version': SERVICE_VERSION,
            'state': 'held',
            'personal_findings_available': False,
            'research_completed': False,
            'reason_codes': sorted(codes or {'EXACT_RELEASE_REQUIRED'}),
        }
