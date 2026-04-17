# RealTimeScheduler

A Python-based real-time task scheduler simulator supporting multiple scheduling policies (EDF, LLF, RMS, DMS, FCFS, RR) with a polymorphic interface for custom policies.

## Features

- **12 built-in scheduling policies** using task parameter interfaces (T, C, D, Val)
- **Polymorphic task data** via Protocol interfaces - custom policies access task data through standard accessors
- **Flexible Val parameter** - can be static values, callable functions, or computed at runtime
- **Policy-based architecture** - OOP design with `SchedulingPolicy` base class
- **Event-driven simulation** from `start` to `end` timestamp
- **ASCII Gantt chart** with ANSI colors in terminal
- **Metrics**: CPU utilization, throughput, deadline miss count, avg response time

## Quick Start

```bash
# Run with default config
python main.py --config config/tasks.yaml

# Override policy from CLI
python main.py --config config/tasks.yaml --strategy edf --end 24

# Multi-processor (2 CPUs)
python main.py --config config/tasks.yaml --strategy edf --processors 2

# Compare all policies
python main.py --config config/tasks.yaml --strategy all

# List available policies
python main.py --config config/tasks.yaml --list-strategies

# Output formats (default: console/ASCII)
python main.py -c config/tasks.yaml -o png -s edf
python main.py -c config/tasks.yaml -o tikz --output-file my_schedule.tex
python main.py -c config/tasks.yaml -o all -s all
```

## Configuration

All settings live in a single YAML file:

```yaml
# Tasks (periodic + aperiodic)
tasks:
  - name: T1
    period: 4.0
    execution_time: 1.0
    deadline: 4.0
    priority: 1
    value: 10                    # Optional: task value for value-based policies
  - name: A1
    arrival_time: 1.0            # aperiodic
    execution_time: 1.5
    deadline: 5.0
    value: lambda t, ct: 100-ct  # Optional: dynamic value computation

# Simulation parameters
simulation:
  start: 0.0
  end: 24.0
  strategy: edf
  num_processors: 2              # 1 = uniprocessor, 2+ = multiprocessor
```

## Built-in Policies

| Policy | Type | Description |
|--------|------|-------------|
| `edf` | dynamic | Earliest Deadline First |
| `llf` | dynamic | Least Laxity First |
| `llf_threshold` | dynamic | LLF with EDF fallback when laxity > threshold |
| `rms` | fixed_priority | Rate Monotonic Scheduling |
| `dms` | fixed_priority | Deadline Monotonic Scheduling |
| `fcfs` | queue | First Come First Served |
| `rr` | round_robin | Round Robin (configurable quantum) |
| `value_based` | value | Select by highest task value (Val) |
| `highest_value` | value | Select by highest raw value |
| `utility_aware` | value | Combine value with urgency (laxity) |
| `hybrid` | value | Weighted combination of priority, deadline, value |

## Task Parameter Interfaces

Tasks expose parameters through standard interfaces for polymorphic access:

| Interface | Property | Description |
|-----------|-----------|-------------|
| `T` | `period` | Task period |
| `C` | `execution_time` | Computation time |
| `D` | `deadline` | Relative deadline |
| `Val` | `value` | Task value (flexible type) |

```python
from src.task import Task

task = Task(name="T1", execution_time=1.0, period=4.0, deadline=4.0, value=10)

# Direct property access
print(task.T)        # 4.0 (period)
print(task.C)        # 1.0 (execution_time)
print(task.D)        # 4.0 (deadline)
print(task.Val)      # 10 (value)

# Via accessor functions (for polymorphic tasks)
from src.task_params import get_task_period, get_task_value, compute_task_value

print(get_task_period(task))           # 4.0
print(get_task_value(task, 0.0))       # 10
print(compute_task_value(task, 0.0))    # 10 (handles callable values)
```

## Custom Policies

### Using the Policy Base Class

Create `src/policy/my_policy.py`:

```python
from typing import Optional, Any, List
from src.policy.templates.base import SchedulingPolicy
from src.task_params import get_task_value, get_task_laxity

class MyValuePolicy(SchedulingPolicy):
    name = "my_value"
    description = "Select task with highest value-to-laxity ratio"

    def select(self, ready_queue: List[Any], current_time: float) -> Optional[Any]:
        if not ready_queue:
            return None

        def value_urgency_ratio(task):
            val = get_task_value(task, current_time) or 0
            laxity = get_task_laxity(task, current_time)
            if laxity <= 0:
                return float('inf')
            return val / laxity

        return max(ready_queue, key=value_urgency_ratio)
```

Register in `src/policy/__init__.py`:

```python
from src.policy.my_policy import MyValuePolicy, my_value_factory

policy_registry.register(MyValuePolicy, my_value_factory)
```

### Using Template Classes

```python
from src.policy.templates import UtilityAwareTemplate

class MyUtilityPolicy(UtilityAwareTemplate):
    name = "my_utility"
    description = "Custom utility-aware policy"

    def __init__(self, urgency_weight: float = 0.6, value_weight: float = 0.4):
        super().__init__(urgency_weight, value_weight)
```

## Architecture

```
src/
├── task.py              Task dataclass with T, C, D, Val interfaces
├── task_params.py       Protocol interfaces and accessor functions
├── config.py            YAML config models
├── selectors.py         Built-in selector functions
├── registry.py          StrategyRegistry (loads from YAML)
├── plugins.py           Python plugin loader
├── simulator.py         Event-driven simulation engine
├── formatters.py        ASCII Gantt + metrics display
└── policy/
    ├── __init__.py      Main exports, policy_registry
    ├── edf.py           EDFPolicy
    ├── llf.py           LLFPolicy, LLFThresholdPolicy
    ├── priority.py      RMSPolicy, DMSPolicy, FixedPriorityPolicy
    ├── fcfs.py          FCFSPolicy
    ├── rr.py            RoundRobinPolicy
    ├── value.py         ValueBasedPolicy, UtilityAwarePolicy, HybridPolicy
    └── templates/
        ├── __init__.py  Template exports
        ├── base.py      SchedulingPolicy ABC, PolicyRegistry
        └── examples.py  Example implementations
```

## Testing

```bash
python -m pytest tests/ -v
# or
python tests/test_schedulers.py
python tests/test_plugin_system.py
```

## License

MIT
