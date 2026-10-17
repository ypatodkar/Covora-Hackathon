"""ICP planning agent: vibe prompt → structured ICP + buyer map (spec §9.1), via the decision cycle."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from covora.agents.step import StepResult, WorkingMemory, run_step
from covora.config import Settings
from covora.gateway.gateway import ModelGateway
from covora.gateway.tasks import TaskType
from covora.icp.schemas import StructuredICP
from covora.memory.prompts import get_prompt, render_prompt
from covora.memory.store import MemoryQuery, MemoryStore
from covora.observability.tracing import RunContext
from covora.workspace.models import Workspace

AGENT = "icp"
GOAL = "Turn the user's description of ideal customers into a structured ICP with a buyer map"
_OFFERING_LABELS = {
    "sales_call": "a product or service that needs a sales call",
    "dealer": "a bulk product for dealers",
}


def _format_profile(profile: dict) -> str:
    lines = [f"Company: {profile['name']}"]
    if profile["description"]:
        lines.append(f"What they sell: {profile['description']}")
    if profile["value_props"]:
        lines.append("Proof points: " + "; ".join(profile["value_props"]))
    lines.append(f"Offering: {_OFFERING_LABELS.get(profile['offering_type'], profile['offering_type'])}")
    return "\n".join(lines)


async def parse_icp(
    prompt_text: str,
    *,
    ctx: RunContext,
    gateway: ModelGateway,
    memory: MemoryStore,
    settings: Settings,
    session: AsyncSession,
) -> StepResult[StructuredICP]:
    ws = (await session.execute(select(Workspace).where(Workspace.id == ctx.workspace_id))).scalar_one()
    profile = {
        "name": ws.name,
        "description": ws.description or "",
        "value_props": list(ws.value_props or []),
        "offering_type": ws.offering_type,
    }
    prompt = await get_prompt(session, "icp_parsing")

    def build_messages(wm: WorkingMemory) -> list[dict]:
        system = render_prompt(prompt.body, company_profile=_format_profile(profile), memories=wm.render_memories())
        return [{"role": "system", "content": system}, {"role": "user", "content": prompt_text}]

    return await run_step(
        ctx=ctx,
        gateway=gateway,
        memory=memory,
        settings=settings,
        agent=AGENT,
        task=TaskType.icp_parsing,
        goal=GOAL,
        inputs={"prompt_text": prompt_text, "company_profile": profile},
        queries=[
            MemoryQuery("episodic", ["icp_edit"], "real", prompt_text, "past ICP corrections by the user", k=5),
            MemoryQuery(
                "semantic", ["insight"], "real", prompt_text, "segment insights", filters={"dimension": "segment"}, k=3
            ),
        ],
        build_messages=build_messages,
        schema=StructuredICP,
    )
