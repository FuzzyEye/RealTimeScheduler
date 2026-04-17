from typing import Optional
from collections import deque
from src.task import Task
from src.scheduler import ScheduleEvent, SchedulingResult, EventType, RunningTask
from src.registry import registry


class SimulationEngine:
    def __init__(
        self,
        tasks,
        start: float,
        end: float,
        strategy_name: str,
        strategy_params: Optional[dict] = None,
        num_processors: int = 1,
    ):
        self.tasks = list(tasks)
        self.start = start
        self.end = end
        self.strategy_name = strategy_name
        self.strategy_params = strategy_params or {}
        self.num_processors = num_processors

        self.result = SchedulingResult()
        self.result.total_time = end - start

        self.current_time = start
        self.ready_queue: list[Task] = []
        self.rr_deque: deque[Task] = deque()
        self.running_list: list[RunningTask] = []
        self.task_completion_times: dict = {}
        self.task_response_times: dict = {}
        self.task_start_times: dict = {}
        self.arrived_keys: set = set()
        self._all_arrivals: list[Task] = list(tasks)

        strategy_def = registry.get(strategy_name)
        if strategy_def is None:
            raise ValueError(
                f"Strategy '{strategy_name}' not found. "
                f"Available: {registry.list_names()}"
            )

        ok, msg = registry.validate(strategy_name)
        if not ok:
            raise ValueError(msg)

        self.stype = strategy_def["type"]

        if self.stype == "round_robin":
            self.quantum = strategy_def.get("params", {}).get("quantum", 1.0)
            self._use_rr = True
        else:
            self.selector_fn = registry.build_selector(self.strategy_name)
            self._use_rr = False
            self.quantum = None

    def _task_key(self, task: Task) -> tuple:
        return (task.name, task.instance_id)

    def _arrive_tasks(self, until: float) -> None:
        for task in self._all_arrivals:
            key = self._task_key(task)
            if task.absolute_arrival <= until and key not in self.arrived_keys:
                self.arrived_keys.add(key)
                copy = task.copy()
                if self._use_rr:
                    self.rr_deque.append(copy)
                else:
                    self.ready_queue.append(copy)

    def _fill_processors(self) -> None:
        available_slots = self.num_processors - len(self.running_list)
        while available_slots > 0 and (self.ready_queue or self.rr_deque):
            task = None
            if self._use_rr:
                if self.rr_deque:
                    task = self.rr_deque.popleft()
            else:
                if self.ready_queue:
                    selected = self.selector_fn(self.ready_queue, self.current_time)
                    if selected:
                        self.ready_queue.remove(selected)
                        task = selected

            if task is None:
                break

            rt = RunningTask(task=task, start_time=self.current_time)
            if self._use_rr:
                rt.quantum = self.quantum
                rt.quantum_expire_time = self.current_time + self.quantum

            self.running_list.append(rt)
            available_slots -= 1

            key = self._task_key(task)
            if key not in self.task_start_times:
                self.task_start_times[key] = self.current_time

            self.result.events.append(ScheduleEvent(
                time=self.current_time,
                event_type=EventType.SCHEDULE,
                task_name=task.name,
                details=f"P{len(self.running_list)} scheduled at {self.current_time:.4f}"
            ))

        if available_slots > 0 and not (self.ready_queue or self.rr_deque):
            pass

    def _check_missed_deadlines(self) -> None:
        all_queue = list(self.rr_deque) if self._use_rr else list(self.ready_queue)
        for task in all_queue:
            key = self._task_key(task)
            if key not in self.task_completion_times:
                if task.absolute_deadline < self.current_time:
                    self.result.missed_deadlines.append(task.name)
                    self.result.events.append(ScheduleEvent(
                        time=task.absolute_deadline,
                        event_type=EventType.DEADLINE_MISS,
                        task_name=task.name,
                        details=f"Missed deadline at {task.absolute_deadline:.4f}",
                    ))
                    self.task_completion_times[key] = task.absolute_deadline

    def _find_next_event_time(self) -> float:
        next_time = self.end

        for rt in self.running_list:
            remaining = rt.task.remaining_time
            complete_at = self.current_time + remaining
            next_time = min(next_time, complete_at)

            if self._use_rr and rt.quantum_expire_time is not None:
                next_time = min(next_time, rt.quantum_expire_time)

        next_arrival = min(
            (t.absolute_arrival for t in self._all_arrivals
             if self._task_key(t) not in self.arrived_keys),
            default=self.end,
        )
        next_time = min(next_time, next_arrival)

        return next_time

    def _advance(self, next_time: float) -> None:
        dt = next_time - self.current_time
        for rt in self.running_list:
            rt.task.advance(dt)
            rt.start_time = self.current_time
        self.current_time = next_time

    def _process_completions(self) -> None:
        completed = []
        for rt in self.running_list:
            if rt.task.remaining_time <= 1e-9:
                completed.append(rt)

        for rt in completed:
            self.running_list.remove(rt)
            task = rt.task
            self.result.events.append(ScheduleEvent(
                time=self.current_time,
                event_type=EventType.COMPLETE,
                task_name=task.name,
                details="Completed",
            ))
            self.result.completed_tasks.append(task.name)
            key = self._task_key(task)
            self.task_completion_times[key] = self.current_time
            self.task_response_times[key] = self.current_time - task.absolute_arrival

    def _process_quantum_expiries(self) -> None:
        expired = []
        for rt in self.running_list:
            if self._use_rr and rt.quantum_expire_time is not None:
                if self.current_time >= rt.quantum_expire_time - 1e-9:
                    expired.append(rt)

        for rt in expired:
            self.running_list.remove(rt)
            task = rt.task
            self.result.events.append(ScheduleEvent(
                time=self.current_time,
                event_type=EventType.QUANTUM_EXPIRE,
                task_name=task.name,
                details=f"Quantum expired at {self.current_time:.4f}",
            ))
            self.rr_deque.append(task)

    def _log_idle(self, dt: float) -> None:
        self.result.cpu_idle_time += dt * (self.num_processors - len(self.running_list))

    def run(self) -> SchedulingResult:
        self.current_time = self.start
        self._arrive_tasks(self.current_time)

        self._fill_processors()

        while self.current_time < self.end:
            if not self.running_list and not self.ready_queue and not self.rr_deque:
                next_arrival = min(
                    (t.absolute_arrival for t in self._all_arrivals
                     if self._task_key(t) not in self.arrived_keys),
                    default=self.end,
                )
                if next_arrival < self.end:
                    idle_dt = next_arrival - self.current_time
                    self._log_idle(idle_dt)
                    self.current_time = next_arrival
                    self._arrive_tasks(self.current_time)
                    self._fill_processors()
                else:
                    idle_dt = self.end - self.current_time
                    self._log_idle(idle_dt)
                    self.current_time = self.end
                    break
                continue

            next_event_time = self._find_next_event_time()
            next_event_time = min(next_event_time, self.end)

            idle_slots = self.num_processors - len(self.running_list)
            if idle_slots > 0 and (self.ready_queue or self.rr_deque):
                idle_dt = next_event_time - self.current_time
                self._log_idle(idle_dt)

            self._advance(next_event_time)

            self._process_completions()
            self._process_quantum_expiries()

            self._arrive_tasks(self.current_time)
            self._check_missed_deadlines()
            self._fill_processors()

        self.result.task_response_times = dict(self.task_response_times)
        return self.result
