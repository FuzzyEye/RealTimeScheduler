from __future__ import annotations

from abc import ABC, abstractmethod

from src.sim.scheduler import SchedulingResult


class SchedulerEngine(ABC):
    """Execution engine interface.

    Future multi-core support should implement this interface without changing
    CLI/application orchestration code.
    """

    @abstractmethod
    def run(self) -> SchedulingResult:
        raise NotImplementedError

