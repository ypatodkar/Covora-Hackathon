"""The campaign pipeline as a checkpointed LangGraph graph (spec §8.1).

discover_companies ⇄ score_companies (waves) → find_people → select_contacts
State holds only ids and control values; the database is the source of truth.
"""

import math
from typing import Literal, TypedDict
from uuid import UUID

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt
from sqlalchemy import func, select

from covora.campaigns.models import Campaign
from covora.discovery.discover import discover_wave
from covora.discovery.enrich import enrich_and_score
from covora.discovery.models import CampaignCompany
from covora.observability.tracing import RunContext, span
from covora.outreach.flow import draft_batch, primaries_in_order, queue_drafts, release, set_arms
from covora.qualification.people import find_people
from covora.qualification.select import select_contacts
from covora.research.provider import BudgetExceeded
from covora.services import Services

StopReason = Literal["enough_qualified", "max_waves", "budget", "no_new_companies"]


class CampaignState(TypedDict, total=False):
    campaign_id: str
    wave: int
    stop_reason: str | None
    next: str
    approval: dict | None
    has_drafts: bool


def stop_reason_for(
    state: CampaignState,
    *,
    qualified: int,
    target_companies: int,
    max_waves: int,
    new_last_wave: int,
    new_prev_wave: int | None,
) -> StopReason | None:
    if state.get("stop_reason"):
        return state["stop_reason"]
    if qualified >= target_companies:
        return "enough_qualified"
    if state["wave"] >= max_waves:
        return "max_waves"
    if new_prev_wave is not None and new_last_wave == 0 and new_prev_wave == 0:
        return "no_new_companies"
    return None


def wave_candidate_limit(*, target_companies: int, qualified: int, cap: int) -> int:
    """New candidates worth scoring this wave: about twice what's still needed (the cost model's margin)."""
    return min(cap, max(5, 2 * (target_companies - qualified)))


def route_after_scoring(state: CampaignState, **kw) -> Literal["discover_companies", "find_people"]:
    return "find_people" if stop_reason_for(state, **kw) else "discover_companies"


def _ctx(config: RunnableConfig, services: Services) -> RunContext:
    cfg = config["configurable"]
    return RunContext(
        run_id=UUID(cfg["run_id"]),
        trace_id=cfg["trace_id"],
        workspace_id=UUID(cfg["workspace_id"]),
        span_id=None,
        sessionmaker=services.sessionmaker,
        secrets=services.settings.secret_values(),
    )


async def _ids(services: Services, campaign_id: UUID, *statuses: str) -> list[UUID]:
    async with services.sessionmaker() as s:
        stmt = select(CampaignCompany.company_id).where(
            CampaignCompany.campaign_id == campaign_id, CampaignCompany.status.in_(statuses)
        )
        return list((await s.execute(stmt)).scalars())


async def _wave_count(services: Services, campaign_id: UUID, wave: int) -> int:
    async with services.sessionmaker() as s:
        stmt = select(func.count()).where(CampaignCompany.campaign_id == campaign_id, CampaignCompany.wave == wave)
        return (await s.execute(stmt)).scalar_one()


async def _first_batch_size(services: Services, campaign_id: UUID) -> int:
    from covora.workspace.models import Workspace
    from covora.workspace.settings import get_workspace_settings

    async with services.sessionmaker() as s:
        campaign = await s.get(Campaign, campaign_id)
        return get_workspace_settings(await s.get(Workspace, campaign.workspace_id)).sending.first_batch_size


async def _save_stop(services: Services, campaign_id: UUID, reason: str) -> None:
    async with services.sessionmaker() as s:
        campaign = await s.get(Campaign, campaign_id)
        campaign.progress = {**campaign.progress, "stop_reason": reason}
        await s.commit()


