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


def test_module_entrypoint_registers_campaign_handler():
    """`python -m covora.worker` runs as __main__; handlers must still land in the registry it uses."""
    import subprocess
    import sys

    out = subprocess.run(
        [sys.executable, "-m", "covora.worker", "--list-handlers"], capture_output=True, text=True, timeout=60
    )
    assert out.returncode == 0, out.stderr
    assert "campaign.run" in out.stdout.split()


def test_worker_process_knows_every_table():
    """The worker imports only what its jobs need; foreign keys must still resolve to known tables."""
    import subprocess
    import sys

    code = (
        "import covora.worker\n"
        "from covora.jobs.registry import load_handlers\n"
        "load_handlers()\n"
        "from covora.db.base import Base\n"
        "[fk.column for table in Base.metadata.tables.values() for fk in table.foreign_keys]\n"
    )
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr[-500:]
