from typing import Optional, Any
from src.policy.templates.base import HeapPolicy, SchedulingContext
from src.core.task_params import get_task_laxity


class LLFPolicy(HeapPolicy):
    name = "llf"
    description = "Least Laxity First - selects task with smallest laxity"

    def __init__(self):
        super().__init__()
        self._current_time = 0.0
        # Make heap keys time-dependent (recomputed via _rebuild_heap()).
        self._key_func = lambda t: get_task_laxity(t, self._current_time)

    def set_current_time(self, current_time: float) -> None:
        self._current_time = float(current_time)
        self._rebuild_heap()

    def select(self) -> Optional[Any]:
        if not self._heap:
            return None
        _, task = self._heap[0]
        return task


class LLFThresholdPolicy(HeapPolicy):
    name = "llf_threshold"
    description = "LLF with threshold - switches to EDF when laxity exceeds threshold"

    def __init__(self, threshold: float = 2.0):
        super().__init__()
        self.threshold = threshold
        self._current_time = 0.0
        self._key_func = lambda t: get_task_laxity(t, self._current_time)

    def set_current_time(self, current_time: float) -> None:
        self._current_time = float(current_time)
        self._rebuild_heap()

    def select(self) -> Optional[Any]:
        if not self._heap:
            return None
        min_laxity = self._heap[0][0]
        if min_laxity > self.threshold:
            return min(self._queue, key=lambda t: t.absolute_deadline) if self._queue else None
        _, task = self._heap[0]
        return task


def llf_factory(params=None):
    return LLFPolicy()


def llf_threshold_factory(params=None):
    threshold = params.get('threshold', 2.0) if params else 2.0
    return LLFThresholdPolicy(threshold=threshold)