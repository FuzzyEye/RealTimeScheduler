from typing import Optional, Any
from src.policy.templates.base import QueuePolicy, SchedulingContext


class RoundRobinPolicy(QueuePolicy):
    name = "rr"
    description = "Round Robin - time quantum scheduling, fair CPU time distribution"

    def __init__(self, quantum: float = 1.0):
        super().__init__()
        self.quantum = quantum
        self.current_quantum_expire: float = 0.0

    def _enqueue(self, task: Any) -> None:
        self._queue.append(task)

    def _remove_from_queue(self, task: Any) -> None:
        self._queue = [t for t in self._queue if t is not task]

    def select(self) -> Optional[Any]:
        if not self._queue:
            return None
        return self._queue[0]

    def requires_preemption(self, context: SchedulingContext) -> bool:
        if context.running_task is None:
            return False
        qet = getattr(context.running_task, 'quantum_expire_time', None)
        if qet is not None and context.current_time >= qet - 1e-9:
            return True
        return False


def rr_factory(params=None):
    quantum = params.get('quantum', 1.0) if params else 1.0
    return RoundRobinPolicy(quantum=quantum)