from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
from src.policy.templates.base import SchedulingPolicy, SchedulingContext


@dataclass
class CPUCore:
    core_id: int
    policy: SchedulingPolicy
    current_task: Optional[Any] = None
    running: bool = False


class Dispatcher:
    def __init__(self, num_cores: int, policy_factory: Any, policy_params: Optional[Dict] = None):
        self.num_cores = num_cores
        self.policy_factory = policy_factory
        self.policy_params = policy_params or {}
        self.cores: List[CPUCore] = []
        self._initialize_cores()

    def _initialize_cores(self) -> None:
        for i in range(self.num_cores):
            policy = self.policy_factory(self.policy_params)
            self.cores.append(CPUCore(core_id=i, policy=policy))

    def get_core(self, core_id: int) -> Optional[CPUCore]:
        return self.cores[core_id] if 0 <= core_id < self.num_cores else None

    def get_available_core(self) -> Optional[CPUCore]:
        for core in self.cores:
            if not core.running:
                return core
        return None

    def dispatch_task(self, task: Any) -> Optional[int]:
        core = self.get_available_core()
        if core is None:
            return None
        core.policy.add_task(task)
        return core.core_id

    def dispatch_tasks(self, tasks: List[Any]) -> Dict[int, List[Any]]:
        results = {i: [] for i in range(self.num_cores)}
        for task in tasks:
            core_id = self.dispatch_task(task)
            if core_id is not None:
                results[core_id].append(task)
        return results

    def get_next_task(self, core_id: int) -> Optional[Any]:
        core = self.get_core(core_id)
        if core is None:
            return None
        return core.policy.select()

    def schedule(self) -> Dict[int, Optional[Any]]:
        schedule_map = {}
        for core in self.cores:
            if not core.running and core.policy.has_pending():
                task = core.policy.select()
                if task is not None:
                    schedule_map[core.core_id] = task
                    core.policy.remove_task(task)
        return schedule_map

    def check_preemptions(self, current_time: float) -> List[tuple]:
        preemptions = []
        for core in self.cores:
            if core.current_task is not None:
                context = SchedulingContext(
                    current_time=current_time,
                    cpu_id=core.core_id,
                    running_task=core.current_task,
                    all_running=[c.current_task for c in self.cores if c.current_task is not None]
                )
                if core.policy.requires_preemption(context):
                    preemptions.append((core.core_id, core.current_task))
                    core.current_task = None
                    core.running = False
        return preemptions

    def get_load(self) -> Dict[int, int]:
        return {i: c.policy.task_count() for i, c in enumerate(self.cores)}

    def total_pending(self) -> int:
        return sum(c.policy.task_count() for c in self.cores)

    def is_idle(self) -> bool:
        return all(not c.running and not c.policy.has_pending() for c in self.cores)

    def get_policy(self, core_id: int) -> Optional[SchedulingPolicy]:
        core = self.get_core(core_id)
        return core.policy if core else None


class LoadBalancedDispatcher(Dispatcher):
    def __init__(self, num_cores: int, policy_factory: Any, policy_params: Optional[Dict] = None, strategy: str = "least_loaded"):
        self.strategy = strategy
        super().__init__(num_cores, policy_factory, policy_params)

    def get_available_core(self) -> Optional[CPUCore]:
        if self.strategy == "least_loaded":
            return min(self.cores, key=lambda c: c.policy.task_count())
        elif self.strategy == "round_robin":
            for core in self.cores:
                if not core.running:
                    return core
            return self.cores[0]
        else:
            return super().get_available_core()


class AffinityAwareDispatcher(Dispatcher):
    def __init__(self, num_cores: int, policy_factory: Any, policy_params: Optional[Dict] = None):
        super().__init__(num_cores, policy_factory, policy_params)
        self.task_affinity: Dict[str, int] = {}

    def dispatch_task(self, task: Any, preferred_core: Optional[int] = None) -> Optional[int]:
        if preferred_core is not None:
            core = self.get_core(preferred_core)
            if core and not core.running:
                core.policy.add_task(task)
                return core.core_id
        task_key = f"{task.name}:{getattr(task, 'instance_id', 0)}"
        if task_key in self.task_affinity:
            core_id = self.task_affinity[task_key]
            core = self.get_core(core_id)
            if core and not core.running:
                core.policy.add_task(task)
                return core.core_id
        return super().dispatch_task(task)