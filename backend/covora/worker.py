"""Background worker: claims jobs from Postgres and runs their handlers (spec §6, §8.4).

Run with:  uv run python -m covora.worker
"""

import asyncio
import contextlib
import logging
import os
import signal
import socket
import sys
from collections.abc import Mapping
from uuid import uuid4

from covora.config import get_settings
from covora.jobs.queue import claim_next, complete, fail
from covora.jobs.registry import Handler, load_handlers
from covora.memory.prompts import sync_prompts
from covora.observability.redaction import redact
from covora.services import Services, build_services

logger = logging.getLogger("covora.worker")


class Worker:
    def __init__(
        self,
        services: Services,
        handlers: Mapping[str, Handler],
        *,
        worker_id: str | None = None,
        poll_interval_s: float = 1.0,
    ) -> None:
        self._services = services
        self._handlers = handlers
        self.worker_id = worker_id or f"{socket.gethostname()}-{os.getpid()}-{uuid4().hex[:6]}"
        self._poll_interval_s = poll_interval_s

    async def run_once(self) -> bool:
        settings = self._services.settings
        job = await claim_next(self._services.sessionmaker, self.worker_id, stale_after_s=settings.job_stale_after_s)
        if job is None:
            return False
        handler = self._handlers.get(job.kind)
        try:
            if handler is None:
                raise LookupError(f"no handler for job kind '{job.kind}'")
            await handler(job, self._services)
        except Exception as exc:
            message = redact(f"{type(exc).__name__}: {exc}", settings.secret_values())
            updated = await fail(self._services.sessionmaker, job.id, message)
            logger.warning("job %s %s failed (%s): %s", job.kind, job.id, updated.status, message)
        else:
            await complete(self._services.sessionmaker, job.id)
            logger.info("job %s %s done", job.kind, job.id)
        return True

    async def run_forever(self, stop: asyncio.Event | None = None) -> None:
        stop = stop or asyncio.Event()
        while not stop.is_set():
            worked = await self.run_once()
            if not worked:
                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(stop.wait(), timeout=self._poll_interval_s)


async def _main() -> None:
    import covora.graphs.jobs  # noqa: F401  (registers job handlers)
    from covora.graphs.checkpointer import ensure_checkpointer_tables

    settings = get_settings()
    await ensure_checkpointer_tables(settings)
    services, engine = build_services(settings)
    async with services.sessionmaker() as session:
        await sync_prompts(session)
    worker = Worker(services, load_handlers(), poll_interval_s=settings.worker_poll_interval_s)
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)
    print(f"worker {worker.worker_id} started", flush=True)
    try:
        await worker.run_forever(stop)
    finally:
        await engine.dispose()
        print(f"worker {worker.worker_id} stopped", flush=True)


def main() -> None:
    if "--list-handlers" in sys.argv:
        print(" ".join(sorted(load_handlers())))
        return
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    asyncio.run(_main())


if __name__ == "__main__":
    main()
