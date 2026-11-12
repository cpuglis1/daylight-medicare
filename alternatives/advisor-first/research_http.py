"""Local research and owner-bound comparison reads over the existing HTTP guards.

The shared, pinned guide server is unchanged. These routes have no model, save,
release, SQL input or external-action capability.
"""
import copy
import hmac
import re
import threading
import time
from urllib.parse import urlsplit

from guest_profiles import ProfileError
from comparison_research import RESEARCH_SCOPE, RepositoryEvidenceSource, validate_research_scope
from comparison_service import ComparisonService
from comparison_preview import preview_for_snapshot


def install_research_routes(server, repository=None, reference_adapter=None, *, previews=None, catalog=None):
    base = server.RequestHandlerClass
    slots = threading.BoundedSemaphore(2)
    research_comparisons = ComparisonService(
        evidence_source=RepositoryEvidenceSource(repository)) if repository else ComparisonService()

    def owned_snapshot(owner, payload):
        """Read a current resolved turn; inspection cannot navigate or unpause.

        The signed profile and current chain/head are checked against the same
        controller authority as a turn. The trusted most recent turn preserves
        the model's validated pause/target rather than recomputing a route.
        """
        continuation = payload.get('continuation')
        if (not isinstance(continuation, str) or
                not re.fullmatch(r'[a-f0-9]{32}\.[a-f0-9]{64}', continuation) or
                not re.fullmatch(r'[A-Za-z0-9-]{10,80}', str(payload.get('requestId', '')))):
            raise ProfileError('Review comparison from the current conversation.', 409)
        guide, record = server.adaptive.validate(copy.deepcopy(payload['guide']), copy.deepcopy(payload['record']))
        chain = continuation.split('.')[0]
        with server.adaptive.lock:
            if (owner in server.adaptive.natural_active or
                    server.adaptive.current_chain.get(owner) != chain or
                    server.adaptive.state_heads.get((owner, chain)) != continuation or
                    not hmac.compare_digest(continuation, server.adaptive.bind(owner, guide, record, chain))):
                raise ProfileError('Your conversation changed. Review its latest state.', 409)
            for entry_key, entry in reversed(list(server.adaptive.turn_journal.items())):
                entry_owner, _ = entry_key
                if (entry_owner == owner and entry['expires'] > time.time() and
                        entry['response'].get('continuation') == continuation):
                    return copy.deepcopy(entry['response']), (entry_key, entry['signature'])
        raise ProfileError('This comparison needs a current conversation snapshot. Your reports are preserved.', 409)

    class Handler(base):
        def research_guard(self, *, writing=False):
            if not self.safe():
                raise ProfileError('Request origin rejected.', 403)
            if urlsplit(self.path).query:
                raise ProfileError('Use a bounded request body, not URL parameters.')
            server.profiles.require(self.token())
            if writing:
                self.csrf()

        def do_GET(self):
            if urlsplit(self.path).path != '/api/research/status':
                return super().do_GET()
            try:
                self.research_guard()
                return self.respond(200, {
                    'configured': repository is not None,
                    'exact_reference_configured': reference_adapter is not None,
                    'comparison_catalog_configured': catalog is not None,
                    'scope': copy.deepcopy(RESEARCH_SCOPE),
                    'purpose': 'internal_research_review',
                    'consumer_release': False, 'personal_comparison': False,
                    'model_calls': 0,
                })
            except ProfileError as error:
                return self.respond(error.code, {'error': str(error)})

        def do_POST(self):
            path = urlsplit(self.path).path
            if path not in {'/api/research/query', '/api/comparison/review'}:
                return super().do_POST()
            acquired = False
            try:
                self.research_guard(writing=True)
                payload = self.body()
                if not slots.acquire(blocking=False):
                    raise ProfileError('Local research is busy. Try again shortly.', 429)
                acquired = True
                if path == '/api/comparison/review':
                    allowed = {'guide', 'record', 'continuation', 'requestId', 'scope'}
                    if previews is not None:
                        allowed.add('preview_days')
                    if (set(payload) - allowed or
                            not {'guide', 'record', 'requestId', 'continuation'} <= set(payload)):
                        raise ProfileError('Use the current comparison review request.')
                    scope = payload.get('scope')
                    if 'preview_days' in payload and scope is not None:
                        raise ProfileError('The preview has a fixed 2026 Collier County scope.', 422)
                    if scope is not None:
                        validate_research_scope(scope)
                    owner = server.profiles.digest(self.token())
                    out, journal_binding = owned_snapshot(owner, payload)
                    preview = (preview_for_snapshot(previews, payload['preview_days'], out)
                               if 'preview_days' in payload else None)
                    try:
                        comparison_service = research_comparisons if scope is not None else ComparisonService()
                        out['comparison'] = comparison_service.evaluate(
                            out['guide'], out['record'],
                            next_question=out['assessment'].get('nextQuestion'),
                            requested_scope=scope)
                    except Exception:
                        if preview is not None:
                            raise ProfileError('The comparison preview needs a fresh check.', 503)
                        # Optional research failure cannot change the controller
                        # snapshot or expose exception/source/customer values.
                        out['comparison']['research'] = {
                            'state': 'unavailable', 'reason_codes': ['RESEARCH_UNAVAILABLE'],
                            'scope': copy.deepcopy(scope), 'consumer_evaluated_count': 0}
                    if preview is not None:
                        out['comparison']['educational_preview'] = preview
                    continuation = out.get('continuation')
                    if continuation:
                        chain = continuation.split('.')[0]
                        with server.adaptive.lock:
                            latest = next(((entry_key, entry['signature'])
                                for entry_key, entry in reversed(list(server.adaptive.turn_journal.items()))
                                if entry_key[0] == owner and entry['expires'] > time.time()
                                and entry['response'].get('continuation') == continuation), None)
                            if (owner in server.adaptive.natural_active or
                                    server.adaptive.current_chain.get(owner) != chain or
                                    server.adaptive.state_heads.get((owner, chain)) != continuation):
                                raise ProfileError('Your conversation changed. Review its latest state.', 409)
                            if latest != journal_binding:
                                raise ProfileError('Your advisor response changed. Review its latest state.', 409)
                    # Return derived data only. Current saving/guide-presentation
                    # preferences are client-owned and intentionally outside the
                    # controller's signed report binding. A cached turn must
                    # never overwrite those choices or re-enable sensitive saving.
                    return self.respond(200, {'comparison':out['comparison'],
                                              'continuation':continuation})
                operation = payload.get('operation')
                if operation == 'catalog':
                    if (set(payload) - {'operation', 'scope', 'offering_id', 'expected_catalog_sha256'}
                            or ('offering_id' in payload and not isinstance(payload['offering_id'], str))):
                        raise ProfileError('Use the supported comparison catalog request.')
                    if catalog is None:
                        raise ProfileError('The local comparison catalog is not connected.', 503)
                    return self.respond(200, catalog.query(payload.get('scope'),
                        offering_id=payload.get('offering_id'),
                        expected_catalog_sha256=payload.get('expected_catalog_sha256')))
                if operation == 'reference':
                    if set(payload) - {'operation', 'offering_id', 'year', 'entry_ids'}:
                        raise ProfileError('Use the exact accepted-reference request.')
                    if reference_adapter is None:
                        raise ProfileError('The original accepted-reference verifier is not connected.', 503)
                    result = reference_adapter.lookup(payload.get('offering_id'),
                        **{key: payload[key] for key in ('year', 'entry_ids') if key in payload})
                    return self.respond(200, result)
                if repository is None:
                    raise ProfileError('Local PostgreSQL research is not connected.', 503)
                if operation == 'list':
                    if set(payload) - {'operation', 'scope', 'after_ordinal', 'limit', 'expected_snapshot_id'}:
                        raise ProfileError('Use the supported catalog request.')
                    validate_research_scope(payload.get('scope'))
                    result = repository.list_plans(payload['scope'],
                        **{key: payload[key] for key in ('after_ordinal', 'limit', 'expected_snapshot_id') if key in payload})
                elif operation == 'inspect':
                    if set(payload) - {'operation', 'offering_id', 'layers', 'limit', 'after_entity_id_by_layer', 'expected_snapshot_id'}:
                        raise ProfileError('Use the supported source inspection request.')
                    result = repository.inspect_plan(payload.get('offering_id'),
                        **{key: payload[key] for key in ('layers', 'limit', 'after_entity_id_by_layer', 'expected_snapshot_id') if key in payload})
                else:
                    raise ProfileError('Choose a supported research operation.')
                return self.respond(200, result)
            except ProfileError as error:
                return self.respond(error.code, {'error': str(error)})
            except (ValueError, TypeError, KeyError):
                return self.respond(422, {'error': 'The research request does not match its exact scope or snapshot.'})
            except (BrokenPipeError, ConnectionResetError):
                return
            except Exception:
                return self.respond(503, {'error': 'Local research is unavailable. Your reports are preserved.'})
            finally:
                if acquired:
                    slots.release()

    server.RequestHandlerClass = Handler
    server.research_repository = repository
    server.reference_adapter = reference_adapter
    return server
