from typing import Optional, Any, List
from src.policy.templates.base import SchedulingPolicy
from src.task_params import get_task_absolute_arrival


class FCFSPolicy(SchedulingPolicy):
    name = "fcfs"
    description = "First Come First Served - selects task that arrived earliest"

    def select(self, ready_queue: List[Any], current_time: float) -> Optional[Any]:
        if not ready_queue:
            return None
        return min(ready_queue, key=lambda t: get_task_absolute_arrival(t))


def fcfs_factory(params=None):
    return FCFSPolicy()
