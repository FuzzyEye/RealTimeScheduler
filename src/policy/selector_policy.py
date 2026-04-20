from __future__ import annotations

from typing import Any, Optional, Callable, List

from src.policy.templates.base import SchedulingPolicy


class SelectorPolicy(SchedulingPolicy):
    """Policy backed by a selector function from `src.registry`.

    This bridges YAML-defined strategies (dynamic/queue/conditional/fallback)
    to the `SchedulingPolicy` interface used by the simulator.
    """

    def __init__(self, selector_fn: Callable[[List[Any], float], Optional[Any]], name: str = "selector"):
        super().__init__()
        self._selector_fn = selector_fn
        self.name = name
        self.description = f"Selector-backed policy ({name})"
        self._current_time: float = 0.0

    def set_current_time(self, current_time: float) -> None:
        self._current_time = float(current_time)

    def _enqueue(self, task: Any) -> None:
        self._queue.append(task)

    def _remove_from_queue(self, task: Any) -> None:
        self._queue = [t for t in self._queue if t is not task]

    def select(self) -> Optional[Any]:
        if not self._queue:
            return None
        return self._selector_fn(self._queue, self._current_time)

