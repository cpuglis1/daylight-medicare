from dataclasses import dataclass
from psycopg.types.json import Jsonb


@dataclass(frozen=True)
class Lease:
    job_id: int
    owner_id: str
    fence: int
    payload: dict


class LeaseLost(RuntimeError):
    pass


def enqueue(connection, key: str, payload: dict, source_id: str = "local-owner-intake") -> int:
    with connection.transaction():
        connection.execute("""INSERT INTO dl_control.job(idempotency_key,source_id,payload)
            VALUES(%s,%s,%s) ON CONFLICT(idempotency_key) DO NOTHING""", (key,source_id,Jsonb(payload)))
        row = connection.execute("SELECT job_id,source_id,payload FROM dl_control.job WHERE idempotency_key=%s", (key,)).fetchone()
        if row[1] != source_id or row[2] != payload:
            raise ValueError("Idempotency key reused with different source/configuration")
        return row[0]


def claim(connection, owner: str, lease_seconds: int = 60, job_id: int | None = None) -> Lease | None:
    if not owner or not 1 <= lease_seconds <= 3600:
        raise ValueError("Invalid lease owner/duration")
    with connection.transaction():
        row = connection.execute("""WITH candidate AS (
          SELECT j.job_id FROM dl_control.job j
          WHERE (j.state='pending' OR (j.state='running' AND j.lease_until<clock_timestamp()))
          AND (%s::bigint IS NULL OR j.job_id=%s)
          AND NOT EXISTS (SELECT 1 FROM dl_control.source_access_state s
            WHERE s.source_id=j.source_id AND s.state IN ('held','stopped'))
          ORDER BY j.job_id FOR UPDATE OF j SKIP LOCKED LIMIT 1
        ) UPDATE dl_control.job j SET owner_id=%s,fence=fence+1,
          lease_until=clock_timestamp()+make_interval(secs=>%s),state='running'
          FROM candidate c WHERE j.job_id=c.job_id RETURNING j.job_id,j.fence,j.payload""", (job_id,job_id,owner,lease_seconds)).fetchone()
        return Lease(row[0],owner,row[1],row[2]) if row else None


def require_lease(connection, lease: Lease):
    row = connection.execute("""SELECT j.job_id FROM dl_control.job j
       WHERE j.job_id=%s AND j.owner_id=%s AND j.fence=%s AND j.state='running'
       AND j.lease_until>clock_timestamp()
       AND NOT EXISTS (SELECT 1 FROM dl_control.source_access_state s
          WHERE s.source_id=j.source_id AND s.state IN ('held','stopped'))
       FOR UPDATE OF j""", (lease.job_id,lease.owner_id,lease.fence)).fetchone()
    if row is None:
        raise LeaseLost("Lease expired, replaced or source stopped")


def heartbeat(connection, lease: Lease, lease_seconds: int = 60):
    if not 1 <= lease_seconds <= 3600:
        raise ValueError("Invalid lease duration")
    with connection.transaction():
        require_lease(connection, lease)
        connection.execute("UPDATE dl_control.job SET lease_until=clock_timestamp()+make_interval(secs=>%s) WHERE job_id=%s", (lease_seconds,lease.job_id))


def stop_source(connection, source_id: str, reason: str):
    if not source_id or not reason:
        raise ValueError("Source and reason required")
    with connection.transaction():
        connection.execute("SELECT dl_control.persist_source_stop(%s,%s)",(source_id,reason))
