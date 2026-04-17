from typing import Optional, Any, List
from src.policy.templates.base import SchedulingPolicy
from src.task_params import get_task_absolute_deadline


class EDFPolicy(SchedulingPolicy):
    name = "edf"
    description = "Earliest Deadline First - selects task with earliest absolute deadline"

    def select(self, ready_queue: List[Any], current_time: float) -> Optional[Any]:
        if not ready_queue:
            return None
        return min(ready_queue, key=lambda t: get_task_absolute_deadline(t))


def edf_factory(params=None):
    return EDFPolicy()
