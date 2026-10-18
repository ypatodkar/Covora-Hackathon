from dataclasses import dataclass

from covora.gateway.tasks import TASK_TIERS, TaskType, Tier


@dataclass(frozen=True)
class ModelIds:
    nano: str
    super: str

    def for_tier(self, tier: Tier) -> str:
        return self.nano if tier is Tier.nano else self.super


@dataclass(frozen=True)
class RoutingDecision:
    tier: Tier
    model: str
    mode: str
    reason: str


def choose_route(task: TaskType, mode: str, models: ModelIds) -> RoutingDecision:
    """Pick the model for one call. Switchyard routing arrives in Plan 6; until then it behaves like fixed."""
    if task is TaskType.embedding:
        raise ValueError("embeddings are not routed")
    if mode == "baseline_nano":
        tier, reason = Tier.nano, "baseline: all tasks → nano"
    elif mode == "baseline_super":
        tier, reason = Tier.super, "baseline: all tasks → super"
    elif mode == "switchyard":
        tier, reason = TASK_TIERS[task], "switchyard not enabled yet; used fixed"
    elif mode == "fixed":
        tier = TASK_TIERS[task]
        reason = f"fixed: {task} → {tier}"
    else:
        raise ValueError(f"unknown routing mode: {mode}")
    return RoutingDecision(tier=tier, model=models.for_tier(tier), mode=mode, reason=reason)


def other_tier(tier: Tier) -> Tier:
    return Tier.super if tier is Tier.nano else Tier.nano
