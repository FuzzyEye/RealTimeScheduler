from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from src.core.config import Config, ConfigSimulation, ConfigStrategy, ConfigTask


def _normalize_numeric_params(value: Any) -> Any:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, list):
        return [_normalize_numeric_params(v) for v in value]
    if isinstance(value, dict):
        return {k: _normalize_numeric_params(v) for k, v in value.items()}
    return value


def load_config(path: str | Path) -> Config:
    with open(path, "r") as f:
        raw = yaml.safe_load(f) or {}

    tasks = [
        ConfigTask(
            name=t["name"],
            execution_time=int(t["execution_time"]),
            period=int(t["period"]) if t.get("period") is not None else None,
            deadline=int(t["deadline"]) if t.get("deadline") is not None else None,
            priority=t.get("priority", 0),
            arrival_time=int(t.get("arrival_time", 0)),
            value=t.get("value"),
        )
        for t in raw.get("tasks", [])
    ]

    sim = raw.get("simulation", {})
    simulation = ConfigSimulation(
        start=int(sim.get("start", 0)),
        end=int(sim.get("end", 10)),
        strategy=sim.get("strategy", "edf"),
        params=_normalize_numeric_params(sim.get("params", {})),
    )

    strategies = [
        ConfigStrategy(
            name=s["name"],
            type=s["type"],
            description=s.get("description", ""),
            selector=s.get("selector"),
            fallback=s.get("fallback"),
            priority_key=s.get("priority_key"),
            condition=s.get("condition"),
            true_branch=s.get("true_branch"),
            false_branch=s.get("false_branch"),
            params=_normalize_numeric_params(s.get("params", {})),
            module=s.get("module"),
            class_name=s.get("class_name"),
        )
        for s in raw.get("strategies", [])
    ]
    return Config(tasks=tasks, simulation=simulation, strategies=strategies)


def register_strategies(config: Config, strategy_registry: Any) -> None:
    for s in config.strategies:
        strategy_registry.register(
            s.name,
            {
                "type": s.type,
                "selector": s.selector,
                "fallback": s.fallback,
                "priority_key": s.priority_key,
                "condition": s.condition,
                "true_branch": s.true_branch,
                "false_branch": s.false_branch,
                "params": s.params,
                "module": s.module,
                "class_name": s.class_name,
                "description": s.description,
            },
        )

