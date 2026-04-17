from typing import Optional, List
from collections import deque
from src.task import Task
from src.scheduler import ScheduleEvent, SchedulingResult, EventType, RunningTask
from src.registry import registry
from src.policy.templates.base import SchedulingPolicy, SchedulingContext
from src.dispatcher import Dispatcher, LoadBalancedDispatcher


def _create_policy_factory(strategy_name: str):
    strategy_def = registry.get(strategy_name)
    if strategy_def is None:
        raise ValueError(f"Strategy '{strategy_name}' not found. Available: {registry.list_names()}")
    
    stype = strategy_def.get("type")
    params = strategy_def.get("params", {})
    
    if stype == "round_robin":
        quantum = params.get("quantum", 1.0)
        from src.policy.rr import RoundRobinPolicy
        return lambda p: RoundRobinPolicy(quantum=quantum)
    elif stype == "fixed_priority":
        priority_key = strategy_def.get("priority_key", "priority")
        from src.policy.priority import FixedPriorityPolicy
        return lambda p: FixedPriorityPolicy(priority_key=priority_key)
    else:
        from src.policy.edf import EDFPolicy
        return lambda p: EDFPolicy()


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
        self.running_list: list[RunningTask] = []
        self.task_completion_times: dict = {}
        self.task_response_times: dict = {}
        self.task_start_times: dict = {}
        self.task_wait_times: dict = {}
        self.task_arrival_times: dict = {}
        self.preemption_count: int = 0
        self.context_switch_count: int = 0
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
        self._policy_factory = _create_policy_factory(strategy_name)

        if self.num_processors > 1:
            self.dispatcher: Dispatcher = LoadBalancedDispatcher(
                self.num_processors, 
                self._policy_factory,
                self.strategy_params
            )
            self.policies: List[SchedulingPolicy] = [c.policy for c in self.dispatcher.cores]
        else:
            self.policies: List[SchedulingPolicy] = [self._policy_factory(self.strategy_params)]
            self.dispatcher = None

    def _task_key(self, task: Task) -> tuple:
        return (task.name, task.instance_id)

    @property
    def current_policy(self) -> SchedulingPolicy:
        return self.policies[0] if self.policies else None

    def _arrive_tasks(self, until: float) -> None:
        for task in self._all_arrivals:
            key = self._task_key(task)
            if task.absolute_arrival <= until and key not in self.arrived_keys:
                self.arrived_keys.add(key)
                copy = task.copy()
                if key not in self.task_arrival_times:
                    self.task_arrival_times[key] = []
                self.task_arrival_times[key].append(copy.absolute_arrival)
                self.result.events.append(ScheduleEvent(
                    time=copy.absolute_arrival,
                    event_type=EventType.ARRIVAL,
                    task_name=copy.name,
                    details=f"Arrived at {copy.absolute_arrival:.4f}",
                ))
                
                if self.dispatcher:
                    self.dispatcher.dispatch_task(copy)
                else:
                    self.policies[0].add_task(copy)

    def _dispatch_to_policy(self, policy: SchedulingPolicy, copy: Task) -> None:
        policy.add_task(copy)

    def _get_policy_for_task(self, task: Task) -> Optional[SchedulingPolicy]:
        for policy in self.policies:
            for t in policy._queue:
                if t is task:
                    return policy
        return self.policies[0] if self.policies else None

    def _fill_processors(self) -> None:
        if self.dispatcher:
            for core in self.dispatcher.cores:
                if not core.running and core.policy.has_pending():
                    task = core.policy.select()
                    if task is None:
                        break
                    core.policy.remove_task(task)

                    key = self._task_key(task)
                    if key in self.task_arrival_times and self.task_arrival_times[key]:
                        arrival = self.task_arrival_times[key].pop(0)
                        wait = self.current_time - arrival
                        if key not in self.task_wait_times:
                            self.task_wait_times[key] = []
                        self.task_wait_times[key].append(wait)

                    rt = RunningTask(task=task, start_time=self.current_time)
                    if hasattr(core.policy, 'quantum'):
                        rt.quantum = core.policy.quantum
                        rt.quantum_expire_time = self.current_time + core.policy.quantum

                    self.running_list.append(rt)
                    core.running = True
                    core.current_task = task
                    self.context_switch_count += 1

                    if key not in self.task_start_times:
                        self.task_start_times[key] = self.current_time

                    self.result.events.append(ScheduleEvent(
                        time=self.current_time,
                        event_type=EventType.SCHEDULE,
                        task_name=task.name,
                        details=f"P{core.core_id} scheduled at {self.current_time:.4f}"
                    ))
        else:
            policy = self.policies[0]
            core_id = 0
            while policy.has_pending():
                task = policy.select()
                if task is None:
                    break
                policy.remove_task(task)

                key = self._task_key(task)
                if key in self.task_arrival_times and self.task_arrival_times[key]:
                    arrival = self.task_arrival_times[key].pop(0)
                    wait = self.current_time - arrival
                    if key not in self.task_wait_times:
                        self.task_wait_times[key] = []
                    self.task_wait_times[key].append(wait)

                rt = RunningTask(task=task, start_time=self.current_time)
                if hasattr(policy, 'quantum'):
                    rt.quantum = policy.quantum
                    rt.quantum_expire_time = self.current_time + policy.quantum

                self.running_list.append(rt)
                self.context_switch_count += 1

                if key not in self.task_start_times:
                    self.task_start_times[key] = self.current_time

                self.result.events.append(ScheduleEvent(
                    time=self.current_time,
                    event_type=EventType.SCHEDULE,
                    task_name=task.name,
                    details=f"P{core_id} scheduled at {self.current_time:.4f}"
                ))

    def _check_missed_deadlines(self) -> None:
        for policy in self.policies:
            for task in policy._queue:
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

            if rt.quantum_expire_time is not None:
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
            
            if self.dispatcher:
                for core in self.dispatcher.cores:
                    if core.current_task is task:
                        core.running = False
                        core.current_task = None
                        break

    def _process_quantum_expiries(self) -> None:
        expired = []
        for rt in self.running_list:
            if rt.quantum_expire_time is not None:
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
            policy = self._get_policy_for_task(task)
            if policy:
                policy.add_task(task)

    def _log_idle(self, dt: float) -> None:
        self.result.cpu_idle_time += dt * (self.num_processors - len(self.running_list))

    def _check_preemption(self) -> None:
        if not self.running_list:
            return

        preempted = []
        for rt in self.running_list:
            if rt.task.remaining_time <= 0:
                continue

            policy = self._get_policy_for_task(rt.task)
            if policy is None:
                continue

            context = SchedulingContext(
                current_time=self.current_time,
                cpu_id=0,
                running_task=rt.task,
                all_running=[r.task for r in self.running_list],
                ready_queue=policy._queue
            )

            if policy.requires_preemption(context):
                preempted.append(rt)

        for rt in preempted:
            if rt.task.remaining_time > 1e-9:
                self.running_list.remove(rt)
                task = rt.task
                self.result.events.append(ScheduleEvent(
                    time=self.current_time,
                    event_type=EventType.PREEMPT,
                    task_name=task.name,
                    details=f"Preempted at {self.current_time:.4f}",
                ))
                self.preemption_count += 1
                policy = self._get_policy_for_task(task)
                if policy:
                    policy.add_task(task)
                
                if self.dispatcher:
                    for core in self.dispatcher.cores:
                        if core.current_task is task:
                            core.running = False
                            core.current_task = None
                            break

    def _process_preemptions(self, next_time: float) -> None:
        preempted = []
        for rt in self.running_list:
            if rt.task.remaining_time <= 0:
                continue
            still_running = True
            for e in self.result.events[-10:]:
                if e.task_name == rt.task.name and e.event_type == EventType.SCHEDULE:
                    if e.time < next_time:
                        still_running = False
                        break
            if not still_running:
                preempted.append(rt)

        for rt in preempted:
            if rt.task.remaining_time > 1e-9:
                self.running_list.remove(rt)
                task = rt.task
                self.result.events.append(ScheduleEvent(
                    time=self.current_time,
                    event_type=EventType.PREEMPT,
                    task_name=task.name,
                    details=f"Preempted at {self.current_time:.4f}",
                ))
                self.preemption_count += 1
                policy = self._get_policy_for_task(task)
                if policy:
                    policy.add_task(task)

    def _has_pending_tasks(self) -> bool:
        if self.dispatcher:
            return self.dispatcher.total_pending() > 0
        return any(p.has_pending() for p in self.policies)

    def run(self) -> SchedulingResult:
        self.current_time = self.start
        self._arrive_tasks(self.current_time)

        self._fill_processors()

        while self.current_time < self.end:
            if not self.running_list and not self._has_pending_tasks():
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
            if idle_slots > 0 and self._has_pending_tasks():
                idle_dt = next_event_time - self.current_time
                self._log_idle(idle_dt)

            self._advance(next_event_time)

            self._process_completions()
            self._process_quantum_expiries()

            self._arrive_tasks(self.current_time)
            self._check_missed_deadlines()
            self._check_preemption()
            self._fill_processors()

        self.result.task_response_times = dict(self.task_response_times)
        self.result.task_completion_times = dict(self.task_completion_times)
        self.result.task_wait_times = dict(self.task_wait_times)
        self.result.task_arrival_times = dict(self.task_arrival_times)
        self.result.preemption_count = self.preemption_count
        self.result.context_switch_count = self.context_switch_count
        return self.result