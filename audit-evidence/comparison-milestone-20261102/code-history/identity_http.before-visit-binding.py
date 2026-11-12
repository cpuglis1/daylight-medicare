"""Current-owner identity routes; no profile mutation, model call or saving.

The caller installs a server-owned service. HTTP never selects source purpose,
audience, owner, adapter facts or source authority from JSON. Every operation is
bound to the current signed conversation and journal before and after reads.
"""
import copy
import hmac
import re
import threading
import time
from urllib.parse import urlsplit

from guest_profiles import ProfileError
from comparison_profile import build_comparison_profile
from identity_journey import IdentityJourney, IdentityJourneyError, IDENTITY_SCOPE


def install_identity_routes(server, service=None):
    service = service if service is not None else IdentityJourney()
    if not isinstance(service, IdentityJourney):
        raise ValueError('SERVER_OWNED_IDENTITY_SERVICE_REQUIRED')
    base = server.RequestHandlerClass
    slots = threading.BoundedSemaphore(2)
    common = {'guide', 'record', 'continuation', 'requestId'}
    operations = {
        '/api/identity/view': {'itemId'},
        '/api/identity/drug/search': {'itemId', 'afterOrdinal', 'expectedSnapshotId', 'choiceToken'},
        '/api/identity/provider/search': {'itemId', 'selector', 'afterOrdinal', 'expectedSnapshotId', 'choiceToken'},
        '/api/identity/confirm': {'choiceToken', 'candidateId', 'confirmed'},
        '/api/identity/forget': {'itemId'},
    }

    def snapshot(owner, payload):
        continuation = payload.get('continuation')
        if (not isinstance(continuation, str)
                or not re.fullmatch(r'[a-f0-9]{32}\.[a-f0-9]{64}', continuation)
                or not re.fullmatch(r'[A-Za-z0-9-]{10,80}', str(payload.get('requestId', '')))):
            raise ProfileError('Use the current conversation for identity details.', 409)
        guide, record = server.adaptive.validate(copy.deepcopy(payload['guide']), copy.deepcopy(payload['record']))
        chain = continuation.split('.')[0]
        with server.adaptive.lock:
            if (owner in server.adaptive.natural_active or server.adaptive.current_chain.get(owner) != chain
                    or server.adaptive.state_heads.get((owner, chain)) != continuation
                    or not hmac.compare_digest(continuation, server.adaptive.bind(owner, guide, record, chain))):
                raise ProfileError('Your conversation changed. Use its latest state.', 409)
            for key, entry in reversed(list(server.adaptive.turn_journal.items())):
                if key[0] == owner and entry['expires'] > time.time() and entry['response'].get('continuation') == continuation:
                    return copy.deepcopy(entry['response']), (key, entry['signature'])
        raise ProfileError('Identity details need a current conversation snapshot.', 409)

    def current(owner, continuation, journal):
        chain = continuation.split('.')[0]
        with server.adaptive.lock:
            latest = next(((key, entry['signature']) for key, entry in
                reversed(list(server.adaptive.turn_journal.items())) if key[0] == owner
                and entry['expires'] > time.time() and entry['response'].get('continuation') == continuation), None)
            if (owner in server.adaptive.natural_active or server.adaptive.current_chain.get(owner) != chain
                    or server.adaptive.state_heads.get((owner, chain)) != continuation or latest != journal):
                raise ProfileError('Your conversation changed. Use its latest state.', 409)

    class Handler(base):
        def identity_guard(self, *, writing=False):
            if not self.safe():
                raise ProfileError('Request origin rejected.', 403)
            if urlsplit(self.path).query:
                raise ProfileError('Use the supported identity request body.')
            server.profiles.require(self.token())
            if writing:
                self.csrf()

        def do_GET(self):
            if urlsplit(self.path).path != '/api/identity/status':
                return super().do_GET()
            try:
                self.identity_guard()
                return self.respond(200, {'identity': service._base(state='capability')})
            except ProfileError as error:
                return self.respond(error.code, {'error': str(error)})

        def do_POST(self):
            path = urlsplit(self.path).path
            if path not in operations:
                return super().do_POST()
            acquired, owner = False, None
            try:
                self.identity_guard(writing=True)
                payload = self.body()
                if (not isinstance(payload, dict) or set(payload) - common - operations[path]
                        or not common <= set(payload)):
                    raise ProfileError('Use the current item identity request.')
                owner = server.profiles.digest(self.token())
                response, journal = snapshot(owner, payload)
                continuation = response['continuation']
                profile = build_comparison_profile(response['guide'], response['record'],
                                                   requested_scope=copy.deepcopy(IDENTITY_SCOPE))
                if not slots.acquire(blocking=False):
                    raise ProfileError('Identity research is busy. Try again shortly.', 429)
                acquired = True
                current(owner, continuation, journal)
                if path == '/api/identity/view':
                    result = service.view(owner, profile, item_id=payload.get('itemId'))
                elif path == '/api/identity/drug/search':
                    result = service.drug_search(owner, profile, item_id=payload.get('itemId'),
                        **{target: payload[source] for source, target in
                           (('afterOrdinal', 'after_ordinal'), ('expectedSnapshotId', 'expected_snapshot_id'),
                            ('choiceToken', 'choice_token')) if source in payload})
                elif path == '/api/identity/provider/search':
                    result = service.provider_search(owner, profile, item_id=payload.get('itemId'),
                        **{target: payload[source] for source, target in
                           (('selector', 'selector'), ('afterOrdinal', 'after_ordinal'),
                            ('expectedSnapshotId', 'expected_snapshot_id'), ('choiceToken', 'choice_token'))
                           if source in payload})
                elif path == '/api/identity/confirm':
                    result = service.confirm(owner, profile, choice_token=payload.get('choiceToken'),
                        candidate_id=payload.get('candidateId'), confirmed=payload.get('confirmed'))
                else:
                    result = service.forget_owner(owner, item_id=payload.get('itemId'))
                try:
                    current(owner, continuation, journal)
                except ProfileError:
                    service.forget_owner(owner)
                    raise
                result['preparation'] = service.preparation(owner, profile)
                current(owner, continuation, journal)
                if service.capability()['state'] != 'internal_research_available':
                    service.forget_owner(owner)
                    result = service.view(owner, profile)
                    result['preparation'] = service.preparation(owner, profile)
                # Only derived identity data returns. Client saving/preferences,
                # current guide, reports, composer and dialogue are never replaced.
                return self.respond(200, {'identity': result, 'continuation': continuation})
            except ProfileError as error:
                if acquired and owner is not None:
                    service.forget_owner(owner)
                return self.respond(error.code, {'error': str(error)})
            except (IdentityJourneyError, ValueError, TypeError, KeyError):
                return self.respond(422, {'identity': service._base(state='held_or_unavailable',
                    reason_codes=['IDENTITY_REQUEST_STALE_UNRESOLVED_OR_SOURCE_CHANGED'])})
            except (BrokenPipeError, ConnectionResetError):
                return
            except Exception:
                return self.respond(503, {'identity': service._base(state='unavailable',
                    reason_codes=['IDENTITY_SOURCE_UNAVAILABLE'])})
            finally:
                if acquired:
                    slots.release()

    server.RequestHandlerClass = Handler
    server.identity_service = service
    return server
