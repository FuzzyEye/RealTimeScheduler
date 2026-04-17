from typing import Optional, Dict, Any
from src.selectors import get_selector, SELECTORS
from src.task_params import get_task_laxity, get_task_absolute_deadline


class StrategyRegistry:
    def __init__(self):
        self._strategies: Dict[str, Dict[str, Any]] = {}

    def register(self, name: str, definition: Dict[str, Any]) -> None:
        self._strategies[name] = definition

    def get(self, name: str) -> Optional[Dict[str, Any]]:
        return self._strategies.get(name)

    def list_names(self) -> list[str]:
        return list(self._strategies.keys())

    def list_strategies(self) -> Dict[str, Dict[str, Any]]:
        return dict(self._strategies)

    def validate(self, name: str) -> tuple[bool, str]:
        if name not in self._strategies:
            return False, f"Strategy '{name}' not found. Available: {self.list_names()}"

        s = self._strategies[name]
        stype = s.get("type")

        if stype == "dynamic":
            if "selector" not in s:
                return False, f"Dynamic strategy '{name}' missing 'selector'"
            if s["selector"] not in SELECTORS:
                return False, f"Unknown selector '{s['selector']}' in strategy '{name}'"
            if s.get("fallback") and s["fallback"] not in self._strategies:
                return False, f"Unknown fallback '{s['fallback']}' in strategy '{name}'"
            return True, ""

        elif stype == "fixed_priority":
            if "priority_key" not in s:
                return False, f"Fixed priority strategy '{name}' missing 'priority_key'"
            return True, ""

        elif stype == "queue":
            if "selector" not in s:
                return False, f"Queue strategy '{name}' missing 'selector'"
            return True, ""

        elif stype == "round_robin":
            quantum = s.get("params", {}).get("quantum")
            if quantum is not None and quantum <= 0:
                return False, f"Round robin strategy '{name}' has invalid quantum <= 0"
            return True, ""

        elif stype == "conditional":
            for branch in ["true_branch", "false_branch"]:
                if s.get(branch) and s[branch] not in self._strategies:
                    return False, f"Unknown {branch} '{s[branch]}' in strategy '{name}'"
            return True, ""

        elif stype == "plugin":
            if not s.get("module") or not s.get("class_name"):
                return False, f"Plugin strategy '{name}' missing 'module' or 'class_name'"
            return True, ""

        else:
            return False, f"Unknown strategy type '{stype}' in '{name}'"

    def build_selector(self, name: str) -> Any:
        s = self._strategies[name]
        stype = s["type"]

        if stype == "dynamic":
            selector_fn = get_selector(s["selector"])
            fallback_name = s.get("fallback")
            params = s.get("params", {})

            def dynamic_wrapper(tasks, current_time):
                result = selector_fn(tasks, current_time)
                if result is not None or fallback_name is None:
                    return result
                return self.build_selector(fallback_name)(tasks, current_time)

            return dynamic_wrapper

        elif stype == "fixed_priority":
            key = s["priority_key"]
            return lambda tasks, current_time: (
                min(tasks, key=lambda t: getattr(t, key, float('inf'))) if tasks else None
            )

        elif stype == "queue":
            selector_fn = get_selector(s["selector"])
            return selector_fn

        elif stype == "round_robin":
            quantum = s.get("params", {}).get("quantum", 1.0)
            return lambda tasks, current_time: (
                tasks[0] if tasks else None
            ), quantum

        elif stype == "conditional":
            cond = s.get("condition", {})
            metric = cond.get("metric")
            operator = cond.get("operator")
            value = cond.get("value")

            def conditional_wrapper(tasks, current_time):
                if not tasks:
                    return None
                if metric == "laxity":
                    min_laxity = min(tasks, key=lambda t: get_task_laxity(t, current_time)).laxity(current_time) if tasks else float('inf')
                    check_val = min_laxity
                elif metric == "deadline":
                    check_val = min(tasks, key=lambda t: get_task_absolute_deadline(t)).absolute_deadline
                else:
                    check_val = 0.0

                op_map = {"lt": lambda a, b: a < b, "le": lambda a, b: a <= b,
                          "gt": lambda a, b: a > b, "ge": lambda a, b: a >= b}
                if op_map.get(operator, lambda a, b: False)(check_val, value):
                    return self.build_selector(s["true_branch"])(tasks, current_time)
                else:
                    return self.build_selector(s["false_branch"])(tasks, current_time)

            return conditional_wrapper

        else:
            raise ValueError(f"Cannot build selector for type '{stype}'")


registry = StrategyRegistry()
