from typing import Optional, Any, Callable, Dict, List
from abc import ABC, abstractmethod


class SchedulingPolicy(ABC):
    """Base class for all scheduling policies.

    To implement a custom policy:
    1. Inherit from SchedulingPolicy
    2. Set `name` and `description` class attributes
    3. Implement the `select()` method

    Example:
        from src.policy.templates.base import SchedulingPolicy
        from src.task_params import get_task_value, get_task_laxity

        class MyPolicy(SchedulingPolicy):
            name = "my_policy"
            description = "My custom scheduling policy"

            def select(self, ready_queue, current_time):
                if not ready_queue:
                    return None
                # Your selection logic here
                return ready_queue[0]
    """

    name: str = "base"
    description: str = "Base scheduling policy"

    @abstractmethod
    def select(self, ready_queue: List[Any], current_time: float) -> Optional[Any]:
        """Select the next task to run from the ready queue.

        Args:
            ready_queue: List of tasks ready to execute
            current_time: Current simulation time

        Returns:
            The selected task, or None if ready_queue is empty
        """
        pass

    def __repr__(self):
        return f"{self.__class__.__name__}(name='{self.name}')"


class PolicyWithParams(ABC):
    """Base class for policies that accept configuration parameters.

    Example:
        class WeightedPolicy(PolicyWithParams):
            name = "weighted"
            description = "Policy with custom weights"

            def __init__(self, priority_weight: float = 0.5, deadline_weight: float = 0.5):
                self.priority_weight = priority_weight
                self.deadline_weight = deadline_weight

            def select(self, ready_queue, current_time):
                ...
    """

    @classmethod
    @abstractmethod
    def from_config(cls, config: Dict[str, Any]) -> "PolicyWithParams":
        """Create policy instance from configuration dict.

        Args:
            config: Configuration dictionary with policy parameters

        Returns:
            Policy instance configured with the given parameters
        """
        pass


SelectorFn = Callable[[List[Any], float], Optional[Any]]

PolicyFactory = Callable[[Optional[Dict[str, Any]]], SchedulingPolicy]


class PolicyRegistry:
    """Registry for managing scheduling policies.

    Use to register and create policy instances.

    Example:
        from src.policy.templates.base import PolicyRegistry, SchedulingPolicy

        registry = PolicyRegistry()

        @registry.register
        class MyPolicy(SchedulingPolicy):
            name = "my_policy"
            description = "My custom policy"

            def select(self, ready_queue, current_time):
                ...

        # Or register with factory:
        registry.register(MyPolicy, lambda cfg: MyPolicy(**cfg))
    """

    def __init__(self):
        self._policies: Dict[str, type] = {}
        self._factories: Dict[str, PolicyFactory] = {}

    def register(self, policy_class: type, factory: Optional[PolicyFactory] = None) -> None:
        """Register a policy class with an optional factory function.

        Args:
            policy_class: The policy class to register
            factory: Optional factory function to create policy instances
        """
        name = getattr(policy_class, 'name', policy_class.__name__.lower())
        self._policies[name] = policy_class
        if factory:
            self._factories[name] = factory
        else:
            self._factories[name] = lambda params: policy_class(**(params or {}))

    def create(self, name: str, params: Optional[Dict[str, Any]] = None) -> SchedulingPolicy:
        """Create a policy instance by name.

        Args:
            name: Policy name
            params: Optional parameters to pass to the factory

        Returns:
            Policy instance

        Raises:
            ValueError: If policy name is not found
        """
        if name not in self._factories:
            raise ValueError(
                f"Unknown policy '{name}'. Available: {list(self._policies.keys())}"
            )
        return self._factories[name](params)

    def get(self, name: str) -> Optional[type]:
        """Get policy class by name."""
        return self._policies.get(name)

    def list_policies(self) -> List[str]:
        """List all registered policy names."""
        return list(self._policies.keys())

    def list_with_descriptions(self) -> Dict[str, str]:
        """Get dict of policy names to descriptions."""
        return {
            name: getattr(cls, 'description', '')
            for name, cls in self._policies.items()
        }
