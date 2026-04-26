from typing import Callable, Optional, Dict, Any
from dataclasses import dataclass
from src.task import Task
from src.task_params import (
    get_task_deadline,
    get_task_laxity,
    get_task_absolute_arrival,
    get_task_period,
    get_task_value,
)


SelectorFn = Callable[[list[Task], float], Task | None]


@dataclass
class Selector:
    name: str
    fn: SelectorFn
    description: str = ""


def earliest_deadline_selector(tasks: list[Task], current_time: float) -> Task | None:
    if not tasks:
        return None
    return min(tasks, key=lambda t: t.absolute_deadline)


def least_laxity_selector(tasks: list[Task], current_time: float) -> Task | None:
    if not tasks:
        return None
    return min(tasks, key=lambda t: get_task_laxity(t, current_time))


def earliest_arrival_selector(tasks: list[Task], current_time: float) -> Task | None:
    if not tasks:
        return None
    return min(tasks, key=lambda t: get_task_absolute_arrival(t))


def highest_priority_selector(tasks: list[Task], current_time: float) -> Task | None:
    if not tasks:
        return None
    return min(tasks, key=lambda t: t.priority)


def shortest_period_selector(tasks: list[Task], current_time: float) -> Task | None:
    if not tasks:
        return None
    return min(tasks, key=lambda t: get_task_period(t) if get_task_period(t) is not None else float('inf'))


def shortest_deadline_selector(tasks: list[Task], current_time: float) -> Task | None:
    if not tasks:
        return None
    return min(tasks, key=lambda t: get_task_deadline(t) if get_task_deadline(t) is not None else float('inf'))


def highest_value_selector(tasks: list[Task], current_time: float) -> Task | None:
    if not tasks:
        return None
    return max(tasks, key=lambda t: get_task_value(t, current_time) if get_task_value(t, current_time) is not None else float('-inf'))


def value_based_selector(tasks: list[Task], current_time: float) -> Task | None:
    if not tasks:
        return None
    return max(tasks, key=lambda t: get_task_value(t, current_time) or 0)


SELECTORS: Dict[str, Selector] = {
    "earliest_deadline": Selector("earliest_deadline", earliest_deadline_selector, "Select task with earliest absolute deadline"),
    "least_laxity": Selector("least_laxity", least_laxity_selector, "Select task with smallest laxity"),
    "earliest_arrival": Selector("earliest_arrival", earliest_arrival_selector, "Select task that arrived earliest"),
    "highest_priority": Selector("highest_priority", highest_priority_selector, "Select task with highest priority (lowest number)"),
    "shortest_period": Selector("shortest_period", shortest_period_selector, "Select task with shortest period"),
    "shortest_deadline": Selector("shortest_deadline", shortest_deadline_selector, "Select task with shortest relative deadline"),
    "highest_value": Selector("highest_value", highest_value_selector, "Select task with highest value (Val)"),
    "value_based": Selector("value_based", value_based_selector, "Select task with highest computed value"),
}


def get_selector(name: str) -> SelectorFn:
    if name not in SELECTORS:
        raise ValueError(f"Unknown selector '{name}'. Available: {list(SELECTORS.keys())}")
    return SELECTORS[name].fn
