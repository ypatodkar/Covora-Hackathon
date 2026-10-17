"""CoALA long-term memory: write, retrieve, supersede, attach outcomes (spec §7.2–7.4)."""

from dataclasses import dataclass, field
from typing import Literal
from uuid import UUID

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from covora.gateway.gateway import ModelGateway
from covora.memory.models import MemoryItem, MemoryRead
from covora.observability.tracing import RunContext, span

Kind = Literal["episodic", "semantic"]
Source = Literal["research", "gmail_sim", "in_app_sim", "mock_sim"]
Scope = Literal["real", "mock"]
EvidenceLevel = Literal["evidence", "signal", "assumption"]

# Memories from mock-prospect simulation never mix with memories about real-researched prospects.
SCOPE_SOURCES: dict[str, tuple[str, ...]] = {
    "real": ("research", "gmail_sim", "in_app_sim"),
    "mock": ("mock_sim",),
}
RETRIEVABLE_EVIDENCE = ("evidence", "signal")


@dataclass
class NewMemory:
    kind: Kind
    subtype: str
    source: Source
    summary: str
    payload: dict
    source_refs: list[dict]
    evidence_level: EvidenceLevel | None = None


@dataclass
class MemoryQuery:
    kind: Kind
    subtypes: list[str]
    scope: Scope
    text: str
    reason: str
    filters: dict = field(default_factory=dict)
    k: int = 5


@dataclass
class RetrievedMemory:
    item: MemoryItem
    score: float
    rank: int
    reason: str


class MemoryStore:
    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession], gateway: ModelGateway) -> None:
        self._sessionmaker = sessionmaker
        self._gateway = gateway

    async def write(self, mem: NewMemory, ctx: RunContext) -> UUID:
        if mem.subtype == "insight":
            if mem.kind != "semantic":
                raise ValueError("insights are semantic memory")
            if mem.evidence_level not in RETRIEVABLE_EVIDENCE:
                raise ValueError("only evidence- or signal-level insights are stored; assumptions are not")
        attrs = {"kind": mem.kind, "subtype": mem.subtype, "source": mem.source}
        async with span(ctx, f"memory.write:{mem.subtype}", "memory", attrs) as sp:
            [vector] = await self._gateway.embed([mem.summary], ctx=sp.ctx, input_type="passage")
            item = MemoryItem(
                workspace_id=ctx.workspace_id,
                kind=mem.kind,
                subtype=mem.subtype,
                source=mem.source,
                summary=mem.summary,
                payload=mem.payload,
                source_refs=mem.source_refs,
                evidence_level=mem.evidence_level,
                embedding=vector,
            )
            async with self._sessionmaker() as s:
                s.add(item)
                await s.commit()
            sp.set("memory_item_id", str(item.id))
        return item.id

    async def attach_outcome(self, item_id: UUID, outcome: dict, ctx: RunContext) -> None:
        """Episodic memory is append-only: an outcome can be attached once and never changed."""
        async with self._sessionmaker() as s:
            updated = await s.execute(
                update(MemoryItem)
                .where(MemoryItem.id == item_id, MemoryItem.outcome.is_(None))
                .values(outcome=outcome)
                .returning(MemoryItem.id)
            )
            if updated.scalar_one_or_none() is None:
                raise ValueError(f"memory {item_id} is missing or already has an outcome")
            await s.commit()

    async def supersede(self, old_id: UUID, new_id: UUID, ctx: RunContext) -> None:
        async with self._sessionmaker() as s:
            await s.execute(update(MemoryItem).where(MemoryItem.id == old_id).values(superseded_by=new_id))
            await s.commit()

    async def retrieve(self, q: MemoryQuery, ctx: RunContext) -> list[RetrievedMemory]:
        attrs = {"subtypes": q.subtypes, "scope": q.scope, "reason": q.reason, "k": q.k}
        async with span(ctx, f"memory.retrieve:{q.kind}", "memory", attrs) as sp:
            [query_vector] = await self._gateway.embed([q.text], ctx=sp.ctx, input_type="query")
            distance = MemoryItem.embedding.cosine_distance(query_vector).label("distance")
            stmt = select(MemoryItem, distance).where(
                MemoryItem.workspace_id == ctx.workspace_id,
                MemoryItem.kind == q.kind,
                MemoryItem.subtype.in_(q.subtypes),
                MemoryItem.source.in_(SCOPE_SOURCES[q.scope]),
                MemoryItem.superseded_by.is_(None),
                or_(MemoryItem.subtype != "insight", MemoryItem.evidence_level.in_(RETRIEVABLE_EVIDENCE)),
            )
            if q.filters:
                stmt = stmt.where(MemoryItem.payload.contains(q.filters))
            stmt = stmt.order_by(distance).limit(q.k)
            async with self._sessionmaker() as s:
                rows = (await s.execute(stmt)).all()
            found = [
                RetrievedMemory(item=item, score=1 - float(dist), rank=i + 1, reason=q.reason)
                for i, (item, dist) in enumerate(rows)
            ]
            sp.set("count", len(found))
        return found

    async def record_reads(self, span_id: UUID, retrieved: list[RetrievedMemory]) -> None:
        if not retrieved:
            return
        async with self._sessionmaker() as s:
            s.add_all(
                MemoryRead(span_id=span_id, memory_item_id=r.item.id, reason=r.reason, rank=r.rank) for r in retrieved
            )
            await s.commit()
