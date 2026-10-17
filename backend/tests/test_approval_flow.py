from sqlalchemy import func, select

from covora.graphs.jobs import run_campaign_job
from covora.outreach.models import EmailMessage


async def _emails(env, **where):
    async with env.sessionmaker() as s:
        stmt = select(EmailMessage).where(EmailMessage.campaign_id == env.campaign_id)
        for key, value in where.items():
            stmt = stmt.where(getattr(EmailMessage, key) == value)
        return list((await s.execute(stmt)).scalars())


async def test_pipeline_pauses_for_approval_with_first_batch(flow_env):
    await flow_env.set_first_batch(1)
    await run_campaign_job(flow_env.job(resume=False), flow_env.services)
    assert (await flow_env.campaign()).status == "awaiting_approval"
    drafts = await _emails(flow_env, kind="cold")
    assert len(drafts) == 1 and drafts[0].status == "draft"


async def test_approve_releases_and_drafts_remaining(flow_env):
    await flow_env.set_first_batch(1)
    await run_campaign_job(flow_env.job(resume=False), flow_env.services)
    first = (await _emails(flow_env, kind="cold"))[0]
    await run_campaign_job(flow_env.resume_job({"approved": [str(first.id)], "rejected": []}), flow_env.services)
    assert (await flow_env.campaign()).status == "sending"
    queued = await _emails(flow_env, kind="cold", status="queued")
    assert first.id in {e.id for e in queued} and len(queued) >= 3


async def test_reject_skips_prospect(flow_env):
    await run_campaign_job(flow_env.job(resume=False), flow_env.services)
    drafts = await _emails(flow_env, kind="cold")
    rejected = drafts[0]
    approved = [str(d.id) for d in drafts[1:]]
    await run_campaign_job(
        flow_env.resume_job({"approved": approved, "rejected": [str(rejected.id)]}), flow_env.services
    )
    from covora.qualification.models import Prospect

    async with flow_env.sessionmaker() as s:
        assert (await s.get(EmailMessage, rejected.id)).status == "rejected"
        assert (await s.get(Prospect, rejected.prospect_id)).status == "skipped"


async def test_approve_requires_awaiting_approval(api, draft_campaign_id):
    body = {"approved": [], "rejected": []}
    assert (await api.post(f"/api/campaigns/{draft_campaign_id}/approve", json=body)).status_code == 409


async def test_draft_edit_writes_user_correction(api, flow_env):
    await run_campaign_job(flow_env.job(resume=False), flow_env.services)
    draft = (await _emails(flow_env, kind="cold"))[0]
    r = await api.patch(f"/api/emails/{draft.id}", json={"subject": "Shorter subject", "body": "Hi Dana, short note."})
    assert r.status_code == 200 and r.json()["subject"] == "Shorter subject"
    from covora.memory.models import MemoryItem

    async with flow_env.sessionmaker() as s:
        count = (await s.execute(select(func.count()).where(MemoryItem.subtype == "user_correction"))).scalar_one()
    assert count == 1
    review = (await api.get(f"/api/campaigns/{flow_env.campaign_id}/review")).json()
    assert any(d["id"] == str(draft.id) for d in review)
