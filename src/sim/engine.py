from __future__ import annotations

import heapq
from dataclasses import dataclass
from typing import Optional

from src.core.registry import registry
from src.core.task import Task
from src.policy.templates.base import SchedulingContext, SchedulingPolicy
from src.sim.interfaces import SchedulerEngine
from src.sim.policy_factory import create_policy
from src.sim.scheduler import EventType, RunningTask, ScheduleEvent, SchedulingResult


@dataclass
class CPUCore:
    core_id: int
    running: Optional[RunningTask] = None
    run_token: int = 0


class SingleCoreEngine(SchedulerEngine):
    """Discrete-event scheduling engine with multi-core capable state model."""

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
        self.tasks = list(tasks)
        self.start = start
        self.end = end
        self.strategy_name = strategy_name
        self.strategy_params = strategy_params or {}
        self.num_processors = max(1, int(num_processors))
        self.preemptive = preemptive

        self.result = SchedulingResult()
        self.result.total_time = end - start

        self.current_time = start
        self.cores = [CPUCore(core_id=i) for i in range(self.num_processors)]
        self.task_completion_times: dict = {}
        self.task_response_times: dict = {}
        self.task_start_times: dict = {}
        self.task_wait_times: dict = {}
        self.task_arrival_times: dict = {}
        self.preemption_count: int = 0
        self.context_switch_count: int = 0
        self.arrived_keys: set = set()
        self.missed_keys: set = set()
        self._event_queue: list[tuple[float, int, str, dict]] = []
        self._event_counter = 0
        self._last_event_time = self.start

        strategy_def = registry.get(strategy_name)
        if strategy_def is None:
            raise ValueError(f"Strategy '{strategy_name}' not found. Available: {registry.list_names()}")
        ok, msg = registry.validate(strategy_name)
        if not ok:
            raise ValueError(msg)
        self.stype = strategy_def["type"]
        self.policy: SchedulingPolicy = create_policy(strategy_name, self.strategy_params)

    @staticmethod
    def _task_key(task: Task) -> tuple:
        return (task.name, task.instance_id)

    def _sync_policy_time(self, current_time: float) -> None:
        try:
            self.policy.set_current_time(current_time)
        except Exception:
            pass

    def _push_event(self, at: float, event_type: str, payload: dict) -> None:
        if at > self.end + self.EPSILON:
            return
        heapq.heappush(self._event_queue, (at, self._event_counter, event_type, payload))
        self._event_counter += 1

    def _advance_time(self, new_time: float) -> None:
        if new_time <= self.current_time + self.EPSILON:
            self.current_time = max(self.current_time, new_time)
            return
        dt = new_time - self.current_time
        running_count = 0
        for core in self.cores:
            if core.running is None:
                continue
            core.running.task.advance(dt)
            core.running.start_time = self.current_time
            running_count += 1
        idle_cores = self.num_processors - running_count
        if idle_cores > 0:
            self.result.cpu_idle_time += dt * idle_cores
        self.current_time = new_time

    def _enqueue_periodic_next(self, task: Task) -> None:
        if not task.is_periodic():
            return
        next_task = task.reset_for_next_period()
        if next_task.absolute_arrival < self.end - self.EPSILON:
            self._push_event(next_task.absolute_arrival, "arrival", {"task": next_task})

    def _record_arrival(self, task: Task) -> None:
        key = self._task_key(task)
        if key in self.arrived_keys:
            return
        self.arrived_keys.add(key)
        task_copy = task.copy()
        self.task_arrival_times.setdefault(key, []).append(task_copy.absolute_arrival)
        self.result.events.append(
            ScheduleEvent(
                time=self.current_time,
                event_type=EventType.ARRIVAL,
                task_name=task_copy.name,
                details=f"Arrived at {self.current_time:.4f}",
            )
        )
        if task_copy.absolute_deadline < float("inf") and task_copy.absolute_deadline <= self.end + self.EPSILON:
            self.result.events.append(
                ScheduleEvent(
                    time=task_copy.absolute_deadline,
                    event_type=EventType.DEADLINE,
                    task_name=task_copy.name,
                    details=f"Deadline at {task_copy.absolute_deadline:.4f} (instance={task_copy.instance_id})",
                )
            )
        self.policy.add_task(task_copy)
        self._enqueue_periodic_next(task)

    def _schedule_on_core(self, core: CPUCore, task: Task) -> None:
        key = self._task_key(task)
        arrivals = self.task_arrival_times.get(key, [])
        if arrivals:
            arrival = arrivals.pop(0)
            self.task_wait_times.setdefault(key, []).append(self.current_time - arrival)

        rt = RunningTask(task=task, start_time=self.current_time)
        if hasattr(self.policy, "quantum"):
            rt.quantum = float(getattr(self.policy, "quantum"))
            rt.quantum_expire_time = self.current_time + rt.quantum

        core.running = rt
        core.run_token += 1
        token = core.run_token
        self.context_switch_count += 1
        self.task_start_times.setdefault(key, self.current_time)
        self.result.events.append(
            ScheduleEvent(
                time=self.current_time,
                event_type=EventType.SCHEDULE,
                task_name=task.name,
                details=f"P{core.core_id + 1} scheduled at {self.current_time:.4f}",
            )
        )
        self._push_event(
            self.current_time + task.remaining_time,
            "completion",
            {"core_id": core.core_id, "token": token},
        )
        if rt.quantum_expire_time is not None:
            self._push_event(
                rt.quantum_expire_time,
                "quantum_expire",
                {"core_id": core.core_id, "token": token},
            )

    def _fill_idle_cores(self) -> None:
        self._sync_policy_time(self.current_time)
        for core in self.cores:
            if core.running is not None or not self.policy.has_pending():
                continue
            task = self.policy.select()
            if task is None:
                continue
            self.policy.remove_task(task)
            self._schedule_on_core(core, task)

    def _check_missed_deadlines(self) -> None:
        self._sync_policy_time(self.current_time)
        candidates = list(self.policy.get_ready_queue())
        for core in self.cores:
            if core.running is not None:
                candidates.append(core.running.task)
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
                        details=f"Missed deadline at {task.absolute_deadline:.4f} (instance={task.instance_id})",
                    )
                )

    def _check_preemption(self) -> None:
        if not self.preemptive:
            return
        self._sync_policy_time(self.current_time)
        running_tasks = [c.running.task for c in self.cores if c.running is not None]
        for core in self.cores:
            if core.running is None or core.running.task.remaining_time <= self.EPSILON:
                continue
            context = SchedulingContext(
                current_time=self.current_time,
                cpu_id=core.core_id,
                running_task=core.running.task,
                all_running=running_tasks,
                ready_queue=self.policy.get_ready_queue(),
            )
            if not self.policy.requires_preemption(context):
                continue
            task = core.running.task
            core.running = None
            core.run_token += 1
            self.result.events.append(
                ScheduleEvent(
                    time=self.current_time,
                    event_type=EventType.PREEMPT,
                    task_name=task.name,
                    details=f"P{core.core_id + 1} preempted at {self.current_time:.4f}",
                )
            )
            self.preemption_count += 1
            self.policy.add_task(task)

    def _handle_completion(self, payload: dict) -> None:
        core = self.cores[payload["core_id"]]
        if payload["token"] != core.run_token or core.running is None:
            return
        if core.running.task.remaining_time > self.EPSILON:
            return
        task = core.running.task
        core.running = None
        core.run_token += 1
        key = self._task_key(task)
        if task.absolute_deadline < self.current_time - self.EPSILON and key not in self.missed_keys:
            self.missed_keys.add(key)
            self.result.missed_deadlines.append(f"{task.name}#{task.instance_id}")
            self.result.events.append(
                ScheduleEvent(
                    time=task.absolute_deadline,
                    event_type=EventType.DEADLINE_MISS,
                    task_name=task.name,
                    details=f"Missed deadline at {task.absolute_deadline:.4f} (instance={task.instance_id})",
                )
            )
        self.result.events.append(
            ScheduleEvent(
                time=self.current_time,
                event_type=EventType.COMPLETE,
                task_name=task.name,
                details=f"Completed on P{core.core_id + 1}",
            )
        )
        self.result.completed_tasks.append(task.name)
        self.task_completion_times[key] = self.current_time
        self.task_response_times[key] = self.current_time - task.absolute_arrival

    def _handle_quantum_expire(self, payload: dict) -> None:
        core = self.cores[payload["core_id"]]
        if payload["token"] != core.run_token or core.running is None:
            return
        rt = core.running
        if rt.quantum_expire_time is None:
            return
        if self.current_time < rt.quantum_expire_time - self.EPSILON:
            return
        task = rt.task
        core.running = None
        core.run_token += 1
        self.result.events.append(
            ScheduleEvent(
                time=self.current_time,
                event_type=EventType.QUANTUM_EXPIRE,
                task_name=task.name,
                details=f"P{core.core_id + 1} quantum expired at {self.current_time:.4f}",
            )
        )
        self.policy.add_task(task)

    def _process_event(self, event_type: str, payload: dict) -> None:
        if event_type == "arrival":
            self._record_arrival(payload["task"])
        elif event_type == "completion":
            self._handle_completion(payload)
        elif event_type == "quantum_expire":
            self._handle_quantum_expire(payload)

    def _has_running(self) -> bool:
        return any(core.running is not None for core in self.cores)

    def run(self) -> SchedulingResult:
        self.current_time = self.start
        self._last_event_time = self.start
        for task in self.tasks:
            if task.absolute_arrival < self.end + self.EPSILON:
                self._push_event(task.absolute_arrival, "arrival", {"task": task})

        while self._event_queue and self.current_time < self.end + self.EPSILON:
            at, _, event_type, payload = heapq.heappop(self._event_queue)
            if at > self.end + self.EPSILON:
                break
            self._advance_time(at)
            self._process_event(event_type, payload)
            self._check_missed_deadlines()
            self._check_preemption()
            self._fill_idle_cores()
            self._last_event_time = self.current_time

        self._advance_time(self.end)
        self._check_missed_deadlines()

        self.result.task_response_times = dict(self.task_response_times)
        self.result.task_completion_times = dict(self.task_completion_times)
        self.result.task_wait_times = dict(self.task_wait_times)
        self.result.task_arrival_times = dict(self.task_arrival_times)
        self.result.preemption_count = self.preemption_count
        self.result.context_switch_count = self.context_switch_count
        return self.result

