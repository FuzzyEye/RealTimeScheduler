from typing import Optional, Any, List
from src.policy.templates.base import SchedulingPolicy


class RoundRobinPolicy(SchedulingPolicy):
    name = "rr"
    description = "Round Robin - time quantum scheduling, fair CPU time distribution"

    def __init__(self, quantum: float = 1.0):
        self.quantum = quantum

    def select(self, ready_queue: List[Any], current_time: float) -> Optional[Any]:
        if not ready_queue:
            return None
        return ready_queue[0]

    def get_quantum(self) -> float:
        return self.quantum


def rr_factory(params=None):
    quantum = params.get('quantum', 1.0) if params else 1.0
    return RoundRobinPolicy(quantum=quantum)
