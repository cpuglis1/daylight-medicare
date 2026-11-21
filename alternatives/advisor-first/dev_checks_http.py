"""Localhost routes for the "Checks and instructions" dev page (D155 Q8, Q2).

Purpose: let Charlie read and edit the conversation checks and the ordering
guidance while testing on :8893/:8894, without editing JSON by hand.

Routes (added to the built advisor handler):
  GET  /api/dev/checks  -> {checks, instructions: {orderingGuidance, default}}
  POST /api/dev/checks  <- {checks?: [{id, title?, question?, floor?, failOnAny?}],
                            orderingGuidance?: str}

Role: installed by server.build() only inside its ``if turn_traces:`` block, so it
exists exactly when local turn traces do: never in the pilot, a hosted origin, or
a plain build() used by tests. install_dev_checks refuses pilot and hosted too,
as a second lock.

Security decisions: every route needs the same-origin check (safe()) and a guest
cookie; POST also needs the CSRF header and a bounded JSON body (the pinned
engine's csrf() and body()). Gates (privacy, sources) are read-only: the
validation in conversation_config refuses any change to them. Both inputs are
validated before either file is written, so a bad check edit never leaves a
half-applied save.
"""
from __future__ import annotations

from urllib.parse import urlsplit

import conversation_config

ROUTE = '/api/dev/checks'


class DevChecksDisabled(RuntimeError):
    """Raised when the dev checks routes are asked for in the pilot or a hosted service."""


def install_dev_checks(service, *, pilot=False, hosted=False,
                       checks_path=None, instructions_path=None):
    """Add the dev checks routes to a built local advisor service.

    Args:
        service: the built server (after install_turn_traces).
        pilot: True for a pilot rehearsal; refused.
        hosted: True when a public origin is set; refused.
        checks_path, instructions_path: override the config files (tests).
    Returns:
        The same service with its RequestHandlerClass extended.
    Raises:
        DevChecksDisabled: for a pilot or hosted service.
    """
    if pilot or hosted:
        raise DevChecksDisabled('The checks page runs only for local testing.')
    from natural_agent import ORDERING_GUIDANCE
    checks_file = checks_path or conversation_config.CHECKS_PATH
    guidance_file = instructions_path or conversation_config.INSTRUCTIONS_PATH
    base = service.RequestHandlerClass

    def snapshot():
        """Return the GET payload: current checks plus current and default guidance."""
        return {
            'checks': conversation_config.load_checks(checks_file)['checks'],
            'instructions': {
                'orderingGuidance': conversation_config.ordering_guidance(guidance_file) or ORDERING_GUIDANCE,
                'default': ORDERING_GUIDANCE,
            },
        }

    class DevChecksHandler(base):
        """Adds GET and POST /api/dev/checks; everything else goes to the base handler."""

        def _guard(self):
            """Return an error response tuple, or None when origin and cookie are fine."""
            if not self.safe():
                return 403, {'error': 'Request origin rejected.'}
            if urlsplit(self.path).query:
                return 422, {'error': 'Do not put details in URLs.'}
            if not self.token():
                return 401, {'error': 'Start a visit first.'}
            return None

        def do_GET(self):
            """Serve the current checks and guidance."""
            if urlsplit(self.path).path != ROUTE:
                return super().do_GET()
            try:
                refused = self._guard()
                if refused:
                    return self.respond(*refused)
                return self.respond(200, snapshot())
            except Exception as error:
                return self._fail(error)

        def do_POST(self):
            """Validate and save edits, then return the new snapshot."""
            if urlsplit(self.path).path != ROUTE:
                return super().do_POST()
            try:
                refused = self._guard()
                if refused:
                    return self.respond(*refused)
                self.csrf()
                value = self.body()
                unknown = set(value) - {'checks', 'orderingGuidance'}
                if unknown or not value:
                    return self.respond(422, {'error': 'Send checks and/or orderingGuidance only.'})
                guidance = value.get('orderingGuidance')
                if guidance is not None:
                    # Validate before any write so a bad check edit cannot half-apply.
                    if (not isinstance(guidance, str) or not guidance.strip()
                            or len(guidance) > conversation_config.MAX_GUIDANCE or '\x00' in guidance):
                        raise conversation_config.ConfigError(
                            f'ordering guidance must be 1-{conversation_config.MAX_GUIDANCE} characters')
                if 'checks' in value:
                    conversation_config.save_checks(value['checks'], checks_file)
                if guidance is not None:
                    conversation_config.save_ordering_guidance(guidance, guidance_file)
                return self.respond(200, snapshot())
            except Exception as error:
                return self._fail(error)

        def _fail(self, error):
            """Map ConfigError/ProfileError codes to a JSON error; anything else is 500."""
            code = getattr(error, 'code', 500)
            code = code if isinstance(code, int) and 400 <= code < 600 else 500
            message = str(error) if code < 500 else 'Checks unavailable.'
            return self.respond(code, {'error': message or 'Checks unavailable.'})

    service.RequestHandlerClass = DevChecksHandler
    return service
