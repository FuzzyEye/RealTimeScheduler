from typing import Optional, Any, List
from src.policy.templates.base import SchedulingPolicy
from src.task_params import get_task_laxity, get_task_absolute_deadline


class EDZLPolicy(SchedulingPolicy):
    name = "edzl"
    description = "Earliest Deadline Zero Laxity - uses EDF but switches to task with zero laxity when any task has zero laxity"

    def select(self, ready_queue: List[Any], current_time: float) -> Optional[Any]:
        if not ready_queue:
            return None

        min_laxity = min(get_task_laxity(t, current_time) for t in ready_queue)

        if abs(min_laxity) < 1e-9:
            return min(ready_queue, key=lambda t: get_task_absolute_deadline(t))

        return min(ready_queue, key=lambda t: get_task_absolute_deadline(t))


class EDZLDeadlineDriven(SchedulingPolicy):
    name = "edzl_dd"
    description = "EDZL Deadline Driven - switches to LLF only when minimum laxity is zero"

    def __init__(self, zero_threshold: float = 0.01):
        self.zero_threshold = zero_threshold

    def select(self, ready_queue: List[Any], current_time: float) -> Optional[Any]:
        if not ready_queue:
            return None

        laxities = [get_task_laxity(t, current_time) for t in ready_queue]
        min_laxity = min(laxities)

        if min_laxity <= self.zero_threshold:
            return min(ready_queue, key=lambda t: get_task_laxity(t, current_time))

        return min(ready_queue, key=lambda t: get_task_absolute_deadline(t))


def edzl_factory(params=None):
    return EDZLPolicy()


def edzl_dd_factory(params=None):
    threshold = params.get('zero_threshold', 0.01) if params else 0.01
    return EDZLDeadlineDriven(zero_threshold=threshold)