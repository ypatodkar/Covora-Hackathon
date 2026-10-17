from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from covora.config import Settings


def checkpointer_url(database_url: str) -> str:
    """psycopg URL for LangGraph's checkpointer, with its tables in the `langgraph` schema."""
    url = database_url.replace("postgresql+psycopg://", "postgresql://", 1)
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}options=-csearch_path%3Dlanggraph"


@asynccontextmanager
async def open_checkpointer(settings: Settings) -> AsyncIterator[AsyncPostgresSaver]:
    async with AsyncPostgresSaver.from_conn_string(checkpointer_url(settings.database_url)) as checkpointer:
        yield checkpointer


async def ensure_checkpointer_tables(settings: Settings) -> None:
    """Create LangGraph's checkpoint tables. Call once at process start, never inside a job:
    setup() uses CREATE INDEX CONCURRENTLY, which waits for every open transaction in the database."""
    async with AsyncPostgresSaver.from_conn_string(checkpointer_url(settings.database_url)) as checkpointer:
        await checkpointer.setup()
