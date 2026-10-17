from covora.qualification.people import find_people
from covora.qualification.validate import classify_email
from tests.helpers import contacts_by_name


async def test_finds_named_people_with_sources(people_env):
    counts = await find_people(
        people_env.campaign_id, people_env.qualified_ids, ctx=people_env.ctx, services=people_env.services
    )
    contacts = await contacts_by_name(people_env.sessionmaker, people_env.workspace.id, "ohio-precision.test")
    assert {"Dana Ruiz", "Mark Ellison"} <= set(contacts)
    assert counts[people_env.company_id("ohio-precision.test")] >= 2


async def test_person_not_in_source_dropped(people_env):
    await find_people(
        people_env.campaign_id, people_env.qualified_ids, ctx=people_env.ctx, services=people_env.services
    )
    contacts = await contacts_by_name(people_env.sessionmaker, people_env.workspace.id, "ohio-precision.test")
    assert "Zed Phantom" not in contacts


async def test_email_not_in_source_not_recorded(people_env):
    await find_people(
        people_env.campaign_id, people_env.qualified_ids, ctx=people_env.ctx, services=people_env.services
    )
    c = await contacts_by_name(people_env.sessionmaker, people_env.workspace.id, "ohio-precision.test")
    assert (c["Mark Ellison"].email, c["Mark Ellison"].email_status) == (None, "missing")
    assert (c["Dana Ruiz"].email, c["Dana Ruiz"].email_status) == ("dana.ruiz@ohio-precision.test", "verified")
    assert c["Dana Ruiz"].linkedin_url == "https://www.linkedin.com/in/dana-ruiz-ops"


def test_classify_email_rules():
    text = "Dana Ruiz, Operations. dana.ruiz@x.test · info@x.test"
    assert classify_email("info@x.test", "Dana Ruiz", text) == ("info@x.test", "unverified")
    assert classify_email("dana.ruiz@x.test", "Dana Ruiz", text) == ("dana.ruiz@x.test", "verified")
    assert classify_email("dr@x.test", "Dana Ruiz", text) == (None, "missing")
