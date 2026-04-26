from typing import Optional, Any
from src.policy.templates.base import HeapPolicy, SchedulingContext
from src.task_params import get_task_value, compute_task_value, get_task_laxity
from heapq import heappush, heappop, heapify


class ValueBasedPolicy(HeapPolicy):
    name = "value_based"
    description = "Value-based scheduling - selects task with highest value"

    def __init__(self):
        super().__init__()
        self._current_time = 0.0

    def _key_func(self, task: Any) -> float:
        val = compute_task_value(task, self._current_time)
        return -val if val is not None else float('-inf')

    def select(self) -> Optional[Any]:
        if not self._heap:
            return None
        return self._heap[0][1]

    def _enqueue(self, task: Any) -> None:
        key = self._key_func(task)
        heappush(self._heap, (key, task))
        if task not in self._queue:
            self._queue.append(task)


class HighestValuePolicy(HeapPolicy):
    name = "highest_value"
    description = "Highest Value - selects task with highest raw value"

    def __init__(self):
        super().__init__()

    def _key_func(self, task: Any) -> float:
        val = get_task_value(task, 0.0)
        return -val if val is not None else float('-inf')

    def select(self) -> Optional[Any]:
        if not self._heap:
            return None
        return self._heap[0][1]

    def _enqueue(self, task: Any) -> None:
        key = self._key_func(task)
        heappush(self._heap, (key, task))
        if task not in self._queue:
            self._queue.append(task)


class UtilityAwarePolicy(HeapPolicy):
    name = "utility_aware"
    description = "Utility-aware scheduling - combines value with urgency"

    def __init__(self, urgency_weight: float = 1.0, value_weight: float = 1.0):
        super().__init__()
        self.urgency_weight = urgency_weight
        self.value_weight = value_weight

    def _key_func(self, task: Any) -> float:
        val = get_task_value(task, 0.0)
        laxity = get_task_laxity(task, 0.0)
        if val is None:
            val = 1.0
        urgency = 1.0 / max(laxity, 0.1)
        return -(self.value_weight * val + self.urgency_weight * urgency)

    def select(self) -> Optional[Any]:
        if not self._heap:
            return None
        return self._heap[0][1]

    def _enqueue(self, task: Any) -> None:
        key = self._key_func(task)
        heappush(self._heap, (key, task))
        if task not in self._queue:
            self._queue.append(task)


class HybridPolicy(HeapPolicy):
    name = "hybrid"
    description = "Hybrid scheduling - weighted combination"

    def __init__(
        self,
        priority_weight: float = 0.3,
        deadline_weight: float = 0.3,
        value_weight: float = 0.4
    ):
        super().__init__()
        self.priority_weight = priority_weight
        self.deadline_weight = deadline_weight
        self.value_weight = value_weight

    def _key_func(self, task: Any) -> float:
        priority_score = 1.0 / max(getattr(task, 'priority', 1), 1)
        laxity = get_task_laxity(task, 0.0)
        deadline_score = 1.0 / max(laxity, 0.1)
        val = get_task_value(task, 0.0)
        value_score = val if isinstance(val, (int, float)) else 1.0
        score = (
            self.priority_weight * priority_score +
            self.deadline_weight * deadline_score +
            self.value_weight * value_score
        )
        return -score

    def select(self) -> Optional[Any]:
        if not self._heap:
            return None
        return self._heap[0][1]

    def _enqueue(self, task: Any) -> None:
        key = self._key_func(task)
        heappush(self._heap, (key, task))
        if task not in self._queue:
            self._queue.append(task)


def value_based_factory(params=None):
    return ValueBasedPolicy()


def highest_value_factory(params=None):
    return HighestValuePolicy()


def utility_aware_factory(params=None):
    urgency_weight = params.get('urgency_weight', 1.0) if params else 1.0
    value_weight = params.get('value_weight', 1.0) if params else 1.0
    return UtilityAwarePolicy(urgency_weight=urgency_weight, value_weight=value_weight)


def hybrid_factory(params=None):
    priority_weight = params.get('priority_weight', 0.3) if params else 0.3
    deadline_weight = params.get('deadline_weight', 0.3) if params else 0.3
    value_weight = params.get('value_weight', 0.4) if params else 0.4
    return HybridPolicy(priority_weight=priority_weight, deadline_weight=deadline_weight, value_weight=value_weight)