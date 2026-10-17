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
