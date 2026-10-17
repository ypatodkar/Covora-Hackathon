from covora.jobs.queue import enqueue
from covora.worker import Worker
from tests.helpers import get_job


async def test_runs_handler_and_completes(services, session):
    seen = []

    async def handler(job, svc):
        seen.append(job.payload["n"])

    await enqueue(session, "demo", {"n": 7})
    assert await Worker(services, {"demo": handler}).run_once() is True
    assert seen == [7] and (await get_job(services.sessionmaker, kind="demo")).status == "done"


async def test_handler_error_fails_job_redacted(services, session):
    async def handler(job, svc):
        raise RuntimeError("bad nvapi-SECRET1234567 call")

    await enqueue(session, "demo", {}, max_attempts=1)
    await Worker(services, {"demo": handler}).run_once()
    job = await get_job(services.sessionmaker, kind="demo")
    assert job.status == "failed" and "nvapi-SECRET1234567" not in job.last_error


async def test_unknown_kind_fails(services, session):
    await enqueue(session, "nope", {}, max_attempts=1)
    await Worker(services, {}).run_once()
    assert "no handler" in (await get_job(services.sessionmaker, kind="nope")).last_error


async def test_idle_returns_false(services):
    assert await Worker(services, {}).run_once() is False
