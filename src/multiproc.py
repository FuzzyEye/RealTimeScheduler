from typing import List, Optional, Dict, Callable
from src.task import Task


class PartitionedScheduler:
    def __init__(self, num_processors: int, partition_strategy: str = "next_fit"):
        self.num_processors = num_processors
        self.partition_strategy = partition_strategy
        self.task_partitions: Dict[int, List[Task]] = {i: [] for i in range(num_processors)}
        self.processor_loads: Dict[int, float] = {i: 0.0 for i in range(num_processors)}

    def partition_tasks(self, tasks: List[Task]) -> Dict[int, List[Task]]:
        periodic_tasks = [t for t in tasks if t.is_periodic()]
        aperiodic_tasks = [t for t in tasks if not t.is_periodic()]

        for task in periodic_tasks:
            util = task.execution_time / task.period if task.period > 0 else task.execution_time
            proc = self._find_processor(util)
            if proc is not None:
                self.task_partitions[proc].append(task)
                self.processor_loads[proc] += util

        for task in aperiodic_tasks:
            proc = self._find_processor(task.execution_time)
            if proc is not None:
                self.task_partitions[proc].append(task)
                self.processor_loads[proc] += task.execution_time / 10.0

        return self.task_partitions

    def _find_processor(self, util: float) -> Optional[int]:
        if self.partition_strategy == "first_fit":
            for i in range(self.num_processors):
                if self.processor_loads[i] + util <= 1.0:
                    return i
            return None
        elif self.partition_strategy == "best_fit":
            best_proc = None
            best_load = float('inf')
            for i in range(self.num_processors):
                load = self.processor_loads[i] + util
                if load <= 1.0 and load < best_load:
                    best_load = load
                    best_proc = i
            return best_proc
        elif self.partition_strategy == "worst_fit":
            max_load = -1
            max_proc = 0
            for i in range(self.num_processors):
                load = self.processor_loads[i]
                if load > max_load:
                    max_load = load
                    max_proc = i
            if max_load + util <= 1.0:
                return max_proc
            return None
        else:
            if self.processor_loads[0] + util <= 1.0:
                return 0
            for i in range(1, self.num_processors):
                if self.processor_loads[i] + util <= 1.0:
                    return i
            return None


class GlobalScheduler:
    def __init__(self, num_processors: int, max_migrations: Optional[int] = None):
        self.num_processors = num_processors
        self.max_migrations = max_migrations
        self.migration_count = 0
        self.last_processor: Dict[str, int] = {}

    def select_for_processor(
        self, ready_queue: List[Task], current_time: float, processor_id: int
    ) -> Optional[Task]:
        if not ready_queue:
            return None

        candidates = []
        for task in ready_queue:
            last_proc = self.last_processor.get(task.name)
            if last_proc != processor_id:
                candidates.append(task)

        if candidates:
            selected = min(
                candidates, key=lambda t: t.absolute_deadline
            )
            return selected

        selected = min(ready_queue, key=lambda t: t.absolute_deadline)
        return selected

    def record_migration(self, task_name: str, from_proc: int, to_proc: int) -> None:
        if self.max_migrations is None or self.migration_count < self.max_migrations:
            self.migration_count += 1
            self.last_processor[task_name] = to_proc

    def can_migrate(self) -> bool:
        return self.max_migrations is None or self.migration_count < self.max_migrations


class PFairScheduler:
    name = "pfair"
    description = "Proportional Fair - optimal multiprocessor scheduling for periodic tasks"

    def schedule(
        self, tasks: List[Task], num_processors: int, current_time: float
    ) -> List[tuple]:
        if not tasks:
            return []

        results = []
        tasks_by_weight = sorted(
            tasks, key=lambda t: t.execution_time / t.period if t.period > 0 else 1.0, reverse=True
        )

        for i, task in enumerate(tasks_by_weight[:num_processors]):
            results.append((task, i % num_processors))

        return results

    def compute_weights(self, tasks: List[Task]) -> Dict[str, float]:
        weights = {}
        for task in tasks:
            if task.period > 0:
                weights[task.name] = task.execution_time / task.period
            else:
                weights[task.name] = 1.0
        return weights


def create_partitioned_scheduler(num_procs: int, strategy: str = "best_fit") -> PartitionedScheduler:
    return PartitionedScheduler(num_processors=num_procs, partition_strategy=strategy)


def create_global_scheduler(num_procs: int, max_migrations: int = 1000) -> GlobalScheduler:
    return GlobalScheduler(num_processors=num_procs, max_migrations=max_migrations)