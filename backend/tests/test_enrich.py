from covora.discovery.enrich import enrich_and_score
from tests.helpers import campaign_companies_by_domain, count_tool_calls, facts_for


async def test_scores_and_qualifies(enrich_env):
    qualified = await enrich_and_score(
        enrich_env.campaign_id, enrich_env.candidate_ids, ctx=enrich_env.ctx, services=enrich_env.services
    )
    rows = await campaign_companies_by_domain(enrich_env.sessionmaker, enrich_env.campaign_id)
    assert rows["ohio-precision.test"].status == "qualified" and rows["ohio-precision.test"].fit_score >= 60
    assert rows["brightpath.test"].status == "rejected"
    assert rows["granite-foods.test"].status == "rejected"
    assert len(qualified) == sum(r.status == "qualified" for r in rows.values())
    assert rows["ohio-precision.test"].rank is not None


async def test_unquoted_revenue_dropped_and_quotes_verified(enrich_env):
    await enrich_and_score(
        enrich_env.campaign_id, enrich_env.candidate_ids, ctx=enrich_env.ctx, services=enrich_env.services
    )
    facts = await facts_for(enrich_env.sessionmaker, enrich_env.workspace.id, "ohio-precision.test")
    assert not [f for f in facts if f.field == "revenue_usd"]
    emp = next(f for f in facts if f.field == "employee_count")
    assert emp.label == "verified" and "18 employees" in emp.quote


async def test_fresh_facts_are_reused(enrich_env, sessionmaker):
    first = enrich_env.candidate_ids[:1]
    await enrich_and_score(enrich_env.campaign_id, first, ctx=enrich_env.ctx, services=enrich_env.services)
    before = await count_tool_calls(sessionmaker)
    await enrich_env.reset_status(first)
    await enrich_and_score(enrich_env.campaign_id, first, ctx=enrich_env.ctx, services=enrich_env.services)
    assert await count_tool_calls(sessionmaker) == before


async def test_judgment_with_foreign_fact_ids_is_cleaned(enrich_env):
    enrich_env.backend.override(
        "FitJudgment",
        lambda inp: {
            "criteria": [
                {"criterion": "industry", "status": "met", "fact_ids": ["not-a-fact"]},
                {"criterion": "made_up", "status": "met", "fact_ids": []},
            ],
            "confidence": "low",
            "reason": "r",
        },
    )
    first = enrich_env.candidate_ids[:1]
    await enrich_and_score(enrich_env.campaign_id, first, ctx=enrich_env.ctx, services=enrich_env.services)
    row = next(
        r
        for r in (await campaign_companies_by_domain(enrich_env.sessionmaker, enrich_env.campaign_id)).values()
        if r.company_id == first[0]
    )
    assert [c["name"] for c in row.criteria] == ["industry", "location", "employee_range", "revenue_range"]
    assert row.criteria[0]["fact_ids"] == []


def test_numeric_value_from_quote_and_empty_facts_dropped():
    from covora.discovery.schemas import ExtractedFact
    from covora.discovery.validate import validate_facts

    pages = {"https://a.test/": "Our team of 18 employees runs two shifts. Founded long ago."}
    facts = [
        ExtractedFact(
            field="employee_count",
            value="",
            source_url="https://a.test/",
            quote="Our team of 18 employees",
            label="verified",
        ),
        ExtractedFact(field="founded_year", value="", source_url="https://a.test/", quote="", label="unverified"),
        ExtractedFact(
            field="industry", value="metal fabrication", source_url="https://a.test/", quote="", label="unverified"
        ),
    ]
    kept = validate_facts(facts, pages)
    assert [(f.field, f.value) for f in kept] == [("employee_count", "18"), ("industry", "metal fabrication")]
