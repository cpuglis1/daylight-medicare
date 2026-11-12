"""Local HTTP recovery seam; pinned engine, storage and paid-call policy stay intact."""
import logging
import threading
from urllib.parse import urlsplit

from guest_profiles import ProfileError

LOGGER = logging.getLogger(__name__)
RECOVERABLE = {
    'Your conversation changed. Keep this message and resume the latest state.': 'conversation_state',
    'Use the current conversation state.': 'conversation_state',
    'Resume the current conversation before continuing. Your reports are preserved.': 'conversation_state',
    'Your earlier message is still being processed. Your work is preserved.': 'conversation_busy',
}


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
            if url.path != '/api/conversation/recover':
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
                result = server.adaptive.recover(server.profiles.digest(self.token()), payload)
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
                return self.respond(503, {'error': 'MidMorning could not reconnect just now.'})
            finally:
                if acquired:
                    slots.release()

    server.RequestHandlerClass = Handler
    return server
