"""Install the D146 conversation task only in a loopback, model-free preview."""

from pathlib import Path
from threading import BoundedSemaphore
from urllib.parse import urlsplit

from guest_profiles import ProfileError
from part_d_visit import PrescriptionVisit

PATH = '/api/prescription-preview/profile'
SCRIPT = '/prescription-profile-preview.js'
ASSET = Path(__file__).resolve().parent / 'part-d-preview/profile.js'


def install_profile_preview(server, service):
    if (not server.adaptive.fixture or server.budget is not None
            or server.server_address[0] != '127.0.0.1'):
        raise ValueError('Use an isolated model-free loopback preview.')
    base = server.RequestHandlerClass
    visit = PrescriptionVisit(server.adaptive, service)
    slots = BoundedSemaphore(2)
    marker = b'<script src="/advisor.js" defer></script>'

    class Handler(base):
        def index_html(self):
            html = super().index_html()
            if html.count(marker) != 1:
                raise ValueError('Use the current Daylight conversation shell.')
            return html.replace(marker, f'<script src="{SCRIPT.lstrip("/")}" defer></script>\n  '.encode() + marker)

        def static_file(self):
            if self.path == SCRIPT:
                return ASSET
            return super().static_file()

        def do_POST(self):
            if urlsplit(self.path).path != PATH:
                return super().do_POST()
            if not self.validate_request():
                return
            try:
                self.csrf()
                if self.path != PATH:
                    raise ProfileError('Use the prescription check without a query string.', 422)
                owner = server.profiles.digest(self.token())
                body = self.body()
                if not slots.acquire(blocking=False):
                    raise ProfileError('Another prescription check is running. Try again shortly.', 429)
                try:
                    result = visit.dispatch(owner, body)
                finally:
                    slots.release()
                return self.respond(200, result)
            except ProfileError as error:
                return self.respond(error.code, {'error': str(error)})
            except (KeyError, TypeError, ValueError):
                return self.respond(422, {'error': 'Use the current prescription question and a supported answer.'})

    server.RequestHandlerClass = Handler
    return server
