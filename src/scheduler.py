from typing import List, Optional, Callable, Any
from dataclasses import dataclass, field
from enum import Enum


class EventType(Enum):
    ARRIVAL = "arrival"
    SCHEDULE = "schedule"
    PREEMPT = "preempt"
    COMPLETE = "complete"
    DEADLINE_MISS = "deadline_miss"
    QUANTUM_EXPIRE = "quantum_expire"
    IDLE = "idle"


@dataclass
class ScheduleEvent:
    time: float
    event_type: EventType
    task_name: str
    details: str = ""


@dataclass
class SchedulingResult:
    events: List[ScheduleEvent] = field(default_factory=list)
    completed_tasks: List[str] = field(default_factory=list)
    missed_deadlines: List[str] = field(default_factory=list)
    cpu_idle_time: float = 0.0
    total_time: float = 0.0
    task_response_times: dict = field(default_factory=dict)

    def cpu_utilization(self) -> float:
        if self.total_time <= 0:
            return 0.0
        return (self.total_time - self.cpu_idle_time) / self.total_time * 100.0

    def throughput(self) -> int:
        return len(self.completed_tasks)

    def deadline_miss_count(self) -> int:
        return len(self.missed_deadlines)


@dataclass
class RunningTask:
    task: 'Task'
    start_time: float
    quantum: Optional[float] = None
    quantum_expire_time: Optional[float] = None
    preempted: bool = False
