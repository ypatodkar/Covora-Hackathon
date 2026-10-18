from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol


class _Price(Protocol):
    input_per_m: float
    output_per_m: float


@dataclass(frozen=True)
class ModelPrice:
    input_per_m: float
    output_per_m: float


def estimate_cost(
    model: str, prompt_tokens: int, completion_tokens: int, prices: Mapping[str, _Price]
) -> float | None:
    """Estimated USD cost of one call; None when the model has no configured price (spec §15.6)."""
    price = prices.get(model)
    if price is None:
        return None
    return (prompt_tokens * price.input_per_m + completion_tokens * price.output_per_m) / 1_000_000
