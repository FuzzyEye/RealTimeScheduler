from __future__ import annotations

from typing import List, Tuple

from src.sim.scheduler import EventType, SchedulingResult


def build_execution_segments(result: SchedulingResult) -> List[Tuple[float, float, str]]:
    segments: List[Tuple[float, float, str]] = []
    running_task = None
    segment_start = 0.0
    sorted_events = sorted(result.events, key=lambda e: e.time)

    for event in sorted_events:
        if event.event_type == EventType.SCHEDULE:
            if running_task is not None and segment_start < event.time:
                segments.append((segment_start, event.time, running_task))
            running_task = event.task_name
            segment_start = event.time
        elif event.event_type in (EventType.COMPLETE, EventType.PREEMPT, EventType.QUANTUM_EXPIRE):
            if running_task == event.task_name:
                segments.append((segment_start, event.time, running_task))
                running_task = None
                segment_start = event.time

    if running_task is not None:
        segments.append((segment_start, result.total_time, running_task))
    return segments

