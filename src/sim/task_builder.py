from __future__ import annotations

from typing import List

from src.core.config import ConfigTask
from src.core.task import Task


def build_tasks(config_tasks: List[ConfigTask], start: float, end: float) -> List[Task]:
    result: List[Task] = []
    for ct in config_tasks:
        if ct.period is not None and ct.period > 0:
            if ct.arrival_time < end:
                result.append(
                    Task(
                        name=ct.name,
                        execution_time=ct.execution_time,
                        period=ct.period,
                        deadline=ct.deadline,
                        priority=ct.priority,
                        arrival_time=ct.arrival_time,
                        instance_id=0,
                        value=ct.value,
                    )
                )
        else:
            result.append(
                Task(
                    name=ct.name,
                    execution_time=ct.execution_time,
                    period=None,
                    deadline=ct.deadline,
                    priority=ct.priority,
                    arrival_time=ct.arrival_time,
                    instance_id=0,
                    value=ct.value,
                )
            )
    return result

