"""Same-origin, CSRF-protected bridge for the separately owned Plans workspace."""
from urllib.parse import urlsplit
from guest_profiles import ProfileError


def install_plan_review(server):
    base = server.RequestHandlerClass

    class Handler(base):
        def do_POST(self):
            url = urlsplit(self.path)
            if url.path != '/api/plans/handoff':
                return super().do_POST()
            try:
                if not self.safe():
                    raise ProfileError('Request origin rejected.', 403)
                self.csrf()
                body = self.body()
                if url.query or not isinstance(body, dict) or set(body) != {'token'}:
                    raise ProfileError('Use the current reviewed-profile receipt.', 422)
                return self.respond(200, server.adaptive.resolve_plans_handoff(
                    server.profiles.digest(self.token()), body['token']))
            except ProfileError as error:
                return self.respond(error.code, {'error': str(error)})
            except (KeyError, TypeError, ValueError):
                return self.respond(422, {'error': 'Use the current reviewed-profile receipt.'})

    server.RequestHandlerClass = Handler
    return server
