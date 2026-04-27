from __future__ import annotations

from src.sim.engine import SingleCoreEngine
from src.sim.interfaces import EngineConfig, SchedulerEngine


def create_engine(tasks, config: EngineConfig) -> SchedulerEngine:
    """Create a scheduler engine from a stable config object."""
    return SingleCoreEngine(
        tasks=tasks,
        start=config.start,
        end=config.end,
        strategy_name=config.strategy_name,
        strategy_params=config.strategy_params,
        num_processors=config.num_processors,
        preemptive=config.preemptive,
    )


def run_simulation(tasks, config: EngineConfig):
    """Convenience API for one-shot simulation execution."""
    return create_engine(tasks, config).run()
