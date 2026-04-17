"""Example custom scheduling policies.

This module provides template implementations that users can use as references
for creating their own scheduling policies.

Example 1: Simple Custom Policy
-------------------------------
    from src.policy.templates.base import SchedulingPolicy
    from src.task_params import get_task_value

    class ValueBasedPolicy(SchedulingPolicy):
        name = "value_based"
        description = "Select task with highest value"

        def select(self, ready_queue, current_time):
            if not ready_queue:
                return None
            return max(ready_queue, key=lambda t: get_task_value(t, current_time) or 0)


Example 2: Policy with Configuration
----------------------------------
    from src.policy.templates.base import SchedulingPolicy
    from src.task_params import get_task_laxity, get_task_value

    class UtilityAwarePolicy(SchedulingPolicy):
        name = "utility_aware"
        description = "Utility-aware scheduling combining value and urgency"

        def __init__(self, urgency_weight: float = 1.0, value_weight: float = 1.0):
            self.urgency_weight = urgency_weight
            self.value_weight = value_weight

        def select(self, ready_queue, current_time):
            if not ready_queue:
                return None

            def compute_utility(task):
                val = get_task_value(task, current_time) or 1.0
                laxity = get_task_laxity(task, current_time)
                urgency = 1.0 / max(laxity, 0.1)
                return self.value_weight * val + self.urgency_weight * urgency

            return max(ready_queue, key=compute_utility)


Example 3: Hybrid Multi-Factor Policy
-------------------------------------
    from src.policy.templates.base import SchedulingPolicy
    from src.task_params import get_task_laxity, get_task_value

    class HybridPolicy(SchedulingPolicy):
        name = "hybrid"
        description = "Weighted combination of priority, deadline, and value"

        def __init__(
            self,
            priority_weight: float = 0.3,
            deadline_weight: float = 0.3,
            value_weight: float = 0.4
        ):
            self.priority_weight = priority_weight
            self.deadline_weight = deadline_weight
            self.value_weight = value_weight

        def select(self, ready_queue, current_time):
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


Example 4: Using Task Interface Properties (T, C, D, Val)
---------------------------------------------------------
    from src.policy.templates.base import SchedulingPolicy

    class ProportionalValuePolicy(SchedulingPolicy):
        name = "proportional_value"
        description = "Select task with highest value-to-remaining-time ratio"

        def select(self, ready_queue, current_time):
            if not ready_queue:
                return None

            def value_per_time(task):
                val = task.Val  # Using interface property
                C = task.C      # Using interface property
                remaining = getattr(task, 'remaining_time', C)
                if remaining <= 0:
                    return float('-inf')
                return (val or 0) / remaining

            return max(ready_queue, key=value_per_time)


Example 5: Dynamic Value Computation
-----------------------------------
    from src.policy.templates.base import SchedulingPolicy
    from src.task_params import compute_task_value

    class DynamicValuePolicy(SchedulingPolicy):
        name = "dynamic_value"
        description = "Select task with highest dynamically computed value"

        def select(self, ready_queue, current_time):
            if not ready_queue:
                return None
            return max(
                ready_queue,
                key=lambda t: compute_task_value(t, current_time, ready_queue=ready_queue) or 0
            )
"""

from typing import Optional, Any, List, Dict
from src.policy.templates.base import SchedulingPolicy
from src.task_params import (
    get_task_value,
    get_task_laxity,
    get_task_computation,
    get_task_deadline,
    compute_task_value,
)


class ValueBasedTemplate(SchedulingPolicy):
    """Template: Value-based selection (highest Val)."""
    name = "value_based_template"
    description = "Select task with highest value (Val) - template example"

    def select(self, ready_queue: List[Any], current_time: float) -> Optional[Any]:
        if not ready_queue:
            return None
        return max(
            ready_queue,
            key=lambda t: compute_task_value(t, current_time, ready_queue=ready_queue) or 0
        )


class UtilityAwareTemplate(SchedulingPolicy):
    """Template: Utility-aware selection combining value with laxity."""
    name = "utility_aware_template"
    description = "Utility-aware scheduling - template example"

    def __init__(self, urgency_weight: float = 1.0, value_weight: float = 1.0):
        self.urgency_weight = urgency_weight
        self.value_weight = value_weight

    def select(self, ready_queue: List[Any], current_time: float) -> Optional[Any]:
        if not ready_queue:
            return None

        def compute_utility(task):
            val = get_task_value(task, current_time)
            if val is None:
                val = 1.0
            laxity = get_task_laxity(task, current_time)
            urgency = 1.0 / max(laxity, 0.1)
            return self.value_weight * (val if isinstance(val, (int, float)) else 1.0) + \
                   self.urgency_weight * urgency

        return max(ready_queue, key=compute_utility)


class ProportionalValueTemplate(SchedulingPolicy):
    """Template: Value per unit of remaining execution time."""
    name = "proportional_value_template"
    description = "Select task with highest value-to-time ratio - template example"

    def select(self, ready_queue: List[Any], current_time: float) -> Optional[Any]:
        if not ready_queue:
            return None

        def value_per_time(task):
            val = get_task_value(task, current_time)
            C = get_task_computation(task)
            remaining = getattr(task, 'remaining_time', C)

            if val is None:
                return 0.0
            if not isinstance(val, (int, float)):
                val = 1.0
            if remaining <= 0:
                return float('-inf')
            return val / remaining

        return max(ready_queue, key=value_per_time)


class HybridTemplate(SchedulingPolicy):
    """Template: Weighted combination of multiple factors."""
    name = "hybrid_template"
    description = "Hybrid multi-factor scheduling - template example"

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


def create_priority_deadline_policy(
    priority_weight: float = 0.5,
    deadline_weight: float = 0.5
) -> SchedulingPolicy:
    """Factory: Create a priority-deadline hybrid policy.

    Args:
        priority_weight: Weight for priority factor (0-1)
        deadline_weight: Weight for deadline factor (0-1)

    Returns:
        Configured hybrid policy instance
    """
    return HybridTemplate(
        priority_weight=priority_weight,
        deadline_weight=deadline_weight,
        value_weight=0.0
    )


def create_value_urgency_policy(
    value_weight: float = 0.5,
    urgency_weight: float = 0.5
) -> SchedulingPolicy:
    """Factory: Create a value-urgency policy.

    Args:
        value_weight: Weight for value factor (0-1)
        urgency_weight: Weight for urgency factor (0-1)

    Returns:
        Configured utility-aware policy instance
    """
    return UtilityAwareTemplate(
        value_weight=value_weight,
        urgency_weight=urgency_weight
    )
