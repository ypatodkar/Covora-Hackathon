import asyncio

from sqlalchemy import func, select, update

from covora.jobs.models import Job
from covora.outreach.models import EmailMessage
from covora.outreach.send import send_due
from covora.outreach.suppression import suppress


async def _emails(env):
    async with env.sessionmaker() as s:
        stmt = select(EmailMessage).where(EmailMessage.campaign_id == env.campaign_id, EmailMessage.kind == "cold")
        return list((await s.execute(stmt)).scalars())


async def _sim_jobs(env) -> int:
    async with env.sessionmaker() as s:
        return (await s.execute(select(func.count()).select_from(Job).where(Job.kind == "sim.reply"))).scalar_one()


async def test_send_due_delivers_in_app_and_schedules_sim_reply(sending_env):
    sent = await send_due(sending_env.services)
    emails = await _emails(sending_env)
    assert sent == len(emails) and all(e.status == "sent" and e.delivery == "in_app" for e in emails)
    assert await _sim_jobs(sending_env) == sent


async def test_suppressed_recipient_not_sent(sending_env):
    target = (await _emails(sending_env))[0]
    async with sending_env.sessionmaker() as s:
        await s.execute(update(EmailMessage).where(EmailMessage.id == target.id).values(intended_to="Blocked@X.test"))
        await s.commit()
        await suppress(s, sending_env.workspace.id, "blocked@x.test", "unsubscribe")
    await send_due(sending_env.services)
    async with sending_env.sessionmaker() as s:
        assert (await s.get(EmailMessage, target.id)).status == "suppressed"


async def test_send_is_idempotent_under_concurrency(sending_env):
    a, b = await asyncio.gather(send_due(sending_env.services), send_due(sending_env.services))
    emails = await _emails(sending_env)
    assert a + b == len(emails) and await _sim_jobs(sending_env) == len(emails)


async def test_campaign_completes_when_queue_empty(sending_env):
    await send_due(sending_env.services)
    assert (await sending_env.campaign()).status == "complete"


async def test_actual_to_never_intended_address(sending_env):
    await send_due(sending_env.services)
    assert all(e.actual_to == "in-app" for e in await _emails(sending_env))
