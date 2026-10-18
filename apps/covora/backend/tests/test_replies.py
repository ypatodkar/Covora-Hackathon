from sqlalchemy import func, select

from covora.memory.models import MemoryItem
from covora.outreach.models import EmailMessage, RepAssignment, SalesRep, Suppression
from covora.qualification.models import Prospect
from covora.replies.backups import activate_due_backups
from covora.replies.handle import handle_reply


async def _add_reps(env, n: int) -> None:
    async with env.sessionmaker() as s:
        for i in range(n):
            s.add(
                SalesRep(
                    workspace_id=env.workspace.id,
                    name=f"Rep {i}",
                    email=f"rep{i}@acme.test",
                    booking_url=f"https://cal.test/rep{i}",
                    active=True,
                )
            )
        await s.commit()


async def _handoffs(env) -> list[EmailMessage]:
    async with env.sessionmaker() as s:
        stmt = select(EmailMessage).where(EmailMessage.campaign_id == env.campaign_id, EmailMessage.kind == "handoff")
        return list((await s.execute(stmt)).scalars())


async def test_interested_hands_off_round_robin_with_booking_link(reply_env):
    await _add_reps(reply_env, 2)
    for pid in reply_env.sent_prospects[:2]:
        email = await reply_env.inbound(pid, "This sounds interesting, happy to chat.")
        assert await handle_reply(email.id, ctx=reply_env.ctx, services=reply_env.services) == "interested"
    handoffs = await _handoffs(reply_env)
    assert len(handoffs) == 2 and {h.cc[0] for h in handoffs} == {"rep0@acme.test", "rep1@acme.test"}
    assert all("https://cal.test/rep" in h.body and h.status == "queued" for h in handoffs)
    async with reply_env.sessionmaker() as s:
        assert (await s.execute(select(func.count()).select_from(RepAssignment))).scalar_one() == 2


async def test_unsubscribe_phrase_overrides_interested_label(reply_env):
    await _add_reps(reply_env, 1)
    pid = reply_env.sent_prospects[0]
    email = await reply_env.inbound(pid, "This sounds interesting, but please unsubscribe me.")
    assert await handle_reply(email.id, ctx=reply_env.ctx, services=reply_env.services) == "unsubscribe"
    assert await _handoffs(reply_env) == []
    async with reply_env.sessionmaker() as s:
        assert (await s.get(Prospect, pid)).status == "suppressed"


async def test_second_interested_reply_takes_no_action(reply_env):
    await _add_reps(reply_env, 1)
    pid = reply_env.sent_prospects[0]
    for _ in range(2):
        email = await reply_env.inbound(pid, "Sounds interesting!")
        await handle_reply(email.id, ctx=reply_env.ctx, services=reply_env.services)
    assert len(await _handoffs(reply_env)) == 1


async def test_interested_without_reps_needs_review(reply_env):
    pid = reply_env.sent_prospects[0]
    email = await reply_env.inbound(pid, "This sounds interesting.")
    await handle_reply(email.id, ctx=reply_env.ctx, services=reply_env.services)
    async with reply_env.sessionmaker() as s:
        assert (await s.get(Prospect, pid)).status == "needs_review"
        assert "sales rep" in (await s.get(EmailMessage, email.id)).error
    assert await _handoffs(reply_env) == []


async def test_wrong_person_activates_backup_once(reply_env):
    pid = reply_env.backup_primary
    for _ in range(2):
        email = await reply_env.inbound(pid, "I'm not the right person for this.")
        await handle_reply(email.id, ctx=reply_env.ctx, services=reply_env.services)
    async with reply_env.sessionmaker() as s:
        backup = (await s.execute(select(Prospect).where(Prospect.id == reply_env.backup_of[pid]))).scalar_one()
        cold = (
            await s.execute(
                select(func.count()).where(EmailMessage.prospect_id == backup.id, EmailMessage.kind == "cold")
            )
        ).scalar_one()
    assert cold == 1


async def test_no_reply_window_activates_backup(reply_env):
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import update

    async with reply_env.sessionmaker() as s:
        old = datetime.now(UTC) - timedelta(hours=2)
        await s.execute(
            update(EmailMessage).where(EmailMessage.campaign_id == reply_env.campaign_id).values(sent_at=old)
        )
        await s.commit()
    assert await activate_due_backups(reply_env.services) >= 1


async def test_outcome_written_to_memory(reply_env):
    await _add_reps(reply_env, 1)
    email = await reply_env.inbound(reply_env.sent_prospects[0], "This sounds interesting.")
    await handle_reply(email.id, ctx=reply_env.ctx, services=reply_env.services)
    async with reply_env.sessionmaker() as s:
        n = (await s.execute(select(func.count()).where(MemoryItem.subtype == "outreach_episode"))).scalar_one()
    assert n == 1
    _ = Suppression
