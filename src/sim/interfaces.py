from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from src.sim.scheduler import SchedulingResult


@dataclass(frozen=True)
class EngineConfig:
    """Stable engine construction contract for app/CLI layers."""

    start: float
    end: float
    strategy_name: str
    num_processors: int = 1
    preemptive: bool = True
    strategy_params: dict[str, Any] = field(default_factory=dict)


class SchedulerEngine(ABC):
    """Execution engine interface.

    Future multi-core support should implement this interface without changing
    CLI/application orchestration code.
    """

    @abstractmethod
    def run(self) -> SchedulingResult:
        raise NotImplementedError

