import hashlib
import json
from datetime import UTC, datetime, timedelta

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from covora.research.models import SearchCache


def cache_key(endpoint: str, params: dict) -> str:
    canonical = json.dumps(params, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(f"{endpoint}|{canonical}".encode()).hexdigest()


async def get_cached(
    sessionmaker: async_sessionmaker[AsyncSession], key: str, *, ttl_days: float
) -> dict | list | None:
    async with sessionmaker() as s:
        row = await s.get(SearchCache, key)
    if row is None or row.created_at < datetime.now(UTC) - timedelta(days=ttl_days):
        return None
    return row.response


async def put_cached(
    sessionmaker: async_sessionmaker[AsyncSession], key: str, endpoint: str, params: dict, response: dict | list
) -> None:
    stmt = insert(SearchCache).values(key=key, endpoint=endpoint, params=params, response=response)
    stmt = stmt.on_conflict_do_update(
        index_elements=["key"], set_={"response": response, "params": params, "created_at": datetime.now(UTC)}
    )
    async with sessionmaker() as s:
        await s.execute(stmt)
        await s.commit()
