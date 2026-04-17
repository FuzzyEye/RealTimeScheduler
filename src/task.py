from dataclasses import dataclass, field
from typing import Any, Optional, Callable


@dataclass
class Task:
    name: str
    execution_time: float
    period: Optional[float] = None
    deadline: Optional[float] = None
    priority: int = 0
    arrival_time: float = 0.0
    instance_id: int = 0
    value: Any = None

    remaining_time: float = field(init=False)
    absolute_deadline: float = field(init=False, default=0.0)
    absolute_arrival: float = field(init=False, default=0.0)
    _period: float = field(init=False, default=0.0)

    @property
    def T(self) -> Optional[float]:
        return self.period

    @property
    def C(self) -> float:
        return self.execution_time

    @property
    def D(self) -> Optional[float]:
        return self.deadline

    @property
    def Val(self) -> Any:
        return self.value

    def compute_value(self, current_time: float = 0.0, **context) -> Any:
        if callable(self.value):
            try:
                return self.value(self, current_time, **context)
            except TypeError:
                return self.value(self, current_time)
        return self.value

    def __post_init__(self):
        self.remaining_time = self.execution_time
        self._period = self.period if self.period is not None else 0.0
        self.absolute_arrival = self.arrival_time
        if self.deadline is not None:
            self.absolute_deadline = self.arrival_time + self.deadline
        elif self.period is not None:
            self.absolute_deadline = self.arrival_time + self.period
        else:
            self.absolute_deadline = float('inf')

    def laxity(self, current_time: float) -> float:
        if self.remaining_time <= 0:
            return float('inf')
        return self.absolute_deadline - current_time - self.remaining_time

    def copy(self) -> 'Task':
        t = Task(
            name=self.name,
            execution_time=self.execution_time,
            period=self.period,
            deadline=self.deadline,
            priority=self.priority,
            arrival_time=self.arrival_time,
            instance_id=self.instance_id,
            value=self.value,
        )
        t.remaining_time = self.remaining_time
        t.absolute_deadline = self.absolute_deadline
        t.absolute_arrival = self.absolute_arrival
        t._period = self._period
        return t

    def advance(self, dt: float) -> None:
        self.remaining_time -= dt

    def reset_for_next_period(self) -> 'Task':
        next_arrival = self.absolute_arrival + self._period
        new_deadline = next_arrival + (
            self.deadline if self.deadline is not None else (self._period or 0)
        )
        new_task = Task(
            name=self.name,
            execution_time=self.execution_time,
            period=self.period,
            deadline=self.deadline,
            priority=self.priority,
            arrival_time=next_arrival,
            instance_id=self.instance_id + 1,
            value=self.value,
        )
        new_task.absolute_arrival = next_arrival
        new_task.absolute_deadline = new_deadline
        new_task._period = self._period
        return new_task

    def is_periodic(self) -> bool:
        return self.period is not None and self.period > 0

    def __hash__(self):
        return hash((self.name, self.instance_id))

    def __eq__(self, other):
        if not isinstance(other, Task):
            return False
        return self.name == other.name and self.instance_id == other.instance_id

    def __lt__(self, other):
        if not isinstance(other, Task):
            return NotImplemented
        if self.absolute_arrival != other.absolute_arrival:
            return self.absolute_arrival < other.absolute_arrival
        if self.name != other.name:
            return self.name < other.name
        return self.instance_id < other.instance_id
