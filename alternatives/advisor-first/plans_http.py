"""Private same-origin APIs; no profile/token in URLs or browser-authored facts."""
from urllib.parse import urlsplit
from guest_profiles import ProfileError
from plans_service import PlansService


def install_plans(server, *, local_review=False):
    service = PlansService(server.adaptive, local_review=local_review)
    server.plans = server.adaptive.plans_service = service
    base = server.RequestHandlerClass

    class Handler(base):
        def respond(self, code, value, mime='application/json; charset=utf-8', cookie=None):
            if self.path == '/api/status' and code == 200 and isinstance(value, dict):
                try:
                    projection, _ = service.projection()
                    status = {**projection['coverage'], 'catalog_sha256': projection['catalog_sha256'],
                              'scope': projection['scope'], 'adapters': projection['adapters']}
                except (OSError, ValueError, KeyError, TypeError):
                    status = {'app_access': 'source_unavailable', 'published_fields': 0}
                value = {**value, 'plans_workspace': status}
            return super().respond(code, value, mime, cookie)

        def do_POST(self):
            url = urlsplit(self.path)
            routes = {'/api/plans/catalog', '/api/plans/workspace', '/api/plans/priorities', '/api/plans/detail'}
            if url.path not in routes:
                return super().do_POST()
            try:
                if not self.safe():
                    raise ProfileError('Request origin rejected.', 403)
                self.csrf()
                body = self.body()
                keys = ({'/api/plans/catalog': set(), '/api/plans/workspace': {'token'},
                         '/api/plans/priorities': {'token', 'order', 'confirmed'},
                         '/api/plans/detail': {'offeringId'}})[url.path]
                if url.query or set(body) != keys:
                    raise ProfileError('Use the current Plans request.', 422)
                owner = server.profiles.digest(self.token())
                if 'token' in keys and (not isinstance(body['token'], str) or not 1 <= len(body['token']) <= 100):
                    raise ProfileError('Use the current reviewed-profile receipt.', 422)
                if url.path.endswith('/detail'):
                    if not isinstance(body['offeringId'], str):
                        raise ProfileError('Use a retained plan identity.', 422)
                    value = service.detail(body['offeringId'])
                elif url.path.endswith('/priorities'):
                    value = service.confirm_priorities(owner, body['token'], body['order'], body['confirmed'])
                else:
                    value = service.workspace(owner, body.get('token'))
                return self.respond(200, value)
            except ProfileError as error:
                return self.respond(error.code, {'error': str(error)})
            except (OSError, ValueError, KeyError, TypeError):
                return self.respond(503, {'error': 'The plan catalog could not be verified. Refresh after the source is restored.',
                                          'code': 'CATALOG_UNAVAILABLE'})

    server.RequestHandlerClass = Handler
    return server
