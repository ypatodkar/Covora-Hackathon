"""The CoALA decision cycle every model-backed agent step runs (spec §7.1).

observe → retrieve (long-term → working memory) → reason (gateway) → act (caller) → learn (episode).
"""

import math
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel

from covora.config import Settings
from covora.gateway.gateway import GatewayResult, ModelGateway
from covora.gateway.tasks import TaskType
from covora.memory.store import MemoryQuery, MemoryStore, NewMemory, RetrievedMemory
from covora.observability.tracing import RunContext, span

T = TypeVar("T", bound=BaseModel)

DEFAULT_BUDGETS: dict[str, int] = {"episodic": 800, "semantic": 800}


def approx_tokens(text: str) -> int:
    return math.ceil(len(text) / 4)


@dataclass
class WorkingMemory:
    agent: str
    goal: str
    inputs: dict[str, Any]
    memories: list[RetrievedMemory]
    constraints: list[str] = field(default_factory=list)

    def render_memories(self) -> str:
        if not self.memories:
            return "(no relevant memories)"
        sections = []
        episodic = [m for m in self.memories if m.item.kind == "episodic"]
        semantic = [m for m in self.memories if m.item.kind == "semantic"]
        if episodic:
            lines = [f"- [mem:{str(m.item.id)[:8]}] {m.item.summary}" for m in episodic]
            sections.append("Past experience (episodic):\n" + "\n".join(lines))
        if semantic:
            lines = []
            for m in semantic:
                tentative = " (tentative)" if m.item.subtype == "insight" and m.item.evidence_level == "signal" else ""
                lines.append(f"- [mem:{str(m.item.id)[:8]}] {m.item.summary}{tentative}")
            sections.append("Known facts and insights (semantic):\n" + "\n".join(lines))
        return "\n\n".join(sections)

    def manifest(self) -> list[dict[str, Any]]:
        return [
            {
                "id": str(m.item.id),
                "kind": m.item.kind,
                "subtype": m.item.subtype,
                "reason": m.reason,
                "rank": m.rank,
                "score": round(m.score, 4),
            }
            for m in self.memories
        ]


@dataclass
class StepResult(Generic[T]):
    output: T
    working_memory: WorkingMemory
    gateway: GatewayResult[T]
    episode_id: UUID | None
    span_id: UUID


def _fit_to_budgets(found: list[RetrievedMemory], budgets: dict[str, int]) -> list[RetrievedMemory]:
    """Keep the highest-scoring memories of each kind that fit its token budget; drop duplicates."""
    kept: list[RetrievedMemory] = []
    used: dict[str, int] = {}
    seen: set[UUID] = set()
    for m in sorted(found, key=lambda m: m.score, reverse=True):
        if m.item.id in seen:
            continue
        cost = approx_tokens(m.item.summary)
        if used.get(m.item.kind, 0) + cost > budgets.get(m.item.kind, 0):
            continue
        used[m.item.kind] = used.get(m.item.kind, 0) + cost
        seen.add(m.item.id)
        kept.append(m)
    return kept


async def run_step(
    *,
    ctx: RunContext,
    gateway: ModelGateway,
    memory: MemoryStore,
    settings: Settings,
    agent: str,
    task: TaskType,
    goal: str,
    inputs: dict[str, Any],
    queries: list[MemoryQuery],
    build_messages: Callable[[WorkingMemory], list[dict]],
    schema: type[T],
    episode: Callable[[T, WorkingMemory], NewMemory | None] | None = None,
    budgets: dict[str, int] | None = None,
) -> StepResult[T]:
    attrs = {"agent": agent, "task": str(task), "goal": goal, "inputs": sorted(inputs)}
    async with span(ctx, f"{agent}:{task}", "agent", attrs) as sp:
        # Retrieve: long-term memory → working memory, within per-kind budgets.
        enabled = settings.memory_enabled(agent)
        found: list[RetrievedMemory] = []
        if enabled:
            for query in queries:
                found.extend(await memory.retrieve(query, sp.ctx))
        kept = _fit_to_budgets(found, budgets or DEFAULT_BUDGETS)
        await memory.record_reads(sp.id, kept)
        wm = WorkingMemory(agent=agent, goal=goal, inputs=inputs, memories=kept)
        sp.set("memory_enabled", enabled)
        sp.set("working_memory", wm.manifest())

        # Reason.
        result = await gateway.complete(task, build_messages(wm), schema=schema, ctx=sp.ctx)

        # Learn: record what was decided; its outcome is attached later.
        episode_id = None
        if episode is not None:
            new_memory = episode(result.output, wm)
            if new_memory is not None:
                episode_id = await memory.write(new_memory, sp.ctx)
    return StepResult(
        output=result.output, working_memory=wm, gateway=result, episode_id=episode_id, span_id=sp.id
    )
