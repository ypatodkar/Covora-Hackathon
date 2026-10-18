"""Job handler that runs (or resumes) a campaign's graph."""

from uuid import UUID

from langgraph.types import Command
from sqlalchemy import update

from covora.campaigns.models import Campaign
from covora.graphs.campaign import build_campaign_graph
from covora.graphs.checkpointer import open_checkpointer
from covora.jobs.models import Job
from covora.jobs.registry import HANDLERS
from covora.observability.models import WorkflowRun
from covora.observability.redaction import redact
from covora.observability.tracing import finish_run, start_run
from covora.outreach.flow import status_after_release
from covora.services import Services

JOB_KIND = "campaign.run"


def thread_id_for(campaign_id: UUID) -> str:
    return f"campaign-{campaign_id}"


async def _set_campaign(services: Services, campaign_id: UUID, **values) -> None:
    async with services.sessionmaker() as s:
        await s.execute(update(Campaign).where(Campaign.id == campaign_id).values(**values))
        await s.commit()


async def run_campaign_job(job: Job, services: Services) -> None:
    campaign_id = UUID(job.payload["campaign_id"])
    resume = bool(job.payload.get("resume"))
    async with services.sessionmaker() as s:
        workspace_id = (await s.get(Campaign, campaign_id)).workspace_id
    await _set_campaign(services, campaign_id, status="running", last_error=None)
    ctx = await start_run(
        services.sessionmaker,
        kind="campaign",
        workspace_id=workspace_id,
        secrets=services.settings.secret_values(),
        campaign_id=campaign_id,
    )
    thread_id = thread_id_for(campaign_id)
    async with services.sessionmaker() as s:
        await s.execute(update(WorkflowRun).where(WorkflowRun.id == ctx.run_id).values(thread_id=thread_id))
        await s.commit()
    config = {
        "configurable": {
            "thread_id": thread_id,
            "run_id": str(ctx.run_id),
            "trace_id": ctx.trace_id,
            "workspace_id": str(workspace_id),
        }
    }
    resume_value = job.payload.get("resume_value")
    if resume_value is not None:
        graph_input = Command(resume=resume_value)
    elif resume:
        graph_input = None
    else:
        graph_input = {"campaign_id": str(campaign_id), "wave": 0, "stop_reason": None, "next": ""}
    try:
        async with open_checkpointer(services.settings) as checkpointer:
            result = await build_campaign_graph(services, checkpointer).ainvoke(graph_input, config)
    except Exception as exc:
        message = redact(f"{type(exc).__name__}: {exc}", services.settings.secret_values())[:2000]
        await finish_run(ctx, status="failed", error=message)
        await _set_campaign(services, campaign_id, status="failed", last_error=message)
        raise
    await finish_run(ctx, status="succeeded")
    if isinstance(result, dict) and result.get("__interrupt__"):
        await _set_campaign(services, campaign_id, status="awaiting_approval")
    else:
        await _set_campaign(services, campaign_id, status=await status_after_release(services, campaign_id))


HANDLERS[JOB_KIND] = run_campaign_job
