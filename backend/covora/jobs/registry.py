"""Job kind → handler. A module of its own, so `python -m covora.worker` (which runs as __main__)
and the modules that register handlers share one registry."""

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from covora.jobs.models import Job

if TYPE_CHECKING:
    from covora.services import Services

Handler = Callable[[Job, "Services"], Awaitable[None]]

HANDLERS: dict[str, Handler] = {}


def load_handlers() -> dict[str, Handler]:
    """Import every module that registers handlers, then return the registry."""
    import covora.graphs.jobs  # noqa: F401

    return HANDLERS
