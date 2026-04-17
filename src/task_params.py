from typing import Any, Optional, Protocol, runtime_checkable, Callable
from dataclasses import dataclass


@runtime_checkable
class TaskTimingProtocol(Protocol):
    @property
    def period(self) -> Optional[float]: ...

    @property
    def execution_time(self) -> float: ...

    @property
    def deadline(self) -> Optional[float]: ...


@runtime_checkable
class TaskValueProtocol(Protocol):
    @property
    def value(self) -> Any: ...


@runtime_checkable
class TaskRuntimeProtocol(Protocol):
    @property
    def remaining_time(self) -> float: ...

    @property
    def absolute_deadline(self) -> float: ...

    @property
    def absolute_arrival(self) -> float: ...


@dataclass
class TaskAccessor:
    """Access task parameters through interfaces for polymorphic support."""

    get_T: Callable[[Any], Optional[float]]
    get_C: Callable[[Any], float]
    get_D: Callable[[Any], Optional[float]]
    get_Val: Callable[[Any, float], Any]

    def period(self, task: Any, current_time: float = 0.0) -> Optional[float]:
        return self.get_T(task)

    def computation(self, task: Any, current_time: float = 0.0) -> float:
        return self.get_C(task)

    def deadline(self, task: Any, current_time: float = 0.0) -> Optional[float]:
        return self.get_D(task)

    def value(self, task: Any, current_time: float = 0.0) -> Any:
        return self.get_Val(task, current_time)

    def laxity(self, task: Any, current_time: float) -> float:
        if isinstance(task, TaskRuntimeProtocol):
            remaining = task.remaining_time
            abs_deadline = task.absolute_deadline
        else:
            remaining = getattr(task, 'remaining_time', 0)
            abs_deadline = getattr(task, 'absolute_deadline', float('inf'))
        if remaining <= 0:
            return float('inf')
        return abs_deadline - current_time - remaining


DEFAULT_ACCESSOR = TaskAccessor(
    get_T=lambda t: getattr(t, 'period', None),
    get_C=lambda t: getattr(t, 'execution_time', 0.0),
    get_D=lambda t: getattr(t, 'deadline', None),
    get_Val=lambda t, ct: getattr(t, 'value', None),
)


def get_task_period(task: Any) -> Optional[float]:
    if isinstance(task, TaskTimingProtocol):
        return task.period
    return getattr(task, 'period', None)


def get_task_computation(task: Any) -> float:
    if isinstance(task, TaskTimingProtocol):
        return task.execution_time
    return getattr(task, 'execution_time', 0.0)


def get_task_deadline(task: Any) -> Optional[float]:
    if isinstance(task, TaskTimingProtocol):
        return task.deadline
    return getattr(task, 'deadline', None)


def get_task_value(task: Any, current_time: float = 0.0) -> Any:
    if isinstance(task, TaskValueProtocol):
        val = task.value
        if callable(val):
            return val(task, current_time)
        return val
    val = getattr(task, 'value', None)
    if callable(val):
        return val(task, current_time)
    return val


def compute_task_value(task: Any, current_time: float = 0.0, **context) -> Any:
    compute_fn = getattr(task, 'compute_value', None)
    if compute_fn is not None and callable(compute_fn):
        return compute_fn(current_time, **context)
    return get_task_value(task, current_time)


def get_task_laxity(task: Any, current_time: float) -> float:
    if isinstance(task, TaskRuntimeProtocol):
        remaining = task.remaining_time
        abs_deadline = task.absolute_deadline
    else:
        remaining = getattr(task, 'remaining_time', 0)
        abs_deadline = getattr(task, 'absolute_deadline', float('inf'))
    if remaining <= 0:
        return float('inf')
    return abs_deadline - current_time - remaining


def get_task_remaining_time(task: Any) -> float:
    if isinstance(task, TaskRuntimeProtocol):
        return task.remaining_time
    return getattr(task, 'remaining_time', 0.0)


def get_task_absolute_deadline(task: Any) -> float:
    if isinstance(task, TaskRuntimeProtocol):
        return task.absolute_deadline
    return getattr(task, 'absolute_deadline', float('inf'))


def get_task_absolute_arrival(task: Any) -> float:
    if isinstance(task, TaskRuntimeProtocol):
        return task.absolute_arrival
    return getattr(task, 'absolute_arrival', 0.0)
