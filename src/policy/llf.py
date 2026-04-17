from typing import Optional, Any
from src.policy.templates.base import HeapPolicy, SchedulingContext
from src.task_params import get_task_laxity


class LLFPolicy(HeapPolicy):
    name = "llf"
    description = "Least Laxity First - selects task with smallest laxity"

    def __init__(self):
        super().__init__()
        self._current_time = 0.0

    def _key_func(self, task: Any) -> float:
        return get_task_laxity(task, self._current_time)

    def _enqueue(self, task: Any) -> None:
        key = get_task_laxity(task, self._current_time)
        heappush(self._heap, (key, task))
        if task not in self._queue:
            self._queue.append(task)

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
        self._fallback_key = lambda t: t.absolute_deadline

    def _key_func(self, task: Any) -> float:
        return get_task_laxity(task, self._current_time)

    def _enqueue(self, task: Any) -> None:
        key = get_task_laxity(task, self._current_time)
        heappush(self._heap, (key, task))
        if task not in self._queue:
            self._queue.append(task)

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