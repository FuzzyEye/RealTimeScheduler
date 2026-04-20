from __future__ import annotations

from typing import Optional

from src.core.registry import registry
from src.policy import policy_registry
from src.policy.selector_policy import SelectorPolicy
from src.policy.templates.base import SchedulingPolicy


def create_policy(strategy_name: str, strategy_params: Optional[dict] = None) -> SchedulingPolicy:
    strategy_def = registry.get(strategy_name)
    if strategy_def is None:
        raise ValueError(f"Strategy '{strategy_name}' not found. Available: {registry.list_names()}")

    params = dict(strategy_def.get("params", {}) or {})
    if strategy_params:
        params.update(strategy_params)
    if strategy_def.get("type") == "fixed_priority" and strategy_def.get("priority_key"):
        params.setdefault("priority_key", strategy_def["priority_key"])

    policy_cls = policy_registry.get(strategy_name)
    if policy_cls is not None:
        return policy_registry.create(strategy_name, params)

    selector_fn = registry.build_selector(strategy_name)
    return SelectorPolicy(selector_fn=selector_fn, name=strategy_name)

