from __future__ import annotations

from typing import Optional

from src.core.registry import registry
from src.core.task import Task
from src.policy.templates.base import SchedulingContext, SchedulingPolicy
from src.sim.interfaces import SchedulerEngine
from src.sim.policy_factory import create_policy
from src.sim.scheduler import EventType, RunningTask, ScheduleEvent, SchedulingResult


class SingleCoreEngine(SchedulerEngine):
    """Single-core, event-driven simulation engine."""

    EPSILON = 1e-9

    def __init__(
        self,
        tasks,
        start: float,
        end: float,
        strategy_name: str,
        strategy_params: Optional[dict] = None,
        num_processors: int = 1,
        preemptive: bool = True,
    ):
        if num_processors != 1:
            raise NotImplementedError(
                "SingleCoreEngine only supports num_processors=1."
            )
        self.tasks = list(tasks)
        self.start = start
        self.end = end
        self.strategy_name = strategy_name
        self.strategy_params = strategy_params or {}
        self.num_processors = num_processors
        self.preemptive = preemptive

        self.result = SchedulingResult()
        self.result.total_time = end - start

        self.current_time = start
        self.running_task: Optional[RunningTask] = None
        self.task_completion_times: dict = {}
        self.task_response_times: dict = {}
        self.task_start_times: dict = {}
        self.task_wait_times: dict = {}
        self.task_arrival_times: dict = {}
        self.preemption_count: int = 0
        self.context_switch_count: int = 0
        self.arrived_keys: set = set()
        self.missed_keys: set = set()
        self._pending_arrivals: list[Task] = sorted(
            list(tasks),
            key=lambda t: (t.absolute_arrival, t.name, t.instance_id),
            reverse=True,
        )

        strategy_def = registry.get(strategy_name)
        if strategy_def is None:
            raise ValueError(f"Strategy '{strategy_name}' not found. Available: {registry.list_names()}")
        ok, msg = registry.validate(strategy_name)
        if not ok:
            raise ValueError(msg)
        self.stype = strategy_def["type"]
        self.policy: SchedulingPolicy = create_policy(strategy_name, self.strategy_params)

    def _enqueue_future_arrival(self, task: Task) -> None:
        insert_at = 0
        task_key = (task.absolute_arrival, task.name, task.instance_id)
        while insert_at < len(self._pending_arrivals):
            prev = self._pending_arrivals[insert_at]
            prev_key = (prev.absolute_arrival, prev.name, prev.instance_id)
            if prev_key <= task_key:
                break
            insert_at += 1
        self._pending_arrivals.insert(insert_at, task)

    @staticmethod
    def _task_key(task: Task) -> tuple:
        return (task.name, task.instance_id)

    def _sync_policy_time(self, current_time: float) -> None:
        try:
            self.policy.set_current_time(current_time)
        except Exception:
            pass

    def _record_arrival(self, task: Task) -> None:
        key = self._task_key(task)
        self.arrived_keys.add(key)
        task_copy = task.copy()
        self.task_arrival_times.setdefault(key, []).append(task_copy.absolute_arrival)
        self.result.events.append(
            ScheduleEvent(
                time=task_copy.absolute_arrival,
                event_type=EventType.ARRIVAL,
                task_name=task_copy.name,
                details=f"Arrived at {int(task_copy.absolute_arrival)}",
            )
        )
        if task_copy.absolute_deadline < float("inf") and task_copy.absolute_deadline <= self.end:
            self.result.events.append(
                ScheduleEvent(
                    time=task_copy.absolute_deadline,
                    event_type=EventType.DEADLINE,
                    task_name=task_copy.name,
                    details=f"Deadline at {int(task_copy.absolute_deadline)} (instance={task_copy.instance_id})",
                )
            )
        self.policy.add_task(task_copy)
        if task.is_periodic():
            next_task = task.reset_for_next_period()
            if next_task.absolute_arrival < self.end - self.EPSILON:
                self._enqueue_future_arrival(next_task)

    def _arrive_tasks(self, until: float) -> None:
        self._sync_policy_time(until)
        while self._pending_arrivals and self._pending_arrivals[-1].absolute_arrival <= until + self.EPSILON:
            task = self._pending_arrivals.pop()
            key = self._task_key(task)
            if key in self.arrived_keys:
                continue
            self._record_arrival(task)

    def _schedule_if_idle(self) -> None:
        if self.running_task is not None or not self.policy.has_pending():
            return
        self._sync_policy_time(self.current_time)
        task = self.policy.select()
        if task is None:
            return
        self.policy.remove_task(task)
        key = self._task_key(task)
        arrivals = self.task_arrival_times.get(key, [])
        if arrivals:
            arrival = arrivals.pop(0)
            self.task_wait_times.setdefault(key, []).append(self.current_time - arrival)

        rt = RunningTask(task=task, start_time=self.current_time)
        if hasattr(self.policy, "quantum"):
            rt.quantum = self.policy.quantum
            rt.quantum_expire_time = self.current_time + self.policy.quantum
        self.running_task = rt
        self.context_switch_count += 1
        self.task_start_times.setdefault(key, self.current_time)
        self.result.events.append(
            ScheduleEvent(
                time=self.current_time,
                event_type=EventType.SCHEDULE,
                task_name=task.name,
                details=f"Scheduled at {int(self.current_time)}",
            )
        )

    def _check_missed_deadlines(self) -> None:
        self._sync_policy_time(self.current_time)
        candidates = list(self.policy.get_ready_queue())
        if self.running_task is not None:
            candidates.append(self.running_task.task)
        for task in candidates:
            key = self._task_key(task)
            if key in self.task_completion_times or key in self.missed_keys:
                continue
            if task.absolute_deadline < self.current_time - self.EPSILON:
                self.missed_keys.add(key)
                self.result.missed_deadlines.append(f"{task.name}#{task.instance_id}")
                self.result.events.append(
                    ScheduleEvent(
                        time=task.absolute_deadline,
                        event_type=EventType.DEADLINE_MISS,
                        task_name=task.name,
                        details=f"Missed deadline at {int(task.absolute_deadline)} (instance={task.instance_id})",
                    )
                )

    def _find_next_event_time(self) -> float:
        next_time = self.end
        if self.running_task is not None:
            remaining = self.running_task.task.remaining_time
            next_time = min(next_time, self.current_time + remaining)
            if self.running_task.quantum_expire_time is not None:
                next_time = min(next_time, self.running_task.quantum_expire_time)
        next_arrival = self._pending_arrivals[-1].absolute_arrival if self._pending_arrivals else self.end
        return min(next_time, next_arrival)

    def _advance(self, next_time: float) -> None:
        dt = next_time - self.current_time
        if self.running_task is not None:
            self.running_task.task.advance(dt)
            self.running_task.start_time = self.current_time
        self.current_time = next_time

    def _process_completion(self) -> None:
        if self.running_task is None or self.running_task.task.remaining_time > self.EPSILON:
            return
        task = self.running_task.task
        self.running_task = None
        key = self._task_key(task)
        if (
            task.absolute_deadline < self.current_time - self.EPSILON
            and key not in self.missed_keys
        ):
            self.missed_keys.add(key)
            self.result.missed_deadlines.append(f"{task.name}#{task.instance_id}")
            self.result.events.append(
                ScheduleEvent(
                    time=task.absolute_deadline,
                    event_type=EventType.DEADLINE_MISS,
                    task_name=task.name,
                    details=f"Missed deadline at {int(task.absolute_deadline)} (instance={task.instance_id})",
                )
            )
        self.result.events.append(
            ScheduleEvent(
                time=self.current_time,
                event_type=EventType.COMPLETE,
                task_name=task.name,
                details="Completed",
            )
        )
        self.result.completed_tasks.append(task.name)
        self.task_completion_times[key] = self.current_time
        self.task_response_times[key] = self.current_time - task.absolute_arrival

    def _process_quantum_expiry(self) -> None:
        if self.running_task is None or self.running_task.quantum_expire_time is None:
            return
        if self.current_time < self.running_task.quantum_expire_time - self.EPSILON:
            return
        task = self.running_task.task
        self.running_task = None
        self.result.events.append(
            ScheduleEvent(
                time=self.current_time,
                event_type=EventType.QUANTUM_EXPIRE,
                task_name=task.name,
                details=f"Quantum expired at {int(self.current_time)}",
            )
        )
        self.policy.add_task(task)

    def _check_preemption(self) -> None:
        if not self.preemptive:
            return
        if self.running_task is None or self.running_task.task.remaining_time <= self.EPSILON:
            return
        self._sync_policy_time(self.current_time)
        context = SchedulingContext(
            current_time=self.current_time,
            cpu_id=0,
            running_task=self.running_task.task,
            all_running=[self.running_task.task],
            ready_queue=self.policy.get_ready_queue(),
        )
        if not self.policy.requires_preemption(context):
            return
        task = self.running_task.task
        self.running_task = None
        self.result.events.append(
            ScheduleEvent(
                time=self.current_time,
                event_type=EventType.PREEMPT,
                task_name=task.name,
                details=f"Preempted at {int(self.current_time)}",
            )
        )
        self.preemption_count += 1
        self.policy.add_task(task)

    def _has_pending_work(self) -> bool:
        return self.running_task is not None or self.policy.has_pending()

    def run(self) -> SchedulingResult:
        self.current_time = self.start
        self._arrive_tasks(self.current_time)
        self._schedule_if_idle()

        while self.current_time < self.end:
            if not self._has_pending_work():
                next_arrival = self._pending_arrivals[-1].absolute_arrival if self._pending_arrivals else self.end
                idle_to = min(next_arrival, self.end)
                if idle_to > self.current_time:
                    self.result.cpu_idle_time += idle_to - self.current_time
                self.current_time = idle_to
                if self.current_time >= self.end:
                    break
                self._arrive_tasks(self.current_time)
                self._schedule_if_idle()
                continue

            next_event_time = min(self._find_next_event_time(), self.end)
            self._advance(next_event_time)
            self._process_completion()
            self._process_quantum_expiry()
            self._arrive_tasks(self.current_time)
            self._check_missed_deadlines()
            self._check_preemption()
            self._schedule_if_idle()

        self.result.task_response_times = dict(self.task_response_times)
        self.result.task_completion_times = dict(self.task_completion_times)
        self.result.task_wait_times = dict(self.task_wait_times)
        self.result.task_arrival_times = dict(self.task_arrival_times)
        self.result.preemption_count = self.preemption_count
        self.result.context_switch_count = self.context_switch_count
        return self.result

