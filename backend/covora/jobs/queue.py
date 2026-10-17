"""Postgres job queue: FOR UPDATE SKIP LOCKED claims, stale-lock recovery, retry with backoff."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import text, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from covora.jobs.models import Job
from covora.observability.redaction import redact

_CLAIM = text(
    """
    UPDATE job
       SET status = 'running', locked_at = now(), locked_by = :worker, attempts = attempts + 1, updated_at = now()
     WHERE id = (
        SELECT id FROM job
         WHERE (status = 'queued' AND run_after <= now())
            OR (status = 'running' AND locked_at < now() - make_interval(secs => :stale))
         ORDER BY run_after
         FOR UPDATE SKIP LOCKED
         LIMIT 1)
    RETURNING id
    """
)


async def enqueue(
    session: AsyncSession,
    kind: str,
    payload: dict,
    *,
    run_after: datetime | None = None,
    max_attempts: int = 3,
) -> Job:
    job = Job(kind=kind, payload=payload, status="queued", attempts=0, max_attempts=max_attempts)
    if run_after is not None:
        job.run_after = run_after
    session.add(job)
    await session.commit()
    await session.refresh(job)
    return job


async def claim_next(
    sessionmaker: async_sessionmaker[AsyncSession], worker_id: str, *, stale_after_s: float = 300
) -> Job | None:
    async with sessionmaker() as s:
        job_id = (await s.execute(_CLAIM, {"worker": worker_id, "stale": stale_after_s})).scalar_one_or_none()
        await s.commit()
        if job_id is None:
            return None
        return await s.get(Job, job_id)


async def complete(sessionmaker: async_sessionmaker[AsyncSession], job_id: UUID) -> None:
    async with sessionmaker() as s:
        await s.execute(update(Job).where(Job.id == job_id).values(status="done", locked_at=None, last_error=None))
        await s.commit()


async def fail(
    sessionmaker: async_sessionmaker[AsyncSession], job_id: UUID, error: str, *, base_delay_s: float = 5.0
) -> Job:
    async with sessionmaker() as s:
        job = await s.get(Job, job_id, with_for_update=True)
        if job is None:
            raise LookupError(f"job {job_id} not found")
        job.last_error = redact(error, [])
        job.locked_at = None
        job.locked_by = None
        if job.attempts < job.max_attempts:
            job.status = "queued"
            job.run_after = datetime.now(UTC) + timedelta(seconds=base_delay_s * 2 ** max(job.attempts - 1, 0))
        else:
            job.status = "failed"
        await s.commit()
        await s.refresh(job)
        return job
