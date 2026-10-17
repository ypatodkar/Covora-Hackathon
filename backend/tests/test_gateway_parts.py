import json

import pytest

from covora.gateway.output import extract_json, strip_reasoning
from covora.gateway.pricing import ModelPrice, estimate_cost
from covora.gateway.router import ModelIds, choose_route
from covora.gateway.tasks import TASK_TIERS, TaskType, Tier


def test_fixed_routing_uses_task_tier():
    m = ModelIds(nano="N", super="S")
    d = choose_route(TaskType.icp_parsing, "fixed", m)
    assert (d.tier, d.model, d.reason) == (Tier.super, "S", "fixed: icp_parsing → super")


def test_baselines_override_tier():
    m = ModelIds(nano="N", super="S")
    assert choose_route(TaskType.icp_parsing, "baseline_nano", m).model == "N"
    assert choose_route(TaskType.email_draft, "baseline_super", m).model == "S"


def test_switchyard_falls_back_to_fixed_for_now():
    d = choose_route(TaskType.email_draft, "switchyard", ModelIds("N", "S"))
    assert d.model == "N" and d.reason == "switchyard not enabled yet; used fixed"


def test_every_non_embedding_task_has_a_tier():
    assert set(TASK_TIERS) == set(TaskType) - {TaskType.embedding}


def test_extract_json_handles_fences_prose_and_think():
    raw = '<think>secret plan</think>\nSure! Here it is:\n```json\n{"a": {"b": [1, 2]}}\n```\nHope that helps.'
    assert json.loads(extract_json(raw)) == {"a": {"b": [1, 2]}}
    assert "secret plan" not in strip_reasoning(raw)


def test_extract_json_raises_without_json():
    with pytest.raises(ValueError):
        extract_json("no json here")


def test_estimate_cost():
    prices = {"S": ModelPrice(input_per_m=1.0, output_per_m=2.0)}
    assert estimate_cost("S", 1_000_000, 500_000, prices) == pytest.approx(2.0)
    assert estimate_cost("unknown", 10, 10, prices) is None