def build_campaign_graph(services: Services, checkpointer):
    async def discover_companies(state: CampaignState, config: RunnableConfig) -> dict:
        wave = state["wave"] + 1
        stop = state.get("stop_reason")
        campaign_id = UUID(state["campaign_id"])
        async with services.sessionmaker() as s:
            target = (await s.get(Campaign, campaign_id)).target_prospects
        limit = wave_candidate_limit(
            target_companies=math.ceil(target * services.settings.contact_yield_buffer),
            qualified=len(await _ids(services, campaign_id, "qualified")),
            cap=services.settings.max_candidates_per_wave,
        )
        async with span(_ctx(config, services), "discover_companies", "stage", {"wave": wave, "limit": limit}) as sp:
            try:
                result = await discover_wave(campaign_id, wave=wave, ctx=sp.ctx, services=services, limit=limit)
                sp.set("new_companies", len(result.new_company_ids))
                sp.set("queries", result.queries)
            except BudgetExceeded:
                stop = "budget"
                sp.set("stop_reason", stop)
        return {"wave": wave, "stop_reason": stop}

    async def score_companies(state: CampaignState, config: RunnableConfig) -> dict:
        campaign_id = UUID(state["campaign_id"])
        stop = state.get("stop_reason")
        async with span(_ctx(config, services), "score_companies", "stage", {"wave": state["wave"]}) as sp:
            if stop is None:
                try:
                    await enrich_and_score(
                        campaign_id, await _ids(services, campaign_id, "candidate"), ctx=sp.ctx, services=services
                    )
                except BudgetExceeded:
                    stop = "budget"
            async with services.sessionmaker() as s:
                target = (await s.get(Campaign, campaign_id)).target_prospects
            reason = stop_reason_for(
                {**state, "stop_reason": stop},
                qualified=len(await _ids(services, campaign_id, "qualified")),
                target_companies=math.ceil(target * services.settings.contact_yield_buffer),
                max_waves=services.settings.max_waves,
                new_last_wave=await _wave_count(services, campaign_id, state["wave"]),
                new_prev_wave=await _wave_count(services, campaign_id, state["wave"] - 1)
                if state["wave"] > 1
                else None,
            )
            if reason:
                await _save_stop(services, campaign_id, reason)
                sp.set("stop_reason", reason)
        return {"stop_reason": reason, "next": "find_people" if reason else "discover_companies"}

    async def find_people_node(state: CampaignState, config: RunnableConfig) -> dict:
        campaign_id = UUID(state["campaign_id"])
        stop = state.get("stop_reason")
        async with span(_ctx(config, services), "find_people", "stage") as sp:
            try:
                await find_people(
                    campaign_id, await _ids(services, campaign_id, "qualified"), ctx=sp.ctx, services=services
                )
            except BudgetExceeded:
                if stop != "budget":
                    stop = "budget"
                    await _save_stop(services, campaign_id, stop)
                sp.set("stop_reason", stop)
        return {"stop_reason": stop}

    async def select_contacts_node(state: CampaignState, config: RunnableConfig) -> dict:
        campaign_id = UUID(state["campaign_id"])
        async with span(_ctx(config, services), "select_contacts", "stage") as sp:
            picked = await select_contacts(
                campaign_id, await _ids(services, campaign_id, "qualified"), ctx=sp.ctx, services=services
            )
            sp.set("prospects", picked)
        return {}

    async def assign_arms(state: CampaignState, config: RunnableConfig) -> dict:
        async with span(_ctx(config, services), "assign_arms", "stage") as sp:
            sp.set("prospects", await set_arms(services, UUID(state["campaign_id"])))
        return {}

    async def draft_first_batch(state: CampaignState, config: RunnableConfig) -> dict:
        campaign_id = UUID(state["campaign_id"])
        async with span(_ctx(config, services), "draft_first_batch", "stage") as sp:
            order = await primaries_in_order(services, campaign_id)
            batch = order[: await _first_batch_size(services, campaign_id)]
            drafted = await draft_batch(services, batch, ctx=sp.ctx)
            sp.set("drafts", len(drafted))
        return {"has_drafts": bool(batch)}

    async def approval(state: CampaignState, config: RunnableConfig) -> dict:
        # Pauses the graph; the API resumes it with {"approved": [...], "rejected": [...]}.
        decision = interrupt({"campaign_id": state["campaign_id"]})
        return {"approval": decision}

    async def release_batch(state: CampaignState, config: RunnableConfig) -> dict:
        async with span(_ctx(config, services), "release_batch", "stage") as sp:
            counts = await release(services, UUID(state["campaign_id"]), state.get("approval") or {})
            sp.set("released", counts)
        return {}

    async def draft_remaining(state: CampaignState, config: RunnableConfig) -> dict:
        campaign_id = UUID(state["campaign_id"])
        async with span(_ctx(config, services), "draft_remaining", "stage") as sp:
            drafted = await draft_batch(services, await primaries_in_order(services, campaign_id), ctx=sp.ctx)
            sp.set("drafts", len(drafted))
            sp.set("queued", await queue_drafts(services, campaign_id))
        return {}

    graph = StateGraph(CampaignState)
    graph.add_node("discover_companies", discover_companies)
    graph.add_node("score_companies", score_companies)
    graph.add_node("find_people", find_people_node)
    graph.add_node("select_contacts", select_contacts_node)
    graph.add_edge(START, "discover_companies")
    graph.add_edge("discover_companies", "score_companies")
    graph.add_conditional_edges(
        "score_companies",
        lambda state: state["next"],
        {"discover_companies": "discover_companies", "find_people": "find_people"},
    )
    graph.add_node("assign_arms", assign_arms)
    graph.add_node("draft_first_batch", draft_first_batch)
    graph.add_node("approval", approval)
    graph.add_node("release_batch", release_batch)
    graph.add_node("draft_remaining", draft_remaining)
    graph.add_edge("find_people", "select_contacts")
    graph.add_edge("select_contacts", "assign_arms")
    graph.add_edge("assign_arms", "draft_first_batch")
    graph.add_conditional_edges(
        "draft_first_batch",
        lambda state: "approval" if state.get("has_drafts") else END,
        {"approval": "approval", END: END},
    )
    graph.add_edge("approval", "release_batch")
    graph.add_edge("release_batch", "draft_remaining")
    graph.add_edge("draft_remaining", END)
    return graph.compile(checkpointer=checkpointer)
