"""Loopback D146 research routes. Exact selections live in visit memory."""

from secrets import token_hex
from threading import BoundedSemaphore, Lock
from time import monotonic

from guest_profiles import ProfileError
from daylight_data.serving.binding import ResearchServingError, digest


PREFIX = '/api/pilot-doctors/'
ROUTES = {'search', 'sites', 'visit', 'selection', 'evidence'}
TTL = 15 * 60
MAX_VISITS = 64
SELECTION_FIELDS = {'candidate_id', 'site_id', 'offering_id', 'intended_date', 'route'}
SEARCH_FIELDS = {'name', 'practice', 'specialty', 'location', 'region', 'year', 'offset', 'limit'}


class DoctorFixtureRoutes:
    def __init__(self, service):
        self.service = service
        self.lock = Lock()
        self.slots = BoundedSemaphore(2)
        self.visits = {}

    def current(self, owner, expected):
        entry = self.active(owner)
        if expected != (entry[0] if entry else None):
            raise ProfileError('DOCTOR_SELECTION_CHANGED', 409)
        return entry

    def active(self, owner):
        now = monotonic()
        self.visits = {key: row for key, row in self.visits.items() if row[2] > now}
        return self.visits.get(owner)

    def dispatch(self, handler, path):
        try:
            if path not in ROUTES:
                raise ProfileError('DOCTOR_ROUTE_UNKNOWN', 404)
            handler.csrf()
            owner = handler.server.profiles.digest(handler.token())
            payload = handler.body()
            if not self.slots.acquire(blocking=False):
                raise ProfileError('DOCTOR_FIXTURE_BUSY', 429)
            try:
                result = self.run(owner, path, payload)
            finally:
                self.slots.release()
            return handler.respond(200, result)
        except ProfileError as error:
            return handler.respond(error.code, {'error': str(error)})
        except ResearchServingError as error:
            status = 503 if str(error).startswith(('PILOT_SOURCE_', 'PILOT_DATABASE_', 'PILOT_EVIDENCE_STALE')) else 422
            return handler.respond(status, {'error': str(error)})

    def run(self, owner, path, body):
        if path == 'search':
            if set(body) - SEARCH_FIELDS:
                raise ProfileError('DOCTOR_INVALID_SEARCH', 422)
            return self.service.search(**body)

        if path == 'sites':
            if set(body) != {'candidate_id', 'offset'}:
                raise ProfileError('DOCTOR_INVALID_SITE_PAGE', 422)
            return self.service.sites(**body)

        if path == 'visit':
            if body:
                raise ProfileError('DOCTOR_INVALID_VISIT', 422)
            with self.lock:
                entry = self.active(owner)
            return {'revision': entry[0] if entry else None, 'has_selection': bool(entry and entry[1])}

        if path == 'selection':
            if set(body) != {'expected_revision', 'selection', 'confirmed'}:
                raise ProfileError('DOCTOR_INVALID_SELECTION', 422)
            selection = body['selection']
            if selection is not None:
                if not isinstance(selection, dict) or set(selection) != SELECTION_FIELDS or body['confirmed'] is not True:
                    raise ProfileError('DOCTOR_EXPLICIT_SELECTION_REQUIRED', 422)
                selection = self.service.selection(**selection)
            elif body['confirmed'] is not False:
                raise ProfileError('DOCTOR_INVALID_SELECTION', 422)
            with self.lock:
                if not self.current(owner, body['expected_revision']) and len(self.visits) >= MAX_VISITS:
                    raise ProfileError('DOCTOR_FIXTURE_BUSY', 429)
                revision = token_hex(16)
                self.visits[owner] = (revision, selection, monotonic() + TTL)
            return {'revision': revision, 'state': 'cleared' if selection is None else 'explicit_selection',
                    'evidence_invalidated': True}

        if set(body) != {'revision'} or not isinstance(body['revision'], str):
            raise ProfileError('DOCTOR_INVALID_REVISION', 422)
        revision = body['revision']
        with self.lock:
            entry = self.current(owner, revision)
            selection = entry[1] if entry else None
        if selection is None:
            raise ProfileError('DOCTOR_EXPLICIT_SELECTION_REQUIRED', 409)
        result = self.service.evidence(selection)
        with self.lock:
            self.current(owner, revision)
        return {**result, 'revision': revision,
                'receipt_id': digest([owner, revision, result['binding_id'], result['selection']])}
