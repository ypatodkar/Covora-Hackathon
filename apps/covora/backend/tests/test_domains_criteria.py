from covora.discovery.criteria import fit_score, icp_criteria
from covora.discovery.domains import is_blocked, normalize_domain
from covora.icp.schemas import StructuredICP
from tests.fixtures_icp import EXAMPLE_ICP


def test_normalize_and_block_domains():
    assert normalize_domain("https://WWW.Ohio-Precision.test:443/about?x=1") == "ohio-precision.test"
    assert normalize_domain("ohio-precision.test") == "ohio-precision.test"
    assert normalize_domain("localhost") is None and normalize_domain("http://10.0.0.1/") is None
    assert is_blocked("uk.linkedin.com", ["linkedin.com"]) and not is_blocked("notlinkedin.com", ["linkedin.com"])


def test_criteria_from_example_icp():
    names = [c.name for c in icp_criteria(StructuredICP.model_validate(EXAMPLE_ICP))]
    assert names == ["industry", "location", "employee_range", "revenue_range"]


def test_fit_score_rules():
    cs = icp_criteria(StructuredICP.model_validate(EXAMPLE_ICP))
    assert fit_score(cs, {"industry": "met", "location": "met"}) == 83
    assert (
        fit_score(cs, {"industry": "not_met", "location": "met", "employee_range": "met", "revenue_range": "met"}) == 20
    )
    assert (
        fit_score(cs, {"industry": "met", "location": "met", "employee_range": "not_met", "revenue_range": "met"}) == 50
    )
    assert fit_score(cs, dict.fromkeys(["industry", "location", "employee_range", "revenue_range"], "met")) == 100


def test_exclusion_met_zeroes_score():
    icp = StructuredICP.model_validate(
        {**EXAMPLE_ICP, "exclusions": [{"value": "government contractors", "origin": "stated"}]}
    )
    cs = icp_criteria(icp)
    assert fit_score(cs, {"industry": "met", "location": "met", "exclusion:0": "met"}) == 0
