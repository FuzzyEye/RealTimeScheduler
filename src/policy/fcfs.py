from typing import Optional, Any
from src.policy.templates.base import HeapPolicy, SchedulingContext
from src.task_params import get_task_absolute_arrival


class FCFSPolicy(HeapPolicy):
    name = "fcfs"
    description = "First Come First Served - selects task that arrived earliest"

    def __init__(self):
        super().__init__(key_func=lambda t: get_task_absolute_arrival(t))

    def _key_func(self, task: Any) -> float:
        return get_task_absolute_arrival(task)


def fcfs_factory(params=None):
    return FCFSPolicy()