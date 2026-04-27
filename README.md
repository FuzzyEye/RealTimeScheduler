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
# Run with modular config (default: ./config)
python main.py

# Optional: choose another config directory
RTS_CONFIG_DIR=./config python main.py
```

## Configuration

The simulator is fully config-driven. Settings are split by module:

- `config/tasks.yaml`: task set only
- `config/system.yaml`: system/simulation/execution/output/export settings
- `config/policy.yaml`: policy strategy definitions

The snippets below are representative examples. Refer to files under `config/` for the full set.

### `config/tasks.yaml`

```yaml
tasks:
  - name: T1
    period: 4.0
    execution_time: 1.0
    deadline: 4.0
    priority: 1
  - name: T2
    period: 6.0
    execution_time: 2.0
    deadline: 6.0
    priority: 2
```

### `config/system.yaml`

```yaml
system:
  simulation:
    start: 0.0
    end: 24.0                    # simulation horizon
    strategy: edf
    num_processors: 1
    preemptive: true
    params: {}

  execution:
    strategy: edf                 # use one strategy; or "all"
    list_strategies: false

  output:
    mode: console                 # console | png | tikz | all
    width: 70
    output_file: null             # set path to save output
```

### `config/policy.yaml`

```yaml
policy:
  - name: edf
    description: "Earliest Deadline First — selects task with earliest absolute deadline"
    type: dynamic
    selector: earliest_deadline
    params: {}

  - name: llf
    description: "Least Laxity First — selects task with smallest laxity"
    type: dynamic
    selector: least_laxity
    fallback: edf
    params: {}
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
├── sim/                 Event-driven simulation package
│   ├── engine.py        Single-core scheduling engine
│   ├── factory.py       Unified engine factory and run API
│   ├── interfaces.py    Stable engine interface/config contracts
│   ├── scheduler.py     Events and scheduling result models
│   ├── task_builder.py  Task instance construction
│   └── policy_factory.py Policy instantiation
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

## License

MIT
