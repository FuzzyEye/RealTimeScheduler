from typing import Optional, Any, List, Dict
from dataclasses import dataclass, field
from src.policy.templates.base import SchedulingPolicy


@dataclass
class ServerState:
    server_id: str
    bandwidth: float
    runtime: float = 0.0
    period: float = 0.0
    deadline: float = float('inf')
    active: bool = False
    current_task: Optional[Any] = None


class CBSQueue:
    def __init__(self, servers: List[ServerState]):
        self.servers = servers

    def get_next_server(self, current_time: float) -> Optional[ServerState]:
        for server in self.servers:
            if server.active:
                return server
        return None if not self.servers else self.servers[0] else None

    def consume_budget(self, server: ServerState, dt: float) -> None:
        server.runtime -= dt
        if server.runtime <= 0:
            server.deadline = current_time + server.period
            server.runtime = server.bandwidth * server.period

    def replenish(self, server: ServerState, current_time: float) -> None:
        if server.runtime <= 0:
            server.deadline = current_time + server.period
            server.runtime = server.bandwidth * server.period
            server.active = True


class CBSPolicy(SchedulingPolicy):
    name = "cbs"
    description = "Constant Bandwidth Server - provides proportional share to each task/flow"

    def __init__(self, default_budget: float = 1.0, period: float = 4.0):
        self.bandwidth_per_server: Dict[str, float] = {}
        self.server_states: Dict[str, ServerState] = {}
        self.pending_requests: Dict[str, List[Any]] = {}
        self.current_time: float = 0.0

    def select(self, ready_queue: List[Any], current_time: float) -> Optional[Any]:
        if not ready_queue:
            return None
        return min(ready_queue, key=lambda t: t.absolute_deadline)

    def register_task(self, task_name: str, bandwidth: float) -> None:
        if task_name not in self.server_states:
            self.server_states[task_name] = ServerState(
                server_id=task_name,
                bandwidth=bandwidth,
                runtime=bandwidth,
            )
            self.pending_requests[task_name] = []
            self.bandwidth_per_server[task_name] = bandwidth

    def on_completion(self, task_name: str, current_time: float) -> None:
        if task_name in self.server_states:
            server = self.server_states[task_name]
            server.active = False


class WeightedFairQueuePolicy(SchedulingPolicy):
    name = "wfq"
    description = "Weighted Fair Queuing - approximates fluid GPS (Generalized Processor Sharing)"

    def __init__(self, weights: Optional[Dict[str, float]] = None):
        self.weights = weights or {}
        self.virtual_finish_times: Dict[str, float] = {}

    def select(self, ready_queue: List[Any], current_time: float) -> Optional[Any]:
        if not ready_queue:
            return None

        for task in ready_queue:
            name = task.name
            if name not in self.virtual_finish_times:
                weight = self.weights.get(name, 1.0)
                self.virtual_finish_times[name] = current_time + task.execution_time / weight

        min_task = min(ready_queue, key=lambda t: self.virtual_finish_times.get(t.name, float('inf')))
        weight = self.weights.get(min_task.name, 1.0)
        self.virtual_finish_times[min_task.name] = self.virtual_finish_times[min_task.name] + min_task.execution_time / weight

        return min_task


class CBSimplePolicy(SchedulingPolicy):
    name = "cbsimple"
    description = "Simple CBS - uses a single bandwidth server with all tasks treated equally"

    def select(self, ready_queue: List[Any], current_time: float) -> Optional[Any]:
        if not ready_queue:
            return None
        return min(ready_queue, key=lambda t: t.absolute_deadline)


def cbs_factory(params=None):
    budget = params.get('budget', 1.0) if params else 1.0
    period = params.get('period', 4.0) if params else 4.0
    return CBSPolicy(default_budget=budget, period=period)


def wfq_factory(params=None):
    weights = params.get('weights', {}) if params else {}
    return WeightedFairQueuePolicy(weights=weights)