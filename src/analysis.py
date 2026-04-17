from typing import List, Optional, Dict
from dataclasses import dataclass, field
from src.task import Task


@dataclass
class SchedulabilityResult:
    is_schedulable: bool
    method: str
    utilization: float = 0.0
    bound: float = 0.0
    details: str = ""


class SchedulabilityAnalysis:
    @staticmethod
    def utilization_bound(n: int) -> float:
        return n * (2 ** (1.0 / n) - 1)

    @staticmethod
    def liu_layland_test(tasks: List[Task]) -> SchedulabilityResult:
        periodic = [t for t in tasks if t.is_periodic()]
        if not periodic:
            return SchedulabilityResult(True, "liu_layland", 0.0, 1.0, "No periodic tasks")

        n = len(periodic)
        U = sum(t.execution_time / t.period for t in periodic if t.period > 0)
        U_bound = SchedulabilityAnalysis.utilization_bound(n)

        is_schedulable = U <= U_bound + 1e-9
        return SchedulabilityResult(
            is_schedulable=is_schedulable,
            method="liu_layland",
            utilization=U,
            bound=U_bound,
            details=f"U={U:.3f}, Bound={U_bound:.3f}, n={n}"
        )

    @staticmethod
    def hyperbolic_bound(tasks: List[Task]) -> SchedulabilityResult:
        periodic = [t for t in tasks if t.is_periodic()]
        if not periodic:
            return SchedulabilityResult(True, "hyperbolic", 0.0, 1.0, "No periodic tasks")

        n = len(periodic)
        ui = sorted([t.execution_time / t.period for t in periodic if t.period > 0])
        product = 1.0
        for u in ui:
            product *= (1.0 + u) - 1.0

        U = sum(ui)
        U_bound = 1.0

        is_schedulable = U <= U_bound and product >= -1e-9
        return SchedulabilityResult(
            is_schedulable=is_schedulable,
            method="hyperbolic",
            utilization=U,
            bound=U_bound,
            details=f"U={U:.3f}, Product={product:.3f}, n={n}"
        )

    @staticmethod
    def response_time_analysis(tasks: List[Task]) -> SchedulabilityResult:
        periodic = [t for t in tasks if t.is_periodic()]
        if not periodic:
            return SchedulabilityResult(True, "response_time", 0.0, 1.0, "No periodic tasks")

        sorted_tasks = sorted(periodic, key=lambda t: t.period)

        R = {}
        for t in sorted_tasks:
            C = t.execution_time
            if t.period not in R or R[t.period] < C:
                R[t.period] = C

            for Tj in sorted_tasks:
                if Tj.period <= t.period:
                    if Tj.period in R:
                        R[t.period] += (C / t.period) * R[Tj.period]

            if R[t.period] > t.period:
                return SchedulabilityResult(
                    is_schedulable=False,
                    method="response_time",
                    utilization=sum(x.execution_time / x.period for x in periodic if x.period > 0),
                    bound=t.period,
                    details=f"Task {t.name}: R={R[t.period]:.3f} > D={t.period}"
                )

        return SchedulabilityResult(
            is_schedulable=True,
            method="response_time",
            utilization=sum(t.execution_time / t.period for t in periodic if t.period > 0),
            bound=1.0,
            details=f"All tasks schedulable. Max R={max(R.values()):.3f}"
        )

    @staticmethod
    def edf_schedulability(tasks: List[Task]) -> SchedulabilityResult:
        periodic = [t for t in tasks if t.is_periodic()]
        if not periodic:
            return SchedulabilityResult(True, "edf", 0.0, 1.0, "No periodic tasks")

        U = sum(t.execution_time / t.period for t in periodic if t.period > 0)
        is_schedulable = U <= 1.0 + 1e-9

        return SchedulabilityResult(
            is_schedulable=is_schedulable,
            method="edf",
            utilization=U,
            bound=1.0,
            details=f"U={U:.3f}, Bound=1.0"
        )

    @staticmethod
    def all_tests(tasks: List[Task]) -> Dict[str, SchedulabilityResult]:
        tests = {
            "rms_liu_layland": SchedulabilityAnalysis.liu_layland_test(tasks),
            "rms_hyperbolic": SchedulabilityAnalysis.hyperbolic_bound(tasks),
            "rms_response_time": SchedulabilityAnalysis.response_time_analysis(tasks),
            "edf": SchedulabilityAnalysis.edf_schedulability(tasks),
        }
        return tests


