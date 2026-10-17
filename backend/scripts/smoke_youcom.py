"""Live check of the You.com setup: search, contents, and whether `site:` filters are honored.

Run from backend/:  uv run python scripts/smoke_youcom.py
Costs about $0.016 of You.com credit. Exits 0 only when search and contents work. Never prints the key.
"""

import asyncio
import sys

from covora.config import get_settings
from covora.db.session import make_engine, make_sessionmaker
from covora.observability.redaction import redact
from covora.observability.tracing import finish_run, start_run
from covora.research.budget import spend
from covora.research.youcom import YouComProvider
from covora.workspace.service import ensure_workspace


async def main() -> int:
    settings = get_settings()
    if not settings.ydc_api_key:
        print("FAIL YDC_API_KEY is not set in .env")
        return 1
    engine = make_engine(settings.database_url)
    sessionmaker = make_sessionmaker(engine)
    async with sessionmaker() as session:
        workspace = await ensure_workspace(session)
    ctx = await start_run(sessionmaker, kind="eval", workspace_id=workspace.id, secrets=settings.secret_values())
    provider = YouComProvider(settings, sessionmaker)
    ok = True
    try:
        results = await provider.search("metal fabrication companies Dayton Ohio", count=5, ctx=ctx)
        print(f"OK search n={len(results)}" if results else "FAIL search returned nothing")
        ok = ok and bool(results)
        for r in results[:3]:
            print(f"   {r.url}  |  {r.title[:70]}")
        if results:
            pages = await provider.contents([results[0].url], ctx=ctx)
            chars = sum(len(p.markdown) for p in pages)
            print(f"OK contents chars={chars}" if chars else "FAIL contents returned no text")
            ok = ok and chars > 0
        people = await provider.search("site:linkedin.com/in operations manager manufacturing Ohio", count=5, ctx=ctx)
        honored = bool(people) and all("linkedin.com" in r.url for r in people)
        print(f"site-operator: {'honored' if honored else 'ignored'} ({len(people)} results)")
    except Exception as exc:
        ok = False
        print(f"FAIL {redact(str(exc), settings.secret_values())[:300]}")
    finally:
        await finish_run(ctx, status="succeeded" if ok else "failed")
        print(f"spend so far: ${await spend(sessionmaker, workspace.id):.4f}")
        await engine.dispose()
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
