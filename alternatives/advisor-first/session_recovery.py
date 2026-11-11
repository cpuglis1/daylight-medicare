"""Local HTTP recovery seam; pinned engine, storage and paid-call policy stay intact."""
import logging
import re
import threading
import time
from urllib.parse import urlsplit

from guest_profiles import ProfileError

LOGGER = logging.getLogger(__name__)
RECOVERABLE = {
    'Your conversation changed. Keep this message and resume the latest state.': 'conversation_state',
    'Use the current conversation state.': 'conversation_state',
    'Resume the current conversation before continuing. Your reports are preserved.': 'conversation_state',
    'Your earlier message is still being processed. Your work is preserved.': 'conversation_busy',
}


def resume_visit(flow, owner, payload):
    """Read the trusted current visit with a cookie-bound request reference."""
    if (not isinstance(payload, dict) or set(payload) - {'requestId', 'previousRequestId'}
            or not payload.get('requestId') or any(
                not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9-]{10,80}', value)
                for value in payload.values())):
        raise ProfileError('Use the current visit reference.', 422)
    with flow.lock:
        now = time.time()
        if flow.revoked_owners.get(owner, 0) > now:
            raise ProfileError('This guest session was deleted.', 401)
        if owner in flow.natural_active:
            return {'status': 'working'}
        entry = next((flow.turn_journal[(owner, key)] for key in payload.values()
                      if (owner, key) in flow.turn_journal
                      and flow.turn_journal[(owner, key)]['expires'] > now), None)
        if entry is None:
            return {'status': 'expired'}
        chain = entry['response']['continuation'].split('.')[0]
        if flow.current_chain.get(owner) != chain:
            return {'status': 'superseded'}
        head = flow.state_heads.get((owner, chain))
        latest = next(((key, item) for (entry_owner, key), item
                       in reversed(list(flow.turn_journal.items()))
                       if entry_owner == owner and item['expires'] > now
                       and item['response'].get('continuation') == head), None)
        if latest is None:
            return {'status': 'expired'}
        request_id, latest_entry = latest
        response = flow.replay_response(owner, latest_entry['response'])
        # The browser must apply its latest explicit choice. A read grants none.
        response['guide']['preferences'].update(saveGuide=False, saveSensitive=False)
        return {'status': 'resumed', 'requestId': request_id, 'response': response}


def install_session_recovery(server):
    base = server.RequestHandlerClass
    slots = threading.BoundedSemaphore(2)

    class Handler(base):
        def respond(self, code, value, mime='application/json; charset=utf-8', cookie=None):
            if (self.path == '/api/conversation/turn' and code == 409
                    and isinstance(value, dict) and value.get('error') in RECOVERABLE):
                value = {**value, 'recovery': RECOVERABLE[value['error']]}
            return super().respond(code, value, mime, cookie)

        def do_POST(self):
            url = urlsplit(self.path)
            if url.path not in {'/api/conversation/recover', '/api/conversation/resume'}:
                return super().do_POST()
            acquired = False
            try:
                if not self.safe():
                    raise ProfileError('Request origin rejected.', 403)
                if url.query:
                    raise ProfileError('Use a request body, not URL parameters.', 422)
                self.csrf()
                payload = self.body()
                if not slots.acquire(blocking=False):
                    return self.respond(200, {'status': 'working'})
                acquired = True
                owner = server.profiles.digest(self.token())
                result = (resume_visit(server.adaptive, owner, payload) if url.path.endswith('/resume')
                          else server.adaptive.recover(owner, payload))
                if result.get('response') and 'requestId' not in result:
                    with server.adaptive.lock:
                        request_id = next((key for (entry_owner, key), item
                                           in reversed(list(server.adaptive.turn_journal.items()))
                                           if entry_owner == owner and item['expires'] > time.time()
                                           and item['response'].get('continuation') == result['response'].get('continuation')), None)
                    if request_id:
                        result = {**result, 'requestId': request_id}
                # No request text, identifiers, profile values or tokens.
                LOGGER.info('Daylight session recovery status=%s', result['status'])
                return self.respond(200, result)
            except ProfileError as error:
                return self.respond(error.code, {'error': str(error)})
            except (KeyError, TypeError, ValueError):
                return self.respond(422, {'error': 'The message could not be reconnected.'})
            except (BrokenPipeError, ConnectionResetError):
                return
            except Exception as error:
                LOGGER.error('Daylight session recovery failed type=%s', type(error).__name__)
                return self.respond(503, {'error': 'Daylight could not reconnect just now.'})
            finally:
                if acquired:
                    slots.release()

    server.RequestHandlerClass = Handler
    return server
