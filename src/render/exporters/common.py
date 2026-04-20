from __future__ import annotations

from src.sim.scheduler import SchedulingResult
from src.sim.timeline import build_execution_segments

TASK_COLORS = [
    "#FF6B6B",
    "#4ECDC4",
    "#FFE66D",
    "#95E1D3",
    "#F38181",
    "#AA96DA",
    "#FCBAD3",
    "#A8D8EA",
    "#FFAAA5",
    "#98DDCA",
]

NAME_TO_COLOR_IDX: dict[str, int] = {}


def get_color(name: str) -> str:
    if name not in NAME_TO_COLOR_IDX:
        NAME_TO_COLOR_IDX[name] = len(NAME_TO_COLOR_IDX) % len(TASK_COLORS)
    return TASK_COLORS[NAME_TO_COLOR_IDX[name]]


def build_segments(result: SchedulingResult):
    return build_execution_segments(result)

