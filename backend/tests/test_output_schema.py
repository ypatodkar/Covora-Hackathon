import json

from covora.gateway.schema import output_schema
from covora.icp.schemas import StructuredICP


def test_output_schema_inlines_refs_and_requires_all_fields():
    schema = output_schema(StructuredICP)
    assert "$ref" not in json.dumps(schema) and "$defs" not in schema
    assert schema["title"] == "StructuredICP"
    assert {"industries", "employee_range", "buyer_map", "summary"} <= set(schema["required"])
    tagged = schema["properties"]["industries"]["items"]
    assert set(tagged["required"]) == {"value", "origin"}
    buyer_map = schema["properties"]["buyer_map"]
    assert set(buyer_map["required"]) == {"target_functions", "by_company_size", "skip_titles"}


def test_nullable_fields_stay_nullable():
    employee_range = output_schema(StructuredICP)["properties"]["employee_range"]
    assert {"type": "null"} in employee_range["anyOf"]