@dataclass
class TaskMetrics:
    name: str
    execution_time: float
    response_time: float
    waiting_time: float
    laxity_at_arrival: float
    deadline: float
    completed: bool
    missed_deadline: bool
    preemptions: int = 0
    arrivals: int = 0


@dataclass
class SimulationMetrics:
    total_time: float
    cpu_utilization: float
    throughput: int
    deadline_misses: int
    waiting_time_avg: float
    waiting_time_max: float
    response_time_avg: float
    response_time_max: float
    response_time_min: float
    response_time_jitter: float
    preemptions: int
    context_switches: int
    idle_time: float
    task_metrics: Dict[str, TaskMetrics] = field(default_factory=dict)
    lateness: float = 0.0

    def to_dict(self) -> dict:
        return {
            "total_time": self.total_time,
            "cpu_utilization": self.cpu_utilization,
            "throughput": self.throughput,
            "deadline_misses": self.deadline_misses,
            "waiting_time_avg": self.waiting_time_avg,
            "waiting_time_max": self.waiting_time_max,
            "response_time_avg": self.response_time_avg,
            "response_time_max": self.response_time_max,
            "response_time_min": self.response_time_min,
            "response_time_jitter": self.response_time_jitter,
            "preemptions": self.preemptions,
            "context_switches": self.context_switches,
            "idle_time": self.idle_time,
            "lateness": self.lateness,
        }


class MetricsCalculator:
    @staticmethod
    def calculate(
        tasks: List[Task],
        result,
        scheduler_result
    ) -> SimulationMetrics:
        total_time = scheduler_result.total_time
        cpu_idle = scheduler_result.cpu_idle_time

        completed = scheduler_result.completed_tasks
        missed = scheduler_result.missed_deadlines

        waiting_times = []
        response_times = []
        preemptions = 0

        task_arrival_times: Dict[tuple, List[float]] = {}
        task_start_times: Dict[tuple, float] = {}
        task_wait_times: Dict[tuple, List[float]] = {}

        for event in scheduler_result.events:
            key = (event.task_name, 0)

            if event.event_type.value == "schedule":
                task_start_times[key] = event.time
                if key in task_arrival_times:
                    arr = task_arrival_times[key][-1]
                    wait = event.time - arr
                    if key not in task_wait_times:
                        task_wait_times[key] = []
                    task_wait_times[key].append(wait)

            elif event.event_type.value == "preempt":
                preemptions += 1

            elif event.event_type.value == "arrival":
                if key not in task_arrival_times:
                    task_arrival_times[key] = []
                task_arrival_times[key].append(event.time)

        all_response_times = list(scheduler_result.task_response_times.values())
        if all_response_times:
            response_times = all_response_times

        waiting_times = []
        for waits in task_wait_times.values():
            waiting_times.extend(waits)

        waiting_avg = sum(waiting_times) / len(waiting_times) if waiting_times else 0.0
        waiting_max = max(waiting_times) if waiting_times else 0.0

        rt_avg = sum(response_times) / len(response_times) if response_times else 0.0
        rt_max = max(response_times) if response_times else 0.0
        rt_min = min(response_times) if response_times else 0.0
        rt_jitter = 0.0
        if len(response_times) > 1:
            avg = rt_avg
            rt_jitter = sum((x - avg) ** 2 for x in response_times) / len(response_times)
            rt_jitter = rt_jitter ** 0.5

        lateness = 0.0
        for task in tasks:
            key = (task.name, task.instance_id)
            if scheduler_result.task_response_times:
                complete_time = scheduler_result.task_completion_times.get(key)
                if complete_time and task.absolute_deadline != float('inf'):
                    lateness = max(lateness, complete_time - task.absolute_deadline)

        cpu_util = (total_time - cpu_idle) / total_time * 100.0 if total_time > 0 else 0.0

        return SimulationMetrics(
            total_time=total_time,
            cpu_utilization=cpu_util,
            throughput=len(completed),
            deadline_misses=len(missed),
            waiting_time_avg=waiting_avg,
            waiting_time_max=waiting_max,
            response_time_avg=rt_avg,
            response_time_max=rt_max,
            response_time_min=rt_min,
            response_time_jitter=rt_jitter,
            preemptions=preemptions,
            context_switches=preemptions + len(completed),
            idle_time=cpu_idle,
            lateness=lateness,
        )