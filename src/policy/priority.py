from typing import Optional, Any, List
from src.policy.templates.base import SchedulingPolicy
from src.task_params import get_task_period


class RMSPolicy(SchedulingPolicy):
    name = "rms"
    description = "Rate Monotonic Scheduling - fixed priority based on period (shorter period = higher priority)"

    def select(self, ready_queue: List[Any], current_time: float) -> Optional[Any]:
        if not ready_queue:
            return None
        return min(ready_queue, key=lambda t: get_task_period(t) if get_task_period(t) is not None else float('inf'))


class DMSPolicy(SchedulingPolicy):
    name = "dms"
    description = "Deadline Monotonic Scheduling - fixed priority based on relative deadline"

    def __init__(self, priority_key: str = "deadline"):
        self.priority_key = priority_key

    def select(self, ready_queue: List[Any], current_time: float) -> Optional[Any]:
        if not ready_queue:
            return None
        return min(ready_queue, key=lambda t: getattr(t, self.priority_key, float('inf')))


class FixedPriorityPolicy(SchedulingPolicy):
    name = "fixed_priority"
    description = "Fixed priority scheduling - selects task by fixed priority attribute"

    def __init__(self, priority_key: str = "priority", reverse: bool = False):
        self.priority_key = priority_key
        self.reverse = reverse

    def select(self, ready_queue: List[Any], current_time: float) -> Optional[Any]:
        if not ready_queue:
            return None
        if self.reverse:
            return max(ready_queue, key=lambda t: getattr(t, self.priority_key, float('-inf')))
        return min(ready_queue, key=lambda t: getattr(t, self.priority_key, float('inf')))


def rms_factory(params=None):
    return RMSPolicy()


def dms_factory(params=None):
    return DMSPolicy()


def fixed_priority_factory(params=None):
    priority_key = params.get('priority_key', 'priority') if params else 'priority'
    reverse = params.get('reverse', False) if params else False
    return FixedPriorityPolicy(priority_key=priority_key, reverse=reverse)
