"""Private identity preparation attached to a current comparison response.

The HTTP caller owns current-owner/current-conversation authentication. This
adapter assesses report-to-source associations, without promoting source use,
reported consistency, plan coverage, clinical equivalence or personal findings.
It does not attach data to the saved profile or the language-model context.
"""
import copy
from dataclasses import fields

from comparison_evidence import canonical_sha256
from comparison_methods import IdentityBinding, assess_identity_binding
from comparison_profile import build_comparison_profile
from comparison_service import ComparisonService
from identity_journey import IDENTITY_SCOPE

VERSION = 'advisor-identity-comparison-preparation-20261102-r1'


def comparison_for_visit(service, visit_key, trusted_response):
    guide, record = trusted_response['guide'], trusted_response['record']
    comparison = ComparisonService().evaluate(guide, record,
        next_question=trusted_response['assessment'].get('nextQuestion'),
        generated_at=trusted_response.get('comparison', {}).get('generated_at'))
    profile = build_comparison_profile(guide, record, requested_scope=copy.deepcopy(IDENTITY_SCOPE))
    preparation = service.preparation(visit_key, profile)
    if (preparation.get('state') != 'identity_selection_preparation_only'
            or preparation.get('personal_output_state') != 'held'
            or preparation.get('coverage_findings') != []
            or preparation.get('saved') is not False
            or preparation.get('ai_context_changed') is not False):
        raise ValueError('IDENTITY_PREPARATION_BOUNDARY_MISMATCH')
    bindings = []
    required = {field.name for field in fields(IdentityBinding)}
    rows = preparation.get('bindings')
    if (not isinstance(rows, list) or len(rows) > 100
            or type(preparation.get('selected_count')) is not int
            or preparation['selected_count'] != len(rows)):
        raise ValueError('IDENTITY_PREPARATION_BINDING_MISMATCH')
    for row in rows:
        value = row.get('binding')
        if (not isinstance(value, dict) or set(value) != required
                or row.get('source_state') != 'requires_live_recheck'
                or row.get('personal_output_state') != 'held'
                or value.get('scope') != IDENTITY_SCOPE
                or row.get('item_id') != value.get('item_id')
                or row.get('kind') != value.get('kind')):
            raise ValueError('IDENTITY_PREPARATION_BINDING_MISMATCH')
        value = copy.deepcopy(value)
        value['report_refs'] = tuple(value['report_refs'])
        value['evidence_refs'] = tuple(value['evidence_refs'])
        bindings.append(IdentityBinding(**value))
    view = service.view(visit_key, profile)
    assessments = []
    for item in view['items']:
        assessment = assess_identity_binding(profile, bindings, kind=item['kind'],
            item_id=item['item_id'], scope=copy.deepcopy(IDENTITY_SCOPE))
        assessments.append({'item_id': item['item_id'], 'kind': item['kind'],
            'technical_report_association': assessment,
            'source_state': 'requires_live_recheck' if assessment['identity_state'] == 'bound' else 'unresolved',
            'reported_details_consistency': 'requires_separate_reconciliation',
            'coverage_state': 'unresolved', 'personal_output_state': 'held'})
    # A policy/visit change must not leave earlier private bindings in the
    # response. HTTP additionally rechecks the current signed head after this.
    if service.capability()['state'] != 'internal_research_available':
        preparation = service.preparation(visit_key, profile)
        assessments = []
    attached = {'version': VERSION, 'state': 'identity_preparation_only',
        'preparation': copy.deepcopy(preparation), 'assessments': assessments,
        'reported_input_completeness_is_not_external_verification': True,
        'coverage_findings': [], 'personal_output_state': 'held',
        'saved': False, 'ai_context_changed': False}
    comparison['case_preparation']['identity_preparation'] = attached
    comparison['binding']['identity_preparation_version'] = VERSION
    fingerprint = canonical_sha256({'base_comparison_id': comparison['comparison_id'],
        'identity_preparation': attached, 'version': VERSION})
    comparison['comparison_id'] = 'comparison:' + fingerprint
    comparison['decision_record_ref'] = 'decision:' + fingerprint
    comparison['decision_record']['identity_preparation_sha256'] = canonical_sha256(attached)
    comparison['decision_record']['case_preparation_sha256'] = canonical_sha256(comparison['case_preparation'])
    return comparison
