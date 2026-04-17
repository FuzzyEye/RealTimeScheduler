from typing import Optional, Any, List
from src.policy.templates.base import SchedulingPolicy
from src.task_params import get_task_laxity


class LLFPolicy(SchedulingPolicy):
    name = "llf"
    description = "Least Laxity First - selects task with smallest laxity (slack time)"

    def select(self, ready_queue: List[Any], current_time: float) -> Optional[Any]:
        if not ready_queue:
            return None
        return min(ready_queue, key=lambda t: get_task_laxity(t, current_time))


class LLFThresholdPolicy(SchedulingPolicy):
    name = "llf_threshold"
    description = "LLF with threshold - switches to EDF when laxity exceeds threshold"

    def __init__(self, threshold: float = 2.0, fallback_policy: SchedulingPolicy = None):
        self.threshold = threshold
        self.fallback_policy = fallback_policy

    def select(self, ready_queue: List[Any], current_time: float) -> Optional[Any]:
        if not ready_queue:
            return None

        min_laxity = min(get_task_laxity(t, current_time) for t in ready_queue)

        if min_laxity > self.threshold:
            if self.fallback_policy:
                return self.fallback_policy.select(ready_queue, current_time)
            from src.policy.edf import EDFPolicy
            return EDFPolicy().select(ready_queue, current_time)

        return min(ready_queue, key=lambda t: get_task_laxity(t, current_time))


def llf_factory(params=None):
    return LLFPolicy()


def llf_threshold_factory(params=None):
    threshold = params.get('threshold', 2.0) if params else 2.0
    return LLFThresholdPolicy(threshold=threshold)
