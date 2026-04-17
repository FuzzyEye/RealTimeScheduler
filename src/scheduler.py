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
    DEADLINE = "deadline"


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
    task_completion_times: dict = field(default_factory=dict)
    task_wait_times: dict = field(default_factory=dict)
    task_arrival_times: dict = field(default_factory=dict)
    preemption_count: int = 0
    context_switch_count: int = 0

    def cpu_utilization(self) -> float:
        if self.total_time <= 0:
            return 0.0
        return (self.total_time - self.cpu_idle_time) / self.total_time * 100.0

    def throughput(self) -> int:
        return len(self.completed_tasks)

    def deadline_miss_count(self) -> int:
        return len(self.missed_deadlines)

    def waiting_time_avg(self) -> float:
        if not self.task_wait_times:
            return 0.0
        all_waits = []
        for waits in self.task_wait_times.values():
            all_waits.extend(waits)
        return sum(all_waits) / len(all_waits) if all_waits else 0.0

    def waiting_time_max(self) -> float:
        if not self.task_wait_times:
            return 0.0
        all_waits = []
        for waits in self.task_wait_times.values():
            all_waits.extend(waits)
        return max(all_waits) if all_waits else 0.0

    def response_time_avg(self) -> float:
        if not self.task_response_times:
            return 0.0
        return sum(self.task_response_times.values()) / len(self.task_response_times)

    def response_time_max(self) -> float:
        if not self.task_response_times:
            return 0.0
        return max(self.task_response_times.values())

    def response_time_min(self) -> float:
        if not self.task_response_times:
            return 0.0
        return min(self.task_response_times.values())

    def response_time_jitter(self) -> float:
        if not self.task_response_times or len(self.task_response_times) < 2:
            return 0.0
        values = list(self.task_response_times.values())
        avg = sum(values) / len(values)
        variance = sum((x - avg) ** 2 for x in values) / len(values)
        return variance ** 0.5

    def lateness(self) -> float:
        lateness = 0.0
        for task_name, times in self.task_completion_times.items():
            if isinstance(task_name, tuple) and len(task_name) >= 2:
                name, instance = task_name[0], task_name[1]
                for event in self.events:
                    if event.task_name == name and event.event_type.value == "schedule":
                        deadline = event.time
                        for comp_time in ([times] if isinstance(times, float) else times):
                            lateness = max(lateness, comp_time - deadline)
        return lateness


@dataclass
class RunningTask:
    task: 'Task'
    start_time: float
    quantum: Optional[float] = None
    quantum_expire_time: Optional[float] = None
    preempted: bool = False
