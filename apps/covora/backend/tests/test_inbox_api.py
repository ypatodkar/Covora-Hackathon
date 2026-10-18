from covora.outreach.models import EmailMessage
from covora.outreach.suppression import suppress
from covora.qualification.models import Contact, Prospect
from covora.replies.handle import handle_reply


async def _reply(env, prospect_id, body):
    email = await env.inbound(prospect_id, body)
    await handle_reply(email.id, ctx=env.ctx, services=env.services)
    return email


async def test_threads_filters(api, reply_env):
    a, b = reply_env.sent_prospects[:2]
    await _reply(reply_env, a, "Sounds interesting, happy to chat")
    await _reply(reply_env, b, "hmm")
    rows = (await api.get("/api/inbox/threads")).json()
    assert len(rows) >= len(reply_env.sent_prospects)
    assert {"prospect_id", "contact", "company", "last_message_at", "last_label", "status", "simulated"} <= set(rows[0])
    interested = (await api.get("/api/inbox/threads?filter=interested")).json()
    assert [r["prospect_id"] for r in interested] == [str(a)]
    review = (await api.get("/api/inbox/threads?filter=needs_review")).json()
    assert str(b) in [r["prospect_id"] for r in review]


async def test_thread_detail_shows_simulated_delivery(api, reply_env):
    pid = reply_env.sent_prospects[0]
    await _reply(reply_env, pid, "Sounds interesting, happy to chat")
    detail = (await api.get(f"/api/inbox/threads/{pid}")).json()
    cold = next(m for m in detail["messages"] if m["kind"] == "cold")
    assert cold["delivery"] == "in_app" and cold["actual_to"] == "in-app"
    inbound = next(m for m in detail["messages"] if m["direction"] == "in")
    assert inbound["label"] == "interested"
    assert detail["contact"]["full_name"] and detail["company"]["name"]


async def test_manual_reply_queued(api, reply_env):
    pid = reply_env.sent_prospects[0]
    r = await api.post(f"/api/inbox/threads/{pid}/reply", json={"body": "Thanks, talk soon."})
    assert r.status_code == 200, r.text
    async with reply_env.sessionmaker() as s:
        from sqlalchemy import select

        rows = list(
            (
                await s.execute(
                    select(EmailMessage).where(EmailMessage.prospect_id == pid, EmailMessage.kind == "manual_reply")
                )
            ).scalars()
        )
    assert len(rows) == 1 and rows[0].status == "queued" and "unsubscribe" in rows[0].body


async def test_reply_to_suppressed_409(api, reply_env):
    pid = reply_env.sent_prospects[0]
    async with reply_env.sessionmaker() as s:
        prospect = await s.get(Prospect, pid)
        contact = await s.get(Contact, prospect.contact_id)
        from covora.campaigns.models import Campaign

        ws_id = (await s.get(Campaign, prospect.campaign_id)).workspace_id
        if not contact.email:
            contact.email = "someone@example.test"
        await suppress(s, ws_id, contact.email, "unsubscribe")
        await s.commit()
    r = await api.post(f"/api/inbox/threads/{pid}/reply", json={"body": "hello"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "suppressed"


async def test_mark_meeting(api, reply_env):
    pid = reply_env.sent_prospects[0]
    r = await api.post(f"/api/prospects/{pid}/meeting")
    assert r.status_code == 200
    async with reply_env.sessionmaker() as s:
        assert (await s.get(Prospect, pid)).meeting_booked_at is not None
