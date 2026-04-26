from typing import Optional, Any, Callable, Dict, List
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from heapq import heappush, heappop, heapify
import time


@dataclass
class SchedulingContext:
    current_time: float
    cpu_id: int
    running_task: Optional[Any] = None
    all_running: List[Any] = field(default_factory=list)
    ready_queue: List[Any] = field(default_factory=list)


class SchedulingPolicy(ABC):
    """Base class for all scheduling policies.

    To implement a custom policy:
    1. Inherit from SchedulingPolicy
    2. Set `name` and `description` class attributes
    3. Implement the `select()` method
    4. Optionally override `add_task()`, `remove_task()`, `requires_preemption()`
    """

    name: str = "base"
    description: str = "Base scheduling policy"

    def __init__(self):
        self._queue: List[Any] = []
        self._task_map: Dict[str, Any] = {}

    def add_task(self, task: Any) -> None:
        key = self._task_key(task)
        self._task_map[key] = task
        self._enqueue(task)

    def remove_task(self, task: Any) -> None:
        key = self._task_key(task)
        self._task_map.pop(key, None)
        self._remove_from_queue(task)

    def has_pending(self) -> bool:
        return len(self._queue) > 0

    def task_count(self) -> int:
        return len(self._queue)

    def _task_key(self, task: Any) -> str:
        return f"{task.name}:{getattr(task, 'instance_id', 0)}"

    @abstractmethod
    def _enqueue(self, task: Any) -> None:
        """Add task to internal queue. Override for custom data structures."""
        pass

    @abstractmethod
    def _remove_from_queue(self, task: Any) -> None:
        """Remove task from internal queue. Override for custom data structures."""
        pass

    @abstractmethod
    def select(self) -> Optional[Any]:
        """Select the next task from internal queue.

        Returns:
            The selected task, or None if queue is empty
        """
        pass

    def requires_preemption(self, context: SchedulingContext) -> bool:
        """Determine if currently running task should be preempted.

        Default implementation checks if there's a higher-priority task ready.
        Override for custom preemption logic.

        Args:
            context: Current scheduling context

        Returns:
            True if preemption is required
        """
        if context.running_task is None or not self.has_pending():
            return False

        incoming = self.select()
        if incoming is None:
            return False

        running = context.running_task
        selected_incoming = self._would_select(incoming)
        selected_running = self._would_select(running)

        return selected_incoming is not None and selected_incoming is not selected_running

    def _would_select(self, task: Any) -> Optional[Any]:
        temp_queue = self._queue.copy()
        self._queue = [task]
        self._enqueue_inplace(task)
        result = self.select()
        self._queue = temp_queue
        return result

    def _enqueue_inplace(self, task: Any) -> None:
        pass

    def __repr__(self):
        return f"{self.__class__.__name__}(name='{self.name}', count={self.task_count()})"


class HeapPolicy(SchedulingPolicy):
    """Abstract base for policies using heap data structure."""

    def __init__(self, key_func: Optional[Callable[[Any], float]] = None):
        super().__init__()
        self._heap: List[Any] = []
        self._key_func = key_func or (lambda t: 0.0)

    def _enqueue(self, task: Any) -> None:
        heappush(self._heap, (self._key_func(task), task))
        if task not in self._queue:
            self._queue.append(task)

    def _remove_from_queue(self, task: Any) -> None:
        self._queue = [t for t in self._queue if t is not task]
        self._rebuild_heap()

    def _rebuild_heap(self) -> None:
        self._heap = [(self._key_func(t), t) for t in self._queue]
        heapify(self._heap)

    def select(self) -> Optional[Any]:
        if not self._heap:
            return None
        _, task = self._heap[0]
        return task

    def get_tasks(self) -> List[Any]:
        return [t for _, t in self._heap]


class QueuePolicy(SchedulingPolicy):
    """Abstract base for policies using simple queue (FIFO)."""

    def __init__(self):
        super().__init__()

    def _enqueue(self, task: Any) -> None:
        self._queue.append(task)

    def _remove_from_queue(self, task: Any) -> None:
        self._queue = [t for t in self._queue if t is not task]

    def select(self) -> Optional[Any]:
        if not self._queue:
            return None
        return self._queue[0]


class PolicyWithParams(ABC):
    """Base class for policies that accept configuration parameters."""

    @classmethod
    @abstractmethod
    def from_config(cls, config: Dict[str, Any]) -> "PolicyWithParams":
        pass


SelectorFn = Callable[[List[Any], float], Optional[Any]]

PolicyFactory = Callable[[Optional[Dict[str, Any]]], SchedulingPolicy]


class PolicyRegistry:
    """Registry for managing scheduling policies."""

    def __init__(self):
        self._policies: Dict[str, type] = {}
        self._factories: Dict[str, PolicyFactory] = {}

    def register(self, policy_class: type, factory: Optional[PolicyFactory] = None) -> None:
        name = getattr(policy_class, 'name', policy_class.__name__.lower())
        self._policies[name] = policy_class
        if factory:
            self._factories[name] = factory
        else:
            self._factories[name] = lambda params: policy_class(**(params or {}))

    def create(self, name: str, params: Optional[Dict[str, Any]] = None) -> SchedulingPolicy:
        if name not in self._factories:
            raise ValueError(f"Unknown policy '{name}'. Available: {list(self._policies.keys())}")
        return self._factories[name](params)

    def get(self, name: str) -> Optional[type]:
        return self._policies.get(name)

    def list_policies(self) -> List[str]:
        return list(self._policies.keys())

    def list_with_descriptions(self) -> Dict[str, str]:
        return {name: getattr(cls, 'description', '') for name, cls in self._policies.items()}