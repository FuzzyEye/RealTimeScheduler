from typing import Optional, Any
from src.policy.templates.base import HeapPolicy, SchedulingContext
from src.task_params import get_task_absolute_deadline


class EDFPolicy(HeapPolicy):
    name = "edf"
    description = "Earliest Deadline First - selects task with earliest absolute deadline"

    def __init__(self):
        super().__init__(key_func=lambda t: get_task_absolute_deadline(t))

    def _key_func(self, task: Any) -> float:
        return get_task_absolute_deadline(task)

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


def edf_factory(params=None):
    return EDFPolicy()