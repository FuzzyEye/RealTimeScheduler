"""Policy templates and base classes.

This module provides the base classes and example implementations
for creating custom scheduling policies.

To implement a custom policy:

1. Inherit from SchedulingPolicy
2. Set `name` and `description` class attributes
3. Implement the `select()` method
4. Use task_params interfaces for accessing task data

Example:
    from src.policy.templates.base import SchedulingPolicy
    from src.task_params import get_task_value

    class MyPolicy(SchedulingPolicy):
        name = "my_policy"
        description = "My custom scheduling policy"

        def select(self, ready_queue, current_time):
            if not ready_queue:
                return None
            return max(ready_queue, key=lambda t: get_task_value(t, current_time) or 0)
"""

from src.policy.templates.base import (
    SchedulingPolicy,
    PolicyWithParams,
    SelectorFn,
    PolicyFactory,
    PolicyRegistry,
)
from src.policy.templates.examples import (
    ValueBasedTemplate,
    UtilityAwareTemplate,
    ProportionalValueTemplate,
    HybridTemplate,
    create_priority_deadline_policy,
    create_value_urgency_policy,
)

__all__ = [
    "SchedulingPolicy",
    "PolicyWithParams",
    "SelectorFn",
    "PolicyFactory",
    "PolicyRegistry",
    "ValueBasedTemplate",
    "UtilityAwareTemplate",
    "ProportionalValueTemplate",
    "HybridTemplate",
    "create_priority_deadline_policy",
    "create_value_urgency_policy",
]
