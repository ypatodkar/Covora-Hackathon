import random

from sqlalchemy import func, select

import covora.sim.simulator as sim
from covora.jobs.models import Job
from covora.outreach.models import EmailMessage
from covora.outreach.send import send_due


def test_outcome_rate_matches_profile():
    profile = sim.load_profile("accelerated")
    rng = random.Random(42)
    features = {"function": "operations", "seniority": "manager", "company_size": 18, "length": "short", "cta": "soft"}
    hits = sum(sim.decide_outcome(profile, features, rng) == "interested" for _ in range(10_000))
    assert abs(hits / 10_000 - 0.06 * 2.0 * 1.8) < 0.015


def test_same_prospect_same_outcome():
    from uuid import uuid4

    profile, pid = sim.load_profile("realistic"), uuid4()
    features = {"function": "finance", "seniority": "vp", "company_size": 300, "length": "medium", "cta": "question"}
    assert sim.decide_outcome(profile, features, sim.rng_for(pid, 7)) == sim.decide_outcome(
        profile, features, sim.rng_for(pid, 7)
    )


async def _first_sent(env) -> EmailMessage:
    await send_due(env.services)
    async with env.sessionmaker() as s:
        stmt = select(EmailMessage).where(EmailMessage.campaign_id == env.campaign_id, EmailMessage.status == "sent")
        return (await s.execute(stmt)).scalars().first()


async def test_simulator_ignores_handoff_replies(sending_env):
    email = await _first_sent(sending_env)
    async with sending_env.sessionmaker() as s:
        row = await s.get(EmailMessage, email.id)
        row.kind = "handoff"
        await s.commit()
    assert await sim.simulate_reply(email.id, ctx=sending_env.ctx, services=sending_env.services) is None


async def test_reply_created_and_handling_enqueued(sending_env, monkeypatch):
    monkeypatch.setattr(sim, "decide_outcome", lambda profile, features, rng: "interested")
    email = await _first_sent(sending_env)
    reply_id = await sim.simulate_reply(email.id, ctx=sending_env.ctx, services=sending_env.services)
    async with sending_env.sessionmaker() as s:
        reply = await s.get(EmailMessage, reply_id)
        handles = (
            await s.execute(select(func.count()).select_from(Job).where(Job.kind == "reply.handle"))
        ).scalar_one()
    assert reply.direction == "in" and reply.source == "in_app_sim" and "interesting" in reply.body
    assert reply.prospect_id == email.prospect_id and handles == 1
