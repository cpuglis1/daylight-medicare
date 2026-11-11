"""Owner-bound Plans application service over the existing profile handoff."""
import copy
import json
from pathlib import Path
import time

from comparison_evidence import canonical_sha256
from guest_profiles import ProfileError
from plans_authority import PlansAuthority
from plans_publication import PlansPublication, publication_permits
from plans_adapters import catalog_metrics, prepare_checks, VerificationFindings
from plans_catalog import PlansCatalog, SHA256
from plans_ranking import METRICS, recommend, reference_ordering

VERSION = 'plans-workspace-20261105-r2'


class PlansService:
    def __init__(self, conversation, *, catalog=None, authority=None, publication=None,
                 local_review=False, findings=None):
        self.conversation = conversation
        self.catalog = catalog or PlansCatalog()
        self.authority = authority or PlansAuthority()
        self.publication = publication or PlansPublication()
        self.local_review = local_review
        self.findings = findings or VerificationFindings()
        self.preferences = {}

    def forget_owner(self, owner):
        for key in [key for key in self.preferences if key[0] == owner]:
            self.preferences.pop(key, None)

    def decision_evidence_digest(self, profile_digest):
        authority = self.authority.read()
        findings = self.findings.read(profile_digest, authority) if profile_digest else {}
        return canonical_sha256({'authority': authority,
            'findings': [{'offering_id': k[0], 'check': k[1], 'finding': v}
                         for k, v in sorted(findings.items())]})

    def _order(self, owner, handoff):
        self.preferences = {k:v for k,v in self.preferences.items() if v['expires'] > time.time()}
        value = self.preferences.get((owner, handoff['token']), {})
        return tuple(value.get('order', ()))

    @staticmethod
    def derived_order(profile):
        """The priority order the person already stated in conversation (T09, then T10).

        Owner direction, November 8, 2026: a person who answered the cost-balance
        and priorities questions must not be told an explicit priority order is
        still required. The reviewed handoff profile is the only source; the
        Plans page still lets them change it.
        """
        try:
            subject = profile['profile_binding']['subject_id']
            facts = profile['facts']
        except (KeyError, TypeError):
            return ()
        def report(path):
            matches = [f for f in facts if f['ref']['path'] == path and f['ref']['subject_id'] == subject
                       and f['ref']['item_id'] is None]
            if len(matches) != 1:
                return None
            f = matches[0]
            return f['value'] if (f.get('usable_for_bound_subject') is True and f.get('usable_as_report') is True
                                   and f['report_state'] == 'reported' and f['ref']['scope'] == 'current') else None
        premium_first = ('monthly_plan_premium', 'in_network_medical_limit')
        limit_first = ('in_network_medical_limit', 'monthly_plan_premium')
        cost = report('guide.fields.needs.costPreference')
        if cost == 'lower_monthly':
            return premium_first
        if cost == 'predictable':
            return limit_first
        priorities = report('guide.fields.needs.priorities')
        priorities = priorities if isinstance(priorities, list) else [priorities] if isinstance(priorities, str) else []
        if 'bills' in priorities:
            return limit_first
        if 'total_cost' in priorities:
            return premium_first
        return ()

    def confirm_priorities(self, owner, token, order, confirmed):
        if (confirmed is not True or not isinstance(order, list) or not 1 <= len(order) <= 2
                or any(not isinstance(k, str) or k not in METRICS for k in order)
                or len(set(order)) != len(order)):
            raise ProfileError('Confirm a supported priority order.', 422)
        with self.conversation.lock:
            handoff = self.conversation.resolve_plans_handoff(owner, token)
            if len(self.preferences) >= 128:
                self.preferences.pop(next(iter(self.preferences)))
            self.preferences[(owner, token)] = {'order': list(order), 'expires': handoff['expiresAt']}
            return self.workspace(owner, token)

    def projection(self):
        catalog = self.catalog.read()
        authority = self.authority.read()
        publication = self.publication.read(local_review=self.local_review)
        plans = []
        for row in catalog['plans']:
            candidate = row['display_candidate']
            identifier = candidate['offering_id']
            cells = {}
            for key, original in candidate['benefits'].items():
                payload = {'offering_id': identifier, 'field': key, 'cell': original}
                accepted = original['state'] != 'held' and publication_permits(publication, 'published_display', payload)
                state = ('not_applicable' if original['state'] == 'not_applicable' else
                         'published' if publication['consumer_approved'] else 'reference') if accepted else 'held'
                cells[key] = {'label': catalog['fields'][key],
                    'state': state,
                    'value': original['value'] if accepted else None,
                    'conditions': copy.deepcopy(original['conditions']),
                    'reason_codes': list(original['reason_codes']) + (
                        ['PUBLICATION_REVIEW_REQUIRED'] if not accepted and original['state'] != 'held' else []),
                    'publication_state': publication['state'],
                    'source_state': original['state'],
                    'evidence_ref': f'r13:{identifier}:{key}', 'catalog_sha256': SHA256}
            examples = {}
            for key, original in candidate['cost_examples'].items():
                dependencies = catalog['example_display_dependencies'][key]
                accepted = (original['state'] == 'numeric_candidate'
                    and all(cells[field]['state'] in {'published', 'reference', 'not_applicable'} for field in dependencies)
                    and publication_permits(publication, 'fictional_example',
                        {'offering_id': identifier, 'example': key, 'cell': original,
                         'assumptions': catalog['example_assumptions'], 'methods': catalog['example_methods']}))
                examples[key] = {'label': catalog['example_columns'][key],
                    'state': ('fictional_example' if publication['consumer_approved'] else 'fictional_reference') if accepted else 'held',
                    'amount': copy.deepcopy(original['amount']) if accepted else None,
                    'reason_codes': list(original['reason_codes']) + (
                        ['EXAMPLE_PUBLICATION_REQUIRED'] if not accepted and original['state'] == 'numeric_candidate' else []),
                    'dependencies': list(dependencies), 'personal_estimate': False}
            plans.append({'id': identifier, 'name': candidate['name'], 'type': candidate['type'],
                'identity_state': 'retained_listing_not_verified_availability',
                'retained_restrictions': copy.deepcopy(candidate['published_restrictions']),
                'restriction_state': 'dated_reference_not_personal_qualification', 'fields': cells, 'examples': examples})
        view = {'version': VERSION, 'catalog_sha256': SHA256, 'scope': copy.deepcopy(catalog['scope']),
            'release_id': publication.get('release_id'), 'plans': plans,
            'publication': {k: publication[k] for k in ('state', 'release_id', 'consumer_approved')},
            'adapters': {'chat_profile': 'connected', 'typed_catalog_metrics': 'connected',
                         'conditional_checks': 'connected', 'verified_findings': 'connected',
                         'automated_personal_verification': 'unavailable',
                         'personal_finding_source': 'exact_purpose_accepted_server_receipts'},
            'coverage': {'retained_identities': len(plans), 'verified_availability': 0,
                         'prepared_fields': sum(len(p['fields']) for p in plans),
                         'published_fields': sum(c['state'] == 'published' for p in plans for c in p['fields'].values()),
                         'usable_reference_fields': sum(c['state'] in {'published', 'reference'} for p in plans for c in p['fields'].values()),
                         'not_applicable_fields': sum(c['state'] == 'not_applicable' for p in plans for c in p['fields'].values()),
                         'material_held_fields': sum(c['source_state'] == 'held' for p in plans for c in p['fields'].values()),
                         'usable_examples': sum(c['amount'] is not None for p in plans for c in p['examples'].values()),
                         'source_use': publication['state'], 'recommendation_authority': authority['status'],
                         'app_access': 'connected'},
            'example_assumptions': copy.deepcopy(catalog['example_assumptions']),
            'notice': ('Local review of 72 retained 2026 Collier listings. Supported source facts and fictional examples are available; independent consumer publication review is pending. '
                       if publication['state'] == 'local_review' else '72 retained 2026 Collier listings. ')
                       + 'Availability and personal fit require separate checks. Each unresolved amount stays held.'}
        teaching = json.loads((Path(__file__).resolve().parent/'web/teaching-facts.json').read_text())
        view['definitions'] = {f['id']: {'title': f['title'], 'text': f['text']}
                               for f in teaching['facts'] if f['id'] in {'costs', 'medical_limit'}}
        # This changes on revocation/expiry as well as accepted release changes.
        view['projection_digest'] = canonical_sha256(view)
        return view, authority

    def workspace(self, owner, token=None):
        with self.conversation.lock:
            handoff = self.conversation.resolve_plans_handoff(owner, token) if token else None
            return self.for_handoff(owner, handoff)

    def detail(self, identifier):
        view, _ = self.projection()
        plan = next((p for p in view['plans'] if p['id'] == identifier), None)
        if not plan:
            raise ProfileError('Use a retained plan identity.', 422)
        row = next(p for p in self.catalog.read()['plans'] if p['display_candidate']['offering_id'] == identifier)
        return {'plan': plan, 'scope': view['scope'], 'catalog_sha256': view['catalog_sha256'],
                'projection_digest': view['projection_digest'],
                'metrics': catalog_metrics(self.catalog.typed(), [plan])[identifier],
                'lineage': copy.deepcopy(row['review_evidence']),
                'example_assumptions': view['example_assumptions']}

    def for_handoff(self, owner, handoff):
        view, authority = self.projection()
        if handoff:
            scope = handoff['scope']
            county = scope.get('county') or {}
            supported = scope.get('year') == 2026 and (county.get('fips') or county.get('county_fips')) == '12021'
            order = self._order(owner, handoff)
            priority_source = 'confirmed' if order else 'none'
            if not order:
                order = self.derived_order(handoff['profile'])
                priority_source = 'derived_from_conversation' if order else 'none'
            metrics = catalog_metrics(self.catalog.typed(), view['plans'])
            findings = self.findings.read(handoff['inputDigest'], authority)
            checks = prepare_checks(handoff['profile'], view['plans'], findings)
            decision = recommend(handoff['inputDigest'], order, view['plans'], authority,
                metrics=metrics, checks=checks, scope_supported=supported)
            view.update(profile_binding={'input_digest': handoff['inputDigest'], 'expires_at': handoff['expiresAt'],
                'reported_info_reviewed': True, 'scope': copy.deepcopy(scope)},
                profile_holds=copy.deepcopy(handoff['holds']), recommendation=decision,
                reference_comparison=reference_ordering(order, view['plans'], metrics, scope_supported=supported),
                metric_coverage={key: sum(row[key]['state'] == 'available' for row in metrics.values()) for key in METRICS})
            view['recommendation']['scope_supported'] = supported
            view['recommendation']['priority_source'] = priority_source
            view['reference_comparison']['priority_source'] = priority_source
        else:
            view.update(profile_binding=None, profile_holds=[], recommendation={'state': 'held',
                'top_three': [], 'tie_groups': [], 'priority_order': [], 'plans': [],
                'reason_codes': ['CONFIRM_CURRENT_PROFILE'], 'scope_supported': False})
            view['reference_comparison'] = {'state': 'held', 'ordered_ids': [], 'first_three': [],
                'reason_codes': ['CONFIRM_CURRENT_PROFILE'], 'personal_recommendation': False}
        # Clients echo a view binding, never their own facts or decision result.
        view['decision_evidence_digest'] = self.decision_evidence_digest(handoff['inputDigest'] if handoff else None)
        view['view_digest'] = canonical_sha256(view)
        return view
