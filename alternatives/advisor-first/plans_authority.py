"""Reloadable exact-purpose release receipts, never a client feature flag.

The default receipt is pending. A later independently reviewed release binds
the immutable source, runtime, each output and each personal check separately.
This does not modify or inherit any older source or consumer acceptance.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from comparison_evidence import canonical_sha256, reject_economic_fields
from plans_catalog import ROOT, SHA256

PATH = ROOT / 'cms-slice/data-sources/plans-workspace-acceptance.json'
METHOD = 'plans-strict-priority-20261105-r2'
RUNTIME_FILES = ('plans_catalog.py', 'plans_authority.py', 'plans_service.py',
                 'plans_http.py', 'plans_context.py', 'plans_ranking.py', 'plans_adapters.py',
                 'natural_flow.py', 'natural_agent.py', 'plan_review.py',
                 'comparison_profile.py', 'plan_review_http.py', 'server.py')


def runtime_digest():
    base = Path(__file__).resolve().parent
    return canonical_sha256({name: hashlib.sha256((base / name).read_bytes()).hexdigest()
                             for name in RUNTIME_FILES})


LOADED_RUNTIME_DIGEST = runtime_digest()


class PlansAuthority:
    def __init__(self, path=PATH, now=None):
        self.path = Path(path)
        self.now = now or (lambda: datetime.now(timezone.utc))

    def read(self):
        """Revocation, expiry, source/code change apply on every operation."""
        try:
            value = json.loads(self.path.read_bytes())
            reject_economic_fields(value)
            def current(review):
                start = datetime.fromisoformat(review['reviewed_at'])
                end = datetime.fromisoformat(review['expires_at'])
                return (start.tzinfo is not None and end.tzinfo is not None
                        and start <= self.now() < end and bool(review['name'].strip())
                        and bool(review['receipt'].strip()))
            if (value['schema'] != 'plans-workspace-acceptance/2'
                    or value['status'] != 'accepted' or not value['release_id']
                    or value['catalog_sha256'] != SHA256 or value['method'] != METHOD
                    or value['runtime_sha256'] != runtime_digest()
                    or value['runtime_sha256'] != LOADED_RUNTIME_DIGEST
                    or not current(value['source_use']) or not current(value['independent_review'])
                    or value['independent_review']['role'] != 'medicare_subject_matter_reviewer'
                    or value['independent_review']['independent_of_sales'] is not True
                    or not isinstance(value['outputs'], dict)):
                raise ValueError('EXACT_RELEASE_REQUIRED')
            return value
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            return {'status': 'pending', 'release_id': None, 'outputs': {}}


def permits(authority, purpose, payload):
    """Both source-use and domain acceptance name this exact purpose/output."""
    key = purpose + ':' + canonical_sha256(payload)
    return (authority.get('status') == 'accepted'
            and purpose in authority.get('source_use', {}).get('purposes', [])
            and authority.get('outputs', {}).get(key) is True)
