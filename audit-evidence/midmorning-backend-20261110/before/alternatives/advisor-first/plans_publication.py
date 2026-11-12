"""Publication is independent of ranking and of a person's verification.

The owner-authorized local review shows the sealed, supported reference cells.
It is not an independent consumer release. A consumer receipt is separately
scoped to exact cells/examples; no recommendation receipt can publish a fact.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

from comparison_evidence import canonical_sha256, reject_economic_fields
from plans_catalog import ROOT, SHA256

PATH = ROOT / 'cms-slice/data-sources/plans-publication.json'
SCHEMA = 'plans-publication/1'


def current(review, now):
    try:
        start, end = (datetime.fromisoformat(review[k]) for k in ('reviewed_at', 'expires_at'))
        return (start.tzinfo is not None and end.tzinfo is not None and start <= now < end
                and bool(review['name'].strip()) and bool(review['receipt'].strip()))
    except (KeyError, ValueError, TypeError, AttributeError):
        return False


class PlansPublication:
    def __init__(self, path=PATH, now=None):
        self.path = Path(path)
        self.now = now or (lambda: datetime.now(timezone.utc))

    def read(self, *, local_review=False):
        held = {'state': 'held', 'release_id': None, 'outputs': {}, 'withheld': [],
                'consumer_approved': False, 'reason_code': 'PUBLICATION_REVIEW_REQUIRED'}
        try:
            value = json.loads(self.path.read_bytes())
            reject_economic_fields(value)
            if (value['schema'] != SCHEMA or value['catalog_sha256'] != SHA256
                    or value.get('revoked') is True or not isinstance(value['withheld'], list)):
                return held
            # This switch is server-owned, enabled only by --local-research.
            # It cannot be requested in a browser payload or inherited from AI consent.
            if local_review and value['local_review']['authorized'] is True:
                return {**held, 'state': 'local_review', 'release_id': value['local_review']['id'],
                        'reason_code': None, 'withheld': value['withheld']}
            release = value['consumer']
            if (release['status'] != 'accepted' or not release['release_id']
                    or not current(release['source_use'], self.now())
                    or not current(release['independent_review'], self.now())
                    or release['independent_review']['independent_of_sales'] is not True
                    or release['independent_review']['role'] != 'medicare_subject_matter_reviewer'
                    or not isinstance(release['outputs'], dict)):
                return held
            return {**release, 'state': 'published', 'consumer_approved': True,
                    'withheld': value['withheld'], 'reason_code': None}
        except (OSError, ValueError, TypeError, KeyError, AttributeError):
            return held


def publication_permits(release, purpose, payload):
    key = purpose + ':' + canonical_sha256(payload)
    if key in release.get('withheld', []):
        return False
    return (release['state'] == 'local_review' or
            release['state'] == 'published'
            and purpose in release.get('source_use', {}).get('purposes', [])
            and release['outputs'].get(key) is True)
