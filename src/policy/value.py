from typing import Optional, Any, List
from src.policy.templates.base import SchedulingPolicy
from src.task_params import get_task_value, compute_task_value, get_task_laxity


class ValueBasedPolicy(SchedulingPolicy):
    name = "value_based"
    description = "Value-based scheduling - selects task with highest value (Val parameter)"

    def select(self, ready_queue: List[Any], current_time: float) -> Optional[Any]:
        if not ready_queue:
            return None
        return max(
            ready_queue,
            key=lambda t: compute_task_value(t, current_time, ready_queue=ready_queue) or float('-inf')
        )


class HighestValuePolicy(SchedulingPolicy):
    name = "highest_value"
    description = "Highest Value - selects task with highest raw value"

    def select(self, ready_queue: List[Any], current_time: float) -> Optional[Any]:
        if not ready_queue:
            return None
        return max(
            ready_queue,
            key=lambda t: get_task_value(t, current_time) if get_task_value(t, current_time) is not None else float('-inf')
        )


class UtilityAwarePolicy(SchedulingPolicy):
    name = "utility_aware"
    description = "Utility-aware scheduling - combines value with urgency (laxity)"

    def __init__(self, urgency_weight: float = 1.0, value_weight: float = 1.0):
        self.urgency_weight = urgency_weight
        self.value_weight = value_weight

    def select(self, ready_queue: List[Any], current_time: float) -> Optional[Any]:
        if not ready_queue:
            return None

        def compute_utility(task):
            val = get_task_value(task, current_time)
            laxity = get_task_laxity(task, current_time)

            if val is None:
                val = 1.0

            urgency = 1.0 / max(laxity, 0.1)
            return self.value_weight * (val if isinstance(val, (int, float)) else 1.0) + self.urgency_weight * urgency

        return max(ready_queue, key=compute_utility)


class HybridPolicy(SchedulingPolicy):
    name = "hybrid"
    description = "Hybrid scheduling - weighted combination of priority, deadline, and value"

    def __init__(
        self,
        priority_weight: float = 0.3,
        deadline_weight: float = 0.3,
        value_weight: float = 0.4
    ):
        self.priority_weight = priority_weight
        self.deadline_weight = deadline_weight
        self.value_weight = value_weight

    def select(self, ready_queue: List[Any], current_time: float) -> Optional[Any]:
        if not ready_queue:
            return None

        def hybrid_score(task):
            priority_score = 1.0 / max(getattr(task, 'priority', 1), 1)
            deadline_score = 1.0 / max(get_task_laxity(task, current_time), 0.1)
            val = get_task_value(task, current_time)
            value_score = val if isinstance(val, (int, float)) else 1.0

            return (
                self.priority_weight * priority_score +
                self.deadline_weight * deadline_score +
                self.value_weight * value_score
            )

        return max(ready_queue, key=hybrid_score)


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
