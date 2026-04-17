"""Scheduling policies module.

Policies implement the SchedulingPolicy interface and provide
task selection logic for the scheduler.

Built-in policies:
    - edf.py: EDFPolicy (Earliest Deadline First)
    - llf.py: LLFPolicy, LLFThresholdPolicy (Least Laxity First)
    - priority.py: RMSPolicy, DMSPolicy, FixedPriorityPolicy (Fixed Priority)
    - fcfs.py: FCFSPolicy (First Come First Served)
    - rr.py: RoundRobinPolicy (Round Robin)
    - value.py: ValueBasedPolicy, HighestValuePolicy, UtilityAwarePolicy, HybridPolicy (Value-based)

To create a custom policy, see src/policy/templates/
"""

from src.policy.templates.base import (
    SchedulingPolicy,
    PolicyWithParams,
    SelectorFn,
    PolicyFactory,
    PolicyRegistry,
)

from src.policy.edf import EDFPolicy, edf_factory
from src.policy.llf import LLFPolicy, LLFThresholdPolicy, llf_factory, llf_threshold_factory
from src.policy.priority import (
    RMSPolicy, DMSPolicy, FixedPriorityPolicy,
    rms_factory, dms_factory, fixed_priority_factory
)
from src.policy.fcfs import FCFSPolicy, fcfs_factory
from src.policy.rr import RoundRobinPolicy, rr_factory
from src.policy.value import (
    ValueBasedPolicy, HighestValuePolicy, UtilityAwarePolicy, HybridPolicy,
    value_based_factory, highest_value_factory, utility_aware_factory, hybrid_factory
)


policy_registry = PolicyRegistry()

policy_registry.register(EDFPolicy, edf_factory)
policy_registry.register(LLFPolicy, llf_factory)
policy_registry.register(LLFThresholdPolicy, llf_threshold_factory)
policy_registry.register(RMSPolicy, rms_factory)
policy_registry.register(DMSPolicy, dms_factory)
policy_registry.register(FixedPriorityPolicy, fixed_priority_factory)
policy_registry.register(FCFSPolicy, fcfs_factory)
policy_registry.register(RoundRobinPolicy, rr_factory)
policy_registry.register(ValueBasedPolicy, value_based_factory)
policy_registry.register(HighestValuePolicy, highest_value_factory)
policy_registry.register(UtilityAwarePolicy, utility_aware_factory)
policy_registry.register(HybridPolicy, hybrid_factory)


__all__ = [
    "SchedulingPolicy",
    "PolicyWithParams",
    "SelectorFn",
    "PolicyFactory",
    "PolicyRegistry",
    "policy_registry",
    "EDFPolicy",
    "LLFPolicy",
    "LLFThresholdPolicy",
    "RMSPolicy",
    "DMSPolicy",
    "FixedPriorityPolicy",
    "FCFSPolicy",
    "RoundRobinPolicy",
    "ValueBasedPolicy",
    "HighestValuePolicy",
    "UtilityAwarePolicy",
    "HybridPolicy",
]
