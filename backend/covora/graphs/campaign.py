"""The campaign pipeline as a checkpointed LangGraph graph (spec §8.1).

discover_companies ⇄ score_companies (waves) → find_people → select_contacts
State holds only ids and control values; the database is the source of truth.
"""

import math
from typing import Literal, TypedDict
from uuid import UUID

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from sqlalchemy import func, select

from covora.campaigns.models import Campaign
from covora.discovery.discover import discover_wave
from covora.discovery.enrich import enrich_and_score
from covora.discovery.models import CampaignCompany
from covora.observability.tracing import RunContext, span
from covora.qualification.people import find_people
from covora.qualification.select import select_contacts
from covora.research.provider import BudgetExceeded
from covora.services import Services

StopReason = Literal["enough_qualified", "max_waves", "budget", "no_new_companies"]


class CampaignState(TypedDict):
    campaign_id: str
    wave: int
    stop_reason: str | None
    next: str


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


async def _save_stop(services: Services, campaign_id: UUID, reason: str) -> None:
    async with services.sessionmaker() as s:
        campaign = await s.get(Campaign, campaign_id)
        campaign.progress = {**campaign.progress, "stop_reason": reason}
        await s.commit()


def build_campaign_graph(services: Services, checkpointer):
    async def discover_companies(state: CampaignState, config: RunnableConfig) -> dict:
        wave = state["wave"] + 1
        stop = state.get("stop_reason")
        async with span(_ctx(config, services), "discover_companies", "stage", {"wave": wave}) as sp:
            try:
                result = await discover_wave(UUID(state["campaign_id"]), wave=wave, ctx=sp.ctx, services=services)
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
    graph.add_edge("find_people", "select_contacts")
    graph.add_edge("select_contacts", END)
    return graph.compile(checkpointer=checkpointer)
