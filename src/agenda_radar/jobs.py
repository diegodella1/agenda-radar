import time

from sqlalchemy import or_, select, text, true, update
from sqlalchemy.dialects.sqlite import insert

from .db import Database
from .models import Job


def enqueue(db: Database, kind: str, payload: dict, key: str, user_id=None) -> int:
    with db.session() as session:
        session.execute(
            insert(Job)
            .values(kind=kind, payload=payload, idempotency_key=key, user_id=user_id)
            .on_conflict_do_nothing()
        )
        return session.scalar(select(Job.id).where(Job.idempotency_key == key))


def claim(db: Database, owner: str, now=None, lease_seconds=300) -> Job | None:
    from .editorial import active_config

    now = time.time() if now is None else now
    with db.session() as session:
        session.execute(text("BEGIN IMMEDIATE"))
        _, config = active_config(session)
        job = session.scalar(
            select(Job)
            .where(
                Job.kind.not_in(["poll", "enrich"]) if not config.run_enabled else true(),
                or_(
                    (Job.status == "pending") & (Job.run_after <= now),
                    (Job.status == "running") & (Job.lease_until < now),
                ),
            )
            .order_by(Job.run_after, Job.id)
            .limit(1)
        )
        if job:
            job.status = "running"
            job.owner = owner
            job.attempt += 1
            job.lease_until = now + lease_seconds
        return job


def finish(db: Database, job_id: int, owner: str, result=None, error=None) -> bool:
    with db.session() as session:
        session.execute(text("BEGIN IMMEDIATE"))
        job = session.get(Job, job_id)
        if not job or job.owner != owner or job.status != "running":
            return False
        job.result = result or {}
        job.error_code = error
        job.status = "done" if not error else ("failed" if job.attempt >= 5 else "pending")
        if error in ("http_401", "http_403", "robots_denied", "not_entitled", "no_credentials"):
            job.status = "failed"
        delay = 3600 if error in ("http_429", "quota_exhausted") else min(3600, 30 * 2**job.attempt)
        job.run_after = time.time() + delay
        job.lease_until = 0
        job.owner = None
        return True


def renew(db: Database, job_id: int, owner: str):
    with db.session() as session:
        session.execute(
            update(Job)
            .where(Job.id == job_id, Job.owner == owner, Job.status == "running")
            .values(lease_until=time.time() + 300)
        )
