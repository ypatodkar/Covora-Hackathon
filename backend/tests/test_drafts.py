from covora.outreach.drafts import FOOTER, DraftEmail, check_draft, draft_email, fill_template
from covora.outreach.models import Template

TEMPLATE = Template(
    name="t",
    angle="pain",
    length="short",
    tone="direct",
    cta="question",
    subject_template="Quick question about {company}",
    body_template="Hi {first_name},\n\n{personal_hook}\n\n{value_prop}\n\n{cta}\n\n{sender_name}",
    offering_types=["sales_call"],
)


async def test_draft_valid_saved_with_footer(draft_env):
    email = await draft_email(draft_env.primary_id, ctx=draft_env.ctx, services=draft_env.services)
    assert email.status == "draft" and email.body.endswith(FOOTER) and email.kind == "cold"
    assert email.personalization and email.personalization[0]["fact_ids"]
    assert email.arm_key in {"A", "B"} and email.template_id is not None


async def test_draft_with_uncited_claim_retried_then_needs_review(draft_env):
    draft_env.backend.override(
        "DraftEmail",
        lambda inp: {
            "subject": "Hi",
            "body": "Hi there, you grew 300% last year!",
            "personalization": [{"text": "you grew 300%", "fact_ids": []}],
        },
    )
    email = await draft_env.draft()
    assert email.status == "needs_review" and "fact" in (email.error or "")
    assert len(draft_env.backend.inputs_for("DraftEmail")) == 2


def test_check_draft_rejects_prices_and_foreign_urls():
    bad = DraftEmail(subject="Deal", body="Get 20% off at https://evil.test now, {first_name}", personalization=[])
    problems = check_draft(bad, template=TEMPLATE, allowed_fact_ids=set(), allowed_urls={"https://acme.test"})
    joined = " ".join(problems)
    assert "price" in joined and "URL" in joined and "placeholder" in joined


def test_fill_template_resolves_placeholders():
    subject, body = fill_template(TEMPLATE, first_name="Dana", company="Ohio Precision", sender_name="Sam")
    assert "{" not in subject + body and "Dana" in body and "Ohio Precision" in subject
