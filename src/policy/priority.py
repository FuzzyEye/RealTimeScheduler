from typing import Optional, Any
from src.policy.templates.base import HeapPolicy, SchedulingContext
from src.task_params import get_task_period


class RMSPolicy(HeapPolicy):
    name = "rms"
    description = "Rate Monotonic Scheduling - fixed priority based on period"

    def __init__(self):
        super().__init__(key_func=lambda t: get_task_period(t) if get_task_period(t) is not None else float('inf'))

    def _key_func(self, task: Any) -> float:
        return get_task_period(task) if get_task_period(task) is not None else float('inf')

    def requires_preemption(self, context: SchedulingContext) -> bool:
        if context.running_task is None:
            return False
        if not self.has_pending():
            return False

        running_key = self._key_func(context.running_task)
        selected = self.select()
        if selected is None:
            return False
        selected_key = self._key_func(selected)
        return selected_key < running_key


class DMSPolicy(HeapPolicy):
    name = "dms"
    description = "Deadline Monotonic Scheduling - fixed priority based on relative deadline"

    def __init__(self, priority_key: str = "deadline"):
        super().__init__(key_func=lambda t: getattr(t, priority_key, float('inf')))
        self.priority_key = priority_key

    def _key_func(self, task: Any) -> float:
        return getattr(task, self.priority_key, float('inf'))


class FixedPriorityPolicy(HeapPolicy):
    name = "fixed_priority"
    description = "Fixed priority scheduling - selects task by fixed priority attribute"

    def __init__(self, priority_key: str = "priority", reverse: bool = False):
        super().__init__()
        self.priority_key = priority_key
        self.reverse = reverse
        self._key_func = lambda t: getattr(t, priority_key, float('-inf' if reverse else float('inf')))

    def _key_func(self, task: Any) -> float:
        return getattr(task, self.priority_key, float('-inf' if self.reverse else float('inf')))

    def requires_preemption(self, context: SchedulingContext) -> bool:
        if context.running_task is None:
            return False
        if not self.has_pending():
            return False
        return self.select() is not context.running_task


def rms_factory(params=None):
    return RMSPolicy()


def dms_factory(params=None):
    return DMSPolicy()


def fixed_priority_factory(params=None):
    priority_key = params.get('priority_key', 'priority') if params else 'priority'
    reverse = params.get('reverse', False) if params else False
    return FixedPriorityPolicy(priority_key=priority_key, reverse=reverse)