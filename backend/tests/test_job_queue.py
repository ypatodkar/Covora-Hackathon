import asyncio
from datetime import UTC, datetime, timedelta

from covora.jobs.queue import claim_next, enqueue, fail
from tests.helpers import set_locked_at


async def test_concurrent_claims_get_different_jobs(session, sessionmaker):
    await enqueue(session, "x", {"n": 1})
    await enqueue(session, "x", {"n": 2})
    a, b = await asyncio.gather(claim_next(sessionmaker, "w1"), claim_next(sessionmaker, "w2"))
    assert {a.payload["n"], b.payload["n"]} == {1, 2}


async def test_fail_requeues_with_backoff_then_fails(session, sessionmaker):
    job = await enqueue(session, "x", {}, max_attempts=2)
    await claim_next(sessionmaker, "w")
    j = await fail(sessionmaker, job.id, "boom", base_delay_s=0)
    assert j.status == "queued" and j.attempts == 1
    await claim_next(sessionmaker, "w")
    j = await fail(sessionmaker, job.id, "boom again", base_delay_s=0)
    assert j.status == "failed" and j.last_error == "boom again"


async def test_future_jobs_not_claimed(session, sessionmaker):
    await enqueue(session, "x", {}, run_after=datetime.now(UTC) + timedelta(hours=1))
    assert await claim_next(sessionmaker, "w") is None


async def test_stale_running_job_reclaimed(session, sessionmaker):
    job = await enqueue(session, "x", {})
    await claim_next(sessionmaker, "w1")
    await set_locked_at(sessionmaker, job.id, datetime.now(UTC) - timedelta(minutes=10))
    again = await claim_next(sessionmaker, "w2", stale_after_s=300)
    assert again.id == job.id and again.locked_by == "w2"
