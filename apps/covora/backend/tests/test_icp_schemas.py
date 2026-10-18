import pytest
from pydantic import ValidationError

from covora.icp.schemas import Range, StructuredICP
from tests.fixtures_icp import VAGUE_ICP_JSON


def test_range_min_greater_than_max_rejected():
    with pytest.raises(ValidationError):
        Range(min=100, max=25)


def test_vague_icp_is_valid():
    icp = StructuredICP.model_validate(VAGUE_ICP_JSON)
    assert icp.industries == [] and icp.employee_range is None and icp.assumptions


def test_model_strings_are_cleaned():
    raw = {
        "summary": " US manufacturers ",
        "assumptions": [": Assumed USD", ""],
        "buyer_map": {
            "target_functions": [{"value": "- operations", "origin": "stated"}],
            "by_company_size": [
                {
                    "employees": {"min": 1, "max": 50},
                    "primary_titles": [".Operations Manager", "• COO", " ", "/owner", "| CEO"],
                    "origin": "inferred",
                }
            ],
        },
    }
    icp = StructuredICP.model_validate(raw)
    assert icp.summary == "US manufacturers" and icp.assumptions == ["Assumed USD"]
    assert icp.buyer_map.target_functions[0].value == "operations"
    assert icp.buyer_map.by_company_size[0].primary_titles == ["Operations Manager", "COO", "owner", "CEO"]
